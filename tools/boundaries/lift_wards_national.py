"""Lift SBM_Wards.geojsonl into per-(state, ulb) Hive shards.

Phase C.3.a of ``docs/archive/plans/20260529-boundary-rip-and-replace-plan.md``: add
the LGD ULB Ward admin level to yen-gov's boundary corpus. ramSeraph
publishes SBM_Wards.geojsonl.7z (~250-350k features per Swachh Bharat
Mission Urban tracking, MoHUA lineage, CC0 1.0; ~30-state coverage —
missing West Bengal / Tripura / Mizoram / Manipur due to upstream SBM
non-participation. The optional C.3.d gap-fill PR can layer
LivingAtlas_Wards + WB_AMRUT_Wards + Shillong_Wards on top later)
from
https://github.com/ramSeraph/indian_admin_boundaries/releases/download/
urban/SBM_Wards.geojsonl.7z.

This orchestrator is a near-identical sibling of
``tools/boundaries/lift_panchayats_national.py`` (C.2.b) — both use a
two-level nested ``state=in_<sNN>/<parent>=<lgd>/`` Hive partition
because per-state ward counts (1,000-10,000+ polygons per high-density
state) would blow the 12 MB shard budget without a second partition
level. The parent partition swaps from ``district=`` (panchayats) to
``ulb=`` (wards) because a ULB can span multiple districts and LGD
treats the ULB as the primary urban entity. The auto-fallback
budget-overflow path is inherited verbatim from
``tools/boundaries/lift_blocks_national.py`` (Phase C.1.c, PR #443):
when a per-shard emission exceeds ``SNAPSHOT_BYTE_BUDGET`` at the
default ``coord_precision``, the script re-emits the same bucket at
``coord_precision - 1`` (~10x coarser tolerance) before falling
through to SKIP.

Why a dedicated one-shot orchestrator (mirrors panchayats + villages +
blocks rationale):

* Each ward feature carries both a state LGD code and a ULB LGD code.
  The output partition is keyed by ECI state code resolved via
  ``state_lgd_resolver`` and the LGD ULB code passed through unchanged
  (``state=in_<sNN>/ulb=<ulb_lgd>/`` two-level Hive). The resolution
  step is the same canonical-table lookup panchayats used.
* ``snapshot.py``'s ``split_by`` machinery emits a flat key-set with no
  parent partition; a multi-state nested lift requires a dedicated
  orchestrator. The panchayats precedent established this shape for
  the ``state=/<parent>=`` two-level shape.
* Reuses ``snapshot.py``'s public primitives so byte format + budget
  gate stay byte-identical with the panchayats entry.

Inputs:
    .runtime/raw/boundaries/snapshot/<bundle>/SBM_Wards.geojsonl.7z
        (fetched if missing; ~50-100 MB compressed estimate based on
        the panchayats archive scale relative to feature count)
    datasets/taxonomy/entities.json
        (state_lgd -> ECI state code mapping)
    datasets/boundaries/boundary_layers.parquet
        (existing rows; merged via ``merge_with_existing=True``)

Outputs:
    datasets/boundaries/in/wards/state=in_<sNN>/ulb=<ulb_lgd>/all.geojson
        (one per (state, ulb) combination that has any retained ward
        features; estimated ~4,500-5,000 shards nationally)
    datasets/boundaries/boundary_layers.parquet
        (new per-(state, ulb) rows added; all other layers preserved)
    datasets/data/entities/source.csv
        (UPSERTed by compile_to_parquet; ramSeraph row unchanged from
        prior runs)

Determinism: features per shard are sorted by ``(wardcode, wardname)``
before emit; coordinates rounded to ``coord_precision=4`` (~11 m,
matches the panchayats entry — wards aggregate revenue parcels +
street networks so they're typically smaller than a panchayat but
want fine vertex precision at zoom 12-16 where a citizen reads a city
map). Two consecutive runs against the same upstream archive produce
byte-identical shards.

Memory note: parses + holds all ~250-350k features in memory during
the group-by pass (~2-3 GB peak). Acceptable on dev machines.

First-snapshot inspection: PR #449 (C.3.a infra) hypothesised LGD
long-form names (``state_lgd`` / ``ulb_lgd`` / ``ward_code`` /
``ward_name``) per the blocks convention. The C.3.b live-lift first-
snapshot revealed SBM Urban uses concatenated-lowercase names
(``statecode`` / ``ulbcode`` / ``wardcode`` / ``wardname``) — a third
distinct convention separate from the C.1.b/C.1.c blocks long-form
AND the C.2.b panchayats short-form (``st_lgd`` / ``dt_lgd``). The
constants at the top of the module are LOCKED at the C.3.b
discovered shape. If a future upstream release renames properties,
update the constants there + the property accessors in the helpers.

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
    compile_to_csv,
)
from yen_gov.canonical.state_lgd_resolver import (  # noqa: E402
    load_state_lgd_to_eci_map,
)

# ---------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------

SBM_WARDS_URL = (
    "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/"
    "urban/SBM_Wards.geojsonl.7z"
)

# 4 decimal places ~ 11 m at the equator; matches lift_panchayats so the
# byte format is stable at the lowest LGD tiers. Wards are typically
# 0.05-2 km^2 (urban grain) — fine vertex precision keeps the boundary
# readable at zoom 12-16 where a citizen reads a city map.
COORD_PRECISION = 4

RAMSERAPH_SOURCE_ID = BOUNDARY_SOURCE_ID_BY_NICKNAME["ramseraph"]

# Upstream property names for the SBM_Wards release. C.3.b first-
# snapshot finding (PR #449 follow-up): SBM_Wards.geojsonl uses
# concatenated-lowercase names (``statecode``/``ulbcode``/``wardcode``/
# ``wardname``), NOT the LGD long-form (``state_lgd``/``ulb_lgd``/
# ``ward_code``/``ward_name``) hypothesised at C.3.a infra-PR time AND
# NOT the short-form (``st_lgd``/``dt_lgd``) surprise that C.2.b
# panchayats revealed. Cause: SBM Urban is a MoHUA-owned system whose
# schema is separate from LGD's panchayats / blocks / villages exports;
# its release format pre-dates the LGD long-form convention. Both
# ``statecode`` and ``ulbcode`` come through as numeric strings ("24",
# "802442") which the grouping helper coerces via ``int()``. The
# ``wardcode`` field is HETEROGENEOUS: most values are numeric strings
# ("4", "7") but a non-trivial minority are free-text labels
# ("Ward No 5", "WARD 12", etc.) carried verbatim from the ULB's own
# nomenclature. The sort helper handles both shapes; downstream
# consumers MUST treat ``wardcode`` as opaque string, not as int.
STATE_PROPERTY = "statecode"
ULB_PROPERTY = "ulbcode"
ID_PROPERTY = "wardcode"
NAME_PROPERTY = "wardname"


# ---------------------------------------------------------------------
# pure logic — testable without I/O
# ---------------------------------------------------------------------


def group_features_by_state_and_ulb(
    features: list[dict[str, Any]],
) -> tuple[dict[tuple[int, int], list[dict[str, Any]]], list[dict[str, Any]]]:
    """Group features by ``(state_lgd, ulb_lgd)`` tuple.

    Returns ``(groups, unkeyed)`` where ``unkeyed`` holds features
    missing EITHER ``state_lgd`` OR ``ulb_lgd`` (or both). Coerces
    both keys to int so callers can rely on integer tuples regardless
    of upstream string/int variation.
    """
    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    unkeyed: list[dict[str, Any]] = []
    for f in features:
        props = f.get("properties", {})
        s = props.get(STATE_PROPERTY)
        u = props.get(ULB_PROPERTY)
        if s is None or s == "" or u is None or u == "":
            unkeyed.append(f)
            continue
        groups.setdefault((int(s), int(u)), []).append(f)
    return groups, unkeyed


def sort_features_deterministically(
    features: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sort features by ``(wardcode, wardname)`` for byte-determinism.

    Ward codes are locally unique within a ULB but NOT globally unique
    (every ULB numbers its wards starting from 1). The secondary
    ``wardname`` key disambiguates within a bucket. Note: this
    function is called per-(state, ulb) bucket where ``wardcode`` is
    already unique within the bucket, so the secondary key is for
    defensive determinism rather than active disambiguation.

    Heterogeneous-wardcode handling (C.3.b first-snapshot finding):
    SBM_Wards ``wardcode`` is sometimes a pure-numeric string ("4",
    "12") and sometimes a free-text label ("Ward No 5", "WARD 12")
    carried verbatim from the source ULB's nomenclature. The sort key
    splits into two cohorts: numeric-castable codes sort first by int
    value (key=(0, int)), then free-text codes sort by str value
    (key=(1, str)). This is byte-stable across runs because the input
    feature list comes from a single archive pass in upstream-emit
    order plus this deterministic re-sort.
    """
    def _key(f: dict[str, Any]) -> tuple[int, int | str, str]:
        props = f.get("properties", {})
        code = props.get(ID_PROPERTY)
        name = props.get(NAME_PROPERTY, "") or ""
        try:
            return (0, int(code) if code is not None else 0, name)
        except (ValueError, TypeError):
            return (1, str(code), name)

    return sorted(features, key=_key)


