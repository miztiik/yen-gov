/**
 * Unit tests for seat-flow-model (gap-closure G5,
 * TODO/20260616-state-event-page-gap-closure-plan.md).
 *
 * Pins the FACTUAL seat-transition contract:
 *  - holds (self-loops) vs flips counted exactly;
 *  - flows aggregate per (prev_party -> curr_party);
 *  - unmatched current seats surface as a "New / redrawn" source;
 *  - top-N bucketing collapses the long tail into "Others" on each side;
 *  - no-prior returns the empty/no_prior model.
 */

import { describe, it, expect } from "vitest";
import { buildSeatFlowModel } from "./seat-flow-model";
import type { ElectionResultRow } from "../view-models/election-results";

// Minimal winner-row factory; only the fields the model reads are set.
function win(
  entity_id: string,
  party_id: string,
  party_short: string,
): ElectionResultRow {
  return {
    entity_id,
    entity_kind: "ac",
    entity_name: entity_id,
    state_slug: "x",
    state_code: "SXX",
    eci_no: Number(entity_id.replace(/\D/g, "")) || 0,
    delim_year: 2008,
    period_label: "AcGen",
    candidate_name: null,
    position: 1,
    votes: null,
    vote_share_pct: null,
    is_winner: true,
    party_id,
    party_eci_code: null,
    party_short,
    party_short_raw: party_short,
    brand_colour_hex: null,
    brand_colour_confidence: null,
    symbol_asset_path: null,
    margin_pct: null,
    turnout_pct: null,
    electors: null,
    votes_polled: null,
    margin_votes: null,
    winner_age: null,
    winner_candidate_name: null,
    reservation: "GEN",
  } as ElectionResultRow;
}

describe("buildSeatFlowModel - no prior", () => {
  it("returns no_prior with empty nodes/flows when previous is null", () => {
    const m = buildSeatFlowModel({
      current: [win("AC1", "parties.IN.BJP", "BJP")],
      previous: null,
    });
    expect(m.no_prior).toBe(true);
    expect(m.left).toEqual([]);
    expect(m.right).toEqual([]);
    expect(m.flows).toEqual([]);
  });

  it("returns no_prior when previous is empty", () => {
    const m = buildSeatFlowModel({
      current: [win("AC1", "parties.IN.BJP", "BJP")],
      previous: [],
    });
    expect(m.no_prior).toBe(true);
  });
});

describe("buildSeatFlowModel - holds vs flips", () => {
  it("counts a held seat as a self-loop hold", () => {
    const m = buildSeatFlowModel({
      current: [win("AC1", "parties.IN.BJP", "BJP")],
      previous: [win("AC1", "parties.IN.BJP", "BJP")],
    });
    expect(m.no_prior).toBe(false);
    expect(m.holds).toBe(1);
    expect(m.flips).toBe(0);
    expect(m.total_seats).toBe(1);
    const self = m.flows.find((f) => f.from_key === f.to_key);
    expect(self?.is_hold).toBe(true);
    expect(self?.seats).toBe(1);
  });

  it("counts a changed seat as a flip cross-flow", () => {
    const m = buildSeatFlowModel({
      current: [win("AC1", "parties.IN.INC", "INC")],
      previous: [win("AC1", "parties.IN.BJP", "BJP")],
    });
    expect(m.holds).toBe(0);
    expect(m.flips).toBe(1);
    const flow = m.flows[0];
    expect(flow.from_key).toBe("parties.IN.BJP");
    expect(flow.to_key).toBe("parties.IN.INC");
    expect(flow.is_hold).toBe(false);
    expect(flow.seats).toBe(1);
  });

  it("aggregates multiple seats into one ribbon", () => {
    const prev = [
      win("AC1", "parties.IN.BJP", "BJP"),
      win("AC2", "parties.IN.BJP", "BJP"),
      win("AC3", "parties.IN.BJP", "BJP"),
    ];
    const curr = [
      win("AC1", "parties.IN.INC", "INC"),
      win("AC2", "parties.IN.INC", "INC"),
      win("AC3", "parties.IN.BJP", "BJP"),
    ];
    const m = buildSeatFlowModel({ current: curr, previous: prev });
    expect(m.holds).toBe(1); // AC3
    expect(m.flips).toBe(2); // AC1 + AC2
    const bjpToInc = m.flows.find(
      (f) => f.from_key === "parties.IN.BJP" && f.to_key === "parties.IN.INC",
    );
    expect(bjpToInc?.seats).toBe(2);
  });
});

describe("buildSeatFlowModel - unmatched (delimitation)", () => {
  it("surfaces a current seat with no prior match as New / redrawn", () => {
    const m = buildSeatFlowModel({
      current: [
        win("AC1", "parties.IN.BJP", "BJP"),
        win("AC2", "parties.IN.INC", "INC"),
      ],
      previous: [win("AC1", "parties.IN.BJP", "BJP")],
    });
    expect(m.unmatched).toBe(1);
    const newNode = m.left.find((n) => n.key === "__new__");
    expect(newNode?.seats).toBe(1);
    const newFlow = m.flows.find((f) => f.from_key === "__new__");
    expect(newFlow?.to_key).toBe("parties.IN.INC");
    expect(newFlow?.seats).toBe(1);
  });
});

describe("buildSeatFlowModel - top-N bucketing", () => {
  it("collapses the long tail into Others on each side", () => {
    // 8 distinct prev+curr parties, topN = 2 -> 2 kept + Others.
    const prev = Array.from({ length: 8 }, (_, i) =>
      win(`AC${i}`, `parties.IN.P${i}`, `P${i}`),
    );
    // current: P0 holds 3 (AC0,AC1,AC2 won by P0); rest stay their own.
    const curr = [
      win("AC0", "parties.IN.P0", "P0"),
      win("AC1", "parties.IN.P0", "P0"),
      win("AC2", "parties.IN.P0", "P0"),
      win("AC3", "parties.IN.P3", "P3"),
      win("AC4", "parties.IN.P4", "P4"),
      win("AC5", "parties.IN.P5", "P5"),
      win("AC6", "parties.IN.P6", "P6"),
      win("AC7", "parties.IN.P7", "P7"),
    ];
    const m = buildSeatFlowModel({ current: curr, previous: prev, topN: 2 });
    const others = m.right.find((n) => n.key === "__others__");
    expect(others).toBeTruthy();
    expect(others?.is_bucket).toBe(true);
    // Right side: P0 (3 seats) kept as top; one more party kept; the rest
    // bucket into Others.
    const kept = m.right.filter((n) => !n.is_bucket);
    expect(kept.length).toBe(2);
  });
});
