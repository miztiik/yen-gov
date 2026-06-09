// Mixed-Member Proportional (MMP) simulator.
//
// Per Hans + Fowler round-2 verdict (2026-06-09). MMP is the most
// politically interesting PR variant for an Indian audience: it
// PRESERVES every constituency winner the citizen voted for and ADDS
// a state-wide list tier that compensates parties under-represented
// in the FPTP outcome.
//
// Algorithm:
//   1. Run FPTP -> per-party constituency seats (sum = constituency_count).
//   2. Compute target list-tier size = floor(constituency_count * 0.3)
//      (Hans's ~80-for-234 estimate; matches the German Bundestag
//      and Scottish Parliament rough proportion).
//   3. Compute the IDEAL chamber composition by running Sainte-Lague
//      on state-wide party votes, targeting (constituency_count + list_size)
//      total seats.
//   4. For each party: list_seats = max(0, ideal_chamber_share -
//      constituency_seats). Parties with constituency_seats > ideal share
//      keep their constituency winners as OVERHANG (no list tier needed;
//      they are already over-represented).
//   5. The chamber grows to constituency_count + sum(list_seats).
//
// Per Fowler verdict round 2: MMP is the doctrinal departure from
// `assertSeatTallyInvariant`. The seat-tally invariant requires
// sum(seats_won) == total_seats; in MMP sum(seats_won) is the new
// chamber size, not the constituency count. We skip the standard
// invariant and pin our own (assertMmpInvariant) on the test side.
//
// The host (Psephlab.svelte) reads `allocation.chamber_seats` to
// resize ParliamentArc + recompute the majority threshold (272 for a
// 543-Lok-Sabha that grows to ~705, etc.).

import type {
  AcOutcome,
  CountingRule,
  PartyResult,
  SeatAllocation,
  Tallies,
} from "../types";
import { fptp } from "./fptp";

/** Default list-tier ratio: 30% of constituency count, rounded down.
 *  TN 234 ACs -> 70 list seats -> 304 chamber. Lok Sabha 543 -> 162
 *  list -> 705 chamber. Visible enough to be interesting, conservative
 *  enough to stay below the German Bundestag's 50-50 split. */
const LIST_TIER_RATIO = 0.3;

