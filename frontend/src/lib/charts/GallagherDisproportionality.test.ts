// Vitest - pure-helper tests for GallagherDisproportionality.svelte
// (E7 Hans Option C carve-out).
//
// Component-render assertions are deferred to Playwright per repo
// vitest doctrine (node-env, no jsdom canvas, no @testing-library/svelte;
// see Skeleton.test.ts + MapHighlightLegend.test.ts + FacetPanelGrid.test.ts
// for the precedent). The 4 exported pure helpers in the
// `<script module>` block are the testable surface:
//
//   - computeGallagher(allocation, total_seats): Gallagher (LS) Index + per-party gap map
//   - gallagherQualifier(index): proportionality band label
//   - buildGallagherRows(allocation, total_seats, top_n): rows + "Other" collapse
//   - formatGapPp(gap): signed "+11.0pp" label
//
// Plus two exported constants the renderer consumes (the citizen-facing
// footer note + the Wikipedia learn-more href) covered by the
// ASCII-only assertion.

import { describe, expect, it } from "vitest";

import {
  GALLAGHER_FOOTER_NOTE,
  GALLAGHER_LEARN_MORE_HREF,
  buildGallagherRows,
  computeGallagher,
  formatGapPp,
  gallagherQualifier,
  type GallagherRow,
} from "./GallagherDisproportionality.svelte";
import type { PartyResult, SeatAllocation } from "../psephlab/types";

// ---------- Fixture builders ------------------------------------------------

function party(
  party_eci_code: string,
  vote_share_pct: number,
  seats_won: number,
  votes = 0,
): PartyResult {
  return {
    party_eci_code,
    party_short: party_eci_code,
    seats_won,
    votes,
    vote_share_pct,
    party_id: `parties.IN.${party_eci_code}`,
  };
}

function allocation(parties: PartyResult[]): SeatAllocation {
  const total_votes = parties.reduce((s, p) => s + p.votes, 0);
  return {
    by_party: parties,
    by_ac: [],
    total_votes,
  };
}

// 2 parties each at 50/50 -> G = 0.
const PERFECT_FIX = allocation([
  party("A", 50, 1),
  party("B", 50, 1),
]);

// 1 party gets all the seats with half the votes -> G = 50 (maximum
// for a 2-party fixture).
const MAX_DISPROP_FIX = allocation([
  party("A", 50, 5),
  party("B", 50, 0),
]);
const MAX_DISPROP_SEATS = 5;

// Simplified TN-2021-shaped fixture (vote shares sum to 100, seats
// sum to 234 = real TN AC count). Values approximate; G expected
// ~10.6 (within brief's [7.5, 11.0] tolerance).
const TN_FIX = allocation([
  party("DMK", 46, 133),
  party("AIADMK", 33, 66),
  party("INC", 5, 18),
  party("OTH", 16, 17),
]);
const TN_SEATS = 234;

// 10-party fixture for the top_n=8 collapse test. Vote shares sum to
// 100; seats sum to 50.
const TEN_PARTY_FIX = allocation([
  party("P01", 22, 12),
  party("P02", 18, 10),
  party("P03", 14, 8),
  party("P04", 12, 6),
  party("P05", 10, 5),
  party("P06", 8, 4),
  party("P07", 6, 2),
  party("P08", 5, 1),
  party("P09", 3, 1),
  party("P10", 2, 1),
]);
const TEN_PARTY_SEATS = 50;

// ---------- computeGallagher: algorithm tests -------------------------------

