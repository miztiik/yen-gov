// Unit tests for the districts view-model loader.
// X1a-fu2-A (2026-06-07): the loaders flipped from
// `registerTable("taxonomy.entities")` (parquet) to a fetch against
// `datasets/taxonomy/entities.json` (the hand-authored SoT) because
// the legacy_id + IN-S22-D567 entity_id shape both consumers need is
// not on geo.csv. Mocks the global fetch and feeds it a hand-rolled
// rowset; the real JSON round-trip is asserted by the Playwright
// golden-path spec.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  loadDistricts,
  loadAllDistrictEntities,
  lgdCodeToDistrictEntityId,
  __resetDistrictEntitiesForTests,
} from "./districts";

// Hand-rolled entities.json rowset covering all the shapes the loaders
// project: country, two states, one UT, several districts (with and
// without legacy_id), an out-of-state district to verify the per-state
// filter, an invalid (no parent state) district to verify the join
// filter.
const sampleEntities = [
  {
    entity_id: "IN",
    entity_type: "country",
    display_name: "India",
  },
  {
    entity_id: "IN-S22",
    entity_type: "state",
    display_name: "Tamil Nadu",
    parent_entity_id: "IN",
  },
  {
    entity_id: "IN-S11",
    entity_type: "state",
    display_name: "Kerala",
    parent_entity_id: "IN",
  },
  {
    entity_id: "IN-U05",
    entity_type: "ut",
    display_name: "NCT of Delhi",
    parent_entity_id: "IN",
  },
  {
    entity_id: "IN-S22-D610",
    entity_type: "district",
    display_name: "Ariyalur",
    parent_entity_id: "IN-S22",
    lgd_code: "610",
    legacy_id: "ARI",
  },
  {
    entity_id: "IN-S22-D568",
    entity_type: "district",
    display_name: "Chennai (formerly Madras)",
    parent_entity_id: "IN-S22",
    lgd_code: "568",
    legacy_id: "CHN",
  },
  {
    entity_id: "IN-S22-D569",
    entity_type: "district",
    display_name: "Coimbatore",
    parent_entity_id: "IN-S22",
    lgd_code: "569",
    legacy_id: "COI",
  },
  // Same state, but no legacy_id - dropped by loadDistricts (cannot
  // back-join to constituencies.json's district_id field).
  {
    entity_id: "IN-S22-D745",
    entity_type: "district",
    display_name: "Mayiladuthurai",
    parent_entity_id: "IN-S22",
    lgd_code: "745",
    legacy_id: null,
  },
  {
    entity_id: "IN-S11-D582",
    entity_type: "district",
    display_name: "Ernakulam",
    parent_entity_id: "IN-S11",
    lgd_code: "582",
    legacy_id: "ERN",
  },
  {
    entity_id: "IN-U05-D050",
    entity_type: "district",
    display_name: "New Delhi",
    parent_entity_id: "IN-U05",
    lgd_code: "50",
    legacy_id: null,
  },
  // Orphan district whose parent_entity_id does not resolve to any
  // state/UT row - dropped by loadAllDistrictEntities' state-name
  // join filter.
  {
    entity_id: "IN-S99-D999",
    entity_type: "district",
    display_name: "Orphan",
    parent_entity_id: "IN-S99",
    lgd_code: "999",
    legacy_id: null,
  },
];

