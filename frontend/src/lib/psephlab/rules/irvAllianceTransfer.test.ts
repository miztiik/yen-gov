// Unit tests for IRV with alliance-transfer.
//
// Two test modes: (a) with alliance data injected -> exercise the
// alliance-targeted transfer, (b) without -> proportional fallback
// (must match instantRunoff.ts).

import { describe, expect, it } from "vitest";
import { irvAllianceTransfer } from "./irvAllianceTransfer";
import { instantRunoff } from "./instantRunoff";
import { FIXTURE } from "../fixtures";
import type { AllianceLookup, CandidateTally, Tallies } from "../types";

function makeAc(
  eci_no: number,
  candidates: CandidateTally[],
): Tallies["acs"][number] {
  return { eci_no, name: `AC${eci_no}`, electorate: 1000, candidates };
}

describe("irvAllianceTransfer - no alliance data -> proportional fallback", () => {
  it("returns identical seats to instantRunoff when tallies.alliances is undefined", () => {
    const a = irvAllianceTransfer.apply(FIXTURE);
    const p = instantRunoff.apply(FIXTURE);
    expect(a.by_party.map((x) => [x.party_eci_code, x.seats_won])).toEqual(
      p.by_party.map((x) => [x.party_eci_code, x.seats_won]),
    );
  });

  it("returns identical seats to instantRunoff when every party returns null", () => {
    const lookup: AllianceLookup = () => null;
    const tallies: Tallies = { ...FIXTURE, alliances: lookup };
    const a = irvAllianceTransfer.apply(tallies);
    const p = instantRunoff.apply(FIXTURE);
    expect(a.by_party.map((x) => [x.party_eci_code, x.seats_won])).toEqual(
      p.by_party.map((x) => [x.party_eci_code, x.seats_won]),
    );
  });
});

