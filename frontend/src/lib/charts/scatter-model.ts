// Pure derivation for Scatter.svelte (PR-W4c, 2026-06-10).
//
// Per TODO/20260609-election-experience-overhaul-plan.md PR-W4c row +
// Max verdict. Extracted from the Svelte component for the W4a-precedent
// reason: vitest runs in node-env and mounting Svelte components needs
// jsdom + @testing-library/svelte, which the project intentionally does
// not install. The 4 brief tests (dot count, sqrt-correct radius, click
// dispatch, filter narrowing) all reduce to pure functions over the
// `ScatterDatum` array; the Svelte component is a thin renderer over
// these helpers + d3-scale.
//
// One scatter datum = one constituency-election. The chart paints one
// dot per row:
//   - X    : turnout %        (0..100)
//   - Y    : margin %         (0..100)
//   - r    : sqrt(margin_votes) (TODO/20260612 Row B: swapped from
//                              electors so the dot encodes "how
//                              decisively was this seat won" - a 3k-vote
//                              squeaker looks tiny next to a 4 lakh-vote
//                              walkover, even when both have the same %
//                              margin. Citizen + Max verdict; OWID
//                              Rosling area-proportional convention
//                              preserved.)
//   - fill : winning party    (resolved by getPartyColor at render time)
//
// All filter narrowing happens here; the component subscribes to the
// reactive output and re-renders. The 6 filter dimensions match the
// plan-doc Max verdict baked into the PR-W4c brief.

/** One constituency-election point on the scatter. */
export interface ScatterDatum {
  /** Canonical entity_id (e.g. `IN-PC-2008-andhra-pradesh-411`). */
  entity_id: string;
  /** LGD state slug for URL construction (e.g. `tamil-nadu`). */
  state_slug: string;
  /** URL-safe constituency name slug (e.g. `mylapore`). */
  constituency_slug: string;
  /** Human-readable constituency name for tooltip / a11y. */
  constituency_name: string;
  /** Event id (e.g. `general-2024`). */
  event_id: string;
  /** Voter turnout as a percentage (0..100). */
  turnout_pct: number;
  /** Winning margin as a percentage of votes polled (0..100). */
  margin_pct: number;
  /** Registered electors (raw count). Carried for tooltip / future
   *  re-encoding; no longer drives the dot radius after TODO/20260612
   *  Row B swapped the encoding to `margin_votes`. */
  electors: number;
  /** Absolute winner-runnerup vote gap. Drives the dot radius via the
   *  Rosling-style sqrt-area scaling (TODO/20260612 Row B). Nullable
   *  because the upstream summary.csv leaves it null for uncontested
   *  seats; the component clamps null to 0 for layout purposes and the
   *  tooltip renders "-" instead of a number. */
  margin_votes: number | null;
  /** Winning party taxonomy id (e.g. `parties.IN.BJP`). */
  winner_party_id: string;
  /** Display short_name for the winning party (tooltip + filter chips). */
  winner_party_short: string;
  /** SC / ST reservation status, or `GEN` for unreserved. The W2b loader
   *  projects this from `entities/electoral.csv.reservation` (NULL maps to
   *  `GEN`). The on-disk column is empty for all rows today; SC/ST filter
   *  chips therefore narrow to zero rows until a future PR backfills the
   *  column. Documented as a known limitation in the PR-W4c body. */
  reservation: "GEN" | "SC" | "ST";
  /** `parliament` for PC-grain rows, `assembly` for AC-grain. Derived
   *  from the event-id prefix at projection time. */
  body: "parliament" | "assembly";
}

/** Filter state for the 6 chart filters. `undefined` and `"all"` both
 *  mean no narrowing on that axis; the explicit `"all"` literal is
 *  carried so the UI can render a sticky pill that stays highlighted. */
export interface ScatterFilters {
  /** Event id; narrows to one event when set. Defaults to "all events". */
  event?: string;
  /** State slug; narrows to one state when set. */
  state?: string;
  /** Party taxonomy id; greys out non-matching dots when set
   *  (NOT a filter — handled in the renderer, exposed here for future
   *  use). Today the chip flips a render style; rows are not dropped. */
  highlight_party?: string;
  reservation?: "all" | "GEN" | "SC" | "ST";
  body?: "all" | "parliament" | "assembly";
  margin_band?: "all" | "lt2" | "2to5" | "5to10" | "gt10";
}

