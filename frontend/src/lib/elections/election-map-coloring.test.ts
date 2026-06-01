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
} from "./election-map-coloring";

function w(partial: Partial<AcWinner> & { ac_eci_no: number }): AcWinner {
  return {
    ac_name: `AC ${partial.ac_eci_no}`,
    party_eci_code: "BJP",
    party_short: "BJP",
    margin_pct: 10,
    turnout_pct: null,
    winner_age: null,
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
