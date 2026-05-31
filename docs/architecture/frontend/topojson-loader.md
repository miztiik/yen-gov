# Frontend TopoJSON loader

**Last Updated**: 2026-05-31

How `frontend/src/lib/boundaries.ts` resolves boundary partitions to a `FeatureCollection` for the choropleth components. Distilled from [docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md](../../../docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md) row P2.3 and the fallback contract in section 5.

## See also

- [docs/how-to/convert-geojson-to-topojson.md](../../how-to/convert-geojson-to-topojson.md) - producer side
- [docs/architecture/decisions/0047-topojson-as-render-encoding.md](../decisions/0047-topojson-as-render-encoding.md)
- [docs/architecture/decisions/0030-canonical-store-shape.md](../decisions/0030-canonical-store-shape.md)
- [docs/architecture/decisions/0031-boundary-geometry-strategy.md](../decisions/0031-boundary-geometry-strategy.md)
- [docs/architecture/frontend/data-loading.md](data-loading.md) - Vite middleware + GH Pages publish

## Public API

Three exports form the contract. They live in `frontend/src/lib/boundaries.ts`.

### `boundaryRelPath(level, parentDistrictLgd?, stateLgd?) -> string`

Resolves a `GeoLevel` plus its parent identifiers to the `.geojson` partition path relative to the `boundaries/in/` root. Stable since before the TopoJSON migration; every existing caller continues to work unchanged.

Example: `boundaryRelPath("state")` returns `"states/all.geojson"`.

### `boundaryRelPaths(level, parentDistrictLgd?, stateLgd?) -> { topo: string; geo: string }`

Sibling of `boundaryRelPath` that returns BOTH the `.topojson` and `.geojson` paths for the partition. Use this from callers that need to reason about both formats explicitly (e.g. preload hints, conformance tests).

Example: `boundaryRelPaths("state")` returns `{ topo: "states/all.topojson", geo: "states/all.geojson" }`.

### `loadBoundaryData(level, parentDistrictLgd?, stateLgd?) -> Promise<FeatureCollection | null>`

The single load entry point for choropleth components. Implements the **topo-first / geo-fallback** contract:

1. Fetch `<base>.topojson`. On `200`, decode via `topojson.feature()` and return.
2. On `404` (no sibling shipped yet): silently fall through to `<base>.geojson`. No console warning - this is the expected steady state during the migration.
3. On HTTP error other than `404`, JSON parse error, or topojson decode error: log `[fallback] topojson:<level> <reason>; falling back to geojson` console warning and fall through to `<base>.geojson`.
4. On geojson fetch failure or `!ok`: return `null` (graceful degradation; the choropleth component renders a "no data" state).

`loadBoundary(...)` is preserved as a backwards-compatible thin wrapper around `loadBoundaryData` so the migration was non-breaking. New call sites SHOULD use `loadBoundaryData` directly.

## Perf instrumentation

When `import.meta.env.VITE_BENCH === "1"` the loader emits `performance.mark` / `performance.measure` calls so the Playwright bench harness can attribute fetch+parse cost per layer:

- `boundary-fetch-start:<label>` and `boundary-source-added:<label>` marks.
- `boundary-load:<label>` measure between them (the load-bearing signal).
- `boundary-load:<label>:<format>` measure tagging which sibling won (`topojson` or `geojson`).

Vite dead-code-eliminates these branches when `VITE_BENCH` is unset, so production bundles pay zero cost. See [docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md](../../../docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md) row P1.2 for the harness contract.

## Conformance invariants

[frontend/src/contracts/boundaries-conform.test.ts](../../../frontend/src/contracts/boundaries-conform.test.ts) enforces:

1. **Sibling pair is the durable contract**: every `.topojson` under `datasets/boundaries/in/**` has a sibling `.geojson` in the same directory. The earlier "cleanup commissioned" framing was REJECTED by the user on 2026-05-31 ("we are using a combination of both") and the sibling-retirement plan-doc was deleted. Both encodings stay; the loader's topo-first / geojson-fallback path is the design, not a transitional state.
2. **Feature-count parity**: `topojson.feature(t, t.objects.<name>).features.length === geojson.features.length` per shard. Coordinate equality is NOT asserted (quantization is by design lossy).
3. **No orphan topojson**: every shipped `.topojson` lives at a Hive partition declared in `datasets/boundaries/boundary_layers.parquet`.

The conformance test is the upstream gap-detector. CI fails on any drift; the loader's fallback path is the runtime safety net, not the contract.

## When NOT to use this loader

- **Vector tiles / PMTiles** for villages + pincodes - the loader has no PMTiles path today. Commissioned at [TODO/2026-05-31-village-pincode-vector-tiles-plan.md](../../../TODO/2026-05-31-village-pincode-vector-tiles-plan.md). When that plan lands, the loader will gain a `.pmtiles`-first branch before topojson.
- **Raster basemap tiles** - already MapLibre's `raster-tile` source path; outside this loader.
- **Direct fetch of a specific partition by Hive path** - the loader assumes the `GeoLevel` enum maps cleanly via `boundaryRelPath`. For arbitrary paths (e.g. one-off dev scripts), prefer `loadBoundaryFromPath(baseGeoRelPath, label)` (lower-level entry point).

## Relation to the ADRs

- **ADR-0047** picks TopoJSON over GeoJSON for the 8 in-scope Track-A boundary layers and codifies the loader's topo-first / geo-fallback contract.
- **ADR-0031** prior format-split-by-layer-size table is partially superseded by ADR-0047 (the GeoJSON cells become TopoJSON; PMTiles trigger column unchanged). ADR-0031 amendment commissioned at parent plan P5.5.
- **ADR-0030** canonical-store shape is unchanged: doubled `.geojson` + `.topojson` siblings are two encodings of one logical layer keyed in `boundary_layers.parquet`.

## Provenance note

`.topojson` siblings carry NO new `source_id`. The encoding is a derivative of the existing `source_id`-bearing GeoJSON; `boundary_layers.parquet` rows are unchanged across the conversion. Holy Law #9 is satisfied because encoding is not provenance (see [docs/concepts/data-provenance.md](../../concepts/data-provenance.md)).