function mockEntitiesJsonFetch(rows: unknown[]): void {
  globalThis.fetch = vi.fn(async () =>
    new Response(JSON.stringify({ entities: rows }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  ) as unknown as typeof fetch;
}

function mockFetchError(status: number, statusText: string): void {
  globalThis.fetch = vi.fn(async () =>
    new Response(null, { status, statusText }),
  ) as unknown as typeof fetch;
}

describe("loadDistricts (entities.json)", () => {
  beforeEach(() => {
    __resetDistrictEntitiesForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns {id, name} rows filtered by parent state, with legacy_id as id", async () => {
    mockEntitiesJsonFetch(sampleEntities);
    const out = await loadDistricts("S22");

    // 3 of 4 S22 districts have legacy_id (Ariyalur, Chennai, Coimbatore).
    // The fourth (Mayiladuthurai, legacy_id=null) is dropped because
    // it cannot back-join to constituencies.json's district_id.
    expect(out).toEqual([
      { id: "ARI", name: "Ariyalur" },
      { id: "CHN", name: "Chennai (formerly Madras)" },
      { id: "COI", name: "Coimbatore" },
    ]);
  });

  it("fetches taxonomy/entities.json from the data base URL", async () => {
    mockEntitiesJsonFetch(sampleEntities);
    await loadDistricts("S22");
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const url = vi.mocked(globalThis.fetch).mock.calls[0][0] as string;
    expect(url).toContain("taxonomy/entities.json");
  });

  it("returns an empty array when the state has no districts with legacy_id", async () => {
    mockEntitiesJsonFetch(sampleEntities);
    // U05 (Delhi) has one district (New Delhi) but no legacy_id, so it
    // falls through to "(unmapped)" in StateOverview. Per-state list
    // is empty.
    const out = await loadDistricts("U05");
    expect(out).toEqual([]);
  });

  it("returns an empty array when the state has no districts in entities.json", async () => {
    mockEntitiesJsonFetch(sampleEntities);
    const out = await loadDistricts("S99");
    expect(out).toEqual([]);
  });

  it("does not return districts from other states", async () => {
    mockEntitiesJsonFetch(sampleEntities);
    const out = await loadDistricts("S22");
    // Kerala's Ernakulam (ERN) must NOT appear in the S22 list.
    expect(out.find((d) => d.id === "ERN")).toBeUndefined();
  });

  it("propagates fetch errors (caller wraps in .catch(() => null))", async () => {
    mockFetchError(404, "Not Found");
    await expect(loadDistricts("S22")).rejects.toThrow(/HTTP 404|404/);
  });
});

// ----------------------------------------------------------------------
// loadAllDistrictEntities (national, LGD-keyed)
// ----------------------------------------------------------------------

describe("loadAllDistrictEntities (entities.json, national, LGD-keyed)", () => {
  beforeEach(() => {
    __resetDistrictEntitiesForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns one row per district with parent state name resolved", async () => {
    mockEntitiesJsonFetch(sampleEntities);
    const out = await loadAllDistrictEntities();

    // 4 of 6 districts have a resolvable parent (5 with lgd_code; the
    // 6th IN-S99-D999 is dropped because its parent IN-S99 does not
    // exist as a state row). All 5 lgd_code-bearing districts in S22
    // (ARI, CHN, COI, Mayiladuthurai) + Ernakulam (S11) + New Delhi
    // (U05) survive. The "orphan" IN-S99-D999 drops out.
    expect(out).toHaveLength(6);
    const first = out.find((d) => d.entity_id === "IN-S22-D568")!;
    expect(first).toMatchObject({
      entity_id: "IN-S22-D568",
      display_name: "Chennai (formerly Madras)",
      lgd_code: "568",
      boundary_join_key: "568",
      parent_entity_id: "IN-S22",
      parent_state_name: "Tamil Nadu",
    });
  });

  it("populates boundary_join_key from lgd_code verbatim on every row", async () => {
    mockEntitiesJsonFetch(sampleEntities);
    const out = await loadAllDistrictEntities();
    for (const row of out) {
      expect(row.boundary_join_key).toBe(row.lgd_code);
    }
  });

  it("resolves parent_state_name for UT-parented districts via self-join", async () => {
    mockEntitiesJsonFetch(sampleEntities);
    const out = await loadAllDistrictEntities();
    const new_delhi = out.find((d) => d.entity_id === "IN-U05-D050")!;
    // UT parent (IN-U05 "NCT of Delhi") resolves via the same
    // entity_type IN ('state', 'ut') self-join filter.
    expect(new_delhi.parent_state_name).toBe("NCT of Delhi");
  });

  it("drops districts whose parent does not resolve to a state/UT row", async () => {
    mockEntitiesJsonFetch(sampleEntities);
    const out = await loadAllDistrictEntities();
    expect(out.find((d) => d.entity_id === "IN-S99-D999")).toBeUndefined();
  });

  it("drops districts without lgd_code (cannot key the map join)", async () => {
    mockEntitiesJsonFetch([
      ...sampleEntities,
      {
        entity_id: "IN-S22-D000",
        entity_type: "district",
        display_name: "Unkeyable",
        parent_entity_id: "IN-S22",
        lgd_code: null,
        legacy_id: null,
      },
    ]);
    const out = await loadAllDistrictEntities();
    expect(out.find((d) => d.entity_id === "IN-S22-D000")).toBeUndefined();
  });

  it("caches the result so the second call does not re-fetch entities.json", async () => {
    mockEntitiesJsonFetch(sampleEntities);
    const first = await loadAllDistrictEntities();
    const second = await loadAllDistrictEntities();
    expect(second).toBe(first);
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });

  it("shares the entities.json cache with loadDistricts (one network fetch)", async () => {
    mockEntitiesJsonFetch(sampleEntities);
    await loadDistricts("S22");
    await loadAllDistrictEntities();
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });

  it("propagates fetch errors", async () => {
    mockFetchError(404, "Not Found");
    await expect(loadAllDistrictEntities()).rejects.toThrow(/HTTP 404|404/);
  });
});

describe("lgdCodeToDistrictEntityId (LGD shape normalisation)", () => {
  beforeEach(() => {
    __resetDistrictEntitiesForTests();
    mockEntitiesJsonFetch(sampleEntities);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("resolves a plain string lgd code to the district entity_id", async () => {
    expect(await lgdCodeToDistrictEntityId("569")).toBe("IN-S22-D569");
  });

  it("resolves an integer lgd code to the district entity_id", async () => {
    expect(await lgdCodeToDistrictEntityId(568)).toBe("IN-S22-D568");
  });

  it("resolves a zero-padded lgd code (parses as integer)", async () => {
    // Fixture has lgd_code: "50" for New Delhi; "050" must match.
    expect(await lgdCodeToDistrictEntityId("050")).toBe("IN-U05-D050");
  });

  it("returns null for an lgd code that does not resolve", async () => {
    expect(await lgdCodeToDistrictEntityId("999999")).toBeNull();
  });

  it("returns null for null / undefined / whitespace inputs", async () => {
    expect(await lgdCodeToDistrictEntityId(null)).toBeNull();
    expect(await lgdCodeToDistrictEntityId(undefined)).toBeNull();
    expect(await lgdCodeToDistrictEntityId("   ")).toBeNull();
  });

  it("returns null for non-numeric input", async () => {
    expect(await lgdCodeToDistrictEntityId("not-a-number")).toBeNull();
  });
});

