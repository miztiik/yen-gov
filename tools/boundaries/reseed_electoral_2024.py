#!/usr/bin/env python3
"""Reseed the electoral rows of datasets/data/entities/boundary_layer.csv for
the 2026-06-16 map-geometry rip (Row 3).

Before: 33 electoral rows = 31 per-state ``delim=2008/ac`` geojson shards +
1 ``delim=2008/pc`` geojson + 1 ``delim=2024/pc`` geojson.

After: 2 electoral rows = 1 national ``delim=2024/ac/all.topojson`` (the
consolidated derived TopoJSON that replaces the 31 shards) + the surviving
``delim=2024/pc/all.geojson``. The 32 ``delim=2008`` electoral rows are
dropped because their geometry is deleted in the same PR.

This is a programmatic transform of the existing CSV via the canonical
writer ``boundary_layers_seed.compile_to_csv`` (NOT a hand-edit, per the
Row 3 handover): it rehydrates every existing row, drops the
``electoral/delim=2008/`` ones, computes the national AC row's feature
count + byte size from the topojson on disk, and re-emits. Idempotent:
re-running after the rip is a no-op (the AC row already present, no
delim=2008 rows left to drop).

The national AC row reuses ``source_id = src-a1dd899f902d`` - the same
citation the 31 per-state shards carried, because the consolidated
TopoJSON is the SAME underlying ramSeraph LGD Assembly-Constituency data,
just relocated + re-encoded. Provenance is preserved, not minted.

Usage:
  python tools/boundaries/reseed_electoral_2024.py --datasets-root datasets
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# tools/ MUST NOT import backend runtime modules at module load for the
# frontend, but per CLAUDE.md section 4 a boundary-seeding tool that calls
# the canonical writer is the documented exception (mirrors snapshot.py).
_REPO = Path(__file__).resolve().parents[2]
_BACKEND = _REPO / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from yen_gov.canonical.boundary_layers_seed import (  # noqa: E402
    BoundaryLayerRow,
    _read_existing_boundary_layers,
    compile_to_csv,
)

# The consolidated national AC layer (produced by consolidate_ac_2024.py).
AC_PARTITION_PATH = "boundaries/electoral/delim=2024/ac/all.topojson"
AC_LAYER_ID = "boundaries.electoral.delim=2024.ac"
AC_TOPOJSON_OBJECT = "ac"
# Same citation triple the 31 per-state delim=2008/ac shards carried
# (ramSeraph LGD Assembly Constituencies). The consolidation relocates +
# re-encodes the SAME data, so provenance is preserved, not minted.
AC_SOURCE_ID = "src-a1dd899f902d"
AC_DELIM_VINTAGE = "2024"

_DROP_SUBSTR = "electoral/delim=2008/"


def _ac_feature_count(topojson_path: Path) -> int:
    """Geometry count of the ``ac`` object in the national AC topology."""
    with topojson_path.open("r", encoding="utf-8") as fh:
        topo = json.load(fh)
    if topo.get("type") != "Topology":
        raise ValueError(f"{topojson_path}: type must be Topology")
    objects = topo.get("objects") or {}
    obj = objects.get(AC_TOPOJSON_OBJECT)
    if not isinstance(obj, dict) or obj.get("type") != "GeometryCollection":
        raise ValueError(
            f"{topojson_path}: objects[{AC_TOPOJSON_OBJECT!r}] must be a GeometryCollection"
        )
    geometries = obj.get("geometries")
    if not isinstance(geometries, list):
        raise ValueError(f"{topojson_path}: objects[{AC_TOPOJSON_OBJECT!r}].geometries missing")
    return len(geometries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--datasets-root",
        type=Path,
        default=Path("datasets"),
        help="Path to the datasets/ directory (default: ./datasets).",
    )
    args = parser.parse_args(argv)
    datasets_root: Path = args.datasets_root.resolve()

    topojson_path = datasets_root / "boundaries" / "electoral" / "delim=2024" / "ac" / "all.topojson"
    if not topojson_path.is_file():
        print(f"ERROR: national AC topojson not found at {topojson_path}", file=sys.stderr)
        return 2

    feature_count = _ac_feature_count(topojson_path)
    size_bytes = topojson_path.stat().st_size

    existing = _read_existing_boundary_layers(datasets_root)
    kept = [r for r in existing if _DROP_SUBSTR not in r.partition_path]
    dropped = len(existing) - len(kept)

    # Drop any prior national-AC row (idempotent re-run) before re-adding.
    kept = [r for r in kept if r.layer_id != AC_LAYER_ID]

    ac_row = BoundaryLayerRow(
        layer_id=AC_LAYER_ID,
        level="ac",
        partition_path=AC_PARTITION_PATH,
        format="topojson",
        crs="EPSG:4326",
        original_feature_count=feature_count,
        retained_feature_count=feature_count,
        unkeyed_count=0,
        size_bytes=size_bytes,
        source_id=AC_SOURCE_ID,
        delimitation_vintage=AC_DELIM_VINTAGE,
        notes=(
            "Consolidated national AC TopoJSON (31 per-state 2008-delimitation "
            "AC shards merged + re-encoded; map-geometry rip Row 3, 2026-06-16). "
            "Frontend decodes object 'ac' + filters by state_ut_code."
        ),
    )

    final_rows = kept + [ac_row]
    written = compile_to_csv(final_rows, datasets_root, merge_with_existing=False)
    print(
        f"reseed-electoral-2024: dropped {dropped} delim=2008 electoral rows; "
        f"added national AC row ({feature_count} features, {size_bytes} bytes); "
        f"final boundary_layer.csv row count = {written}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
