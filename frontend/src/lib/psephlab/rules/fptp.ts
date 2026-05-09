// First-Past-The-Post counting rule.
//
// Per AC: the candidate with the highest vote total wins. Ties broken by
// candidate name ascending — deterministic, matches what ECI does in
// practice (lots draws aside, which we don't model).
//
// This is the v1 default and the only rule shipped. Other rules (IRV, STV,
// D'Hondt, Sainte-Laguë) are sketched in psephlab.md for v2+.

import type { AcOutcome, CountingRule, PartyResult, SeatAllocation, Tallies } from "../types";

function tally_winner(candidates: { votes: number; name: string }[]):
  | { idx: number; runner_up_idx: number | null }
  | null {
  if (candidates.length === 0) return null;
  let win = 0;
  for (let i = 1; i < candidates.length; i++) {
    const c = candidates[i];
    const w = candidates[win];
    if (c.votes > w.votes || (c.votes === w.votes && c.name < w.name)) {
      win = i;
    }
  }
  // Pick a runner-up: highest votes excluding the winner.
  let runner: number | null = null;
  for (let i = 0; i < candidates.length; i++) {
    if (i === win) continue;
    if (runner === null) {
      runner = i;
      continue;
    }
    const c = candidates[i];
    const r = candidates[runner];
    if (c.votes > r.votes || (c.votes === r.votes && c.name < r.name)) {
      runner = i;
    }
  }
  return { idx: win, runner_up_idx: runner };
}

export const fptp: CountingRule = {
  id: "fptp",
  label: "First-Past-The-Post",
  apply(tallies: Tallies): SeatAllocation {
    const by_ac: AcOutcome[] = [];
    // Aggregate per-party totals across all ACs.
    const totals = new Map<string, PartyResult>();
    let total_votes = 0;

    for (const ac of tallies.acs) {
      const ac_total = ac.candidates.reduce((s, c) => s + c.votes, 0);
      total_votes += ac_total;

      // Per-party AC totals (NOTA included for vote-share completeness;
      // NOTA cannot win, but its votes count toward the denominator).
      for (const c of ac.candidates) {
        const t = totals.get(c.party_eci_code);
        if (t) {
          t.votes += c.votes;
        } else {
          totals.set(c.party_eci_code, {
            party_eci_code: c.party_eci_code,
            party_short: c.party_short,
            seats_won: 0,
            votes: c.votes,
            vote_share_pct: 0,
          });
        }
      }

      const win = tally_winner(ac.candidates);
      if (!win) continue;
      const winner = ac.candidates[win.idx];
      const runner_up = win.runner_up_idx == null ? null : ac.candidates[win.runner_up_idx];

      // NOTA technically can never be a "winner" — we still report the seat
      // as the highest non-NOTA, mirroring real-world behaviour.
      let effective_winner = winner;
      let effective_runner = runner_up;
      if (winner.party_eci_code === "NOTA") {
        const non_nota = ac.candidates.filter(c => c.party_eci_code !== "NOTA");
        const w2 = tally_winner(non_nota);
        if (w2) {
          effective_winner = non_nota[w2.idx];
          effective_runner = w2.runner_up_idx == null ? null : non_nota[w2.runner_up_idx];
        }
      }

      const seat_party = totals.get(effective_winner.party_eci_code);
      if (seat_party) seat_party.seats_won += 1;

      const margin_votes = effective_runner ? effective_winner.votes - effective_runner.votes : effective_winner.votes;
      by_ac.push({
        eci_no: ac.eci_no,
        name: ac.name,
        winner: effective_winner,
        runner_up: effective_runner,
        margin_votes,
        margin_pct: ac_total === 0 ? 0 : (100 * margin_votes) / ac_total,
      });
    }

    // Normalize vote shares against the global denominator.
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

    return { by_party, by_ac, total_votes };
  },
};
