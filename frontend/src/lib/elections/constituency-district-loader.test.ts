// Row-4 oracle (TODO/20260622-election-constituency-grouping-plan.md):
// the pure AC -> {district, reservation, eci_no} enrichment builder.
//
// Tested with a BOUNDED in-memory Andhra Pradesh fixture (no DuckDB
// spin-up, no real corpus walk - per the no-frontend-corpus-explosion
// rule). The fixture uses real AP slugs + display names so the
// "resolve the slug, never title-case it" guarantee is exercised on a
// genuinely punctuated name ("Dr. B.R. Ambedkar Konaseema").

import { describe, expect, it } from "vitest";
import {
  buildAcEnrichmentMap,
  type DistrictRow,
  type ElectoralAcRow,
  type MembershipRow,
} from "./constituency-district-loader";

// AC 3166 spans two districts (Konaseema primary, East Godavari not) ->
// proves an AC lands in exactly one group. AC 9999 is in electoral.csv
// but has NO membership edge -> proves the unmapped -> null "Other" path.
const membership: MembershipRow[] = [
  {
    electoral_id: "IN-AC-2008-andhra-pradesh-3166",
    lgd_district_id: "andhra-pradesh/dr-b-r-ambedkar-konaseema",
    is_primary: true,
  },
  {
    electoral_id: "IN-AC-2008-andhra-pradesh-3166",
    lgd_district_id: "andhra-pradesh/east-godavari",
    is_primary: false,
  },
  {
    electoral_id: "IN-AC-2008-andhra-pradesh-3167",
    lgd_district_id: "andhra-pradesh/dr-b-r-ambedkar-konaseema",
    is_primary: true,
  },
  {
    electoral_id: "IN-AC-2008-andhra-pradesh-3200",
    lgd_district_id: "andhra-pradesh/guntur",
    is_primary: true,
  },
  {
    electoral_id: "IN-AC-2008-andhra-pradesh-3201",
    lgd_district_id: "andhra-pradesh/guntur",
    is_primary: true,
  },
  {
    electoral_id: "IN-AC-2008-andhra-pradesh-3250",
    lgd_district_id: "andhra-pradesh/krishna",
    is_primary: true,
  },
];

const districts: DistrictRow[] = [
  {
    entity_id: "andhra-pradesh/dr-b-r-ambedkar-konaseema",
    name: "Dr. B.R. Ambedkar Konaseema",
  },
  { entity_id: "andhra-pradesh/east-godavari", name: "East Godavari" },
  { entity_id: "andhra-pradesh/guntur", name: "Guntur" },
  { entity_id: "andhra-pradesh/krishna", name: "Krishna" },
];

const electoralAcs: ElectoralAcRow[] = [
  { entity_id: "IN-AC-2008-andhra-pradesh-3166", reservation: "GEN", eci_no: 163 },
  { entity_id: "IN-AC-2008-andhra-pradesh-3167", reservation: "GEN", eci_no: 165 },
  { entity_id: "IN-AC-2008-andhra-pradesh-3200", reservation: "SC", eci_no: 95 },
  { entity_id: "IN-AC-2008-andhra-pradesh-3201", reservation: "GEN", eci_no: 96 },
  { entity_id: "IN-AC-2008-andhra-pradesh-3250", reservation: "GEN", eci_no: 80 },
  // Unmapped: present in electoral.csv, absent from membership.
  { entity_id: "IN-AC-2008-andhra-pradesh-9999", reservation: "ST", eci_no: 200 },
];

// Every lgd_district_id slug in the fixture (used to assert no slug
// ever leaks into a district VALUE).
const allSlugs = new Set(membership.map((m) => m.lgd_district_id));

describe("buildAcEnrichmentMap (Row-4 oracle, AP fixture)", () => {
  const map = buildAcEnrichmentMap(membership, districts, electoralAcs);
  const districtNames = districts.map((d) => d.name);

  it("never emits a raw slug: every district is a real LGD name or null", () => {
    for (const [, enr] of map) {
      if (enr.district_name === null) continue;
      expect(districtNames).toContain(enr.district_name);
      expect(allSlugs.has(enr.district_name)).toBe(false);
      expect(enr.district_name).not.toContain("/");
    }
  });

  it("distinct non-null districts == distinct is_primary districts for AP", () => {
    // Expected from the fixture: the is_primary edges resolve to
    // Konaseema (3166, 3167), Guntur (3200, 3201), Krishna (3250).
    // East Godavari is is_primary=false -> excluded.
    const expected = new Set<string>();
    for (const m of membership) {
      if (!m.is_primary) continue;
      const name = districts.find((d) => d.entity_id === m.lgd_district_id)?.name;
      if (name) expected.add(name);
    }
    const actual = new Set<string>();
    for (const [, enr] of map) {
      if (enr.district_name !== null) actual.add(enr.district_name);
    }
    expect([...actual].sort()).toEqual([...expected].sort());
    // Sanity: AP groups into more than one district (proves grouping
    // lights up rather than collapsing to one flat list).
    expect(actual.size).toBe(3);
    expect(actual).toContain("Dr. B.R. Ambedkar Konaseema");
    expect(actual).not.toContain("East Godavari"); // is_primary=false
  });

  it("maps each AC to exactly one district (no AC in two groups)", () => {
    // The multi-district AC resolves to its PRIMARY district only.
    expect(map.get("IN-AC-2008-andhra-pradesh-3166")?.district_name).toBe(
      "Dr. B.R. Ambedkar Konaseema",
    );
    // A Map keyed by electoral_id structurally guarantees one entry per
    // AC; assert the count matches the distinct ACs in the inputs.
    const distinctAcs = new Set<string>([
      ...membership.map((m) => m.electoral_id),
      ...electoralAcs.map((e) => e.entity_id),
    ]);
    expect(map.size).toBe(distinctAcs.size);
  });

  it("passes reservation + eci_no through from electoral.csv", () => {
    expect(map.get("IN-AC-2008-andhra-pradesh-3200")).toEqual({
      district_name: "Guntur",
      reservation: "SC",
      eci_no: 95,
    });
  });

  it("an unmapped AC keeps reservation + eci_no but has null district", () => {
    expect(map.get("IN-AC-2008-andhra-pradesh-9999")).toEqual({
      district_name: null,
      reservation: "ST",
      eci_no: 200,
    });
  });
});
