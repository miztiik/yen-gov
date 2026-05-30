"""Lift LGD_panchayats.geojsonl into per-(state, district) Hive shards.

Phase C.2 of ``docs/archive/plans/20260529-boundary-rip-and-replace-plan.md``: add the
LGD Gram Panchayat admin level to yen-gov's boundary corpus. ramSeraph
publishes LGD_panchayats.geojsonl.7z (~255,304 features per LGD Directory;
~225-245k actually emitted due to ~9-state coverage gap in HP/J&K/Sikkim/
NE) from the LGD / BharatMaps lineage at
https://github.com/ramSeraph/indian_admin_boundaries/releases/download/
panchayats/LGD_panchayats.geojsonl.7z.

This orchestrator is a near-identical sibling of
``tools/boundaries/lift_villages_national.py`` — both use the two-level
nested ``state=in_<sNN>/district=<lgd>/`` Hive partition because per-state
GP counts (300-2500 polygons per high-density state) would blow the
12 MB shard budget without a second partition level. The auto-fallback
budget-overflow path is inherited verbatim from
``tools/boundaries/lift_blocks_national.py`` (Phase C.1.c, PR #443):
when a per-shard emission exceeds ``SNAPSHOT_BYTE_BUDGET`` at the
default ``coord_precision``, the script re-emits the same bucket at
``coord_precision - 1`` (~10x coarser tolerance) before falling
through to SKIP.

Why a dedicated one-shot orchestrator (mirrors villages + blocks
rationale):

* Each panchayat feature carries both ``state_lgd`` and ``dist_lgd``
  properties. The output partition is keyed by ECI state code resolved
  via ``state_lgd_resolver`` and the LGD district code passed through
  unchanged (``state=in_<sNN>/district=<lgd>/`` two-level Hive). The
  resolution step is the same canonical-table lookup villages used.
* ``snapshot.py``'s ``split_by`` machinery emits a flat key-set with no
  parent partition; a multi-state nested lift requires a dedicated
  orchestrator. The villages precedent established this shape.
* Reuses ``snapshot.py``'s public primitives so byte format + budget
  gate stay byte-identical with the villages entry.

Inputs:
    .runtime/raw/boundaries/snapshot/<bundle>/LGD_panchayats.geojsonl.7z
        (fetched if missing; large — ~50-80 MB compressed estimate
        based on the villages archive scale relative to feature count)
    datasets/taxonomy/entities.json
        (state_lgd -> ECI state code mapping)
    datasets/boundaries/boundary_layers.parquet
        (existing rows; merged via ``merge_with_existing=True``)

Outputs:
    datasets/boundaries/in/panchayats/state=in_<sNN>/district=<lgd>/all.geojson
        (one per (state, district) combination that has any retained
        panchayat features; estimated ~792 shards nationally)
    datasets/boundaries/boundary_layers.parquet
        (new per-(state, district) rows added; all other layers preserved)
    datasets/taxonomy/sources.parquet
        (UPSERTed by compile_to_parquet; ramSeraph row unchanged from
        prior runs)

Determinism: features per shard are sorted by ``(panchayat_lgd, pname)``
before emit; coordinates rounded to ``coord_precision=4`` (~11 m, matches
the villages entry — panchayats aggregate revenue villages so they're
typically larger than a single village but still want fine vertex
precision at zoom 10-14 where a citizen reads them). Two consecutive
runs against the same upstream archive produce byte-identical shards.

Memory note: parses + holds all ~255k features in memory during the
group-by pass (~2 GB peak). Acceptable on dev machines.

First-snapshot inspection: the LGD_panchayats property names assumed
below (``panchayat_lgd`` / ``pname``) follow the LGD-conventional
shape (``block_lgd`` / ``block_name``, ``village_lgd`` / ``vlgname``).
If the first snapshot reveals different upstream names, callers MUST
update the constants at the top of the module + the corresponding
property accessors in the helpers. The C.2 recon verdict flagged this
as the C.2.b first-snapshot confirmation step
(analogous to C.1.b's block_lgd / block_name confirmation).

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

LGD_PANCHAYATS_URL = (
    "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/"
    "panchayats/LGD_panchayats.geojsonl.7z"
)

# 4 decimal places ~ 11 m at the equator; matches lift_villages so the
# byte format is stable at the lowest two LGD tiers. Gram panchayats
# aggregate 5-30 revenue villages so their outline is typically 5-50
# km^2 — fine vertex precision keeps the shape readable at zoom 10-14.
COORD_PRECISION = 4

RAMSERAPH_SOURCE_ID = BOUNDARY_SOURCE_ID_BY_NICKNAME["ramseraph"]

# Upstream property names for the LGD_Panchayats release. First-snapshot
# inspection (2026-05-30) showed the panchayats geojsonl uses LGD short
# codes (``st_lgd`` / ``dt_lgd`` / ``gp_code`` / ``gp_name``) rather than
# the longer names used by the blocks layer (``state_lgd`` / ``dist_lgd``
# / ``block_lgd`` / ``block_name``). Same upstream maintainer, different
# property naming convention per layer — keep these constants the single
# source-of-truth so a future schema flip is a 4-line edit.
STATE_PROPERTY = "st_lgd"
DISTRICT_PROPERTY = "dt_lgd"
ID_PROPERTY = "gp_code"
NAME_PROPERTY = "gp_name"


# ---------------------------------------------------------------------
# pure logic — testable without I/O
# ---------------------------------------------------------------------


def group_features_by_state_and_district(
    features: list[dict[str, Any]],
) -> tuple[dict[tuple[int, int], list[dict[str, Any]]], list[dict[str, Any]]]:
    """Group features by ``(st_lgd, dt_lgd)`` tuple.

    Returns ``(groups, unkeyed)`` where ``unkeyed`` holds features
    missing EITHER ``st_lgd`` OR ``dt_lgd`` (or both). Coerces both
    keys to int so callers can rely on integer tuples regardless of
    upstream string/int variation.
    """
    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    unkeyed: list[dict[str, Any]] = []
    for f in features:
        props = f.get("properties", {})
        s = props.get(STATE_PROPERTY)
        d = props.get(DISTRICT_PROPERTY)
        if s is None or s == "" or d is None or d == "":
            unkeyed.append(f)
            continue
        groups.setdefault((int(s), int(d)), []).append(f)
    return groups, unkeyed


def sort_features_deterministically(
    features: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sort features by ``(gp_code, gp_name)`` for byte-determinism.

    Panchayat LGD codes are globally unique within India per the LGD
    scheme, so ``gp_code`` alone gives a total order. The secondary
    ``gp_name`` key only matters if two rows happen to share an LGD
    code (a data bug we want to surface deterministically rather
    than interleave randomly).
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


def lift_panchayats_to_per_district_shards(
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

    Auto-fallback: when a per-shard emission exceeds
    ``SNAPSHOT_BYTE_BUDGET`` at the default ``coord_precision``, the
    script re-emits the same bucket at ``coord_precision - 1`` (~10x
    coarser tolerance) before falling through to SKIP. Inherited
    verbatim from ``lift_blocks_national.py`` (PR #443).
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

    print(f"  parsed {len(features):,} panchayat features", flush=True)

    groups, unkeyed_no_prop = group_features_by_state_and_district(features)
    print(
        f"  grouped into {len(groups):,} (state, district) buckets "
        f"({len(unkeyed_no_prop)} feature(s) lack "
        f"{STATE_PROPERTY}/{DISTRICT_PROPERTY})",
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
                kind="panchayats",
                state=eci,
                district_lgd=str(dist_lgd),
            )
            bucket_sorted = sort_features_deterministically(bucket)
            shard_path = datasets_root / partition_path
            emit_feature_collection(shard_path, bucket_sorted)
            size = shard_path.stat().st_size
            used_precision = coord_precision
            used_tol = simpl_tol
            if size > SNAPSHOT_BYTE_BUDGET:
                # Auto-fallback: re-emit the over-budget bucket at the
                # next coarser precision (`coord_precision - 1`) before
                # giving up. Mirrors lift_blocks_national.py (PR #443).
                # Uniform script rule (NOT per-state hand-coded carve-out)
                # so renderer-side heterogeneity is invisible (join_property
                # is the LGD id; vertex precision only affects edge
                # vertex count, invisible at choropleth zoom 10-14 for
                # typical panchayat size).
                fallback_precision = coord_precision - 1
                fallback_tol = 10**-fallback_precision
                for feat in bucket_sorted:
                    if feat.get("geometry"):
                        feat["geometry"] = _round_coords_geom(
                            feat["geometry"], fallback_precision
                        )
                emit_feature_collection(shard_path, bucket_sorted)
                size = shard_path.stat().st_size
                used_precision = fallback_precision
                used_tol = fallback_tol
                print(
                    f"    {eci}/d={dist_lgd:>4}: over budget at "
                    f"precision={coord_precision}; fallback to "
                    f"precision={fallback_precision} -> "
                    f"{size / 1024:>7.0f} KB",
                    flush=True,
                )
                if size > SNAPSHOT_BYTE_BUDGET:
                    shard_path.unlink()
                    # opportunistically remove now-empty district= dir
                    # so it doesn't show as an empty dir in `git status`
                    # after a SKIP. parent.parent (state=in_<lc>/) is
                    # left alone — it will be rmdir'd opportunistically
                    # when remove_stale_shards runs or when the next
                    # SKIP in the same state empties it.
                    try:
                        shard_path.parent.rmdir()
                    except OSError:
                        pass
                    print(
                        f"    {eci}/d={dist_lgd:>4}: even at "
                        f"precision={fallback_precision} shard "
                        f"{size / 1024 / 1024:.1f} MB exceeds "
                        f"{SNAPSHOT_BYTE_BUDGET / 1024 / 1024:.0f} MB budget - SKIP",
                        flush=True,
                    )
                    continue
            retained = len(bucket_sorted)
            rows.append(
                BoundaryLayerRow(
                    layer_id=layer_id,
                    level="panchayat",
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
                    simplification_tolerance_deg=used_tol,
                )
            )
            per_state_count[eci] = per_state_count.get(eci, 0) + 1
            per_state_features[eci] = per_state_features.get(eci, 0) + retained
        print(
            f"    {eci}: {per_state_count.get(eci, 0):>3} districts, "
            f"{per_state_features.get(eci, 0):>6,} panchayats",
            flush=True,
        )

    return rows


def remove_stale_shards(panchayats_dir: Path, keep_partition_paths: set[str]) -> int:
    """Delete any panchayat shard not in the keep set.

    The lift replaces the entire panchayats tree, so stale shards from
    a prior lift run would otherwise persist on disk. Returns the count
    of files deleted.
    """
    if not panchayats_dir.exists():
        return 0
    deleted = 0
    for shard in panchayats_dir.rglob("all.geojson"):
        # partition_path keys in the parquet are repo-relative POSIX
        # rooted at boundaries/in/...; reconstruct the same shape from
        # the absolute shard path.
        rel = shard.relative_to(panchayats_dir.parent.parent.parent).as_posix()
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
            "Lift LGD_panchayats.geojsonl into per-(state, district) Hive shards."
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
            "iterating locally to avoid re-downloading."
        ),
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    datasets_root = root / "datasets"
    entities_path = datasets_root / "taxonomy" / "entities.json"
    raw_root = root / ".runtime" / "raw" / "boundaries"

    print(f"[lift_panchayats_national] root={root}", flush=True)
    print(f"  entities: {entities_path}", flush=True)

    state_lgd_to_eci = load_state_lgd_to_eci_map(entities_path)
    print(f"  loaded {len(state_lgd_to_eci)} state_lgd -> ECI mappings", flush=True)

    bundle_dir = raw_root / "snapshot" / "panchayats"
    extract_dir = bundle_dir / "_extracted"

    def _find_extracted() -> Path | None:
        """Discover the extracted .geojsonl via rglob; case-preserving on Windows.

        Upstream archive in this release ships ``LGD_Panchayats.geojsonl``
        (capital P). Hardcoding either case would break on case-sensitive
        filesystems (linux CI) or on case-preserving ones (Windows + git);
        rglob mirrors what ``fetch_geojsonl_7z`` does internally.
        """
        if not extract_dir.exists():
            return None
        matches = sorted(extract_dir.rglob("*.geojsonl"))
        return matches[0] if matches else None

    extracted_geojsonl = _find_extracted()

    if extracted_geojsonl is None and args.skip_fetch:
        print(
            f"  ERROR: --skip-fetch but no .geojsonl under {extract_dir}",
            file=sys.stderr,
            flush=True,
        )
        return 2

    if extracted_geojsonl is None:
        print(f"  fetching + extracting {LGD_PANCHAYATS_URL}", flush=True)
        _ = fetch_geojsonl_7z(
            [LGD_PANCHAYATS_URL],
            bundle_dir,
            coord_precision=None,  # round in lift loop, not here
        )
        extracted_geojsonl = _find_extracted()
        if extracted_geojsonl is None:
            print(
                f"  ERROR: fetch succeeded but no .geojsonl under {extract_dir}",
                file=sys.stderr,
                flush=True,
            )
            return 2

    print(f"  extracted: {extracted_geojsonl.name}", flush=True)

    rows = lift_panchayats_to_per_district_shards(
        extracted_geojsonl,
        state_lgd_to_eci,
        datasets_root,
    )

    keep_paths = {row.partition_path for row in rows}
    panchayats_dir = datasets_root / "boundaries" / "in" / "panchayats"
    deleted = remove_stale_shards(panchayats_dir, keep_paths)
    if deleted:
        print(f"  removed {deleted} stale shard(s) not in the lift output", flush=True)

    layer_count, source_count = compile_to_parquet(
        rows,
        datasets_root,
        merge_with_existing=True,
    )
    print(
        f"  boundary_layers.parquet: {layer_count} rows total "
        f"({len(rows)} panchayat rows this lift) | "
        f"sources.parquet: {source_count} rows",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
