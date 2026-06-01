"""Lift LGD_Villages.geojsonl into per-state/per-district Hive shards.

Phase C of ``TODO/20260524-boundary-coverage-expansion-plan.md``: extend
the existing TN-only village adoption (38 per-district shards under
``boundaries/in/villages/state=tamil-nadu/district=*/all.geojson``) to all
states/UTs where ramSeraph publishes village geometry. Per the plan,
upstream coverage gap (HP, J&K, Sikkim, ML, MZ, MN, NL, AR — 8
states/UTs) is acknowledged and tracked separately via a recon note;
bhuvan fall-back is OUT OF SCOPE for Phase C.

Why a dedicated one-shot orchestrator (mirrors Phase B's
``lift_subdistricts_national.py`` rationale):

* Each village feature carries both ``state_lgd`` and ``dist_lgd``
  properties. The output partition is keyed by ECI state code resolved
  via ``state_lgd_resolver`` and the LGD district code passed through
  unchanged (``state=in_<sNN>/district=<lgd>/`` two-level Hive). The
  resolution step is the same canonical-table lookup Phase B used; this
  script just adds a second partition level.
* ``snapshot.py``'s ``split_by`` machinery emits a flat key-set with no
  parent partition (the existing TN entry hard-codes
  ``state_filter={state_lgd:33}`` then splits by ``dist_lgd``); a
  multi-state lift would either require teaching snapshot.py about
  per-row state resolution OR a separate orchestrator. We chose the
  latter because Phase B set the precedent and the two-level nesting
  works cleanly with ``_paths.derive_hive(kind="villages", state=eci,
  district_lgd=str(lgd))``.
* Reuses ``snapshot.py``'s public primitives so byte format + budget
  gate stay byte-identical with the TN entry's prior output.

Inputs:
    .runtime/raw/boundaries/snapshot/<bundle>/LGD_Villages.geojsonl.7z
        (fetched if missing; large — ~60 MB compressed / ~1.8 GB
        extracted)
    datasets/taxonomy/entities.json
        (state_lgd -> ECI state code mapping)
    datasets/boundaries/boundary_layers.parquet
        (existing rows; merged via ``merge_with_existing=True``)

Outputs:
    datasets/boundaries/in/villages/state=in_<sNN>/district=<lgd>/all.geojson
        (one per (state, district) combination that has any retained
        village features)
    datasets/boundaries/boundary_layers.parquet
        (new per-(state,district) rows added; existing 38 TN rows
        replaced by same-PK new rows; all other layers preserved)
    datasets/taxonomy/sources.parquet
        (UPSERTed by compile_to_parquet; ramSeraph row unchanged from
        prior runs)

Determinism: features per shard are sorted by ``(village_lgd, vlgname)``
before emit; coordinates rounded to ``coord_precision=4`` (~11 m, matches
the existing TN entry); same byte format as snapshot.py. Two consecutive
runs against the same upstream archive produce byte-identical shards.

Memory note: parses + holds all ~360k features in memory during the
group-by pass (~3 GB peak). Acceptable on dev machines; if it becomes
a constraint later, the loop can be split into an upstream pass that
buckets feature byte-offsets and a per-bucket emission pass.

Pure stdlib + duckdb (via the canonical writer) + py7zr (via
fetch_geojsonl_7z). No external HTTP libs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------
# import dance — see lift_subdistricts_national.py for rationale.
# ---------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
BACKEND = REPO_ROOT / "backend"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from _paths import derive_hive  # noqa: E402
from snapshot import (  # noqa: E402
    SNAPSHOT_BYTE_BUDGET,
    _round_coords_geom,
    emit_feature_collection,
    fetch_geojsonl_7z,
)

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

LGD_VILLAGES_URL = (
    "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/"
    "villages/LGD_Villages.geojsonl.7z"
)

# 4 decimal places ≈ 11 m at the equator; matches the existing TN
# entry's coord_precision so byte format is stable across the lift.
# Villages are physically smaller than subdistricts so a coarser
# precision would over-simplify visible polygon edges.
COORD_PRECISION = 4

RAMSERAPH_SOURCE_ID = BOUNDARY_SOURCE_ID_BY_NICKNAME["ramseraph"]


# ---------------------------------------------------------------------
# pure logic — testable without I/O
# ---------------------------------------------------------------------


def group_features_by_state_and_district(
    features: list[dict[str, Any]],
) -> tuple[dict[tuple[int, int], list[dict[str, Any]]], list[dict[str, Any]]]:
    """Group features by ``(state_lgd, dist_lgd)`` tuple.

    Returns ``(groups, unkeyed)`` where ``unkeyed`` holds features
    missing EITHER ``state_lgd`` OR ``dist_lgd`` (or both). Coerces
    both keys to int so callers can rely on integer tuples regardless
    of upstream string/int variation.
    """
    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    unkeyed: list[dict[str, Any]] = []
    for f in features:
        props = f.get("properties", {})
        s = props.get("state_lgd")
        d = props.get("dist_lgd")
        if s is None or s == "" or d is None or d == "":
            unkeyed.append(f)
            continue
        groups.setdefault((int(s), int(d)), []).append(f)
    return groups, unkeyed


def sort_features_deterministically(
    features: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sort features by ``(village_lgd, vlgname)`` for byte-determinism.

    Village LGD codes are globally unique within India per the LGD
    scheme, so ``village_lgd`` alone gives a total order. The secondary
    ``vlgname`` key only matters if two rows happen to share an LGD
    code (a data bug we want to surface deterministically rather than
    interleave randomly).
    """
    return sorted(
        features,
        key=lambda f: (
            int(f.get("properties", {}).get("village_lgd") or 0),
            f.get("properties", {}).get("vlgname", "") or "",
        ),
    )


