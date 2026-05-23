// Pure helpers for the small-multiples sparkline renderer.
//
// Doctrine ties:
//   - Phase 4 of the charting modernisation plan: sparkline must be
//     trajectory-honest. That requires (a) a SIGNED y-domain so
//     `-3.4 → -1.1` doesn't render as if it were `+3.4 → +1.1`, and
//     (b) a zero baseline when the domain straddles zero, so the
//     citizen can see negative values for what they are.
//   - R-08 BBA: helpers ship before the adopter so we can lock the
//     contract with pure tests.
//   - The current `IndicatorSmallMultiples.svelte` uses `Math.abs`
//     for both `y_max` and y-projection. That collapses sign — a
//     state that went from -50 to +50 looks like a state that went
//     from 50 to 50. These helpers replace that with proper signed
//     projection.

// ─── y-domain ──────────────────────────────────────────────────────

export interface YDomain {
  readonly min: number;
  readonly max: number;
  /** True when the domain straddles zero (renderer should draw a baseline). */
  readonly includes_zero: boolean;
}

/**
 * Compute the shared y-domain across all visible series.
 *
 *   - Missing / NaN values are skipped.
 *   - When all values are non-negative, `min = 0` so bars grow from
 *     the bottom (no truncated y-axis lying about magnitude).
 *   - When values straddle zero, `min` and `max` are the true bounds
 *     so the zero line falls inside the inner plot rect.
 *   - When all values are negative, `max = 0` so the citizen sees the
 *     trajectory pulling away from zero downward.
 *   - When no values exist, returns `{min: 0, max: 1, includes_zero: true}`
 *     (a sane default the renderer can render flat against).
 */
export function computeYDomain(
  series_values: readonly (number | null | undefined)[],
): YDomain {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  let saw_any = false;
  for (const v of series_values) {
    if (v === null || v === undefined || Number.isNaN(v)) continue;
    saw_any = true;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  if (!saw_any) return { min: 0, max: 1, includes_zero: true };
  // Anchor min to 0 when all values are non-negative (most indicators).
  if (min >= 0) min = 0;
  // Anchor max to 0 when all values are non-positive.
  if (max <= 0) max = 0;
  // Degenerate: all values were exactly 0.
  if (min === max) return { min: 0, max: 1, includes_zero: true };
  return { min, max, includes_zero: min <= 0 && max >= 0 };
}

// ─── projection ────────────────────────────────────────────────────

export interface SparkPoint {
  readonly time: string;
  readonly value: number;
}

export interface SparkProjection {
  readonly view_box_width: number;
  readonly view_box_height: number;
  readonly pad_x: number;
  readonly pad_y: number;
  readonly y_domain: YDomain;
  readonly time_axis: readonly string[];
}

/**
 * Project a value to a y-coordinate in the SVG viewBox.
 * `min` maps to the bottom of the inner rect, `max` to the top.
 * Honours signed domains.
 */
export function projectY(value: number, proj: SparkProjection): number {
  const inner_h = proj.view_box_height - 2 * proj.pad_y;
  const span = proj.y_domain.max - proj.y_domain.min;
  if (span <= 0) return proj.pad_y + inner_h;
  const frac = (value - proj.y_domain.min) / span;
  const clamped = Math.max(0, Math.min(1, frac));
  return proj.pad_y + inner_h - clamped * inner_h;
}

/**
 * Project a time index to an x-coordinate in the SVG viewBox.
 */
export function projectX(time: string, proj: SparkProjection): number | null {
  const inner_w = proj.view_box_width - 2 * proj.pad_x;
  const idx = proj.time_axis.indexOf(time);
  if (idx < 0) return null;
  const span = proj.time_axis.length - 1;
  if (span <= 0) return proj.pad_x + inner_w / 2;
  return proj.pad_x + (idx / span) * inner_w;
}

/**
 * Build an SVG path-d string for the supplied series, segmenting
 * across missing values (each contiguous run of present points
 * becomes its own M..L subpath).
 *
 * Returns `""` when the projection has fewer than 2 time slots or
 * no present points.
 */
export function pathForSeries(
  series: readonly SparkPoint[],
  proj: SparkProjection,
): string {
  if (series.length === 0 || proj.time_axis.length < 2) return "";
  const out: string[] = [];
  let on_segment = false;
  for (const p of series) {
    if (p.value === null || p.value === undefined || Number.isNaN(p.value)) {
      on_segment = false;
      continue;
    }
    const x = projectX(p.time, proj);
    if (x === null) {
      on_segment = false;
      continue;
    }
    const y = projectY(p.value, proj);
    out.push(`${on_segment ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`);
    on_segment = true;
  }
  return out.join(" ");
}

/**
 * Project the latest present point in the series for the end-of-line
 * dot + chip. Returns `null` when no present points exist.
 */
export function latestDot(
  series: readonly SparkPoint[],
  proj: SparkProjection,
): { readonly cx: number; readonly cy: number; readonly value: number; readonly time: string } | null {
  for (let i = series.length - 1; i >= 0; i--) {
    const p = series[i];
    if (p.value === null || p.value === undefined || Number.isNaN(p.value)) continue;
    const x = projectX(p.time, proj);
    if (x === null) continue;
    return { cx: x, cy: projectY(p.value, proj), value: p.value, time: p.time };
  }
  return null;
}

/**
 * Compute the x-coordinates for series-break dashed markers, given the
 * times at which the breaks occurred. Times that fall outside
 * `time_axis` are dropped.
 */
export function breakXs(
  break_times: readonly string[],
  proj: SparkProjection,
): readonly number[] {
  const out: number[] = [];
  for (const t of break_times) {
    const x = projectX(t, proj);
    if (x !== null) out.push(x);
  }
  return out;
}

/**
 * Compute the y-coordinate of the zero baseline within the inner plot
 * rect. Returns `null` when the domain does not straddle zero.
 */
export function zeroBaselineY(proj: SparkProjection): number | null {
  if (!proj.y_domain.includes_zero) return null;
  return projectY(0, proj);
}
