"""One-shot ledger resync: rewrite the electoral rows in
``datasets/data/entities/boundary_layer.csv`` to match the on-disk
slug-keyed shards under ``datasets/boundaries/electoral/...``.

Kept (not deleted) as the receipt of HOW the Item 1 ledger backfill was
performed. Per CLAUDE.md section 10, structural fixes only - no monkey
patches.

Context: G10 (PR #838) moved AC boundary files to
``datasets/boundaries/electoral/delim=<year>/ac/state=<slug>/...`` but
the ledger at ``datasets/data/entities/boundary_layer.csv`` still has
only 1 electoral row (state=in_s01, the pre-2026-06-09 ECI-derived form
for andhra-pradesh). The remaining 30 AC state shards (and 1 PC layer)
on disk are NOT represented in the ledger. This script:

1. Loads the existing ledger via ``_read_existing_boundary_layers``.
2. Filters out ALL existing electoral rows (any layer_id starting
   with ``boundaries.electoral.``). The 1 legacy
   ``state=in_s01`` row is dropped here.
3. Scans ``datasets/boundaries/electoral/`` for .geojson files (only -
   .topojson + .pmtiles derivatives are NOT ledger rows per the
   existing convention) and builds one BoundaryLayerRow per shard
   keyed by LGD-name slug.
4. Combines admin-spine rows (preserved verbatim) + new electoral
   rows + writes the full set via ``compile_to_csv`` (REPLACE).

Scope (Hans+Max+Gregor verdict, 2026-06-09):
  * ELECTORAL ONLY: admin-spine rows (4013) are out-of-scope here per
    the in-flight admin slug-partition chunk's ownership.
  * AC shards: 31 (one per state subtree on disk).
  * PC shard: 1 (national delim=2024).
  * Expected final electoral row count: 32 (31 AC + 1 PC).

Brief math check: the brief said "1 existing row rewrite + 30 missing
rows scanned + emitted = 31 total" - the 31 is the AC count (29 net
new + 1 rewritten + 1 already on disk before delim=2008 was the only
vintage); plus the 1 PC layer the brief did not enumerate but is
genuinely on disk + has no ledger row. Including PC keeps the ledger
honest (every .geojson under boundaries/electoral/ has a ledger row).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
BACKEND = REPO_ROOT / "backend"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BACKEND))

from _paths import KIND_TO_LEVEL, derive_hive  # noqa: E402

from yen_gov.canonical.boundary_layers_seed import (  # noqa: E402
    BOUNDARY_SOURCE_ID_BY_NICKNAME,
    BoundaryLayerRow,
    _read_existing_boundary_layers,
    compile_to_csv,
)

DATASETS_ROOT = REPO_ROOT / "datasets"
ELECTORAL_ROOT = DATASETS_ROOT / "boundaries" / "electoral"

# Hand-authored source-id assignments per electoral subtree. PRE-2026-06-09
# only AC delim=2008 was in the ledger via the HTL fallback (now replaced
# by ramSeraph + shijithpk). Looking at the existing 1 row:
# state=in_s01 used src-a1dd899f902d which is the ramSeraph source_id
# (BOUNDARY_SOURCE_ID_BY_NICKNAME["ramseraph"]). The PC layer comes from
# shijithpk's PC 2024 publication
# (BOUNDARY_SOURCE_ID_BY_NICKNAME["shijithpk_pc_2024"]).
#
# The slug-vs-ECI mapping is not the script's concern - the source_id
# is keyed by the (delim, kind) tuple per source nickname. Per
# pipeline.json the AC delim=2008 source_triple is ramSeraph
# "Indian Admin Boundaries (LGD-keyed)" "lgd-latest-extra1" (line 36-40)
# for every state - one source covers all 31 state shards.
SOURCE_ID_FOR_AC_DELIM_2008 = BOUNDARY_SOURCE_ID_BY_NICKNAME["ramseraph"]
SOURCE_ID_FOR_PC_DELIM_2024 = BOUNDARY_SOURCE_ID_BY_NICKNAME["shijithpk_pc_2024"]


def _count_features(geojson_path: Path) -> int:
    """Count features in a FeatureCollection .geojson file."""
    doc = json.loads(geojson_path.read_text(encoding="utf-8"))
    features = doc.get("features") or []
    return len(features)


def _eci_from_slug(slug: str) -> str | None:
    """Reverse map: LGD-name slug -> ECI st_code. Sources from
    datasets/taxonomy/lgd_states.json. Returns None if unmatched
    (callers carry None as the entity_state column value).
    """
    doc = json.loads(
        (REPO_ROOT / "datasets" / "taxonomy" / "lgd_states.json").read_text(encoding="utf-8")
    )
    for state in doc["states"]:
        if str(state.get("slug")) == slug:
            return str(state["eci_st_code"])
    return None


def scan_electoral_disk() -> list[BoundaryLayerRow]:
    """Scan ``datasets/boundaries/electoral/`` for .geojson files and
    build one BoundaryLayerRow per shard.

    Returns rows sorted by layer_id for deterministic output.
    """
    rows: list[BoundaryLayerRow] = []

    if not ELECTORAL_ROOT.is_dir():
        return rows

    # --- AC subtree: delim=<year>/ac/state=<slug>/all.geojson ---
    for delim_dir in sorted(ELECTORAL_ROOT.glob("delim=*")):
        # AC layer (per-state shards)
        ac_dir = delim_dir / "ac"
        if ac_dir.is_dir():
            delim = delim_dir.name.removeprefix("delim=")
            for state_dir in sorted(ac_dir.glob("state=*")):
                geojson_path = state_dir / "all.geojson"
                if not geojson_path.is_file():
                    continue
                slug = state_dir.name.removeprefix("state=")
                eci_code = _eci_from_slug(slug)
                feature_count = _count_features(geojson_path)
                size_bytes = geojson_path.stat().st_size
                partition_path, layer_id = derive_hive(
                    kind="ac",
                    delim=delim,
                    state_slug=slug,
                    ext="geojson",
                )
                rows.append(
                    BoundaryLayerRow(
                        layer_id=layer_id,
                        level="ac",
                        entity_state=eci_code,
                        partition_path=partition_path,
                        format="geojson",
                        crs="EPSG:4326",
                        simplification_algorithm="coord-precision-round",
                        simplification_tolerance_deg=1e-06,
                        original_feature_count=feature_count,
                        retained_feature_count=feature_count,
                        unkeyed_count=0,
                        size_bytes=size_bytes,
                        source_id=SOURCE_ID_FOR_AC_DELIM_2008,
                        delimitation_vintage=delim,
                    )
                )

        # PC layer (national, no state= partition)
        pc_dir = delim_dir / "pc"
        if pc_dir.is_dir():
            delim = delim_dir.name.removeprefix("delim=")
            geojson_path = pc_dir / "all.geojson"
            if geojson_path.is_file():
                feature_count = _count_features(geojson_path)
                size_bytes = geojson_path.stat().st_size
                partition_path, layer_id = derive_hive(
                    kind="pc",
                    delim=delim,
                    ext="geojson",
                )
                rows.append(
                    BoundaryLayerRow(
                        layer_id=layer_id,
                        level="pc",
                        partition_path=partition_path,
                        format="geojson",
                        crs="EPSG:4326",
                        simplification_algorithm="coord-precision-round",
                        simplification_tolerance_deg=1e-06,
                        original_feature_count=feature_count,
                        retained_feature_count=feature_count,
                        unkeyed_count=0,
                        size_bytes=size_bytes,
                        source_id=SOURCE_ID_FOR_PC_DELIM_2024,
                        delimitation_vintage=delim,
                    )
                )

    rows.sort(key=lambda r: r.layer_id)
    return rows


def resync_electoral_ledger() -> tuple[int, int, int, int]:
    """Read existing ledger, drop electoral rows, add fresh electoral
    rows, write back. Admin-spine rows preserved verbatim.

    Returns:
        ``(electoral_before, admin_preserved, electoral_after, total_after)``.
    """
    existing = _read_existing_boundary_layers(DATASETS_ROOT)
    electoral_before = sum(
        1 for r in existing if r.layer_id.startswith("boundaries.electoral.")
    )
    admin_preserved = [
        r for r in existing if not r.layer_id.startswith("boundaries.electoral.")
    ]
    new_electoral = scan_electoral_disk()
    all_rows = admin_preserved + new_electoral
    n_written = compile_to_csv(all_rows, DATASETS_ROOT, merge_with_existing=False)
    return electoral_before, len(admin_preserved), len(new_electoral), n_written


if __name__ == "__main__":
    before, admin, electoral, total = resync_electoral_ledger()
    print(
        f"electoral_before={before} admin_preserved={admin} "
        f"electoral_after={electoral} total_rows={total}"
    )
