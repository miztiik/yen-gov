# Small multiples (Phase 4)

**Last Updated**: 2026-05-25

Pure helpers that fix the `IndicatorSmallMultiples` signed-domain bug. Pre-fix the renderer used `Math.abs` for both y_max and projection, which collapsed sign: a state going `-50 → +50` looked identical to `+50 → +50`. The helpers ship signed domain, signed projection, and path-break behaviour.

## What it is

- [`frontend/src/lib/charts/small-multiples/helpers.ts`](../../../../frontend/src/lib/charts/small-multiples/helpers.ts):
  - `computeYDomain(values) → { min, max, includes_zero }` — anchors min at 0 when ALL values are non-neg, anchors max at 0 when ALL values are non-pos; preserves true bounds when the series straddles zero.
  - `projectX(period_index, period_count, x_extent)` and `projectY(value, y_domain, y_extent)` — honour signed domain.
  - `pathForSeries(points)` — emits `M..L..M..L..` segments so the path breaks around missing values; missing-at-end does NOT linger on the chart.
  - `latestDot(points)`, `breakXs(points)`, `zeroBaselineY(y_domain, y_extent)`.
- Adopter: [`IndicatorSmallMultiples.svelte`](../../../../frontend/src/lib/IndicatorSmallMultiples.svelte) consumes the helpers (Phase 4 follow-up PR).

## Doctrinal rules

- **Signed domain is the default.** `computeYDomain` returns `{min, max, includes_zero}`. When `includes_zero === true`, the renderer draws a zero baseline (via `zeroBaselineY`). Anchoring is one-sided: all non-neg → `min = 0` (true max used); all non-pos → `max = 0` (true min used); straddling → true bounds on both sides.
- **Path breaks at missing.** `pathForSeries` returns a `d` string with `M` commands at every missing-gap boundary. Renderer does NOT bridge missing values with a straight line (that would lie about the data). For dashed-bridge behaviour, see [`TimeSeriesLine`](generic-renderers.md) which has its own `suppress_breaks` flag.
- **All helpers are pure.** Null / NaN / undefined are ignored cleanly (not throwing, not coercing to 0). Empty input returns `{ min: 0, max: 0, includes_zero: true }`.
- **No domain inflation.** Helpers do NOT add padding above the max or below the min. If the renderer wants headroom, it inflates the extent at projection time.

## Test surface

- [`small-multiples/helpers.test.ts`](../../../../frontend/src/lib/charts/small-multiples/helpers.test.ts) — 21 vitest cases (empty input; all non-neg / non-pos; straddling; null/NaN/undefined ignored; projection on min/max/0; path segmentation at missing; latest dot; break xs; zero baseline; signed vs unsigned regression).

## See also

- [`generic-renderers.md`](generic-renderers.md) — TimeSeriesLine has its own break/bridge contract (`suppress_breaks` flag).
- [`overview.md`](../overview.md) — visualization catalog.

## Historical citations

Distils `.commit-msg-48.txt`, `.commit-msg-49.txt` and `.pr-body-48.md`, `.pr-body-49.md` (deleted on distillation). PR-48 = helpers; PR-49 = `IndicatorSmallMultiples` adopter.
