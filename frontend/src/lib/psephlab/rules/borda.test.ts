// Unit tests for the Borda Count rule (FPTP-rank proxy).
//
// FIXTURE state-wide totals (excl NOTA): DMK 1300, AIADMK 1480, BJP 180.
// Per-AC Borda contributions:
//   AC1: DMK 600 (rank 1, 3 pts), AIADMK 300 (rank 2, 2 pts), BJP 90 (rank 3, 1 pt).
//        Party Borda from AC1: DMK 3, AIADMK 2, BJP 1.
//   AC2: AIADMK 700 (1, 3), DMK 200 (2, 2), BJP 90 (3, 1).
//        Party Borda from AC2: AIADMK 3, DMK 2, BJP 1.
//   AC3: DMK 500 (1, 2), AIADMK 480 (2, 1). (Only 2 non-NOTA candidates.)
//        Party Borda from AC3: DMK 2, AIADMK 1.
// Sum: DMK 3+2+2 = 7. AIADMK 2+3+1 = 6. BJP 1+1 = 2.
//
// Sainte-Lague allocation on (DMK=7, AIADMK=6, BJP=2) for 3 seats:
//   Round 1: DMK/1=7 > AIADMK/1=6 > BJP/1=2. DMK wins. DMK=1.
//   Round 2: AIADMK/1=6 > DMK/3=2.33 > BJP/1=2. AIADMK wins. AIADMK=1.
//   Round 3: DMK/3=2.33 > BJP/1=2 > AIADMK/3=2. DMK wins. DMK=2.
// Final Borda: DMK=2, AIADMK=1, BJP=0. SAME outcome as FPTP on this fixture.

import { describe, expect, it } from "vitest";
import { borda } from "./borda";
import { FIXTURE } from "../fixtures";
import type { CandidateTally, Tallies } from "../types";

function makeAc(
  eci_no: number,
  candidates: CandidateTally[],
): Tallies["acs"][number] {
  return { eci_no, name: `AC${eci_no}`, electorate: 1000, candidates };
}

describe("borda - 3-AC fixture", () => {
  it("allocates 3 seats: DMK=2, AIADMK=1, BJP=0", () => {
    const r = borda.apply(FIXTURE);
    const seats = (code: string) =>
      r.by_party.find((p) => p.party_eci_code === code)?.seats_won ?? 0;
    expect(seats("DMK")).toBe(2);
    expect(seats("AIADMK")).toBe(1);
    expect(seats("BJP")).toBe(0);
  });

  it("excludes NOTA from the Borda calculation", () => {
    const r = borda.apply(FIXTURE);
    expect(r.by_party.find((p) => p.party_eci_code === "NOTA")).toBeUndefined();
  });

  it("by_ac is empty (Borda is state-wide PR-shaped under our proxy)", () => {
    const r = borda.apply(FIXTURE);
    expect(r.by_ac).toEqual([]);
  });

  it("sum of seats_won == number of ACs (E5 invariant)", () => {
    const r = borda.apply(FIXTURE);
    const sum = r.by_party.reduce((s, p) => s + p.seats_won, 0);
    expect(sum).toBe(3);
  });
});

describe("borda - diverges from FPTP when small parties accumulate ranks broadly", () => {
  it("Party C with no FPTP wins gains a seat under Borda by accumulating 2nd-place ranks", () => {
    // 6 ACs. A always wins (FPTP A=6, B=0, C=0). But C is consistently
    // 2nd; B is consistently 3rd. Borda points per AC: A 3, C 2, B 1.
    // State-wide Borda totals: A = 6*3 = 18; C = 6*2 = 12; B = 6*1 = 6.
    // Sainte-Lague on (A=18, C=12, B=6) for 6 seats:
    //   1. A/1=18. A=1.
    //   2. C/1=12. C=1.
    //   3. A/3=6 tie with B/1=6. A < B; A wins. A=2.
    //   4. B/1=6. B=1.
    //   5. C/3=4 vs A/5=3.6 vs B/3=2. C wins. C=2.
    //   6. A/5=3.6 vs B/3=2 vs C/5=2.4. A wins. A=3.
    // Final Borda: A=3, C=2, B=1. Versus FPTP A=6, B=0, C=0.
    // C goes from 0 to 2 seats under Borda. The Hans-defended reveal.
    const acs: Tallies["acs"] = [];
    for (let i = 1; i <= 6; i++) {
      acs.push(
        makeAc(i, [
          { party_eci_code: "A", party_short: "A", name: `A${i}`, votes: 500, party_id: "parties.IN.A" },
          { party_eci_code: "C", party_short: "C", name: `C${i}`, votes: 300, party_id: "parties.IN.C" },
          { party_eci_code: "B", party_short: "B", name: `B${i}`, votes: 200, party_id: "parties.IN.B" },
        ]),
      );
    }
    const tallies: Tallies = { scope: FIXTURE.scope, acs };
    const r = borda.apply(tallies);
    const seats = (code: string) =>
      r.by_party.find((p) => p.party_eci_code === code)?.seats_won ?? 0;
    expect(seats("A")).toBe(3);
    expect(seats("C")).toBe(2);
    expect(seats("B")).toBe(1);
  });
});

describe("borda - degenerate inputs", () => {
  it("handles an empty tally without throwing", () => {
    const r = borda.apply({ scope: FIXTURE.scope, acs: [] });
    expect(r.by_party).toEqual([]);
    expect(r.by_ac).toEqual([]);
    expect(r.total_votes).toBe(0);
  });

  it("handles a single-candidate AC (Borda points = 1)", () => {
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "DMK", party_short: "DMK", name: "D", votes: 100, party_id: "parties.IN.DMK" },
        ]),
      ],
    };
    const r = borda.apply(tallies);
    expect(r.by_party).toHaveLength(1);
    expect(r.by_party[0].seats_won).toBe(1);
  });

  it("is deterministic across repeated invocations", () => {
    const a = borda.apply(FIXTURE);
    const b = borda.apply(FIXTURE);
    expect(a.by_party.map((p) => [p.party_eci_code, p.seats_won])).toEqual(
      b.by_party.map((p) => [p.party_eci_code, p.seats_won]),
    );
  });
});

describe("borda - metadata contract", () => {
  it("exposes round-2 metadata fields", () => {
    expect(borda.id).toBe("borda");
    expect(borda.label).toContain("Borda");
    expect(borda.short_label).toBe("Borda Count");
    expect(borda.validity).toBe("medium_validity");
    expect(borda.requires_banner).toBe(true);
    expect((borda.caveat ?? "").length).toBeGreaterThan(50);
    expect(borda.assumptions?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("metadata is ASCII-only", () => {
    const text = [
      borda.label,
      borda.short_label ?? "",
      borda.headline ?? "",
      borda.caveat ?? "",
      ...(borda.assumptions ?? []),
    ].join("\n");
    expect(Array.from(text).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});
