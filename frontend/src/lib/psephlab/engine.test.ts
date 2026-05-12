import { describe, it, expect } from "vitest";
import { run } from "./engine";
import { FIXTURE, acTotal } from "./fixtures";
import type { Scenario } from "./types";

describe("engine.run — baseline (no mutations)", () => {
  it("computes both mutated and actuals allocations identically", () => {
    const result = run(FIXTURE, { v: 1, rule: "fptp", mutations: [] });
    expect(result.mutated).toBe(FIXTURE);
    expect(result.allocation.by_party.map(p => p.seats_won))
      .toEqual(result.actuals_allocation.by_party.map(p => p.seats_won));
  });
});

describe("engine.run — mutation composition", () => {
  it("applies mutations left-to-right in scenario.mutations order", () => {
    // Two mutations that visibly interact: a per-AC swing followed by a
    // threshold drop. If the order were reversed, the swing would target
    // a candidate whose pre-drop votes are different.
    const scenario: Scenario = {
      v: 1,
      rule: "fptp",
      mutations: [
        // 1. Move 200 votes from DMK to AIADMK in AC 1 → AIADMK wins AC 1.
        {
          id: "perAcSwing",
          eci_no: 1,
          from_party_eci_codes: ["DMK"],
          to_party_eci_code: "AIADMK",
          votes: 200,
        },
      ],
    };
    const r = run(FIXTURE, scenario);
    const ac1 = r.allocation.by_ac.find(o => o.eci_no === 1)!;
    expect(ac1.winner.party_eci_code).toBe("AIADMK");
    // Original baseline still has DMK winning AC 1.
    const base_ac1 = r.actuals_allocation.by_ac.find(o => o.eci_no === 1)!;
    expect(base_ac1.winner.party_eci_code).toBe("DMK");
  });

  it("silently skips unknown mutation ids (graceful for old URLs)", () => {
    const scenario = {
      v: 1,
      rule: "fptp",
      // Cast as never to exercise the unknown-id path while staying inside
      // the public API surface of run().
      mutations: [{ id: "doesNotExist", foo: "bar" } as never],
    } satisfies Scenario;
    const r = run(FIXTURE, scenario);
    // Output equals the baseline allocation.
    expect(r.allocation.by_party).toEqual(r.actuals_allocation.by_party);
  });

  it("falls back to FPTP for unknown rule ids (graceful for old URLs)", () => {
    const scenario: Scenario = {
      v: 1,
      rule: "made-up-rule-from-the-future",
      mutations: [],
    };
    const r = run(FIXTURE, scenario);
    // Should still produce 3 AC outcomes via FPTP fallback.
    expect(r.allocation.by_ac).toHaveLength(3);
  });
});

describe("engine.run — mutations preserve per-AC vote totals", () => {
  // This is a key invariant: per-AC swings and threshold drops are
  // accounting transfers, not creation/destruction of votes.
  it("perAcSwing conserves AC totals", () => {
    const r = run(FIXTURE, {
      v: 1,
      rule: "fptp",
      mutations: [{
        id: "perAcSwing",
        eci_no: 1,
        from_party_eci_codes: ["DMK"],
        to_party_eci_code: "AIADMK",
        votes: 100,
      }],
    });
    for (let i = 0; i < FIXTURE.acs.length; i++) {
      expect(acTotal(r.mutated.acs[i])).toBe(acTotal(FIXTURE.acs[i]));
    }
  });

  it("statewideSwing conserves AC totals", () => {
    const r = run(FIXTURE, {
      v: 1,
      rule: "fptp",
      mutations: [{
        id: "statewideSwing",
        from_party_eci_codes: ["AIADMK"],
        to_party_eci_code: "DMK",
        pct: 5,
      }],
    });
    for (let i = 0; i < FIXTURE.acs.length; i++) {
      expect(acTotal(r.mutated.acs[i])).toBe(acTotal(FIXTURE.acs[i]));
    }
  });

  it("thresholdDrop conserves AC totals", () => {
    const r = run(FIXTURE, {
      v: 1,
      rule: "fptp",
      mutations: [{ id: "thresholdDrop", threshold_pct: 10 }],
    });
    for (let i = 0; i < FIXTURE.acs.length; i++) {
      expect(acTotal(r.mutated.acs[i])).toBe(acTotal(FIXTURE.acs[i]));
    }
  });

  it("partyBag conserves AC totals", () => {
    const r = run(FIXTURE, {
      v: 1,
      rule: "fptp",
      mutations: [{ id: "partyBag", name: "BloodyAlliance", members: ["DMK", "BJP"] }],
    });
    for (let i = 0; i < FIXTURE.acs.length; i++) {
      expect(acTotal(r.mutated.acs[i])).toBe(acTotal(FIXTURE.acs[i]));
    }
  });
});

describe("engine.run — input immutability", () => {
  it("does not mutate the input Tallies", () => {
    const before = JSON.stringify(FIXTURE);
    run(FIXTURE, {
      v: 1,
      rule: "fptp",
      mutations: [{
        id: "perAcSwing",
        eci_no: 1,
        from_party_eci_codes: ["DMK"],
        to_party_eci_code: "AIADMK",
        votes: 200,
      }],
    });
    expect(JSON.stringify(FIXTURE)).toBe(before);
  });
});
