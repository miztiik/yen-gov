// Proportional representation using the Sainte-Lague divisor method.
//
// Per parent plan section 25.6b-seam + override sub-plan
// `TODO/20260608-e6-user-override-and-pl2-pl3-execution-subplan.md`.
//
// State-wide aggregation of votes; divisor sequence 1, 3, 5, 7, 9, ...
// Seats allocated iteratively to the party with the highest quotient at
// each step. This is a pedagogical illustration of PR on the same ballots
// cast under FPTP, NOT a prediction of real-world PR outcomes (voters
// strategise to the system).
//
// NOTA is excluded from the divisor calculation (cannot translate to a
// seat). by_ac is intentionally empty because PR does not bind to
// per-constituency outcomes; the host renderer treats the empty array as
// "this method does not allocate per-AC" and surfaces a note.

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
}

export const sainteLague: CountingRule = {
  id: "proportional",
  label: "Proportional (Sainte-Lague, state-wide)",
  requires_banner: true,
  caveat:
    "Indian Lok Sabha and Vidhan Sabha elections use First-Past-The-Post, " +
    "not Proportional Representation. This re-allocation takes the SAME " +
    "ballots cast in this election and distributes seats by the " +
    "Sainte-Lague divisor method (divisors 1, 3, 5, 7, ...) using " +
    "state-wide party vote totals. The result is a MECHANICAL " +
    "illustration of the difference between FPTP and PR - NOT a " +
    "prediction of how voters would vote under a different system.",
  assumptions: [
    "Voters cast the same ballots under PR as under FPTP (unrealistic - real voters strategise to the system).",
    "NOTA votes are excluded from the divisor calculation (they cannot translate to a seat).",
    "Seats are not distributed per-AC; PR allocates state-wide totals.",
    "Number of seats to allocate = number of ACs in the tally.",
  ],

  apply(tallies: Tallies): SeatAllocation {
    const total_seats = tallies.acs.length;

    // Aggregate per-party state-wide totals, excluding NOTA. The
    // candidate's party_id + brand metadata is taken from the first row
    // seen (every row for a given party_eci_code carries the same
    // dim_parties JOIN payload).
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
          });
        }
      }
    }

    // Sainte-Lague: iterative seat allocation. Each round, the party with
    // the highest quotient (votes / next_divisor) wins one seat. Divisor
    // sequence: 1, 3, 5, 7, ... -> the per-party next divisor is
    // (2 * seats_awarded_so_far) + 1.
    const party_seats = new Map<string, number>();
    for (const code of party_votes.keys()) party_seats.set(code, 0);

    for (let seat = 0; seat < total_seats; seat++) {
      let best_code: string | null = null;
      let best_quotient = -Infinity;
      for (const [code, agg] of party_votes) {
        const divisor = 2 * (party_seats.get(code) ?? 0) + 1;
        const quotient = agg.votes / divisor;
        if (
          quotient > best_quotient ||
          (quotient === best_quotient &&
            (best_code === null || agg.party_short < (party_votes.get(best_code)?.party_short ?? "")))
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
      });
    }
    by_party.sort(
      (a, b) =>
        b.seats_won - a.seats_won ||
        b.votes - a.votes ||
        a.party_short.localeCompare(b.party_short),
    );

    const by_ac: AcOutcome[] = [];

    assertSeatTallyInvariant(
      {
        total_seats,
        parties: by_party.map((p) => ({
          party_id: p.party_id,
          seats_won: p.seats_won,
        })),
      },
      "psephlab:sainteLague",
    );

    return { by_party, by_ac, total_votes };
  },
};
