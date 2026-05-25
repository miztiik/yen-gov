import { describe, it, expect } from "vitest";
import { uniqueFacetsInOrder, pickDefaultFacet } from "./facet-picker";
import type { IndicatorRow } from "./indicators";

// RPO-shape fixture: S22 has all 3 facets across 2 years; S11 has only
// solar; S99 absent. Mirrors the data shape the canonical adapter emits
// for energy/state_rpo_compliance_pct (see indicator-allowlist.ts).
const RPO_ROWS: IndicatorRow[] = [
  { entity_id: "S22", time: "2022", value: 45,  facet: "solar"     },
  { entity_id: "S22", time: "2023", value: 50,  facet: "solar"     },
  { entity_id: "S22", time: "2022", value: 75,  facet: "non-solar" },
  { entity_id: "S22", time: "2023", value: 80,  facet: "non-solar" },
  { entity_id: "S22", time: "2022", value: 120, facet: "total"     },
  { entity_id: "S22", time: "2023", value: 130, facet: "total"     },
  { entity_id: "S11", time: "2023", value: 60,  facet: "solar"     },
];

describe("uniqueFacetsInOrder", () => {
  it("returns distinct facets in first-appearance order", () => {
    expect(uniqueFacetsInOrder(RPO_ROWS)).toEqual([
      "solar",
      "non-solar",
      "total",
    ]);
  });

  it("skips null and empty facets", () => {
    const rows: IndicatorRow[] = [
      { entity_id: "S22", time: "2024", value: 10, facet: null },
      { entity_id: "S22", time: "2024", value: 20, facet: "" },
      { entity_id: "S22", time: "2024", value: 30, facet: "a" },
    ];
    expect(uniqueFacetsInOrder(rows)).toEqual(["a"]);
  });

  it("returns [] when no row carries a facet (non-faceted indicator)", () => {
    const rows: IndicatorRow[] = [
      { entity_id: "S22", time: "2024", value: 100, facet: null },
      { entity_id: "S11", time: "2024", value: 200, facet: null },
    ];
    expect(uniqueFacetsInOrder(rows)).toEqual([]);
  });
});

describe("pickDefaultFacet", () => {
  const FACETS = ["solar", "non-solar", "total"] as const;

  it("returns null when facets is empty (signals not-faceted)", () => {
    expect(pickDefaultFacet(RPO_ROWS, "S22", [])).toBeNull();
  });

  it("falls back to first declared facet when home_entity is null", () => {
    expect(pickDefaultFacet(RPO_ROWS, null, FACETS)).toBe("solar");
  });

  it("falls back to first declared facet when home has no data in any facet", () => {
    expect(pickDefaultFacet(RPO_ROWS, "S99", FACETS)).toBe("solar");
  });

  it("picks the only-covered facet when home has data in just one (S11 has only solar)", () => {
    expect(pickDefaultFacet(RPO_ROWS, "S11", FACETS)).toBe("solar");
  });

  it("breaks ties using declaration order (S22 has 2 rows in each facet — first wins)", () => {
    expect(pickDefaultFacet(RPO_ROWS, "S22", FACETS)).toBe("solar");
  });

  it("respects a reordered declaration list on ties (non-solar first => non-solar wins)", () => {
    expect(
      pickDefaultFacet(RPO_ROWS, "S22", ["non-solar", "solar", "total"]),
    ).toBe("non-solar");
  });

  it("counts only non-null values (1 solar value beats 3 null totals)", () => {
    const rows: IndicatorRow[] = [
      { entity_id: "S22", time: "2022", value: 45,   facet: "solar" },
      { entity_id: "S22", time: "2022", value: null, facet: "total" },
      { entity_id: "S22", time: "2023", value: null, facet: "total" },
      { entity_id: "S22", time: "2024", value: null, facet: "total" },
    ];
    expect(pickDefaultFacet(rows, "S22", ["solar", "total"])).toBe("solar");
  });

  it("ignores rows for other entities when counting (S11's solar row does not boost S22's count)", () => {
    const facet_choice = pickDefaultFacet(RPO_ROWS, "S22", FACETS);
    // S22 has 2 rows in EACH facet; S11 has 1 row in solar. If the helper
    // were leaking across entities, S11's row would tip solar to 3 and
    // win unambiguously — but that's the same outcome as the tiebreaker
    // path. The discriminating check is the reordered-declaration test
    // above, which proves declaration order — not a leak — drives the tie.
    expect(facet_choice).toBe("solar");
  });
});
