/**
 * compare-dot-summary: pure To-winner party-dot tally for the
 * election-compare table toolbar (`CompareElections.svelte`).
 *
 * Mirrors the state event page's winner-dot strip
 * (`StateEventConstituencyList.svelte`'s `dot_strip`) but anchored to the
 * compare surface per the plan-doc (section 3a of
 * TODO/20260617-election-compare-ux-overhaul-plan.md):
 *
 *   dots = the DISTINCT To-winner parties present in the CURRENT
 *   filtered + searched rows, ordered by frequency descending (most seats
 *   first), capped at 6, with a "+k" overflow count when more distinct
 *   parties exist. Orphan rows ("Boundary changed" / "New seat") have no
 *   stable To-party and are excluded from the tally - the same exclusion
 *   the flip / hold KPIs apply.
 *
 * Anchoring the dots to the To-winner column (not a fixed metric) makes
 * them self-adapt to the active filter: with Holds active they read as
 * "parties holding", with Flips active as "parties flipped to", with All
 * as the overall winner palette.
 *
 * Pure: the colour resolver is INJECTED as a parameter so this model does
 * not import `getPartyColor` (the route wires the real resolver; tests
 * stub it). Same inputs -> same output. No I/O, no shared mutable state.
 */

/** Maximum number of colour dots rendered before overflowing into "+k". */
export const MAX_COMPARE_DOTS = 6;

/**
 * Minimal structural shape this model reads. The route's full `CompareRow`
 * satisfies it without the model importing the route (structural typing).
 */
export interface CompareDotRow {
  to_party_id: string | null;
  is_orphan: boolean;
}

/** Ordered distinct To-winner dot colours + the overflow count. */
export interface CompareDotSummary {
  /** Up to `MAX_COMPARE_DOTS` resolved `#rrggbb` hex strings, most-seats
   *  first. Distinctness is by party_id (two parties that resolve to the
   *  same hex still occupy two dots). */
  dots: string[];
  /** Distinct To-winner parties beyond the cap; 0 when none overflow. */
  overflow: number;
}

/**
 * Build the To-winner party-dot summary over the current filtered rows.
 *
 * @param rows       the filtered + searched compare rows.
 * @param resolveHex injected colour resolver: party_id -> `#rrggbb`. The
 *                   route passes `(pid) => getPartyColor(pid, null).hex`.
 */
export function buildCompareDotSummary(
  rows: readonly CompareDotRow[],
  resolveHex: (party_id: string) => string,
): CompareDotSummary {
  // Tally To-winner party frequency, excluding orphans + null party ids.
  const counts = new Map<string, number>();
  for (const r of rows) {
    if (r.is_orphan) continue;
    const pid = r.to_party_id;
    if (!pid) continue;
    counts.set(pid, (counts.get(pid) ?? 0) + 1);
  }

  // Order by frequency descending; tie-break by party_id ascending so the
  // dot order is deterministic (and testable) under equal seat counts.
  const ordered = [...counts.entries()].sort((a, b) => {
    if (b[1] !== a[1]) return b[1] - a[1];
    return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0;
  });

  const dots = ordered
    .slice(0, MAX_COMPARE_DOTS)
    .map(([pid]) => resolveHex(pid));
  const overflow = Math.max(0, ordered.length - MAX_COMPARE_DOTS);
  return { dots, overflow };
}
