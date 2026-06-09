// Two-Round-System (TRS) Round 2 with proportional eliminated-vote
// transfer.
//
// Per Hans + Fowler round-2 verdict (2026-06-09). France runs its
// presidential elections this way: if no candidate clears 50% in
// round 1, the top 2 advance to a round-2 runoff. We simulate the
// runoff by REDISTRIBUTING the eliminated-candidate votes to the
// top 2 in PROPORTION to those top 2's first-round shares.
//
// This is the "weak" TRS Round 2: voters of eliminated candidates
// are treated as politically agnostic between the survivors. The
// alliance variant (trsRound2Alliance.ts) preserves bloc discipline.
// The two views BRACKET the real round-2 outcome.
//
// Per-AC algorithm:
//   1. Sort non-NOTA candidates by votes DESC. The top 2 survive.
//   2. Sum eliminated votes = (non-NOTA non-survivor votes).
//   3. Survivor 1 share = s1.votes / (s1.votes + s2.votes).
//      Survivor 2 share = 1 - survivor 1 share.
//   4. New votes: s1.new = s1.votes + eliminated * s1_share;
//                 s2.new = s2.votes + eliminated * s2_share.
//   5. Winner = higher of s1.new, s2.new (ties by name ASC).
//
// NOTA is excluded from top-2 selection AND from redistribution (its
// votes are "exhausted"). If only one non-NOTA candidate exists,
// they win uncontested.

import type {
  AcOutcome,
  CandidateTally,
  CountingRule,
  PartyResult,
  SeatAllocation,
  Tallies,
} from "../types";
import { assertSeatTallyInvariant } from "../../charts/count-seats";

interface SurvivorPair {
  s1: CandidateTally;
  s2: CandidateTally;
  eliminated_votes: number;
}

function pickTopTwoAndEliminated(
  candidates: readonly CandidateTally[],
): SurvivorPair | { winner: CandidateTally } | null {
  const non_nota = candidates.filter((c) => c.party_eci_code !== "NOTA");
  if (non_nota.length === 0) return null;
  if (non_nota.length === 1) return { winner: non_nota[0] };

  // Sort by votes DESC (deterministic via candidate name + party ASC).
  const sorted = [...non_nota].sort(
    (a, b) =>
      b.votes - a.votes ||
      a.name.localeCompare(b.name) ||
      a.party_eci_code.localeCompare(b.party_eci_code),
  );
  const s1 = sorted[0];
  const s2 = sorted[1];
  let eliminated_votes = 0;
  for (let i = 2; i < sorted.length; i++) eliminated_votes += sorted[i].votes;
  return { s1, s2, eliminated_votes };
}

function runoffOneAc(candidates: readonly CandidateTally[]): CandidateTally | null {
  const picked = pickTopTwoAndEliminated(candidates);
  if (!picked) return null;
  if ("winner" in picked) return picked.winner;
  const { s1, s2, eliminated_votes } = picked;
  // Redistribute eliminated votes proportionally to s1 + s2 first-round
  // shares. When s1 + s2 == 0, leave votes as-is (both are zero; pick
  // by name ASC fallback).
  const denom = s1.votes + s2.votes;
  if (denom === 0) {
    return s1.name <= s2.name ? s1 : s2;
  }
  const s1_share = s1.votes / denom;
  const s1_new = s1.votes + eliminated_votes * s1_share;
  const s2_new = s2.votes + eliminated_votes * (1 - s1_share);
  if (s1_new > s2_new) return s1;
  if (s2_new > s1_new) return s2;
  return s1.name <= s2.name ? s1 : s2;
}

export const trsRound2: CountingRule = {
  id: "trs-round-2",
  label: "Top-2 Runoff (proportional transfer)",
  short_label: "Top-2 Runoff (proportional)",
  headline: "Eliminate everyone below second, redistribute by vote share.",
  validity: "medium_validity",
  requires_banner: true,
  caveat:
    "We keep the top two candidates in each AC and redistribute the votes " +
    "of every eliminated candidate to those two in proportion to their " +
    "first-round shares. France's presidential model, applied per " +
    "constituency. This is the WEAK transfer rule: voters of eliminated " +
    "candidates are treated as politically agnostic between the survivors. " +
    "The alliance variant (Top-2 Runoff with alliances) shows the OTHER " +
    "extreme. The truth lives between them; these two views BRACKET the " +
    "real outcome.",
  assumptions: [
    "Holds constant: top 2 candidates in each AC by first-preference votes survive to round 2.",
    "Holds constant: every eliminated voter chooses between the top 2 in proportion to those two's first-round AC shares.",
    "Holds constant: alliance affinity is NOT used (see Top-2 Runoff with alliances for the alliance-discipline variant).",
    "Holds constant: NOTA votes are excluded from top-2 selection and from redistribution.",
    "Reveals: the seats where the FPTP leader's plurality is below 50% AND the eliminated bloc is large enough to flip the winner.",
  ],

  apply(tallies: Tallies): SeatAllocation {
    const by_ac: AcOutcome[] = [];
    const totals = new Map<string, PartyResult>();
    let total_votes = 0;

    for (const ac of tallies.acs) {
      const ac_total = ac.candidates.reduce((s, c) => s + c.votes, 0);
      total_votes += ac_total;

      // Per-party first-preference totals (mirrors FPTP shape).
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

      const winner = runoffOneAc(ac.candidates);
      if (!winner) continue;
      const seat_party = totals.get(winner.party_eci_code);
      if (seat_party) seat_party.seats_won += 1;

      // Runner-up: highest first-preference excluding the winner.
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
      "psephlab:trsRound2",
    );

    return { by_party, by_ac, total_votes };
  },
};
