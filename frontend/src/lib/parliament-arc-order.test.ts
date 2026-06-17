import { describe, it, expect } from "vitest";
import { orderArcParties } from "./parliament-arc-order";

interface P {
  party_short: string;
  seats_won: number;
}
const p = (party_short: string, seats_won: number): P => ({ party_short, seats_won });

describe("orderArcParties", () => {
  it("orders by seats descending when no alliance resolver is given", () => {
    const out = orderArcParties([p("A", 5), p("C", 20), p("B", 12)]);
    expect(out.map((x) => x.party_short)).toEqual(["C", "B", "A"]);
  });

  it("drops zero-seat parties", () => {
    const out = orderArcParties([p("A", 0), p("B", 3)]);
    expect(out.map((x) => x.party_short)).toEqual(["B"]);
  });

  it("breaks seat ties by party_short alphabetical", () => {
    const out = orderArcParties([p("Z", 4), p("A", 4)]);
    expect(out.map((x) => x.party_short)).toEqual(["A", "Z"]);
  });

  it("groups by alliance: blocs by total seats desc, parties within by seats desc", () => {
    // NDA = BJP(240)+JDU(12) = 252; INDIA = INC(99)+SP(37) = 136; unaligned IND(7)
    const parties = [
      p("INC", 99),
      p("BJP", 240),
      p("IND", 7),
      p("JDU", 12),
      p("SP", 37),
    ];
    const alliance: Record<string, string | null> = {
      BJP: "NDA",
      JDU: "NDA",
      INC: "INDIA",
      SP: "INDIA",
      IND: null,
    };
    const out = orderArcParties(parties, (x) => alliance[x.party_short] ?? null);
    // NDA bloc first (BJP, JDU), then INDIA bloc (INC, SP), then unaligned IND last
    expect(out.map((x) => x.party_short)).toEqual(["BJP", "JDU", "INC", "SP", "IND"]);
  });

  it("places unaligned parties last even when individually large", () => {
    // A big unaligned party must still trail the smaller aligned bloc.
    const parties = [p("BIG", 100), p("X", 30), p("Y", 25)];
    const alliance: Record<string, string | null> = { X: "BLOC", Y: "BLOC", BIG: null };
    const out = orderArcParties(parties, (x) => alliance[x.party_short] ?? null);
    expect(out.map((x) => x.party_short)).toEqual(["X", "Y", "BIG"]);
  });

  it("preserves the exact seat total across the reordering", () => {
    const parties = [p("A", 5), p("B", 12), p("C", 20)];
    const before = parties.reduce((s, x) => s + x.seats_won, 0);
    const after = orderArcParties(parties, () => "ONE").reduce((s, x) => s + x.seats_won, 0);
    expect(after).toBe(before);
  });
});
