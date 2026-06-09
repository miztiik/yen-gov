// Unit tests for TRS Round 2 (alliance pool).
//
// Two test modes: (a) with alliance data injected -> exercise the
// alliance-pool transfer, (b) without alliance data -> exercise the
// proportional fallback (must match trsRound2.ts output exactly).

import { describe, expect, it } from "vitest";
import { trsRound2Alliance } from "./trsRound2Alliance";
import { trsRound2 } from "./trsRound2";
import { FIXTURE } from "../fixtures";
import type { AllianceLookup, CandidateTally, Tallies } from "../types";

function makeAc(
  eci_no: number,
  candidates: CandidateTally[],
): Tallies["acs"][number] {
  return { eci_no, name: `AC${eci_no}`, electorate: 1000, candidates };
}

describe("trsRound2Alliance - no alliance data -> proportional fallback", () => {
  it("returns identical seats to trsRound2 when tallies.alliances is undefined", () => {
    const a = trsRound2Alliance.apply(FIXTURE);
    const p = trsRound2.apply(FIXTURE);
    expect(a.by_party.map((x) => [x.party_eci_code, x.seats_won])).toEqual(
      p.by_party.map((x) => [x.party_eci_code, x.seats_won]),
    );
  });

  it("returns identical seats to trsRound2 when every party returns null", () => {
    const lookup: AllianceLookup = () => null;
    const tallies: Tallies = { ...FIXTURE, alliances: lookup };
    const a = trsRound2Alliance.apply(tallies);
    const p = trsRound2.apply(FIXTURE);
    expect(a.by_party.map((x) => [x.party_eci_code, x.seats_won])).toEqual(
      p.by_party.map((x) => [x.party_eci_code, x.seats_won]),
    );
  });
});

describe("trsRound2Alliance - alliance-pool transfer", () => {
  it("eliminated INDIA-bloc votes route 100% to the INDIA survivor (flip)", () => {
    // AC: NDA1 400, INDIA1 380, INDIA2 220.
    // Top 2 = NDA1, INDIA1. Eliminated = INDIA2 (220).
    // Proportional rule would give: NDA1 += 220*(400/780) = 112.8 -> 512.8.
    //                               INDIA1 += 220*(380/780) = 107.2 -> 487.2.
    //                               Winner: NDA1.
    // Alliance rule: INDIA2's 220 votes all go to INDIA1 (the INDIA survivor).
    //                NDA1 stays at 400.
    //                INDIA1 += 220 = 600.
    //                Winner: INDIA1 (FLIP from proportional).
    const lookup: AllianceLookup = (id) => {
      if (id === "parties.IN.NDA1") return "NDA";
      if (id === "parties.IN.INDIA1") return "INDIA";
      if (id === "parties.IN.INDIA2") return "INDIA";
      return null;
    };
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "NDA1", party_short: "NDA1", name: "N1", votes: 400, party_id: "parties.IN.NDA1" },
          { party_eci_code: "INDIA1", party_short: "INDIA1", name: "I1", votes: 380, party_id: "parties.IN.INDIA1" },
          { party_eci_code: "INDIA2", party_short: "INDIA2", name: "I2", votes: 220, party_id: "parties.IN.INDIA2" },
        ]),
      ],
      alliances: lookup,
    };
    const a = trsRound2Alliance.apply(tallies);
    expect(a.by_ac[0].winner.party_eci_code).toBe("INDIA1");

    // Sanity check that proportional gives the OTHER answer on the same input.
    const p = trsRound2.apply({ ...tallies, alliances: undefined });
    expect(p.by_ac[0].winner.party_eci_code).toBe("NDA1");
  });

  it("when neither top 2 is in the eliminated's alliance, falls back to proportional", () => {
    // AC: A 500 (alliance X), B 400 (alliance Y), C 100 (alliance Z).
    // Top 2: A, B. Eliminated C (alliance Z; no survivor in Z).
    // Proportional fallback for C: A += 100*(500/900)=55.5 -> 555.5;
    //                               B += 100*(400/900)=44.4 -> 444.4.
    // Winner: A.
    const lookup: AllianceLookup = (id) => {
      if (id === "parties.IN.A") return "X";
      if (id === "parties.IN.B") return "Y";
      if (id === "parties.IN.C") return "Z";
      return null;
    };
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "A", party_short: "A", name: "A1", votes: 500, party_id: "parties.IN.A" },
          { party_eci_code: "B", party_short: "B", name: "B1", votes: 400, party_id: "parties.IN.B" },
          { party_eci_code: "C", party_short: "C", name: "C1", votes: 100, party_id: "parties.IN.C" },
        ]),
      ],
      alliances: lookup,
    };
    const r = trsRound2Alliance.apply(tallies);
    expect(r.by_ac[0].winner.party_eci_code).toBe("A");
  });

  it("when both top 2 are in the eliminated's alliance, splits proportionally within the pool", () => {
    // AC: A 500 (alliance X), B 400 (alliance X), C 100 (alliance X).
    // Top 2: A, B (both X). Eliminated C 100 (also X).
    // Per code: both survivors share alliance with C -> split proportionally.
    //   A += 100*(500/900) = 55.5 -> 555.5
    //   B += 100*(400/900) = 44.4 -> 444.4
    // Winner: A.
    const lookup: AllianceLookup = (_id) => "X";
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "A", party_short: "A", name: "A1", votes: 500, party_id: "parties.IN.A" },
          { party_eci_code: "B", party_short: "B", name: "B1", votes: 400, party_id: "parties.IN.B" },
          { party_eci_code: "C", party_short: "C", name: "C1", votes: 100, party_id: "parties.IN.C" },
        ]),
      ],
      alliances: lookup,
    };
    const r = trsRound2Alliance.apply(tallies);
    expect(r.by_ac[0].winner.party_eci_code).toBe("A");
  });

  it("E5 invariant: sum(seats_won) == AC count", () => {
    const lookup: AllianceLookup = (id) =>
      id === "parties.IN.DMK" ? "INDIA" : id === "parties.IN.AIADMK" ? "NDA" : null;
    const tallies: Tallies = { ...FIXTURE, alliances: lookup };
    const r = trsRound2Alliance.apply(tallies);
    const sum = r.by_party.reduce((s, p) => s + p.seats_won, 0);
    expect(sum).toBe(3);
  });
});

describe("trsRound2Alliance - metadata contract", () => {
  it("exposes round-2 metadata fields", () => {
    expect(trsRound2Alliance.id).toBe("trs-round-2-alliance");
    expect(trsRound2Alliance.label).toContain("alliance");
    expect(trsRound2Alliance.short_label).toBe("Top-2 Runoff (alliance)");
    expect(trsRound2Alliance.validity).toBe("medium_validity");
    expect(trsRound2Alliance.requires_banner).toBe(true);
    expect((trsRound2Alliance.caveat ?? "").length).toBeGreaterThan(50);
    expect(trsRound2Alliance.assumptions?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("metadata is ASCII-only", () => {
    const text = [
      trsRound2Alliance.label,
      trsRound2Alliance.short_label ?? "",
      trsRound2Alliance.headline ?? "",
      trsRound2Alliance.caveat ?? "",
      ...(trsRound2Alliance.assumptions ?? []),
    ].join("\n");
    expect(Array.from(text).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});
