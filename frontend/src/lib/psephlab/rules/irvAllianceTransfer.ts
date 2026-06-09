// Ranked-choice with alliance-transfer (IRV alliance variant).
//
// Per Hans + Fowler round-2 verdict (2026-06-09). The proportional
// variant (instantRunoff.ts) redistributes eliminated votes to all
// surviving non-NOTA candidates in proportion to those candidates'
// CURRENT vote shares. This variant uses ALLIANCE DISCIPLINE: when a
// candidate is eliminated, 100% of their votes go to surviving
// candidates in the SAME alliance. If no survivor shares the alliance
// (or the eliminated candidate has no alliance), fall back to
// proportional uniform transfer.
//
// Per-AC algorithm (per round):
//   1. If a non-NOTA candidate has > 50% of remaining non-NOTA votes,
//      they win.
//   2. Otherwise, eliminate the lowest-vote non-NOTA candidate.
//   3. Transfer their votes:
//      a. Compute the eliminated's alliance via tallies.alliances.
//      b. Find surviving non-NOTA candidates in the same alliance.
//      c. If any: distribute eliminated votes among them in proportion
//         to those allies' CURRENT vote shares (so a stronger ally gets
//         a larger transfer; mirrors the proportional rule WITHIN the
//         alliance pool).
//      d. If none: fall back to the proportional rule across ALL
//         surviving non-NOTA candidates.
//
// Same NOTA + tie-breaking rules as the proportional variant.

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

interface RoundCandidate {
  ref: CandidateTally;
  votes: number;
}

function allianceRunoffOneAc(
  candidates: readonly CandidateTally[],
  alliances: AllianceLookup | undefined,
): CandidateTally | null {
  if (candidates.length === 0) return null;

  const round: RoundCandidate[] = candidates.map((c) => ({ ref: c, votes: c.votes }));
  const lookup = alliances ?? (() => null);

  for (let iter = 0; iter < candidates.length + 1; iter++) {
    const non_nota = round.filter((r) => r.ref.party_eci_code !== "NOTA");
    if (non_nota.length === 0) return null;
    if (non_nota.length === 1) return non_nota[0].ref;

    const non_nota_total = non_nota.reduce((s, r) => s + r.votes, 0);
    for (const r of non_nota) {
      if (non_nota_total > 0 && r.votes > 0.5 * non_nota_total) return r.ref;
    }

    // Eliminate the lowest-vote non-NOTA candidate.
    let min_idx = -1;
    let min_votes = Infinity;
    let min_name = "";
    for (let j = 0; j < round.length; j++) {
      const r = round[j];
      if (r.ref.party_eci_code === "NOTA") continue;
      if (
        r.votes < min_votes ||
        (r.votes === min_votes && r.ref.name < min_name)
      ) {
        min_idx = j;
        min_votes = r.votes;
        min_name = r.ref.name;
      }
    }
    if (min_idx === -1) break;
    const eliminated = round[min_idx];
    const eliminated_votes = eliminated.votes;
    const eliminated_alliance = lookup(eliminated.ref.party_id);
    round.splice(min_idx, 1);

    if (eliminated_votes <= 0) continue;

    const survivors = round.filter((r) => r.ref.party_eci_code !== "NOTA");
    // Try alliance-targeted transfer first.
    if (eliminated_alliance != null) {
      const allies = survivors.filter(
        (r) => lookup(r.ref.party_id) === eliminated_alliance,
      );
      if (allies.length > 0) {
        const ally_total = allies.reduce((s, r) => s + r.votes, 0);
        if (ally_total > 0) {
          for (const r of allies) {
            r.votes += eliminated_votes * (r.votes / ally_total);
          }
        } else {
          // Allies all at zero votes: split equally among them.
          for (const r of allies) {
            r.votes += eliminated_votes / allies.length;
          }
        }
        continue;
      }
    }

    // Fallback: proportional uniform transfer across all survivors.
    const survivor_total = survivors.reduce((s, r) => s + r.votes, 0);
    if (survivor_total > 0) {
      for (const r of survivors) {
        r.votes += eliminated_votes * (r.votes / survivor_total);
      }
    }
  }

  // Defensive fallback: highest non-NOTA remaining.
  const remaining = round
    .filter((r) => r.ref.party_eci_code !== "NOTA")
    .sort((a, b) => b.votes - a.votes || a.ref.name.localeCompare(b.ref.name));
  return remaining[0]?.ref ?? null;
}

export const irvAllianceTransfer: CountingRule = {
  id: "ranked-choice-alliance",
  label: "Ranked-choice (alliance-transfer)",
  short_label: "Ranked-choice (alliance)",
  headline: "Eliminated votes route to alliance partners first.",
  validity: "medium_validity",
  requires_banner: true,
  caveat:
    "Same elimination loop as Ranked-choice (proportional transfer), but " +
    "when a candidate is eliminated their votes route preferentially to " +
    "any surviving candidate in the same alliance (NDA stays in NDA, INDIA " +
    "stays in INDIA). This is the politically grounded version of IRV. " +
    "Compare with the proportional variant: the difference between the " +
    "two reveals where alliance coordination would change the outcome and " +
    "where it would not. When no curated alliance map exists for this " +
    "election, the method degrades to proportional transfer.",
  assumptions: [
    "Holds constant: each voter's first preference matches their FPTP vote.",
    "Holds constant: when a candidate is eliminated, their votes route 100% to surviving candidates in the same alliance (split proportionally to those allies' current shares).",
    "Holds constant: if no survivor shares the eliminated candidate's alliance, the votes redistribute proportionally to ALL surviving non-NOTA candidates (proportional fallback).",
    "Holds constant: NOTA is never eliminated and never receives transfers; if only NOTA plus one non-NOTA remain, the non-NOTA candidate wins.",
    "Reveals: the seats where alliance discipline matters more than party identity in a multi-candidate race.",
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

      const winner = allianceRunoffOneAc(ac.candidates, tallies.alliances);
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
      "psephlab:irvAllianceTransfer",
    );

    return { by_party, by_ac, total_votes };
  },
};
