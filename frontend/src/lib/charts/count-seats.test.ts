// countSeats + assertSeatTallyInvariant unit tests.
//
// Parent plan section 25.6a (`TODO/20260603-data-and-charting-platform-reset-plan.md`)
// + gate `seats-invariant-test` (section 22.6): the seam MUST enforce
//
//   sum over parties of seats_won  ==  total_seats
//
// and the contract assertion MUST throw on every violation so the ~2x
// double-count regression class cannot return. Method gate (25.6b-seam)
// MUST throw for every non-FPTP value until the E6 sub-plan ships.

import { describe, it, expect } from "vitest";

import {
  type SeatTally,
  type SeatTallyCandidacyRow,
  type SeatTallyMethod,
  assertSeatTallyInvariant,
  countSeats,
} from "./count-seats";

// ---------- Small fixture: 5 ACs, 3 parties --------------------------------
//
// 5 constituencies, FPTP outcome:
//   AC-1 -> DMK
//   AC-2 -> DMK
//   AC-3 -> AIADMK
//   AC-4 -> AIADMK
//   AC-5 -> INC
// Expected SeatTally: total=5, DMK=2 AIADMK=2 INC=1.

function fiveAcCandidacies(): SeatTallyCandidacyRow[] {
  return [
    // AC-1 winner DMK
    { entity_id: "AC-1", party_id: "parties.IN.DMK", position: 1 },
    { entity_id: "AC-1", party_id: "parties.IN.AIADMK", position: 2 },
    // AC-2 winner DMK
    { entity_id: "AC-2", party_id: "parties.IN.DMK", position: 1 },
    { entity_id: "AC-2", party_id: "parties.IN.INC", position: 2 },
    // AC-3 winner AIADMK
    { entity_id: "AC-3", party_id: "parties.IN.AIADMK", position: 1 },
    { entity_id: "AC-3", party_id: "parties.IN.DMK", position: 2 },
    // AC-4 winner AIADMK
    { entity_id: "AC-4", party_id: "parties.IN.AIADMK", position: 1 },
    { entity_id: "AC-4", party_id: "parties.IN.DMK", position: 2 },
    // AC-5 winner INC
    { entity_id: "AC-5", party_id: "parties.IN.INC", position: 1 },
    { entity_id: "AC-5", party_id: "parties.IN.DMK", position: 2 },
  ];
}

describe("countSeats: FPTP method", () => {
  it("returns the expected SeatTally for a 5-AC fixture", () => {
    const tally = countSeats("fptp", fiveAcCandidacies());

    expect(tally.total_seats).toBe(5);
    expect(tally.parties).toHaveLength(3);

    // Sort-stable: seats_won DESC, party_id ASC tiebreak.
    expect(tally.parties[0]).toEqual({
      party_id: "parties.IN.AIADMK",
      seats_won: 2,
    });
    expect(tally.parties[1]).toEqual({
      party_id: "parties.IN.DMK",
      seats_won: 2,
    });
    expect(tally.parties[2]).toEqual({
      party_id: "parties.IN.INC",
      seats_won: 1,
    });

    // The cardinal invariant: sum(seats_won) == total_seats.
    const sum = tally.parties.reduce((s, p) => s + p.seats_won, 0);
    expect(sum).toBe(tally.total_seats);
  });

  it("returns an empty tally for empty input", () => {
    const tally = countSeats("fptp", []);
    expect(tally.total_seats).toBe(0);
    expect(tally.parties).toEqual([]);
  });

  it("returns total_seats=0 when no row has position=1", () => {
    const rows: SeatTallyCandidacyRow[] = [
      { entity_id: "AC-1", party_id: "parties.IN.DMK", position: 2 },
      { entity_id: "AC-1", party_id: "parties.IN.AIADMK", position: 3 },
    ];
    const tally = countSeats("fptp", rows);
    expect(tally.total_seats).toBe(0);
    expect(tally.parties).toEqual([]);
  });

  it("collapses a double-counted position=1 row to a single seat (defensive)", () => {
    // Same entity_id at position=1 twice (e.g. a JOIN double-count). The
    // Map collapses to one; the per-AC seat is only counted once. This
    // is the defence-in-depth path: the SQL-side bug should still be
    // fixed (the assertSeatTallyInvariant call against the upstream feed
    // would catch it), but countSeats does not propagate the duplicate.
    const rows: SeatTallyCandidacyRow[] = [
      { entity_id: "AC-1", party_id: "parties.IN.DMK", position: 1 },
      { entity_id: "AC-1", party_id: "parties.IN.DMK", position: 1 },
    ];
    const tally = countSeats("fptp", rows);
    expect(tally.total_seats).toBe(1);
    expect(tally.parties).toEqual([
      { party_id: "parties.IN.DMK", seats_won: 1 },
    ]);
  });

  it("leaves NULL party_id winners unattributed but counts them in total_seats", () => {
    // Per orchestrator section 25.6b-seam: "unbindable party_id stays
    // unattributed". Callers needing strict sum-equals-total must coalesce
    // nulls (e.g. 'OTHER' bucket) BEFORE calling countSeats.
    const rows: SeatTallyCandidacyRow[] = [
      { entity_id: "AC-1", party_id: "parties.IN.DMK", position: 1 },
      { entity_id: "AC-2", party_id: null, position: 1 }, // unattributed
      { entity_id: "AC-3", party_id: "parties.IN.AIADMK", position: 1 },
    ];
    const tally = countSeats("fptp", rows);
    expect(tally.total_seats).toBe(3);
    expect(tally.parties).toHaveLength(2);
    const sum = tally.parties.reduce((s, p) => s + p.seats_won, 0);
    expect(sum).toBe(2); // sum < total because of the unattributed seat
  });
});

