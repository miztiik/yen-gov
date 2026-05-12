import { describe, it, expect } from "vitest";
import { fptp } from "./fptp";
import { FIXTURE } from "../fixtures";
import type { CandidateTally, Tallies } from "../types";

function ac(eci_no: number, candidates: CandidateTally[]): Tallies["acs"][number] {
  return { eci_no, name: `AC${eci_no}`, electorate: 1000, candidates };
}

describe("fptp — basic counting", () => {
  const result = fptp.apply(FIXTURE);

  it("totals all votes across all ACs", () => {
    expect(result.total_votes).toBe(3000);
  });

  it("declares a winner per AC (3 ACs → 3 outcomes)", () => {
    expect(result.by_ac).toHaveLength(3);
  });

  it("DMK wins AC 1 (600 vs AIADMK 300)", () => {
    const ac1 = result.by_ac.find(o => o.eci_no === 1)!;
    expect(ac1.winner.party_eci_code).toBe("DMK");
    expect(ac1.runner_up?.party_eci_code).toBe("AIADMK");
    expect(ac1.margin_votes).toBe(300);
    expect(ac1.margin_pct).toBeCloseTo(30, 5);
  });

  it("AIADMK wins AC 2", () => {
    const ac2 = result.by_ac.find(o => o.eci_no === 2)!;
    expect(ac2.winner.party_eci_code).toBe("AIADMK");
  });

  it("aggregates seats: DMK=2, AIADMK=1, BJP=0, NOTA=0", () => {
    const seats = Object.fromEntries(result.by_party.map(p => [p.party_eci_code, p.seats_won]));
    expect(seats.DMK).toBe(2);
    expect(seats.AIADMK).toBe(1);
    expect(seats.BJP).toBe(0);
    expect(seats.NOTA).toBe(0);
  });

  it("vote shares sum to 100 (within rounding)", () => {
    const sum = result.by_party.reduce((s, p) => s + p.vote_share_pct, 0);
    expect(sum).toBeCloseTo(100, 5);
  });

  it("orders by_party by seats DESC, then votes DESC, then party_short ASC", () => {
    const out = result.by_party.map(p => p.party_short);
    // DMK (2 seats) > AIADMK (1 seat) > {AIADMK 1480, BJP 180, NOTA 40} sorted by votes DESC
    expect(out[0]).toBe("DMK");
    expect(out[1]).toBe("AIADMK");
    // BJP (180 votes) before NOTA (40 votes).
    expect(out.indexOf("BJP")).toBeLessThan(out.indexOf("NOTA"));
  });
});

describe("fptp — NOTA cannot win a seat", () => {
  it("treats highest non-NOTA as the effective winner if NOTA polls highest", () => {
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        ac(1, [
          { party_eci_code: "NOTA",   party_short: "NOTA",   name: "NOTA", votes: 500 },
          { party_eci_code: "DMK",    party_short: "DMK",    name: "X",    votes: 300 },
          { party_eci_code: "AIADMK", party_short: "AIADMK", name: "Y",    votes: 200 },
        ]),
      ],
    };
    const r = fptp.apply(tallies);
    expect(r.by_ac[0].winner.party_eci_code).toBe("DMK");
    expect(r.by_ac[0].runner_up?.party_eci_code).toBe("AIADMK");
    const seats = Object.fromEntries(r.by_party.map(p => [p.party_eci_code, p.seats_won]));
    expect(seats.NOTA).toBe(0);
    expect(seats.DMK).toBe(1);
  });
});

describe("fptp — ties", () => {
  it("breaks ties by candidate name ascending", () => {
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        ac(1, [
          { party_eci_code: "DMK",    party_short: "DMK",    name: "Zebra",   votes: 500 },
          { party_eci_code: "AIADMK", party_short: "AIADMK", name: "Alpha",   votes: 500 },
        ]),
      ],
    };
    const r = fptp.apply(tallies);
    expect(r.by_ac[0].winner.name).toBe("Alpha");
  });
});

describe("fptp — degenerate inputs", () => {
  it("returns 0 outcomes for an empty AC list", () => {
    const r = fptp.apply({ scope: FIXTURE.scope, acs: [] });
    expect(r.by_ac).toEqual([]);
    expect(r.total_votes).toBe(0);
    expect(r.by_party).toEqual([]);
  });

  it("skips an AC with no candidates", () => {
    const r = fptp.apply({ scope: FIXTURE.scope, acs: [ac(7, [])] });
    expect(r.by_ac).toEqual([]);
  });

  it("does not divide by zero when all AC votes are 0", () => {
    const r = fptp.apply({
      scope: FIXTURE.scope,
      acs: [ac(1, [
        { party_eci_code: "DMK",    party_short: "DMK",    name: "A", votes: 0 },
        { party_eci_code: "AIADMK", party_short: "AIADMK", name: "B", votes: 0 },
      ])],
    });
    expect(r.by_ac[0].margin_pct).toBe(0);
    expect(r.by_party.every(p => p.vote_share_pct === 0)).toBe(true);
  });
});
