// Unit tests for the D'Hondt rule.
//
// FIXTURE state-wide totals (excl NOTA): DMK 1300, AIADMK 1480, BJP 180.
// Seats = 3 (one per AC in FIXTURE).
//
// D'Hondt allocation: each round picks the party with the highest
// quotient (votes / (seats_so_far + 1)).
//
// Round 1 quotients: DMK 1300/1=1300, AIADMK 1480/1=1480, BJP 180/1=180.
//                   AIADMK wins (1480). AIADMK seats = 1.
// Round 2 quotients: DMK 1300/1=1300, AIADMK 1480/2=740, BJP 180/1=180.
//                   DMK wins (1300). DMK seats = 1.
// Round 3 quotients: DMK 1300/2=650, AIADMK 1480/2=740, BJP 180/1=180.
//                   AIADMK wins (740). AIADMK seats = 2.
//
// Final: AIADMK 2, DMK 1, BJP 0. SAME outcome as Sainte-Lague on this
// fixture because the seat count is tiny. The two methods diverge at
// larger seat counts; the divergence-with-Sainte-Lague test below uses
// a synthetic fixture to expose the difference (D'Hondt favours
// AIADMK because it's larger).

import { describe, expect, it } from "vitest";
import { dhondt } from "./dhondt";
import { sainteLague } from "./sainteLague";
import { FIXTURE } from "../fixtures";
import type { CandidateTally, Tallies } from "../types";

function makeAc(
  eci_no: number,
  candidates: CandidateTally[],
): Tallies["acs"][number] {
  return { eci_no, name: `AC${eci_no}`, electorate: 1000, candidates };
}

describe("dhondt - 3-AC fixture", () => {
  it("allocates 3 seats across FIXTURE: AIADMK=2, DMK=1, BJP=0", () => {
    const r = dhondt.apply(FIXTURE);
    const seats = (code: string) =>
      r.by_party.find((p) => p.party_eci_code === code)?.seats_won ?? 0;
    expect(seats("AIADMK")).toBe(2);
    expect(seats("DMK")).toBe(1);
    expect(seats("BJP")).toBe(0);
  });

  it("excludes NOTA from the party allocation", () => {
    const r = dhondt.apply(FIXTURE);
    expect(r.by_party.find((p) => p.party_eci_code === "NOTA")).toBeUndefined();
  });

  it("by_ac is empty (PR does not bind per-constituency)", () => {
    const r = dhondt.apply(FIXTURE);
    expect(r.by_ac).toEqual([]);
  });

  it("sum of seats_won == number of ACs (E5 invariant)", () => {
    const r = dhondt.apply(FIXTURE);
    const sum = r.by_party.reduce((s, p) => s + p.seats_won, 0);
    expect(sum).toBe(FIXTURE.acs.length);
  });

  it("total_votes counts every cast vote (NOTA included)", () => {
    const r = dhondt.apply(FIXTURE);
    expect(r.total_votes).toBe(3000);
  });
});

