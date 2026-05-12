import { describe, it, expect } from "vitest";
import { perAcSwing } from "./perAcSwing";
import { FIXTURE, acTotal } from "../fixtures";

function votesIn(t: typeof FIXTURE, eci_no: number, party: string): number {
  const ac = t.acs.find(a => a.eci_no === eci_no)!;
  return ac.candidates.find(c => c.party_eci_code === party)?.votes ?? 0;
}

describe("perAcSwing", () => {
  it("moves the requested votes from a single source to the destination", () => {
    const out = perAcSwing.apply(FIXTURE, {
      id: "perAcSwing",
      eci_no: 1,
      from_party_eci_codes: ["DMK"],
      to_party_eci_code: "AIADMK",
      votes: 100,
    });
    expect(votesIn(out, 1, "DMK")).toBe(500);
    expect(votesIn(out, 1, "AIADMK")).toBe(400);
    // Other ACs unchanged.
    expect(votesIn(out, 2, "DMK")).toBe(votesIn(FIXTURE, 2, "DMK"));
  });

  it("conserves the AC total", () => {
    const out = perAcSwing.apply(FIXTURE, {
      id: "perAcSwing",
      eci_no: 1,
      from_party_eci_codes: ["DMK"],
      to_party_eci_code: "AIADMK",
      votes: 100,
    });
    expect(acTotal(out.acs[0])).toBe(acTotal(FIXTURE.acs[0]));
  });

  it("clamps to source capacity instead of going negative", () => {
    const out = perAcSwing.apply(FIXTURE, {
      id: "perAcSwing",
      eci_no: 1,
      from_party_eci_codes: ["BJP"], // BJP only has 90 votes in AC 1
      to_party_eci_code: "DMK",
      votes: 1000,
    });
    expect(votesIn(out, 1, "BJP")).toBe(0);
    expect(votesIn(out, 1, "DMK")).toBe(600 + 90);
  });

  it("pulls many-to-one proportionally from multiple sources", () => {
    const out = perAcSwing.apply(FIXTURE, {
      id: "perAcSwing",
      eci_no: 1,
      from_party_eci_codes: ["DMK", "AIADMK"], // pool = 600+300 = 900
      to_party_eci_code: "BJP",
      votes: 90, // 10% of pool → 60 from DMK, 30 from AIADMK
    });
    expect(votesIn(out, 1, "DMK")).toBe(540);
    expect(votesIn(out, 1, "AIADMK")).toBe(270);
    expect(votesIn(out, 1, "BJP")).toBe(180);
  });

  it("is a no-op when votes <= 0", () => {
    expect(perAcSwing.apply(FIXTURE, {
      id: "perAcSwing",
      eci_no: 1,
      from_party_eci_codes: ["DMK"],
      to_party_eci_code: "AIADMK",
      votes: 0,
    })).toBe(FIXTURE);
  });

  it("is a no-op when destination party isn't on the AC ballot", () => {
    const out = perAcSwing.apply(FIXTURE, {
      id: "perAcSwing",
      eci_no: 3, // AC 3 has no BJP candidate
      from_party_eci_codes: ["DMK"],
      to_party_eci_code: "BJP",
      votes: 50,
    });
    expect(votesIn(out, 3, "DMK")).toBe(votesIn(FIXTURE, 3, "DMK"));
  });

  it("is a no-op when the source list is empty after removing the destination", () => {
    const out = perAcSwing.apply(FIXTURE, {
      id: "perAcSwing",
      eci_no: 1,
      from_party_eci_codes: ["DMK"],
      to_party_eci_code: "DMK", // source == dest → filtered out
      votes: 50,
    });
    expect(out).toBe(FIXTURE);
  });
});
