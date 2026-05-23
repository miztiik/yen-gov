// Phase 3 — Ranked comparison polish helpers.
//
// Pure helpers consumed by IndicatorRanked.svelte and any future
// ranked-comparison renderer.
//
// Doctrine:
//
//   - Plan §3 task: "Add a median marker or peer-band marker to the
//     inline bar area."
//
//   - Plan §3 task: "When compare state is selected, show a
//     plain-language gap line: 'Tamil Nadu is X above/below Karnataka'
//     with direction-aware wording."
//
//   - Plan §3 honesty rule: "Preserve existing honesty rule: suppress
//     rank when comparability: not_comparable_across_states."
//
//   - R-08 BBA: pure helpers; renderers feed their domain values.
//
//   - CLAUDE.md §10: closed-enum `IndicatorDirection`,
//     `PeerBandKind`, `BadgeKind`.

/**
 * Indicator direction — used to pick gap wording.
 *
 *   - `higher_is_better`: literacy, GSDP per capita, vaccine coverage.
 *   - `lower_is_better`:  IMR, NPL ratio, unemployment rate.
 *   - `neutral`:          population, area — direction has no goodness.
 */
export type IndicatorDirection =
  | "higher_is_better"
  | "lower_is_better"
  | "neutral";

/** What to show as the peer-band marker on the inline bar. */
export type PeerBandKind = "median" | "iqr" | "p10_p90";

/** Result of `computePeerBand` — values are absolute, not normalised. */
export interface PeerBand {
  readonly kind: PeerBandKind;
  /** Median value (always present when count > 0). */
  readonly median: number | null;
  /** Lower band edge (p25 for iqr, p10 for p10_p90, equal to median for median-only). */
  readonly lower: number | null;
  /** Upper band edge (p75 for iqr, p90 for p10_p90, equal to median for median-only). */
  readonly upper: number | null;
  /** Number of present (non-null) values used. */
  readonly count: number;
}

/**
 * Compute median / IQR / p10_p90 for an array of values (nulls ignored).
 *
 * Returns null edges when `kind === "median"` (lower / upper degenerate
 * to median for a single marker line).
 *
 * Pure. Stable. Empty input → all fields null with count 0.
 */
export function computePeerBand(
  values: ReadonlyArray<number | null | undefined>,
  kind: PeerBandKind = "median",
): PeerBand {
  // Filter nulls / undefineds / NaN.
  const present: number[] = [];
  for (const v of values) {
    if (v === null || v === undefined) continue;
    if (Number.isNaN(v)) continue;
    present.push(v);
  }
  if (present.length === 0) {
    return { kind, median: null, lower: null, upper: null, count: 0 };
  }
  // Sort ascending.
  const sorted = present.slice().sort((a, b) => a - b);
  const median = quantile(sorted, 0.5);
  if (kind === "median") {
    return { kind, median, lower: median, upper: median, count: sorted.length };
  }
  if (kind === "iqr") {
    return {
      kind,
      median,
      lower: quantile(sorted, 0.25),
      upper: quantile(sorted, 0.75),
      count: sorted.length,
    };
  }
  // p10_p90
  return {
    kind,
    median,
    lower: quantile(sorted, 0.10),
    upper: quantile(sorted, 0.90),
    count: sorted.length,
  };
}

/**
 * Linear-interpolation quantile (matches numpy's "linear" interpolation
 * convention — the most common one in citizen-data work). Sorted input
 * required; q in [0, 1]. Always returns a number for non-empty input.
 */
function quantile(sorted: readonly number[], q: number): number {
  if (sorted.length === 1) return sorted[0];
  const idx = (sorted.length - 1) * q;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  const frac = idx - lo;
  return sorted[lo] + (sorted[hi] - sorted[lo]) * frac;
}

// ─── gap wording ───────────────────────────────────────────────────

/**
 * Where the marker sits relative to the bar in the visible plot domain.
 * Renderers use this to compute the x-coordinate. `pct_of_max` is the
 * marker's value as a fraction of the BAR-AREA max (the same max used
 * to draw bars), clamped to [0, 1].
 */
export interface PeerBandMarker {
  readonly kind: PeerBandKind;
  readonly median: number | null;
  readonly lower: number | null;
  readonly upper: number | null;
  readonly count: number;
  /** Median / band edges as fractions of `max_abs_value`, clamped 0..1. */
  readonly median_pct_of_max: number | null;
  readonly lower_pct_of_max: number | null;
  readonly upper_pct_of_max: number | null;
}

/**
 * Project a `PeerBand` onto a marker view-model relative to a known
 * bar-area max. Pure; no DOM.
 */
