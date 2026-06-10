import { describe, it, expect } from "vitest";

import {
  deriveAllianceBreakdown,
  partyKey,
  type WinnerInput,
} from "./alliance-totals-model";
import type { AllianceLookup } from "../psephlab/types";

function makeLookup(map: Record<string, string>): AllianceLookup {
  return (party_id: string) => map[party_id] ?? null;
}

const W = (
  party_id: string | null,
  party_short: string | null,
): WinnerInput => ({ party_id, party_short });

describe("partyKey", () => {
  it("returns party_id verbatim when present", () => {
    expect(partyKey({ party_id: "parties.IN.BJP", party_short: "BJP" })).toBe(
      "parties.IN.BJP",
    );
  });

  it("synthesises a fallback id from eci_code/short, uppercased", () => {
    expect(
      partyKey({
        party_id: null,
        party_short: "bjp",
        party_eci_code: "BJP",
      }),
    ).toBe("parties.IN.BJP");
    expect(
      partyKey({
        party_id: null,
        party_short: "ind",
      }),
    ).toBe("parties.IN.IND");
    expect(
      partyKey({
        party_id: null,
        party_short: null,
      }),
    ).toBe("parties.IN.UNK");
  });
});

describe("deriveAllianceBreakdown", () => {
  const lookup = makeLookup({
    "parties.IN.BJP": "NDA",
    "parties.IN.INC": "INDIA",
    "parties.IN.JDU": "NDA",
    "parties.IN.SP": "INDIA",
    // CPI(M) intentionally absent -> Others
  });

  it("renders alliance-first totals NDA 11 / INDIA 7 / Others 2", () => {
    // 11 NDA seats (8 BJP + 3 JDU), 7 INDIA (5 INC + 2 SP), 2 Others (CPM)
    const winners: WinnerInput[] = [
      ...Array.from({ length: 8 }, () => W("parties.IN.BJP", "BJP")),
      ...Array.from({ length: 3 }, () => W("parties.IN.JDU", "JDU")),
      ...Array.from({ length: 5 }, () => W("parties.IN.INC", "INC")),
      ...Array.from({ length: 2 }, () => W("parties.IN.SP", "SP")),
      ...Array.from({ length: 2 }, () => W("parties.IN.CPM", "CPI(M)")),
    ];
    const out = deriveAllianceBreakdown(winners, lookup);
    expect(out.rows).toEqual([
      { alliance: "NDA", seats: 11 },
      { alliance: "INDIA", seats: 7 },
      { alliance: "Others", seats: 2 },
    ]);
    expect(out.has_any).toBe(true);
  });

  it("orders declared alliances by seats desc; Others always last", () => {
    const winners: WinnerInput[] = [
      W("parties.IN.SP", "SP"), // INDIA 1
      W("parties.IN.CPM", "CPI(M)"), // Others 1
      ...Array.from({ length: 5 }, () => W("parties.IN.BJP", "BJP")), // NDA 5
    ];
    const out = deriveAllianceBreakdown(winners, lookup);
    expect(out.rows.map((r) => r.alliance)).toEqual(["NDA", "INDIA", "Others"]);
  });

  it("buckets parties under each alliance and sorts within by seats desc", () => {
    const winners: WinnerInput[] = [
      ...Array.from({ length: 3 }, () => W("parties.IN.JDU", "JDU")),
      ...Array.from({ length: 8 }, () => W("parties.IN.BJP", "BJP")),
    ];
    const out = deriveAllianceBreakdown(winners, lookup);
    const nda = out.by_alliance.get("NDA");
    expect(nda).toBeDefined();
    expect(nda!.map((p) => p.party_short)).toEqual(["BJP", "JDU"]);
    expect(nda!.map((p) => p.seats)).toEqual([8, 3]);
  });

  it("has_any=false when every party falls under Others (no alliances)", () => {
    const winners: WinnerInput[] = [
      ...Array.from({ length: 5 }, () => W("parties.IN.CPM", "CPI(M)")),
    ];
    const empty_lookup = makeLookup({});
    const out = deriveAllianceBreakdown(winners, empty_lookup);
    expect(out.has_any).toBe(false);
    expect(out.rows).toEqual([{ alliance: "Others", seats: 5 }]);
  });

  it("omits Others entirely when every party is allied", () => {
    const winners: WinnerInput[] = [
      W("parties.IN.BJP", "BJP"),
      W("parties.IN.INC", "INC"),
    ];
    const out = deriveAllianceBreakdown(winners, lookup);
    expect(out.rows.map((r) => r.alliance)).toEqual(["NDA", "INDIA"]);
  });

  it("treats null-party-id winners via partyKey fallback", () => {
    const winners: WinnerInput[] = [
      { party_id: null, party_short: "BJP", party_eci_code: "BJP" },
      { party_id: null, party_short: "BJP", party_eci_code: "BJP" },
    ];
    const out = deriveAllianceBreakdown(winners, lookup);
    expect(out.rows).toEqual([{ alliance: "NDA", seats: 2 }]);
  });
});
