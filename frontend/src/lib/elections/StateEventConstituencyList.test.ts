// Oracle unit tests for the constituency list's pure logic (Row 2 of
// TODO/20260622-election-constituency-grouping-plan.md). The component
// (`StateEventConstituencyList.svelte`) is a thin renderer over these
// helpers, so testing the helpers IS testing the component's contract.
//
// Pure: node-env, no DOM, no Svelte mount (mirrors the dir's existing
// readFileSync/pure-helper test convention). No mocks - every assertion
// runs the real exported function the UI calls.

import { describe, it, expect } from "vitest";

import {
  buildPartyStrip,
  marginBand,
  reservationKind,
  sortLeaves,
  applyFilters,
  distinctDistrictCount,
  formatCountLine,
  STRIP_OTHER_COLOR,
  type StripInput,
} from "./constituency-list-tokens";

// Expand a {short: seatCount} map into per-seat strip inputs. Party id ==
// short; colour is deterministic per party.
function rowsFromCounts(counts: Record<string, number>): StripInput[] {
  const colors: Record<string, string> = {
    TDP: "#fdd835",
    YSRCP: "#1565c0",
    JSP: "#e53935",
    A: "#111111",
    B: "#222222",
    C: "#333333",
    D: "#444444",
    E: "#555555",
    F: "#666666",
  };
  const out: StripInput[] = [];
  for (const [short, n] of Object.entries(counts)) {
    for (let k = 0; k < n; k++) {
      out.push({
        winner_party_short: short,
        winner_party_id: short,
        winner_color: colors[short] ?? "#999999",
      });
    }
  }
  return out;
}

// A minimal leaf used by the filter / sort / count oracles.
interface Leaf {
  entity_id: string;
  entity_name: string;
  district?: string | null;
  reservation?: string | null;
  eci_no?: number | null;
  margin_pct: number | null;
}

function leaf(over: Partial<Leaf> & { entity_name: string }): Leaf {
  return {
    entity_id: over.entity_id ?? over.entity_name,
    entity_name: over.entity_name,
    district: over.district,
    reservation: over.reservation,
    eci_no: over.eci_no,
    margin_pct: over.margin_pct ?? null,
  };
}

describe("buildPartyStrip - proportional segmented strip", () => {
  it("ORACLE: {TDP:9, YSRCP:6, JSP:2} -> 3 segments summing 100%, desc, label 'TDP 9/17'", () => {
    const strip = buildPartyStrip(rowsFromCounts({ TDP: 9, YSRCP: 6, JSP: 2 }));

    // Exactly 3 segments (no "other" - only 3 distinct parties).
    expect(strip.segments).toHaveLength(3);
    expect(strip.segments.some((s) => s.is_other)).toBe(false);

    // Ordered descending by seat count.
    expect(strip.segments.map((s) => s.party_short)).toEqual(["TDP", "YSRCP", "JSP"]);
    expect(strip.segments.map((s) => s.count)).toEqual([9, 6, 2]);

    // Widths proportional + summing to 100%.
    const sum = strip.segments.reduce((acc, s) => acc + s.pct, 0);
    expect(sum).toBeCloseTo(100, 6);
    expect(strip.segments[0].pct).toBeCloseTo((9 / 17) * 100, 6);
    expect(strip.segments[1].pct).toBeGreaterThan(strip.segments[2].pct);

    // Leading-party label spells the leader - NEVER colour-only.
    expect(strip.leader_label).toBe("TDP 9/17");
    expect(strip.total).toBe(17);
  });

  it("ORACLE: sweep {TDP:16} -> 1 full-width segment, label 'TDP 16/16'", () => {
    const strip = buildPartyStrip(rowsFromCounts({ TDP: 16 }));
    expect(strip.segments).toHaveLength(1);
    expect(strip.segments[0].pct).toBe(100);
    expect(strip.segments[0].count).toBe(16);
    expect(strip.leader_label).toBe("TDP 16/16");
  });

  it("collapses parties beyond the top-4 into ONE 'Other' segment", () => {
    // 6 distinct parties -> top 4 + Other(E+F).
    const strip = buildPartyStrip(rowsFromCounts({ A: 5, B: 4, C: 3, D: 2, E: 1, F: 1 }));
    expect(strip.segments).toHaveLength(5);
    const other = strip.segments[strip.segments.length - 1];
    expect(other.is_other).toBe(true);
    expect(other.party_short).toBe("Other");
    expect(other.color).toBe(STRIP_OTHER_COLOR);
    expect(other.count).toBe(2); // E(1) + F(1)
    expect(strip.leader_label).toBe("A 5/16");
    const sum = strip.segments.reduce((acc, s) => acc + s.pct, 0);
    expect(sum).toBeCloseTo(100, 6);
  });

  it("empty group yields no segments and an empty label", () => {
    const strip = buildPartyStrip([]);
    expect(strip.segments).toHaveLength(0);
    expect(strip.leader_label).toBe("");
    expect(strip.total).toBe(0);
  });
});