describe("countSeats: method gate (25.6b-seam)", () => {
  // Per orchestrator anti-pattern + plan section 25.6: "DO NOT implement
  // countSeats 'ranked-choice' / 'approval' / 'proportional' methods (those
  // are E6 sub-plan; politically sensitive, requires Citizen + Hans second
  // opinion + a 'hypothetical recount, not official result' banner)".
  const rejected: SeatTallyMethod[] = ["ranked-choice", "approval", "proportional"];
  for (const method of rejected) {
    it(`throws for unsupported method "${method}"`, () => {
      expect(() => countSeats(method, fiveAcCandidacies())).toThrow(
        /unsupported method/i,
      );
      expect(() => countSeats(method, fiveAcCandidacies())).toThrow(
        /25\.6b-seam/,
      );
    });
  }
});

describe("assertSeatTallyInvariant", () => {
  it("passes for a tally whose parties sum equals total_seats", () => {
    const tally: SeatTally = {
      total_seats: 234,
      parties: [
        { party_id: "parties.IN.DMK", seats_won: 133 },
        { party_id: "OTHER", seats_won: 68 },
        { party_id: "parties.IN.INC", seats_won: 18 },
        { party_id: "parties.IN.PMK", seats_won: 5 },
        { party_id: "parties.IN.BJP", seats_won: 4 },
        { party_id: "parties.IN.VCK", seats_won: 4 },
        { party_id: "parties.IN.CPI", seats_won: 2 },
      ],
    };
    expect(() => assertSeatTallyInvariant(tally)).not.toThrow();
  });

  it("throws when sum(seats_won) != total_seats (the 2x regression class)", () => {
    // Synthetic: sum = 468 but total_seats = 234 (the orchestrator's
    // ~2x double-count signature).
    const tally: SeatTally = {
      total_seats: 234,
      parties: [
        { party_id: "parties.IN.DMK", seats_won: 266 },
        { party_id: "parties.IN.AIADMK", seats_won: 200 },
        { party_id: "parties.IN.INC", seats_won: 2 },
      ],
    };
    expect(() => assertSeatTallyInvariant(tally)).toThrow(
      /SeatTally invariant violated/,
    );
    expect(() => assertSeatTallyInvariant(tally)).toThrow(
      /sum\(seats_won\)=468/,
    );
    expect(() => assertSeatTallyInvariant(tally)).toThrow(/total_seats=234/);
  });

  it("includes the optional label in the error message", () => {
    const tally: SeatTally = {
      total_seats: 5,
      parties: [{ party_id: "parties.IN.DMK", seats_won: 7 }],
    };
    expect(() => assertSeatTallyInvariant(tally, "tn-2021-state-overview")).toThrow(
      /\(tn-2021-state-overview\)/,
    );
  });

  it("passes for an empty tally (total=0, parties=[])", () => {
    expect(() =>
      assertSeatTallyInvariant({ total_seats: 0, parties: [] }),
    ).not.toThrow();
  });

  it("throws when an under-count drift is non-zero (sum < total)", () => {
    // Symmetric defence: drift below is also a contract violation. State-
    // overview's NULL party_id winners would surface here if the SQL
    // did NOT COALESCE to 'OTHER' before calling countSeats.
    const tally: SeatTally = {
      total_seats: 100,
      parties: [{ party_id: "parties.IN.DMK", seats_won: 60 }],
    };
    expect(() => assertSeatTallyInvariant(tally)).toThrow(
      /sum\(seats_won\)=60.*total_seats=100/,
    );
  });
});

describe("countSeats + assertSeatTallyInvariant end-to-end (the gate)", () => {
  it("returns an invariant-satisfying tally for the 5-AC fixture", () => {
    const tally = countSeats("fptp", fiveAcCandidacies());
    expect(() => assertSeatTallyInvariant(tally, "5-ac-fixture")).not.toThrow();
  });

  it("scales to a 234-AC fixture (TN-shaped, the Tamil Nadu seat count)", () => {
    // Synthesize 234 winners across 4 parties (DMK 133 / AIADMK 66 / INC 25 / BJP 10).
    const rows: SeatTallyCandidacyRow[] = [];
    const distribution: Array<[string, number]> = [
      ["parties.IN.DMK", 133],
      ["parties.IN.AIADMK", 66],
      ["parties.IN.INC", 25],
      ["parties.IN.BJP", 10],
    ];
    let next = 1;
    for (const [party_id, count] of distribution) {
      for (let i = 0; i < count; i++) {
        rows.push({ entity_id: `AC-${next++}`, party_id, position: 1 });
      }
    }
    expect(next - 1).toBe(234);

    const tally = countSeats("fptp", rows);
    expect(tally.total_seats).toBe(234);
    expect(() =>
      assertSeatTallyInvariant(tally, "tn-2021-shaped-fixture"),
    ).not.toThrow();
    const sum = tally.parties.reduce((s, p) => s + p.seats_won, 0);
    expect(sum).toBe(234);
  });
});
