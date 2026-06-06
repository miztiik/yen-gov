"""Lift LGD_Subdistricts.geojsonl into 36 per-state Hive shards.

Phase B of ``TODO/20260524-boundary-coverage-expansion-plan.md``: extend
the existing TN-only sub-district adoption (~5,084 features in
``boundaries/in/subdistricts/state=tamil-nadu/all.geojson``) to all 36
states/UTs by emitting per-state shards keyed by ECI state code
(``state=himachal-pradesh/...``, ``state=delhi/...``, etc).

Why a dedicated one-shot orchestrator rather than extending
``tools/boundaries/snapshot.py``:

* The per-state shard emission requires resolving each feature's
  numeric ``state_lgd`` property (e.g. ``2``) to an ECI state code
  (``S08``) via a lookup against ``datasets/taxonomy/entities.json``.
  ``snapshot.py``'s existing ``split_by`` machinery emits shards keyed
  by the raw group key (e.g. ``district=603``), not by a value derived
  from a per-row lookup against another canonical table.
* Adding the resolver into ``snapshot.py``'s per-pipeline-entry orchestrator
  would require either teaching ``derive_hive`` about state-code
  resolution or layering a new pipeline.json field semantics. Both are
  larger changes than the one-shot lift this PR ships, and Phase C
  (village lift) can independently choose to invoke this script or
  reuse a generalised snapshot.py extension after Phase B's pattern
  stabilises.
* This script reuses ``snapshot.py``'s public primitives
  (``fetch_geojsonl_7z``, ``emit_feature_collection``,
  ``_round_coords_geom``, ``SNAPSHOT_BYTE_BUDGET``) so the citizen-side
  byte format and the budget gate stay byte-for-byte identical to what
  ``snapshot.py`` produces.

Inputs:
    .runtime/raw/boundaries/snapshot/<bundle>/LGD_Subdistricts.geojsonl.7z
        (fetched if missing)
    datasets/taxonomy/entities.json
        (state_lgd -> ECI state code mapping)
    datasets/boundaries/boundary_layers.parquet
        (existing rows; merged via merge_with_existing=True)

Outputs:
    datasets/boundaries/in/subdistricts/state=in_<sNN>/all.geojson
        (one per state/UT that has any retained subdistricts)
    datasets/boundaries/boundary_layers.parquet
        (new per-state rows added; existing TN row replaced by same-PK
        new row; all other rows preserved)
    datasets/data/entities/source.csv
        (UPSERTed by compile_to_parquet; ramSeraph row unchanged from
        prior runs)

Determinism: features per shard are sorted by
``(subdt_lgd, sdtname)`` before emit; coordinates rounded to
``coord_precision=3`` (~110 m); same byte format as snapshot.py. Two
consecutive runs against the same upstream archive produce
byte-identical shards.

Pure stdlib + duckdb (via the canonical writer) + py7zr (via
fetch_geojsonl_7z). No external HTTP libs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------
# import dance: this is a top-level script in tools/boundaries/, but it
# wants both the local helpers (snapshot, _paths) and the canonical
# writer in backend/yen_gov/. Put both on sys.path before doing the
# imports so the script works whether invoked from repo root or its own
# directory.
# ---------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
BACKEND = REPO_ROOT / "backend"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# local helpers (tools/boundaries/_paths.py, tools/boundaries/snapshot.py)
from _paths import derive_hive  # noqa: E402
from snapshot import (  # noqa: E402
    SNAPSHOT_BYTE_BUDGET,
    _round_coords_geom,
    emit_feature_collection,
    fetch_geojsonl_7z,
)

# canonical writer
from yen_gov.canonical.boundary_layers_seed import (  # noqa: E402
    BOUNDARY_SOURCE_ID_BY_NICKNAME,
    BoundaryLayerRow,
    compile_to_parquet,
)
from yen_gov.canonical.state_lgd_resolver import (  # noqa: E402
    load_state_lgd_to_eci_map,
)

# ---------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------

LGD_SUBDISTRICTS_URL = (
    "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/"
    "subdistricts/LGD_Subdistricts.geojsonl.7z"
)

# 3 decimal places ≈ 110 m at the equator; matches the existing TN
# entry's coord_precision so the byte format is stable across the lift.
COORD_PRECISION = 3

RAMSERAPH_SOURCE_ID = BOUNDARY_SOURCE_ID_BY_NICKNAME["ramseraph"]


# ---------------------------------------------------------------------
# pure logic — testable without I/O
# ---------------------------------------------------------------------


def group_features_by_state_lgd(
    features: list[dict[str, Any]],
) -> tuple[dict[int, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Group features by ``state_lgd`` property.

    Returns ``(groups, unkeyed)`` where ``unkeyed`` holds features with
    no ``state_lgd`` (or ``None``). Coerces the property to int so callers
    can rely on integer keys regardless of upstream string/int variation.
    """
    groups: dict[int, list[dict[str, Any]]] = {}
    unkeyed: list[dict[str, Any]] = []
    for f in features:
        v = f.get("properties", {}).get("state_lgd")
        if v is None or v == "":
            unkeyed.append(f)
            continue
        groups.setdefault(int(v), []).append(f)
    return groups, unkeyed