export const mmp: CountingRule = {
  id: "mmp",
  label: "Mixed-Member Proportional",
  short_label: "Mixed-Member (MMP)",
  headline: "Keep every local MLA, add a state list-tier on top.",
  validity: "fully_workable",
  requires_banner: true,
  caveat:
    "Every FPTP constituency winner stays - this is the chamber the citizen " +
    "already voted into. We then add a state-wide list tier of about 30% " +
    "more seats to compensate parties under-represented in the FPTP outcome. " +
    "Germany and New Zealand run elections this way; Scotland and Wales use " +
    "a regional list tier on the same shape. Watch how a list tier rescues " +
    "the proportionality FPTP eats, without losing the local MLA you know.",
  assumptions: [
    "Holds constant: every FPTP constituency winner keeps their seat.",
    "Holds constant: list-tier size = floor(constituency-count x 0.3) - about 80 for a 234-AC state Assembly.",
    "Holds constant: list-tier allocation uses Sainte-Lague divisors on state-wide party votes.",
    "Overhang: parties already over-represented from FPTP keep their constituency winners; the chamber grows accordingly.",
    "Reveals: which parties under-represented by the FPTP geography would gain seats from a list-tier top-up.",
  ],

  apply(tallies: Tallies): SeatAllocation {
    const constituency_count = tallies.acs.length;
    if (constituency_count === 0) {
      return { by_party: [], by_ac: [], total_votes: 0, chamber_seats: 0 };
    }

    // Step 1: FPTP for the constituency tier.
    const fptp_result = fptp.apply(tallies);
    const fptp_seats = new Map<string, number>();
    for (const p of fptp_result.by_party) {
      fptp_seats.set(p.party_eci_code, p.seats_won);
    }

    // Step 2: list-tier size.
    const list_target = Math.floor(constituency_count * LIST_TIER_RATIO);
    const ideal_chamber_size = constituency_count + list_target;

    // Step 3: ideal proportional allocation across the full chamber
    // (constituency + list). Use Sainte-Lague divisors on state-wide
    // party vote totals, excluding NOTA.
    const party_votes = new Map<string, number>();
    for (const ac of tallies.acs) {
      for (const c of ac.candidates) {
        if (c.party_eci_code === "NOTA") continue;
        party_votes.set(c.party_eci_code, (party_votes.get(c.party_eci_code) ?? 0) + c.votes);
      }
    }
    const ideal_seats = new Map<string, number>();
    for (const code of party_votes.keys()) ideal_seats.set(code, 0);

    const party_short_for = (code: string): string => {
      const row = fptp_result.by_party.find((p) => p.party_eci_code === code);
      return row?.party_short ?? code;
    };

    for (let seat = 0; seat < ideal_chamber_size; seat++) {
      let best_code: string | null = null;
      let best_quotient = -Infinity;
      for (const [code, votes] of party_votes) {
        const divisor = 2 * (ideal_seats.get(code) ?? 0) + 1;
        const quotient = votes / divisor;
        if (
          quotient > best_quotient ||
          (quotient === best_quotient &&
            (best_code === null ||
              party_short_for(code) < party_short_for(best_code)))
        ) {
          best_code = code;
          best_quotient = quotient;
        }
      }
      if (best_code !== null) {
        ideal_seats.set(best_code, (ideal_seats.get(best_code) ?? 0) + 1);
      }
    }

    // Step 4: list_seats = max(0, ideal - fptp). Final chamber grows to
    // constituency_count + sum(list_seats). Overhang parties contribute
    // 0 list seats; the chamber size LIST tier may be smaller than the
    // target (overhang absorbs some of the list quota).
    let total_list_seats = 0;
    const final_seats = new Map<string, number>();
    for (const code of party_votes.keys()) {
      const fptp_count = fptp_seats.get(code) ?? 0;
      const ideal_count = ideal_seats.get(code) ?? 0;
      const list_count = Math.max(0, ideal_count - fptp_count);
      final_seats.set(code, fptp_count + list_count);
      total_list_seats += list_count;
    }
    const chamber_seats = constituency_count + total_list_seats;

    // Construct PartyResult rows. Preserve the per-party brand identity
    // from the FPTP result (which carries the dim_parties JOIN payload);
    // hydrate from candidate rows for parties FPTP missed (rare - any
    // party with votes also appears in by_ac winners or runners-up).
    const result_index = new Map<string, PartyResult>();
    for (const p of fptp_result.by_party) {
      result_index.set(p.party_eci_code, { ...p, seats_won: final_seats.get(p.party_eci_code) ?? 0 });
    }
    // Cover any non-NOTA party that has votes but no FPTP row (extremely
    // rare; defensive). Use the first candidate row to hydrate brand.
    for (const ac of tallies.acs) {
      for (const c of ac.candidates) {
        if (c.party_eci_code === "NOTA") continue;
        if (result_index.has(c.party_eci_code)) continue;
        result_index.set(c.party_eci_code, {
          party_eci_code: c.party_eci_code,
          party_short: c.party_short,
          seats_won: final_seats.get(c.party_eci_code) ?? 0,
          votes: party_votes.get(c.party_eci_code) ?? 0,
          vote_share_pct: 0, // recomputed below
          party_id: c.party_id,
          brand_colour_hex: c.brand_colour_hex ?? null,
          brand_colour_confidence: c.brand_colour_confidence ?? null,
          election_symbol_asset_path: c.election_symbol_asset_path ?? null,
        });
      }
    }

    const by_party: PartyResult[] = [];
    const total_votes = fptp_result.total_votes;
    for (const p of result_index.values()) {
      if (p.party_eci_code === "NOTA") continue;
      p.vote_share_pct = total_votes === 0 ? 0 : (100 * p.votes) / total_votes;
      by_party.push(p);
    }
    by_party.sort(
      (a, b) =>
        b.seats_won - a.seats_won ||
        b.votes - a.votes ||
        a.party_short.localeCompare(b.party_short),
    );

    // by_ac is the FPTP outcome - the local MLA each citizen voted for.
    const by_ac: AcOutcome[] = fptp_result.by_ac;

    // We deliberately skip assertSeatTallyInvariant - MMP's per-rule
    // invariant is `sum(seats_won) == chamber_seats` (which is
    // `constituency_count + list_seats_added`), not `total_seats`. The
    // test pin lives in mmp.test.ts via a custom assertMmpInvariant.

    return { by_party, by_ac, total_votes, chamber_seats };
  },
};
