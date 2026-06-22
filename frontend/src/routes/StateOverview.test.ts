import { describe, expect, it } from "vitest";
import {
  buildKpiTiles,
  NO_ASSEMBLY_UT_SLUGS,
  buildAcNameDistrictIndex,
  districtNameForConstituency,
  groupConstituenciesByDistrict,
} from "./StateOverview.svelte";
import { slugify } from "../lib/slug";
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

// ---------------------------------------------------------------------------
// Row 6 - landing-page district grouping via the universal membership source.
//
// Bounded Andhra Pradesh fixture. AP's boundaries_sot constituencies.json has
// NO inline district_id (only 5 states do), so before Row 6 the landing list
// was flat. The enrichment map is keyed by entity_id with the district on the
// `...-<serial>` form; the `...-eci<NN>` ballot-alias row carries a NULL
// district and must be skipped (it must never shadow the real edge). The
// landing list shares only the NAME with the canonical store, so the join is
// `slug(name) -> entity_id -> district_name`.
// ---------------------------------------------------------------------------

const AP_ENRICHMENT = new Map<string, { district_name: string | null }>([
  ["IN-AC-2008-andhra-pradesh-3166", { district_name: "Dr B R Ambedkar Konaseema" }],
  ["IN-AC-2008-andhra-pradesh-3169", { district_name: "East Godavari" }],
  ["IN-AC-2008-andhra-pradesh-3175", { district_name: "East Godavari" }],
  // Ballot-number alias row: authoritative eci_no but NO membership edge.
  ["IN-AC-2008-andhra-pradesh-eci44", { district_name: null }],
]);

const AP_STATE_ACS: { entity_id: string; name: string }[] = [
  { entity_id: "IN-AC-2008-andhra-pradesh-3166", name: "Amalapuram" },
  { entity_id: "IN-AC-2008-andhra-pradesh-3169", name: "Mandapeta" },
  { entity_id: "IN-AC-2008-andhra-pradesh-3175", name: "Rajanagaram" },
  // UPPERCASE alias of Amalapuram with a null district - must be skipped.
  { entity_id: "IN-AC-2008-andhra-pradesh-eci44", name: "AMALAPURAM" },
];

function cons(
  eci_no: number,
  name: string,
  reservation: "GEN" | "SC" | "ST" = "GEN",
  district_id?: string,
): ConstituencyEntry {
  return district_id ? { eci_no, name, reservation, district_id } : { eci_no, name, reservation };
}

describe("buildAcNameDistrictIndex (Row 6 universal membership join)", () => {
  it("resolves slug(name) -> district from the enrichment", () => {
    const idx = buildAcNameDistrictIndex(AP_STATE_ACS, AP_ENRICHMENT);
    expect(idx.get("amalapuram")).toBe("Dr B R Ambedkar Konaseema");
    expect(idx.get("mandapeta")).toBe("East Godavari");
    expect(idx.get("rajanagaram")).toBe("East Godavari");
  });

  it("skips null-district alias rows so they never shadow the real edge", () => {
    const idx = buildAcNameDistrictIndex(AP_STATE_ACS, AP_ENRICHMENT);
    // The `-eci44` alias (null district, UPPERCASE "AMALAPURAM") slugs to the
    // same "amalapuram" key but must NOT overwrite the `-3166` edge to null.
    expect(idx.get("amalapuram")).toBe("Dr B R Ambedkar Konaseema");
    expect(idx.size).toBe(3);
  });

  it("ignores AC entity_ids absent from the enrichment", () => {
    const idx = buildAcNameDistrictIndex(
      [{ entity_id: "IN-AC-2008-andhra-pradesh-9999", name: "Ghost" }],
      AP_ENRICHMENT,
    );
    expect(idx.size).toBe(0);
  });
});

