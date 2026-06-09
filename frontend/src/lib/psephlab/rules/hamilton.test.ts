// Unit tests for the Hamilton (Largest Remainder) PR rule.
//
// FIXTURE state-wide totals (excl NOTA): DMK 1300, AIADMK 1480, BJP 180.
// Total non-NOTA = 2960. Seats = 3.
//
// Hare quota = 2960 / 3 = 986.67.
// Exact shares: DMK 1300/986.67=1.317, AIADMK 1480/986.67=1.500,
//               BJP 180/986.67=0.182.
// Integer shares: DMK=1, AIADMK=1, BJP=0. Total allocated = 2. Remaining = 1.
// Remainders: AIADMK 0.500, DMK 0.317, BJP 0.182.
// Largest remainder = AIADMK -> 1 more seat.
// Final: AIADMK=2, DMK=1, BJP=0.

import { describe, expect, it } from "vitest";
import { hamilton } from "./hamilton";
import { FIXTURE } from "../fixtures";
import type { CandidateTally, Tallies } from "../types";

function makeAc(
  eci_no: number,
  candidates: CandidateTally[],
): Tallies["acs"][number] {
  return { eci_no, name: `AC${eci_no}`, electorate: 1000, candidates };
}

describe("hamilton - 3-AC fixture", () => {
  it("allocates 3 seats across FIXTURE: AIADMK=2, DMK=1, BJP=0", () => {
    const r = hamilton.apply(FIXTURE);
    const seats = (code: string) =>
      r.by_party.find((p) => p.party_eci_code === code)?.seats_won ?? 0;
    expect(seats("AIADMK")).toBe(2);
    expect(seats("DMK")).toBe(1);
    expect(seats("BJP")).toBe(0);
  });

  it("excludes NOTA from the party allocation", () => {
    const r = hamilton.apply(FIXTURE);
    expect(r.by_party.find((p) => p.party_eci_code === "NOTA")).toBeUndefined();
  });

  it("by_ac is empty (PR does not bind per-constituency)", () => {
    const r = hamilton.apply(FIXTURE);
    expect(r.by_ac).toEqual([]);
  });

  it("sum of seats_won == number of ACs (E5 invariant)", () => {
    const r = hamilton.apply(FIXTURE);
    const sum = r.by_party.reduce((s, p) => s + p.seats_won, 0);
    expect(sum).toBe(FIXTURE.acs.length);
  });
});

describe("hamilton - largest-remainder mechanics", () => {
  // Crafted to expose the largest-remainder step.
  // 3 ACs (3 seats). 3 parties:
  //   A: 500 (51% of 980 non-NOTA)
  //   B: 290 (29.6%)
  //   C: 190 (19.4%)
  //   NOTA: 20 (excluded)
  // Quota = 980/3 = 326.67.
  // Exact: A 500/326.67=1.531, B 290/326.67=0.888, C 190/326.67=0.582.
  // Integer: A=1, B=0, C=0. Allocated 1. Remaining 2.
  // Remainders: B 0.888, C 0.582, A 0.531.
  // Largest 2 remainders: B + C.
  // Final: A=1, B=1, C=1. The small parties B and C ride remainders into
  // seats; D'Hondt on the same input would give A=2, B=1, C=0.
  it("awards remainder seats to parties with the largest fractional shares", () => {
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "A", party_short: "A", name: "A1", votes: 167, party_id: "parties.IN.A" },
          { party_eci_code: "B", party_short: "B", name: "B1", votes: 97, party_id: "parties.IN.B" },
          { party_eci_code: "C", party_short: "C", name: "C1", votes: 63, party_id: "parties.IN.C" },
          { party_eci_code: "NOTA", party_short: "NOTA", name: "NOTA", votes: 7, party_id: "parties.IN.NOTA" },
        ]),
        makeAc(2, [
          { party_eci_code: "A", party_short: "A", name: "A2", votes: 167, party_id: "parties.IN.A" },
          { party_eci_code: "B", party_short: "B", name: "B2", votes: 97, party_id: "parties.IN.B" },
          { party_eci_code: "C", party_short: "C", name: "C2", votes: 63, party_id: "parties.IN.C" },
          { party_eci_code: "NOTA", party_short: "NOTA", name: "NOTA", votes: 7, party_id: "parties.IN.NOTA" },
        ]),
        makeAc(3, [
          { party_eci_code: "A", party_short: "A", name: "A3", votes: 166, party_id: "parties.IN.A" },
          { party_eci_code: "B", party_short: "B", name: "B3", votes: 96, party_id: "parties.IN.B" },
          { party_eci_code: "C", party_short: "C", name: "C3", votes: 64, party_id: "parties.IN.C" },
          { party_eci_code: "NOTA", party_short: "NOTA", name: "NOTA", votes: 6, party_id: "parties.IN.NOTA" },
        ]),
      ],
    };
    const r = hamilton.apply(tallies);
    const seats = (code: string) =>
      r.by_party.find((p) => p.party_eci_code === code)?.seats_won ?? 0;
    expect(seats("A")).toBe(1);
    expect(seats("B")).toBe(1);
    expect(seats("C")).toBe(1);
  });

  it("integer-share total matches when all parties have whole-number quotas (no remainder seats needed)", () => {
    // 6 ACs (6 seats). 2 parties exactly 50/50: A 1200, B 1200. NOTA 0.
    // Quota = 2400/6 = 400. A 1200/400=3.0, B 1200/400=3.0. Integer total 6 = total seats.
    // No remainder allocation; A=3, B=3.
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: Array.from({ length: 6 }, (_, i) =>
        makeAc(i + 1, [
          { party_eci_code: "A", party_short: "A", name: `A${i}`, votes: 200, party_id: "parties.IN.A" },
          { party_eci_code: "B", party_short: "B", name: `B${i}`, votes: 200, party_id: "parties.IN.B" },
        ]),
      ),
    };
    const r = hamilton.apply(tallies);
    const seats = (code: string) =>
      r.by_party.find((p) => p.party_eci_code === code)?.seats_won ?? 0;
    expect(seats("A")).toBe(3);
    expect(seats("B")).toBe(3);
  });
});

