# datasets/features/

**Last Updated**: 2026-05-22

Citizen-facing feature geometry that doesn't fit the canonical Parquet store. Point, line, and polygon data published as GeoJSON for cross-language consumption (DuckDB-WASM can't render geometry; MapLibre reads GeoJSON natively).

## Current contents

| Path | Type | Adapter | Consumer | Notes |
| --- | --- | --- | --- | --- |
| `in/energy/power-plants.geojson` | FeatureCollection (Point) | [`backend/yen_gov/sources/india_geodata/power_plants.py`](../../backend/yen_gov/sources/india_geodata/power_plants.py) | Frontend energy-hub map | Generating stations across India from india-geodata + CEA upstream. See [`docs/research/energy-power-plants.md`](../../docs/research/energy-power-plants.md). |
| `in/energy/power-plants.geojson.metadata.json` | Sidecar | Same | Same | Provenance + bounding box + count. |

## Why GeoJSON, not Parquet

- **No analytical query path**: power-plant points feed a single map layer; no filter/aggregate workload that warrants DuckDB-WASM.
- **MapLibre native ingest**: avoids a runtime conversion step that Parquet → GeoJSON would require.
- **Citizen page payload size**: small enough (~few hundred KB) to ship inline without tiling.

## When this directory retires

Per Gregor audit #4 in [`TODO/20260521-phase-2-preflight-audit-gregor.md`](../../TODO/20260521-phase-2-preflight-audit-gregor.md), boundaries (`datasets/boundaries/`) graduate to a fifth P.\* family using PMTiles for large layers + a citation-ledger row per upstream. When that work happens, the same codec decision (PMTiles vs GeoJSON) gets re-applied here. Today's small two-file shape stays GeoJSON.

## Adding a new feature layer

1. Authoring adapter goes under `backend/yen_gov/sources/<source>/` and writes to `datasets/features/in/<topic>/<name>.geojson`.
2. Sibling `.metadata.json` carries `{"source_id": "src-<12chars>", "feature_count": N, "bounds": [...]}`. `source_id` MUST resolve in `datasets/taxonomy/sources.parquet` (CLAUDE.md §12).
3. Add a row to the table above.
4. Update [`docs/reference/data-coverage-report.md`](../../docs/reference/data-coverage-report.md) with the citizen-facing one-liner.

## See also

- [`docs/architecture/data/canonical-store.md`](../../docs/architecture/data/canonical-store.md) §2b.3 — retirement table.
- [`docs/architecture/data/boundaries.md`](../../docs/architecture/data/boundaries.md) — sister codec discussion for administrative geometry.
