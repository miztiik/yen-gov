/**
 * Unit tests for cross-event-sankey-model (R5 of
 * TODO/20260615-state-election-event-page-redesign-plan.md, 2026-06-15).
 *
 * Asserts the Max + Jony verdict baked into the row spec:
 *  - top-N + Others bucketing on the diverging bar
 *  - signed delta arithmetic (seats_current - seats_prev)
 *  - sort by max(current, prev) desc with abs-delta tiebreak
 *  - no_prior=true when previous is null OR empty - the section
 *    renders the no-prior copy with no button and no DivergingBar
 *  - sankey_actuals / sankey_scenario carry the FULL aggregated lists
 *    (not just top-N) so the ribbon arithmetic does not pre-collapse
 *  - color resolution falls back to the algorithmic tier when no
 *    brand_colour row is on the loaded winners
 */

import { describe, expect, it } from "vitest";

import {
  buildCrossEventSankeyModel,
  DEFAULT_TOP_N,
} from "./cross-event-sankey-model";
import type { ElectionResultRow } from "../view-models/election-results";

function fakeWinner(
  partial: Partial<ElectionResultRow> & {
    eci_no: number;
    entity_name: string;
    party_id: string;
    party_short: string;
  },
): ElectionResultRow {
  return {
    state_code: partial.state_code ?? "S13",
    state_slug: partial.state_slug ?? "maharashtra",
    eci_no: partial.eci_no,
    entity_id: partial.entity_id ?? `S13-AC-${partial.eci_no}`,
    entity_kind: partial.entity_kind ?? "ac",
    entity_name: partial.entity_name,
    delim_year: partial.delim_year ?? 2008,
    period_label: partial.period_label ?? "AcGenNov2024",
    candidate_name: partial.candidate_name ?? "Test Candidate",
    position: partial.position ?? 1,
    votes: partial.votes ?? null,
    vote_share_pct: partial.vote_share_pct ?? 40,
    is_winner: partial.is_winner ?? true,
    party_id: partial.party_id,
    party_short: partial.party_short,
    party_eci_code: partial.party_eci_code ?? partial.party_short,
    party_short_raw: partial.party_short_raw ?? null,
    brand_colour_hex: partial.brand_colour_hex ?? null,
    brand_colour_confidence: partial.brand_colour_confidence ?? null,
    symbol_asset_path: partial.symbol_asset_path ?? null,
    margin_pct: partial.margin_pct ?? 5,
    turnout_pct: partial.turnout_pct ?? 60,
    electors: partial.electors ?? 200000,
    votes_polled: partial.votes_polled ?? 100000,
    margin_votes: partial.margin_votes ?? null,
    winner_age: partial.winner_age ?? null,
    winner_candidate_name: partial.winner_candidate_name ?? "Test Candidate",
    reservation: partial.reservation ?? "GEN",
  } as ElectionResultRow;
}

function mkWinners(
  parties: Array<{ party_id: string; party_short: string; n: number }>,
): ElectionResultRow[] {
  const rows: ElectionResultRow[] = [];
  let eci = 1;
  for (const p of parties) {
    for (let i = 0; i < p.n; i++) {
      rows.push(
        fakeWinner({
          eci_no: eci,
          entity_name: `Seat ${eci}`,
          party_id: p.party_id,
          party_short: p.party_short,
        }),
      );
      eci++;
    }
  }
  return rows;
}

describe("buildCrossEventSankeyModel - no-prior case", () => {
  it("returns no_prior=true when previous is null", () => {
    const model = buildCrossEventSankeyModel({
      current: mkWinners([{ party_id: "parties.IN.BJP", party_short: "BJP", n: 100 }]),
      previous: null,
    });
    expect(model.no_prior).toBe(true);
    expect(model.diverging).toEqual([]);
    expect(model.sankey_actuals).toEqual([]);
    expect(model.sankey_scenario).toEqual([]);
  });

  it("returns no_prior=true when previous is empty array", () => {
    const model = buildCrossEventSankeyModel({
      current: mkWinners([{ party_id: "parties.IN.BJP", party_short: "BJP", n: 100 }]),
      previous: [],
    });
    expect(model.no_prior).toBe(true);
    expect(model.diverging).toHaveLength(0);
  });
});

