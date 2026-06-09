// Method-preview helpers for the Election Studio MethodDrawer.
//
// Per Jony + Fowler convergence (ship-loop verdict, 2026-06-09):
// every drawer card carries a live preview of "what would happen
// under this rule" - top-3 parties by seats won, plus the chamber
// size when it grows past constituency count (MMP overhang).
//
// The drawer is the load-bearing teaching moment of the Election
// Studio: the citizen taps the pill, sees 12 outcomes side-by-side,
// and picks one. Without the preview the drawer is a fancy dropdown
// (Fowler verdict 1).
//
// Compute timing: all 12 previews compute ONCE when Tallies loads,
// memoised in a $derived on Psephlab.svelte. Drawer-open never
// triggers compute - the previews are precomputed so the drawer
// animates without input lag (Jony verdict; Fowler perf budget).
//
// Engine call shape: `rule.apply(tallies)` directly, NOT
// `engine.run(tallies, scenarioWithRule(id))`. The drawer needs ONLY
// the unmutated baseline; bypassing run() saves the mutation pipeline
// + the duplicate baseline pass (Fowler verdict 2).
//
// Sandbox-fence preservation: this module never calls
// `count-seats.ts::countSeats()` (the renderer-facing seam that
// throws for non-FPTP from non-Psephlab callers). It calls
// `rule.apply()` directly (the engine seam, Psephlab-internal). The
// fence is unchanged (Fowler verdict 4).

import type { CountingRule, SeatAllocation, Tallies } from "./types";

/** One row in the preview's top-N party list. */
export interface PreviewItem {
  /** ECI party short label (e.g. "DMK", "AIADMK"). */
  party_short: string;
  /** Canonical taxonomy id (e.g. "parties.IN.DMK"). Threaded through
   *  for future 3-tier brand-colour resolution; the drawer renders
   *  monochrome today (Jony verdict). */
  party_id: string;
  /** Seats won under the rule's allocation. */
  seats: number;
  /** Brand colour hex from dim_parties (optional; null for sentinels
   *  + uncurated parties). Threaded through for the same reason as
   *  party_id. */
  hex: string | null;
}

/** Per-method preview payload rendered on each drawer card. */
export interface PreviewInfo {
  /** Top parties by seats_won DESC. At most `top_n` entries; drops
   *  parties with `seats_won === 0`. */
  top: ReadonlyArray<PreviewItem>;
  /** Effective chamber size for this rule. For most rules this equals
   *  the constituency count (`tallies.acs.length`); MMP grows past
   *  the constituency count via overhang compensation
   *  (`allocation.chamber_seats > tallies.acs.length`). */
  chamber: number;
}

/** Default top-N for the drawer preview line. Three parties fits one
 *  line on a 360px viewport for the median Indian state (per Jony
 *  mobile-constraint verdict). */
export const PREVIEW_TOP_N = 3;

/** Build a PreviewInfo from a SeatAllocation. Pure; safe to call on
 *  every render (the caller memoises). */
export function buildPreview(
  allocation: SeatAllocation,
  total_acs: number,
  top_n: number = PREVIEW_TOP_N,
): PreviewInfo {
  const top: PreviewItem[] = [];
  // by_party is already sorted by seats_won DESC, votes DESC,
  // party_short ASC (every rule does this before returning - see
  // fptp.ts / sainteLague.ts / etc.). Filter zero-seat parties then
  // take the first top_n.
  for (const p of allocation.by_party) {
    if (p.seats_won <= 0) continue;
    top.push({
      party_short: p.party_short,
      party_id: p.party_id,
      seats: p.seats_won,
      hex: p.brand_colour_hex ?? null,
    });
    if (top.length >= top_n) break;
  }
  const chamber = allocation.chamber_seats ?? total_acs;
  return { top, chamber };
}

/** Build the per-rule preview map for the whole MethodDrawer.
 *
 * Returns `null` when `tallies` is null (the actuals are still
 * loading); the drawer renders cards without preview lines in that
 * arm. Returns an empty Map when `tallies` is non-null but the rule
 * list is empty (defensive; the registry is always non-empty in
 * practice).
 *
 * Per Fowler verdict: calls `rule.apply(tallies)` directly to skip
 * the unneeded mutation pipeline in `engine.run()`. */
export function buildMethodPreviews(
  tallies: Tallies | null,
  rules: ReadonlyArray<CountingRule>,
  top_n: number = PREVIEW_TOP_N,
): ReadonlyMap<string, PreviewInfo> | null {
  if (!tallies) return null;
  const out = new Map<string, PreviewInfo>();
  for (const rule of rules) {
    const allocation = rule.apply(tallies);
    out.set(rule.id, buildPreview(allocation, tallies.acs.length, top_n));
  }
  return out;
}

/** Format the preview's top-N parties as a one-line readable string.
 *  Per Jony verdict: "DMK 133 / AIADMK 66 / INC 18". The separator
 *  is ` / ` (space, slash, space) with the slash rendered in muted
 *  ink at render time. Returns the empty string when the preview is
 *  empty (the drawer hides the line in that arm). */
export function formatPreviewLine(preview: PreviewInfo): string {
  if (preview.top.length === 0) return "";
  return preview.top
    .map((p) => `${p.party_short} ${p.seats}`)
    .join(" / ");
}

/** Format the MMP chamber-growth suffix when the rule's chamber is
 *  larger than the constituency count. Returns an empty string when
 *  chamber equals constituency_seats (the dominant case). Per Jony
 *  verdict: " (234 -> 304)" with an ASCII arrow.
 *
 *  Surfaced as a separate helper so the drawer can render it in
 *  muted ink alongside the preview line. */
export function formatChamberSuffix(
  preview: PreviewInfo,
  constituency_seats: number,
): string {
  if (preview.chamber === constituency_seats) return "";
  return ` (${constituency_seats} -> ${preview.chamber})`;
}
