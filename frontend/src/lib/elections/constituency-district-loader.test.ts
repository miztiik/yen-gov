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
  buildAcEntities,
  buildAcNameIndex,
  buildPcGrouping,
  resolveAcByName,
  type DistrictRow,
  type ElectoralAcEntityRow,
  type ElectoralAcRow,
  type MembershipRow,
  type PcRef,
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

// ---------------------------------------------------------------------------
// Row-5 oracle (TODO/20260622-election-constituency-grouping-plan.md): the
// pure PC -> AC -> District grouping for a state's general (parliament) page.
// Bounded in-memory AP fixture (no DuckDB) exercising the native PC join
// (AC.parent == PCwinner.entity_id), the is_primary district resolution, the
// re-delimitation ORPHAN -> "Other" path, and the delimitation + state
// scoping. The AC `parent` IS the PC entity_id verbatim from electoral.csv.
// ---------------------------------------------------------------------------

const PC_AMALAPURAM = "IN-PC-2008-andhra-pradesh-411";
const PC_VIJAYAWADA = "IN-PC-2008-andhra-pradesh-415";

// The two AP PCs that would be the NATIONAL-PC winners for the event.
const pcRefs: PcRef[] = [
  { entity_id: PC_AMALAPURAM, name: "Amalapuram" },
  { entity_id: PC_VIJAYAWADA, name: "Vijayawada" },
];

// is_primary edges (AC 3166 spans two districts; Konaseema is plurality).
const pcMembership: MembershipRow[] = [
  { electoral_id: "IN-AC-2008-andhra-pradesh-3166", lgd_district_id: "andhra-pradesh/dr-b-r-ambedkar-konaseema", is_primary: true },
  { electoral_id: "IN-AC-2008-andhra-pradesh-3166", lgd_district_id: "andhra-pradesh/east-godavari", is_primary: false },
  { electoral_id: "IN-AC-2008-andhra-pradesh-3167", lgd_district_id: "andhra-pradesh/dr-b-r-ambedkar-konaseema", is_primary: true },
  { electoral_id: "IN-AC-2008-andhra-pradesh-3250", lgd_district_id: "andhra-pradesh/krishna", is_primary: true },
  { electoral_id: "IN-AC-2008-andhra-pradesh-3251", lgd_district_id: "andhra-pradesh/ntr", is_primary: true },
  { electoral_id: "IN-AC-2008-andhra-pradesh-9001", lgd_district_id: "andhra-pradesh/krishna", is_primary: true },
  { electoral_id: "IN-AC-2008-andhra-pradesh-8001", lgd_district_id: "andhra-pradesh/krishna", is_primary: true },
  { electoral_id: "IN-AC-2008-telangana-7001", lgd_district_id: "telangana/hyderabad", is_primary: true },
];

const pcDistricts: DistrictRow[] = [
  { entity_id: "andhra-pradesh/dr-b-r-ambedkar-konaseema", name: "Dr. B.R. Ambedkar Konaseema" },
  { entity_id: "andhra-pradesh/east-godavari", name: "East Godavari" },
  { entity_id: "andhra-pradesh/krishna", name: "Krishna" },
  { entity_id: "andhra-pradesh/ntr", name: "NTR" },
  { entity_id: "telangana/hyderabad", name: "Hyderabad" },
];

