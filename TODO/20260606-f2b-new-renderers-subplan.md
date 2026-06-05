# F2b sub-plan - new renderers (GeoChoropleth + Matrix + Treemap + CirclePack + C2/C3/C5 primitives)

**Last Updated**: 2026-06-06
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk F2b
**Status**: IN-FLIGHT (spawning 2026-06-06)
**Authority**: Jony (chart-ergonomics + map-engine doctrine section 14.5) / Hans (data shape contracts inherited from U4) / Fowler (strangler-fig topology shared with F2a) per CLAUDE.md section 0a

---

## Why this exists

Parent chunk F2b reads as one row in the parent Execution Ledger (22.5) - "new renderers (treemap/circlepack/choropleth/matrix)". The actual delivery is **SEVEN distinct renderer surfaces** that each need their own diff + gate + sandbox demo + drift-gate update:

1. **C2 `<ChoroplethLegend>` + C3 `<MapTooltip>` + C5 `<SourceLine>` primitives** (parent section 14.3): the rectangular binned intensity bar with value-tick marker; the region tooltip with parent + formatted value + swatch; the one-line `Source: <owner> (as of <vintage>)` chip. Every map and the matrix render through these three primitives so they ship first.
2. **`GeoChoropleth{fill}` renderer** (parent section 15.1 row 1; chart-index.md section 1 row 1): the d3-geo SVG static-welfare-map primitive that consumes the F4-shipped `datasets/boundaries/in/districts/all.topojson` + the island-render-smoke contract. The single biggest "tortoise -> leopard" performance win per parent section 14.5; the renderer that finally lets a state / district choropleth render without a maplibre GL context.
3. **`Matrix` (heatmap) renderer** (parent section 15.1 row 3): entity x year coloured cells; shares `ColorScale + Legend` with GeoChoropleth per parent section 14.5 doctrine #5 ("Shared ColorScale + Legend primitive serves both `<Choropleth>` and `<Matrix>`"). Replaces the remittance circle-pack with the SGDP-across-states-over-time shape.
4. **`Treemap` renderer** (parent section 15.1 row 7): d3-hierarchy `treemap()`-driven tiled part-to-whole renderer; sqrt area scale; labels survive at 360px. Restored to the base set 2026-06-04 (parent section 20.7); coexists with CirclePack.
5. **`CirclePack` renderer** modes `pack` + `bubble` (parent section 15.1 row 8): d3-hierarchy `pack()`-driven clustered-magnitude renderer; sqrt area scale (same honesty as Treemap); discriminator vs Treemap = clustered-magnitude vibe vs precise-compare.
6. **`GeoChoropleth{symbol}` mode** (parent section 15.1 row 2; chart-index.md section 1 row 2): the icon-cartogram extension to GeoChoropleth - one sanitised SVG glyph per region from the closed `frontend/src/lib/party-symbols/` allowlist registry, area-sized by value (sqrt scale), over a faint base outline. Missing glyph falls back to a plain sized dot. Lower-priority extension to F2b.3, ships after F2b.3 lands.
7. **Closure**: distil the seam shape into [docs/architecture/frontend/design-system.md](../docs/architecture/frontend/design-system.md) (the canonical chart-architecture home; the originally-imagined `chart-architecture.md` was never created - design-system.md absorbed the role per the U-track + F2a distillation precedent), flip parent ledger F2b row to MERGED, archive this sub-plan to `docs/archive/plans/`.

Per CLAUDE.md correction-level discipline (>= 4 files structural -> propose breakdown first; >= 5 = core design) and parent plan section 24.5 sub-plan spawning rule, this is sub-plan territory.

Same pattern as the U1 / U2 / U5 / B1 / B2a / B2b / B2b.4 / B2b.5 / F1 / F2a sub-plans.

This sub-plan is the merge-queue authority for F2b. The parent ledger row stays `DEFERRED-TO-SUBPLAN` until F2b.8 (closure) merges, at which point parent flips to `MERGED` with the closure PR# stamped.

---

## Scope

### In scope (this sub-plan)