def sort_features_deterministically(
    features: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sort features by ``(subdt_lgd, sdtname)`` for byte-determinism.

    Subdistrict LGD codes are globally unique within India per the LGD
    scheme, so ``subdt_lgd`` alone gives a total order. The secondary
    ``sdtname`` key only matters if two rows happen to share an LGD code
    (a data bug we want to surface deterministically rather than
    interleave randomly).
    """
    return sorted(
        features,
        key=lambda f: (
            int(f.get("properties", {}).get("subdt_lgd") or 0),
            f.get("properties", {}).get("sdtname", "") or "",
        ),
    )


# ---------------------------------------------------------------------
# main orchestration
# ---------------------------------------------------------------------


def lift_subdistricts_to_per_state_shards(
    geojsonl_path: Path,
    state_lgd_to_eci: dict[int, str],
    datasets_root: Path,
    *,
    coord_precision: int = COORD_PRECISION,
) -> list[BoundaryLayerRow]:
    """Parse the national geojsonl, group by state_lgd, emit per-state shards.

    Returns one ``BoundaryLayerRow`` per emitted shard. Features whose
    ``state_lgd`` doesn't map to any current state (e.g. historic codes,
    upstream data drift) are tallied in the log but do NOT emit a shard.
    Features with no ``state_lgd`` at all are reported as unkeyed.
    """
    import json  # local import to keep the module-level imports tight

    features: list[dict[str, Any]] = []
    with geojsonl_path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            feat = json.loads(line)
            if "geometry" in feat and feat["geometry"]:
                feat["geometry"] = _round_coords_geom(feat["geometry"], coord_precision)
            features.append(feat)

    print(f"  parsed {len(features):,} subdistrict features", flush=True)

    groups, unkeyed_no_prop = group_features_by_state_lgd(features)
    print(
        f"  grouped into {len(groups)} state_lgd buckets "
        f"({len(unkeyed_no_prop)} feature(s) lack state_lgd)",
        flush=True,
    )

    unknown_state_lgd = sorted(set(groups) - set(state_lgd_to_eci))
    if unknown_state_lgd:
        unknown_total = sum(len(groups[k]) for k in unknown_state_lgd)
        print(
            f"  WARNING: {len(unknown_state_lgd)} state_lgd value(s) not in "
            f"ECI map ({unknown_total} feature(s)): {unknown_state_lgd}",
            flush=True,
        )

    rows: list[BoundaryLayerRow] = []
    simpl_tol = 10**-coord_precision

    # Emit in deterministic ECI order (S01, S02, ..., U01, ...).
    for lgd in sorted(state_lgd_to_eci):
        eci = state_lgd_to_eci[lgd]
        bucket = groups.get(lgd, [])
        if not bucket:
            print(f"    {eci} (lgd={lgd:>3}): 0 features — SKIP", flush=True)
            continue
        partition_path, layer_id = derive_hive(
            kind="subdistricts",
            state=eci,
        )
        bucket_sorted = sort_features_deterministically(bucket)
        shard_path = datasets_root / partition_path
        emit_feature_collection(shard_path, bucket_sorted)
        size = shard_path.stat().st_size
        if size > SNAPSHOT_BYTE_BUDGET:
            shard_path.unlink()
            print(
                f"    {eci} (lgd={lgd:>3}): shard {size / 1024 / 1024:.1f} MB "
                f"exceeds {SNAPSHOT_BYTE_BUDGET / 1024 / 1024:.0f} MB budget — SKIP",
                flush=True,
            )
            continue
        retained = len(bucket_sorted)
        rows.append(
            BoundaryLayerRow(
                layer_id=layer_id,
                level="subdistrict",
                partition_path=partition_path,
                format="geojson",
                crs="EPSG:4326",
                original_feature_count=retained,
                retained_feature_count=retained,
                unkeyed_count=0,
                size_bytes=size,
                source_id=RAMSERAPH_SOURCE_ID,
                entity_state=eci,
                simplification_algorithm="coord-precision-round",
                simplification_tolerance_deg=simpl_tol,
            )
        )
        print(
            f"    {eci} (lgd={lgd:>3}): {retained:>5} features, "
            f"{size / 1024:>7.0f} KB",
            flush=True,
        )

    return rows


def remove_stale_shards(subdistricts_dir: Path, keep_partition_paths: set[str]) -> int:
    """Delete any ``subdistricts/state=in_*/all.geojson`` shard not in the keep set.

    The lift replaces the entire subdistricts tree, so stale shards from
    a prior lift run (or the legacy TN-only entry that's now superseded
    via same-PK replacement) would otherwise persist on disk. Returns
    the count of files deleted.
    """
    if not subdistricts_dir.exists():
        return 0
    deleted = 0
    for shard in list(subdistricts_dir.rglob("all.geojson")):
        rel = shard.relative_to(subdistricts_dir.parent.parent.parent).as_posix()
        if rel in keep_partition_paths:
            continue
        shard.unlink()
        deleted += 1
        try:
            shard.parent.rmdir()  # remove empty state=in_* dir
        except OSError:
            pass
    return deleted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lift LGD_Subdistricts.geojsonl into 36 per-state Hive shards.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repo root (default: cwd).",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help=(
            "Skip the upstream fetch; require the geojsonl.7z to already be "
            "on disk under .runtime/raw/boundaries/snapshot/. Useful when "
            "iterating locally to avoid re-downloading 60 MB."
        ),
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    datasets_root = root / "datasets"
    entities_path = datasets_root / "taxonomy" / "entities.json"
    raw_root = root / ".runtime" / "raw" / "boundaries"

    print(f"[lift_subdistricts_national] root={root}", flush=True)
    print(f"  entities: {entities_path}", flush=True)

    state_lgd_to_eci = load_state_lgd_to_eci_map(entities_path)
    print(f"  loaded {len(state_lgd_to_eci)} state_lgd -> ECI mappings", flush=True)

    # bundle dir matches snapshot.py's TN entry so the cached archive +
    # extraction are reused if the prior TN snapshot already ran.
    bundle_dir = raw_root / "snapshot" / "S22-subdistricts"
    extracted_geojsonl = bundle_dir / "_extracted" / "LGD_Subdistricts.geojsonl"

    if not extracted_geojsonl.exists() and args.skip_fetch:
        print(
            f"  ERROR: --skip-fetch but no geojsonl at {extracted_geojsonl}",
            file=sys.stderr,
            flush=True,
        )
        return 2

    if not extracted_geojsonl.exists():
        print(f"  fetching + extracting {LGD_SUBDISTRICTS_URL}", flush=True)
        # fetch_geojsonl_7z returns (features, sources) but we don't want
        # to hold all 7,000 features in memory pre-coord-round; the
        # bundle_dir-side _extracted file is the side-effect we actually
        # consume. Discard the in-memory result.
        _ = fetch_geojsonl_7z(
            [LGD_SUBDISTRICTS_URL],
            bundle_dir,
            coord_precision=None,  # round in lift loop, not here
        )

    rows = lift_subdistricts_to_per_state_shards(
        extracted_geojsonl,
        state_lgd_to_eci,
        datasets_root,
    )

    keep_paths = {row.partition_path for row in rows}
    subdistricts_dir = datasets_root / "boundaries" / "in" / "subdistricts"
    deleted = remove_stale_shards(subdistricts_dir, keep_paths)
    if deleted:
        print(f"  removed {deleted} stale shard(s) not in the lift output", flush=True)

    layer_count, source_count = compile_to_parquet(
        rows,
        datasets_root,
        merge_with_existing=True,
    )
    print(
        f"  boundary_layers.parquet: {layer_count} rows total "
        f"({len(rows)} subdistrict rows this lift) | "
        f"sources.parquet: {source_count} rows",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
