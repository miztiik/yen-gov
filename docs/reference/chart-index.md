# Chart Index

**Last Updated**: 2026-06-05

> **Two-line doctrine.** Before charting a new indicator, consult BOTH section-15.4 reference galleries (revisual.co + Data-Analytics archetype index) AND pick a renderer from THIS index. Only propose a NEW renderer when (a) neither gallery's relevant archetype maps onto the base set AND (b) >= 2 indicators need it; one indicator's wish for a novel form is met by the nearest base chart, never a new Svelte file.

This is the operational face of [`the schema is the design system`](../concepts/schema-is-the-design-system.md): a citizen picks an indicator, the picker in `ChartShell`'s toolbar offers exactly the renderers `indicator.chart_types[]` declares INTERSECT `feasibleAt(dataShape, grain, timeCardinality, geometryAvailable)`. This document is the human-readable CONTRACT; [`feasibleAt()`](../../frontend/src/lib/grapher/feasibleAt.ts) (landed in plan chunk U4) is the machine implementation. A drift gate at [frontend/src/lib/grapher/chart-index.drift.test.ts](../../frontend/src/lib/grapher/chart-index.drift.test.ts) asserts the three artifacts (the `ChartType` union, the rows in this doc, the matrix `feasibleAt()` implements) stay 1:1.

The base set per plan section 15.1 is **eight renderers** plus one optional `Radar`. Election-only renderers (`PartyBar`, `SeatDonut`, `ParliamentArc`, `TileCartogram` in election mode, etc.) stay fenced to election mounts per [ADR-0048](../architecture/decisions/0048-elections-drill-ia-and-tile-cartogram.md) and are NOT in this base set.

## 1. The base set - one row per renderer (mode)

The `Thumb` column is the Lucide icon id (kebab-case) that the picker will render at 24px from [frontend/public/icons/](../../frontend/public/icons/) (plan section 21.10; the file set lands in chunk U3). All eight glyphs are members of one open icon family (Lucide ISC), recorded in `LICENCES.md`.

