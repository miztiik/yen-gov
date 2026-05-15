# Map — cartography & geographic overlays

**Last Updated**: 2026-05-15 (revision: Phase 3 Lakshadweep callout inset)

The map is the primary visual surface for the Citizen and Strategist personas. It composes multiple layers — administrative boundaries, election outcomes, and (future) socio-economic overlays — over a vector basemap. This page covers the library choice, the boundary data pipeline, layer composition, and how the map integrates with [Psephlab](psephlab.md).

## Library: MapLibre GL JS

The frontend uses **[MapLibre GL JS](https://maplibre.org/)** (open-source fork of Mapbox GL JS pre-license-change) for all map rendering.

### Why MapLibre

- **Multi-layer composition.** Election choropleths, district boundaries, socio-economic bubbles, and labels all stack as independent layers with their own data sources, paint expressions, and event handlers. d3-geo can do this but quickly becomes a custom render loop; MapLibre handles it natively.
- **Vector tiles + data-driven styling.** Party color and margin opacity become declarative `paint` expressions over a vector source. Animating between scenarios is a single `setPaintProperty()` call that the GPU interpolates.
- **Pan/zoom/touch out of the box.** Mobile-quality interaction with no custom code.
- **GitHub Pages compatible.** Fully client-side; works with free OSM raster tiles or self-hosted PMTiles (preferred — see below).
- **Future-proof for socio-economic overlays.** Heatmaps, bubbles, time-series, and 3D extrusions are all built-in layer types. The user explicitly named this as a v2+ requirement; MapLibre is the only choice in the list that doesn't require a rewrite to support it.
- **Bundle.** ~250 KB gzipped. Acceptable given it replaces what would otherwise be d3-geo + custom interaction code.

### Map library — alternatives considered

- **d3-geo with TopoJSON.** Smallest bundle, full SVG control. Rejected because: (a) every overlay (bubbles, heatmaps, labels-with-collision) is hand-rolled; (b) pan/zoom/touch is a pile of custom event handlers; (c) when the user adds socio-economic layers, we would migrate then anyway. Choosing d3-geo for v1 only to migrate later is the worst of both worlds.
- **Leaflet + GeoJSON.** Lightweight (~40 KB), great ergonomics. Rejected because: (a) raster-only by default; (b) animation of fill colors between scenarios is jerky; (c) no GPU-accelerated styling expressions, so per-AC paint changes touch the DOM.
- **Mapbox GL JS (proprietary).** Same API as MapLibre but requires a Mapbox access token and traffic-based pricing. Rejected on principle (CLAUDE.md "Open source first") and operationally (we can't ship a public token in a static bundle).
- **Deck.gl.** Powerful for large datasets and 3D, but overkill for choropleths and adds React/Lumagl baggage.

## Boundary data pipeline

Indian administrative boundaries are not packaged as one clean source. The pipeline:

```
datameet/maps + HTL/shapefiles  ← upstream (CC-BY 4.0 / MIT)
   │
   ▼ (one-time per delimitation cycle, run locally on Linux/macOS/WSL2 — see tools/boundaries/README.md)
tools/boundaries/build.py    ← download → mapshaper simplify → tippecanoe → PMTiles
   │
   ▼
datasets/boundaries/in/      ← committed PMTiles + manifest.json (populated only after CI run; absent on a fresh clone)
   ├── india-states.pmtiles
   └── ac/
       ├── S22-ac.pmtiles    (Tamil Nadu 234 ACs)
       ├── S25-ac.pmtiles    (West Bengal 294 ACs)
       ├── S11-ac.pmtiles    (Kerala 140 ACs)
       └── S03-ac.pmtiles    (Assam 126 ACs — see delimitation_warning in pipeline.json)
   └── manifest.json         (populated by CI; resolver falls back to GeoJSON snapshot or upstream when missing)
```

Sources:

- **States outline:** [datameet/maps](https://github.com/datameet/maps) `States/Admin2.shp` (CC-BY 4.0). Includes the post-2014 Telangana split, the post-2019 Ladakh split (PR #73), and the merged Dadra-and-Nagar-Haveli-and-Daman-and-Diu UT. Replaces the geohacker/india GADM v2 (~2012) layer that pre-dated all three reorganizations.
- **AC outlines:** [HindustanTimesLabs/shapefiles](https://github.com/HindustanTimesLabs/shapefiles) `state_ut/<state>/assembly/*.json` (MIT). One file per state, joined on `AC_NO`.

Each PMTiles file is ~200–500 KB (simplified to ~10 m precision for choropleths — election maps don't need 1 m).

The pipeline is **build-time only**, not runtime. Boundaries change infrequently (delimitation cycles); fetching them at user load is wasted bandwidth. They live under `datasets/boundaries/in/` once the workflow has produced them; until then, the resolver below transparently fetches GeoJSON from upstream so the map still renders. Per CLAUDE.md §12 every PMTiles file is paired with a `manifest.json` entry recording `{ url, fetched_at }` for the upstream commit.

### Why PMTiles

[PMTiles](https://github.com/protomaps/PMTiles) is a single-file vector-tile container that MapLibre reads via a [protocol handler](https://github.com/protomaps/PMTiles/tree/main/js#maplibre-gl-js). One file per layer = one HTTP request, range-requested for the visible viewport. The alternative (a directory of `{z}/{x}/{y}.pbf` tiles) would mean shipping thousands of tiny files, which GitHub Pages handles poorly and which inflates the deploy artifact.

### Boundary pipeline — alternatives considered

- **Runtime fetch from a public CDN (e.g. data.gov.in).** Rejected: introduces an external availability dependency the static bundle would otherwise not need. CLAUDE.md ADR-0003 already established a no-runtime-fetch posture for raw artifacts.
- **GeoJSON files committed directly.** Workable for state-level (~50 KB India) but blows up at AC level (TN AC GeoJSON is ~2.5 MB unsimplified). PMTiles is ~5× smaller and supports per-zoom precision.
- **Self-host vector tiles on a tile server.** Requires infrastructure (Holy Law #1 violation).

## Layer composition

A typical state-level Explore view stacks:

```
[base]      OSM raster (CARTO Voyager style, low-saturation)  — context
[admin]    state-boundary line layer from india-states.pmtiles — orientation
[ac-fill]  AC choropleth from S22-ac.pmtiles + result.summary  — primary signal
[ac-line]  AC boundary thin line                              — separator
[labels]   district labels from MapLibre default              — wayfinding
```

Each layer is added to the same `Map` instance. The `ac-fill` layer's `paint['fill-color']` is a data-driven expression keyed on the joined `result.summary` row's `winner_party_eci_code`, mapped through the user's color overrides. Margin opacity is `paint['fill-opacity']` driven by margin percentage.

When Psephlab is active, the `ac-fill` layer's data source is swapped from `result.summary` to `engine.run(actuals, scenario).perAcWinners`. The transition is a `setPaintProperty` call wrapped in a `flyTo`-style animation; the GPU interpolates the colors. No DOM thrash, no per-frame React/Svelte reactivity.

## Color & overrides

Party color comes from [`overview.md` > color scheme](overview.md#color-scheme): a default canonical palette in `frontend/src/lib/colors/parties.default.ts`, with per-party user overrides from `localStorage` and (in shared scenarios) from the URL fragment. The map reads this map of overrides and rebuilds the `fill-color` expression when it changes.

Margin shading uses opacity, not hue: a 51%–49% AC paints the winning party at ~30% opacity; a 70%+ landslide paints at ~95%. This keeps the map honest — the eye reads a tied AC as "barely won" rather than as a confident block of color.

## Future overlays (v2+)

The user explicitly called out non-election overlays. The following are designed for but not implemented in v1:

| Layer | Source | MapLibre layer type |
| --- | --- | --- |
| Population density | Census 2021 + WorldPop | `heatmap` or `fill` with extrusion |
| Literacy rate | Census 2021 | `fill` choropleth (toggleable) |
| Per-capita income | NSS / state stats bureau | `fill` choropleth |
| Caste / community composition | Census | `bubble` (custom symbol layer) |
| Voter turnout history | ECI past elections | `fill` choropleth, time-slider |

Each lives under `datasets/overlays/in/<topic>.pmtiles` with the same provenance contract. The map UI exposes them as a togglable layer panel in the sidebar; only one socio-economic layer is rendered at a time (cognitive load), but it can stack on top of the election choropleth via the `fill-opacity` slider.

## Implementation notes (Phase 1d)

The first cut of the map components landed under `frontend/src/lib/maplibre/`:

- `sources.ts` — declarative table of boundary sources (one per India-states + per-state AC layers), each with the upstream URL, the property name to join on (`ST_NM` for datameet states, `AC_NO` for HTL AC files), and license attribution. The hand-maintained `STATE_NAME_TO_ECI` map bridges English state names to ECI state codes (`Tamil Nadu` → `S22`, …) so the India choropleth can look up `result.summary.json` per state.
- `MapChoropleth.svelte` — generic, library-agnostic to its parents. Takes a `BoundaryEntry`, a `fills` map keyed by the join-property value, optional `opacities` and `tooltips`, and `onSelect`/`onHover` callbacks. Owns map lifecycle and rebuilds `fill-color` / `fill-opacity` paint expressions whenever its props change (Svelte 5 `$effect`).
- `IndiaMap.svelte` and `StateAcMap.svelte` — thin domain wrappers. `IndiaMap` fetches `result.summary.json` for every state in `STATE_NAME_TO_ECI` and colors each by leading party (most seats won, votes as tiebreak). `StateAcMap` queries `results.sqlite` via the cached `getDb` for `(ac_eci_no → winner_party_eci_code, party_short, margin_pct)` and colors AC fills by winning party with opacity proportional to margin (clamped to 30 % to keep the legend readable; ties drop to the floor so razor-thin wins visually scream "close").

### Source resolution: manifest → local snapshot → upstream fallback

`resolveSource(entry)` is **three-tier**, tried in order, first hit wins:

1. **PMTiles via manifest** — when the boundary CI workflow has run and committed PMTiles, the resolver returns `{ kind: "pmtiles", url: "pmtiles:///data/boundaries/in/<id>.pmtiles" }` and registers the `pmtiles` protocol shim once per page.
2. **Local GeoJSON snapshot** — the second tier (added in the May 2026 UX audit). When `BoundaryEntry.geojson_local_path` is set, the resolver returns `{ kind: "geojson", url: "/data/<path>" }` pointing at a snapshotted file under `datasets/boundaries/in/geojson/`. Snapshots are produced by `tools/boundaries/snapshot.py` (see below).
3. **Upstream raw GeoJSON** — last-resort live fetch of the original `geojson_url` declared on the entry. Slow (TN AC ~1 MB, India states ~22 MB) and depends on raw.githubusercontent.com being reachable; only kicks in when no snapshot exists for that layer.

Why the middle tier exists. Before the snapshot tier, the manifest probe missing → straight to a 1–22 MB fetch from GitHub on every cold load, and TN often appeared "blank" because the polygons hadn't streamed in yet. The snapshot tier is local, instant, and version-pinned. PMTiles is still the long-term winner (smaller payload, range requests, zoom-aware precision); the snapshot tier is the gap-filler until `tools/boundaries/build.py` is run and its PMTiles output committed.

### `tools/boundaries/snapshot.py`

Standalone, dependency-free Python script (urllib only, per `tools/` self-contained rule). Reads `tools/boundaries/pipeline.json`, downloads each entry, writes the GeoJSON to `datasets/boundaries/in/geojson/<name>.geojson` and a sidecar `<name>.geojson.sources.json` carrying the CLAUDE.md §12 `sources: [{url, fetched_at}]` array.

The sidecar exists because GeoJSON's `FeatureCollection` schema doesn't accept arbitrary top-level keys cleanly; an out-of-band sidecar is the lowest-friction way to carry provenance without bending the spec.

A 12 MB per-file budget covers all current layers, including the converted datameet states layer (~11 MB at coord_precision=3, gzips to ~3 MB). Per-state AC layers (Tamil Nadu, Kerala, West Bengal, Assam) all fit comfortably and are committed.

### `AC_NO` type-coercion

The HTL shapefiles (the upstream for state-level AC choropleths) export `AC_NO` as a **string** (`"2"`), while the parent results data keys ACs by integer `eci_no`. MapLibre's `["match"]` paint expression does strict equality, so a numeric key never matches a string property — leaving every polygon at the layer's default fill (the long-standing "TN constituency map renders blank slate-50" bug).

`MapChoropleth.svelte`'s `fill_expression()` / `opacity_expression()` / `highlight_filter()` now wrap the property accessor in `["to-number", ["get", entry.join_property]]` whenever the lookup keys are all integer-shaped. State-name layers (`ST_NM`) keep the plain `["get", …]` form. The numeric-vs-string detection is a per-call regex check on the keys — cheap and correct without introducing a per-entry "key type" config field.

### Constituency drilldown — highlighted-AC mini-map

`StateAcMap.svelte` accepts an optional `highlight_eci_no?: number`. When set, the matched AC paints at full opacity and every other AC drops to `base × 0.18`, and a third line layer (slate-900, 2.5 px) outlines just the focused feature. This drives the per-AC drilldown page's "Location in {state}" section, giving users a "you are here" sense without a separate map component. The highlight filter goes through the same numeric-coercion path as fills/opacities.

### Bundle: static import + manualChunks code-split

MapChoropleth statically imports `maplibre-gl` and `pmtiles`. Earlier attempts at `import("maplibre-gl")` inside `onMount` (the textbook pattern for lazy-loading heavy libs) produced no chunk file at all under vite 6 + `@sveltejs/vite-plugin-svelte` 4 — the dynamic import was silently elided despite the rest of the component compiling correctly. We did not chase the underlying cause; static imports paired with a `manualChunks` directive in `vite.config.ts` give the same end-state (a separate cacheable chunk) without fighting the toolchain.

Chunk sizes after Phase 1d:

| Chunk | Raw | gzipped | When loaded |
| --- | --- | --- | --- |
| `index-*.js` (app) | 174 KB | 63 KB | every route |
| `maplibre-*.js` (maplibre-gl + pmtiles) | 805 KB | 219 KB | first map mount; cached thereafter |
| `index-*.css` (app + maplibre.css) | 80 KB | 13 KB | every route |
| `sql-wasm-*.wasm` | 644 KB | 323 KB | first SQL query |

The maplibre chunk loads in parallel with the app chunk on the first route that mounts a map, then stays cached for the rest of the session.

## Boundary loader (`frontend/src/lib/boundaries.ts`) — Phase 2 of TN-GRANULAR-GEO-PLAN

A single typed entry point — `loadBoundary(level, parentDistrictLgd?, stateLgd?)` — replaces the per-component `fetch('/some-boundary.json')` pattern. The loader is a pure path resolver (`boundaryBasename`) wrapped around a fetcher; it does not know about colours, click handlers, or choropleth values. It only answers: *given (level, parent district lgd, state lgd), where is the GeoJSON and what property carries the join key?*

### Path table

| Level | URL | Join key |
| --- | --- | --- |
| `country` | `india-soi.geojson` | none (silhouette only) |
| `state` | `india-states.geojson` | `ST_NM` (datameet lineage — English name) |
| `district` | `india-districts.geojson` | `dist_lgd` (LGD numeric) |
| `subdistrict` | `<S>-subdistricts.geojson` (one file per state) | `subdt_lgd` (ramSeraph upstream property) |
| `village` | `<S>-villages-<dist_lgd>.geojson` (one file per district) | `vil_lgd` (ramSeraph upstream property) |

Property names match what ramSeraph's upstream actually emits — `subdt_lgd` / `vil_lgd` (not `subdist_lgd` / `village_lgd`). The plan referenced the longer names; the loader honours the disk shape, since renaming on the upstream feeds would mean shipping a parallel write pipeline (Holy Law #5: structural fixes only — and "use what's actually on disk" is the structural fix).

### Per-district village split + index manifest

The per-district village split is the contract Phase 1b nailed: a single district click pulls ~10–600 KB instead of the full TN villages bundle (~200 MB raw, ~50 MB even at `coord_precision=4`). Which district shards exist on disk is communicated by the per-state index manifest (`<S>-villages-index.json`, schema `boundary.villages_index.schema.json` v2.0). The loader reads it once, caches the set of present `dist_lgd` codes, and returns `null` for any village query whose district is absent — never speculatively probes a 404 on hover.

### 404-as-null contract

Every `loadBoundary` call that hits a missing file resolves to `null` rather than throwing. Callers (the choropleth, drill-down components) degrade gracefully — show an inline toast, keep the parent layer visible — instead of crashing the page. This mirrors `resolveSource()` in `maplibre/sources.ts`. Caller-input bugs (asking for `subdistrict` without a state, asking for `village` without a parent district) DO throw — those are tests-should-have-caught-this conditions, not graceful-degradation conditions.

### Why `fetch` and not `import.meta.glob`

Vite's `import.meta.glob` would let the bundler see the per-district shards at build time, but `datasets/` is **served at runtime** via the dev-server middleware + Pages, not bundled into the SPA. The glob would not see `datasets/` even if the right primitive existed. Runtime `fetch` is the correct primitive for "load when clicked".

### Test coverage (CLAUDE.md §15)

Four files in `frontend/src/lib/`:

- `boundaries.path.test.ts` (unit, 13 tests) — pure resolver, no I/O.
- `boundaries.integration.test.ts` (integration, 9 tests) — `fetch` mocked at the loader's contract boundary (Holy Law #7 carve-out: the loader's contract IS the fetch boundary). Exercises path composition, 404-as-null, network-error-as-null, missing-index degradation, and per-state index caching.
- `boundaries.contract.test.ts` (contract, 156 tests) — sibling-`sources.json` presence per `*.geojson`, join-key property presence on every LGD-keyed feature (sampled at first/middle/last to bound runtime), index→shard one-to-one consistency, orphan-file detector against the loader's path table.
- `boundaries.budget.test.ts` (contract, 44 tests) — per-shard byte ceilings (4 MB village / 8 MB subdistrict / 16 MB national) and a chunk-count ratchet at 80 `*.geojson` files.

The orphan-boundary check lives next to the loader (in `boundaries.contract.test.ts`) rather than in `frontend/src/contracts/catalogue-coverage.test.ts`, because the catalogue test is concerned with **indicator** artifacts referenced by `topic-catalogue.json`. Boundary files are not indicators and the catalogue has no concept of them. The loader's path table IS the boundary equivalent of the catalogue, so the orphan check belongs at the same layer that produces the contract.

### Caching

The per-state villages index is memoised in a `Map<stateLgd, Promise<VillagesIndex | null>>` for the lifetime of the page. The GeoJSON shards themselves are not memoised by the loader — the browser HTTP cache + Pages' `Cache-Control` already do that, and a JS-side cache for ~50 MB of geometry is the wrong allocator. A test-only `_resetCachesForTesting()` is exported to keep vitest cases isolated; it is not part of the public API.

## Drill-down UX (Phase 3 of TN-GRANULAR-GEO-PLAN)

`IndicatorChoropleth.svelte` ships a state→district→subdistrict→village drill on TN-scoped indicators (`highlight_state === "S22"`). Sign-off: Jony APPROVED-WITH-EDITS 2026-05-15; the five edits are baked into the implementation as called out below.

### Zoom-and-replace (not stacked)

Each click discards the parent layer and renders the child layer in its place — same legend, same slider, same headline. The alternative (stacked layers with a fade-in child) was rejected on Jony's review because at village zoom the citizen has no spatial reference for "where in TN am I"; the breadcrumb glyph (below) carries that signal more cleanly than half-faded parent polygons.

### Breadcrumb pattern

Top-of-map nav: `India › Tamil Nadu › Coimbatore › Pollachi`. Each crumb is a back-affordance — clicking returns to that level (the `goBack(state, idx)` reducer in `drilldown.ts` pops the stack to that index and clears parent/state context that no longer applies).

- **14 px monochrome SVG glyph** beside each crumb name (Jony edit #2 — bumped from 12 px on Jony's request because at 12 px the centroid dot was indistinguishable from the bullet separator). The glyph reuses an inline `<svg>` rather than a new component file (per the plan: no new components for crumbs/glyphs — inline in the choropleth).
- **Re-clicking the active crumb is a recentre signal, not a no-op** (Jony edit #1). `goBack(state, stack.length)` returns the same state object referentially, which the choropleth observes and treats as "fit map to current bbox". Re-fitting the map handle is deferred until MapChoropleth grows a `recentre` prop; until then the click is logged but has no visible effect.

### Lazy fetch + spinner + dim

Each drill click invokes `loadBoundary(level, parentDistrictLgd, stateLgd)` from `boundaries.ts` lazily — village shards are never preloaded.

- **During fetch**: the map dims to 60 % opacity (CSS `opacity` transition, 250 ms ease-out) and a centred overlay surfaces "Loading <level> boundaries…" with a spinner (Jony edit #3 — exact polygon-overlay positioning requires the maplibre map handle for LngLat→pixel projection, deferred; the centred overlay + dim carries the "something is happening" signal honestly in the meantime).
- **On failure** (404, network error, missing index entry): `deeper_fetch_error` surfaces an inline amber toast at the bottom of the map ("village boundaries unavailable"); the breadcrumb is rolled back via `goBack` to the parent level so the citizen never lands on a level with no data underneath. This is the loader's 404-as-null contract bubbled up to the UI.

### min_grain gating

The `IndicatorMeta.min_grain` field (`country|state|district|subdistrict|village`, optional) gates click depth (Jony edit #4 + plan §Phase 3 goal #5). When set, `isLevelEnabled(candidate, min_grain)` refuses any drill below the floor; greyed crumbs in the breadcrumb surface `blockedCrumbTooltip(min_grain)` ("this indicator is measured at district level, not village") in their `title` attribute so the citizen reads the floor without a second tap.

The schema bump that lands `min_grain` on the on-disk `indicator.schema.json` is deferred to a follow-up commit; the TS type accepts the field today so the drill-down honours it as soon as a producer starts emitting it. (Per CLAUDE.md §11: the schema bump must precede the first artifact that sets the field.)

### Empty-state hatch + dual tooltip

When the active level has polygons with no value (the common case at deeper levels today, since no indicator emits district / subdistrict / village rows yet):

- **Per-polygon hover tooltip** is specific (Jony edit #5): "Nilgiris — no data, 2024" — naming the polygon and the selected time, never a generic "no data" string.
- **Legend chip** below the map shows the aggregate count, labelled with the unit so it reads unambiguously: "12 districts, no data" (not just "12 — no data" which the eye groups as a value bucket).

The diagonal-hatch fill on the polygon itself (the Phase 3 goal #6 visual) is deferred to a polish commit — implementing it requires extending `MapChoropleth` with a `fill-pattern` image registration (~30 LOC) and a per-key pattern selector. Tracked as a stub: until then, no-data polygons render with the existing default soft slate, and the count + tooltip carry the editorial signal.

### 250 ms transition + reduced motion

The fade-out / fade-in across drill levels uses a CSS `opacity` transition at 250 ms ease-out (plan §Phase 3 goal #7). When `prefers-reduced-motion: reduce` matches, `drill_transition_ms` collapses to 0 and the swap is instant. The actual map remount (the `{#key}` block re-keys MapChoropleth on level change) is what swaps the geometry; the opacity transition fades over the swap.

### Why this lives inline in `IndicatorChoropleth.svelte`

The plan was explicit: no new components for crumbs / glyphs — inline them in the choropleth. The drill state machine is the only seam carved out (`drilldown.ts`), and only because pure orchestration logic must be unit-testable without mounting Svelte (the project's vitest stack does not bundle `@testing-library/svelte`; see `IndicatorChoropleth.boundaries.test.ts` header for the reasoning).

## Diagonal-hatch fill for no-data polygons (Phase 4 d1 of TN-GRANULAR-GEO-PLAN)

Pulled forward from Phase 3 c3 deferral. The drill-down's deeper levels (district / subdistrict / village) currently render as "no data" because no indicator emits rows at those grains yet. A flat slate-200 fill on every polygon reads as "this region has the minimum value" — indistinguishable from the lowest choropleth bucket. The well-known cartographic convention for missing-data is a **diagonal hatch** overlay, which reads unambiguously as "different kind of empty".

### Implementation

A pure helper in `frontend/src/lib/maplibre/hatch.ts` (`diagonalHatch()`) generates an 8×8 RGBA tile of slate-400 stripes on transparent background. `MapChoropleth.svelte` registers it once on `map.on("load", …)` via `map.addImage("yen-hatch", …)` (idempotent — guarded by `hasImage`). A second fill layer `yen-fill-hatch` sits between the flat-fill and line layers, painted with `fill-pattern: "yen-hatch"`. Its filter selects features whose join-key is **not** in the `fills` map, gated on the new `hatch_unmapped: boolean = false` prop (default off → no behaviour change for existing consumers).

`IndicatorChoropleth.svelte` opts in (`hatch_unmapped={drill_state.level !== "state"}`) so deeper drill levels get the hatch automatically until a producer starts emitting district / subdistrict / village rows.

### Why the helper is pure

Vitest cannot mount maplibre (no @testing-library/svelte, jsdom has no real canvas). Carving the pattern generator out of the Svelte component lets us assert the pixel layout directly (`hatch.test.ts`: 5 cases — buffer shape, default colour, transparency, seam-tiling, custom colour). The wiring inside the component is paint-only — no behavioural branching beyond the filter rebuild already covered by the existing `repaint()` effect.

## Recentre signal (Phase 4 d3 of TN-GRANULAR-GEO-PLAN)

Pulled forward from Phase 3 c3 deferral. Jony's edit #1 in the Phase 3 sign-off was: "re-clicking the active crumb is a recentre, not a no-op." The drill state machine (`drilldown.ts`) returns the same `DrillState` object on a re-click, so a structural-equality `$effect` would not fire. We needed a separate change-on-each-click signal.

`MapChoropleth.svelte` gains an optional `recentre_signal?: number` prop. Any change in its value (typically a monotonic counter) triggers `map.fitBounds(data_bbox, …)` with a 400 ms animated tween. Initial mount is NOT a recentre — the load handler already fits bounds, so the first observed value is captured silently. `IndicatorChoropleth.svelte` exposes the active-level pill (the trailing italic label after the breadcrumb crumbs) as a button; clicking it increments `recentre_count` and forwards it to MapChoropleth.

This intentionally does NOT use a Svelte store or event bus — the prop is the single source of truth, the counter is a plain `$state` in the parent, and the child's effect-tracking does the work. No global state, no over-engineered signal abstraction.

## District-level state filter (Phase 4 d4 of TN-GRANULAR-GEO-PLAN)

Pulled forward from Phase 3 c3 deferral. `india-districts.geojson` is national (~766 features). When the drill-down clicks TN at state level, the choropleth would render every Indian district — the citizen sees a country-wide layer instead of TN's 38 districts. Honest behaviour: `loadBoundary("district", undefined, stateLgd)` filters the loaded FeatureCollection to features whose `state_lgd` (numeric upstream property) equals the requested state.

### Why filter in the loader, not in MapChoropleth

The loader's contract is "give me the FeatureCollection for this layer". The maplibre layer-filter alternative (load all 766, paint only 38) wastes ~3 MB of bandwidth per click and leaves the source data semantically lying about scope. Filtering in the loader keeps the source/scope contract honest and lets the bbox-fit logic in MapChoropleth zoom to TN naturally.

### Type coercion note

Upstream `state_lgd` is numeric (`33`); the drill-down state machine carries LGD codes as strings (URL-safe). The filter coerces both sides via `Number(...)` and rejects non-finite values, so a malformed stateLgd silently returns the unfiltered FC (which is the safer degradation — citizens see a country-scale layer rather than an empty map).

### Test

`IndicatorChoropleth.boundaries.test.ts` adds a mixed-state fixture (5 TN + 3 Gujarat) and asserts `loadBoundary("district", undefined, "33")` returns exactly the 5 TN features.

## Polygon-positioned loading overlay (Phase 4 d2 of TN-GRANULAR-GEO-PLAN)

Pulled forward from Phase 3 c3 deferral. Jony's edit #3 was: "the loading spinner should sit over the polygon the user just tapped, not the canvas centre — otherwise on a tall national map the user's eye is at the click but the feedback is 400 px away." The Phase 3 ship punted with a centred fallback because the natural fix is `map.project(LngLat) → {x, y}`, which needs the maplibre handle.

### Decision: declarative props, not handle exposure

Three options were on the table:

- **A. Declarative `pending` + `pending_at` + `pending_label` props on MapChoropleth.** The component owns the projection and the DOM; parents stay maplibre-unaware.
- **B. Expose the map handle via `onMapReady(map)` callback.** Parents `map.project(...)` themselves and render their own overlay.
- **C. Add a parallel `LoadingOverlay` slot facade.**

Fowler and Gregor independently picked **A**. Reasons: (1) **B is a one-way door** — once any consumer holds the handle, every future change to MapChoropleth's internals risks breaking that consumer; (2) **encapsulation** — the maplibre instance stays a private implementation detail (Holy Law #5: no band-aids; punching a handle hole because we need one feature today is a band-aid against future-us); (3) **precedent** — `recentre_signal` (Phase 4 d3, commit `f767831`) already established the declarative-signal-prop pattern, A keeps the API symmetric; (4) **YAGNI on C** — a slot facade only pays off when there are 3+ overlay kinds, which we don't have.

### Mechanism

Three new props on MapChoropleth:

- `pending?: boolean` — render the overlay or not.
- `pending_at?: [number, number]` — lng/lat to anchor it. Re-projected inside `map.on("move", ...)` and `map.on("zoom", ...)` so the spinner stays pinned to the polygon as the camera animates a `fitBounds` mid-fetch.
- `pending_label?: string` — copy under the spinner.

The click handler now forwards `at: [e.lngLat.lng, e.lngLat.lat]` on `onSelect`, so parents that want polygon-anchored overlays don't have to compute centroids. `IndicatorChoropleth` captures `sel.at` into `pending_pos` and forwards it; if it's null (e.g. a programmatic level change), MapChoropleth falls back to the canvas-centre overlay.

### Why the projection isn't unit-tested

`map.project(LngLat)` is maplibre's; the only thing our code does is call it inside `move`/`zoom` listeners and stash the result in `$state`. There is no pure helper to extract here — projection is the contract boundary. Vitest can't mount maplibre, so this is verified via the manual smoke flow (see CLAUDE.md §13) and the integration test for the click-`at` forwarding lives at the `onSelect` shape.

## Mobile pinch-to-drill (Phase 4 of TN-GRANULAR-GEO-PLAN)

Phase 3 §143 reserved pinch for Phase 4 — tap was the only drill affordance on the TN drill-down. Phone users were left with cooperative-zoom that did nothing semantically useful: pinch in, see a bigger version of the same layer.

### Mechanism

`MapChoropleth.svelte` gains an optional `pinch_to_drill?: boolean = false` prop. When on, the component records the zoom level at `touchstart` (along with the touch count) and on `touchend` checks two things: the gesture started with ≥ 2 fingers (a true pinch, not an accidental one-finger drag) AND the zoom delta exceeded `PINCH_DRILL_DELTA = 0.6` (filters jitter). When both hold, it queries rendered features at the gesture's `lngLat` and dispatches `onSelect` with the same shape a click would produce — including `at` so the spinner pins over the gesture point.

`IndicatorChoropleth.svelte` opts in (`pinch_to_drill={drill_enabled}`) so the prop is on for TN drill-down maps and off for `IndiaMap` / state-overview maps that don't drill.

### Why opt-in, not always-on

A non-drill map (the home-page IndiaMap, a state-overview indicator without `highlight_state === "S22"`) has no useful "drill" semantics — pinching there should still just zoom. Coupling pinch to drill globally would surprise users who pinched only to read a label more closely. The prop keeps pinch-to-drill scoped to maps that are actually a drill-down surface.

### Why threshold + finger-count gating

Without the finger-count check, a single-finger tap that incidentally bumps the zoom by `0.7` (rare but possible on jittery touchscreens) would drill. Without the zoom-delta check, every pinch — including pinches the user meant only to zoom by a notch — would drill. Both gates together approximate the user's intent: "I deliberately zoomed in hard."

### Why no unit test

Touch events on a maplibre instance need a real pointer-event runtime; jsdom provides neither, and our vitest stack can't mount maplibre. The drill-dispatch shape (`onSelect({ key, properties, at })`) is the same one the click handler uses and is already covered by `IndicatorChoropleth.boundaries.test.ts`. CLAUDE.md §13 manual smoke (touch DevTools or a real phone) is the verification tier.

## Methodology-break "i" glyph in the legend (Phase 3 §g of TN-GRANULAR-GEO-PLAN)

Indicators carry two governance-honesty fields on their metadata block: `methodology_vintage` (free-form short string naming the methodology revision under which values were computed — e.g. "GSDP base 2011-12") and `series_breaks` (an array of `{at_time, kind, note}` objects marking time-points where the series stops being comparable across the boundary). The full text already renders in the source card at the foot of every `IndicatorChoropleth.svelte` instance, so methodology context is reachable but lives below the fold.

The Phase 3 polish bullet (Jony edit §g) called for **demoting the methodology marker out of polygon tooltips and into the legend**. Two implementation considerations:

- **Why not on the polygon tooltip.** A tooltip the citizen reads dozens of times during a drill should show one number first; methodology is the rare per-indicator caveat, not a per-polygon fact. Decorating every tooltip with the same break-text turns the caveat into noise.
- **Why a legend "i" badge specifically.** The legend is where the citizen looks once per indicator to learn what the colour ramp means; pinning the caveat there reaches the same eye-stop as the unit and direction cue.

Implementation (`IndicatorChoropleth.svelte`):

- A `methodology_summary` derived state joins `methodology_vintage` + every `series_breaks[i]` into newline-delimited text, returning `""` when both are absent.
- The legend header conditionally renders a 14px circular slate-200 chip with text "i" when `methodology_summary` is non-empty. The chip's native `title` attribute carries the summary so a hover shows the full text without a popover library.
- Polygon tooltips remain unchanged — they never carried methodology, so the bullet's "demote-from-polygons" half is preventive, not a code removal.

The bullet's "second line on affected districts in affected years" sub-clause is descoped: `series_breaks` is indicator-level (not per-feature × per-year), so per-polygon × per-year filtering would require data shape we don't emit. The legend glyph carries the same information at the lower visual weight the bullet asked for. If a future schema bump promotes break entries to per-entity, the polygon-tooltip second-line variant becomes implementable; until then the legend glyph is the honest surface.

## Lakshadweep callout inset (Phase 3 §c of TN-GRANULAR-GEO-PLAN)

Lakshadweep is sub-pixel at national zoom on a choropleth — it appears as the smallest dot in the Arabian Sea, and citizens routinely lose track of it. Standard Indian-cartography practice is an inset showing the islands at exaggerated scale, with a labelled border (NOT a connecting line — a line would imply geographic continuity that isn't there; the labelled border carries the meaning).

### Implementation

Pure helper module `frontend/src/lib/lakshadweep.ts` exposes three functions:

- `extractLakshadweepGeometry(fc)` — pulls the Lakshadweep feature out of an india-states-shaped FC by `ST_NM === "Lakshadweep"`.
- `geometryBbox(geometry)` — walks coordinates computing min/max lng/lat. Returns `null` for degenerate input.
- `geometryToSvgPath(geometry, viewbox)` — equirectangular Y-flipped aspect-preserving projection, supports Polygon + MultiPolygon, returns the SVG path `d=` attribute string.

`IndicatorChoropleth.svelte` wires it via a `$effect` that calls `loadBoundary("state")` (cached, free after the parent map's first load), extracts the geometry, projects it into an 80×80 viewbox with padding 6, and stores the path in `lakshadweep_path: $state<string>`. The inset SVG renders bottom-left of the map wrapper, gated on `drill_state.level === "state" && lakshadweep_path` — so it appears at the national/state-overview level and disappears once the citizen drills into a TN polygon (where the islands are no longer relevant context).

### Why SVG inset, not a second MapChoropleth

A second maplibre instance would double the WebGL memory cost (~150–250 KB per Map plus tile caches) for a feature that needs no pan/zoom/click. The geometry comes free from the parent's already-loaded `india-states.geojson`, the projection over 4° of latitude near the equator is fractions of a pixel different between equirectangular and Mercator (so we avoid pulling in a projection library), and an inline `<path>` is ~100 bytes vs a second canvas.

### Why a labelled border, not a connecting line

A connecting line from the inset to the islands' true location would suggest the islands are part of the mainland's coastline — they aren't. The inset is a standalone re-projected fragment; the labelled border ("Lakshadweep / shown 10×") declares the discontinuity honestly. This matches the convention used by the Survey of India's official maps.

### Why the helper is pure

Vitest cannot mount maplibre, but the projection math is the actual logic worth testing — bbox walking, MultiPolygon flattening, Y-flip orientation, aspect-preserving centring. Carving the helper out of the Svelte component lets `lakshadweep.test.ts` (11 cases) assert the path string directly. The component-side wiring is a single `$effect` and a conditional render, both verified manually per CLAUDE.md §13.

## See also

- [Frontend overview](overview.md) — visualization catalog, personas.
- [Psephlab](psephlab.md) — how the map's `ac-fill` swaps data when a scenario is active.
- [Data provenance](../../concepts/data-provenance.md) — applies to boundary PMTiles too.
- CLAUDE.md §3 (datasets contract surface), §12 (sources).
