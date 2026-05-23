# Charts subsystem index

**Last Updated**: 2026-05-25

The `docs/architecture/frontend/charts/` directory holds per-primitive subsystem docs for the charting system. Each file documents one primitive's contract, doctrinal rules, and test surface.

| Doc | Scope |
| --- | --- |
| [`chart-shell.md`](chart-shell.md) | Shared frame (title, honesty banners, sources footer, action buttons). |
| [`source-list-v2.md`](source-list-v2.md) | Citation-ledger render surface; consumed by ChartShell footer. |
| [`stacked-trend.md`](stacked-trend.md) | Original v1 design draft (2026-05-14). Historical; superseded by `stacked-trend-v2.md`. |
| [`stacked-trend-v2.md`](stacked-trend-v2.md) | Realized v2 renderer (Phase 2 of the modernisation plan). |
| [`composition-bar.md`](composition-bar.md) | Horizontal 100%-stacked-bar primitive for single-entity composition. |
| [`temporal-viewport.md`](temporal-viewport.md) | Brush helpers + component; index-first time-window control. |
| [`sort-policy-and-builders.md`](sort-policy-and-builders.md) | Closed-enum sort policy + view-model builders (bar / multi-dim / time). |
| [`generic-renderers.md`](generic-renderers.md) | The five Phase 3.5 renderers (HorizontalGroupedBar, OrderedCategoryBar, DumbbellRange, TimeSeriesLine, FacetPanelGrid) + IndicatorRanked polish. |
| [`small-multiples.md`](small-multiples.md) | Pure helpers for signed-domain small multiples (fixes the `Math.abs` sign-collapse bug). |
| [`icon-registry.md`](icon-registry.md) | Build-time SVG allowlist parser + Vite plugin. |
| [`choropleth-ramp.md`](choropleth-ramp.md) | OkLCh ramp constants, accessor, monotonicity tests. |

## See also

- [`../overview.md`](../overview.md) — frontend architecture overview with the renderer catalog (one-line summary per renderer).
- [`../colours.md`](../colours.md) — colour-system subsystem (links to `choropleth-ramp.md` for the ramp contract).
- [`../../../how-to/distill.md`](../../../how-to/distill.md) — the seven-step citizen-first distill runbook.
- [TODO/20260518-frontend-charting-modernisation-plan.md](../../../../TODO/20260518-frontend-charting-modernisation-plan.md) — the master plan these docs distil.
