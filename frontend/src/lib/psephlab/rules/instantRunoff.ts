// Instant Runoff Voting (IRV) with uniform-transfer rule.
//
// Per parent plan section 25.6b-seam + override sub-plan
// `TODO/20260608-e6-user-override-and-pl2-pl3-execution-subplan.md`.
//
// Per-AC: iteratively eliminate the lowest-vote candidate (excluding
// NOTA). When a candidate is eliminated, their votes transfer to
// surviving non-NOTA candidates IN PROPORTION to those survivors'
// CURRENT vote shares (uniform-transfer rule). The first candidate to
// reach > 50% of remaining non-NOTA votes wins that AC.
//
// NOTA is never eliminated (NOTA is a legitimate ballot choice) and
// never receives transfers (it has no platform to transfer to). If
// only NOTA + one non-NOTA remain, the non-NOTA wins (mirrors fptp.ts
// NOTA-fallback rule).
//
// Honest caveat: Indian EVMs do not record ranked ballots. The
// uniform-transfer assumption is defensible but un-testable.

import type {
  AcOutcome,
  CandidateTally,
  CountingRule,
  PartyResult,
  SeatAllocation,
  Tallies,
} from "../types";
import { assertSeatTallyInvariant } from "../../charts/count-seats";

interface RoundCandidate {
  ref: CandidateTally; // back-pointer to the original immutable tally row
  votes: number;       // mutable per-round vote count
}

function runoff_one_ac(candidates: readonly CandidateTally[]): CandidateTally | null {
  if (candidates.length === 0) return null;

  const round: RoundCandidate[] = candidates.map((c) => ({
    ref: c,
    votes: c.votes,
  }));

  // Loop until we have a winner or only one non-NOTA candidate is left.
  // Hard upper bound = candidate count (each round eliminates one).
  for (let i = 0; i < candidates.length + 1; i++) {
    const non_nota = round.filter((r) => r.ref.party_eci_code !== "NOTA");
    if (non_nota.length === 0) {
      // No non-NOTA left at all; the AC is uncontested by real parties.
      return null;
    }
    if (non_nota.length === 1) {
      // Single non-NOTA remaining -> wins regardless of NOTA share.
      return non_nota[0].ref;
    }
    const non_nota_total = non_nota.reduce((s, r) => s + r.votes, 0);
    // > 50% non-NOTA majority -> winner.
    for (const r of non_nota) {
      if (non_nota_total > 0 && r.votes > 0.5 * non_nota_total) {
        return r.ref;
      }
    }
    // Otherwise eliminate the lowest-vote non-NOTA candidate (ties
    // broken by candidate name ASC for determinism).
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
    const eliminated_votes = round[min_idx].votes;
    round.splice(min_idx, 1);

    // Transfer eliminated votes to surviving non-NOTA candidates in
    // proportion to those survivors' CURRENT vote shares.
    const survivors = round.filter((r) => r.ref.party_eci_code !== "NOTA");
    const survivor_total = survivors.reduce((s, r) => s + r.votes, 0);
    if (survivor_total > 0 && eliminated_votes > 0) {
      for (const r of survivors) {
        r.votes += eliminated_votes * (r.votes / survivor_total);
      }
    }
  }

  // Defensive: fall back to highest non-NOTA still in the round set.
  const remaining_non_nota = round
    .filter((r) => r.ref.party_eci_code !== "NOTA")
    .sort((a, b) => b.votes - a.votes || a.ref.name.localeCompare(b.ref.name));
  return remaining_non_nota[0]?.ref ?? null;
}

export const instantRunoff: CountingRule = {
  id: "ranked-choice",
  label: "Ranked-choice (proportional transfer)",
  short_label: "Ranked-choice (proportional)",
  headline: "Eliminate the weakest, share their votes by current strength.",
  validity: "medium_validity",
  requires_banner: true,
  caveat:
    "India's EVMs do not record ranked ballots, so we hold each voter's " +
    "second preference proportional to current first-preference shares in " +
    "their constituency. Watch where this method DIVERGES from the official " +
    "count - the seats that flip are the ones where the FPTP plurality is " +
    "so structurally narrow that almost any reasonable transfer rule would " +
    "flip them. The unflipped seats stay neutral; they prove neither " +
    "stability nor instability under real ranked ballots. Read flips as a " +
    "lower bound on how different India would look with real ranked-choice " +
    "ballots.",
  assumptions: [
    "Holds constant: each voter's first preference matches their FPTP vote.",
    "Holds constant: when a candidate is eliminated, their votes redistribute to surviving non-NOTA candidates in proportion to those candidates' CURRENT vote shares.",
    "NOTA is never eliminated and never receives transfers; if only NOTA plus one non-NOTA remain, the non-NOTA candidate wins.",
    "Tie-breaking on elimination: lowest votes first; ties broken by candidate name ASC.",
    "Reveals: the seats where the FPTP plurality is structurally fragile.",
  ],

  apply(tallies: Tallies): SeatAllocation {
    const by_ac: AcOutcome[] = [];
    const totals = new Map<string, PartyResult>();
    let total_votes = 0;

    for (const ac of tallies.acs) {
      const ac_total = ac.candidates.reduce((s, c) => s + c.votes, 0);
      total_votes += ac_total;

      // Aggregate per-party totals (using first-preference votes;
      // mirrors fptp.ts behaviour so vote_share_pct stays comparable).
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

      const winner = runoff_one_ac(ac.candidates);
      if (!winner) continue;

      const seat_party = totals.get(winner.party_eci_code);
      if (seat_party) seat_party.seats_won += 1;

      // Runner-up: highest first-preference vote-getter excluding the
      // winner (mirrors fptp.ts conventions).
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
      "psephlab:instantRunoff",
    );

    return { by_party, by_ac, total_votes };
  },
};
