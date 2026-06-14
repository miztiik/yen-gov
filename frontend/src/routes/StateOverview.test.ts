import { describe, expect, it } from "vitest";
import { buildKpiTiles, NO_ASSEMBLY_UT_SLUGS } from "./StateOverview.svelte";
import type { ConstituencyEntry } from "../lib/data";
import type { District } from "../lib/view-models/districts";

function ac(eci_no: number, reservation: "GEN" | "SC" | "ST"): ConstituencyEntry {
  return { eci_no, name: `AC-${eci_no}`, reservation };
}

const TN_FOUR: ConstituencyEntry[] = [
  ac(1, "GEN"),
  ac(2, "GEN"),
  ac(3, "SC"),
  ac(4, "ST"),
];

const DISTRICTS_THREE: District[] = [
  { id: "D1", name: "District One" },
  { id: "D2", name: "District Two" },
  { id: "D3", name: "District Three" },
];

describe("buildKpiTiles", () => {
  it("returns empty array when acs is null (loader in flight)", () => {
    expect(buildKpiTiles(null, null, null)).toEqual([]);
    expect(buildKpiTiles(null, DISTRICTS_THREE, 1000)).toEqual([]);
  });

  it("emits 4 tiles when electors is null/0/undefined", () => {
    const noElectors = buildKpiTiles(TN_FOUR, DISTRICTS_THREE, null);
    expect(noElectors).toHaveLength(4);
    expect(noElectors.map(t => t.key)).toEqual([
      "assemblies", "districts", "reserved", "general",
    ]);

    expect(buildKpiTiles(TN_FOUR, DISTRICTS_THREE, 0)).toHaveLength(4);
    expect(buildKpiTiles(TN_FOUR, DISTRICTS_THREE, undefined)).toHaveLength(4);
  });

  it("emits 5 tiles when electors > 0; voters tile uses Indian compact format", () => {
    const tiles = buildKpiTiles(TN_FOUR, DISTRICTS_THREE, 31_200_000);
    expect(tiles).toHaveLength(5);
    const voters = tiles.find(t => t.key === "voters");
    expect(voters?.label).toBe("Total voters");
    // en-IN compact-notation: 3.12 Cr (crore = 10^7). Exact glyph
    // varies (NBSP vs regular space); assert the digit shape + Cr.
    expect(voters?.value).toMatch(/^3\.12\s*Cr$/);
  });

  it("splits reservation correctly: RESERVED = SC+ST, GENERAL = GEN", () => {
    const tiles = buildKpiTiles(TN_FOUR, DISTRICTS_THREE, null);
    const reserved = tiles.find(t => t.key === "reserved");
    const general = tiles.find(t => t.key === "general");
    expect(reserved?.value).toBe("2"); // 1 SC + 1 ST
    expect(general?.value).toBe("2");  // 2 GEN
  });

  it("DISTRICTS tile shows em-dash when districts loader has not resolved", () => {
    const tiles = buildKpiTiles(TN_FOUR, null, null);
    const districts = tiles.find(t => t.key === "districts");
    expect(districts?.value).toBe("-");
  });

  it("ASSEMBLIES value formats large counts with Indian grouping", () => {
    const bigAcs: ConstituencyEntry[] = Array.from({ length: 1234 }, (_, i) =>
      ac(i + 1, i % 3 === 0 ? "SC" : "GEN"),
    );
    const tiles = buildKpiTiles(bigAcs, DISTRICTS_THREE, null);
    const assemblies = tiles.find(t => t.key === "assemblies");
    // en-IN groups as 1,234 (no lakhs separator for 4-digit numbers).
    expect(assemblies?.value).toBe("1,234");
  });
});

describe("NO_ASSEMBLY_UT_SLUGS", () => {
  it("enumerates exactly the 5 UTs without a Vidhan Sabha", () => {
    expect(NO_ASSEMBLY_UT_SLUGS.size).toBe(5);
    expect([...NO_ASSEMBLY_UT_SLUGS].sort()).toEqual([
      "andaman-and-nicobar-islands",
      "chandigarh",
      "dadra-and-nagar-haveli-and-daman-and-diu",
      "ladakh",
      "lakshadweep",
    ]);
  });

  it("excludes the 3 UTs that DO have assemblies (Delhi / Puducherry / J&K)", () => {
    // Slugs are the canonical entities.json display_name shape (what
    // states.slug() actually returns at runtime), not the seed shape.
    expect(NO_ASSEMBLY_UT_SLUGS.has("nct-of-delhi")).toBe(false);
    expect(NO_ASSEMBLY_UT_SLUGS.has("puducherry")).toBe(false);
    expect(NO_ASSEMBLY_UT_SLUGS.has("jammu-and-kashmir-ut")).toBe(false);
  });

  it("excludes regular states", () => {
    for (const s of ["tamil-nadu", "karnataka", "kerala", "uttar-pradesh", "sikkim", "goa"]) {
      expect(NO_ASSEMBLY_UT_SLUGS.has(s)).toBe(false);
    }
  });
});