describe("irvAllianceTransfer - alliance-targeted transfer", () => {
  it("eliminated INDIA-bloc votes route to the only INDIA survivor (flip)", () => {
    // AC: NDA1 400, INDIA1 350, INDIA2 250.
    // Round 1: non-NOTA total 1000. NDA1 = 400/1000 = 40% (no majority).
    //          Eliminate lowest: INDIA2 (250).
    // Alliance branch: INDIA2's 250 votes go to INDIA1 (only INDIA
    //   survivor; INDIA1 is in alliance INDIA, NDA1 is in alliance NDA).
    //   INDIA1 += 250 = 600. NDA1 stays 400.
    // Round 2: non-NOTA total 1000. INDIA1 = 600/1000 = 60% > 50%.
    //   Winner: INDIA1.
    //
    // Proportional IRV would give: INDIA2's 250 split between NDA1+INDIA1
    //   proportional to current shares -> NDA1 +250*400/750=133 -> 533;
    //   INDIA1 +250*350/750=117 -> 467. NDA1 > 50% no, 533/1000=53.3% > 50%.
    //   Winner: NDA1. FLIP confirmed.
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
          { party_eci_code: "INDIA1", party_short: "INDIA1", name: "I1", votes: 350, party_id: "parties.IN.INDIA1" },
          { party_eci_code: "INDIA2", party_short: "INDIA2", name: "I2", votes: 250, party_id: "parties.IN.INDIA2" },
        ]),
      ],
      alliances: lookup,
    };
    const a = irvAllianceTransfer.apply(tallies);
    expect(a.by_ac[0].winner.party_eci_code).toBe("INDIA1");

    // Sanity: proportional IRV picks NDA1.
    const p = instantRunoff.apply({ ...tallies, alliances: undefined });
    expect(p.by_ac[0].winner.party_eci_code).toBe("NDA1");
  });

  it("when no survivor shares the eliminated's alliance, falls back to proportional", () => {
    // AC: A 500 (alliance X), B 400 (alliance Y), C 100 (alliance Z).
    // Round 1: no majority. Eliminate C (lowest).
    // Z has no survivor -> fallback to proportional:
    //   A += 100*(500/900)=55.5 -> 555.5. B += 100*(400/900)=44.4 -> 444.4.
    // Round 2: A 555.5/1000=55.55% > 50%. Winner: A.
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
    const r = irvAllianceTransfer.apply(tallies);
    expect(r.by_ac[0].winner.party_eci_code).toBe("A");
  });

  it("multiple allies share the transfer proportionally within the pool", () => {
    // AC: NDA1 300, INDIA1 250, INDIA2 250, INDIA3 200.
    // Round 1: NDA1 300/1000 = 30% (no majority). Lowest: INDIA3 (200).
    // Alliance branch: INDIA3 -> alliance INDIA. Allies = INDIA1, INDIA2.
    //   Ally total = 250+250 = 500. INDIA3's 200 splits 50/50:
    //   INDIA1 += 100 -> 350. INDIA2 += 100 -> 350.
    // Round 2: NDA1 300, INDIA1 350, INDIA2 350. Non-NOTA total 1000.
    //   No majority. Lowest: NDA1 (300).
    // Alliance branch: NDA1 -> alliance NDA. No NDA survivors. Fallback
    //   to proportional: INDIA1 += 300*(350/700)=150 -> 500.
    //                    INDIA2 += 300*(350/700)=150 -> 500.
    // Round 3: INDIA1 500, INDIA2 500. Tie. Lowest by name ASC: INDIA1
    //   (since "INDIA1" < "INDIA2"). Wait, tie-breaking on elimination is
    //   by NAME ASC where name is the candidate name (here "I1" < "I2").
    //   Eliminate INDIA1. INDIA2 wins.
    const lookup: AllianceLookup = (id) => {
      if (id === "parties.IN.NDA1") return "NDA";
      if (id.startsWith("parties.IN.INDIA")) return "INDIA";
      return null;
    };
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "NDA1", party_short: "NDA1", name: "N1", votes: 300, party_id: "parties.IN.NDA1" },
          { party_eci_code: "INDIA1", party_short: "INDIA1", name: "I1", votes: 250, party_id: "parties.IN.INDIA1" },
          { party_eci_code: "INDIA2", party_short: "INDIA2", name: "I2", votes: 250, party_id: "parties.IN.INDIA2" },
          { party_eci_code: "INDIA3", party_short: "INDIA3", name: "I3", votes: 200, party_id: "parties.IN.INDIA3" },
        ]),
      ],
      alliances: lookup,
    };
    const r = irvAllianceTransfer.apply(tallies);
    // INDIA bloc ends with the seat; specific candidate depends on
    // tie-breaking in round 3 (INDIA2 wins after INDIA1 is eliminated).
    expect(r.by_ac[0].winner.party_eci_code.startsWith("INDIA")).toBe(true);
  });

  it("E5 invariant: sum(seats_won) == AC count", () => {
    const lookup: AllianceLookup = (id) =>
      id === "parties.IN.DMK" ? "INDIA" : id === "parties.IN.AIADMK" ? "NDA" : null;
    const tallies: Tallies = { ...FIXTURE, alliances: lookup };
    const r = irvAllianceTransfer.apply(tallies);
    const sum = r.by_party.reduce((s, p) => s + p.seats_won, 0);
    expect(sum).toBe(3);
  });
});

describe("irvAllianceTransfer - metadata contract", () => {
  it("exposes round-2 metadata fields", () => {
    expect(irvAllianceTransfer.id).toBe("ranked-choice-alliance");
    expect(irvAllianceTransfer.label).toContain("alliance");
    expect(irvAllianceTransfer.short_label).toBe("Ranked-choice (alliance)");
    expect(irvAllianceTransfer.validity).toBe("medium_validity");
    expect(irvAllianceTransfer.requires_banner).toBe(true);
    expect((irvAllianceTransfer.caveat ?? "").length).toBeGreaterThan(50);
    expect(irvAllianceTransfer.assumptions?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("metadata is ASCII-only", () => {
    const text = [
      irvAllianceTransfer.label,
      irvAllianceTransfer.short_label ?? "",
      irvAllianceTransfer.headline ?? "",
      irvAllianceTransfer.caveat ?? "",
      ...(irvAllianceTransfer.assumptions ?? []),
    ].join("\n");
    expect(Array.from(text).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});