describe("computeGallagher (Least-Squares Index)", () => {
  it("returns G = 0 for perfect proportionality (2 parties, 50/50/50)", () => {
    const result = computeGallagher(PERFECT_FIX, 2);
    expect(result.index).toBe(0);
    // Both parties at vote = seat = 50% -> gap = 0.
    expect(result.per_party_gap_pp.get("A")).toBe(0);
    expect(result.per_party_gap_pp.get("B")).toBe(0);
  });

  it("returns G = 50 for maximum disproportionality (50% votes -> 100% seats)", () => {
    const result = computeGallagher(MAX_DISPROP_FIX, MAX_DISPROP_SEATS);
    // sqrt(0.5 * (50^2 + 50^2)) = sqrt(2500) = 50.
    expect(result.index).toBe(50);
    expect(result.per_party_gap_pp.get("A")).toBeCloseTo(+50, 6);
    expect(result.per_party_gap_pp.get("B")).toBeCloseTo(-50, 6);
  });

  it("returns G in [7.5, 11.0] for the TN-2021 fixture", () => {
    const result = computeGallagher(TN_FIX, TN_SEATS);
    expect(result.index).toBeGreaterThanOrEqual(7.5);
    expect(result.index).toBeLessThanOrEqual(11.0);
  });

  it("returns G = 0 for an empty allocation", () => {
    const empty = allocation([]);
    const result = computeGallagher(empty, 0);
    expect(result.index).toBe(0);
    expect(result.per_party_gap_pp.size).toBe(0);
  });

  it("returns G = 0 for a single-party 100% allocation", () => {
    const solo = allocation([party("A", 100, 5)]);
    const result = computeGallagher(solo, 5);
    expect(result.index).toBe(0);
    expect(result.per_party_gap_pp.get("A")).toBe(0);
  });

  it("DMK gap is POSITIVE (over-represented) and OTH gap is NEGATIVE in TN fixture", () => {
    // Brief test 6 named INC for the negative-gap assertion, but with
    // 5% votes -> 18/234 = 7.69% seats, INC is actually slightly
    // OVER-represented (+2.69pp) in this fixture. Substituting "OTH"
    // (16% votes -> 7.26% seats = -8.74pp) which IS under-represented.
    const result = computeGallagher(TN_FIX, TN_SEATS);
    const dmk = result.per_party_gap_pp.get("DMK")!;
    const oth = result.per_party_gap_pp.get("OTH")!;
    expect(dmk).toBeGreaterThan(0);     // over-represented
    expect(oth).toBeLessThan(0);        // under-represented
  });
});

// ---------- computeGallagher: index precision contract ---------------------

describe("computeGallagher index precision", () => {
  it("rounds the index to at most 1 decimal place", () => {
    const result = computeGallagher(TN_FIX, TN_SEATS);
    // result.index * 10 should be an integer (i.e. exactly 1-decimal form).
    expect(Number.isInteger(Math.round(result.index * 10))).toBe(true);
    expect(result.index * 10).toBe(Math.round(result.index * 10));
  });
});

// ---------- gallagherQualifier ---------------------------------------------

describe("gallagherQualifier", () => {
  it("returns 'very proportional' for G < 5", () => {
    expect(gallagherQualifier(0)).toBe("very proportional");
    expect(gallagherQualifier(4.9)).toBe("very proportional");
  });

  it("returns 'moderately proportional' for 5 <= G < 10", () => {
    expect(gallagherQualifier(5)).toBe("moderately proportional");
    expect(gallagherQualifier(9.9)).toBe("moderately proportional");
  });

  it("returns 'disproportional' for 10 <= G < 20", () => {
    expect(gallagherQualifier(10)).toBe("disproportional");
    expect(gallagherQualifier(19.9)).toBe("disproportional");
  });

  it("returns 'very disproportional' for G >= 20", () => {
    expect(gallagherQualifier(20)).toBe("very disproportional");
    expect(gallagherQualifier(50)).toBe("very disproportional");
  });

  it("returns 'very proportional' for non-finite input (defensive)", () => {
    expect(gallagherQualifier(Number.NaN)).toBe("very proportional");
  });
});

// ---------- formatGapPp ----------------------------------------------------

describe("formatGapPp", () => {
  it("formats positive gaps with explicit '+' and 1 decimal", () => {
    expect(formatGapPp(10.84)).toBe("+10.8pp");
    expect(formatGapPp(0.05)).toBe("+0.1pp");
  });

  it("formats negative gaps with leading '-' and 1 decimal", () => {
    expect(formatGapPp(-4.79)).toBe("-4.8pp");
    expect(formatGapPp(-0.04)).toBe("-0.0pp");
  });

  it("formats zero as '+0.0pp'", () => {
    expect(formatGapPp(0)).toBe("+0.0pp");
  });

  it("returns '0.0pp' for non-finite input (defensive)", () => {
    expect(formatGapPp(Number.NaN)).toBe("0.0pp");
  });
});

// ---------- buildGallagherRows ---------------------------------------------