describe("hamilton - degenerate inputs", () => {
  it("handles an empty tally without throwing", () => {
    const r = hamilton.apply({ scope: FIXTURE.scope, acs: [] });
    expect(r.by_party).toEqual([]);
    expect(r.by_ac).toEqual([]);
    expect(r.total_votes).toBe(0);
  });

  it("returns 0 seats for everyone when all votes are NOTA", () => {
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "NOTA", party_short: "NOTA", name: "NOTA", votes: 100, party_id: "parties.IN.NOTA" },
        ]),
      ],
    };
    const r = hamilton.apply(tallies);
    // NOTA is excluded; no parties remain -> no allocation.
    expect(r.by_party).toEqual([]);
  });

  it("allocates all seats to the lone party when only one has votes", () => {
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "DMK", party_short: "DMK", name: "X", votes: 500, party_id: "parties.IN.DMK" },
          { party_eci_code: "NOTA", party_short: "NOTA", name: "NOTA", votes: 100, party_id: "parties.IN.NOTA" },
        ]),
        makeAc(2, [
          { party_eci_code: "DMK", party_short: "DMK", name: "Y", votes: 600, party_id: "parties.IN.DMK" },
        ]),
      ],
    };
    const r = hamilton.apply(tallies);
    expect(r.by_party).toHaveLength(1);
    expect(r.by_party[0].party_eci_code).toBe("DMK");
    expect(r.by_party[0].seats_won).toBe(2);
  });

  it("is deterministic across repeated invocations", () => {
    const a = hamilton.apply(FIXTURE);
    const b = hamilton.apply(FIXTURE);
    expect(a.by_party.map((p) => [p.party_eci_code, p.seats_won])).toEqual(
      b.by_party.map((p) => [p.party_eci_code, p.seats_won]),
    );
  });
});

describe("hamilton - metadata contract", () => {
  it("exposes the round-2 metadata fields", () => {
    expect(hamilton.id).toBe("proportional-hamilton");
    expect(hamilton.label).toContain("Hamilton");
    expect(hamilton.short_label).toBe("Largest Remainder PR");
    expect(hamilton.headline).toBeTruthy();
    expect(hamilton.validity).toBe("fully_workable");
    expect(hamilton.requires_banner).toBe(true);
    expect((hamilton.caveat ?? "").length).toBeGreaterThan(50);
    expect(hamilton.assumptions?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("metadata is ASCII-only", () => {
    const text = [
      hamilton.label,
      hamilton.short_label ?? "",
      hamilton.headline ?? "",
      hamilton.caveat ?? "",
      ...(hamilton.assumptions ?? []),
    ].join("\n");
    expect(Array.from(text).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});
