// Unit tests for sainteLague rule (E6).
//
// Pins: state-wide PR allocation correctness against the FIXTURE +
// edge cases (empty input, single-party, ties). Also pins the
// caveat + assumptions metadata is non-empty so the banner can mount
// without runtime checks.

import { describe, it, expect } from "vitest";
import { sainteLague } from "./sainteLague";
import { FIXTURE } from "../fixtures";
import type { CandidateTally, Tallies } from "../types";

function makeAc(
  eci_no: number,
  candidates: CandidateTally[],
): Tallies["acs"][number] {
  return { eci_no, name: `AC${eci_no}`, electorate: 1000, candidates };
}

describe("sainteLague — proportional (state-wide)", () => {
  // FIXTURE totals (excl NOTA): DMK 1300, AIADMK 1480, BJP 180. Seats = 3.
  // Round 1: max quotient AIADMK 1480/1 = 1480 -> AIADMK gets 1.
  // Round 2: max quotient DMK 1300/1 = 1300 (AIADMK now 1480/3 = 493.33) -> DMK gets 1.
  // Round 3: max quotient AIADMK 1480/3 = 493.33 (DMK now 1300/3 = 433.33,
  //          BJP 180/1 = 180) -> AIADMK gets second seat.
  // Final: AIADMK 2, DMK 1, BJP 0.
  it("allocates 3 seats across FIXTURE: AIADMK=2, DMK=1, BJP=0", () => {
    const r = sainteLague.apply(FIXTURE);
    const seats = (code: string) =>
      r.by_party.find((p) => p.party_eci_code === code)?.seats_won ?? 0;
    expect(seats("AIADMK")).toBe(2);
    expect(seats("DMK")).toBe(1);
    expect(seats("BJP")).toBe(0);
  });

  it("excludes NOTA from the party allocation entirely", () => {
    const r = sainteLague.apply(FIXTURE);
    expect(r.by_party.find((p) => p.party_eci_code === "NOTA")).toBeUndefined();
  });

  it("by_ac is empty (PR does not bind per-constituency)", () => {
    const r = sainteLague.apply(FIXTURE);
    expect(r.by_ac).toEqual([]);
  });

  it("sum of seats_won across parties == number of ACs (E5 invariant green)", () => {
    const r = sainteLague.apply(FIXTURE);
    const sum = r.by_party.reduce((s, p) => s + p.seats_won, 0);
    expect(sum).toBe(FIXTURE.acs.length);
  });

  it("total_votes counts every cast vote, NOTA included (mirrors fptp.ts)", () => {
    const r = sainteLague.apply(FIXTURE);
    expect(r.total_votes).toBe(3000); // 1000 + 1000 + 1000 from FIXTURE
  });

  it("handles an empty tally without throwing", () => {
    const r = sainteLague.apply({ scope: FIXTURE.scope, acs: [] });
    expect(r.by_party).toEqual([]);
    expect(r.by_ac).toEqual([]);
    expect(r.total_votes).toBe(0);
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
    const r = sainteLague.apply(tallies);
    expect(r.by_party).toHaveLength(1);
    expect(r.by_party[0].party_eci_code).toBe("DMK");
    expect(r.by_party[0].seats_won).toBe(2);
  });

  it("is deterministic across repeated invocations on the same input", () => {
    const a = sainteLague.apply(FIXTURE);
    const b = sainteLague.apply(FIXTURE);
    expect(a.by_party.map((p) => [p.party_eci_code, p.seats_won])).toEqual(
      b.by_party.map((p) => [p.party_eci_code, p.seats_won]),
    );
  });

  it("exposes caveat + assumptions + requires_banner metadata", () => {
    expect(sainteLague.requires_banner).toBe(true);
    expect(sainteLague.caveat ?? "").not.toBe("");
    expect(sainteLague.assumptions?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("caveat + assumptions are ASCII-only (no curly quotes / em-dash / emoji)", () => {
    const allText = [sainteLague.caveat ?? "", ...(sainteLague.assumptions ?? []), sainteLague.label].join(
      "\n",
    );
    expect(Array.from(allText).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});
