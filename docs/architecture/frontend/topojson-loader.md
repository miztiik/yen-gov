# Frontend TopoJSON loader

**Last Updated**: 2026-05-31

How `frontend/src/lib/boundaries.ts` resolves boundary partitions to a `FeatureCollection` for the choropleth components.

## See also

- [docs/how-to/convert-geojson-to-topojson.md](../../how-to/convert-geojson-to-topojson.md) - producer side
- [#adr-0047-topojson-as-render-encoding](#adr-0047-topojson-as-render-encoding) - design rationale (folded receipt below)
- [docs/architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm](../data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm)
- [docs/architecture/data/boundaries.md#adr-0031-boundary-geometry-strategy](../data/boundaries.md#adr-0031-boundary-geometry-strategy)
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

Vite dead-code-eliminates these branches when `VITE_BENCH` is unset, so production bundles pay zero cost.

## Conformance invariants

[frontend/src/contracts/boundaries-conform.test.ts](../../../frontend/src/contracts/boundaries-conform.test.ts) enforces:

1. **Sibling pair is the durable contract**: every `.topojson` under `datasets/boundaries/in/**` has a sibling `.geojson` in the same directory. The earlier "cleanup commissioned" framing was REJECTED by the user on 2026-05-31 ("we are using a combination of both") and the sibling-retirement plan was deleted. Both encodings stay; the loader's topo-first / geojson-fallback path is the design, not a transitional state.
2. **Feature-count parity**: `topojson.feature(t, t.objects.<name>).features.length === geojson.features.length` per shard. Coordinate equality is NOT asserted (quantization is by design lossy).
3. **No orphan topojson**: every shipped `.topojson` lives at a Hive partition declared in `datasets/boundaries/boundary_layers.parquet`.

The conformance test is the upstream gap-detector. CI fails on any drift; the loader's fallback path is the runtime safety net, not the contract.

## When NOT to use this loader

- **Vector tiles / PMTiles** for villages + pincodes - the loader has no PMTiles path today. When that work lands, the loader will gain a `.pmtiles`-first branch before topojson.
- **Raster basemap tiles** - already MapLibre's `raster-tile` source path; outside this loader.
- **Direct fetch of a specific partition by Hive path** - the loader assumes the `GeoLevel` enum maps cleanly via `boundaryRelPath`. For arbitrary paths (e.g. one-off dev scripts), prefer `loadBoundaryFromPath(baseGeoRelPath, label)` (lower-level entry point).

## Relation to the ADRs

- **ADR-0047** picks TopoJSON over GeoJSON for the 8 in-scope Track-A boundary layers and codifies the loader's topo-first / geo-fallback contract.
- **ADR-0031** prior format-split-by-layer-size table is partially superseded by ADR-0047 (the GeoJSON cells become TopoJSON; PMTiles trigger column unchanged). ADR-0031 amendment noted.
- **ADR-0030** canonical-store shape is unchanged: doubled `.geojson` + `.topojson` siblings are two encodings of one logical layer keyed in `boundary_layers.parquet`.

## Provenance note

`.topojson` siblings carry NO new `source_id`. The encoding is a derivative of the existing `source_id`-bearing GeoJSON; `boundary_layers.parquet` rows are unchanged across the conversion. Holy Law #9 is satisfied because encoding is not provenance (see [docs/concepts/data-provenance.md](../../concepts/data-provenance.md)).

## Design rationale

This section folds in the receipt from the originating ADR that pinned the encoding choice for this subsystem (originating ADR-0047-topojson file deleted in D-DOC3.10 closure 2026-06-05), per the ADR retirement contract ([decision-index.md](../../reference/decision-index.md)). The verbatim rejected alternatives live under [Rejected alternatives](#rejected-alternatives).

### ADR-0047: topojson-as-render-encoding

**Context.** yen-gov shipped boundary polygons as GeoJSON under `datasets/boundaries/in/<layer>/<partition>/all.geojson`. These files are fetched by the static frontend on every relevant page (India home, state, district pages). For mid-to-large feature counts (state ~36, district ~780, AC ~4,100), GeoJSON's verbosity and lack of topology-sharing made payloads 60-80% larger than necessary, hurting wire bytes and cold-cache time-to-first-paint on slow mobile networks. TopoJSON (Bostock 2012) is a GeoJSON-extension format that shares arc geometry across adjacent polygons and quantises coordinates to an integer grid; for shared-edge admin polygons (which all yen-gov boundary layers are), this produces dramatic size reductions with no semantic loss at typical choropleth zoom levels.

**Decision.** TopoJSON becomes the preferred shipping encoding for the 8 in-scope boundary layers (country, state, district, subdistrict, AC, PC, ULB-wards, panchayats). Villages and pincodes are out-of-scope (their bottleneck is browser render cost, not file format - they get the Track A2 PMTiles successor). **In-place conversion only, no external source adoption.** Both candidate external mirrors (geoBoundaries `wmgeolab`, `udit-001`) strip LGD codes from their published features (Max audit 2026-05-31); adopting them as canonical breaks every join in the canonical Parquet store. yen-gov's existing LGD-keyed GeoJSONs are converted to TopoJSON in place; the canonical identity surface is unchanged. `.topojson` siblings carry no new `source_id` (encoding is a derivative of the existing `source_id`-bearing GeoJSON; Holy Law #9 satisfied because encoding is not provenance). Tooling is the Mapshaper CLI (Fowler verdict 2026-05-31) subprocess-invoked from Python lift orchestrators with a pinned version. Quantisation is the OWID default 1e5 (~1 m precision), hardcoded; revisited per-layer only if visual-diff smoke flags artifacts at home-page zoom. Loader contract: frontend prefers `.topojson`; on 404 or parse-error falls back to `.geojson` sibling; no user toggle. The conformance test is the upstream gap-detector - CI fails if a declared partition lacks both formats.

**Phasing.** Phase 1 (India home, state layer) shipped behind a measured STOP CONDITION (Jony's noise-floor methodology, no fixed % target). Phases 2-3 cascaded once Phase 1 proved the encoding swap cleared the noise floor on real throttled hardware.

**Relation to ADR-0031.** **Partially supersedes** ADR-0031's format-split-by-layer-size table: the GeoJSON cells in that table become TopoJSON post-PR-Z4; the PMTiles trigger column is unchanged. The rest of ADR-0031 (sibling-family, manifest discovery, no-move rule, deletion exclusion) is unchanged. Track A `.geojson` sibling-retirement was REJECTED by the user on 2026-05-31 ("we are using a combination of both"); both encodings stay on disk and the topo-first / geojson-fallback contract in `loadBoundaryData()` is the durable design.

**Consequences (positive).** 60-80% wire-byte reduction on state / district / AC / PC / wards / panchayats (Fowler estimate based on mapshaper production-pipeline history). Faster cold-cache TTFP on Slow-4G + 4x-CPU-throttled mobile (Jony noise-floor-multiple verification gate). Lower egress cost on GH Pages. No new upstream dependency in canonical store (Max). Loader fallback contract means a broken topojson file degrades gracefully instead of breaking the page (user instruction).

**Consequences (negative).** Adds Node toolchain (Mapshaper CLI) to dev + CI install requirements (single global package, pinned version - smaller surface than a per-repo `node_modules`). `topojson.feature()` decode step adds ~main-thread cost per page load (Jony metric 3 - must not regress beyond noise floor). Doubles boundary file count during the transition (sibling `.geojson` + `.topojson`); the user's "we are using a combination of both" verdict makes the doubling durable, not transitional. Mapshaper version becomes a contract surface - a version bump = schema-version-style migration (regenerate all topojson under new version, validate diff, swap, drop old).

**Acceptance evidence (2026-05-31).** All 8 Track A boundary layers (country, state, district, subdistrict, AC, PC, ULB-wards, panchayats) AND both Track A2 layers (villages, postal) ship `.topojson` siblings 100% coverage. Loader topojson-first / geojson-fallback contract live in production via `frontend/src/lib/boundaries.ts`. Conformance test asserts feature-count parity per shard via `frontend/src/contracts/boundaries-conform.test.ts` (4137 assertions green per PR #500 gate). PR map: P0 (#486), P1 (#487), P2 (#488), P3 (#489), P4.1 (#490), P4.2 (#491), P4.3 (#493 partial + #500 complete), P4.4 (#494 partial + #502 complete), P4.5 (#495 partial + #504 complete), P4.6 (#492), batched converter (#496), P5.1+P5.2 distill (#498), P5.3 PMTiles successor (#497), P5.4 retirement plan (#499), P5.5 ADR flip (#505).

## Rejected alternatives

### ADR-0047 rejected alternatives

Verbatim from the originating ADR. Append-only per ADR retirement contract.

- **A - Adopt geoBoundaries as canonical for ADM0-ADM2.** geoBoundaries normalises every feature to its universal schema (`shapeName`, `shapeISO`, `shapeID`, `shapeGroup`, `shapeType`). The LGD code that yen-gov uses as canonical join identity is stripped, even though geoBoundaries' own metadata cites `lgdirectory.gov.in` as upstream for ADM2/3/4. Adopting would force either a fragile 780-row name-crosswalk (Anantnag vs Anantnag vs Anant Nag, plus bifurcation drift) or upstream PR to wmgeolab (no SLA). Both costlier than in-place conversion. See [docs/architecture/data/boundaries.md](../data/boundaries.md) section "2026-05-31 2026-05-31-geoboundaries-udit001-source-audit" (lifted 2026-06-08 G4 from `notes/2026-05-31-geoboundaries-udit001-source-audit.md`).
- **B - Adopt udit-001.** Same LGD-strip problem at smaller coverage (country + state + per-state district only). Hobbyist provenance. No benefit over (A).
- **C - Hybrid: geoBoundaries as render-only tier with canonical-Parquet lookup by indexed feature ID.** Possible but adds a load-bearing runtime join in the frontend that does not exist today. High engineering cost. Defers all the LGD-strip risk to a brittle indexed lookup. Rejected - encoding swap delivers the perf win without introducing new identity surface.
- **D - Python `topojson` package.** Less battle-tested than Mapshaper on Indian coastline multipolygons (Sundarbans, Kutch, Konkan). Pure-Python wins on integration aesthetics but loses on production-grade output. Fowler verdict 2026-05-31.
- **E - Vector tiles (PMTiles / MVT) as Phase 1.** Right answer for villages + pincodes; wrong answer for state + district where feature counts are small enough that the tile overhead exceeds the gain.
- **F - Replace `.geojson` in place (no sibling kept).** Rejected per user 2026-05-31: "retain geojson until full swap; we will delete in separate plan". The retirement was deferred; the user further REJECTED the retirement itself on 2026-05-31 ("we are using a combination of both") and the sibling-retirement plan was deleted. Both encodings stay on disk as the durable design.
- **G - User-facing toggle for format.** Rejected per user 2026-05-31: "no user toggle". Loader behaviour is deterministic - topojson-first with mechanical fallback on parse failure.