describe("marginBand - RdYlBu bands (shared with StateOverview)", () => {
  it("< 5 is the red nail-biter band", () => {
    expect(marginBand(2.1)).toEqual({ key: "nail-biter", hex: "#d7191c", label: "nail-biter" });
  });
  it("[5,10) is the orange contestable band", () => {
    expect(marginBand(5)?.key).toBe("contestable");
    expect(marginBand(7.4)?.hex).toBe("#fdae61");
  });
  it(">= 10 is the blue comfortable band", () => {
    expect(marginBand(10)?.key).toBe("comfortable");
    expect(marginBand(12.6)?.hex).toBe("#2c7bb6");
  });
  it("returns null for an unknown margin", () => {
    expect(marginBand(null)).toBeNull();
    expect(marginBand(undefined)).toBeNull();
    expect(marginBand(Number.NaN)).toBeNull();
  });
});

describe("reservationKind - GEN / SC / ST normalisation", () => {
  it("maps SC / ST (any case, padded) to themselves", () => {
    expect(reservationKind("SC")).toBe("SC");
    expect(reservationKind("st")).toBe("ST");
    expect(reservationKind(" ST ")).toBe("ST");
  });
  it("collapses GEN / null / undefined / empty to GEN (no badge)", () => {
    expect(reservationKind("GEN")).toBe("GEN");
    expect(reservationKind(null)).toBe("GEN");
    expect(reservationKind(undefined)).toBe("GEN");
    expect(reservationKind("")).toBe("GEN");
  });
});

describe("applyFilters + count line - Reserved filter AND name search", () => {
  const rows: Leaf[] = [
    leaf({ entity_name: "Alpha", reservation: "SC", district: "D1" }),
    leaf({ entity_name: "Beta", reservation: "GEN", district: "D1" }),
    leaf({ entity_name: "Gamma", reservation: "ST", district: "D2" }),
    leaf({ entity_name: "Delta", reservation: "SC", district: "D2" }),
  ];

  it("ORACLE: Reserved=SC yields only SC leaves and the count text matches", () => {
    const sc = applyFilters(rows, "", "SC");
    expect(sc.map((r) => r.entity_name)).toEqual(["Alpha", "Delta"]);
    const text = formatCountLine(sc.length, distinctDistrictCount(sc));
    expect(text).toBe("2 constituencies in 2 districts");
  });

  it("All shows every row; the count reflects the full set", () => {
    const all = applyFilters(rows, "", "All");
    expect(all).toHaveLength(4);
    expect(formatCountLine(all.length, distinctDistrictCount(all))).toBe("4 constituencies in 2 districts");
  });

  it("AND-composes the name search with the Reserved filter", () => {
    const scAlpha = applyFilters(rows, "alp", "SC");
    expect(scAlpha.map((r) => r.entity_name)).toEqual(["Alpha"]);
    expect(formatCountLine(scAlpha.length, distinctDistrictCount(scAlpha))).toBe("1 constituency in 1 district");
  });
});

describe("sortLeaves - ballot order vs by-margin", () => {
  const rows: Leaf[] = [
    leaf({ entity_id: "a", entity_name: "A", eci_no: 3, margin_pct: 12 }),
    leaf({ entity_id: "b", entity_name: "B", eci_no: 1, margin_pct: 2 }),
    leaf({ entity_id: "c", entity_name: "C", eci_no: 2, margin_pct: 7 }),
  ];

  it("ORACLE: ballot orders by eci_no ascending; margin orders nail-biters first", () => {
    expect(sortLeaves(rows, "ballot").map((r) => r.eci_no)).toEqual([1, 2, 3]);
    expect(sortLeaves(rows, "margin").map((r) => r.margin_pct)).toEqual([2, 7, 12]);
  });

  it("does not mutate the input array", () => {
    const before = rows.map((r) => r.entity_id);
    sortLeaves(rows, "margin");
    expect(rows.map((r) => r.entity_id)).toEqual(before);
  });

  it("sinks null sort keys to the end, stably", () => {
    const mixed: Leaf[] = [
      leaf({ entity_id: "x", entity_name: "X", eci_no: null, margin_pct: 5 }),
      leaf({ entity_id: "y", entity_name: "Y", eci_no: 2, margin_pct: 5 }),
      leaf({ entity_id: "z", entity_name: "Z", eci_no: 1, margin_pct: 5 }),
    ];
    expect(sortLeaves(mixed, "ballot").map((r) => r.entity_id)).toEqual(["z", "y", "x"]);
  });
});
