# StackedTrendV2

**Last Updated**: 2026-05-25

Phase 2 of the [charting modernisation plan](../../../../docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md). Successor to the v1 [`stacked-trend.md`](stacked-trend.md) design draft. The v1 doc remains as the original 2026-05-14 plan; this file documents what actually shipped (PRs #134–#148, May 2026).

## What it is

A generic stacked-trend renderer at [`frontend/src/lib/charts/StackedTrendV2.svelte`](../../../../frontend/src/lib/charts/StackedTrendV2.svelte) backed by:

- **Zod model** — [`frontend/src/lib/charts/stacked-trend-v2/types.ts`](../../../../frontend/src/lib/charts/stacked-trend-v2/types.ts) defines `StackedTrendV2Model` (root `schema_version: "2.0"`) and `StackedTrendV2Source` (11-column [ADR-0032](../../../reference/decision-index.md) ledger).
- **View-model helpers** — [`frontend/src/lib/charts/stacked-trend-v2/helpers.ts`](../../../../frontend/src/lib/charts/stacked-trend-v2/helpers.ts) ships pure helpers for segmented mode, pinned readout, inline labels overlay, missing/`not_applicable` hatch, motion, and SVG export. `MODE_LABELS = { percent: "Share", absolute: "Total" }` — the renderer paints from this constant.
- **Adopters** — [`ElectionSeatsTrend.svelte`](../../../../frontend/src/lib/ElectionSeatsTrend.svelte) and `StackedTrendArtifact.svelte` (Track-D D10–D12). The v1 `StackedTrend.svelte` was deleted in D13 once both adopters migrated.

## Doctrinal rules

- **Source schema discipline.** `StackedTrendV2Source` excludes `url`, `fetched_at`, and `content_hash` at the type system level — the zod schema makes these unrepresentable so adapters cannot accidentally leak fetch telemetry into the citizen-facing ledger. The `sources_v2_discipline` test in `types.test.ts` pins this.
- **No silent schema defaults.** Missing `schema_version: "2.0"` is a zod-validation failure; the literal must be present.
- **Migrations are branch-by-abstraction** ([R-08](../../../how-to/distill.md)). v2 ships alongside v1; each caller migrates in its own PR; v1 deletion is the FINAL PR after the last caller migrates. No mid-stack pivots; no parallel-renderer drift.
- **SVG export uses solid fills only.** No gradients or patterns (the hatch is rendered via a `<pattern>` reference, which export inlines as a solid placeholder); the theme is captured at emission time.
- **Stable Playwright selectors.** The mode toggle wrapper carries `data-control="mode-toggle"` and each button carries `data-mode-value={percent|absolute}`. Tests target these attributes, NOT the visible copy — see commit `f915ecb9` for the regression that prompted this rule (the copy moved from "percent"/"absolute" to "Share"/"Total" via `MODE_LABELS`).
- **Pinned readout survives period changes.** When the citizen pins a segment and then drags the temporal brush, the pinned state stays pinned; the readout recomputes against the new window.

## Test surface

- [`stacked-trend-v2/types.test.ts`](../../../../frontend/src/lib/charts/stacked-trend-v2/types.test.ts) — 25 vitest cases (root schema, ledger discipline, fixture round-trip, category fills, bar segments, `OTHER_CATEGORY` alignment).
- [`stacked-trend-v2/helpers.test.ts`](../../../../frontend/src/lib/charts/stacked-trend-v2/helpers.test.ts) — per-feature coverage (segmented mode, pinned readout, labels, hatch, export).
- [`frontend/e2e/stacked-trend.spec.ts`](../../../../frontend/e2e/stacked-trend.spec.ts) — Playwright smoke that mounts `/t/energy`, asserts the toggle renders, switches modes via `data-mode-value`, and confirms the SourceList footer paints.

## See also

- [`overview.md`](../overview.md) — visualization catalog (StackedTrendV2 row at line 116).
- [`chart-shell.md`](chart-shell.md) — shared frame wrapping StackedTrendV2's title, honesty, sources, and actions.
- [`source-list-v2.md`](source-list-v2.md) — ledger renderer that StackedTrendV2's footer mounts.
- [`temporal-viewport.md`](temporal-viewport.md) — brush helpers driving the temporal-window control.
- [`sort-policy-and-builders.md`](sort-policy-and-builders.md) — view-model builders that StackedTrendV2 consumes for category ordering.
- [ADR-0032](../../../reference/decision-index.md) — sources citation-ledger contract (the v2 source shape).

## Historical citations

This doc distils:

- Commit messages: [`.commit-msg-5.txt`](#) through [`.commit-msg-13.txt`](#), [`.commit-msg-15.txt`](#)–[`.commit-msg-17.txt`](#), [`.commit-msg-19.txt`](#) (deleted on distillation).
- PR bodies: `.pr-body-5.md` through `.pr-body-13.md`, `.pr-body-15.md`–`.pr-body-17.md`, `.pr-body-19.md` (deleted on distillation).
- Merged PRs on `main`: #134 through #148 (May 2026).