describe("buildCrossEventSankeyModel - delta arithmetic", () => {
  it("emits signed delta (current - prev) for each party", () => {
    const model = buildCrossEventSankeyModel({
      current: mkWinners([
        { party_id: "parties.IN.BJP", party_short: "BJP", n: 132 },
        { party_id: "parties.IN.INC", party_short: "INC", n: 16 },
      ]),
      previous: mkWinners([
        { party_id: "parties.IN.BJP", party_short: "BJP", n: 105 },
        { party_id: "parties.IN.INC", party_short: "INC", n: 44 },
      ]),
    });
    expect(model.no_prior).toBe(false);
    const by_id = new Map(model.diverging.map((r) => [r.party_id, r]));
    expect(by_id.get("parties.IN.BJP")?.delta).toBe(27);
    expect(by_id.get("parties.IN.INC")?.delta).toBe(-28);
  });

  it("handles parties present in ONLY the previous event (delta=-prev)", () => {
    const model = buildCrossEventSankeyModel({
      current: mkWinners([{ party_id: "parties.IN.BJP", party_short: "BJP", n: 100 }]),
      previous: mkWinners([
        { party_id: "parties.IN.BJP", party_short: "BJP", n: 50 },
        { party_id: "parties.IN.DEFUNCT", party_short: "DEFUNCT", n: 30 },
      ]),
    });
    const by_id = new Map(model.diverging.map((r) => [r.party_id, r]));
    expect(by_id.get("parties.IN.DEFUNCT")?.delta).toBe(-30);
    expect(by_id.get("parties.IN.DEFUNCT")?.seats_current).toBe(0);
  });

  it("handles parties present in ONLY the current event (delta=+current)", () => {
    const model = buildCrossEventSankeyModel({
      current: mkWinners([
        { party_id: "parties.IN.BJP", party_short: "BJP", n: 50 },
        { party_id: "parties.IN.NEW", party_short: "NEW", n: 25 },
      ]),
      previous: mkWinners([{ party_id: "parties.IN.BJP", party_short: "BJP", n: 100 }]),
    });
    const by_id = new Map(model.diverging.map((r) => [r.party_id, r]));
    expect(by_id.get("parties.IN.NEW")?.delta).toBe(25);
    expect(by_id.get("parties.IN.NEW")?.seats_prev).toBe(0);
  });
});

describe("buildCrossEventSankeyModel - top-N + Others bucketing", () => {
  it("collapses parties past top-N into 'Others' with summed seats", () => {
    // 8 parties; default top-N = 6; expect 6 named + 1 Others.
    const parties = [
      { party_id: "parties.IN.P1", party_short: "P1", n: 100 },
      { party_id: "parties.IN.P2", party_short: "P2", n: 80 },
      { party_id: "parties.IN.P3", party_short: "P3", n: 60 },
      { party_id: "parties.IN.P4", party_short: "P4", n: 40 },
      { party_id: "parties.IN.P5", party_short: "P5", n: 20 },
      { party_id: "parties.IN.P6", party_short: "P6", n: 15 },
      { party_id: "parties.IN.P7", party_short: "P7", n: 10 },
      { party_id: "parties.IN.P8", party_short: "P8", n: 5 },
    ];
    const model = buildCrossEventSankeyModel({
      current: mkWinners(parties),
      previous: mkWinners(parties.map((p) => ({ ...p, n: Math.max(0, p.n - 5) }))),
    });
    expect(model.diverging).toHaveLength(DEFAULT_TOP_N + 1);
    const others = model.diverging[model.diverging.length - 1];
    expect(others.is_others).toBe(true);
    expect(others.party_short).toBe("Others");
    expect(others.seats_current).toBe(10 + 5); // P7 + P8 current
    expect(others.seats_prev).toBe(5 + 0); // P7 + P8 prev (P8 prev was max(0, 0)=0)
    expect(others.delta).toBe(15 - 5);
    expect(others.color_hex).toBe("#94a3b8");
  });

  it("does NOT add Others when party count <= top-N", () => {
    const parties = [
      { party_id: "parties.IN.P1", party_short: "P1", n: 100 },
      { party_id: "parties.IN.P2", party_short: "P2", n: 80 },
    ];
    const model = buildCrossEventSankeyModel({
      current: mkWinners(parties),
      previous: mkWinners(parties),
    });
    expect(model.diverging).toHaveLength(2);
    expect(model.diverging.some((r) => r.is_others)).toBe(false);
  });

  it("respects an explicit top_n override", () => {
    const parties = [
      { party_id: "parties.IN.P1", party_short: "P1", n: 100 },
      { party_id: "parties.IN.P2", party_short: "P2", n: 80 },
      { party_id: "parties.IN.P3", party_short: "P3", n: 60 },
    ];
    const model = buildCrossEventSankeyModel({
      current: mkWinners(parties),
      previous: mkWinners(parties),
      top_n: 2,
    });
    // 3 parties; top_n=2; 2 named + 1 Others row for the tail.
    expect(model.diverging).toHaveLength(3);
    expect(model.diverging[model.diverging.length - 1].is_others).toBe(true);
  });
});