describe("buildGallagherRows", () => {
  it("emits one row per input party when count <= top_n", () => {
    const out = buildGallagherRows(TN_FIX, TN_SEATS, 8);
    expect(out.rows).toHaveLength(4);
    expect(out.other).toBeNull();
  });

  it("ranks rows by seat_share desc (DMK first in TN fixture)", () => {
    const out = buildGallagherRows(TN_FIX, TN_SEATS, 8);
    expect(out.rows[0].party_eci_code).toBe("DMK");
    expect(out.rows[1].party_eci_code).toBe("AIADMK");
  });

  it("emits exactly top_n named rows + an 'Other' row when count > top_n", () => {
    const out = buildGallagherRows(TEN_PARTY_FIX, TEN_PARTY_SEATS, 8);
    expect(out.rows).toHaveLength(8);
    expect(out.other).not.toBeNull();
    expect(out.other!.party_eci_code).toBe("OTHER");
    expect(out.other!.party_short).toBe("Other");
  });

  it("aggregates the 'Other' row by summing vote_share + seat_share of the tail", () => {
    const out = buildGallagherRows(TEN_PARTY_FIX, TEN_PARTY_SEATS, 8);
    // After sort: P01 (24% seat), P02 (20%), P03 (16%), P04 (12%), P05 (10%),
    // P06 (8%), P07 (4%), P08 (2%) = top 8. Tail = P09 (vote 3, seats 1) +
    // P10 (vote 2, seats 1).
    const tailVoteSum = 3 + 2;          // 5
    const tailSeatSum = (1 + 1) * 100 / TEN_PARTY_SEATS; // 4
    expect(out.other!.vote_share_pct).toBeCloseTo(tailVoteSum, 6);
    expect(out.other!.seat_share_pct).toBeCloseTo(tailSeatSum, 6);
    expect(out.other!.gap_pp).toBeCloseTo(tailSeatSum - tailVoteSum, 6);
  });

  it("computes seat_share + gap_pp per row from total_seats", () => {
    const out = buildGallagherRows(TN_FIX, TN_SEATS, 8);
    const dmk = out.rows.find((r) => r.party_eci_code === "DMK")!;
    expect(dmk.seat_share_pct).toBeCloseTo((100 * 133) / 234, 4);
    expect(dmk.gap_pp).toBeCloseTo((100 * 133) / 234 - 46, 4);
  });

  it("max_share is the largest single vote_share or seat_share across rendered rows", () => {
    const out = buildGallagherRows(TN_FIX, TN_SEATS, 8);
    // DMK seat_share = 133/234 = 56.84% is the largest in the fixture.
    expect(out.max_share).toBeCloseTo((100 * 133) / 234, 4);
  });

  it("returns an empty layout for empty allocation", () => {
    const out = buildGallagherRows(allocation([]), 0, 8);
    expect(out.rows).toEqual([]);
    expect(out.other).toBeNull();
    expect(out.max_share).toBe(0);
  });
});

// ---------- ASCII-only contract --------------------------------------------

describe("ASCII-only contract (CLAUDE.md doctrine)", () => {
  // Strict ASCII printable + space + newline. No curly quotes, em-dashes,
  // bullet glyphs, or other non-ASCII (the chart text-content boundary).
  const ASCII_OK = /^[\x20-\x7E\n]*$/;

  it("GALLAGHER_FOOTER_NOTE is ASCII-only", () => {
    expect(ASCII_OK.test(GALLAGHER_FOOTER_NOTE)).toBe(true);
  });

  it("GALLAGHER_LEARN_MORE_HREF is ASCII-only", () => {
    expect(ASCII_OK.test(GALLAGHER_LEARN_MORE_HREF)).toBe(true);
  });

  it("every gallagherQualifier band label is ASCII-only", () => {
    const bands = [
      gallagherQualifier(0),
      gallagherQualifier(5),
      gallagherQualifier(10),
      gallagherQualifier(20),
    ];
    for (const band of bands) {
      expect(ASCII_OK.test(band)).toBe(true);
    }
  });

  it("formatGapPp output is ASCII-only across signs", () => {
    for (const v of [10.8, -4.8, 0, 100, -100]) {
      expect(ASCII_OK.test(formatGapPp(v))).toBe(true);
    }
  });

  it("buildGallagherRows row labels (incl. 'Other') are ASCII-only", () => {
    const out = buildGallagherRows(TEN_PARTY_FIX, TEN_PARTY_SEATS, 8);
    const labels: string[] = [
      ...out.rows.map((r: GallagherRow) => r.party_short),
      ...(out.other ? [out.other.party_short] : []),
    ];
    for (const label of labels) {
      expect(ASCII_OK.test(label)).toBe(true);
    }
  });
});
