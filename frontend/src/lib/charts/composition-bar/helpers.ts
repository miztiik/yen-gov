// CompositionBar — pure geometry + summary helpers. No Svelte, no DOM.
//
// The renderer (`CompositionBar.svelte`) consumes these helpers to
// project a view-model onto SVG coordinates and short summary text.
// Keeping the math here means vitest can pin the percent maths to
// 4 decimal places without booting jsdom.

import type {
  CompositionBarModel,
  CompositionBarSegment,
} from "./types";

/**
 * One segment projected onto the 0..100 horizontal axis. The renderer
 * places each segment as a `<rect>` at `x_pct` with width `width_pct`.
 *
 * `share_pct` is the **honest** share (value / sum-of-values * 100);
 * `width_pct` may be lifted to `MIN_VISUAL_WIDTH_PCT` for tiny
 * segments and the borrow is taken from the largest segment so the
 * sum stays 100 — same trick as `SeatDonut`'s `visual_angles`. Tiny
 * segments stay visible at chart widths where 0.2% would otherwise
 * sub-pixel away. The numeric readout still reports the honest share.
 */
export interface CompositionBarSegmentProjection {
  readonly id: string;
  readonly label: string;
  readonly value: number;
  readonly fill: string;
  readonly swatch_role: string;
  readonly is_tail: boolean;
  readonly x_pct: number;
  readonly width_pct: number;
  readonly share_pct: number;
}

/** Floor width below which a segment becomes visually invisible at
 *  realistic chart widths (300..900 px). 0.6% = ~2 px at 320 px width. */
export const MIN_VISUAL_WIDTH_PCT = 0.6;

/**
 * Sum the segment values. Stable on empty input (returns 0) so callers
 * can guard divide-by-zero with a single check.
 */
export function totalSegmentValue(
  segments: readonly CompositionBarSegment[],
): number {
  return segments.reduce((acc, s) => acc + s.value, 0);
}

/**
 * Honest share of each segment in percent. Sum equals 100 when total
 * is positive; returns zeros (and a zero sum) when total is zero so
 * the caller can short-circuit empty charts cleanly.
 */
export function shareOfTotalPct(
  segments: readonly CompositionBarSegment[],
): readonly number[] {
  const total = totalSegmentValue(segments);
  if (total <= 0) return segments.map(() => 0);
  return segments.map(s => (s.value / total) * 100);
}

/**
 * Project a view-model onto the SVG horizontal axis with the
 * tiny-segment lift applied. Returns one projection per non-zero
 * segment in input order; zero-value segments are filtered out
 * (a zero-width rect renders nothing).
 *
 * The borrowing rule matches `SeatDonut.visual_angles`: tiny segments
 * (below `MIN_VISUAL_WIDTH_PCT`) get lifted, and the deficit is
 * subtracted from the LARGEST segment (it can spare a fraction of a
 * percent without becoming visually wrong).
 */
export function projectSegments(
  segments: readonly CompositionBarSegment[],
): readonly CompositionBarSegmentProjection[] {
  const nonZero = segments.filter(s => s.value > 0);
  if (nonZero.length === 0) return [];
  const honestShares = shareOfTotalPct(nonZero);

  // Lift tiny shares + track the deficit.
  let borrowed = 0;
  const lifted = honestShares.map(p => {
    if (p > 0 && p < MIN_VISUAL_WIDTH_PCT) {
      borrowed += MIN_VISUAL_WIDTH_PCT - p;
      return MIN_VISUAL_WIDTH_PCT;
    }
    return p;
  });

  if (borrowed > 0) {
    // Subtract from the largest visible share. Index-of-max is stable
    // on ties (first-wins).
    let maxIdx = 0;
    for (let i = 1; i < lifted.length; i++) {
      if (lifted[i] > lifted[maxIdx]) maxIdx = i;
    }
    lifted[maxIdx] = Math.max(0, lifted[maxIdx] - borrowed);
  }

  // Accumulate x positions left-to-right.
  let cursor = 0;
  return nonZero.map((seg, i) => {
    const width = lifted[i];
    const projection: CompositionBarSegmentProjection = {
      id: seg.id,
      label: seg.label,
      value: seg.value,
      fill: seg.fill,
      swatch_role: seg.swatch_role,
      is_tail: seg.is_tail,
      x_pct: cursor,
      width_pct: width,
      share_pct: honestShares[i],
    };
    cursor += width;
    return projection;
  });
}

/**
 * Format a single segment for the legend / readout: `<label> — <value>
 * <unit> (<share>%)`. Shares are formatted to 1 decimal place; values
 * are passed through (the adapter is responsible for unit
 * conversion). Used only by the legend and the optional summary
 * helper, not by the bar itself.
 */
export function formatSegmentReadout(
  segment: CompositionBarSegment,
  share_pct: number,
  total_unit: string,
): string {
  const sharePart = `${share_pct.toFixed(1)}%`;
  return `${segment.label} — ${segment.value} ${total_unit} (${sharePart})`;
}

/**
 * Sum-check: assert the sum of segment values equals (or is close to)
 * `total_value`. Used by both the contract test on fixtures and at
 * adapter time to fail loud if the segments don't add up.
 *
 * Tolerance is absolute (0.5) because segment values are typically
 * integer seats or whole-number MW; allow 0.5 to absorb rounding in
 * the rare share-percent case.
 */
export function segmentsSumMatchesTotal(
  model: CompositionBarModel,
  tolerance: number = 0.5,
): boolean {
  const sum = totalSegmentValue(model.segments);
  return Math.abs(sum - model.total_value) <= tolerance;
}
