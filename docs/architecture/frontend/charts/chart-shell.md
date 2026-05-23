# ChartShell — shared chart frame

**Last Updated**: 2026-05-25

Phase 1.4 task 1 of the [charting modernisation plan](../../../../docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md). The shared frame every yen-gov chart eventually mounts inside, so title, subtitle, honesty banners, sources, and action buttons follow consistent rules.

## What it is

- [`frontend/src/lib/charts/ChartShell.svelte`](../../../../frontend/src/lib/charts/ChartShell.svelte) — host component with named slots for title row, toolbar, subtitle, honesty banners, chart body, [SourceListV2](source-list-v2.md) footer, and action footer.
- [`frontend/src/lib/charts/chart-shell/types.ts`](../../../../frontend/src/lib/charts/chart-shell/types.ts) — `ChartShellAction` is a CLOSED enum of six ids: `view_data`, `download`, `copy_link`, `share`, `reset_view`, `full_range`. Also exports `ChartShellActionSpec` and `ChartShellHonestyBanner`.
- [`frontend/src/lib/charts/chart-shell/actions.ts`](../../../../frontend/src/lib/charts/chart-shell/actions.ts) — pure helpers: `ALLOWED_ACTIONS`, `filterAllowedActions(...)` (preserves order), `sortActionsForFooter(...)` (stable canonical order).

## Doctrinal rules

- **Action vocabulary is CLOSED** (CLAUDE.md §10 three-place lock). Adding a new action requires editing `types.ts` + `actions.ts` + the [plan doc](../../../../docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md) in lockstep. Build will pass without the doc edit, so the lock is procedural; the closed `ChartShellAction` union enforces the code half.
- **Shell never fetches.** ChartShell receives `readonly SourceV2Row[]` from upstream (R-28). It does not know dataset paths, manifest URLs, or any I/O. Loaders run before mount; rows arrive resolved.
- **Sources rendering is delegated.** ChartShell forwards rows to [`SourceListV2`](source-list-v2.md); the shell adds no new telemetry surface and cannot smuggle `url` or `fetched_at` because the type system forbids them.
- **No aria/role attributes** (CLAUDE.md §0a — a11y descoped). Visible affordances only. `<button>` elements remain real so keyboard activation works for free.
- **Adopters wrap, never inline.** A renderer that needs the frame uses `<ChartShell>...</ChartShell>` as its outer element. Renderers MAY render bare for inline embedding (e.g., the [`charts sandbox`](../../../../frontend/src/routes/DevChartsSandbox.svelte)) by passing `wrap_in_shell={false}` to the renderer.

## Test surface

- [`chart-shell/actions.test.ts`](../../../../frontend/src/lib/charts/chart-shell/actions.test.ts) — 14 vitest cases: closed-enum freeze, `filterAllowedActions` preserves input order, `sortActionsForFooter` returns canonical order, composition (`filter then sort`) is stable.

## See also

- [`overview.md`](../overview.md) — visualization catalog (ChartShell row at line 115).
- [`source-list-v2.md`](source-list-v2.md) — the footer surface ChartShell delegates source rendering to.
- [`stacked-trend-v2.md`](stacked-trend-v2.md), [`composition-bar.md`](composition-bar.md), [`generic-renderers.md`](generic-renderers.md) — adopters.

## Historical citations

Distils `.commit-msg-29.txt`, `.commit-msg-33.txt` and `.pr-body-4.md`, `.pr-body-14.md`, `.pr-body-29.md`, `.pr-body-33.md` (deleted on distillation). PR-4 introduced SourceListV2 types alongside the shell scaffolding.
