# CompositionBar (Phase 3.6)

**Last Updated**: 2026-06-05

Horizontal 100%-stacked-bar primitive for single-entity composition (party seats in one state, fuel mix in one state, budget heads in one FY). Shipped as a three-PR split per R-16: primitive -> adapter -> mount.

> **F2a.5 migration (2026-06-05)**: the standalone `CompositionBar.svelte` renderer was retired. The diverging composition body now lives inside [`CategoryBar.svelte`](../../../../frontend/src/lib/charts/CategoryBar.svelte) as `mode="diverging"`, consuming the same `CompositionBarModel` view-model. The `composition-bar/` adapter package (types + helpers + adapter + experiment-definition) is unchanged and is the stable contract surface. Deeper rewrite of this doc lands in F2a.5.3.

## What it is

- [`frontend/src/lib/charts/CategoryBar.svelte`](../../../../frontend/src/lib/charts/CategoryBar.svelte) `mode="diverging"` - horizontal stacked-bar renderer (post-F2a.5.2); takes pre-coloured segments and a verdict caption. Lifted byte-identical from the retired `lib/CompositionBar.svelte` body in F2a.5.1.
- [`frontend/src/lib/charts/composition-bar/types.ts`](../../../../frontend/src/lib/charts/composition-bar/types.ts) - `CompositionBarModel`, `CompositionBarSegment` (zod contract with `is_tail` flag for collapsed tail segment).
- [`frontend/src/lib/charts/composition-bar/helpers.ts`](../../../../frontend/src/lib/charts/composition-bar/helpers.ts) — pure helpers: `totalSegmentValue`, `shareOfTotalPct`, `projectSegments` (tiny-segment lift), `formatSegmentReadout`, `segmentsSumMatchesTotal`.
- Fixture: Gujarat 2022 (BJP 156/182 = 85.7%, party-dominant; exercises tail handling).
- A/B experiment: mounted on state-hub behind a GrowthBook flag (Phase 3.6 (c)).

## Doctrinal rules

- **Tail segments stay visible.** Segments below `MIN_VISUAL_WIDTH_PCT` (0.6%) get lifted to that minimum width; the borrowed width is subtracted from the largest segment (mirrors `SeatDonut`). The honest `share_pct` stays on the segment so the legend shows the truth even when the bar is visually lifted. Citizens never see a "hidden" or "footnoted" segment.
- **Renderer never knows colours.** The adapter supplies `fill: /^#[0-9a-f]{6}$/i` on every segment. Renderer does not import `categoryColour` or `partyColour`; colour resolution is the adapter's job.
- **No variant prop.** CompositionBar is HORIZONTAL STACKED by definition. Donut, pie, and sunburst variants are forbidden. A new shape = a new component.
- **Mount inside [ChartShell](chart-shell.md).** Footer uses [SourceListV2](source-list-v2.md). R-24 (no chrome duplication) + R-28 (no fetch in shell) both compliant.
- **A/B switch lives in adapter**, not renderer. Renderer takes the model; experiment branches in the page picks which model to pass.

## Test surface

- [`composition-bar/helpers.test.ts`](../../../../frontend/src/lib/charts/composition-bar/helpers.test.ts) — 23 vitest cases (geometry, share computation, lift, sum-check, formatter).
- [`composition-bar/types.test.ts`](../../../../frontend/src/lib/charts/composition-bar/types.test.ts) — 17 vitest cases (zod contract, Gujarat fixture round-trip).
- [`frontend/e2e/composition-bar-mount.spec.ts`](../../../../frontend/e2e/composition-bar-mount.spec.ts) — Playwright mount smoke under the experiment flag.

## See also

- [`overview.md`](../overview.md) — visualization catalog (`CompositionBar` row at line 122).
- [`chart-shell.md`](chart-shell.md).
- [`source-list-v2.md`](source-list-v2.md).

## Historical citations

Distils `.commit-msg-30.txt`–`.commit-msg-32.txt` and `.pr-body-30.md`–`.pr-body-33.md` (deleted on distillation). PR-33 wired the footer action slots on CompositionBar (Phase 1.4 task 4).
