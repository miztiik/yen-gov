// Top-2 Runoff with alliance-pool transfer (TRS Round 2, alliance variant).
//
// Per Hans + Fowler round-2 verdict (2026-06-09). The proportional
// variant (trsRound2.ts) treats eliminated voters as politically
// agnostic between the top 2 survivors. This variant uses ALLIANCE
// DISCIPLINE: eliminated INDIA-bloc votes go to the surviving INDIA
// candidate; NDA the same. We hold alliance discipline at 100% - the
// perfect-coordination limit.
//
// Per-AC algorithm:
//   1. Same top-2 selection as proportional TRS.
//   2. For each eliminated candidate:
//      a. Look up the candidate's alliance via tallies.alliances(party_id).
//      b. If one of the top 2 shares that alliance: 100% of votes go to
//         that survivor.
//      c. If both top 2 share that alliance (rare): split proportionally
//         to first-round shares.
//      d. If neither top 2 shares the alliance (or candidate has no
//         alliance): fall back to proportional split (same as
//         trsRound2.ts).
//
// Fallback: when no alliance data exists for the event (the lookup
// returns null for every party_id), this rule degrades to TRS Round 2
// proportional. The inline caveat surfaces the fallback to the citizen.

import type {
  AcOutcome,
  AllianceLookup,
  CandidateTally,
  CountingRule,
  PartyResult,
  SeatAllocation,
  Tallies,
} from "../types";
import { assertSeatTallyInvariant } from "../../charts/count-seats";

interface RunoffStateRow {
  ref: CandidateTally;
  votes: number;
}

function runoffAllianceOneAc(
  candidates: readonly CandidateTally[],
  alliances: AllianceLookup | undefined,
): CandidateTally | null {
  const non_nota = candidates.filter((c) => c.party_eci_code !== "NOTA");
  if (non_nota.length === 0) return null;
  if (non_nota.length === 1) return non_nota[0];

  const sorted = [...non_nota].sort(
    (a, b) =>
      b.votes - a.votes ||
      a.name.localeCompare(b.name) ||
      a.party_eci_code.localeCompare(b.party_eci_code),
  );
  const s1: RunoffStateRow = { ref: sorted[0], votes: sorted[0].votes };
  const s2: RunoffStateRow = { ref: sorted[1], votes: sorted[1].votes };

  const lookup = alliances ?? (() => null);
  const s1_alliance = lookup(s1.ref.party_id);
  const s2_alliance = lookup(s2.ref.party_id);

  // Eliminated candidates (positions >= 2).
  for (let i = 2; i < sorted.length; i++) {
    const c = sorted[i];
    if (c.votes <= 0) continue;
    const c_alliance = lookup(c.party_id);
    if (c_alliance != null && c_alliance === s1_alliance && c_alliance === s2_alliance) {
      // Both survivors are in the same alliance as c: split
      // proportionally to first-round shares (preserves the
      // alliance pool's internal distribution).
      const denom = s1.ref.votes + s2.ref.votes;
      if (denom > 0) {
        s1.votes += c.votes * (s1.ref.votes / denom);
        s2.votes += c.votes * (s2.ref.votes / denom);
      }
    } else if (c_alliance != null && c_alliance === s1_alliance) {
      s1.votes += c.votes;
    } else if (c_alliance != null && c_alliance === s2_alliance) {
      s2.votes += c.votes;
    } else {
      // c has no alliance, or its alliance has no survivor: proportional fallback.
      const denom = s1.ref.votes + s2.ref.votes;
      if (denom > 0) {
        s1.votes += c.votes * (s1.ref.votes / denom);
        s2.votes += c.votes * (s2.ref.votes / denom);
      }
    }
  }

  if (s1.votes > s2.votes) return s1.ref;
  if (s2.votes > s1.votes) return s2.ref;
  return s1.ref.name <= s2.ref.name ? s1.ref : s2.ref;
}