describe("dhondt - divergence from Sainte-Lague at scale", () => {
  // Canonical Wikipedia textbook fixture (Highest averages method).
  // Votes: A=10000, B=8000, C=6000, D=4000. 5 seats.
  //
  // D'Hondt (divisors 1, 2, 3, ...):
  //   A: 10000, 5000, 3333. B: 8000, 4000. C: 6000, 3000. D: 4000, 2000.
  //   Picks: 10000 A=1, 8000 B=1, 6000 C=1, 5000 A=2, 4000 (tie B/2=4000
  //   with D/1=4000; party_short ASC -> B wins) B=2.
  //   Final: A=2, B=2, C=1, D=0.
  //
  // Sainte-Lague (divisors 1, 3, 5, ...):
  //   A: 10000, 3333, 2000. B: 8000, 2667. C: 6000, 2000. D: 4000.
  //   Picks: 10000 A=1, 8000 B=1, 6000 C=1, 4000 D=1, 3333 A=2.
  //   Final: A=2, B=1, C=1, D=1.
  //
  // The divergence: under D'Hondt the 4000-vote D loses to the 8000-vote
  // B's second-seat quotient; under Sainte-Lague D rides in at the cost
  // of B's second seat. Classic large-party / small-party tilt.
  it("D'Hondt favours the larger party B over the smaller party D vs Sainte-Lague", () => {
    const scope = FIXTURE.scope;
    const acs: Tallies["acs"] = [];
    // 5 ACs each contributing A=2000, B=1600, C=1200, D=800 (totals 10000,
    // 8000, 6000, 4000).
    for (let i = 1; i <= 5; i++) {
      acs.push(
        makeAc(i, [
          { party_eci_code: "A", party_short: "A", name: `A${i}`, votes: 2000, party_id: "parties.IN.A" },
          { party_eci_code: "B", party_short: "B", name: `B${i}`, votes: 1600, party_id: "parties.IN.B" },
          { party_eci_code: "C", party_short: "C", name: `C${i}`, votes: 1200, party_id: "parties.IN.C" },
          { party_eci_code: "D", party_short: "D", name: `D${i}`, votes: 800, party_id: "parties.IN.D" },
        ]),
      );
    }
    const tallies: Tallies = { scope, acs };
    const d = dhondt.apply(tallies);
    const s = sainteLague.apply(tallies);
    const dSeats = (code: string) => d.by_party.find((p) => p.party_eci_code === code)?.seats_won ?? 0;
    const sSeats = (code: string) => s.by_party.find((p) => p.party_eci_code === code)?.seats_won ?? 0;

    // D'Hondt: A=2, B=2, C=1, D=0
    expect(dSeats("A")).toBe(2);
    expect(dSeats("B")).toBe(2);
    expect(dSeats("C")).toBe(1);
    expect(dSeats("D")).toBe(0);

    // Sainte-Lague: A=2, B=1, C=1, D=1 (D rides in at B's expense)
    expect(sSeats("A")).toBe(2);
    expect(sSeats("B")).toBe(1);
    expect(sSeats("C")).toBe(1);
    expect(sSeats("D")).toBe(1);

    // Both rules allocate the same total seat count.
    const dTotal = d.by_party.reduce((sum, p) => sum + p.seats_won, 0);
    const sTotal = s.by_party.reduce((sum, p) => sum + p.seats_won, 0);
    expect(dTotal).toBe(5);
    expect(sTotal).toBe(5);
  });
});

describe("dhondt - degenerate inputs", () => {
  it("handles an empty tally without throwing", () => {
    const r = dhondt.apply({ scope: FIXTURE.scope, acs: [] });
    expect(r.by_party).toEqual([]);
    expect(r.by_ac).toEqual([]);
    expect(r.total_votes).toBe(0);
  });

  it("allocates all seats to the lone party when only one has votes", () => {
    const tallies: Tallies = {
      scope: FIXTURE.scope,
      acs: [
        makeAc(1, [
          { party_eci_code: "DMK", party_short: "DMK", name: "X", votes: 500, party_id: "parties.IN.DMK" },
          { party_eci_code: "NOTA", party_short: "NOTA", name: "NOTA", votes: 100, party_id: "parties.IN.NOTA" },
        ]),
        makeAc(2, [
          { party_eci_code: "DMK", party_short: "DMK", name: "Y", votes: 600, party_id: "parties.IN.DMK" },
        ]),
      ],
    };
    const r = dhondt.apply(tallies);
    expect(r.by_party).toHaveLength(1);
    expect(r.by_party[0].party_eci_code).toBe("DMK");
    expect(r.by_party[0].seats_won).toBe(2);
  });

  it("is deterministic across repeated invocations on the same input", () => {
    const a = dhondt.apply(FIXTURE);
    const b = dhondt.apply(FIXTURE);
    expect(a.by_party.map((p) => [p.party_eci_code, p.seats_won])).toEqual(
      b.by_party.map((p) => [p.party_eci_code, p.seats_won]),
    );
  });
});

describe("dhondt - metadata contract", () => {
  it("exposes label + short_label + headline + validity + requires_banner", () => {
    expect(dhondt.id).toBe("proportional-dhondt");
    expect(dhondt.label).toContain("D'Hondt");
    expect(dhondt.short_label).toBe("Proportional (D'Hondt)");
    expect(dhondt.headline).toBeTruthy();
    expect(dhondt.validity).toBe("fully_workable");
    expect(dhondt.requires_banner).toBe(true);
    expect((dhondt.caveat ?? "").length).toBeGreaterThan(50);
    expect(dhondt.assumptions?.length ?? 0).toBeGreaterThanOrEqual(3);
  });

  it("metadata is ASCII-only", () => {
    const text = [
      dhondt.label,
      dhondt.short_label ?? "",
      dhondt.headline ?? "",
      dhondt.caveat ?? "",
      ...(dhondt.assumptions ?? []),
    ].join("\n");
    expect(Array.from(text).every((c) => c.charCodeAt(0) < 128)).toBe(true);
  });
});
