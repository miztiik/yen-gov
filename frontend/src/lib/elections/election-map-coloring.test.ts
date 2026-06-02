import { describe, expect, it } from "vitest";
import type { AcWinner } from "../view-models/state-overview";
import { DEFAULT_ELECTION_FILTERS } from "../election-filters";
import {
  DIMMED_OPACITY,
  NO_VALUE_FILL,
  buildAcFills,
  buildAcOpacities,
  hasModeCoverage,
  lerpColor,
  matchesFilters,
  mirrorLgdKeys,
} from "./election-map-coloring";

function w(partial: Partial<AcWinner> & { ac_eci_no: number }): AcWinner {
  return {
    ac_name: `AC ${partial.ac_eci_no}`,
    party_id: "parties.IN.BJP",
    party_eci_code: "BJP",
    party_short: "BJP",
    margin_pct: 10,
    turnout_pct: null,
    winner_age: null,
    brand_colour_hex: null,
    brand_colour_confidence: null,
    ...partial,
  };
}

const partyFill = (code: string | null, short: string) =>
  code === "INC" || short === "INC" ? "#1f77b4" : "#ff7f0e";

describe("lerpColor", () => {
  it("returns endpoints at t=0 and t=1", () => {
    expect(lerpColor("#000000", "#ffffff", 0)).toBe("#000000");
    expect(lerpColor("#000000", "#ffffff", 1)).toBe("#ffffff");
  });
  it("clamps t outside [0,1]", () => {
    expect(lerpColor("#000000", "#ffffff", -5)).toBe("#000000");
    expect(lerpColor("#000000", "#ffffff", 5)).toBe("#ffffff");
  });
  it("interpolates the midpoint", () => {
    expect(lerpColor("#000000", "#ffffff", 0.5)).toBe("#808080");
  });
});

describe("hasModeCoverage", () => {
  const rows = [
    w({ ac_eci_no: 1, winner_age: 50 }),
    w({ ac_eci_no: 2, winner_age: 60 }),
    w({ ac_eci_no: 3, winner_age: null }),
  ];
  it("winner mode is always available", () => {
    expect(hasModeCoverage([], "winner")).toBe(true);
  });
  it("false for empty rows on a continuous mode", () => {
    expect(hasModeCoverage([], "age")).toBe(false);
  });
  it("gates below the 80% default threshold", () => {
    // 2/3 ≈ 0.67 < 0.8
    expect(hasModeCoverage(rows, "age")).toBe(false);
  });
  it("passes when above the threshold", () => {
    expect(hasModeCoverage(rows, "age", 0.6)).toBe(true);
  });
});

describe("matchesFilters", () => {
  it("matches all under the default filter", () => {
    expect(matchesFilters(w({ ac_eci_no: 1 }), DEFAULT_ELECTION_FILTERS)).toBe(true);
  });
  it("dims a party not in the party set", () => {
    const f = { ...DEFAULT_ELECTION_FILTERS, parties: ["INC"] };
    expect(matchesFilters(w({ ac_eci_no: 1, party_eci_code: "BJP" }), f)).toBe(false);
    expect(matchesFilters(w({ ac_eci_no: 2, party_eci_code: "INC" }), f)).toBe(true);
  });
  it("applies the margin band", () => {
    const f = { ...DEFAULT_ELECTION_FILTERS, margin: "lt2" as const };
    expect(matchesFilters(w({ ac_eci_no: 1, margin_pct: 1 }), f)).toBe(true);
    expect(matchesFilters(w({ ac_eci_no: 2, margin_pct: 25 }), f)).toBe(false);
  });
});

describe("buildAcFills", () => {
  it("winner mode uses the party resolver", () => {
    const rows = [
      w({ ac_eci_no: 1, party_eci_code: "BJP" }),
      w({ ac_eci_no: 2, party_eci_code: "INC" }),
    ];
    const fills = buildAcFills(rows, "winner", partyFill);
    expect(fills[1]).toBe("#ff7f0e");
    expect(fills[2]).toBe("#1f77b4");
  });

  it("continuous mode ramps min→max and neutralises nulls", () => {
    const rows = [
      w({ ac_eci_no: 1, turnout_pct: 50 }),
      w({ ac_eci_no: 2, turnout_pct: 70 }),
      w({ ac_eci_no: 3, turnout_pct: null }),
    ];
    const fills = buildAcFills(rows, "turnout", partyFill);
    expect(fills[1]).toBe("#e0f2fe"); // ramp start (min)
    expect(fills[2]).toBe("#0369a1"); // ramp end (max)
    expect(fills[3]).toBe(NO_VALUE_FILL);
  });
});

