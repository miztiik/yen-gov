# Temporal viewport brush (Phase 1.5)

**Last Updated**: 2026-05-25

Pure helpers plus a brush component that let any time-axis chart restrict its visible window to an index range, with stable URL serialisation across data revisions. Decoupled from calendar math by design: the brush operates on indices into `ordered_period_ids`, not dates.

## What it is

- [`frontend/src/lib/charts/temporal-viewport/types.ts`](../../../../frontend/src/lib/charts/temporal-viewport/types.ts) — `TemporalDomain`, `TemporalWindow`, `TemporalDomainKind`, `TemporalPreset`, `TemporalWindowIndices`.
- [`frontend/src/lib/charts/temporal-viewport/helpers.ts`](../../../../frontend/src/lib/charts/temporal-viewport/helpers.ts) — pure helpers: `buildDomain`, `parseLeadingYear`, `fullWindow`, `isFullWindow`, `windowIndices`, `clampWindow`, `presetWindow`, `filterItemsToWindow`.
- [`frontend/src/lib/charts/temporal-viewport/TemporalViewportBrush.svelte`](../../../../frontend/src/lib/charts/temporal-viewport/TemporalViewportBrush.svelte) — small UI component that emits brush events; calls into the helpers above for state transitions.
- **First adopter**: [`StackedTrendV2`](stacked-trend-v2.md) wires the brush via its `visible_period_ids` view-model input.

## Doctrinal rules

- **Indices, not dates.** The brush emits `[start_index, end_index]` into the `ordered_period_ids` array. Year arithmetic is used ONLY by the date-derivable presets (`5y`, `10y`, `25y`); the brush itself is calendar-free, so it works for election-cycle and custom dimensions too.
- **`parseLeadingYear` is structural.** It matches bare year (`"2024"`), year + separator (`"2024-25"`), FY prefix (`"FY24"`). Election-event ids like `"AcGenMay2023"` do NOT match — adapters declare them as `election_cycle` or `custom` so the brush degrades to ordinal indexing.
- **Stale ids degrade silently.** A serialised brush URL referencing a `period_id` that no longer exists falls back to `fullWindow`; never throws. Data revisions that drop a period leave bookmarks survivable.
- **Reversed windows normalise silently.** `clampWindow` swaps `from > to`. Single-period windows are preserved (`from === to` is valid).
- **All helpers are pure and null-honest.** Nulls do not throw; empty arrays do not throw.

## Test surface

- [`temporal-viewport/helpers.test.ts`](../../../../frontend/src/lib/charts/temporal-viewport/helpers.test.ts) — 45 vitest cases (index-first contract, stale-id fallback, reversed normalisation, single-period, year parsing, edge cases).
- [`frontend/src/lib/charts/temporal-viewport/TemporalViewportBrush.test.ts`](../../../../frontend/src/lib/charts/temporal-viewport/TemporalViewportBrush.test.ts) — 3 vitest cases for component mount/event emission.
- [`frontend/e2e/temporal-brush-mount.spec.ts`](../../../../frontend/e2e/temporal-brush-mount.spec.ts) — Playwright smoke against the StackedTrendV2 adopter.

## See also

- [`stacked-trend-v2.md`](stacked-trend-v2.md) — first adopter.
- [`sort-policy-and-builders.md`](sort-policy-and-builders.md) — the `chronological` sort policy re-uses `parseLeadingYear` so brush math and chart math agree.
- [`overview.md`](../overview.md).

## Historical citations

Distils `.commit-msg-34.txt`–`.commit-msg-36.txt` and `.pr-body-34.md`–`.pr-body-36.md` (deleted on distillation).