# ---------------------------------------------------------------------
# main orchestration
# ---------------------------------------------------------------------


def lift_villages_to_per_district_shards(
    geojsonl_path: Path,
    state_lgd_to_eci: dict[int, str],
    datasets_root: Path,
    *,
    coord_precision: int = COORD_PRECISION,
) -> list[BoundaryLayerRow]:
    """Parse the national geojsonl, group by (state, district), emit per shard.

    Returns one ``BoundaryLayerRow`` per emitted shard. Features whose
    ``state_lgd`` doesn't map to a currently-valid state (e.g. historic
    codes, upstream data drift) are tallied + WARN-logged but do NOT
    emit a shard. Features lacking ``state_lgd`` or ``dist_lgd`` are
    reported as unkeyed.
    """
    import json

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

    print(f"  parsed {len(features):,} village features", flush=True)

    groups, unkeyed_no_prop = group_features_by_state_and_district(features)
    print(
        f"  grouped into {len(groups):,} (state, district) buckets "
        f"({len(unkeyed_no_prop)} feature(s) lack state_lgd/dist_lgd)",
        flush=True,
    )

    # free the parsed list — groups now owns every feature dict.
    del features

    unknown_state_lgd = sorted(
        {s for (s, _d) in groups} - set(state_lgd_to_eci)
    )
    if unknown_state_lgd:
        unknown_total = sum(
            len(v) for (s, _d), v in groups.items() if s in unknown_state_lgd
        )
        print(
            f"  WARNING: {len(unknown_state_lgd)} state_lgd value(s) not in "
            f"ECI map ({unknown_total} feature(s)): {unknown_state_lgd}",
            flush=True,
        )

    rows: list[BoundaryLayerRow] = []
    simpl_tol = 10**-coord_precision

    # Per-state counts for the summary; emit in deterministic
    # (ECI state, district_lgd) order.
    per_state_count: dict[str, int] = {}
    per_state_features: dict[str, int] = {}

    # Iterate ECI states in deterministic order so the lift output is
    # readable per-state; within a state, districts in numeric order.
    for state_lgd in sorted(state_lgd_to_eci):
        eci = state_lgd_to_eci[state_lgd]
        state_districts = sorted(
            d for (s, d) in groups if s == state_lgd
        )
        if not state_districts:
            continue
        for dist_lgd in state_districts:
            bucket = groups[(state_lgd, dist_lgd)]
            partition_path, layer_id = derive_hive(
                kind="villages",
                state=eci,
                district_lgd=str(dist_lgd),
            )
            bucket_sorted = sort_features_deterministically(bucket)
            shard_path = datasets_root / partition_path
            emit_feature_collection(shard_path, bucket_sorted)
            size = shard_path.stat().st_size
            if size > SNAPSHOT_BYTE_BUDGET:
                shard_path.unlink()
                print(
                    f"    {eci}/d={dist_lgd:>4}: shard {size / 1024 / 1024:.1f} MB "
                    f"exceeds {SNAPSHOT_BYTE_BUDGET / 1024 / 1024:.0f} MB budget — SKIP",
                    flush=True,
                )
                continue
            retained = len(bucket_sorted)
            rows.append(
                BoundaryLayerRow(
                    layer_id=layer_id,
                    level="village",
                    partition_path=partition_path,
                    format="geojson",
                    crs="EPSG:4326",
                    original_feature_count=retained,
                    retained_feature_count=retained,
                    unkeyed_count=0,
                    size_bytes=size,
                    source_id=RAMSERAPH_SOURCE_ID,
                    entity_state=eci,
                    entity_district=str(dist_lgd),
                    simplification_algorithm="coord-precision-round",
                    simplification_tolerance_deg=simpl_tol,
                )
            )
            per_state_count[eci] = per_state_count.get(eci, 0) + 1
            per_state_features[eci] = per_state_features.get(eci, 0) + retained
        print(
            f"    {eci}: {per_state_count.get(eci, 0):>3} districts, "
            f"{per_state_features.get(eci, 0):>6,} villages",
            flush=True,
        )

    return rows


