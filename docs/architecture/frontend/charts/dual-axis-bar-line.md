# DualAxisBarLine — dual-axis bar + line primitive

**Last Updated**: 2026-06-12

Closed-renderer extension shipped in PR-4 of [TODO/20260612-party-rendering-and-party-pages-plan.md](../../../../TODO/20260612-party-rendering-and-party-pages-plan.md). Inline-folded ADR lives in [docs/concepts/schema-is-the-design-system.md](../../../concepts/schema-is-the-design-system.md#dualaxisbarline-pr-4-of-todo20260612-party-rendering-and-party-pages-plan-2026-06-12) per the no-new-ADR-file routing contract.

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
