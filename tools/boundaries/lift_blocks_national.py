"""Lift LGD_Blocks.geojsonl into per-state Hive shards.

Phase C.1 of ``TODO/20260529-boundary-rip-and-replace-plan.md``: add the
Development Block admin level to yen-gov's boundary corpus. ramSeraph
publishes LGD_Blocks.geojsonl.7z (~7,323 features) from the LGD /
BharatMaps lineage at https://github.com/ramSeraph/indian_admin_boundaries/
releases/download/blocks/LGD_Blocks.geojsonl.7z.

This orchestrator mirrors ``tools/boundaries/lift_subdistricts_national.py``
so the byte format + per-state hive-partition logic stay consistent
across the LGD admin spine. The two lift scripts are intentionally
near-identical sibling files (rather than a parameterised single
script) so a future change to one level's emission semantics can be
made without touching the other.

Why a dedicated one-shot orchestrator rather than extending
``tools/boundaries/snapshot.py``:

* Per-state shard emission requires resolving each feature's numeric
  ``state_lgd`` property to an ECI state code via a lookup against
  ``datasets/taxonomy/entities.json``. ``snapshot.py``'s ``split_by``
  machinery emits shards keyed by the raw group key
  (e.g. ``state=22``), not by a value derived from a per-row lookup.
* Phase C.1 verdict ([notes/2026-05-29-c1-blocks-source-hunt-verdict.md])
  explicitly chose this pattern: it reuses ``snapshot.py``'s public
  primitives (``fetch_geojsonl_7z``, ``emit_feature_collection``,
  ``_round_coords_geom``, ``SNAPSHOT_BYTE_BUDGET``) so citizen-side byte
  format and the budget gate stay byte-for-byte identical to other
  layers, but skips the snapshot.py ``inputs[]`` loop that would
  otherwise require teaching ``derive_hive`` about state-code
  resolution.

Inputs:
    .runtime/raw/boundaries/snapshot/<bundle>/LGD_Blocks.geojsonl.7z
        (fetched if missing)
    datasets/taxonomy/entities.json
        (state_lgd -> ECI state code mapping)
    datasets/boundaries/boundary_layers.parquet
        (existing rows; merged via merge_with_existing=True)

Outputs:
    datasets/boundaries/in/blocks/state=in_<sNN>/all.geojson
        (one per state/UT that has any retained blocks)
    datasets/boundaries/boundary_layers.parquet
        (new per-state rows added; all other rows preserved)
    datasets/taxonomy/sources.parquet
        (UPSERTed by compile_to_parquet; ramSeraph row unchanged from
        prior runs — same producer/title/vintage as the subdistricts
        + districts + states entries)

Determinism: features per shard are sorted by ``(block_lgd, block_name)``
before emit; coordinates rounded to ``coord_precision=3`` (~110 m); same
byte format as snapshot.py + lift_subdistricts. Two consecutive runs
against the same upstream archive produce byte-identical shards.

Pure stdlib + duckdb (via the canonical writer) + py7zr (via
fetch_geojsonl_7z). No external HTTP libs.

First-snapshot inspection: the LGD_Blocks property names assumed below
(``block_lgd`` / ``block_name``) are the LGD-conventional names also
used in the LGD_Subdistricts schema (``subdt_lgd`` / ``sdtname`` for
that level). If the first snapshot reveals different names, callers
MUST update the constants at the top of the module + the corresponding
``group_features_by_state_lgd`` / ``sort_features_deterministically``
property accessors. The recon verdict flagged this as the C.1
first-snapshot confirmation step (analogous to D.0's State_LGD /
STNAME confirmation).
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

LGD_BLOCKS_URL = (
    "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/"
    "blocks/LGD_Blocks.geojsonl.7z"
)

# 3 decimal places ~ 110 m at the equator; matches lift_subdistricts so
# the byte format is stable across the LGD admin spine. Blocks are
# typically 50-500 km^2; 110 m precision is well below visual choropleth
# resolution at zoom 6-12 (the recommended tippecanoe range).
COORD_PRECISION = 3

RAMSERAPH_SOURCE_ID = BOUNDARY_SOURCE_ID_BY_NICKNAME["ramseraph"]

# LGD-conventional property names for the Blocks layer. Mirrors the
# districts (dist_lgd / dtname) + subdistricts (subdt_lgd / sdtname)
# convention. If first snapshot reveals different upstream names,
# update both constants + the property accessors in the grouping /
# sorting helpers below.
ID_PROPERTY = "block_lgd"
NAME_PROPERTY = "block_name"


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
    """Sort features by ``(block_lgd, block_name)`` for byte-determinism.

    Block LGD codes are globally unique within India per the LGD scheme,
    so ``block_lgd`` alone gives a total order. The secondary
    ``block_name`` key only matters if two rows happen to share an LGD
    code (a data bug we want to surface deterministically rather than
    interleave randomly).
    """
    return sorted(
        features,
        key=lambda f: (
            int(f.get("properties", {}).get(ID_PROPERTY) or 0),
            f.get("properties", {}).get(NAME_PROPERTY, "") or "",
        ),
    )


# ---------------------------------------------------------------------
# main orchestration
# ---------------------------------------------------------------------


def lift_blocks_to_per_state_shards(
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

    print(f"  parsed {len(features):,} block features", flush=True)

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
            print(f"    {eci} (lgd={lgd:>3}): 0 features - SKIP", flush=True)
            continue
        partition_path, layer_id = derive_hive(
            kind="blocks",
            state=eci,
        )
        bucket_sorted = sort_features_deterministically(bucket)
        shard_path = datasets_root / partition_path
        emit_feature_collection(shard_path, bucket_sorted)
        size = shard_path.stat().st_size
        if size > SNAPSHOT_BYTE_BUDGET:
            shard_path.unlink()
            # Also remove the now-empty state=in_<lc>/ directory so it
            # doesn't show up as an empty dir in `git status` after a
            # SKIP. The parent of the parent (boundaries/in/blocks/)
            # is intentionally preserved.
            try:
                shard_path.parent.rmdir()
            except OSError:
                pass
            print(
                f"    {eci} (lgd={lgd:>3}): shard {size / 1024 / 1024:.1f} MB "
                f"exceeds {SNAPSHOT_BYTE_BUDGET / 1024 / 1024:.0f} MB budget - SKIP",
                flush=True,
            )
            continue
        retained = len(bucket_sorted)
        rows.append(
            BoundaryLayerRow(
                layer_id=layer_id,
                level="block",
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


def remove_stale_shards(blocks_dir: Path, keep_partition_paths: set[str]) -> int:
    """Delete any ``blocks/state=in_*/all.geojson`` shard not in the keep set.

    The lift replaces the entire blocks tree, so stale shards from a
    prior lift run would otherwise persist on disk. Returns the count
    of files deleted.
    """
    if not blocks_dir.exists():
        return 0
    deleted = 0
    for shard in blocks_dir.rglob("all.geojson"):
        rel = shard.relative_to(blocks_dir.parent.parent.parent).as_posix()
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
        description="Lift LGD_Blocks.geojsonl into per-state Hive shards.",
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
            "iterating locally to avoid re-downloading."
        ),
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    datasets_root = root / "datasets"
    entities_path = datasets_root / "taxonomy" / "entities.json"
    raw_root = root / ".runtime" / "raw" / "boundaries"

    print(f"[lift_blocks_national] root={root}", flush=True)
    print(f"  entities: {entities_path}", flush=True)

    state_lgd_to_eci = load_state_lgd_to_eci_map(entities_path)
    print(f"  loaded {len(state_lgd_to_eci)} state_lgd -> ECI mappings", flush=True)

    bundle_dir = raw_root / "snapshot" / "blocks"
    extracted_geojsonl = bundle_dir / "_extracted" / "LGD_Blocks.geojsonl"

    if not extracted_geojsonl.exists() and args.skip_fetch:
        print(
            f"  ERROR: --skip-fetch but no geojsonl at {extracted_geojsonl}",
            file=sys.stderr,
            flush=True,
        )
        return 2

    if not extracted_geojsonl.exists():
        print(f"  fetching + extracting {LGD_BLOCKS_URL}", flush=True)
        # fetch_geojsonl_7z returns (features, sources) but we don't want
        # to hold all features in memory pre-coord-round; the bundle_dir-
        # side _extracted file is the side-effect we actually consume.
        # Discard the in-memory result.
        _ = fetch_geojsonl_7z(
            [LGD_BLOCKS_URL],
            bundle_dir,
            coord_precision=None,  # round in lift loop, not here
        )

    rows = lift_blocks_to_per_state_shards(
        extracted_geojsonl,
        state_lgd_to_eci,
        datasets_root,
    )

    keep_paths = {row.partition_path for row in rows}
    blocks_dir = datasets_root / "boundaries" / "in" / "blocks"
    deleted = remove_stale_shards(blocks_dir, keep_paths)
    if deleted:
        print(f"  removed {deleted} stale shard(s) not in the lift output", flush=True)

    layer_count, source_count = compile_to_parquet(
        rows,
        datasets_root,
        merge_with_existing=True,
    )
    print(
        f"  boundary_layers.parquet: {layer_count} rows total "
        f"({len(rows)} block rows this lift) | "
        f"sources.parquet: {source_count} rows",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