// Four in-scope AP-2008 ACs (2 per PC) + three edge ACs that MUST NOT group
// under a PC: 9001 (parent PC 999 not a winner -> orphan), 8001 (1976 delim
// -> filtered), 7001 (telangana -> filtered).
const pcElectoralAcs: ElectoralAcEntityRow[] = [
  { entity_id: "IN-AC-2008-andhra-pradesh-3166", name: "Amalapuram", parent: PC_AMALAPURAM, state: "andhra-pradesh", delim_year: 2008, reservation: "SC", eci_no: 163 },
  { entity_id: "IN-AC-2008-andhra-pradesh-3167", name: "Razole", parent: PC_AMALAPURAM, state: "andhra-pradesh", delim_year: 2008, reservation: "GEN", eci_no: 164 },
  { entity_id: "IN-AC-2008-andhra-pradesh-3250", name: "Vijayawada West", parent: PC_VIJAYAWADA, state: "andhra-pradesh", delim_year: 2008, reservation: "GEN", eci_no: 80 },
  { entity_id: "IN-AC-2008-andhra-pradesh-3251", name: "Mylavaram", parent: PC_VIJAYAWADA, state: "andhra-pradesh", delim_year: 2008, reservation: "GEN", eci_no: 82 },
  { entity_id: "IN-AC-2008-andhra-pradesh-9001", name: "Orphan AC", parent: "IN-PC-2008-andhra-pradesh-999", state: "andhra-pradesh", delim_year: 2008, reservation: "GEN", eci_no: 300 },
  { entity_id: "IN-AC-2008-andhra-pradesh-8001", name: "Old Delim AC", parent: "IN-PC-1976-andhra-pradesh-9", state: "andhra-pradesh", delim_year: 1976, reservation: "GEN", eci_no: 5 },
  { entity_id: "IN-AC-2008-telangana-7001", name: "Telangana AC", parent: "IN-PC-2008-telangana-1", state: "telangana", delim_year: 2008, reservation: "GEN", eci_no: 1 },
];

describe("buildAcEntities + buildPcGrouping (Row-5 oracle, AP general fixture)", () => {
  const entities = buildAcEntities(pcMembership, pcDistricts, pcElectoralAcs);
  const districtNames = pcDistricts.map((d) => d.name);

  it("buildAcEntities resolves the is_primary district to a real LGD name (never a slug)", () => {
    const byId = new Map(entities.map((e) => [e.entity_id, e]));
    // The multi-district AC resolves to its PLURALITY district (Konaseema),
    // not the is_primary=false East Godavari edge.
    expect(byId.get("IN-AC-2008-andhra-pradesh-3166")?.district_name).toBe(
      "Dr. B.R. Ambedkar Konaseema",
    );
    for (const e of entities) {
      if (e.district_name === null) continue;
      expect(districtNames).toContain(e.district_name);
      expect(e.district_name).not.toContain("/"); // never a raw slug
    }
    // parent_pc_id + state + delim_year carried through verbatim.
    const a3166 = byId.get("IN-AC-2008-andhra-pradesh-3166");
    expect(a3166?.parent_pc_id).toBe(PC_AMALAPURAM);
    expect(a3166?.state).toBe("andhra-pradesh");
    expect(a3166?.delim_year).toBe(2008);
  });

  const grouping = buildPcGrouping(pcRefs, entities, "andhra-pradesh", 2008);

  it("leaves equal EXACTLY the ACs whose parent == that PC entity_id", () => {
    const leafIdsFor = (pcName: string) =>
      new Set(
        grouping.leaves
          .filter((l) => l.pc_group === pcName)
          .map((l) => l.entity_id),
      );
    const expectedFor = (pcId: string) =>
      new Set(
        pcElectoralAcs
          .filter(
            (e) =>
              e.parent === pcId &&
              e.state === "andhra-pradesh" &&
              e.delim_year === 2008,
          )
          .map((e) => e.entity_id),
      );
    expect([...leafIdsFor("Amalapuram")].sort()).toEqual(
      [...expectedFor(PC_AMALAPURAM)].sort(),
    );
    expect([...leafIdsFor("Vijayawada")].sort()).toEqual(
      [...expectedFor(PC_VIJAYAWADA)].sort(),
    );
    // Concretely: Amalapuram has 3166 + 3167.
    expect([...leafIdsFor("Amalapuram")].sort()).toEqual([
      "IN-AC-2008-andhra-pradesh-3166",
      "IN-AC-2008-andhra-pradesh-3167",
    ]);
  });

  it("each leaf shows its is_primary district name (real LGD name, not a slug)", () => {
    const byId = new Map(grouping.leaves.map((l) => [l.entity_id, l]));
    expect(byId.get("IN-AC-2008-andhra-pradesh-3166")?.district_name).toBe(
      "Dr. B.R. Ambedkar Konaseema",
    );
    expect(byId.get("IN-AC-2008-andhra-pradesh-3251")?.district_name).toBe("NTR");
    for (const l of grouping.leaves) {
      if (l.district_name === null) continue;
      expect(l.district_name).not.toContain("/");
    }
  });

  it("childCountByPcId feeds the group-header child_count (one per child AC)", () => {
    expect(grouping.childCountByPcId.get(PC_AMALAPURAM)).toBe(2);
    expect(grouping.childCountByPcId.get(PC_VIJAYAWADA)).toBe(2);
    // The orphan's parent PC is not a winner -> not counted.
    expect(
      grouping.childCountByPcId.get("IN-PC-2008-andhra-pradesh-999"),
    ).toBeUndefined();
  });

  it("an AC whose parent PC is not a winner is an orphan (pc_group null), never dropped", () => {
    const orphan = grouping.leaves.find(
      (l) => l.entity_id === "IN-AC-2008-andhra-pradesh-9001",
    );
    expect(orphan).toBeDefined();
    expect(orphan?.pc_group).toBeNull();
    // Still carries its district so the component groups it under its
    // district / "Other" instead of dropping it (plan 7.2).
    expect(orphan?.district_name).toBe("Krishna");
  });

  it("scopes to the state + live delimitation (old-delim + other-state ACs excluded)", () => {
    const ids = new Set(grouping.leaves.map((l) => l.entity_id));
    expect(ids.has("IN-AC-2008-andhra-pradesh-8001")).toBe(false); // 1976 delim
    expect(ids.has("IN-AC-2008-telangana-7001")).toBe(false); // telangana
    // Exactly the 5 in-scope AP-2008 ACs (4 grouped under a PC + 1 orphan).
    expect(grouping.leaves.length).toBe(5);
  });
});

