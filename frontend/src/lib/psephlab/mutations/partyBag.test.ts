import { describe, it, expect } from "vitest";
import { partyBag, bagCode } from "./partyBag";
import { FIXTURE, acTotal } from "../fixtures";
import type { Tallies } from "../types";

function findCandidate(t: Tallies, eci_no: number, party: string) {
  const ac = t.acs.find(a => a.eci_no === eci_no)!;
  return ac.candidates.find(c => c.party_eci_code === party);
}

describe("bagCode", () => {
  it("prefixes the bag name with 'bag:'", () => {
    expect(bagCode("Alliance")).toBe("bag:Alliance");
  });
});

describe("partyBag", () => {
  it("merges members into one synthetic candidate per AC", () => {
    const out = partyBag.apply(FIXTURE, {
      id: "partyBag",
      name: "Bloc",
      members: ["DMK", "BJP"],
    });
    // AC 1: DMK 600 + BJP 90 = 690 pooled into bag.
    const bag = findCandidate(out, 1, "bag:Bloc")!;
    expect(bag).toBeDefined();
    expect(bag.votes).toBe(690);
    // Members are removed from the AC.
    expect(findCandidate(out, 1, "DMK")).toBeUndefined();
    expect(findCandidate(out, 1, "BJP")).toBeUndefined();
    // Non-member candidates remain.
    expect(findCandidate(out, 1, "AIADMK")?.votes).toBe(300);
    expect(findCandidate(out, 1, "NOTA")?.votes).toBe(10);
  });

  it("conserves per-AC totals", () => {
    const out = partyBag.apply(FIXTURE, {
      id: "partyBag",
      name: "Bloc",
      members: ["DMK", "BJP"],
    });
    for (let i = 0; i < FIXTURE.acs.length; i++) {
      expect(acTotal(out.acs[i])).toBe(acTotal(FIXTURE.acs[i]));
    }
  });

  it("uses the single member's name as the bag candidate's name when only one member is present in an AC", () => {
    // AC 3 has no BJP candidate; bagging DMK + BJP in AC 3 only pools DMK.
    const out = partyBag.apply(FIXTURE, {
      id: "partyBag",
      name: "Bloc",
      members: ["DMK", "BJP"],
    });
    const bag = findCandidate(out, 3, "bag:Bloc")!;
    expect(bag.name).toBe("C1"); // the only DMK candidate name in AC 3
  });

  it("uses '<name> (N)' when multiple members are present", () => {
    const out = partyBag.apply(FIXTURE, {
      id: "partyBag",
      name: "Bloc",
      members: ["DMK", "BJP"],
    });
    const bag = findCandidate(out, 1, "bag:Bloc")!;
    expect(bag.name).toBe("Bloc (2)");
  });

  it("is a no-op when name is empty or members list is empty", () => {
    expect(partyBag.apply(FIXTURE, { id: "partyBag", name: "", members: ["DMK"] })).toBe(FIXTURE);
    expect(partyBag.apply(FIXTURE, { id: "partyBag", name: "X", members: [] })).toBe(FIXTURE);
  });

  it("leaves an AC untouched when no member parties are present in it", () => {
    const out = partyBag.apply(FIXTURE, {
      id: "partyBag",
      name: "Bloc",
      members: ["XYZ", "ABC"], // neither contests
    });
    expect(out.acs[0]).toBe(FIXTURE.acs[0]);
  });
});
