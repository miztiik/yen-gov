import { describe, it, expect } from "vitest";
import { statewideSwing } from "./statewideSwing";
import { FIXTURE, acTotal } from "../fixtures";

function votesIn(t: typeof FIXTURE, eci_no: number, party: string): number {
  const ac = t.acs.find(a => a.eci_no === eci_no)!;
  return ac.candidates.find(c => c.party_eci_code === party)?.votes ?? 0;
}

describe("statewideSwing", () => {
  it("moves pct of each source candidate's votes to the destination, per AC", () => {
    const out = statewideSwing.apply(FIXTURE, {
      id: "statewideSwing",
      from_party_eci_codes: ["AIADMK"],
      to_party_eci_code: "DMK",
      pct: 10,
    });
    // AC1: AIADMK 300 → -30 → 270; DMK 600 → +30 → 630
    expect(votesIn(out, 1, "AIADMK")).toBe(270);
    expect(votesIn(out, 1, "DMK")).toBe(630);
    // AC2: AIADMK 700 → -70 → 630; DMK 200 → +70 → 270
    expect(votesIn(out, 2, "AIADMK")).toBe(630);
    expect(votesIn(out, 2, "DMK")).toBe(270);
  });

  it("conserves per-AC totals across every AC", () => {
    const out = statewideSwing.apply(FIXTURE, {
      id: "statewideSwing",
      from_party_eci_codes: ["AIADMK"],
      to_party_eci_code: "DMK",
      pct: 10,
    });
    for (let i = 0; i < FIXTURE.acs.length; i++) {
      expect(acTotal(out.acs[i])).toBe(acTotal(FIXTURE.acs[i]));
    }
  });

  it("is a no-op in ACs where the destination didn't contest", () => {
    const out = statewideSwing.apply(FIXTURE, {
      id: "statewideSwing",
      from_party_eci_codes: ["DMK"],
      to_party_eci_code: "BJP", // BJP missing from AC 3
      pct: 10,
    });
    // AC 3 untouched.
    expect(votesIn(out, 3, "DMK")).toBe(votesIn(FIXTURE, 3, "DMK"));
    expect(votesIn(out, 3, "AIADMK")).toBe(votesIn(FIXTURE, 3, "AIADMK"));
    // AC 1 + 2 swung.
    expect(votesIn(out, 1, "BJP")).toBeGreaterThan(votesIn(FIXTURE, 1, "BJP"));
  });

  it("supports many-to-one swings", () => {
    const out = statewideSwing.apply(FIXTURE, {
      id: "statewideSwing",
      from_party_eci_codes: ["DMK", "AIADMK"], // both donate to BJP
      to_party_eci_code: "BJP",
      pct: 10,
    });
    // AC1: DMK -60, AIADMK -30, BJP gains 90 (60+30) → 90 + 90 = 180
    expect(votesIn(out, 1, "DMK")).toBe(540);
    expect(votesIn(out, 1, "AIADMK")).toBe(270);
    expect(votesIn(out, 1, "BJP")).toBe(180);
  });

  it("is a no-op when pct <= 0", () => {
    expect(statewideSwing.apply(FIXTURE, {
      id: "statewideSwing",
      from_party_eci_codes: ["AIADMK"],
      to_party_eci_code: "DMK",
      pct: 0,
    })).toBe(FIXTURE);
  });

  it("is a no-op when sources list collapses to empty after removing dest", () => {
    expect(statewideSwing.apply(FIXTURE, {
      id: "statewideSwing",
      from_party_eci_codes: ["DMK"],
      to_party_eci_code: "DMK",
      pct: 10,
    })).toBe(FIXTURE);
  });
});

describe("statewideSwing — defaultConfig", () => {
  it("targets top-3 → top-2 (kingmaker drain) when a third party exists", () => {
    const cfg = statewideSwing.defaultConfig(FIXTURE);
    // Statewide totals: DMK=1300, AIADMK=1480, BJP=180. Sorted: AIADMK > DMK > BJP.
    // top-2 = DMK, top-3 = BJP.
    expect(cfg.to_party_eci_code).toBe("DMK");
    expect(cfg.from_party_eci_codes).toEqual(["BJP"]);
    expect(cfg.pct).toBe(0);
  });
});
