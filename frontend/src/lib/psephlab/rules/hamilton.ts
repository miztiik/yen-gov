// Proportional representation using the Hare quota + Largest Remainder
// (Hamilton) method.
//
// Per Hans + Fowler round-2 verdict (2026-06-09 debate). Hamilton is
// the "natural" PR method - each party's exact seat share is the
// integer part of (vote_share x total_seats). Remaining seats go to
// the parties with the largest fractional remainders.
//
// Mathematically simple but susceptible to two well-known paradoxes
// (Alabama paradox, where increasing total seats can DECREASE a
// party's seats; Population paradox, where a party gaining vote share
// can lose a seat). Both surface as "fascinating limit" sections in
// the /docs/concepts/counting-methods/hamilton.md long-form.
//
// Used in many Latin American PR systems + Russia's federal-list tier.
// Provides the third reference point alongside Sainte-Lague (most
// small-party-friendly) and D'Hondt (most large-party-friendly).

import type {
  AcOutcome,
  CountingRule,
  PartyResult,
  SeatAllocation,
  Tallies,
} from "../types";
import { assertSeatTallyInvariant } from "../../charts/count-seats";

interface PartyAggregate {
  party_eci_code: string;
  party_short: string;
  votes: number;
  party_id: string;
  brand_colour_hex: string | null;
  brand_colour_confidence: "high" | "medium" | "low" | null;
  election_symbol_asset_path: string | null;
}

export const hamilton: CountingRule = {
  id: "proportional-hamilton",
  label: "Largest Remainder PR (Hamilton)",
  short_label: "Largest Remainder PR",
  headline: "Whole-seat shares first, then leftovers settle the remainder.",
  validity: "fully_workable",
  requires_banner: true,
  caveat:
    "Each party's exact seat share is the integer part of " +
    "(vote-share x total-seats). Whatever seats remain go to the parties " +
    "with the largest fractional remainders. The arithmetic is the " +
    "simplest of the PR rules - one division per party - and the result " +
    "is the easiest to explain to a citizen. Watch how it sits between " +
    "Sainte-Lague and D'Hondt: a small party with a 0.51 remainder can " +
    "shed a half-seat off a larger party, surfacing fringes in a way " +
    "D'Hondt smooths over.",
  assumptions: [
    "Holds constant: ballots cast remain as cast.",
    "Holds constant: state-wide pool; no multi-member districts.",
    "Holds constant: Hare quota (total votes / total seats) with integer-first allocation.",
    "NOTA is excluded from the quota calculation - it cannot translate to a seat.",
    "Reveals: where small parties on the cusp of viability would land if remainders mattered.",
  ],

  apply(tallies: Tallies): SeatAllocation {
    const total_seats = tallies.acs.length;

    // Aggregate per-party state-wide totals, excluding NOTA.
    const party_votes = new Map<string, PartyAggregate>();
    let total_votes = 0;
    let total_votes_non_nota = 0;

    for (const ac of tallies.acs) {
      for (const c of ac.candidates) {
        total_votes += c.votes;
        if (c.party_eci_code === "NOTA") continue;
        total_votes_non_nota += c.votes;
        const existing = party_votes.get(c.party_eci_code);
        if (existing) {
          existing.votes += c.votes;
        } else {
          party_votes.set(c.party_eci_code, {
            party_eci_code: c.party_eci_code,
            party_short: c.party_short,
            votes: c.votes,
            party_id: c.party_id,
            brand_colour_hex: c.brand_colour_hex ?? null,
            brand_colour_confidence: c.brand_colour_confidence ?? null,
            election_symbol_asset_path: c.election_symbol_asset_path ?? null,
          });
        }
      }
    }

    const party_seats = new Map<string, number>();
    for (const code of party_votes.keys()) party_seats.set(code, 0);

    if (total_seats > 0 && total_votes_non_nota > 0) {
      // Hare quota = total_votes_non_nota / total_seats. Each party's
      // exact seat share is votes / quota = (votes * total_seats /
      // total_votes_non_nota).
      const quota = total_votes_non_nota / total_seats;

      interface RemainderEntry {
        party_eci_code: string;
        remainder: number;
        votes: number;
        party_short: string;
      }
      const remainders: RemainderEntry[] = [];
      let allocated = 0;

      for (const [code, agg] of party_votes) {
        const exact = agg.votes / quota;
        const whole = Math.floor(exact);
        party_seats.set(code, whole);
        allocated += whole;
        remainders.push({
          party_eci_code: code,
          remainder: exact - whole,
          votes: agg.votes,
          party_short: agg.party_short,
        });
      }

      // Allocate the remaining seats to the largest fractional remainders.
      // Tie-breakers: higher total votes ASC; party_short ASC. Deterministic.
      remainders.sort(
        (a, b) =>
          b.remainder - a.remainder ||
          b.votes - a.votes ||
          a.party_short.localeCompare(b.party_short),
      );
      const remaining = total_seats - allocated;
      for (let i = 0; i < remaining && i < remainders.length; i++) {
        const entry = remainders[i];
        party_seats.set(
          entry.party_eci_code,
          (party_seats.get(entry.party_eci_code) ?? 0) + 1,
        );
      }
    }

    const by_party: PartyResult[] = [];
    for (const [code, agg] of party_votes) {
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

    // Skip the seat-tally invariant when there are zero non-NOTA parties
    // to allocate to (degenerate NOTA-only AC case). See dhondt.ts for
    // the parallel comment.
    if (by_party.length > 0 || total_seats === 0) {
      assertSeatTallyInvariant(
        {
          total_seats,
          parties: by_party.map((p) => ({
            party_id: p.party_id,
            seats_won: p.seats_won,
          })),
        },
        "psephlab:hamilton",
      );
    }

    return { by_party, by_ac, total_votes };
  },
};
