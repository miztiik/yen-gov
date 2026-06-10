// Pure derivation for InlineCounterfactualSwing.svelte (PR-W3b, 2026-06-10).
//
// Extracted from the Svelte component for the same reason as
// alliance-totals-model: vitest runs in node-env and mounting Svelte
// components needs jsdom + @testing-library/svelte, which the project
// intentionally does not install. The pure derivation tests cover the
// engine composition (statewideSwing mutation + fptp rule) end-to-end.

import { run } from "../psephlab/engine";
import type {
  PartyResult,
  Scenario,
  SeatAllocation,
  Tallies,
} from "../psephlab/types";

/** A single seat-tally row for the "Seats under this swing" card. */
export interface SwingSeatRow {
  party_eci_code: string;
  party_short: string;
  baseline_seats: number;
  swung_seats: number;
  delta: number;
}

/** Choice items for the from/to dropdowns. */
export interface PartyChoice {
  party_eci_code: string;
  party_short: string;
  /** Statewide vote total (for sort order in the dropdown). */
  votes: number;
}

/** Compose statewideSwing + fptp via the existing engine and project
 *  the per-party delta table for the seats-card. Pure — safe to call
 *  on every slider tick. */
export function deriveSwingSeats(
  actuals: Tallies,
  from_party_eci_code: string | null,
  to_party_eci_code: string | null,
  pct: number,
): SwingSeatRow[] {
  const scenario: Scenario = {
    v: 1,
    rule: "fptp",
    mutations:
      from_party_eci_code && to_party_eci_code && pct > 0
        ? [
            {
              id: "statewideSwing",
              from_party_eci_codes: [from_party_eci_code],
              to_party_eci_code,
              pct,
            },
          ]
        : [],
  };
  const result = run(actuals, scenario);
  return projectSeatDeltas(result.actuals_allocation, result.allocation);
}

function projectSeatDeltas(
  baseline: SeatAllocation,
  swung: SeatAllocation,
): SwingSeatRow[] {
  const by = new Map<
    string,
    { party_short: string; baseline_seats: number; swung_seats: number }
  >();
  const upsert = (party_eci_code: string, party_short: string): {
    party_short: string;
    baseline_seats: number;
    swung_seats: number;
  } => {
    const hit = by.get(party_eci_code);
    if (hit) return hit;
    const row = { party_short, baseline_seats: 0, swung_seats: 0 };
    by.set(party_eci_code, row);
    return row;
  };
  for (const p of baseline.by_party as readonly PartyResult[]) {
    upsert(p.party_eci_code, p.party_short).baseline_seats = p.seats_won;
  }
  for (const p of swung.by_party as readonly PartyResult[]) {
    upsert(p.party_eci_code, p.party_short).swung_seats = p.seats_won;
  }
  const rows: SwingSeatRow[] = [];
  for (const [party_eci_code, r] of by) {
    if (r.baseline_seats === 0 && r.swung_seats === 0) continue;
    rows.push({
      party_eci_code,
      party_short: r.party_short,
      baseline_seats: r.baseline_seats,
      swung_seats: r.swung_seats,
      delta: r.swung_seats - r.baseline_seats,
    });
  }
  rows.sort((a, b) => b.swung_seats - a.swung_seats);
  return rows;
}

/** Distinct party choices for the dropdowns, sorted by statewide votes
 *  desc so the dominant parties appear first. NOTA is excluded — a
 *  swing TO NOTA is not a meaningful counterfactual. */
export function listPartyChoices(actuals: Tallies): PartyChoice[] {
  const totals = new Map<string, PartyChoice>();
  for (const ac of actuals.acs) {
    for (const c of ac.candidates) {
      if (c.party_eci_code === "NOTA") continue;
      const hit = totals.get(c.party_eci_code);
      if (hit) {
        hit.votes += c.votes;
      } else {
        totals.set(c.party_eci_code, {
          party_eci_code: c.party_eci_code,
          party_short: c.party_short,
          votes: c.votes,
        });
      }
    }
  }
  return [...totals.values()].sort((a, b) => b.votes - a.votes);
}
