# Generic renderers (Phase 3 + 3.5)

**Last Updated**: 2026-05-25

Five generic chart renderers plus two adopter-polish PRs that consume the [view-model builders](sort-policy-and-builders.md). Separation of concerns: builder locks sort / project / dimension choices; renderer draws the result; no domain logic in Svelte.

## What it is

| Renderer | Builder | Purpose |
| --- | --- | --- |
| [`HorizontalGroupedBar.svelte`](../../../../frontend/src/lib/charts/HorizontalGroupedBar.svelte) | `buildHorizontalGroupedBarViewModel` | One row per entity × N grouped bars (party seats, fuel mix, age cohorts). Module-exported `legendColour()` is the colour fallback. |
| [`OrderedCategoryBar.svelte`](../../../../frontend/src/lib/charts/OrderedCategoryBar.svelte) | `buildOrderedCategoryBarViewModel` | Categories with a natural order (deciles, age bands, education levels). |
| [`DumbbellRange.svelte`](../../../../frontend/src/lib/charts/DumbbellRange.svelte) | `buildDumbbellRangeViewModel` | Two-endpoint change (2011 → 2021, before/after policy window). |
| [`TimeSeriesLine.svelte`](../../../../frontend/src/lib/charts/TimeSeriesLine.svelte) | `buildTimeSeriesLineViewModel` | Multi-series lines with break / dashed-bridge behaviour. |
| [`FacetPanelGrid.svelte`](../../../../frontend/src/lib/charts/FacetPanelGrid.svelte) | `buildFacetPanelGridViewModel` | Small-multiples panel grid with explicit `shared_scale` flag. |

Adopter polish:

- [`IndicatorRanked.svelte`](../../../../frontend/src/lib/IndicatorRanked.svelte) — Phase 3: peer-median tick + direction-aware verdict (closed enum `verdict`: `ahead | behind | equal | differs`).
- [`IndicatorSmallMultiples.svelte`](../../../../frontend/src/lib/IndicatorSmallMultiples.svelte) — Phase 4: signed y-domain + signed projection (fixes `Math.abs` sign-collapse). See [`small-multiples.md`](small-multiples.md).

## Doctrinal rules

- **`OrderedCategoryBar` forbids value sort.** Policy is `axis_order` OR `alphabetical` only; the builder enforces it at the type level (narrower `OrderedCategoryBarPolicy` union). A downstream PR that tries to value-sort fails compilation.
- **`FacetPanelGrid` honours `shared_scale`.** When `true`, all panels project against `global_max_abs_value`; when `false`, each panel projects against its own `max_abs_value`. The per-panel `is_max_in_panel` flag is relative to the panel's own scale, regardless.
- **Missing cells show hatch + "no data".** No renderer leaves a cell blank. True zero ≠ missing; missing ≠ true zero. The honesty rule is enforced visually.
- **No reorder in the renderer.** Every renderer consumes builder order verbatim. Pinned items get an amber accent; pinned status does not re-sort. See [`sort-policy-and-builders.md`](sort-policy-and-builders.md).
- **`IndicatorRanked` wording never says "better" / "worse".** Direction lives in the `verdict` enum; the renderer decides whether to badge. Avoids judgement language in cross-indicator framing.
- **All renderers MAY mount inside [ChartShell](chart-shell.md)** via `wrap_in_shell={true}` (default), or bare via `wrap_in_shell={false}` (for inline embedding such as the [`charts sandbox`](../../../../frontend/src/routes/DevChartsSandbox.svelte)).
- **Pinned-series stroke is thicker on TimeSeriesLine** (visual weight only; no extra colour band). Same rule as `OrderedCategoryBar`'s pinned-row amber accent.

## Test surface

- Per-renderer vitest: `HorizontalGroupedBar.test.ts`, `OrderedCategoryBar.test.ts`, `DumbbellRange.test.ts`, `TimeSeriesLine.test.ts`, `FacetPanelGrid.test.ts` (5–7 cases each).
- [`frontend/e2e/indicator-ranked-polish.spec.ts`](../../../../frontend/e2e/indicator-ranked-polish.spec.ts) — Playwright spec for the median tick + verdict copy.
- [`frontend/e2e/dev-charts-sandbox.spec.ts`](../../../../frontend/e2e/dev-charts-sandbox.spec.ts) — runtime mount smoke against all five renderers via [`/dev/charts-sandbox`](../../../../frontend/src/routes/DevChartsSandbox.svelte) (Phase 6).

## See also

- [`overview.md`](../overview.md) — visualization catalog (rows 117–121).
- [`sort-policy-and-builders.md`](sort-policy-and-builders.md) — the contract these renderers consume.
- [`chart-shell.md`](chart-shell.md), [`source-list-v2.md`](source-list-v2.md).

## Historical citations

Distils `.commit-msg-41.txt`–`.commit-msg-47.txt` and `.pr-body-41.md`–`.pr-body-47.md` (deleted on distillation). PRs 41–42 = IndicatorRanked adopter; PRs 43–47 = the five renderers in order: HorizontalGroupedBar, OrderedCategoryBar, DumbbellRange, TimeSeriesLine, FacetPanelGrid.
