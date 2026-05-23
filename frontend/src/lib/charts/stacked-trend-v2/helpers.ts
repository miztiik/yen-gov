// StackedTrendV2 — pure view-model helpers (Phase 2.1, R-09).
//
// Per TODO/20260518-frontend-charting-modernisation-plan.md Phase 2.1.
// These helpers extract the math previously inlined in v1
// `frontend/src/lib/charts/StackedTrend.svelte` (`barTotal`, `segHeight`,
// `maxTotal`) into typed, testable pure functions, plus the new helpers
// the v2 polish work needs (visible-category set, label eligibility,
// readout rows).
//
// Branch by Abstraction (R-08): v1's inline helpers are UNTOUCHED. v2's
// shell (`../StackedTrendV2.svelte`) does NOT consume these helpers yet —
// it stays inert until Phase 2.1c+ wires bar geometry. Caller migration
// is sequenced in Track-D D10..D12.
//
// All helpers honour the v2 type contract from `./types.ts`:
//
//   - `availability !== "present"` segments are EXCLUDED from totals,
//     EXCLUDED from share denominators, and surface in readout rows with
//     their availability so the renderer can show a hatch / "n/a" label.
//   - `segment.value === null` is treated as the same class as a
//     non-present availability (no numeric contribution).
//   - The `bar.total` override on a `StackedTrendV2Bar` wins over the
//     computed sum so adapters can pre-pin a denominator that differs
//     from the segment sum (e.g. a published total that includes
//     un-classified residue not represented as a segment).
//
// No DOM, no fetch, no DuckDB. Vitest unit coverage in
// `./helpers.test.ts`. Phase 2.2's R-11 contract-tier round-trip lives
// in Playwright per the canonical-loader convention (vitest can't load
// DuckDB-WASM in node env, see
// `frontend/src/lib/canonical/manifest.test.ts`).

import type {
  StackedTrendV2Bar,
  StackedTrendV2Category,
  StackedTrendV2Model,
  StackedTrendV2Segment,
} from "./types";

/**
 * Default share-of-bar threshold (percent points) above which an inline
 * label is eligible to render on a segment. Below the threshold the
 * renderer falls back to the legend (Phase 2.4 3-tier rule). Chosen to
 * match the v1 design-doc convention of ~8% — small enough to label the
 * common cases (gas, hydro on a power-source bar), large enough to
 * avoid clutter on mobile widths.
 */
export const DEFAULT_LABEL_THRESHOLD_PCT = 8;

/**
 * Citizen-readable label per chart mode (R-12, Phase 2.2).
 *
 * Kept as plain English so the segmented control reads naturally
 * ("Share" / "Total") rather than as engineering jargon
 * ("Percent" / "Absolute"). The internal mode token stays
 * `percent` / `absolute` so existing helper signatures and the
 * `model.default_mode` field don't move.
 */
export const MODE_LABELS: Readonly<Record<"percent" | "absolute", string>> = {
  percent: "Share",
  absolute: "Total",
};

/**
 * Resolve the chart's INITIAL mode at mount time (R-12, Phase 2.2).
 *
 * Precedence: caller's optional `mode_override` wins, otherwise the
 * model's `default_mode` (which zod has already defaulted to
 * `"percent"` when the adapter omitted it). The citizen can override
 * either choice via the segmented control once the chart is mounted;
 * the override prop is the INITIAL state, not a permanent lock.
 *
 * Extracted from the component so the resolution rule is unit-testable
 * without mounting Svelte.
 */
export function resolveInitialMode(
  modeOverride: "percent" | "absolute" | undefined,
  modelDefault: "percent" | "absolute",
): "percent" | "absolute" {
  return modeOverride ?? modelDefault;
}

/**
 * Sum of present, non-null segment values on a bar.
 *
 * If `bar.total` is explicitly set on the bar, that wins — the adapter
 * has pre-pinned a denominator (e.g. a published total that includes
 * un-classified residue). Otherwise the helper sums every segment with
 * `availability === "present"` and a non-null value. Missing /
 * not_applicable / null segments contribute nothing.
 *
 * Returns 0 when all segments are missing — callers MUST handle this
 * explicitly before dividing (see `segmentSharePct`).
 */
export function barTotal(bar: StackedTrendV2Bar): number {
  if (bar.total != null) return bar.total;
  let acc = 0;
  for (const seg of bar.segments) {
    if (seg.availability !== "present") continue;
    if (seg.value == null) continue;
    acc += seg.value;
  }
  return acc;
}

/**
 * Max bar-total across every bar in a series, with a floor of 1.
 *
 * The floor of 1 mirrors v1 behaviour — it keeps absolute-mode height
 * arithmetic safe when every bar is zero (otherwise we'd divide by
 * zero in `segmentVisualHeightPct`). Empty `bars` arrays return 1.
 */
export function maxBarTotal(bars: readonly StackedTrendV2Bar[]): number {
  let max = 1;
  for (const bar of bars) {
    const t = barTotal(bar);
    if (t > max) max = t;
  }
  return max;
}

/**
 * Share of a single segment within its bar's total, expressed as a
 * percentage (0–100, NOT 0–1).
 *
 * Returns 0 for missing / not_applicable / null segments — they do not
 * contribute to the denominator and have no share to report. Returns 0
 * when the bar total is <= 0 (cannot divide).
 */
