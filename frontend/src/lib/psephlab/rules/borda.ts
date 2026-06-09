// Borda Count simulator.
//
// Per Hans + Fowler round-2 verdict (2026-06-09). Borda is a positional
// rank-based system. Each voter ranks every candidate; the candidate at
// position i in a voter's ballot earns (N - i) points where N is the
// candidate count. Sum across all voters; highest total wins.
//
// India does not collect ranked ballots, so we PROXY each voter's
// ranking with the FPTP rank order within their constituency: every
// voter is assumed to share the AC-level FPTP rank order as their
// preference order. This is a strong assumption (see /docs/concepts/
// counting-methods/borda.md "The fascinating limit").
//
// Algorithm (state-wide):
//   1. Per AC: sort non-NOTA candidates by first-preference votes
//      descending. Candidate at position i (0-indexed) earns
//      (n - i) Borda points per voter in the AC; total Borda
//      points = (n - i) * voters_in_ac.
//      Actually we simplify: per AC the candidate at position i gets
//      (n - i) * total_ac_votes_for_non_nota Borda points.
//      EVEN SIMPLER: per AC, the candidate at position i contributes
//      (n - i) points to their party's state-wide Borda total
//      (one unit weight per AC).
//   2. Per party: sum Borda points across all ACs.
//   3. Allocate total_seats (= AC count) proportionally to party
//      Borda totals using Sainte-Lague divisors.
//   4. by_ac is empty (Borda is a state-wide PR-shaped rule under
//      our proxy).
//
// The "1 point per AC per rank" weighting (NOT vote-weighted) is the
// AC-equal-weighting assumption. Hans flagged this explicitly in his
// "Borda - The fascinating limit": small ACs and big ACs contribute
// the same Borda mass per candidate position, which biases the result
// toward parties that field candidates in many small ACs.

import type {
  AcOutcome,
  CountingRule,
  PartyResult,
  SeatAllocation,
  Tallies,
} from "../types";
import { assertSeatTallyInvariant } from "../../charts/count-seats";

interface BordaAggregate {
  party_eci_code: string;
  party_short: string;
  borda_points: number;
  votes: number;
  party_id: string;
  brand_colour_hex: string | null;
  brand_colour_confidence: "high" | "medium" | "low" | null;
  election_symbol_asset_path: string | null;
}

export const borda: CountingRule = {
  id: "borda",
  label: "Borda Count (rank-based scoring)",
  short_label: "Borda Count",
  headline: "Rank-based scoring - every position earns points.",
  validity: "medium_validity",
  requires_banner: true,
  caveat:
    "We assign each candidate Borda points based on their FPTP-rank in " +
    "their constituency: the top vote-getter earns N points, the second " +
    "earns N-1, and so on. Sum across the state, then allocate seats " +
    "proportionally to total Borda points. The Borda rule rewards broad " +
    "acceptability over plurality strength. Watch where Borda DIVERGES " +
    "from FPTP - those are the seats where candidates who finish second " +
    "or third everywhere gain from the points geometry. Borda is " +
    "mathematically clean; the assumption that voters' second " +
    "preferences match FPTP rank is the load-bearing one.",
  assumptions: [
    "Holds constant: ranks fixed to FPTP vote order within each AC.",
    "Holds constant: equal AC weighting (one rank-position unit per AC, regardless of electorate size).",
    "Holds constant: NOTA is excluded from the Borda calculation.",
    "Holds constant: state-wide allocation via Sainte-Lague divisors on party Borda totals.",
    "Reveals: how Borda's points geometry rewards broad acceptability versus FPTP's plurality strength.",
  ],

  apply(tallies: Tallies): SeatAllocation {
    const total_seats = tallies.acs.length;

    const aggs = new Map<string, BordaAggregate>();
    let total_votes = 0;

    // Track first-preference votes too so by_party.vote_share_pct
    // stays meaningful (mirrors FPTP shape).
    for (const ac of tallies.acs) {
      for (const c of ac.candidates) {
        total_votes += c.votes;
        if (c.party_eci_code === "NOTA") continue;
        const existing = aggs.get(c.party_eci_code);
        if (existing) {
          existing.votes += c.votes;
        } else {
          aggs.set(c.party_eci_code, {
            party_eci_code: c.party_eci_code,
            party_short: c.party_short,
            borda_points: 0,
            votes: c.votes,
            party_id: c.party_id,
            brand_colour_hex: c.brand_colour_hex ?? null,
            brand_colour_confidence: c.brand_colour_confidence ?? null,
            election_symbol_asset_path: c.election_symbol_asset_path ?? null,
          });
        }
      }
    }

    // Per-AC Borda: sort non-NOTA candidates by votes DESC, assign
    // points = (n - position) where n is the non-NOTA candidate count
    // in that AC. Add to the party aggregate.
    for (const ac of tallies.acs) {
      const non_nota = ac.candidates.filter((c) => c.party_eci_code !== "NOTA");
      const sorted = [...non_nota].sort(
        (a, b) =>
          b.votes - a.votes ||
          a.name.localeCompare(b.name) ||
          a.party_eci_code.localeCompare(b.party_eci_code),
      );
      const n = sorted.length;
      for (let i = 0; i < n; i++) {
        const points = n - i;
        const candidate = sorted[i];
        const agg = aggs.get(candidate.party_eci_code);
        if (agg) agg.borda_points += points;
      }
    }

    // Sainte-Lague allocation on Borda points. NOTA excluded by
    // construction (filtered above).
    const party_seats = new Map<string, number>();
    for (const code of aggs.keys()) party_seats.set(code, 0);

    for (let seat = 0; seat < total_seats; seat++) {
      let best_code: string | null = null;
      let best_quotient = -Infinity;
      for (const [code, agg] of aggs) {
        const divisor = 2 * (party_seats.get(code) ?? 0) + 1;
        const quotient = agg.borda_points / divisor;
        if (
          quotient > best_quotient ||
          (quotient === best_quotient &&
            (best_code === null ||
              agg.party_short < (aggs.get(best_code)?.party_short ?? "")))
        ) {
          best_code = code;
          best_quotient = quotient;
        }
      }
      if (best_code !== null) {
        party_seats.set(best_code, (party_seats.get(best_code) ?? 0) + 1);
      }
    }

    const by_party: PartyResult[] = [];
    for (const [code, agg] of aggs) {
      by_party.push({
        party_eci_code: code,
        party_short: agg.party_short,
        seats_won: party_seats.get(code) ?? 0,
        votes: agg.votes,
        vote_share_pct: total_votes === 0 ? 0 : (100 * agg.votes) / total_votes,
        party_id: agg.party_id,
        brand_colour_hex: agg.brand_colour_hex,
        brand_colour_confidence: agg.brand_colour_confidence,
        election_symbol_asset_path: agg.election_symbol_asset_path,
      });
    }
    by_party.sort(
      (a, b) =>
        b.seats_won - a.seats_won ||
        b.votes - a.votes ||
        a.party_short.localeCompare(b.party_short),
    );

    const by_ac: AcOutcome[] = [];

    if (by_party.length > 0 || total_seats === 0) {
      assertSeatTallyInvariant(
        {
          total_seats,
          parties: by_party.map((p) => ({
            party_id: p.party_id,
            seats_won: p.seats_won,
          })),
        },
        "psephlab:borda",
      );
    }

    return { by_party, by_ac, total_votes };
  },
};
