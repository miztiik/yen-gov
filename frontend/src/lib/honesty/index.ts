/**
 * Honesty primitives — Phase 2 of TODO/VIZ-LAYER-GAPS-PLAN.md.
 *
 * Five small Svelte components that consume the Phase 1 renderer
 * helpers (../indicator-render.ts) and surface the disclosures the
 * 2026-05-15 audit found missing. Each is intentionally bland and
 * single-purpose; chart parents compose them.
 *
 *   - SeriesBreakAnnotation: vertical marker inside a plot.
 *   - SnapshotBadge:         "single-year snapshot", "current prices", etc.
 *   - DirectionLegendCue:    "↑ better", "↓ better", "↔ neutral".
 *   - VintageTooltipLine:    methodology vintage + nearest break note.
 *   - RebaseBanner:          banner above index-series charts.
 *
 * No state, no fetch, no DOM math — all positioning data is passed in.
 */
export { default as SeriesBreakAnnotation } from "./SeriesBreakAnnotation.svelte";
export { default as SnapshotBadge } from "./SnapshotBadge.svelte";
export { default as DirectionLegendCue } from "./DirectionLegendCue.svelte";
export { default as VintageTooltipLine } from "./VintageTooltipLine.svelte";
export { default as RebaseBanner } from "./RebaseBanner.svelte";
