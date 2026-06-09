// Proportional representation using the D'Hondt divisor method.
//
// Per Hans + Fowler round-2 verdict (2026-06-09 debate). D'Hondt is the
// "first PR rule citizens encounter in academic discussions of FPTP
// reform" - it favours large parties more than Sainte-Lague because the
// divisor sequence is 1, 2, 3, ... versus Sainte-Lague's 1, 3, 5, 7, ...
//
// State-wide aggregation of votes; iterative seat allocation to the
// party with the highest quotient (votes / next_divisor). Per-party
// next divisor is `seats_awarded_so_far + 1`.
//
// NOTA is excluded from the divisor calculation (cannot translate to
// a seat). by_ac is empty (PR does not bind to per-constituency
// outcomes).
//
// Algorithm mirrors sainteLague.ts; the only difference is the divisor
// sequence. Fowler verdict: "90% copy of sainteLague.ts; divisor n+1
// instead of 2n+1."

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

export const dhondt: CountingRule = {
  id: "proportional-dhondt",
  label: "Proportional (D'Hondt, state pool)",
  short_label: "Proportional (D'Hondt)",
  headline: "Proportional, but the biggest party gets a quiet bonus.",
  validity: "fully_workable",
  requires_banner: true,
  caveat:
    "Same state-wide pool as Sainte-Lague, but the divisor sequence runs " +
    "1, 2, 3 instead of 1, 3, 5. Watch how a small switch in divisor " +
    "shifts seats from regional parties to the largest party - the " +
    "contrast is one of the cleanest demonstrations that no PR rule is " +
    "neutral on party size. Used in Belgium, Israel, the Netherlands, " +
    "and Spain.",
  assumptions: [
    "Holds constant: ballots cast remain as cast (real voters strategise to whichever system they vote under).",
    "Holds constant: state-wide pool; no multi-member districts.",
    "Holds constant: D'Hondt divisors (larger-party friendly versus Sainte-Lague).",
    "NOTA is excluded from the divisor calculation - it cannot translate to a seat.",
    "Reveals: how sensitive proportionality is to a single design choice no citizen ever sees on the ballot.",
  ],

  apply(tallies: Tallies): SeatAllocation {
    const total_seats = tallies.acs.length;

    const party_votes = new Map<string, PartyAggregate>();
    let total_votes = 0;

    for (const ac of tallies.acs) {
      for (const c of ac.candidates) {
        total_votes += c.votes;
        if (c.party_eci_code === "NOTA") continue;
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

    // D'Hondt: iterative seat allocation. Each round, the party with
    // the highest quotient (votes / next_divisor) wins one seat. Divisor
    // sequence: 1, 2, 3, 4, ... -> the per-party next divisor is
    // `seats_awarded_so_far + 1`.
    const party_seats = new Map<string, number>();
    for (const code of party_votes.keys()) party_seats.set(code, 0);

    for (let seat = 0; seat < total_seats; seat++) {
      let best_code: string | null = null;
      let best_quotient = -Infinity;
      for (const [code, agg] of party_votes) {
        const divisor = (party_seats.get(code) ?? 0) + 1;
        const quotient = agg.votes / divisor;
        if (
          quotient > best_quotient ||
          (quotient === best_quotient &&
            (best_code === null ||
              agg.party_short <
                (party_votes.get(best_code)?.party_short ?? "")))
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
    // to allocate to (degenerate NOTA-only AC case). The assertion's
    // contract is sum(seats_won) == total_seats; with zero allocatable
    // parties total_seats > 0 trivially violates it. The host UI shows
    // an empty seat panel; no party can be awarded a seat.
    if (by_party.length > 0 || total_seats === 0) {
      assertSeatTallyInvariant(
        {
          total_seats,
          parties: by_party.map((p) => ({
            party_id: p.party_id,
            seats_won: p.seats_won,
          })),
        },
        "psephlab:dhondt",
      );
    }

    return { by_party, by_ac, total_votes };
  },
};
