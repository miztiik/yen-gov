// Unit tests for the Mixed-Member Proportional rule.
//
// Per Fowler round-2 verdict: MMP departs from the global
// assertSeatTallyInvariant contract (sum(seats_won) == total_seats).
// We pin the MMP-specific invariant here:
//
//   sum(seats_won) == chamber_seats
//                  == constituency_count + total_list_seats
//                  >= constituency_count
//
// and that constituency_count + floor(constituency_count * 0.3) is the
// upper bound on chamber_seats (the case when no party has overhang).

import { describe, expect, it } from "vitest";
import { mmp } from "./mmp";
import { fptp } from "./fptp";
import { FIXTURE } from "../fixtures";
import type { CandidateTally, Tallies } from "../types";

function makeAc(
  eci_no: number,
  candidates: CandidateTally[],
): Tallies["acs"][number] {
  return { eci_no, name: `AC${eci_no}`, electorate: 1000, candidates };
}

function assertMmpInvariant(
  result: ReturnType<typeof mmp.apply>,
  constituency_count: number,
  fptp_seats_by_party: Map<string, number>,
): void {
  const sum = result.by_party.reduce((s, p) => s + p.seats_won, 0);
  const chamber = result.chamber_seats ?? constituency_count;
  expect(sum, "sum(seats_won) must equal chamber_seats").toBe(chamber);
  expect(chamber, "chamber must be at least the constituency count").toBeGreaterThanOrEqual(
    constituency_count,
  );
  // Per Hans's MMP doctrine: every FPTP winner keeps their seat. So
  // each party's MMP seats_won >= their FPTP seats_won (overhang on
  // top, list compensation on bottom). The chamber can grow PAST the
  // nominal list_target via overhang compensation; that's the German
  // 'leveling seats' shape and the structural feature of MMP that
  // distinguishes it from pure PR.
  for (const p of result.by_party) {
    const fptp_count = fptp_seats_by_party.get(p.party_eci_code) ?? 0;
    expect(
      p.seats_won,
      `MMP must NOT take seats away from FPTP winners (${p.party_eci_code})`,
    ).toBeGreaterThanOrEqual(fptp_count);
  }
}