// ---------------------------------------------------------------------------
// Name-bridge oracle (fix/assembly-district-name-join): assembly RESULT
// winners carry the RESULTS-scheme entity_id `IN-S<NN>-AC-<delim>-<eci_no>`,
// which does NOT match the canonical electoral_id the district edge is keyed
// on. The bridge is the AC NAME. This proves the entity_id-only join resolves
// NOTHING for results-scheme winners, while the (state, name) bridge recovers
// the district for every name-matching winner and leaves the rest null (the
// component's "Other" bucket). Bounded in-memory AP fixture (no DuckDB).
// ---------------------------------------------------------------------------

const NB_MEMBERSHIP: MembershipRow[] = [
  { electoral_id: "IN-AC-2008-andhra-pradesh-3166", lgd_district_id: "andhra-pradesh/dr-b-r-ambedkar-konaseema", is_primary: true },
  { electoral_id: "IN-AC-2008-andhra-pradesh-3250", lgd_district_id: "andhra-pradesh/krishna", is_primary: true },
];

const NB_DISTRICTS: DistrictRow[] = [
  { entity_id: "andhra-pradesh/dr-b-r-ambedkar-konaseema", name: "Dr. B.R. Ambedkar Konaseema" },
  { entity_id: "andhra-pradesh/krishna", name: "Krishna" },
];

// Canonical electoral.csv AC rows. The `...-eci44` ALIAS of Amalapuram
// (authoritative ballot serial, UPPERCASE name, NO membership district) must
// NOT shadow the district-bearing `...-3166` row in the name index.
const NB_ELECTORAL: ElectoralAcEntityRow[] = [
  { entity_id: "IN-AC-2008-andhra-pradesh-3166", name: "Amalapuram", parent: null, state: "andhra-pradesh", delim_year: 2008, reservation: "SC", eci_no: 163 },
  { entity_id: "IN-AC-2008-andhra-pradesh-3250", name: "Vijayawada West", parent: null, state: "andhra-pradesh", delim_year: 2008, reservation: "GEN", eci_no: 80 },
  { entity_id: "IN-AC-2008-andhra-pradesh-eci44", name: "AMALAPURAM", parent: null, state: "andhra-pradesh", delim_year: 2008, reservation: "SC", eci_no: 44 },
];