1. **C2 `<ChoroplethLegend>.svelte`** (NEW): horizontal binned intensity bar; props `domain`, `bins`, `value_tick?`, `title`, `format_value`, `swatch_for_value`. Pure presentation leaf. Value-tick marker (caret + hairline) renders only when `value_tick != null` and `value_tick` lies inside `domain`. Per parent section 14.3 + Jony's bank-branch-chart observation.
2. **C3 `<MapTooltip>.svelte`** (NEW): region label + parent (state) + formatted value + swatch chip. Absolute-positioned by caller via `x` + `y` props (no positioning logic inside; the renderer owns where to mount). Pure presentation leaf.
3. **C5 `<SourceLine>.svelte`** (NEW): one-line `Source: <owner> (as of <vintage>)` chip. Reads from the 4-field source row shape (`{owner, title, vintage, url}`); citizen-readable; no truncation. The seam every renderer drops into ChartShell's footer / subtitle slot.
4. **`color-scale.ts`** (NEW, shared) + **`color-scale.test.ts`** (NEW): pure helper module exposing `binnedSequential(domain, bins, scheme): (v: number) => string` + `binnedDiverging(domain, bins, scheme): ...`. Consumed by C2 + GeoChoropleth + Matrix per parent section 14.5 doctrine #5 ("Shared ColorScale + Legend primitive"). Built on `d3-scale.scaleSequential` + `d3-scale.scaleDiverging` + the small palette set already used by the existing `IndicatorChoropleth.svelte`.
5. **`GeoChoropleth.svelte`** (NEW): d3-geo + topojson renderer; props `topojson_path`, `feature_key`, `rows`, `selected_time`, `domain?`, `color_scheme`, `tooltip?`, `legend?`. Consumes the F4-shipped `topojson-island-render` smoke as its regression contract (does NOT re-import the smoke; relies on it staying green). Renders ALL geometry; no-data regions get the C4 hatch fill (the diagonal-stripe SVG pattern lifted from existing `OrderedCategoryBar.ocb__hatch`-style precedent). Mounted INSIDE C2 + C3 + C5 primitives.
6. **`Matrix.svelte`** (NEW): entity x year heatmap; props `rows`, `entity_label_fn`, `time_label_fn`, `value_label_fn?`, `color_scheme`. Shares `color-scale.ts` with GeoChoropleth. No SVG-geometry math; just `<rect>` grid + axis labels. Mounted INSIDE C2 (the same legend strip the choropleth uses).
7. **`Treemap.svelte`** (NEW): d3-hierarchy `treemap()`-driven tiled renderer; props `rows`, `parent_label_fn?`, `color_for_node`. Sqrt area scale baked into the d3-hierarchy `sum()` accumulator. Labels render only when the tile is wider than the label's natural width + padding; below that the tile is a swatch only with the label exposed via tooltip.
8. **`CirclePack.svelte`** (NEW): d3-hierarchy `pack()`-driven clustered-magnitude renderer; props `rows`, `mode: "pack" | "bubble"`, `parent_label_fn?`, `color_for_node`. Mode `pack` = `pack().padding(2)`; mode `bubble` = `pack().padding(8)` with no hierarchy (flat children only). Labels inside the circle when circle radius > label-width; below that the label exposes via tooltip.
9. **`GeoChoropleth.symbol-mode`** extension: add `mode: "fill" | "symbol"` discriminator to `GeoChoropleth` + when `mode === "symbol"` derive centroids via `d3-geo.geoCentroid` + render one `<PartySymbolGlyph>`-equivalent per region, area-sized via `d3-scale.scaleSqrt` keyed on `value`. Glyphs come from the closed `frontend/src/lib/party-symbols/` allowlist (reuses the existing sanitiser + svg whitelist). Missing glyph falls back to a plain sized `<circle>`.
10. **Sandbox demos** (`frontend/src/routes/DevChartsSandbox.svelte` EDIT): add ONE fixture section per renderer (5 in total: GeoChoropleth-fill, Matrix, Treemap, CirclePack, GeoChoropleth-symbol). Fixtures are realistic-shaped but synthetic per the existing sandbox doctrine; numbers must not be cited.
11. **Drift gate** ([docs/reference/chart-index.md](../docs/reference/chart-index.md) EDIT): each new renderer was already listed in section 1 (post-U4); F2b's job is to confirm the drift gate stays green - no chart-index.md row edit needed because U4 pre-loaded all 12 ChartType members + their section-1 rows. The renderer files appearing on disk for the first time MAY trigger an outbound-link audit at closure (F2b.8); no in-line gate edit per F2b.2..F2b.7.
12. **Per-renderer vitest units** (NEW, one per renderer): cover the pure helper exports (color-scale bin assignment, treemap/pack layout summary, centroid-by-feature, value-tick visibility predicate). vitest is node-env (CLAUDE.md section 14 + /memories/lessons.md); DOM rendering tests live in section-13 browser smoke.
13. **Per-renderer section-13 in-browser smoke** (CLAUDE.md section 13): navigate to `/dev/charts-sandbox`, attach `page.on('response', ...)`, confirm (a) the new fixture section renders visibly, (b) no new console errors, (c) no failed requests, (d) for GeoChoropleth the topojson loads from `/data/boundaries/in/districts/all.topojson` (or equivalent state shard).
14. `docs/architecture/frontend/design-system.md` (EDIT, F2b.8 only) - add `F2b - new renderers + map primitives` row to the Per-component migration table; add a subsection per renderer with the seam shape + the discriminated-union pattern extension; flip the parent F2b ledger row to MERGED in the same PR; add See-also entries for this archived sub-plan.
15. `TODO/20260603-data-and-charting-platform-reset-plan.md` (EDIT) - flip F2b row from `TODO` to `DEFERRED-TO-SUBPLAN` in the spawn PR; stamp PR#s for F2b.2..F2b.8 as each lands; flip to `MERGED` at F2b.8 closure.
16. `git mv TODO/20260606-f2b-new-renderers-subplan.md docs/archive/plans/20260606-f2b-new-renderers-subplan.md` at F2b.8 closure.