export function segmentSharePct(
  segment: StackedTrendV2Segment,
  total: number,
): number {
  if (segment.availability !== "present") return 0;
  if (segment.value == null) return 0;
  if (total <= 0) return 0;
  return (segment.value / total) * 100;
}

/**
 * Visual height of a single segment within the chart canvas, expressed
 * as a percentage of the canvas height (0–100).
 *
 * In `percent` mode every bar is rendered at 100% height, so the
 * segment's height equals its share of the bar's total.
 *
 * In `absolute` mode the bar's height scales with `barTotalForBar /
 * maxTotal`, and the segment's height within that bar scales with
 * `segment.value / barTotalForBar`. The two ratios collapse into
 * `segment.value / maxTotal` once you divide them out — which is what
 * v1 does and what makes the height stable as the user toggles modes.
 *
 * Missing / not_applicable / null segments return 0.
 */
export function segmentVisualHeightPct(
  segment: StackedTrendV2Segment,
  barTotalForBar: number,
  maxTotal: number,
  mode: "percent" | "absolute",
): number {
  if (segment.availability !== "present") return 0;
  if (segment.value == null) return 0;
  if (mode === "percent") {
    if (barTotalForBar <= 0) return 0;
    return (segment.value / barTotalForBar) * 100;
  }
  if (maxTotal <= 0) return 0;
  return (segment.value / maxTotal) * 100;
}

/**
 * Set of category IDs that have at least one bar with a present,
 * non-null, non-zero value somewhere in the model.
 *
 * A category whose segments are universally missing / not_applicable /
 * null / zero adds noise to the legend and the readout panel — the
 * renderer (and the future label-eligibility code) uses this set to
 * keep visible chrome tied to actual data. Order matches the
 * `model.categories` array so the renderer's existing palette ordering
 * is preserved.
 */
export function visibleCategoryIds(
  model: StackedTrendV2Model,
): readonly string[] {
  const visible = new Set<string>();
  for (const bar of model.bars) {
    for (const seg of bar.segments) {
      if (seg.availability !== "present") continue;
      if (seg.value == null) continue;
      if (seg.value === 0) continue;
      visible.add(seg.category_id);
    }
  }
  return model.categories
    .map((c) => c.id)
    .filter((id) => visible.has(id));
}

/**
 * Is an inline label eligible to render on a segment, given its visual
 * height in canvas-percent units?
 *
 * Pure comparison helper — the renderer computes the visual height with
 * `segmentVisualHeightPct` and passes it in. Decoupling the comparison
 * from the geometry keeps the threshold tunable per-route (a dense
 * mobile width might lift the threshold to 12% to avoid overlap) and
 * keeps the helper trivially testable.
 *
 * A negative visual height returns false (defensive — shouldn't happen
 * given the geometry helpers floor at 0, but cheap to assert).
 */
export function isLabelEligible(
  visualHeightPct: number,
  thresholdPct: number = DEFAULT_LABEL_THRESHOLD_PCT,
): boolean {
  if (visualHeightPct < 0) return false;
  return visualHeightPct >= thresholdPct;
}

/**
 * One row in the pinned readout panel — Phase 2.3 (R-12 no-hover-state).
 *
 * Present rows carry a positive `share_pct`; missing / not_applicable
 * rows carry `share_pct === 0` and a non-null `availability_label` (or
 * the readable default the renderer falls back to). The renderer
 * resolves the fill colour via the existing `categoryFill` helper —
 * fill is a render concern, not a model concern, so it stays out of
 * `ReadoutRow`.
 */
export interface ReadoutRow {
  category_id: string;
  label: string;
  value: number | null;
  share_pct: number;
  availability: "present" | "missing" | "not_applicable";
  availability_label?: string;
}

/**
 * One readout row per segment on the bar, joined to the category label
 * from `model.categories`. Sorted by share descending, then by category
 * `order` (then by id) for deterministic tie-breaking. Missing /
 * not_applicable rows sink to the bottom (share_pct === 0).
 *
 * Segments referencing an unknown category_id (not in `categories`) are
 * skipped — the readout panel never shows a row it can't label. This
 * mirrors v1 silently dropping unknown segments in `inUseCodes` /
 * `fillFor` rather than fabricating a placeholder label.
 */
export function readoutRows(
  bar: StackedTrendV2Bar,
  categories: readonly StackedTrendV2Category[],
): readonly ReadoutRow[] {
  const total = barTotal(bar);
  const byId = new Map(categories.map((c) => [c.id, c]));
  const orderById = new Map(
    categories.map((c, i) => [c.id, c.order ?? i]),
  );

  const rows: ReadoutRow[] = [];
  for (const seg of bar.segments) {
    const cat = byId.get(seg.category_id);
    if (!cat) continue;
    rows.push({
      category_id: seg.category_id,
      label: cat.label,
      value: seg.availability === "present" ? seg.value : null,
      share_pct: segmentSharePct(seg, total),
      availability: seg.availability,
      availability_label: seg.availability_label,
    });
  }

  rows.sort((a, b) => {
    if (a.share_pct !== b.share_pct) return b.share_pct - a.share_pct;
    const ao = orderById.get(a.category_id) ?? 0;
    const bo = orderById.get(b.category_id) ?? 0;
    if (ao !== bo) return ao - bo;
    return a.category_id.localeCompare(b.category_id);
  });

  return rows;
}
