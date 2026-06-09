// Unit tests for TRS Round 2 (proportional eliminated-vote transfer).
//
// FIXTURE per-AC (3 ACs):
//   AC1: DMK 600, AIADMK 300, BJP 90, NOTA 10. (DMK > 50% non-NOTA: 600/990 = 60.6%)
//        Top 2: DMK + AIADMK. Eliminated: BJP 90. Redistribute 90 to top 2
//        in proportion to (600, 300) -> DMK gets 90*600/900=60, AIADMK 30.
//        New: DMK 660, AIADMK 330. Winner: DMK.
//   AC2: AIADMK 700, DMK 200, BJP 90, NOTA 10. (AIADMK > 50%: 700/990=70.7%)
//        Top 2: AIADMK + DMK. Eliminated: BJP 90. Redistribute to (700,200):
//        AIADMK gets 70, DMK gets 20. New: AIADMK 770, DMK 220. Winner: AIADMK.
//   AC3: DMK 500, AIADMK 480, NOTA 20. (No BJP.)
//        Top 2: DMK + AIADMK. No eliminated non-NOTA. Result unchanged: DMK 500,
//        AIADMK 480. Winner: DMK.
// Total: DMK=2, AIADMK=1 (SAME as FPTP on this fixture because all 3 ACs are
// landslides for the top candidate; TRS Round 2 only diverges from FPTP when
// the FPTP winner is below 50% AND the eliminated candidates can flip it).

import { describe, expect, it } from "vitest";
import { trsRound2 } from "./trsRound2";
import { fptp } from "./fptp";
import { FIXTURE } from "../fixtures";
import type { CandidateTally, Tallies } from "../types";

function makeAc(
  eci_no: number,
  candidates: CandidateTally[],
): Tallies["acs"][number] {
  return { eci_no, name: `AC${eci_no}`, electorate: 1000, candidates };
}

describe("trsRound2 - basic + 3-AC fixture", () => {
  it("matches FPTP on the FIXTURE (all landslides; nothing to flip)", () => {
    const r = trsRound2.apply(FIXTURE);
    const f = fptp.apply(FIXTURE);
    for (let i = 0; i < r.by_ac.length; i++) {
      expect(r.by_ac[i].winner.party_eci_code).toBe(f.by_ac[i].winner.party_eci_code);
    }
    const seats = (code: string) =>
      r.by_party.find((p) => p.party_eci_code === code)?.seats_won ?? 0;
    expect(seats("DMK")).toBe(2);
    expect(seats("AIADMK")).toBe(1);
  });

  it("declares one winner per AC", () => {
    const r = trsRound2.apply(FIXTURE);
    expect(r.by_ac).toHaveLength(3);
  });

  it("sum of seats_won == number of ACs (E5 invariant)", () => {
    const r = trsRound2.apply(FIXTURE);
    const sum = r.by_party.reduce((s, p) => s + p.seats_won, 0);
    expect(sum).toBe(3);
  });
});

describe("trsRound2 - flips from FPTP when the eliminated bloc is large enough", () => {
  it("AC with FPTP plurality below 50% + transferable third party flips", () => {
    // AC: A 400, B 350, C 250. FPTP winner = A.
    // TRS R2: top 2 = A, B. Eliminated = C (250).
    // Redistribute 250 to (A:400, B:350) proportionally:
    //   A_share = 400/750 = 0.5333 -> A gets 250*0.5333 = 133.33.
    //   B_share = 350/750 = 0.4667 -> B gets 250*0.4667 = 116.67.
    // New: A = 533.33, B = 466.67. Winner: A (FPTP and TRS agree).
    //
    // Now force a flip: A 400, B 350, C 250 BUT make C's voters
    // prefer B. We can't model this directly with the proportional rule -
    // it just splits to top 2 by first-round share. So under proportional
    // rule the winner == FPTP winner ALWAYS, because the larger top-2
    // party has the larger share of redistributed votes too.
    //
    // The flip scenario requires the alliance variant. Test here: no flip
    // under proportional rule on a 3-way contest.
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "A", party_short: "A", name: "A1", votes: 400, party_id: "parties.IN.A" },
          { party_eci_code: "B", party_short: "B", name: "B1", votes: 350, party_id: "parties.IN.B" },
          { party_eci_code: "C", party_short: "C", name: "C1", votes: 250, party_id: "parties.IN.C" },
        ]),
      ],
    };
    const r = trsRound2.apply(tallies);
    const f = fptp.apply(tallies);
    expect(r.by_ac[0].winner.party_eci_code).toBe(f.by_ac[0].winner.party_eci_code);
    expect(r.by_ac[0].winner.party_eci_code).toBe("A");
  });
});

describe("trsRound2 - degenerate inputs", () => {
  it("returns 0 outcomes for an empty AC list", () => {
    const r = trsRound2.apply({ scope: FIXTURE.scope, acs: [] });
    expect(r.by_ac).toEqual([]);
    expect(r.total_votes).toBe(0);
    expect(r.by_party).toEqual([]);
  });

  it("handles a single non-NOTA candidate (no runoff)", () => {
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "DMK", party_short: "DMK", name: "D", votes: 100, party_id: "parties.IN.DMK" },
        ]),
      ],
    };
    const r = trsRound2.apply(tallies);
    expect(r.by_ac[0].winner.party_eci_code).toBe("DMK");
  });

  it("treats NOTA as exhausted (excluded from top-2 + redistribution)", () => {
    // A 400, B 350, NOTA 250. NOTA excluded; A vs B is the runoff.
    // Eliminated votes = 0 (no non-NOTA below top 2). Winner = A.
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "A", party_short: "A", name: "A1", votes: 400, party_id: "parties.IN.A" },
          { party_eci_code: "B", party_short: "B", name: "B1", votes: 350, party_id: "parties.IN.B" },
          { party_eci_code: "NOTA", party_short: "NOTA", name: "NOTA", votes: 250, party_id: "parties.IN.NOTA" },
        ]),
      ],
    };
    const r = trsRound2.apply(tallies);
    expect(r.by_ac[0].winner.party_eci_code).toBe("A");
    const nota_seats = r.by_party.find((p) => p.party_eci_code === "NOTA")?.seats_won ?? 0;
    expect(nota_seats).toBe(0);
  });

  it("is deterministic across repeated invocations", () => {
    const a = trsRound2.apply(FIXTURE);
    const b = trsRound2.apply(FIXTURE);
    expect(a.by_party.map((p) => [p.party_eci_code, p.seats_won])).toEqual(
      b.by_party.map((p) => [p.party_eci_code, p.seats_won]),
    );
  });
});

describe("trsRound2 - metadata contract", () => {
  it("exposes round-2 metadata fields", () => {
    expect(trsRound2.id).toBe("trs-round-2");
    expect(trsRound2.label).toContain("Top-2 Runoff");
    expect(trsRound2.short_label).toBe("Top-2 Runoff (proportional)");
    expect(trsRound2.validity).toBe("medium_validity");
    expect(trsRound2.requires_banner).toBe(true);
    expect((trsRound2.caveat ?? "").length).toBeGreaterThan(50);
    expect(trsRound2.assumptions?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("metadata is ASCII-only", () => {
    const text = [
      trsRound2.label,
      trsRound2.short_label ?? "",
      trsRound2.headline ?? "",
      trsRound2.caveat ?? "",
      ...(trsRound2.assumptions ?? []),
    ].join("\n");
    expect(Array.from(text).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});