### Out of scope (other parent chunks / sub-plans)

- **F2a CategoryBar consolidation** (parent F2a / `OrderedCategoryBar` + `HorizontalGroupedBar` + `composition-bar/` -> `CategoryBar{ranked,stacked,diverging}`): MERGED ([archive](../docs/archive/plans/20260605-f2a-categorybar-consolidation-subplan.md), PRs #781 + #782 + #784 + #785 + #786 + #787 closure). F2b builds on F2a's discriminated-union pattern for the GeoChoropleth `mode: "fill" | "symbol"` extension.
- **F3 reference line** (parent F3 / TimeSeriesLine reference_series + StatusGlyph + indicator_direction): MERGED #779. Independent of F2b; F2b does not re-touch `TimeSeriesLine.svelte` or `status-glyph/`.
- **F4 d3-geo + topojson + island-render-smoke** (parent F4): MERGED #788. F2b consumes the deps F4 added (`d3-geo` + `@types/d3-geo` + `topojson-client` + `@types/topojson-client` + `@types/topojson-specification`) directly. F2b ALSO consumes the `topojson-island-render.test.ts` smoke as its regression contract; it does NOT re-add or duplicate the smoke.
- **F1 CSV loaders + parity-oracle-rewrite** (parent F1): DEFERRED-TO-SUBPLAN #777 (master worktree work; F1.1 STOP-AND-SURFACE in flight). F2b is data-layer-agnostic per parent section 22.5 user override and ships parallel-OK with the X1a/X1b cutover. F2b renderers consume `(entity, time, value)` shape; they do not know about storage format (parquet vs csv abstraction lives below the renderer seam).
- **X1a reader flip + X1b parquet delete** (parent X1a/X1b): BLOCKED on F1. F2b ships before X cutover; renderers stay byte-identical when X1a/X1b lands.
- **TimeControl primitive** (parent section 15.2): an existing `temporal-viewport/` package; F2b's GeoChoropleth + Matrix may eventually consume `TimeControl` for year-over-year animation, but the v1 of each renderer ships with `selected_time?` as a static prop (no in-renderer playback). Future TimeControl integration is its own follow-on chunk (`E1` parent ledger row carries part of this scope).
- **Election-experience refinements** (parent section 25 / chunks `E1` ChartShell time_label slot, `E2` PartyPill, `E3` state silhouette on StateAcMap + TileCartogram, `E4` two highlight modes, `E5` ParliamentArc seats invariant): all parent-ledger rows downstream of F2b. F2b.8 closure unblocks E3.
- **The "(i) glyph on each ChartShell title linking to `/docs/indicator/<id>`"** (parent section 21.8 / U5 closure): the (i) link is the JOB OF every renderer that has an indicator id, lifted in renderer-by-renderer migration. F2b's new renderers MAY add the (i) link directly when first wired into a citizen route, but the v1 sandbox demos render WITHOUT the (i) glyph (the sandbox has no indicator id to link to).
- **CategoryBar mode="diverging" + TimeControl = animated pyramid** (parent section 15.1 collapse): not new code; the `CategoryBar mode="diverging"` shipped in F2a + the existing `temporal-viewport/` package + a future TimeControl integration combine to deliver the animated pyramid without a new renderer. F2b does not own this composition.
- **Per-indicator chart Svelte files** (parent section 15.3 / "Do NOT build"): F2b explicitly does NOT mint per-indicator art. The icon-cartogram (F2b.7) is the one fenced place per-indicator illustration could re-enter; the fence is the closed sanitised glyph registry + dot fallback. No inline drawings.
- **The DEPRECATED `chart_type` singular field on grapher/indicator_render.json** (post-U4 reader-before-writer): F2b does NOT delete the deprecated singular field. That deletion rides in a later cleanup chunk after the writer-side migration completes per [ADR-0047](../docs/architecture/data/schema-evolution.md#adr-0047-schema-version-compatibility-contract).

---

## Sub-row Execution Ledger

| Sub-row | Blocks on | Parallel-OK with | Gate | PR# | Status |
| --- | --- | --- | --- | --- | --- |
| F2b.1 spawn sub-plan (this file + parent ledger flip to DEFERRED-TO-SUBPLAN) | - | - | docs-review | #789 | IN-FLIGHT |
| F2b.2 C2 + C3 + C5 primitives + color-scale.ts shared helper + tests | F2b.1 | F2b.3..F2b.6 (file-disjoint) | vitest(color-scale, value-tick predicate) + svelte-check | _pending_ | IN-FLIGHT |
| F2b.3 GeoChoropleth{fill} renderer + sandbox demo + section-13 smoke | F2b.2 | F2b.4, F2b.5, F2b.6 | vitest(domain calc, feature-key join) + section-13 in-browser smoke (sandbox) + topojson load assertion | - | TODO |
| F2b.4 Matrix renderer + sandbox demo + section-13 smoke | F2b.2 | F2b.3, F2b.5, F2b.6 | vitest(cell layout, color-scale share) + section-13 in-browser smoke (sandbox) | - | TODO |
| F2b.5 Treemap renderer + sandbox demo + section-13 smoke | F2b.2 | F2b.3, F2b.4, F2b.6 | vitest(treemap layout summary, label visibility predicate) + section-13 in-browser smoke (sandbox) | - | TODO |
| F2b.6 CirclePack renderer (modes pack + bubble) + sandbox demo + section-13 smoke | F2b.2 | F2b.3, F2b.4, F2b.5 | vitest(pack layout summary, mode discriminator) + section-13 in-browser smoke (sandbox) | - | TODO |
| F2b.7 GeoChoropleth{symbol} mode extension + sandbox demo + section-13 smoke | F2b.3 | F2b.4, F2b.5, F2b.6 (file-disjoint - extends F2b.3 only) | vitest(centroid-by-feature, sqrt-area scale, glyph fallback) + section-13 in-browser smoke (sandbox) | - | TODO |
| F2b.8 closure (distil into design-system.md F2b row; flip parent F2b ledger; archive this sub-plan) | F2b.2, F2b.3, F2b.4, F2b.5, F2b.6, F2b.7 | - | docs-review | - | TODO |

Parallel-safe groups: F2b.2 primitives ship FIRST (every renderer depends on them). After F2b.2 lands, F2b.3 + F2b.4 + F2b.5 + F2b.6 are file-disjoint (each ships its own renderer Svelte file + its own vitest + edits its own sandbox section); they can ship in parallel BUT for orchestrator simplicity this sub-plan defaults to SERIAL (one per PR; the sandbox edits collide trivially if parallel which is the only real reason for serial). F2b.7 ships AFTER F2b.3 (extends the GeoChoropleth file). F2b.8 is closure.

If F2b.3 (GeoChoropleth{fill} - the heaviest renderer) grows beyond one PR (legend + tooltip + value-tick wiring + topojson loader + color scale + 9-state sandbox demo + section-13 smoke), spawn a sub-sub-plan `TODO/<YYYYMMDD>-f2b-3-geochoropleth-fill-subsubplan.md` with per-deliverable rows per parent section 24.5.

---

## Per-sub-row notes

### F2b.2 C2 + C3 + C5 primitives + color-scale.ts shared helper + tests

**Files (~6 NEW, ~400 LOC including tests):**

- `frontend/src/lib/charts/color-scale.ts` (NEW, ~80 LOC) - pure helper module exposing `binnedSequential({domain, bins, scheme})` + `binnedDiverging({domain, mid_value, bins, scheme})` + `colorForValue(value, scale): string`. Module-scope exports; consumed by C2 (legend), GeoChoropleth (fill resolution), Matrix (cell fill). The `scheme` arg is the same closed-enum vocabulary the existing `IndicatorChoropleth.svelte` consumes via `hueForDirection()` + `sequentialSwatch()` (do not regress that existing surface; the new helper is a typed wrapper around the same palette set).
- `frontend/src/lib/charts/color-scale.test.ts` (NEW, ~90 LOC, ~12 cases) - covers (a) `binnedSequential` partition correctness (5-bin domain `[0, 100]` -> bin edges `[0, 20, 40, 60, 80, 100]`), (b) value-at-bin-boundary attribution (lower-inclusive), (c) diverging mid-value handling, (d) `colorForValue` for out-of-domain values (clamps to nearest endpoint).
- `frontend/src/lib/charts/ChoroplethLegend.svelte` (NEW, ~120 LOC) - C2. Horizontal binned intensity bar; props `{domain, bins, value_tick?, title, format_value, swatch_for_value}`. Value-tick rendering predicate is the testable surface: `shouldRenderValueTick(domain, value_tick)` -> `boolean` (false when `value_tick == null` OR `value_tick < domain[0]` OR `value_tick > domain[1]`). The caret + hairline glyph is SVG; positioning is `cx = (value_tick - domain[0]) / (domain[1] - domain[0]) * width`. No DOM tests; the predicate is unit-covered.
- `frontend/src/lib/charts/MapTooltip.svelte` (NEW, ~80 LOC) - C3. Absolute-positioned tooltip with region label + parent + formatted value + swatch chip. Props `{x, y, region_label, parent_label?, value, format_value, swatch_color}`. Renders only when value is supplied; no positioning logic inside (caller decides where).
- `frontend/src/lib/charts/SourceLine.svelte` (NEW, ~40 LOC) - C5. One-line `Source: <owner> (as of <vintage>)` chip. Props `{owner, vintage, url?}`. When `url` supplied, renders the line as a link. Reads from the existing 4-field source row shape (`{owner, title, vintage, url}` per parent section 7 / U5 IndicatorDoc precedent).
- `frontend/src/lib/charts/__tests__/value-tick.test.ts` (NEW, ~50 LOC, ~6 cases) - covers the `shouldRenderValueTick` predicate exported from `ChoroplethLegend.svelte`'s `<script module>` block (Svelte 5 pattern from F2a + IndicatorJump + GeoBreadcrumb).

**Gate:** vitest (color-scale + value-tick) + svelte-check 0 errors. No section-13 smoke (no renderer mounted yet).

**Doctrine:** the three primitives + color-scale ship as one PR because they form a tightly-coupled contract surface; splitting them would either ship a primitive with no consumer or force two PRs that each need svelte-check + vitest stable. The d3 sub-package deps consumed (`d3-scale`, `d3-scale-chromatic`, `d3-format`) are added to `frontend/package.json` dependencies in this PR (same shape as F4's d3-geo dep lift per [/memories/session/u7-f4-shipped.md](../memories/session/u7-f4-shipped.md)).

### F2b.3 GeoChoropleth{fill} renderer + sandbox demo + section-13 smoke

**Files (~4 NEW + 1 EDIT, ~450 LOC including tests):**

- `frontend/src/lib/charts/GeoChoropleth.svelte` (NEW, ~280 LOC) - the d3-geo SVG renderer. Props `{topojson_path, feature_key, rows, selected_time?, domain?, color_scheme, mode?, height?}`. Loads the topojson via `fetch(DATA_BASE + topojson_path)` (no DuckDB / no maplibre); decodes via `feature(topology, topology.objects[objectKey])`; fits projection via `geoMercator().fitSize([width, height], collection)` per the F4 smoke contract; renders per-feature `<path>` filled via `colorForValue(rows.get(feature.properties[feature_key]), color_scale)`. No-data regions fall through to the C4 diagonal-stripe SVG hatch (lifted from the existing pattern in `OrderedCategoryBar.ocb__hatch` / `HorizontalGroupedBar.hgb__cell-hatch`; the pattern is now owned by CategoryBar's preserved class names post-F2a). C2 mounts above the body; C3 mounts via `$state` on hover (the testable surface is the centroid-by-feature helper); C5 mounts in ChartShell footer (when `wrap_in_shell={true}`).
- `frontend/src/lib/charts/GeoChoropleth.test.ts` (NEW, ~120 LOC, ~10 cases) - covers (a) `domain([rows])` derivation when no `domain` prop supplied (min/max of values), (b) feature-key join correctness (rows-by-feature-key map shape), (c) the `value-tick` predicate wiring (legend renders with `value_tick` set to the hovered region's value), (d) no-data fall-through (rows with `value == null` route to hatch).
- `frontend/src/routes/DevChartsSandbox.svelte` (EDIT, +60 LOC) - add a NEW section `### GeoChoropleth{fill} - district-level fixture` mounting `<GeoChoropleth topojson_path="/boundaries/in/states/all.topojson" feature_key="st_lgd" rows={state_rows} ... />` with a fixture of ~10 state values keyed on `st_lgd`. The sandbox section is hidden behind a `<details>` element by default (consistent with the existing sandbox section convention).
- **No new chart-index.md row.** U4 pre-loaded the `choropleth` Machine id row in section 1 + the matrix row in section 2. F2b.3 makes the row LIVE (the renderer now exists), but the drift gate parses section 1 / section 2 prose against the `ChartType` union; the union already has `"choropleth"` since U4. F2b.8 closure may add a hyperlink from the chart-index.md row to the new Svelte file as a See-also; the gate does not require it.

**Gate:** vitest (GeoChoropleth + color-scale share) + svelte-check + section-13 in-browser smoke (`/dev/charts-sandbox`). The smoke MUST attach `page.on('response', ...)` before navigation and confirm the topojson loads from `/data/boundaries/in/states/all.topojson` (or districts shard); the topojson file is the F4-shipped corpus and the smoke is the regression contract.

**Doctrine:** GeoChoropleth is the heaviest single renderer in F2b. It composes C2 + C3 + C5 + the topojson loader + the color scale + the optional `mode` discriminator for F2b.7. Per parent section 14.5: d3-geo SVG only (no maplibre GL context); shared `ColorScale + Legend` primitive serves both this renderer and Matrix.

### F2b.4 Matrix renderer + sandbox demo + section-13 smoke

**Files (~3 NEW + 1 EDIT, ~280 LOC including tests):**

- `frontend/src/lib/charts/Matrix.svelte` (NEW, ~180 LOC) - entity x year heatmap. Props `{rows, entity_label_fn, time_label_fn, value_label_fn?, color_scheme, height?, cell_min_width?}`. Internal helpers: `rowsByEntityByTime(rows)` -> `Map<entity_id, Map<time, value>>` (pure, testable); `axisGrid({entities, times, cell_w, cell_h, label_w})` -> SVG geometry. Color scale shared with GeoChoropleth via `color-scale.ts`. Column highlight on hover (the C2 legend value-tick) follows the same predicate as GeoChoropleth.
- `frontend/src/lib/charts/Matrix.test.ts` (NEW, ~80 LOC, ~8 cases) - covers (a) `rowsByEntityByTime` Map shape correctness, (b) sort stability (entities by alphabetical default, times by chronological), (c) cell-fill resolution via shared `color-scale.ts`, (d) hover predicate (hovering a cell highlights the value-tick on the legend).
- `frontend/src/routes/DevChartsSandbox.svelte` (EDIT, +50 LOC) - add `### Matrix (heatmap) - SGDP across states x years` section with ~5 states x ~10 years of fixture values.
- **No new chart-index.md row.** Same as F2b.3: U4 pre-loaded `matrix` Machine id.

**Gate:** vitest (Matrix + color-scale share) + svelte-check + section-13 in-browser smoke (`/dev/charts-sandbox`).

**Doctrine:** Matrix shares ColorScale + Legend with GeoChoropleth per parent section 14.5 doctrine #5. No new SVG-geometry math; just `<rect>` grid + axis labels. The `cell_min_width` prop is the responsive control: at 360px the matrix wraps to fewer cells visible (the dimension picker is a future TimeControl integration).

### F2b.5 Treemap renderer + sandbox demo + section-13 smoke

**Files (~3 NEW + 1 EDIT, ~260 LOC including tests):**

- `frontend/src/lib/charts/Treemap.svelte` (NEW, ~170 LOC) - d3-hierarchy `treemap()`-driven tiled renderer. Props `{rows, parent_label_fn?, color_for_node, height?, label_min_tile_width_px?}`. Internal helpers: `treemapLayout(rows, {width, height})` -> array of `{id, label, value, x0, x1, y0, y1, color}` (pure, testable, uses d3-hierarchy `hierarchy().sum().treemap().size()`). Labels render only when `(x1 - x0) >= label_min_tile_width_px` (default 40px); below that the tile is a swatch only with the label exposed via tooltip.
- `frontend/src/lib/charts/Treemap.test.ts` (NEW, ~70 LOC, ~7 cases) - covers (a) `treemapLayout` returns one tile per row, (b) tile areas are sqrt-proportional (4x value tile reads as 4x area, not 16x), (c) label visibility predicate at boundaries (39px = swatch-only, 40px = label-visible), (d) flat-list input (no `parent_label_fn`) renders as a single-level treemap.
- `frontend/src/routes/DevChartsSandbox.svelte` (EDIT, +50 LOC) - add `### Treemap - revenue per capita by city-pop band` section with ~12 city-pop-band buckets.
- **No new chart-index.md row.** Same as F2b.3 / F2b.4: U4 pre-loaded `treemap` Machine id.

**Gate:** vitest (Treemap layout summary + label visibility predicate) + svelte-check + section-13 in-browser smoke (`/dev/charts-sandbox`).

**Doctrine:** sqrt area scale is HONESTY per parent section 15.1; this is the discriminator vs raw area which is a perceptual lie for magnitude. `d3-hierarchy.hierarchy(rows).sum(d => d.value)` is the correct accumulator (d3 internally applies the sqrt at layout time when the tile shape is treemap).

### F2b.6 CirclePack renderer (modes pack + bubble) + sandbox demo + section-13 smoke

**Files (~3 NEW + 1 EDIT, ~280 LOC including tests):**

- `frontend/src/lib/charts/CirclePack.svelte` (NEW, ~190 LOC) - d3-hierarchy `pack()`-driven clustered-magnitude renderer. Props `{rows, mode: "pack" | "bubble", parent_label_fn?, color_for_node, height?, label_min_circle_radius_px?}`. Mode `pack` = `pack().padding(2)`; mode `bubble` = `pack().padding(8)` with no hierarchy (flat children only). Internal helpers: `packLayout(rows, {width, height, mode})` -> array of `{id, label, value, x, y, r, color}` (pure, testable). Labels render only when `r >= label_min_circle_radius_px` (default 24px); below that the circle is a swatch only with the label via tooltip.
- `frontend/src/lib/charts/CirclePack.test.ts` (NEW, ~80 LOC, ~9 cases) - covers (a) `packLayout` returns one circle per row, (b) mode discriminator (pack padding=2, bubble padding=8), (c) bubble-mode collapses hierarchy (parent_label_fn ignored), (d) circle areas are sqrt-proportional (matches Treemap honesty), (e) label visibility predicate at boundaries.
- `frontend/src/routes/DevChartsSandbox.svelte` (EDIT, +50 LOC) - add `### CirclePack{pack,bubble} - city-revenue magnitude` section with ~20 city revenues + a `<SegmentedControl>` (from U4) toggling mode between pack and bubble.
- **No new chart-index.md row.** Same as F2b.3 / F2b.4 / F2b.5: U4 pre-loaded `circle-pack` Machine id.

**Gate:** vitest (CirclePack layout summary + mode discriminator) + svelte-check + section-13 in-browser smoke (`/dev/charts-sandbox`).

**Doctrine:** sqrt area scale same as Treemap (honesty). Discriminator vs Treemap per parent section 15.1: precise-compare -> Treemap, clustered-magnitude vibe -> CirclePack. Per parent section 20.7 user override 2026-06-04 (CirclePack restored to base set).

### F2b.7 GeoChoropleth{symbol} mode extension + sandbox demo + section-13 smoke

**Files (~1 EDIT + 1 NEW + 1 EDIT, ~180 LOC including tests):**

- `frontend/src/lib/charts/GeoChoropleth.svelte` (EDIT, +90 LOC) - add `mode: "fill" | "symbol"` discriminator. When `mode === "symbol"`: derive centroids via `d3-geo.geoCentroid(feature)`; size each glyph via `d3-scale.scaleSqrt().domain(domain).range([min_glyph_px, max_glyph_px])` keyed on `value`; render glyph as `<PartySymbolGlyph>`-equivalent reading from the closed `frontend/src/lib/party-symbols/` allowlist registry. Missing glyph falls back to a plain sized `<circle>` (per parent section 15.1 "missing glyph falls back to a plain sized dot").
- `frontend/src/lib/charts/GeoChoropleth.symbol.test.ts` (NEW, ~60 LOC, ~6 cases) - covers (a) centroid-by-feature helper returns `[lng, lat]` pair, (b) sqrt-area-scale glyph size resolution (4x value -> 2x glyph size, not 4x; HONEST area), (c) glyph fallback when `symbol_id` not in registry, (d) faint base outline renders behind glyphs (per parent section 15.1).
- `frontend/src/routes/DevChartsSandbox.svelte` (EDIT, +40 LOC) - extend the F2b.3 GeoChoropleth-fill section with a sibling `### GeoChoropleth{symbol} - icon-cartogram` section; reuse the same state fixture; pick a glyph from the closed registry (or fall back to dot if none available for the fixture's `symbol_id`).
- **No new chart-index.md row.** Same as F2b.3..F2b.6: U4 pre-loaded `choropleth-symbol` Machine id.

**Gate:** vitest (centroid-by-feature + sqrt-area scale + glyph fallback) + svelte-check + section-13 in-browser smoke (`/dev/charts-sandbox`).

**Doctrine:** REJECTED per parent section 15.1: animated SVG (smoke/gas puffs scaled by emission). Glyphs are static, sized by value via sqrt area scale; motion carries no signal beyond size. The factory/animal glyph sized by value is the whole story.

### F2b.8 closure

- Distil the F2b renderer set + the C2/C3/C5 primitive shape into [docs/architecture/frontend/design-system.md](../docs/architecture/frontend/design-system.md) section "F2b - new renderers + map primitives". Add See-also entries for this archived sub-plan + the F4 island-render-smoke contract that GeoChoropleth consumes.
- Flip the parent F2b ledger row to MERGED in this same PR; stamp the closure PR# + the per-sub-row PR#s.
- Archive this sub-plan to `docs/archive/plans/20260606-f2b-new-renderers-subplan.md` with a "Plan complete" block per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).
- Add to chart-index.md section 1 See-also: a hyperlink per renderer row to the new Svelte file (additive; the drift gate does not require it but downstream agents benefit from the direct link).
- Confirm: parent ledger downstream rows now unblock - `E3 state silhouette on StateAcMap+TileCartogram` (parent ledger row, blocks on F2b) is the immediate next ready chunk.

---

## Contract invariants (inherited from parent 14.3 / 14.5 / 15.1 / 21.7 / 21.9 / 22.4)

1. **Data shape**: every renderer consumes `(entity, time, value)` rows only. No knowledge of storage format (parquet vs csv abstraction lives in the loader seam below the renderer). Per parent section 22.4 invariant #4 + the F-track session brief.
2. **ChartType union**: each renderer's Machine id matches the `ChartType` union member 1:1 (post-U4: `choropleth`, `choropleth-symbol`, `matrix`, `treemap`, `circle-pack` are all already members). The chart-drift test ([frontend/src/lib/grapher/chart-index.drift.test.ts](../frontend/src/lib/grapher/chart-index.drift.test.ts)) MUST stay green at each F2b PR.
3. **One card per measure** (CLAUDE.md anti-pattern): new renderers slot into the existing `IndicatorCard` shell or are mounted directly via `topic-dispatch.ts`. F2b does NOT mint new wrapper components or split a measure into per-facet cards.
4. **Honesty**: sqrt area scale on Treemap + CirclePack + GeoChoropleth{symbol} (per parent section 15.1); diagonal-stripe hatch for no-data regions (per parent section 14.3 C4); numeric labels always (never color alone) per parent section 14.5 doctrine #5.
5. **Static-first**: all renderers ship in the static bundle (Holy Law #1). No new external dependency beyond the d3 sub-packages (d3-hierarchy, d3-scale, d3-scale-chromatic, d3-format) added in F2b.2; `d3-geo` + `topojson-client` already shipped by F4.
6. **No per-indicator code**: F2b renderers are schema-driven (per `chart_types[]` on `datasets/grapher/indicator_render.json` from U4 + `value_kind`/`unit`/`entity_kind` from the indicator catalogue). The icon-cartogram (F2b.7) glyph registry is the one fenced place per-indicator illustration could re-enter; the fence is the closed sanitised allowlist + dot fallback per parent section 15.1.
7. **Strangler-fig topology**: each PR is independently revertable. F2b does NOT delete the existing `IndicatorChoropleth.svelte` (maplibre-based) or `MapChoropleth.svelte` until a separate post-F2b chunk migrates the state / district choropleth routes to GeoChoropleth. The maplibre path stays live until the d3-geo path is proven across the production routes.
8. **Section 13 smoke is the safety net**: every renderer PR runs `/dev/charts-sandbox` smoke per CLAUDE.md section 13; for F2b.3 (the GeoChoropleth heaviest) the smoke also asserts the topojson loads from the F4-shipped corpus path.

---

## Why this shape (vs renderer-by-renderer ad-hoc shipping)

- **C2/C3/C5 ship first** because every renderer depends on them. Shipping the primitives in a separate PR (F2b.2) means the four renderer PRs (F2b.3..F2b.6) are file-disjoint and each one's review is bounded to the renderer file + its test + a sandbox edit.
- **GeoChoropleth ships AHEAD of Matrix / Treemap / CirclePack** because (a) it consumes the F4-shipped topojson + smoke contract directly (the most-recent merged work; freshest in reviewer context), (b) it is the highest-value renderer per parent section 14.5 ("the single biggest tortoise -> leopard performance win"), (c) it stands up the ColorScale + Legend pattern that Matrix then reuses.
- **GeoChoropleth{symbol} ships LAST among renderers** because it extends F2b.3's discriminated-union shape; it is a thin extension PR, not a standalone renderer. User brief explicitly relaxed F2b.7 to "lower priority", which means it MAY be deferred to a follow-on session if context tightens; F2b.8 closure can ship with F2b.7 in TODO if the user re-prioritises.
- **F2b.8 closure** is its own PR (not bundled into F2b.7) per the U-track + F2a precedent: closure-only docs PRs are reviewable in one breath, parent ledger flips reach main fast, and the sub-plan archive happens atomically with the row flip.
- **Two-PR fast-paths exist** (e.g. F2b.2 + F2b.3 could ship in one PR if the GeoChoropleth body is small enough) but the default is one row per PR for reviewability. The orchestrator escalates to a fast-path only when the diff stays under ~400 LOC (per [/memories/session/u7-f4-shipped.md](../memories/session/u7-f4-shipped.md) F4 single-PR lesson).

---

## Session-end / context-tightening contract

If a session terminates before F2b.8 closes, the next session reads the parent ledger F2b row (`DEFERRED-TO-SUBPLAN <spawn-PR#>`) + this sub-plan's Sub-row Execution Ledger to know which sub-row is next. The sub-rows stamp `PR#` as each lands, so the merge-queue is recoverable from a fresh `git pull` + `Get-Content TODO/20260606-f2b-new-renderers-subplan.md`.

## See also

- [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) sections 14.3, 14.5, 15.1, 22.4, 22.6 - the design-spec source for F2b.
- [docs/archive/plans/20260605-f2a-categorybar-consolidation-subplan.md](../docs/archive/plans/20260605-f2a-categorybar-consolidation-subplan.md) - the F2a sub-plan F2b builds on (discriminated-union pattern + sandbox seam).
- [docs/architecture/frontend/design-system.md](../docs/architecture/frontend/design-system.md) - the canonical chart-architecture home; F2b distillation lands here at F2b.8 closure.
- [docs/reference/chart-index.md](../docs/reference/chart-index.md) - the 12-member ChartType contract + drift gate. U4 pre-loaded all F2b Machine ids; F2b makes the rows LIVE.
- [frontend/src/contracts/topojson-island-render.test.ts](../frontend/src/contracts/topojson-island-render.test.ts) - the F4 regression contract GeoChoropleth consumes.
- [frontend/src/lib/charts/CategoryBar.svelte](../frontend/src/lib/charts/CategoryBar.svelte) - the F2a-shipped discriminated-union pattern F2b extends (`mode: "fill" | "symbol"` on GeoChoropleth; `mode: "pack" | "bubble"` on CirclePack).
- [CLAUDE.md](../CLAUDE.md) section 13 (UI verification) + Holy Law #1 (static-first) + Holy Law #6 (no hardcoding) + Holy Law #10 (tests ship with feature).
