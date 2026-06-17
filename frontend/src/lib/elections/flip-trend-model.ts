/**
 * flip-trend-model: pure flip-count delta for the election-compare hero
 * strip (`CompareElections.svelte`, `/compare/elections/<state>/<from>/<to>`).
 *
 * PR5 of TODO/20260617-election-compare-ux-overhaul-plan.md answers the
 * citizen + Hans reading "is volatility rising?": on a page showing
 * From=N-1 vs To=N, surface whether flipping went UP or DOWN versus the
 * PREVIOUS transition (N-2 -> N-1). The component loads ONE extra event
 * (the same-body event immediately before `from`) and feeds the three
 * winner sets here.
 *
 * Extracted as a pure `.ts` model so the flip math is vitest-tested in the
 * node env WITHOUT mounting Svelte (the frontend vitest run has no jsdom).
 * The Svelte component stays a thin template that calls `computeFlipTrend`
 * from a `$derived`.
 *
 * Comparability (Hans caveat): seat sets shift across delimitation breaks,
 * so a pair's flips are counted ONLY on seats present in BOTH events of
 * that pair. A seat with an unknown (null) winner party on either side is
 * non-comparable - it is excluded from BOTH the comparable-seat base AND
 * the flip count (we cannot tell whether such a seat flipped).
 *
 * Pure: same inputs -> same output. No I/O, no Svelte import, no loader
 * import, no shared mutable state.
 */

/** Minimal per-seat winner shape this model reads (one row per entity). */
export interface FlipTrendWinner {
  entity_id: string;
  party_id: string | null;
}

/** Flip-trend result for the Flips KPI delta pill. */
export interface FlipTrend {
  /** Flips for the CURRENT transition (from -> to), comparable seats only. */
  flips_this: number;
  /** Flips for the PRIOR transition (prevPrev -> from), comparable seats only. */
  flips_prior: number;
  /** flips_this - flips_prior. Positive = more seats flipped this time. */
  delta: number;
  /** Comparable-seat base for the current pair (intersection with both
   *  sides' winner party known). */
  comparable_this: number;
  /** Comparable-seat base for the prior pair. */
  comparable_prior: number;
}

/**
 * Count flips for one ordered pair of winner sets.
 *
 * A seat counts toward `comparable` when its entity_id is present in BOTH
 * sets AND both sides carry a non-null winner party (otherwise the seat is
 * non-comparable and excluded). Of the comparable seats, those whose
 * winner party differs are `flips`.
 */
function countPairFlips(
  earlier: readonly FlipTrendWinner[],
  later: readonly FlipTrendWinner[],
): { flips: number; comparable: number } {
  const later_party_by_entity = new Map<string, string | null>();
  for (const w of later) later_party_by_entity.set(w.entity_id, w.party_id);

  let flips = 0;
  let comparable = 0;
  for (const w of earlier) {
    if (!later_party_by_entity.has(w.entity_id)) continue; // not in intersection
    const earlier_party = w.party_id;
    const later_party = later_party_by_entity.get(w.entity_id) ?? null;
    // Null party on either side -> non-comparable; skip entirely.
    if (earlier_party === null || later_party === null) continue;
    comparable++;
    if (earlier_party !== later_party) flips++;
  }
  return { flips, comparable };
}

/**
 * Compute the flip-trend delta over three winner sets.
 *
 * @param prevPrevWinners winners of the event before `from` (N-2). Empty
 *                        when there is no prior event - the prior pair then
 *                        has zero comparable seats and zero flips.
 * @param fromWinners     winners of the `from` event (N-1).
 * @param toWinners       winners of the `to` event (N).
 */
export function computeFlipTrend({
  prevPrevWinners,
  fromWinners,
  toWinners,
}: {
  prevPrevWinners: readonly FlipTrendWinner[];
  fromWinners: readonly FlipTrendWinner[];
  toWinners: readonly FlipTrendWinner[];
}): FlipTrend {
  const current = countPairFlips(fromWinners, toWinners);
  const prior = countPairFlips(prevPrevWinners, fromWinners);
  return {
    flips_this: current.flips,
    flips_prior: prior.flips,
    delta: current.flips - prior.flips,
    comparable_this: current.comparable,
    comparable_prior: prior.comparable,
  };
}