// The Row-4 enrichment map is keyed by the CANONICAL electoral_id.
const NB_ELECTORAL_ROWS: ElectoralAcRow[] = NB_ELECTORAL.map((e) => ({
  entity_id: e.entity_id,
  reservation: e.reservation,
  eci_no: e.eci_no,
}));

// Assembly RESULT winners: RESULTS-scheme entity_id (state code + ballot
// serial) that matches NO canonical electoral_id; only the NAME matches.
// "Unmapped Seat" has no canonical name twin -> stays null.
const NB_WINNERS: { entity_id: string; entity_name: string }[] = [
  { entity_id: "IN-S01-AC-2008-44", entity_name: "Amalapuram" },
  { entity_id: "IN-S01-AC-2008-80", entity_name: "Vijayawada West" },
  { entity_id: "IN-S01-AC-2008-99", entity_name: "Unmapped Seat" },
];

describe("buildAcNameIndex + resolveAcByName (name-bridge oracle, results-id mismatch)", () => {
  const acEntities = buildAcEntities(NB_MEMBERSHIP, NB_DISTRICTS, NB_ELECTORAL);
  const enrich = buildAcEnrichmentMap(NB_MEMBERSHIP, NB_DISTRICTS, NB_ELECTORAL_ROWS);
  const nameIndex = buildAcNameIndex(acEntities);

  // The EXACT resolution the assembly page runs: entity_id FIRST (exact),
  // then the (state, name) bridge on a miss.
  const resolveMeta = (w: { entity_id: string; entity_name: string }) =>
    enrich.get(w.entity_id) ??
    resolveAcByName(nameIndex, "andhra-pradesh", w.entity_name) ??
    null;

  it("entity_id-only resolves NOTHING for results-scheme winners", () => {
    for (const w of NB_WINNERS) {
      expect(enrich.get(w.entity_id)).toBeUndefined();
    }
  });

  it("the name bridge resolves the district for every name-matching winner", () => {
    expect(resolveMeta(NB_WINNERS[0])?.district_name).toBe(
      "Dr. B.R. Ambedkar Konaseema",
    );
    expect(resolveMeta(NB_WINNERS[1])?.district_name).toBe("Krishna");
  });

  it("carries reservation through the name bridge", () => {
    expect(resolveMeta(NB_WINNERS[0])?.reservation).toBe("SC");
  });

  it("a winner with no canonical name twin stays null (-> Other bucket)", () => {
    expect(resolveMeta(NB_WINNERS[2])).toBeNull();
  });

  it("a district-less ballot alias never shadows the real district edge", () => {
    // "Amalapuram" (district-bearing 3166) and "AMALAPURAM" (district-less
    // eci44 alias) slug to the same (state, name) key; the district-bearing
    // row must win.
    const info = resolveAcByName(nameIndex, "andhra-pradesh", "Amalapuram");
    expect(info?.district_name).toBe("Dr. B.R. Ambedkar Konaseema");
    expect(info?.entity_id).toBe("IN-AC-2008-andhra-pradesh-3166");
  });

  it("coverage rises from entity_id-only (0) to name-bridged (2 of 3)", () => {
    const entityIdCoverage = NB_WINNERS.filter(
      (w) => enrich.get(w.entity_id)?.district_name != null,
    ).length;
    const nameBridgedCoverage = NB_WINNERS.filter(
      (w) => resolveMeta(w)?.district_name != null,
    ).length;
    expect(entityIdCoverage).toBe(0);
    expect(nameBridgedCoverage).toBe(2);
    expect(nameBridgedCoverage).toBeGreaterThan(entityIdCoverage);
  });

  it("keys by state so same-named ACs in other states never collide", () => {
    expect(resolveAcByName(nameIndex, "telangana", "Amalapuram")).toBeNull();
  });
});
