# DualAxisBarLine — dual-axis bar + line primitive

**Last Updated**: 2026-06-14

Closed-renderer extension shipped in PR-4 of [docs/archive/plans/20260612-party-rendering-and-party-pages-plan.md](../../../archive/plans/20260612-party-rendering-and-party-pages-plan.md). Composite mode (additive `mode: "composite"` prop) shipped in PR-10 of [docs/archive/plans/20260614-party-page-reimagination-plan.md](../../../archive/plans/20260614-party-page-reimagination-plan.md). Inline-folded ADR lives in [docs/concepts/schema-is-the-design-system.md](../../../concepts/schema-is-the-design-system.md#dualaxisbarline-pr-4-of-todo20260612-party-rendering-and-party-pages-plan-2026-06-12) per the no-new-ADR-file routing contract.

## What it is

- [`frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte`](../../../../frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.svelte) — pure d3-scale + Svelte 5 SVG component. Bars on the left Y axis, line + dots on the right Y axis, ordinal X axis on shared `period_label`.
- Pure helpers extracted to its `<script module>` block (project doctrine; vitest pins the contract without mounting Svelte): `buildScales(bars, line)`, `pickLabelStride(width, year_count, mobile_stride)`, `yearFromPeriodLabel(period_label)`.
- Test surface: [`DualAxisBarLine.test.ts`](../../../../frontend/src/lib/charts/DualAxisBarLine/DualAxisBarLine.test.ts) covers the three pure helpers across happy-path + defensive edges.

## Contract

| Prop | Shape | Notes |
| --- | --- | --- |
| `bars` | `{ period_label, value }[]` | Bar series. X scale derives its domain from this + `line`. |
| `line` | `{ period_label, value }[]` | Line series. Period labels not in `bars` extend the X domain. |
| `bar_color` | `string` (hex) | Bar fill. Caller drives via the party-colour resolver. |
| `line_color` | `string?` | Line + dot colour. Default `#334155` (slate-700). |
| `bar_y_label` | `string?` | Left Y axis label. Default `"Value"`. |
| `line_y_label` | `string?` | Right Y axis label. Default `"Line"`. |
| `bar_format` | `(n: number) => string` | Bar value formatter (tick labels + tooltip). |
| `line_format` | `(n: number) => string` | Line value formatter; when the sample (1.0) includes `%` the right axis caps at 100. |
| `height` | `number?` | SVG height. Default 360. |
| `mobile_label_stride` | `number?` | X-label stride at viewport < 640px. Default 4. |
| `mode` | `"dual-axis" \| "composite"` | Encoding mode. Default `"dual-axis"` (legacy: bars + line on two Y axes). `"composite"` collapses to a single 0-100 Y axis where bar HEIGHT = `bars[i].value` (vote-share %) and bar fill is split into a saturated lower band of height `bars[i].value * (line[i].value / line_denominator)` (seats-won subset) plus a 40%-opacity upper band (didn't-convert remainder). Line series is hidden in composite mode (the conversion ratio is in the fill geometry, not a separate series). See [Mode: composite](#mode-composite) below. |

## Mode: composite

Added 2026-06-14 in PR-10 of [docs/archive/plans/20260614-party-page-reimagination-plan.md](../../../archive/plans/20260614-party-page-reimagination-plan.md). Default is preserved as `"dual-axis"`; consumers opt in.

The composite encoding answers the citizen question "what share of the vote did the party get, and how much of that converted to seats?" in ONE bar geometry on ONE Y axis (0-100%). Per cycle:

- **X position**: cycle year (existing band scale).
- **Bar height**: `vote_share_pct` (single Y axis labelled "Vote share %").
- **Bar fill (lower band)**: from the bottom up to `bar_height * (seats_won / seats_contested)`, the brand colour at full saturation. This is the seat-conversion subset.
- **Bar fill (upper band)**: from the seat-conversion band up to the bar top, the brand colour at 40% opacity. This is the "didn't convert" remainder.
- **Bar width**: per the existing band scale.
- **Tooltip**: `Year: 2024 - vote share 36.5% - seats 211 of 543 contested (seat conversion 38.9%)`.

The line series is hidden in composite mode; the conversion story lives in the fill geometry, not a parallel series. Methodology-break markers + caption stay anchored to the X band (unchanged from `"dual-axis"` mode).

**Geometry assertions** (vitest + browser smoke): the chart SVG carries `<rect data-mode="composite" data-overlay="seats-fill">` elements per cycle so contract tests can pin the two-band split without mounting Svelte.

**Qualifying indicators** (closed-renderer extension-log entry):

- Parliament: vote-share + seat-conversion (citizen-facing primary view on `/parties/<slug>`).
- State Assembly: parallel.
- Future: per-event vote-share + winner-margin.
- Future: per-state turnout + valid-vote-share.

Full doctrine: [docs/concepts/schema-is-the-design-system.md](../../../concepts/schema-is-the-design-system.md#closed-renderer-extension-log).

## Mobile behaviour

- Wrapper binds `clientWidth`; SVG width scales to parent.
- X-label stride = `mobile_label_stride` at viewport < 640px; stride = 2 above 640px when year-count > 12 (label-density rule); stride = 1 otherwise.
- Tap on a bar reveals a `ChartTooltip` with year + both values.

## Doctrinal rules

- **Standalone, not composed.** The primitive is NOT extracted from `StackedTrendV2` (Jony B2 verdict); the encoding is qualitatively different (overlay of 2 series on 2 axes vs N-series stack on one axis). Mid-PR composition pivots violate the verdict and the no-strangler-fig user direction.
- **No new npm deps.** Pure d3-scale (`scaleBand`, `scaleLinear`) + Svelte 5. The `@floating-ui` library that surfaced in early design notes was rejected.
- **No data fetching.** The renderer accepts pre-shaped `bars` + `line` arrays; consumers (e.g. [Party.svelte](../../../../frontend/src/routes/Party.svelte)) hand-shape from their view-model.
- **No aria/role.** Per CLAUDE.md §0a — a11y descoped at the project level.
- **Reuse guard.** Future bar+line surfaces MUST mount this primitive; rebuilding bar+line in another file violates the schema-is-the-design-system rule.

## See also

- [docs/concepts/schema-is-the-design-system.md](../../../concepts/schema-is-the-design-system.md#closed-renderer-extension-log) — closed-renderer extension log + qualifying-indicator threshold.
- [docs/architecture/frontend/party-rendering.md](../party-rendering.md) — adopter (per-party page).
- [docs/architecture/frontend/charts/stacked-trend-v2.md](stacked-trend-v2.md) — sibling closed-renderer (N-series stack; not the same encoding).