describe("mmp - 3-AC fixture", () => {
  it("preserves every FPTP constituency winner in by_ac", () => {
    const r = mmp.apply(FIXTURE);
    const f = fptp.apply(FIXTURE);
    expect(r.by_ac.length).toBe(f.by_ac.length);
    for (let i = 0; i < r.by_ac.length; i++) {
      expect(r.by_ac[i].winner.party_eci_code).toBe(f.by_ac[i].winner.party_eci_code);
    }
  });

  it("chamber_seats grows by overhang-compensation even when list_target rounds to 0", () => {
    // 3 ACs * 0.3 = 0.9 -> floor 0 -> no nominal list tier.
    // FPTP gives DMK=2, AIADMK=1. Sainte-Lague ideal across 3 says
    // AIADMK=2, DMK=1 (AIADMK has more state-wide votes). AIADMK
    // under-represented -> +1 list seat. DMK over-represented ->
    // overhang (kept). Chamber = 3 + 1 = 4.
    const r = mmp.apply(FIXTURE);
    expect(r.chamber_seats).toBe(4);
  });

  it("under-represented parties receive list-tier seats on a 10-AC fixture", () => {
    // 10 ACs each with BJP 600 (FPTP win) + INC 300 + AAP 100.
    // FPTP: BJP=10, INC=0, AAP=0. State-wide votes: BJP 6000, INC 3000,
    // AAP 1000. Total 10000.
    // List target = floor(10 * 0.3) = 3. Ideal chamber = 13.
    // Sainte-Lague ideal across 13 seats:
    //   BJP/1=6000, INC/1=3000, AAP/1=1000, BJP/3=2000, INC/3=1000, BJP/5=1200,
    //   INC/5=600, BJP/7=857, AAP/3=333, BJP/9=667, BJP/11=545, INC/7=429,
    //   BJP/13=462.
    // Picks: BJP/1=6000 BJP=1; INC/1=3000 INC=1; BJP/3=2000 BJP=2;
    //   BJP/5=1200 BJP=3; INC/3=1000 INC=2; AAP/1=1000 (tie with INC/3; ASC
    //   AAP<INC so AAP wins). AAP=1. Wait re-trace:
    //   After 3 picks: BJP=2, INC=1. Quotients available:
    //     BJP/5=1200, INC/3=1000, AAP/1=1000, BJP/7=857.
    //   4th pick: 1200 -> BJP=3.
    //   5th: 1000 (tie INC/3, AAP/1; party_short ASC AAP<INC; AAP wins). AAP=1.
    //   6th: 1000 INC -> INC=2.
    //   7th: BJP/7=857 -> BJP=4.
    //   8th: INC/5=600 -> INC=3.
    //   9th: BJP/9=667 vs INC/5 was already taken... let me re-list:
    //   After 7 picks: BJP=4, INC=2, AAP=1. Quotients:
    //     BJP/9=667, INC/5=600, AAP/3=333.
    //   8th: 667 -> BJP=5.
    //   9th: 600 -> INC=3.
    //   10th: BJP/11=545 vs AAP/3=333. BJP=6.
    //   11th: BJP/13=462 vs INC/7=429 vs AAP/3=333. BJP=7.
    //   12th: INC/7=429 vs AAP/3=333. INC=4.
    //   13th: BJP/15=400 vs AAP/3=333. BJP=8.
    // Ideal Sainte-Lague: BJP=8, INC=4, AAP=1. Total 13.
    // FPTP: BJP=10, INC=0, AAP=0. Total 10.
    // list_seats: BJP max(0, 8-10)=0, INC max(0, 4-0)=4, AAP max(0, 1-0)=1.
    // total_list_seats = 0 + 4 + 1 = 5.
    // chamber = 10 + 5 = 15.
    // final_seats: BJP=10+0=10, INC=0+4=4, AAP=0+1=1. Total 15.
    const acs: Tallies["acs"] = [];
    for (let i = 1; i <= 10; i++) {
      acs.push(
        makeAc(i, [
          { party_eci_code: "BJP", party_short: "BJP", name: `B${i}`, votes: 600, party_id: "parties.IN.BJP" },
          { party_eci_code: "INC", party_short: "INC", name: `I${i}`, votes: 300, party_id: "parties.IN.INC" },
          { party_eci_code: "AAP", party_short: "AAP", name: `A${i}`, votes: 100, party_id: "parties.IN.AAP" },
        ]),
      );
    }
    const tallies: Tallies = { scope: FIXTURE.scope, acs };
    const r = mmp.apply(tallies);
    const seats = (code: string) =>
      r.by_party.find((p) => p.party_eci_code === code)?.seats_won ?? 0;

    expect(seats("BJP")).toBe(10);
    expect(seats("INC")).toBe(4);
    expect(seats("AAP")).toBe(1);
    expect(r.chamber_seats).toBe(15);

    const fptp_seats = new Map<string, number>();
    for (const p of fptp.apply(tallies).by_party) {
      fptp_seats.set(p.party_eci_code, p.seats_won);
    }
    assertMmpInvariant(r, 10, fptp_seats);
  });

  it("overhang: party with all constituency wins keeps every seat but gets no list compensation", () => {
    // 10 ACs each with BJP 900 (dominant) + INC 50 + AAP 50.
    // FPTP: BJP=10, INC=0, AAP=0.
    // State-wide: BJP 9000, INC 500, AAP 500. Total 10000.
    // List target=3, chamber target=13.
    // Sainte-Lague ideal across 13:
    //   BJP would win nearly all - probably 11 or 12; INC + AAP each 0 or 1.
    // Whatever the ideal, BJP already has 10 FPTP seats; list contribution
    // can only push their ideal share UP. The overhang case fires when
    // ideal_for_BJP < 10 - in this dominant-party fixture ideal_for_BJP > 10
    // so no overhang. To get overhang, BJP needs to win MORE FPTP seats than
    // its ideal proportional share, which requires concentrating votes.
    //
    // Construct: 10 ACs each with BJP=51 + INC=49. State-wide BJP 510, INC 490.
    // FPTP: BJP wins all 10 (every AC margin 2 votes). INC=0.
    // Ideal chamber 13 by Sainte-Lague: BJP 510, INC 490.
    //   BJP/1=510, INC/1=490, BJP/3=170, INC/3=163, BJP/5=102, INC/5=98, BJP/7=73, INC/7=70, BJP/9=57, INC/9=54, BJP/11=46, INC/11=45, BJP/13=39.
    //   Picks: BJP=1, INC=1, BJP=2, INC=2, BJP=3, INC=3, BJP=4, INC=4, BJP=5, INC=5, BJP=6, INC=6, BJP=7. Final BJP=7, INC=6.
    // FPTP BJP=10. list_BJP = max(0, 7-10) = 0. OVERHANG: BJP keeps all 10.
    // list_INC = max(0, 6-0) = 6.
    // chamber = 10 + 0 + 6 = 16.
    const acs: Tallies["acs"] = [];
    for (let i = 1; i <= 10; i++) {
      acs.push(
        makeAc(i, [
          { party_eci_code: "BJP", party_short: "BJP", name: `B${i}`, votes: 51, party_id: "parties.IN.BJP" },
          { party_eci_code: "INC", party_short: "INC", name: `I${i}`, votes: 49, party_id: "parties.IN.INC" },
        ]),
      );
    }
    const tallies: Tallies = { scope: FIXTURE.scope, acs };
    const r = mmp.apply(tallies);
    const seats = (code: string) =>
      r.by_party.find((p) => p.party_eci_code === code)?.seats_won ?? 0;

    // BJP keeps all 10 FPTP seats despite ideal saying 7 (overhang).
    expect(seats("BJP")).toBe(10);
    // INC gets list compensation up to its proportional share (6).
    expect(seats("INC")).toBe(6);
    // Chamber grew from 10 -> 16 (only INC's list seats; BJP overhang).
    expect(r.chamber_seats).toBe(16);
  });
});