def remove_stale_shards(villages_dir: Path, keep_partition_paths: set[str]) -> int:
    """Delete any village shard not in the keep set.

    The lift replaces the entire villages tree, so stale shards from a
    prior lift run (or the legacy TN-only entries that are now
    superseded via same-PK replacement) would otherwise persist on
    disk. Returns the count of files deleted.
    """
    if not villages_dir.exists():
        return 0
    deleted = 0
    for shard in list(villages_dir.rglob("all.geojson")):
        # partition_path keys in the parquet are repo-relative POSIX
        # rooted at boundaries/in/...; reconstruct the same shape from
        # the absolute shard path.
        rel = shard.relative_to(villages_dir.parent.parent.parent).as_posix()
        if rel in keep_partition_paths:
            continue
        shard.unlink()
        deleted += 1
        # opportunistically remove now-empty district= dir, then the
        # parent state= dir if also empty. rmdir silently fails on
        # non-empty so this is safe.
        try:
            shard.parent.rmdir()
        except OSError:
            pass
        try:
            shard.parent.parent.rmdir()
        except OSError:
            pass
    return deleted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Lift LGD_Villages.geojsonl into per-state/per-district Hive shards."
        ),
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
            "iterating locally to avoid re-downloading ~60 MB."
        ),
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    datasets_root = root / "datasets"
    entities_path = datasets_root / "taxonomy" / "entities.json"
    raw_root = root / ".runtime" / "raw" / "boundaries"

    print(f"[lift_villages_national] root={root}", flush=True)
    print(f"  entities: {entities_path}", flush=True)

    state_lgd_to_eci = load_state_lgd_to_eci_map(entities_path)
    print(f"  loaded {len(state_lgd_to_eci)} state_lgd -> ECI mappings", flush=True)

    # bundle dir matches the snapshot key the TN-only village entry
    # used, so the cached archive + extraction are reused if the prior
    # TN snapshot already ran. The cached file is the FULL national
    # LGD_Villages.geojsonl regardless of the bundle name suffix
    # (snapshot.py downloads the upstream URL once per bundle dir; the
    # state_filter is applied downstream in snapshot.py's split-emit,
    # not at fetch time).
    bundle_dir = raw_root / "snapshot" / "S22-villages-_dist_lgd_"
    extracted_geojsonl = bundle_dir / "_extracted" / "LGD_Villages.geojsonl"

    if not extracted_geojsonl.exists() and args.skip_fetch:
        print(
            f"  ERROR: --skip-fetch but no geojsonl at {extracted_geojsonl}",
            file=sys.stderr,
            flush=True,
        )
        return 2

    if not extracted_geojsonl.exists():
        print(f"  fetching + extracting {LGD_VILLAGES_URL}", flush=True)
        _ = fetch_geojsonl_7z(
            [LGD_VILLAGES_URL],
            bundle_dir,
            coord_precision=None,  # round in lift loop, not here
        )

    rows = lift_villages_to_per_district_shards(
        extracted_geojsonl,
        state_lgd_to_eci,
        datasets_root,
    )

    keep_paths = {row.partition_path for row in rows}
    villages_dir = datasets_root / "boundaries" / "in" / "villages"
    deleted = remove_stale_shards(villages_dir, keep_paths)
    if deleted:
        print(f"  removed {deleted} stale shard(s) not in the lift output", flush=True)

    layer_count, source_count = compile_to_parquet(
        rows,
        datasets_root,
        merge_with_existing=True,
    )
    print(
        f"  boundary_layers.parquet: {layer_count} rows total "
        f"({len(rows)} village rows this lift) | "
        f"sources.parquet: {source_count} rows",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
