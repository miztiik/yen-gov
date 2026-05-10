# Map — cartography & geographic overlays

**Last Updated**: 2026-05-10 (revision: post-Phase-1d sync; UX audit P1)

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

## See also

- [Frontend overview](overview.md) — visualization catalog, personas.
- [Psephlab](psephlab.md) — how the map's `ac-fill` swaps data when a scenario is active.
- [Data provenance](../../concepts/data-provenance.md) — applies to boundary PMTiles too.
- CLAUDE.md §3 (datasets contract surface), §12 (sources).