describe("buildCrossEventSankeyModel - sort order", () => {
  it("sorts by max(seats_current, seats_prev) desc", () => {
    const model = buildCrossEventSankeyModel({
      current: mkWinners([
        { party_id: "parties.IN.SMALL", party_short: "SMALL", n: 10 },
        { party_id: "parties.IN.BIG", party_short: "BIG", n: 100 },
        { party_id: "parties.IN.MID", party_short: "MID", n: 50 },
      ]),
      previous: mkWinners([
        { party_id: "parties.IN.SMALL", party_short: "SMALL", n: 200 }, // ranks 1st by max
        { party_id: "parties.IN.BIG", party_short: "BIG", n: 80 },
        { party_id: "parties.IN.MID", party_short: "MID", n: 30 },
      ]),
    });
    expect(model.diverging.map((r) => r.party_short)).toEqual([
      "SMALL",
      "BIG",
      "MID",
    ]);
  });
});

describe("buildCrossEventSankeyModel - sankey input shape", () => {
  it("emits the FULL aggregated lists for sankey_actuals/scenario (not top-N pruned)", () => {
    const parties = [
      { party_id: "parties.IN.P1", party_short: "P1", n: 100 },
      { party_id: "parties.IN.P2", party_short: "P2", n: 80 },
      { party_id: "parties.IN.P3", party_short: "P3", n: 60 },
      { party_id: "parties.IN.P4", party_short: "P4", n: 40 },
      { party_id: "parties.IN.P5", party_short: "P5", n: 20 },
      { party_id: "parties.IN.P6", party_short: "P6", n: 15 },
      { party_id: "parties.IN.P7", party_short: "P7", n: 10 },
      { party_id: "parties.IN.P8", party_short: "P8", n: 5 },
    ];
    const model = buildCrossEventSankeyModel({
      current: mkWinners(parties),
      previous: mkWinners(parties),
    });
    // Sankey should carry all 8 parties on both sides.
    expect(model.sankey_actuals).toHaveLength(8);
    expect(model.sankey_scenario).toHaveLength(8);
    // No "Others" in the sankey shape.
    expect(model.sankey_actuals.some((r) => r.party_short === "Others")).toBe(false);
  });

  it("PartyResult.seats_won matches the aggregated seat count", () => {
    const model = buildCrossEventSankeyModel({
      current: mkWinners([{ party_id: "parties.IN.BJP", party_short: "BJP", n: 132 }]),
      previous: mkWinners([{ party_id: "parties.IN.BJP", party_short: "BJP", n: 105 }]),
    });
    expect(model.sankey_scenario[0].seats_won).toBe(132);
    expect(model.sankey_actuals[0].seats_won).toBe(105);
  });
});

describe("buildCrossEventSankeyModel - color resolution", () => {
  it("emits a non-empty color_hex for every diverging row (algorithmic tier fallback)", () => {
    const model = buildCrossEventSankeyModel({
      current: mkWinners([{ party_id: "parties.IN.X", party_short: "X", n: 5 }]),
      previous: mkWinners([{ party_id: "parties.IN.X", party_short: "X", n: 3 }]),
    });
    expect(model.diverging[0].color_hex).toMatch(/^#[0-9a-f]{6}$/i);
  });
});
