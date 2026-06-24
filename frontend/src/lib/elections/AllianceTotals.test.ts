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
  opts: Partial<WinnerInput> = {},
): WinnerInput => ({ party_id, party_short, ...opts });

/** Repeat a winner row `n` times (one row per won seat). */
const seats = (n: number, w: WinnerInput): WinnerInput[] =>
  Array.from({ length: n }, () => w);

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
    // CPI(M) / DMK / IND intentionally absent -> unaligned
  });

  it("ranks declared alliances as forces; small unaligned falls to Others", () => {
    // NDA 11 (8 BJP + 3 JDU), INDIA 7 (5 INC + 2 SP), CPM 2 (unaligned).
    const winners: WinnerInput[] = [
      ...seats(8, W("parties.IN.BJP", "BJP")),
      ...seats(3, W("parties.IN.JDU", "JDU")),
      ...seats(5, W("parties.IN.INC", "INC")),
      ...seats(2, W("parties.IN.SP", "SP")),
      ...seats(2, W("parties.IN.CPM", "CPI(M)")),
    ];
    const out = deriveAllianceBreakdown(winners, lookup);
    expect(out.forces.map((f) => [f.name, f.seats, f.kind])).toEqual([
      ["NDA", 11, "alliance"],
      ["INDIA", 7, "alliance"],
    ]);
    // CPM (2) is smaller than the smallest declared alliance (INDIA 7),
    // so it stays in the residual bucket.
    expect(out.others.map((p) => [p.party_short, p.seats])).toEqual([
      ["CPI(M)", 2],
    ]);
    expect(out.others_seats).toBe(2);
    expect(out.total_seats).toBe(20);
    expect(out.majority_threshold).toBe(11);
    expect(out.has_any).toBe(true);
  });

  it("promotes a large non-aligned party above the smallest declared alliance into its own force (TN-2026 fix)", () => {
    // The largest party is in NEITHER alliance. It must surface as the
    // rank-1 force, NOT be buried inside Others.
    const winners: WinnerInput[] = [
      ...seats(8, W("parties.IN.BJP", "BJP")),
      ...seats(5, W("parties.IN.INC", "INC")),
      ...seats(13, W("parties.IN.DMK", "DMK")), // unaligned, biggest
    ];
    const out = deriveAllianceBreakdown(winners, lookup);
    expect(out.forces.map((f) => [f.name, f.seats, f.kind])).toEqual([
      ["DMK", 13, "party"],
      ["NDA", 8, "alliance"],
      ["INDIA", 5, "alliance"],
    ]);
    expect(out.forces[0]!.members).toHaveLength(1);
    expect(out.others).toEqual([]);
    expect(out.others_seats).toBe(0);
  });

  it("keeps genuinely small unaligned parties in Others", () => {
    const winners: WinnerInput[] = [
      ...seats(8, W("parties.IN.BJP", "BJP")),
      ...seats(5, W("parties.IN.INC", "INC")),
      ...seats(1, W("parties.IN.IND", "IND")), // below the smallest alliance
    ];
    const out = deriveAllianceBreakdown(winners, lookup);
    expect(out.forces.map((f) => f.name)).toEqual(["NDA", "INDIA"]);
    expect(out.others.map((p) => [p.party_short, p.seats])).toEqual([
      ["IND", 1],
    ]);
    expect(out.others_seats).toBe(1);
  });

  it("computes the majority threshold as floor(total/2)+1", () => {
    const even = deriveAllianceBreakdown(
      [
        ...seats(12, W("parties.IN.BJP", "BJP")),
        ...seats(8, W("parties.IN.INC", "INC")),
      ],
      lookup,
    );
    expect(even.total_seats).toBe(20);
    expect(even.majority_threshold).toBe(11);

    const odd = deriveAllianceBreakdown(
      [
        ...seats(11, W("parties.IN.BJP", "BJP")),
        ...seats(10, W("parties.IN.INC", "INC")),
      ],
      lookup,
    );
    expect(odd.total_seats).toBe(21);
    expect(odd.majority_threshold).toBe(11);
  });

  it("has_any=false and promotes nobody when no party is in a declared alliance", () => {
    const winners: WinnerInput[] = seats(5, W("parties.IN.CPM", "CPI(M)"));
    const out = deriveAllianceBreakdown(winners, makeLookup({}));
    expect(out.has_any).toBe(false);
    expect(out.forces).toEqual([]);
    expect(out.others.map((p) => [p.party_short, p.seats])).toEqual([
      ["CPI(M)", 5],
    ]);
    expect(out.others_seats).toBe(5);
  });

  it("breaks seat ties deterministically by name ascending", () => {
    const winners: WinnerInput[] = [
      ...seats(5, W("parties.IN.BJP", "BJP")), // NDA 5
      ...seats(5, W("parties.IN.INC", "INC")), // INDIA 5
    ];
    const out = deriveAllianceBreakdown(winners, lookup);
    expect(out.forces.map((f) => f.name)).toEqual(["INDIA", "NDA"]);
  });

  it("sorts member parties within an alliance by seats desc", () => {
    const winners: WinnerInput[] = [
      ...seats(3, W("parties.IN.JDU", "JDU")),
      ...seats(8, W("parties.IN.BJP", "BJP")),
    ];
    const out = deriveAllianceBreakdown(winners, lookup);
    const nda = out.forces.find((f) => f.name === "NDA");
    expect(nda?.members.map((p) => p.party_short)).toEqual(["BJP", "JDU"]);
    expect(nda?.members.map((p) => p.seats)).toEqual([8, 3]);
  });

  it("threads brand colour + the page mute key onto each member", () => {
    const winners: WinnerInput[] = seats(
      2,
      W("parties.IN.BJP", "BJP", {
        party_eci_code: "369",
        brand_colour_hex: "#ea580c",
        brand_colour_confidence: "high",
      }),
    );
    const out = deriveAllianceBreakdown(winners, lookup);
    const bjp = out.forces[0]!.members[0]!;
    expect(bjp.brand_colour_hex).toBe("#ea580c");
    expect(bjp.brand_colour_confidence).toBe("high");
    // mute_key matches the page's hidden_parties key space
    // (party_eci_code ?? party_short).
    expect(bjp.mute_key).toBe("369");
    expect(out.forces[0]!.mute_keys).toEqual(["369"]);
  });

  it("falls back to party_short for the mute key when no eci code", () => {
    const winners: WinnerInput[] = seats(1, W("parties.IN.DMK", "DMK"));
    const out = deriveAllianceBreakdown(winners, lookup);
    // DMK is unaligned and alone -> no declared alliance, so it stays in
    // Others with mute_key = party_short.
    expect(out.others[0]!.mute_key).toBe("DMK");
  });

  it("treats null-party-id winners via partyKey fallback", () => {
    const winners: WinnerInput[] = seats(2, {
      party_id: null,
      party_short: "BJP",
      party_eci_code: "BJP",
    });
    const out = deriveAllianceBreakdown(winners, lookup);
    expect(out.forces.map((f) => [f.name, f.seats])).toEqual([["NDA", 2]]);
  });
});
