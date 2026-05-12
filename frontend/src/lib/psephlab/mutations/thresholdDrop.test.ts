import { describe, it, expect } from "vitest";
import { thresholdDrop } from "./thresholdDrop";
import { FIXTURE, acTotal } from "../fixtures";
import type { Tallies } from "../types";

function votesIn(t: Tallies, eci_no: number, party: string): number {
  const ac = t.acs.find(a => a.eci_no === eci_no)!;
  return ac.candidates.find(c => c.party_eci_code === party)?.votes ?? 0;
}

describe("thresholdDrop", () => {
  it("drops candidates below the threshold and redistributes proportionally", () => {
    // AC1 totals 1000. At 10%: BJP (90, 9%) is below; NOTA (10) is exempt.
    // Survivors: DMK 600, AIADMK 300 → pool 900. Freed = 90.
    // DMK gains round(600/900 * 90) = 60; AIADMK gains round(300/900 * 90) = 30.
    const out = thresholdDrop.apply(FIXTURE, { id: "thresholdDrop", threshold_pct: 10 });
    expect(votesIn(out, 1, "BJP")).toBe(0);
    expect(votesIn(out, 1, "DMK")).toBe(660);
    expect(votesIn(out, 1, "AIADMK")).toBe(330);
    // NOTA exempt: never gains, never loses.
    expect(votesIn(out, 1, "NOTA")).toBe(10);
  });

  it("conserves per-AC totals exactly (rounding drift absorbed by largest survivor)", () => {
    const out = thresholdDrop.apply(FIXTURE, { id: "thresholdDrop", threshold_pct: 10 });
    for (let i = 0; i < FIXTURE.acs.length; i++) {
      expect(acTotal(out.acs[i])).toBe(acTotal(FIXTURE.acs[i]));
    }
  });

  it("never drops NOTA even when its share is below threshold", () => {
    // NOTA in AC 1 polls 1% → well below any threshold.
    const out = thresholdDrop.apply(FIXTURE, { id: "thresholdDrop", threshold_pct: 50 });
    expect(votesIn(out, 1, "NOTA")).toBe(10);
  });

  it("is a no-op when threshold_pct <= 0", () => {
    expect(thresholdDrop.apply(FIXTURE, { id: "thresholdDrop", threshold_pct: 0 })).toBe(FIXTURE);
  });

  it("leaves an AC untouched when nothing is below the threshold", () => {
    // AC 3 candidates: DMK 50%, AIADMK 48%, NOTA 2%. NOTA is exempt;
    // at 1% threshold no non-NOTA candidate is below.
    const out = thresholdDrop.apply(FIXTURE, { id: "thresholdDrop", threshold_pct: 1 });
    expect(out.acs[2]).toBe(FIXTURE.acs[2]);
  });
});