describe("buildAcOpacities", () => {
  it("winner mode keeps the margin-based base for matching units", () => {
    const rows = [w({ ac_eci_no: 1, margin_pct: 30 })];
    const op = buildAcOpacities(rows, "winner", DEFAULT_ELECTION_FILTERS);
    expect(op[1]).toBeCloseTo(0.95, 5);
  });

  it("dims units filtered out by party", () => {
    const rows = [
      w({ ac_eci_no: 1, party_eci_code: "BJP" }),
      w({ ac_eci_no: 2, party_eci_code: "INC" }),
    ];
    const f = { ...DEFAULT_ELECTION_FILTERS, parties: ["INC"] };
    const op = buildAcOpacities(rows, "winner", f);
    expect(op[1]).toBe(DIMMED_OPACITY);
    expect(op[2]).toBeGreaterThan(DIMMED_OPACITY);
  });

  it("continuous mode keeps matching units near-opaque", () => {
    const rows = [w({ ac_eci_no: 1, turnout_pct: 60 })];
    const op = buildAcOpacities(rows, "turnout", DEFAULT_ELECTION_FILTERS);
    expect(op[1]).toBe(0.9);
  });
});

// Row B2 (ADR-0049) — the parity oracle for the canonical lgd_ac_id join.
// mirrorLgdKeys must make the choropleth resolve to the SAME value whether
// maplibre matches a polygon on its eci_no (legacy) or its lgd_ac_id
// (canonical). These are the behavioural net: a regression here would
// silently recolour or blank covered constituencies post-migration.
describe("mirrorLgdKeys", () => {
  it("returns the base unchanged when the lookup is null (pre-load window)", () => {
    const base = { 1: "#aaa", 2: "#bbb" };
    expect(mirrorLgdKeys(base, null)).toBe(base);
  });

  it("returns the base unchanged when the lookup is empty (uncovered state)", () => {
    const base = { 1: "#aaa", 2: "#bbb" };
    expect(mirrorLgdKeys(base, new Map())).toBe(base);
  });

  it("mirrors each eci_no value under its lgd_ac_id, preserving the eci keys", () => {
    const base = { 1: "#aaa", 2: "#bbb" };
    const lookup = new Map<number, number>([
      [1, 22001],
      [2, 22002],
    ]);
    const out = mirrorLgdKeys(base, lookup);
    // eci keys retained (hex cartogram + label paths still match)
    expect(out[1]).toBe("#aaa");
    expect(out[2]).toBe("#bbb");
    // lgd keys added with the SAME value (the canonical-join parity)
    expect(out[22001]).toBe("#aaa");
    expect(out[22002]).toBe("#bbb");
  });

  it("byte-identical parity: every covered AC resolves equal on both keys", () => {
    const rows = [
      w({ ac_eci_no: 1, party_short: "BJP" }),
      w({ ac_eci_no: 2, party_short: "INC", party_eci_code: "INC" }),
      w({ ac_eci_no: 3, party_short: "BJP" }),
    ];
    const base = buildAcFills(rows, "winner", partyFill);
    const lookup = new Map<number, number>([
      [1, 22001],
      [2, 22002],
      [3, 22003],
    ]);
    const out = mirrorLgdKeys(base, lookup);
    for (const [eci, lgd] of lookup) {
      expect(out[lgd]).toBe(base[eci]);
    }
  });

  it("does not invent a key for an AC the crosswalk omits (uncovered seat)", () => {
    const base = { 1: "#aaa", 2: "#bbb" };
    // only AC 1 is mapped; AC 2 has no lgd_ac_id
    const lookup = new Map<number, number>([[1, 22001]]);
    const out = mirrorLgdKeys(base, lookup);
    expect(out[22001]).toBe("#aaa");
    expect(Object.keys(out).sort()).toEqual(["1", "2", "22001"]);
  });

  it("skips the mirror when lgd_ac_id equals eci_no (no self-collision)", () => {
    const base = { 5: "#ccc" };
    const lookup = new Map<number, number>([[5, 5]]);
    const out = mirrorLgdKeys(base, lookup);
    expect(Object.keys(out)).toEqual(["5"]);
  });
});