export const trsRound2Alliance: CountingRule = {
  id: "trs-round-2-alliance",
  label: "Top-2 Runoff (alliance pool)",
  short_label: "Top-2 Runoff (alliance)",
  headline: "Same shape, but alliance partners pool their eliminated votes.",
  validity: "medium_validity",
  requires_banner: true,
  caveat:
    "Same top-2 runoff as the proportional variant, but eliminated " +
    "candidates pass their votes to the surviving candidate in the same " +
    "alliance. NDA-bloc voters route to the NDA survivor; INDIA-bloc " +
    "voters route to the INDIA survivor. We hold alliance discipline at " +
    "100% - the perfect-coordination LIMIT, not the prediction. " +
    "Together with the proportional variant, these two views BRACKET " +
    "the real outcome between zero discipline and total discipline. " +
    "When no curated alliance map exists for this election, the method " +
    "degrades to TRS Round 2 (proportional).",
  assumptions: [
    "Holds constant: top 2 candidates in each AC by first-preference votes survive to round 2.",
    "Holds constant: 100% alliance transfer discipline (NDA voters always pick NDA survivor; INDIA always picks INDIA).",
    "Holds constant: current published alliance map as of poll date (single static lookup; coalitions changing mid-campaign are not modeled).",
    "Holds constant: candidates with no alliance or whose alliance has no survivor split proportionally (proportional fallback).",
    "Reveals: the upper bound of alliance arithmetic when coordination is perfect.",
  ],

  apply(tallies: Tallies): SeatAllocation {
    const by_ac: AcOutcome[] = [];
    const totals = new Map<string, PartyResult>();
    let total_votes = 0;

    for (const ac of tallies.acs) {
      const ac_total = ac.candidates.reduce((s, c) => s + c.votes, 0);
      total_votes += ac_total;

      for (const c of ac.candidates) {
        const t = totals.get(c.party_eci_code);
        if (t) {
          t.votes += c.votes;
          if (t.party_id == null && c.party_id != null) {
            t.party_id = c.party_id;
            t.brand_colour_hex = c.brand_colour_hex ?? null;
            t.brand_colour_confidence = c.brand_colour_confidence ?? null;
            t.election_symbol_asset_path = c.election_symbol_asset_path ?? null;
          }
        } else {
          totals.set(c.party_eci_code, {
            party_eci_code: c.party_eci_code,
            party_short: c.party_short,
            seats_won: 0,
            votes: c.votes,
            vote_share_pct: 0,
            party_id: c.party_id,
            brand_colour_hex: c.brand_colour_hex ?? null,
            brand_colour_confidence: c.brand_colour_confidence ?? null,
            election_symbol_asset_path: c.election_symbol_asset_path ?? null,
          });
        }
      }

      const winner = runoffAllianceOneAc(ac.candidates, tallies.alliances);
      if (!winner) continue;
      const seat_party = totals.get(winner.party_eci_code);
      if (seat_party) seat_party.seats_won += 1;

      let runner_up: CandidateTally | null = null;
      for (const c of ac.candidates) {
        if (c === winner) continue;
        if (
          runner_up == null ||
          c.votes > runner_up.votes ||
          (c.votes === runner_up.votes && c.name < runner_up.name)
        ) {
          runner_up = c;
        }
      }
      const margin_votes = runner_up ? winner.votes - runner_up.votes : winner.votes;
      by_ac.push({
        eci_no: ac.eci_no,
        name: ac.name,
        winner,
        runner_up,
        margin_votes,
        margin_pct: ac_total === 0 ? 0 : (100 * margin_votes) / ac_total,
      });
    }

    const by_party: PartyResult[] = [];
    for (const t of totals.values()) {
      t.vote_share_pct = total_votes === 0 ? 0 : (100 * t.votes) / total_votes;
      by_party.push(t);
    }
    by_party.sort(
      (a, b) =>
        b.seats_won - a.seats_won ||
        b.votes - a.votes ||
        a.party_short.localeCompare(b.party_short),
    );

    assertSeatTallyInvariant(
      {
        total_seats: by_ac.length,
        parties: by_party.map((p) => ({
          party_id: p.party_id,
          seats_won: p.seats_won,
        })),
      },
      "psephlab:trsRound2Alliance",
    );

    return { by_party, by_ac, total_votes };
  },
};