export function projectPeerBandMarker(
  band: PeerBand,
  max_abs_value: number,
): PeerBandMarker {
  const clamp = (v: number | null): number | null => {
    if (v === null) return null;
    if (max_abs_value <= 0) return null;
    const pct = Math.abs(v) / max_abs_value;
    if (!Number.isFinite(pct)) return null;
    if (pct < 0) return 0;
    if (pct > 1) return 1;
    return pct;
  };
  return {
    kind: band.kind,
    median: band.median,
    lower: band.lower,
    upper: band.upper,
    count: band.count,
    median_pct_of_max: clamp(band.median),
    lower_pct_of_max: clamp(band.lower),
    upper_pct_of_max: clamp(band.upper),
  };
}

// ─── gap wording ───────────────────────────────────────────────────

/**
 * Citizen-facing gap line, computed from a home + compare pair.
 *
 *   - `gap`        — signed: `home_value - compare_value`.
 *   - `abs_gap`    — magnitude.
 *   - `direction`  — `"above"` / `"below"` / `"equal"` / `"missing"`.
 *   - `verdict`    — `"better"` / `"worse"` / `"equal"` / `"neutral"` /
 *                    `"missing"` per indicator direction.
 *   - `wording`    — plain-language sentence with the actual state names.
 *   - `formatted_gap` — the abs_gap formatted via the caller-supplied
 *                    formatter (e.g. `(v) => v.toFixed(1) + "%"`).
 */
export interface GapLine {
  readonly home_name: string;
  readonly compare_name: string;
  readonly home_value: number | null;
  readonly compare_value: number | null;
  readonly gap: number | null;
  readonly abs_gap: number | null;
  readonly direction: "above" | "below" | "equal" | "missing";
  readonly verdict: "better" | "worse" | "equal" | "neutral" | "missing";
  readonly formatted_gap: string;
  readonly wording: string;
}

export interface ComputeGapInput {
  readonly home_name: string;
  readonly home_value: number | null;
  readonly compare_name: string;
  readonly compare_value: number | null;
  readonly direction: IndicatorDirection;
  /** Formatter for the absolute gap magnitude. */
  readonly format_gap: (v: number) => string;
}

/**
 * Compose a citizen-facing gap line. Pure; no DOM, no global state.
 *
 * Wording rules:
 *
 *   - Missing endpoint → "No data to compare {home} with {compare}."
 *   - equal             → "{home} matches {compare}."
 *   - above + better    → "{home} is {Δ} above {compare}."
 *   - above + worse     → "{home} is {Δ} above {compare}." (no goodness verbs)
 *   - above + neutral   → "{home} is {Δ} above {compare}."
 *   - below mirrors above with "below".
 *
 * Honesty: the gap line NEVER calls a state "better" or "worse"
 * directly in the wording — direction is encoded in the `verdict`
 * field for the renderer to badge separately. This preserves the
 * Phase 3 rule "preserve existing honesty rule".
 */
export function computeGapLine(input: ComputeGapInput): GapLine {
  const hv = input.home_value;
  const cv = input.compare_value;
  const isMissing
    = hv === null
      || cv === null
      || hv === undefined
      || cv === undefined
      || Number.isNaN(hv)
      || Number.isNaN(cv);
  if (isMissing) {
    return {
      home_name: input.home_name,
      compare_name: input.compare_name,
      home_value: hv ?? null,
      compare_value: cv ?? null,
      gap: null,
      abs_gap: null,
      direction: "missing",
      verdict: "missing",
      formatted_gap: "",
      wording: `No data to compare ${input.home_name} with ${input.compare_name}.`,
    };
  }
  const gap = (hv as number) - (cv as number);
  const abs_gap = Math.abs(gap);
  const formatted_gap = input.format_gap(abs_gap);
  let direction: GapLine["direction"];
  if (gap > 0) direction = "above";
  else if (gap < 0) direction = "below";
  else direction = "equal";
  let verdict: GapLine["verdict"];
  if (direction === "equal") verdict = "equal";
  else if (input.direction === "neutral") verdict = "neutral";
  else if (
    (direction === "above" && input.direction === "higher_is_better")
    || (direction === "below" && input.direction === "lower_is_better")
  )
    verdict = "better";
  else verdict = "worse";
  let wording: string;
  if (direction === "equal") {
    wording = `${input.home_name} matches ${input.compare_name}.`;
  } else if (direction === "above") {
    wording = `${input.home_name} is ${formatted_gap} above ${input.compare_name}.`;
  } else {
    wording = `${input.home_name} is ${formatted_gap} below ${input.compare_name}.`;
  }
  return {
    home_name: input.home_name,
    compare_name: input.compare_name,
    home_value: hv as number,
    compare_value: cv as number,
    gap,
    abs_gap,
    direction,
    verdict,
    formatted_gap,
    wording,
  };
}