describe("districtNameForConstituency (Row 6 resolver: universal then legacy)", () => {
  const idx = buildAcNameDistrictIndex(AP_STATE_ACS, AP_ENRICHMENT);
  const legacy = new Map<string, string>([["LEG", "Legacy District"]]);

  it("prefers the universal index over the legacy district_id", () => {
    const ac = cons(44, "Amalapuram", "SC", "LEG");
    expect(districtNameForConstituency(ac, idx, legacy)).toBe("Dr B R Ambedkar Konaseema");
  });

  it("falls back to the legacy district_id name when universal misses", () => {
    // Non-regression for the 5 boundaries_sot states that carry district_id.
    const ac = cons(70, "Unjoined Seat", "GEN", "LEG");
    expect(districtNameForConstituency(ac, idx, legacy)).toBe("Legacy District");
  });

  it("falls back to the raw district_id when the legacy name map misses", () => {
    const ac = cons(70, "Unjoined Seat", "GEN", "ZZ");
    expect(districtNameForConstituency(ac, idx, legacy)).toBe("ZZ");
  });

  it("returns null (=> Other bucket) when neither resolves, incl. null index", () => {
    expect(districtNameForConstituency(cons(71, "No District"), idx, new Map())).toBeNull();
    expect(districtNameForConstituency(cons(71, "No District"), null, new Map())).toBeNull();
  });
});

describe("groupConstituenciesByDistrict (Row 6 landing grouping ORACLE)", () => {
  const idx = buildAcNameDistrictIndex(AP_STATE_ACS, AP_ENRICHMENT);
  const resolve = (ac: ConstituencyEntry) => idx.get(slugify(ac.name)) ?? null;

  // The landing list as it arrives from constituencies.json: AUTHORITATIVE
  // eci_no, no district_id. One AC ("Unmapped Seat") has no membership edge.
  const AP_ACS: ConstituencyEntry[] = [
    cons(44, "Amalapuram", "SC"),
    cons(48, "Mandapeta"),
    cons(50, "Rajanagaram"),
    cons(99, "Unmapped Seat"),
  ];

  it("groups AP from the membership source, covering EVERY AC (none dropped)", () => {
    const groups = groupConstituenciesByDistrict(AP_ACS, "", resolve);
    const total = groups.reduce((s, g) => s + g.acs.length, 0);
    expect(total).toBe(AP_ACS.length);
  });

  it("yields more than one distinct district (AP is no longer a flat list)", () => {
    const groups = groupConstituenciesByDistrict(AP_ACS, "", resolve);
    const mapped = groups.filter(g => !g.is_other);
    expect(mapped.length).toBeGreaterThan(1);
    expect(new Set(mapped.map(g => g.name)).size).toBeGreaterThan(1);
  });

  it("keeps unmapped ACs in a single trailing Other bucket", () => {
    const groups = groupConstituenciesByDistrict(AP_ACS, "", resolve);
    const other = groups.filter(g => g.is_other);
    expect(other).toHaveLength(1);
    expect(other[0].acs.map(a => a.name)).toEqual(["Unmapped Seat"]);
    expect(groups[groups.length - 1].is_other).toBe(true);
  });

  it("sorts groups by AC count desc (Other last) and ACs by ballot order", () => {
    const groups = groupConstituenciesByDistrict(AP_ACS, "", resolve);
    expect(groups.map(g => g.name)).toEqual([
      "East Godavari", // 2 ACs
      "Dr B R Ambedkar Konaseema", // 1 AC
      "Other constituencies", // 1 AC, forced last
    ]);
    const eg = groups.find(g => g.name === "East Godavari")!;
    expect(eg.acs.map(a => a.eci_no)).toEqual([48, 50]);
  });

  it("applies the name / eci_no search filter and drops empty districts", () => {
    const byName = groupConstituenciesByDistrict(AP_ACS, "amala", resolve);
    expect(byName).toHaveLength(1);
    expect(byName[0].name).toBe("Dr B R Ambedkar Konaseema");
    expect(byName[0].acs.map(a => a.name)).toEqual(["Amalapuram"]);

    const byNumber = groupConstituenciesByDistrict(AP_ACS, "99", resolve);
    expect(byNumber).toHaveLength(1);
    expect(byNumber[0].is_other).toBe(true);
  });

  it("returns no groups when nothing matches the search", () => {
    expect(groupConstituenciesByDistrict(AP_ACS, "no-such-seat", resolve)).toEqual([]);
  });
});
