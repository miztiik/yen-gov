# Map — cartography & geographic overlays

**Last Updated**: 2026-06-11 (revision: PR-2 of elections-off-MapLibre plan - d3-geo named primary renderer; MapLibre deprecated, retained until PR-6)

The map is the primary visual surface for the Citizen and Strategist personas. It composes multiple layers — administrative boundaries, election outcomes, and (future) socio-economic overlays — over a vector basemap. This page covers the library choice, the boundary data pipeline, layer composition, and how the map integrates with [Psephlab](psephlab.md).

## Library: d3-geo SVG (primary); MapLibre GL JS (deprecated, retained until PR-6)

The primary renderer for ALL choropleths - welfare AND election (national state-leading-party, AC drill-down, PC atlas) - is **d3-geo SVG**. This is the ruling baked in [TODO/20260603-data-and-charting-platform-reset-plan.md](../../../TODO/20260603-data-and-charting-platform-reset-plan.md) section 14.5 ("d3-geo SVG for ALL static welfare choropleths; maplibre-gl fenced to the election AC pan/zoom explorer only"). The election-side execution lives in [TODO/20260611-elections-off-maplibre-and-map-ux-plan.md](../../../TODO/20260611-elections-off-maplibre-and-map-ux-plan.md): PR-4 ships the national leading-party d3-geo replacement at `frontend/src/lib/charts/IndiaPartyMap.svelte` (to be created by PR-4); PR-5 ships the per-state AC + highlight d3-geo replacement at `frontend/src/lib/charts/StateAcMapD3.svelte` (to be created by PR-5); PR-6 drops `maplibre-gl` + `pmtiles` from `frontend/package.json` and deletes `frontend/src/lib/maplibre/` wholesale.