/** Discrete margin-of-victory bands per Max verdict. */
export type MarginBand = "lt2" | "2to5" | "5to10" | "gt10";

/** Bin a margin_pct into one of the four canonical bands. */
export function marginBandOf(margin_pct: number): MarginBand {
  if (margin_pct < 2) return "lt2";
  if (margin_pct < 5) return "2to5";
  if (margin_pct < 10) return "5to10";
  return "gt10";
}

/** Apply the 6-filter contract over an array of rows. Pure (input is
 *  `readonly`, output is a fresh array). Stable order — the renderer
 *  paints in caller-supplied order so larger PCs sit behind smaller
 *  ACs only when the caller pre-sorts. */
export function applyFilters(
  data: readonly ScatterDatum[],
  filters: ScatterFilters,
): ScatterDatum[] {
  return data.filter((d) => {
    if (filters.event && d.event_id !== filters.event) return false;
    if (filters.state && d.state_slug !== filters.state) return false;
    if (
      filters.reservation &&
      filters.reservation !== "all" &&
      d.reservation !== filters.reservation
    ) {
      return false;
    }
    if (filters.body && filters.body !== "all" && d.body !== filters.body) {
      return false;
    }
    if (
      filters.margin_band &&
      filters.margin_band !== "all" &&
      marginBandOf(d.margin_pct) !== filters.margin_band
    ) {
      return false;
    }
    return true;
  });
}

/** Rosling-precedent radius for a single dot. Pure: same inputs ->
 *  same output, no shared state. `electors` and `max_electors` are
 *  raw counts; `max_r` is the radius in pixels assigned to the largest
 *  dot in the chart.
 *
 *  Visual AREA is proportional to `electors` (radius scales as
 *  sqrt(value)). Two PCs whose electors differ by 4x produce dots
 *  whose RADII differ by 2x and whose AREAS differ by 4x — matches
 *  OWID's bubble convention.
 *
 *  The component clamps the rendered radius to a small floor (so a
 *  PC of 100k electors is still visible) but the model returns the
 *  pure sqrt-scaled value so tests can assert the ratio exactly. */
export function sqrtRadius(
  electors: number,
  max_electors: number,
  max_r: number = 22,
): number {
  if (max_electors <= 0) return 0;
  const v = Math.max(0, electors);
  return max_r * Math.sqrt(v / max_electors);
}

/** Largest `electors` value in a row set. Convenience helper so the
 *  caller does not have to inline the same reduce on every render. */
export function maxElectors(data: readonly ScatterDatum[]): number {
  let m = 0;
  for (const d of data) {
    if (d.electors > m) m = d.electors;
  }
  return m;
}

/** Largest non-null `margin_votes` value in a row set. Drives the
 *  scatter chart's r-scale domain after the TODO/20260612 Row B
 *  encoding swap. Returns 0 when every row is null / negative. */
export function maxMarginVotes(data: readonly ScatterDatum[]): number {
  let m = 0;
  for (const d of data) {
    const v = d.margin_votes;
    if (v != null && v > m) m = v;
  }
  return m;
}

/** Compute the Y-axis upper bound for the scatter chart per the
 *  TODO/20260612 Row A spec.
 *
 *  Returns `max(40, ceil(1.1 * max_margin_pct / 10) * 10)`, capped at
 *  100. Empty input -> 40 (Rosling axiom: never collapse the chart to
 *  zero range). The result is always a multiple of 10 so tick rendering
 *  stays clean.
 *
 *  Pure: same input -> same output, no shared state. */
export function computeYMax(filtered: readonly ScatterDatum[]): number {
  const FLOOR = 40;
  if (filtered.length === 0) return FLOOR;
  let max = 0;
  for (const d of filtered) {
    if (d.margin_pct > max) max = d.margin_pct;
  }
  if (max <= 0) return FLOOR;
  const candidate = Math.ceil((max * 1.1) / 10) * 10;
  return Math.min(100, Math.max(FLOOR, candidate));
}