The `Machine id` column is the kebab-case literal carried by `ChartType` ([frontend/src/lib/grapher/catalogue.ts](../../frontend/src/lib/grapher/catalogue.ts)) AND by `chart_types[]` in [datasets/grapher/*.json](../../datasets/grapher/). It is the load-bearing handle the drift gate parses: `Machine id <-> ChartType union member <-> feasibleAt() output literal` must stay 1:1.

| # | Renderer (mode) | Machine id | Thumb | long-format CSV shape needed | Use when | Feasibility rule |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `GeoChoropleth{fill}` | `choropleth` | `map` | `(entity, time, value)`, one time slice; `entity` keyed by LGD / ECI / ISO and joinable to the rendered-grain geometry | district / state coverage map; any single-measure-over-geo headline | geometry MUST exist at the rendered grain; if absent, silently removed and default falls to next `chart_types[]` entry (citizen never sees a map that cannot draw) |
| 2 | `GeoChoropleth{symbol}` | `choropleth-symbol` | `map-pinned` | `(entity, time, value)` + `symbol_id` FK to closed icon registry | icon-cartogram: one glyph per region, area-sized by value (sqrt) over faint base outline | symbol MUST resolve in the sanitised registry; missing glyph falls back to a plain sized dot; animated SVG is REJECTED (motion carries no signal beyond size) |
| 3 | `Matrix` (heatmap) | `matrix` | `grid-3x3` | `(entity, time, value)`, all slices | many entities x many time slices on one screen; SGDP-across-states-over-time, climate-stripes shape | shares `ColorScale + Legend` with Choropleth; numeric labels always (never colour alone); ranked fallback always available |
| 4 | `CategoryBar{ranked}` | `ranked` | `bar-chart-3` | `(entity, value)` + optional `facet` | plain ranked comparison; the GUARANTEED non-empty terminal fallback (plan section 23.5) | `ranked` is present in EVERY matrix row below; the drift gate enforces this so a blank card is impossible |
| 5 | `CategoryBar{stacked}` | `stacked` | `chart-column-stacked` | `(entity, facet, value)` | part-to-whole within each entity (e.g. workforce by sector per state); category-on-axis only | DO NOT use for time-on-x stacked area (that is `StackedTrendV2`, fenced to elections); document the boundary or a third stacked surface forks |
| 6 | `CategoryBar{diverging}` | `diverging` | `align-horizontal-distribute-center` | `(entity, facet, value)` with a centre baseline (likert split or sex axis) | N/S/E/W confidence likert; age-sex pyramid; workforce M/F | likert == pyramid == one component; DO NOT build a Pyramid component or a Likert component (plan section 15.1 collapse) |
| 7 | `TimeLine` | `line` | `trending-up` | `(entity, time, value)`, 1-3 series | a small number of named series moving through time | brush + range label live in `ChartShell` header per plan section 25.2; `referenceSeries` slot for national line per plan section 20.11 |
| 8 | `Scatter{size}` | `scatter` | `circle-dot` | two indicators joined per entity `(entity, time, x, y)` + optional `size` | CHIP vs NSDP per-capita; any two-measure correlation; bubble == size mode | NO standalone Bubble renderer; the axes-bearing bubble IS `Scatter{size}` (plan section 15.3) |
| 9 | `DumbbellRange{dot}` | `dumbbell-dot` | `git-commit-horizontal` | `(entity, value_start, value_end)` | start->end pair per entity; absolute level compare at two points | uses the existing `frontend/src/lib/charts/DumbbellRange.svelte`; no new file |
| 10 | `DumbbellRange{arrow}` | `dumbbell-arrow` | `move-right` | `(entity, value_start, value_end)` + indicator `direction` | year-over-year direction (e.g. 2021->2022 cybercrime per lakh); good-up AND bad-up read correctly | arrowhead at end + open-ring at origin; colour by `direction` (`higher_is_better\|lower_is_better\|neutral`); delta label via existing `format_delta` |
| 11 | `Treemap` | `treemap` | `layout-dashboard` | `(category\|entity, value)` + optional one `parent` level | part-to-whole where precise size compare matters (tiles, zero dead space); economic-disparity by city-pop band | sqrt area scale (honest area; 4x value reads as 4x not 16x); labels MUST survive at 360px |
| 12 | `CirclePack{pack,bubble}` | `circle-pack` | `circle` | `(category\|entity, value)` + optional one `parent` level | pure magnitude clusters / shallow hierarchy; city-revenue packed-bubble; "these blobs, sized" not exact ranking | sqrt area scale (same honesty); discriminator vs Treemap: precise-compare -> Treemap, clustered-magnitude vibe -> CirclePack |
| 13 (opt) | `Radar` | (none yet) | `radar` | `(entity, facet=spoke, value)` | CHIPS sub-pillar spider | LOW priority; reads poorly on mid-tier Android; prefer `CategoryBar{stacked}` or `HorizontalGroupedBar` for sub-pillar compare; build only on explicit request |

The optional `Radar` row carries `(none yet)` in the Machine id column: it is deliberately NOT a `ChartType` member until the >= 2-indicator rule (section 5 below) is met for it. The drift gate skips rows whose Machine id starts with `(`.

`OrderedCategoryBar` + `HorizontalGroupedBar` + `composition-bar/` collapse INTO `CategoryBar(mode=...)` in plan chunk F2a (the consolidation PR; structural merge with golden-render gates). Until F2a ships, those three Svelte files remain on disk as the implementation; this doc is the post-collapse contract.

### 1a. Deprecated machine ids (reader keeps them readable per ADR-0047)

The frontend reader (`catalogue.ts` `DEPRECATED_CHART_TYPE_ALIASES`) accepts the legacy literals below until F2a / F2b consolidate the renderer set. New writes (in `datasets/grapher/*.json` and ingest emitters) MUST use one of the section-1 Machine ids above. The drift gate IGNORES this section when computing the 1:1 contract.

| Legacy machine id | Aliases to | Production renderer today |
| --- | --- | --- |
| `stacked-trend` | `line` | `StackedTrendV2.svelte` (stacked area over time; subsumed by `bar-stacked` + `TimeControl` composition after F2a/F2b) |

## 2. Data-shape -> encoding matrix - the picker's pure-function source of truth

`feasibleAt(dataShape, grain, timeCardinality, geometryAvailable) -> ChartType[]` is a pure function with no per-indicator code. The intersect against `indicator.chart_types[]` is what the picker offers; an intersect of exactly one encoding renders NO switcher. The matrix below is the contract the function implements; one row of this table is one branch of `feasibleAt()`. The encodings column uses the section-1 prose form; the drift gate maps each prose entry back to its Machine id via section 1.

| Data shape (after the query) | `time` cardinality | Allowed encodings (then intersect grain) |
| --- | --- | --- |
| one measure over geo, one slice | 1 | `GeoChoropleth{fill}` (iff geometry), `CategoryBar{ranked}` |
| one measure over geo, many slices | > 1 | `Matrix` (entity x year), `TimeLine`, `GeoChoropleth{fill}` + `TimeControl`, `CategoryBar{ranked}` |
| one measure, 1-3 named series over time | > 1 | `TimeLine`, `Matrix`, `CategoryBar{ranked}` |
| two measures joined per entity (+ optional size) | any | `Scatter{size}`, `CategoryBar{ranked}` |
| one measure split by ordered / diverging facet | any | `CategoryBar{diverging}` (+ `TimeControl` if animated), `CategoryBar{ranked}` |
| part-to-whole, precise compare | any | `Treemap`, `CategoryBar{stacked}`, `CategoryBar{ranked}` |
| pure magnitude clusters / shallow hierarchy | any | `CirclePack{bubble}`, `Treemap`, `CategoryBar{ranked}` |
| start -> end pair per entity | 2 | `DumbbellRange{dot}`, `DumbbellRange{arrow}`, `CategoryBar{ranked}` |
| one measure over geo, glyph-honest | 1 | `GeoChoropleth{symbol}` (iff symbol resolves AND geometry), `CategoryBar{ranked}` |

**Guaranteed fallback.** `CategoryBar{ranked}` is present in EVERY row above. Every shape reaching the renderer has at least `(entity, value)`, so the intersect is never empty even when `indicator.chart_types:["choropleth"]` and geometry is absent at the rendered grain - the citizen sees a ranked bar, never a blank card. The drift gate (section 4 below) enforces `ranked` in every row.

**Grain feasibility gate.** `GeoChoropleth{fill}` and `GeoChoropleth{symbol}` are silently removed when geometry is absent at the rendered grain (see plan section 16.2 grain matrix). The default then falls to the next entry in `indicator.chart_types[]`. A district choropleth at sub-district grain without sub-district geometry simply does not appear in the picker.

**Single-encoding intersect.** If the intersect of `chart_types[]` and `feasibleAt(...)` is exactly one encoding, the picker renders NO segmented control - one card, one chart, no controls. The switcher only appears when there are >= 2 feasible offers.

## 3. Forbidden encodings - why this matrix can never emit them

Pie / donut, 3D bars, blind unlabeled bars, and a bar for two continuous measures are not "policy-disallowed"; they are UNREACHABLE because no row of the matrix above ever emits them. Concretely:

- **Pie / donut.** Angle is a perceptual lie for magnitude. Part-to-whole goes to `Treemap` (precise compare) or `CategoryBar{stacked}` (compare within entity). No matrix row emits a `Pie` chart type, and no row ever will.
- **3D bars / pseudo-isometric columns.** Foreshortening lies about height. Quantity stays in 2D; no row emits.
- **Bar for two continuous measures.** Two measures joined per entity go to `Scatter{size}`; using a bar would force one measure to vanish into a label. No row emits a bar for the two-measure shape.
- **Blind unlabeled bar.** Every `CategoryBar` row carries `(entity, value)` with `entity` mandatory and numeric labels present; the renderer rejects rows missing the entity column at the typed-read boundary (plan section 23.2). A truly unlabeled bar cannot construct.
- **Animated SVG cartogram.** Motion carries no signal beyond size; the `GeoChoropleth{symbol}` row uses sqrt-area-scale static glyphs. Animation is rejected on reductionism + mid-tier-Android performance grounds (plan section 15.1).

A future maintainer who wants any of the above must add a row to section 2 (matrix) AND add a member to the `ChartType` union AND change `feasibleAt()` - the drift gate rejects partial changes.

## 4. Drift gate - keep the three artifacts 1:1

The contract surface is THREE artifacts that MUST stay 1:1:

1. The `ChartType` union at [frontend/src/lib/grapher/catalogue.ts](../../frontend/src/lib/grapher/catalogue.ts) (post-U4: 12 members; pre-U4 was the 3-value form `"stacked-trend" | "ranked" | "choropleth"`, retained now as a DEPRECATED alias map in `DEPRECATED_CHART_TYPE_ALIASES`).
2. The renderer rows in section 1 of this doc (the Machine id column is the load-bearing handle).
3. The matrix rows in section 2 of this doc, encoded by [`feasibleAt()`](../../frontend/src/lib/grapher/feasibleAt.ts).

The drift gate at [frontend/src/lib/grapher/chart-index.drift.test.ts](../../frontend/src/lib/grapher/chart-index.drift.test.ts) (sibling to [`catalogue.test.ts`](../../frontend/src/lib/grapher/catalogue.test.ts)) asserts (all LIVE post-U4):

- The doc is present and contains a parseable section 1 table AND a section 2 matrix table.
- Every `ChartType` member has exactly ONE section-1 row (matched on the Machine id column), and vice-versa.
- Every matrix row of section 2 lists `CategoryBar{ranked}` as a feasible encoding (the guaranteed fallback).
- Every encoding listed in any section-2 row maps via section 1 prose -> Machine id to a `ChartType` union member.
- Every `feasibleAt()` branch is non-empty AND contains `ranked`.

A PR that adds a renderer to either side without the other will fail the gate. The optional `Radar` row (section 1 #13) carries the `(none yet)` Machine id and is therefore EXEMPT from the union-membership assertion until the >= 2-indicator rule is met for it.

## 5. How to add a new renderer (process)

1. Confirm the >= 2-indicator rule (plan section 15.4): name the two indicators that need the new renderer, and confirm that neither of the two reference galleries (revisual.co + Data-Analytics) maps the underlying archetype onto an existing base-set member. A single indicator's wish for a novel form is not enough.
2. Add a row to section 1 (renderer name + Machine id + Lucide thumb id + long-format CSV shape + use-when + feasibility rule).
3. Add the encoding to every applicable section-2 matrix row (and ensure `CategoryBar{ranked}` stays present as the guaranteed fallback).
4. Widen the `ChartType` union at [frontend/src/lib/grapher/catalogue.ts](../../frontend/src/lib/grapher/catalogue.ts), accepting any retired literal as a deprecated alias (reader-before-writer per [ADR-0047](../architecture/decisions/0047-schema-version-compatibility-contract.md)).
5. Extend [`feasibleAt()`](../../frontend/src/lib/grapher/feasibleAt.ts) with the new branch.
6. Ship the Svelte component AND the icon SVG at [frontend/public/icons/](../../frontend/public/icons/) (the icon's filename stem MUST match the Thumb id in section 1).
7. The drift gate MUST stay green: 1:1 across the three artifacts.

Removal is the inverse and goes through the same gate.

## See also

- [docs/concepts/schema-is-the-design-system.md](../concepts/schema-is-the-design-system.md) - the doctrine ("no page renders a single indicator with code another indicator could not reuse")
- [docs/concepts/citizen-first.md](../concepts/citizen-first.md) - the reductionism that drives the closed renderer set
- [docs/concepts/owid-alignment.md](../concepts/owid-alignment.md) - one indicator = one long-format series, the shape the matrix consumes
- [docs/architecture/decisions/0045-grapher-catalogue-split.md](../architecture/decisions/0045-grapher-catalogue-split.md) - render hints live in `datasets/grapher/`, not on the canonical catalogues
- [docs/architecture/decisions/0048-elections-drill-ia-and-tile-cartogram.md](../architecture/decisions/0048-elections-drill-ia-and-tile-cartogram.md) - why election-only renderers stay fenced
- [TODO/20260603-data-and-charting-platform-reset-plan.md](../../TODO/20260603-data-and-charting-platform-reset-plan.md) - the binding rip plan; sections 15.1 (renderer set), 15.4 (galleries), 16.2 (grain feasibility), 20.9 (this doc's commission), 21.9 (rational chart-viz / matrix), 23.5 (guaranteed-fallback rule)
- [frontend/src/lib/grapher/catalogue.ts](../../frontend/src/lib/grapher/catalogue.ts) - the `ChartType` union, half of the drift contract
- [frontend/src/lib/grapher/feasibleAt.ts](../../frontend/src/lib/grapher/feasibleAt.ts) - the pure-function source of truth implementing section 2's matrix
- [frontend/src/lib/grapher/chart-index.drift.test.ts](../../frontend/src/lib/grapher/chart-index.drift.test.ts) - the drift gate (all assertions LIVE post-U4)