**[MapLibre GL JS](https://maplibre.org/) + [PMTiles](https://github.com/protomaps/PMTiles) are DEPRECATED.** They still drive the live election surfaces today via `frontend/src/lib/maplibre/MapChoropleth.svelte` and its `IndiaMap.svelte` / `StateAcMap.svelte` wrappers; PR-1 of the plan above patched their UX inline (`cooperativeGestures: false` + `+ / - / home` button trio) while the d3-geo migration is in flight. No new code should mount the maplibre engine.

### Why d3-geo (one paragraph)

Plain SVG over our existing TopoJSON corpus (`datasets/boundaries/in/{states,districts}/all.topojson`, plus per-state AC GeoJSON), backed by `d3-geo` for projection / path generation and `d3-zoom` for pan / zoom / pinch. No GPU canvas, no WebGL context, no scroll-wheel capture (so no `cooperativeGestures` UX trap - scroll-wheel zooms without Ctrl), trivial to add a `+ / - / home` button trio by driving `svg.transition().call(zoom.scaleBy, ...)` / `svg.transition().call(zoom.transform, d3.zoomIdentity)` on a single shared `d3.zoom()` behaviour, and ~10 KB bundle cost (`d3-geo` + `d3-zoom`) versus ~230 KB gzipped for the maplibre-gl + pmtiles pair. The shape mirrors comparable Indian civic sites: IndiaVotes hand-rolls inline SVG choropleths, and Bharat Pashudhan's `keyStatistics` route also serves an SVG choropleth over a topojson - the d3-geo migration aligns yen-gov with the surface citizens already know.

### Map library - alternatives considered (kept for the record)

- **Leaflet + GeoJSON.** Lighter than MapLibre (~40 KB) but still captures the scroll wheel and needs a raster basemap configured. d3-geo over the topojson we already ship is structurally simpler and matches the d3-geo primitives already used elsewhere in the codebase (`GeoChoropleth.svelte`, `TileCartogram.svelte`).
- **MapLibre GL JS.** Was chosen for v1 because pan/zoom/touch worked out of the box and multi-layer composition was easier than hand-rolling. The migration was triggered by (i) the ~230 KB gzipped bundle cost relative to plain SVG, (ii) the `cooperativeGestures` UX trap (scroll-wheel was Ctrl-gated, which contradicts the citizen expectation set by every comparable Indian civic site), and (iii) the sub-pixel-feature visibility problem with Lakshadweep at national zoom - the citizen-visibility fix lands in PR-4 of [TODO/20260611-elections-off-maplibre-and-map-ux-plan.md](../../../TODO/20260611-elections-off-maplibre-and-map-ux-plan.md) via a minimum-size dot marker at the path centroid, which the maplibre engine offered no clean way to layer per-feature without spinning up a parallel symbol layer with its own paint expressions.
- **Mapbox GL JS.** Proprietary; ruled out by [CLAUDE.md](../../../CLAUDE.md) Holy Law #8 ("Open source first") and operationally ruled out because a public Mapbox token cannot be safely shipped in a static bundle.
- **Deck.gl.** Powerful for large datasets and 3D, but overkill for choropleths and adds React/Lumagl baggage.

## Citizen scroll-zoom UX (post-PR-1, pre-d3-migration)

Until PR-4 + PR-5 of [TODO/20260611-elections-off-maplibre-and-map-ux-plan.md](../../../TODO/20260611-elections-off-maplibre-and-map-ux-plan.md) ship the d3-geo replacement, the live election surfaces still mount MapLibre. PR-1 of that plan flipped `MapChoropleth.svelte`'s `cooperativeGestures: true` to `false` and added an absolutely-positioned `+ / - / home` button trio over the map container. Scroll-wheel zooms without Ctrl; the buttons drive `map.zoomIn()` / `map.zoomOut()` / `map.fitBounds(initialBounds)` respectively. This is the interim citizen-UX fix - it brings MapLibre's runtime behaviour into line with what the d3-geo surfaces will provide structurally.

After PR-4 + PR-5 land, the same UX is built into the SVG renderer via a single shared `d3.zoom()` handler: scroll-wheel and pinch are wired through `zoom.on("zoom", e => g.attr("transform", e.transform))`, and the `+ / - / home` buttons drive `svg.transition().call(zoom.scaleBy, 1.5)` / `svg.transition().call(zoom.scaleBy, 0.667)` / `svg.transition().call(zoom.transform, d3.zoomIdentity)` respectively. No `cooperativeGestures` analogue exists because SVG does not capture the scroll wheel - the citizen does not have to learn a modifier key to zoom.

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

## Home default theme (day-of-year rotation)

The Home surface (`#/`) does NOT default to the election theme. It rotates among a curated pool of national-scope indicators by UTC day-of-year, so the same calendar date yields the same default theme across all visitors. Determinism keeps a fresh Home share-link refresh-stable (the same `#/` URL today + tomorrow produces a predictable sequence) and debuggable (a screenshot dated 2026-06-11 always pins to the same indicator id).

The curated pool is one indicator per topic family (Hans + Max authority per plan-doc PR-4-precursor PR-2 verdict, 2026-06-11):

- `fiscal/outstanding_debt_pct_gsdp` (Money & debt)
- `economy/gdp_inr_crore` (Economy)
- `prices/cpi_inflation_pct` (Prices & inflation)
- `environment/india_ghg_emissions_mtco2e_by_sector` (Environment)
- `agriculture/pashu_aadhaar_count_cattle` (Farming & livestock)

Rotation contract. The picked id is `CURATED_DEFAULT_THEMES[dayOfYear(now) % availablePool.length]` where `availablePool` is the intersection of the curated pool with the live catalogue's national-scope indicators. `dayOfYear` is computed off UTC (not local time) so visitors in different time zones see the same default on the same calendar date. Locked by the contract test at [../../../frontend/src/lib/home-theme.test.ts](../../../frontend/src/lib/home-theme.test.ts).

Fallback to election theme. If the catalogue is null (bootstrap window) OR fewer than 3 curated ids resolve to a national-scope indicator in the live catalogue, `defaultHomeTheme(catalogue)` silently returns `{ kind: "election" }`. Election is the safe default; the fallback is a degraded surface, not a doctrinal preference - if a curated id drops out of the national-scope pool, the next pipeline run should restore it.

Sticky bookmark. `?theme=indicator/<id>` (e.g. `?theme=indicator/fiscal/outstanding_debt_pct_gsdp`) and `?theme=election` URL params override the rotation; a shared URL with one of these params pins the theme for that visitor. The theme picker still lists all 21 themes (Election + 20 national-scope indicators) grouped by topic, so the rotation never hides choice.

Expansion path. Adding a new topic family (e.g. Education, Health) is a one-row edit to `CURATED_DEFAULT_THEMES` in [../../../frontend/src/lib/home-theme.ts](../../../frontend/src/lib/home-theme.ts); keep one-per-topic discipline (the pool surfaces topic coverage; multiple ids from the same family would skew the rotation toward whichever family is over-represented).

## Map / Equal seats mode (election mounts)

Per [ADR-0048](../../reference/decision-index.md), election surfaces carry a segmented toggle labelled **`Map`** / **`Equal seats`** — never the jargon "choropleth" / "cartogram". Default is geographic (`Map`) at every level. The mode persists to the URL as `?view=geo|hex`. The `Equal seats` arm renders a tile cartogram (`frontend/src/lib/charts/TileCartogram.svelte`) where each tile is one constituency, sized equally, fed by a layout dataset under `datasets/grapher/election_tile_layouts.json` ([ADR-0045](../../reference/decision-index.md): render data is frontend-owned). The legend line reads **"Each tile = one seat."**

The cartogram is grain-agnostic: the same primitive renders AC tiles (state surface) and PC tiles (national `/t/elections/:event` atlas), dispatched from the row's `entity_kind`. The toggle and `TileCartogram` are fenced to **election mounts only** in v1 — equal-sizing welfare indicators is misleading and is rejected on doctrinal grounds (Hans + Max veto; see [schema-is-the-design-system.md](../../concepts/schema-is-the-design-system.md)).

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

- `sources.ts` — declarative table of boundary sources (one per India-states + per-state AC layers), each with the upstream URL, the property name to join on (`ST_NM` for datameet states, `AC_NO` for HTL AC files), and license attribution. State-name → ECI-code resolution is **not** hand-coded here any more — it derives from the canonical `datasets/taxonomy/entities.parquet` corpus via the [`view-models/states.ts`](../../../frontend/src/lib/view-models/states.ts) loader (T.0e, May 2026). `sources.ts` re-exports `eciFromStateName(name)` as a thin async shim for callers that want the old single-function API; new code should call `loadStates()` directly to get the full `StateRow` shape (which includes `boundary_join_name` — the DataMeet `ST_NM` join key, which diverges from `display_name` for Delhi / Andaman & Nicobar / Jammu & Kashmir).
- `MapChoropleth.svelte` — generic, library-agnostic to its parents. Takes a `BoundaryEntry`, a `fills` map keyed by the join-property value, optional `opacities` and `tooltips`, and `onSelect`/`onHover` callbacks. Owns map lifecycle and rebuilds `fill-color` / `fill-opacity` paint expressions whenever its props change (Svelte 5 `$effect`).
- `IndiaMap.svelte` and `StateAcMap.svelte` — thin domain wrappers. `IndiaMap` calls `loadStates()` (see above), then fetches `result.summary.json` for every currently-valid state/UT and colors each by winning party (most seats won, votes as tiebreak). This election theme is no longer the Home default - it survives as the explicit `?theme=election` choice and as one of 21 options in the picker; the Home rotation lives in [Home default theme (day-of-year rotation)](#home-default-theme-day-of-year-rotation) above. `StateAcMap` queries `results.sqlite` via the cached `getDb` for `(ac_eci_no → winner_party_eci_code, party_short, margin_pct)` and colors AC fills by winning party with opacity proportional to margin (clamped to 30 % to keep the legend readable; ties drop to the floor so razor-thin wins visually scream "close"). **DEPRECATED ->** `IndiaMap.svelte` is being replaced by `frontend/src/lib/charts/IndiaPartyMap.svelte` (to be created by PR-4 of [TODO/20260611-elections-off-maplibre-and-map-ux-plan.md](../../../TODO/20260611-elections-off-maplibre-and-map-ux-plan.md)); `StateAcMap.svelte` is being replaced by `frontend/src/lib/charts/StateAcMapD3.svelte` (to be created by PR-5 of the same plan). Both files remain on disk during the transition and PR-6 deletes them with the rest of `frontend/src/lib/maplibre/`.

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

## Boundary loader (`frontend/src/lib/boundaries.ts`) — Phase 2 of TN-GRANULAR-GEO-PLAN

A single typed entry point — `loadBoundary(level, parentDistrictLgd?, stateLgd?)` — replaces the per-component `fetch('/some-boundary.json')` pattern. The loader is a pure path resolver (`boundaryBasename`) wrapped around a fetcher; it does not know about colours, click handlers, or choropleth values. It only answers: *given (level, parent district lgd, state lgd), where is the GeoJSON and what property carries the join key?*

### Path table

| Level | URL | Join key |
| --- | --- | --- |
| `country` | `country/all.geojson` | none (silhouette only) |
| `state` | `states/all.geojson` | `ST_NM` (datameet lineage — English name) |
| `district` | `districts/all.geojson` | `dist_lgd` (LGD numeric) |
| `subdistrict` | `subdistricts/state=in_<lc>/all.geojson` (one file per state) | `subdt_lgd` (ramSeraph upstream property) |
| `village` | `villages/state=in_<lc>/district=<dist_lgd>/all.geojson` (one file per district) | `vil_lgd` (ramSeraph upstream property) |

Property names match what ramSeraph's upstream actually emits — `subdt_lgd` / `vil_lgd` (not `subdist_lgd` / `village_lgd`). The plan referenced the longer names; the loader honours the disk shape, since renaming on the upstream feeds would mean shipping a parallel write pipeline (Holy Law #5: structural fixes only — and "use what's actually on disk" is the structural fix).

### Per-district village split — no index manifest (post-T.0d)

The per-district village split is the contract Phase 1b nailed: a single district click pulls ~10–600 KB instead of the full TN villages bundle (~200 MB raw, ~50 MB even at `coord_precision=4`). Under T.0d (2026-05-22) the per-state `<S>-villages-index.json` manifest is retired — Hive partitioning makes the on-disk presence of a shard at `villages/state=tamil-nadu/district=<lgd>/all.geojson` self-describing. The loader fetches the partition path directly and lets a 404 propagate as `null` (graceful degradation — see below). One fewer manifest to keep in sync; one fewer pre-flight round-trip per village query.

### 404-as-null contract

Every `loadBoundary` call that hits a missing file resolves to `null` rather than throwing. Callers (the choropleth, drill-down components) degrade gracefully — show an inline toast, keep the parent layer visible — instead of crashing the page. This mirrors `resolveSource()` in `maplibre/sources.ts`. Caller-input bugs (asking for `subdistrict` without a state, asking for `village` without a parent district) DO throw — those are tests-should-have-caught-this conditions, not graceful-degradation conditions.

### Why `fetch` and not `import.meta.glob`

Vite's `import.meta.glob` would let the bundler see the per-district shards at build time, but `datasets/` is **served at runtime** via the dev-server middleware + Pages, not bundled into the SPA. The glob would not see `datasets/` even if the right primitive existed. Runtime `fetch` is the correct primitive for "load when clicked".

### Test coverage (CLAUDE.md §15)

Four files in `frontend/src/lib/` + one in `frontend/src/contracts/`:

- `boundaries.path.test.ts` (unit, ~18 tests) — pure resolver, no I/O. Asserts Hive-relative paths.
- `boundaries.integration.test.ts` (integration, 9 tests) — `fetch` mocked at the loader's contract boundary (Holy Law #7 carve-out: the loader's contract IS the fetch boundary). Exercises path composition, 404-as-null, network-error-as-null, single-fetch-no-index-probe for villages.
- `boundaries.contract.test.ts` (contract, ~46 tests) — round-trips `boundaryRelPath` against the on-disk TN village shards; samples first/middle/last features for join-key property presence.
- `boundaries-conform.test.ts` in `frontend/src/contracts/` (T.0d) - every `**/*.geojson` under `boundaries/in/` matches a known Hive-shape pattern; legacy sidecar / index manifest survivors are gated to zero; `datasets/boundaries/boundary_layers.parquet` exists; the states layer carries its `State_LGD` join key.

Full boundary gzip-budget checks live at the boundary tooling seam, not in frontend vitest. Run `python tools/boundaries/simplify.py --dry-run --skip-parquet` whenever a PR changes boundary geometry or simplification policy.

### Caching

The browser HTTP cache + Pages' `Cache-Control` handle GeoJSON shard caching. There is no JS-side cache for the ~50 MB of geometry — wrong allocator. A test-only `_resetCachesForTesting()` is exported (now a no-op after T.0d retired the per-state index cache) to keep vitest cases isolated; it is not part of the public API.

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

## All entities render on the map at true geographic location

**As of 2026-05-30 (D.1.A)**, every administrative entity — states, UTs including sub-pixel offshore ones (Lakshadweep, Andaman & Nicobar, Dadra & NH and Daman & Diu) — renders on the choropleth at its true geographic location. There is no per-entity polygon extractor, no callout inset, no chip-strip value surface, no leader line, and no feature flag to restore any of those.

User mandate (verbatim, 2026-05-29): *"REMOVE ANY SIDE FIXES FOR LAKSHADWEEP AS DATA TABLE, IF THE MAPS INCLUDE IT, EVEN IF THE CHOROPLETH IS UNVISIBLE LETS JUST KEEP IT IN THE MAP."*

**Citizen-visibility follow-on (PR-4 of [TODO/20260611-elections-off-maplibre-and-map-ux-plan.md](../../../TODO/20260611-elections-off-maplibre-and-map-ux-plan.md)).** The D.1.A retirement preserved the no-side-fix mandate by rendering the Lakshadweep polygon at its true geographic location, but at national zoom on a 1280 px viewport the polygon bbox collapses to sub-pixel - the citizen can see Lakshadweep is on the map (in the legend / tooltip rollups), but cannot easily click it. PR-4's d3-geo `IndiaPartyMap.svelte` (to be created) layers a minimum-size dot marker (`<circle r=7>`) at the path's `geoCentroid()` projected coordinate for every UT whose path bbox is < ~14 px in either dimension, with the SAME fill + tooltip + click handler as the polygon. This is NOT a callout inset, NOT a chip strip, NOT a leader line - the polygon stays at its true location, the dot is a clickable target overlay so the citizen has a hit area when the polygon is sub-pixel. The mandate ("NO side fixes") is preserved: the dot is a marker on the same map at the same projection, not a separate surface.

If a UT's polygon is sub-pixel at the current zoom level, that is the correct citizen experience — the citizen zooms in to see. Downstream surfaces (data tables, CSV exports, ranking lists, tooltip rollups, winner-name panels) are a UI/UX concern owned by Jony + Citizen per [CLAUDE.md](../../../CLAUDE.md) section 0a and are NOT prescribed here; they naturally render one row per entity because they are built from entity-keyed observation rows, and if a value is absent the cell renders ` - ` (the same null-render any state with a data gap gets).

### Retired in D.1.A (2026-05-30)

The following were deleted in PR #455:

- `frontend/src/lib/lakshadweep.ts` + `frontend/src/lib/lakshadweep.test.ts` (Phase 3 §c polygon extractor + SVG projection helpers).
- `frontend/src/lib/UnmappedRegionChips.svelte` + `frontend/src/lib/unmapped-region-chips.ts` + `frontend/src/lib/unmapped-region-chips.test.ts` (ADR-0029 chip-strip subsystem).
- `frontend/src/lib/format.ts` + `frontend/src/lib/format.test.ts` (`formatPopulationShort`, only consumed by the chip strip).
- `docs/concepts/unmapped-regions.md` (chip-strip concept doc).
- The legacy SVG inset render block + chip-strip render block + `VITE_UNMAPPED_REGION_CHIPS` feature flag + population loader effect, all inside [`IndicatorChoropleth.svelte`](../../../frontend/src/lib/IndicatorChoropleth.svelte).
- The Playwright chip-strip assertion in [`frontend/e2e/golden-path.spec.ts`](../../../frontend/e2e/golden-path.spec.ts).
- The `UT_CODES_WITH_ASSEMBLY` UT-exclusion carve-out in [`backend/yen_gov/coverage.py`](../../../backend/yen_gov/coverage.py) — UTs now appear in coverage reports exactly like states.

[ADR-0029](../../archive/decisions/0029-unmapped-region-chips.md) (archived 2026-06-04 per D-DOC3.7; body preserved verbatim) carries the full retirement entry.

## Rejected alternatives

This section folds in receipts for the moved-to-archive ADRs whose rejected-alternative trace pins to this subsystem, per the ADR retirement contract ([decision-index.md](../../reference/decision-index.md)). Append-only.

### ADR-0029 rejected alternatives

Chip-based unmapped-region label (per archived [ADR-0029](../../archive/decisions/0029-unmapped-region-chips.md)); the surface was retired wholesale 2026-05-30 in PR #455 alongside the legacy polygon-inset surface that the ADR originally proposed to replace. Both side-fix surfaces were eliminated by the user mandate "REMOVE ANY SIDE FIXES FOR LAKSHADWEEP AS DATA TABLE, IF THE MAPS INCLUDE IT, EVEN IF THE CHOROPLETH IS UNVISIBLE LETS JUST KEEP IT IN THE MAP." Generalised rule from that mandate: if the polygon is on the map (even sub-pixel / invisible at default zoom), do not add side-fix surfaces - the map polygon is the only authoritative surface; if a citizen needs to read a sub-pixel UT they zoom in. What stays preserved from the ADR's rationale: no leader lines; no hand-curated UT subset; documentation as audit trail (archived ADR-0029 remains the durable record of how the chip-strip was reasoned about, why it shipped, and why it was retired - for any future agent who proposes a similar side-fix surface).

## See also

- [Frontend overview](overview.md) — visualization catalog, personas.
- [Psephlab](psephlab.md) — how the map's `ac-fill` swaps data when a scenario is active.
- [Data provenance](../../concepts/data-provenance.md) — applies to boundary PMTiles too.
- [Boundary-data philosophy](../../concepts/boundary-data-philosophy.md) -- the "why" behind every boundary-data choice (polygons vs topographic raster, GADM rejection, TopoJSON adoption status, DIGIPIN deferral, HTL kept on purpose).
- CLAUDE.md §3 (datasets contract surface), §12 (sources).
