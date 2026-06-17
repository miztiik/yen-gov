/**
 * Unit tests for compare-kpis (PR4 of
 * TODO/20260617-election-compare-ux-overhaul-plan.md).
 *
 * Pins the compare hero KPI contract:
 *  - flip / hold / total-seat counts (orphans excluded);
 *  - new-party-entry SEAT count + the distinct new-party id set;
 *  - composition % math (flips_pct / holds_pct, 0-100);
 *  - divide-by-zero guard (null pct when no comparable seats);
 *  - the per-row `isNewPartyRow` predicate.
 *
 * Pure model -> no Svelte mount, runs in the node env.
 */

import { describe, it, expect } from "vitest";
import {
  buildCompareKpis,
  isNewPartyRow,
  type CompareKpiRow,
} from "./compare-kpis";

// Minimal kpi-row factory; only the fields the model reads are set.
function kpiRow(
  from_party_id: string | null,
  to_party_id: string | null,
  is_flip: boolean,
  is_orphan = false,
): CompareKpiRow {
  return { from_party_id, to_party_id, is_flip, is_orphan };
}

// 4 comparable seats (2 flips, 2 holds) + 2 orphans. From-winner baseline
// over ALL rows = {dmk, admk, inc}. "bjp" is the only brand-new To-winner
// (won zero seats in `from`).
const ROWS: CompareKpiRow[] = [
  kpiRow("dmk", "dmk", false), // hold (dmk)
  kpiRow("admk", "dmk", true), // flip TO dmk (not new - dmk won in from)
  kpiRow("dmk", "bjp", true), // flip TO bjp (NEW party)
  kpiRow("admk", "admk", false), // hold (admk)
  kpiRow(null, "dmk", false, true), // orphan (new seat)
  kpiRow("inc", null, false, true), // orphan (boundary changed)
];

describe("buildCompareKpis: counts", () => {
  it("counts flips, holds and total comparable seats (orphans excluded)", () => {
    const k = buildCompareKpis(ROWS);
    expect(k.flips).toBe(2);
    expect(k.holds).toBe(2);
    expect(k.total_seats).toBe(4);
  });

  it("total_seats equals flips + holds", () => {
    const k = buildCompareKpis(ROWS);
    expect(k.total_seats).toBe(k.flips + k.holds);
  });

  it("excludes orphan rows from every count", () => {
    // Two extra orphans whose to-party is brand new must NOT inflate any
    // count (orphans have no stable comparable seat).
    const withOrphans: CompareKpiRow[] = [
      ...ROWS,
      kpiRow(null, "newp", false, true),
      kpiRow("dmk", null, false, true),
    ];
    const k = buildCompareKpis(withOrphans);
    expect(k.total_seats).toBe(4);
    expect(k.flips).toBe(2);
    expect(k.holds).toBe(2);
    expect(k.new_party_entries).toBe(1);
    expect(k.new_party_ids.has("newp")).toBe(false);
  });
});

describe("buildCompareKpis: new-party entries", () => {
  it("counts the SEATS won by a brand-new party and lists the party id", () => {
    const k = buildCompareKpis(ROWS);
    expect(k.new_party_entries).toBe(1);
    expect([...k.new_party_ids]).toEqual(["bjp"]);
  });

  it("new_party_entries is a seat count, not a distinct-party count", () => {
    // Two seats both won by the same brand-new party -> 2 entries, 1 id.
    const rows: CompareKpiRow[] = [
      kpiRow("dmk", "dmk", false),
      kpiRow("dmk", "aap", true),
      kpiRow("admk", "aap", true),
    ];
    const k = buildCompareKpis(rows);
    expect(k.new_party_entries).toBe(2);
    expect([...k.new_party_ids]).toEqual(["aap"]);
  });

  it("a To-winner that already won in `from` is NOT a new party", () => {
    const k = buildCompareKpis(ROWS);
    expect(k.new_party_ids.has("dmk")).toBe(false);
    expect(k.new_party_ids.has("admk")).toBe(false);
  });
});

describe("buildCompareKpis: composition %", () => {
  it("computes flips_pct / holds_pct as shares of total_seats (0-100)", () => {
    const k = buildCompareKpis(ROWS);
    expect(k.flips_pct).toBe(50);
    expect(k.holds_pct).toBe(50);
  });

  it("computes a non-even split (7 flips / 3 holds -> 70% / 30%)", () => {
    const rows: CompareKpiRow[] = [];
    for (let i = 0; i < 7; i++) rows.push(kpiRow("a", "b", true));
    for (let i = 0; i < 3; i++) rows.push(kpiRow("a", "a", false));
    const k = buildCompareKpis(rows);
    expect(k.total_seats).toBe(10);
    expect(k.flips_pct).toBe(70);
    expect(k.holds_pct).toBe(30);
  });

  it("flips_pct + holds_pct sum to 100 when there are comparable seats", () => {
    const k = buildCompareKpis(ROWS);
    expect((k.flips_pct ?? 0) + (k.holds_pct ?? 0)).toBe(100);
  });
});

describe("buildCompareKpis: divide-by-zero guard", () => {
  it("returns null pct + zero counts for no rows", () => {
    const k = buildCompareKpis([]);
    expect(k.total_seats).toBe(0);
    expect(k.flips).toBe(0);
    expect(k.holds).toBe(0);
    expect(k.new_party_entries).toBe(0);
    expect(k.flips_pct).toBeNull();
    expect(k.holds_pct).toBeNull();
    expect(k.new_party_ids.size).toBe(0);
  });

  it("returns null pct when every row is an orphan (no comparable seats)", () => {
    const rows: CompareKpiRow[] = [
      kpiRow(null, "dmk", false, true),
      kpiRow("inc", null, false, true),
    ];
    const k = buildCompareKpis(rows);
    expect(k.total_seats).toBe(0);
    expect(k.flips_pct).toBeNull();
    expect(k.holds_pct).toBeNull();
  });
});

describe("isNewPartyRow", () => {
  const { new_party_ids } = buildCompareKpis(ROWS);

  it("is true for a non-orphan row whose to-party is in the new set", () => {
    expect(isNewPartyRow(kpiRow("dmk", "bjp", true), new_party_ids)).toBe(true);
  });

  it("is false for a row whose to-party already won in `from`", () => {
    expect(isNewPartyRow(kpiRow("admk", "dmk", true), new_party_ids)).toBe(
      false,
    );
  });

  it("is false for an orphan even if its to-party is in the new set", () => {
    expect(isNewPartyRow(kpiRow(null, "bjp", false, true), new_party_ids)).toBe(
      false,
    );
  });

  it("is false for a row with a null to-party", () => {
    expect(isNewPartyRow(kpiRow("inc", null, false, true), new_party_ids)).toBe(
      false,
    );
  });
});