# ---------------------------------------------------------------------
# main orchestration
# ---------------------------------------------------------------------


def lift_wards_to_per_ulb_shards(
    geojsonl_path: Path,
    state_lgd_to_eci: dict[int, str],
    datasets_root: Path,
    *,
    coord_precision: int = COORD_PRECISION,
) -> list[BoundaryLayerRow]:
    """Parse the national geojsonl, group by (state, ulb), emit per shard.

    Returns one ``BoundaryLayerRow`` per emitted shard. Features whose
    ``state_lgd`` doesn't map to a currently-valid state (e.g. historic
    codes, upstream data drift) are tallied + WARN-logged but do NOT
    emit a shard. Features lacking ``state_lgd`` or ``ulb_lgd`` are
    reported as unkeyed.

    Auto-fallback: when a per-shard emission exceeds
    ``SNAPSHOT_BYTE_BUDGET`` at the default ``coord_precision``, the
    script re-emits the same bucket at ``coord_precision - 1`` (~10x
    coarser tolerance) before falling through to SKIP. Inherited
    verbatim from ``lift_blocks_national.py`` (PR #443) +
    ``lift_panchayats_national.py`` (PR #446).
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

    print(f"  parsed {len(features):,} ward features", flush=True)

    groups, unkeyed_no_prop = group_features_by_state_and_ulb(features)
    print(
        f"  grouped into {len(groups):,} (state, ulb) buckets "
        f"({len(unkeyed_no_prop)} feature(s) lack "
        f"{STATE_PROPERTY}/{ULB_PROPERTY})",
        flush=True,
    )

    # free the parsed list — groups now owns every feature dict.
    del features

    unknown_state_lgd = sorted(
        {s for (s, _u) in groups} - set(state_lgd_to_eci)
    )
    if unknown_state_lgd:
        unknown_total = sum(
            len(v) for (s, _u), v in groups.items() if s in unknown_state_lgd
        )
        print(
            f"  WARNING: {len(unknown_state_lgd)} state_lgd value(s) not in "
            f"ECI map ({unknown_total} feature(s)): {unknown_state_lgd}",
            flush=True,
        )

    rows: list[BoundaryLayerRow] = []
    simpl_tol = 10**-coord_precision

    # Per-state counts for the summary; emit in deterministic
    # (ECI state, ulb_lgd) order.
    per_state_count: dict[str, int] = {}
    per_state_features: dict[str, int] = {}

    # Iterate ECI states in deterministic order so the lift output is
    # readable per-state; within a state, ULBs in numeric order.
    for state_lgd in sorted(state_lgd_to_eci):
        eci = state_lgd_to_eci[state_lgd]
        state_ulbs = sorted(
            u for (s, u) in groups if s == state_lgd
        )
        if not state_ulbs:
            continue
        for ulb_lgd in state_ulbs:
            bucket = groups[(state_lgd, ulb_lgd)]
            partition_path, layer_id = derive_hive(
                kind="wards",
                state=eci,
                ulb_lgd=str(ulb_lgd),
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
                # giving up. Mirrors lift_blocks_national.py (PR #443)
                # + lift_panchayats_national.py (PR #446).
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
                    f"    {eci}/u={ulb_lgd:>6}: over budget at "
                    f"precision={coord_precision}; fallback to "
                    f"precision={fallback_precision} -> "
                    f"{size / 1024:>7.0f} KB",
                    flush=True,
                )
                if size > SNAPSHOT_BYTE_BUDGET:
                    shard_path.unlink()
                    # opportunistically remove now-empty ulb= dir so
                    # it doesn't show as an empty dir in `git status`
                    # after a SKIP. parent.parent (state=in_<lc>/) is
                    # left alone — it will be rmdir'd opportunistically
                    # when remove_stale_shards runs or when the next
                    # SKIP in the same state empties it.
                    try:
                        shard_path.parent.rmdir()
                    except OSError:
                        pass
                    print(
                        f"    {eci}/u={ulb_lgd:>6}: even at "
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
                    level="ward",
                    partition_path=partition_path,
                    format="geojson",
                    crs="EPSG:4326",
                    original_feature_count=retained,
                    retained_feature_count=retained,
                    unkeyed_count=0,
                    size_bytes=size,
                    source_id=RAMSERAPH_SOURCE_ID,
                    entity_state=eci,
                    entity_city=str(ulb_lgd),
                    simplification_algorithm="coord-precision-round",
                    simplification_tolerance_deg=used_tol,
                )
            )
            per_state_count[eci] = per_state_count.get(eci, 0) + 1
            per_state_features[eci] = per_state_features.get(eci, 0) + retained
        print(
            f"    {eci}: {per_state_count.get(eci, 0):>4} ULBs, "
            f"{per_state_features.get(eci, 0):>7,} wards",
            flush=True,
        )

    return rows


def remove_stale_shards(wards_dir: Path, keep_partition_paths: set[str]) -> int:
    """Delete any ward shard not in the keep set.

    The lift replaces the entire wards tree, so stale shards from a
    prior lift run would otherwise persist on disk. Returns the count
    of files deleted.
    """
    if not wards_dir.exists():
        return 0
    deleted = 0
    for shard in list(wards_dir.rglob("all.geojson")):
        # partition_path keys in the parquet are repo-relative POSIX
        # rooted at boundaries/in/...; reconstruct the same shape from
        # the absolute shard path.
        rel = shard.relative_to(wards_dir.parent.parent.parent).as_posix()
        if rel in keep_partition_paths:
            continue
        shard.unlink()
        deleted += 1
        # opportunistically remove now-empty ulb= dir, then the parent
        # state= dir if also empty. rmdir silently fails on non-empty
        # so this is safe.
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
            "Lift SBM_Wards.geojsonl into per-(state, ulb) Hive shards."
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

    print(f"[lift_wards_national] root={root}", flush=True)
    print(f"  entities: {entities_path}", flush=True)

    state_lgd_to_eci = load_state_lgd_to_eci_map(entities_path)
    print(f"  loaded {len(state_lgd_to_eci)} state_lgd -> ECI mappings", flush=True)

    bundle_dir = raw_root / "snapshot" / "wards"
    extract_dir = bundle_dir / "_extracted"

    def _find_extracted() -> Path | None:
        """Discover the extracted .geojsonl via rglob; case-preserving on Windows.

        Upstream archive in this release ships ``SBM_Wards.geojsonl``
        (capital W). Hardcoding either case would break on case-sensitive
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
        print(f"  fetching + extracting {SBM_WARDS_URL}", flush=True)
        _ = fetch_geojsonl_7z(
            [SBM_WARDS_URL],
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

    rows = lift_wards_to_per_ulb_shards(
        extracted_geojsonl,
        state_lgd_to_eci,
        datasets_root,
    )

    keep_paths = {row.partition_path for row in rows}
    wards_dir = datasets_root / "boundaries" / "in" / "wards"
    deleted = remove_stale_shards(wards_dir, keep_paths)
    if deleted:
        print(f"  removed {deleted} stale shard(s) not in the lift output", flush=True)

    layer_count = compile_to_csv(
        rows,
        datasets_root,
        merge_with_existing=True,
    )
    print(
        f"  boundary_layer.csv: {layer_count} rows total "
        f"({len(rows)} ward rows this lift)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