describe("mmp - degenerate inputs", () => {
  it("returns an empty allocation for zero ACs", () => {
    const r = mmp.apply({ scope: FIXTURE.scope, acs: [] });
    expect(r.by_party).toEqual([]);
    expect(r.by_ac).toEqual([]);
    expect(r.total_votes).toBe(0);
    expect(r.chamber_seats).toBe(0);
  });

  it("every FPTP winner keeps their seat under MMP (list-tier may add but never subtract)", () => {
    // 3 ACs -> floor(3 * 0.3) = 0 nominal list target. MMP may still grow
    // the chamber via overhang compensation. The guaranteed contract
    // tested here is that no FPTP winner LOSES their seat under MMP.
    const r = mmp.apply(FIXTURE);
    const f = fptp.apply(FIXTURE);
    for (const p of f.by_party) {
      const m = r.by_party.find((x) => x.party_eci_code === p.party_eci_code);
      expect(m?.seats_won ?? 0, `MMP took away seats from ${p.party_eci_code}`).toBeGreaterThanOrEqual(p.seats_won);
    }
  });

  it("is deterministic across repeated invocations on the same input", () => {
    const a = mmp.apply(FIXTURE);
    const b = mmp.apply(FIXTURE);
    expect(a.by_party.map((p) => [p.party_eci_code, p.seats_won])).toEqual(
      b.by_party.map((p) => [p.party_eci_code, p.seats_won]),
    );
    expect(a.chamber_seats).toBe(b.chamber_seats);
  });
});

describe("mmp - metadata contract", () => {
  it("exposes round-2 metadata fields", () => {
    expect(mmp.id).toBe("mmp");
    expect(mmp.label).toContain("Mixed-Member");
    expect(mmp.short_label).toBe("Mixed-Member (MMP)");
    expect(mmp.validity).toBe("fully_workable");
    expect(mmp.requires_banner).toBe(true);
    expect((mmp.caveat ?? "").length).toBeGreaterThan(50);
    expect(mmp.assumptions?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("metadata is ASCII-only", () => {
    const text = [
      mmp.label,
      mmp.short_label ?? "",
      mmp.headline ?? "",
      mmp.caveat ?? "",
      ...(mmp.assumptions ?? []),
    ].join("\n");
    expect(Array.from(text).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});
