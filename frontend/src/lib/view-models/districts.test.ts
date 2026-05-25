// Unit tests for the districts view-model loader (Phase-0 closeout
// T.0c-ii-B.2; extended in PR B.05 C1 with national LGD-keyed loader
// for district-grain choropleth).
//
// Mocks `query` + `registerTable` at `../duckdb` per the contract pattern
// established by PR-E (constituency.test.ts) and PR-F (state-overview.
// test.ts). The real Parquet round-trip is asserted by the Playwright
// golden-path spec against the live TN shard.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerTable: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

import { query, registerTable } from "../duckdb";
import {
  loadDistricts,
  loadAllDistrictEntities,
  lgdCodeToDistrictEntityId,
  __resetDistrictEntitiesForTests,
} from "./districts";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);

const districtRows = [
  { id: "ARI", name: "Ariyalur" },
  { id: "CHN", name: "Chennai (formerly Madras)" },
  { id: "COI", name: "Coimbatore" },
];

describe("loadDistricts (taxonomy.entities)", () => {
  beforeEach(() => {
    mockedQuery.mockReset();
    mockedRegister.mockReset();
    mockedRegister.mockResolvedValue("noop");
  });

  it("registers taxonomy.entities and returns {id, name} rows", async () => {
    mockedQuery.mockResolvedValueOnce(districtRows);
    const out = await loadDistricts("S22");

    expect(mockedRegister).toHaveBeenCalledWith("taxonomy.entities");
    expect(out).toEqual([
      { id: "ARI", name: "Ariyalur" },
      { id: "CHN", name: "Chennai (formerly Madras)" },
      { id: "COI", name: "Coimbatore" },
    ]);
  });

  it("SQL filters by parent_entity_id with the state prefix", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    await loadDistricts("S11");
    const sql = mockedQuery.mock.calls[0][0] as string;

    expect(sql).toMatch(/FROM\s+entities/);
    expect(sql).toMatch(/entity_type\s*=\s*'district'/);
    expect(sql).toMatch(/parent_entity_id\s*=\s*'IN-S11'/);
    expect(sql).toMatch(/ORDER BY display_name/);
  });

  it("returns an empty array when the state has no districts in entities.parquet", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    const out = await loadDistricts("S99");
    expect(out).toEqual([]);
  });

  it("escapes single quotes in the state code (defence-in-depth)", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    await loadDistricts("S'22");
    const sql = mockedQuery.mock.calls[0][0] as string;
    // The state code is interpolated as 'IN-S\'22'; the doubled quote is
    // DuckDB's literal-escape convention.
    expect(sql).toContain("'IN-S''22'");
  });

  it("drops rows where id or name is null (legacy_id IS NULL guard)", async () => {
    mockedQuery.mockResolvedValueOnce([
      { id: "ARI", name: "Ariyalur" },
      { id: null, name: "Unmapped" },
      { id: "CHN", name: null },
    ]);
    const out = await loadDistricts("S22");
    expect(out).toEqual([{ id: "ARI", name: "Ariyalur" }]);
  });

  it("propagates DuckDB-WASM errors (caller wraps in .catch(() => null))", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("HTTP 404"));
    await expect(loadDistricts("S22")).rejects.toThrow(/HTTP 404/);
  });
});

// ----------------------------------------------------------------------
// PR B.05 C1 — loadAllDistrictEntities (national, LGD-keyed)
// ----------------------------------------------------------------------

const districtEntityRows = [
  {
    entity_id: "IN-S22-D567",
    display_name: "Coimbatore",
    lgd_code: "567",
    parent_entity_id: "IN-S22",
    parent_state_name: "Tamil Nadu",
  },
  {
    entity_id: "IN-S22-D571",
    display_name: "Chennai",
    lgd_code: "571",
    parent_entity_id: "IN-S22",
    parent_state_name: "Tamil Nadu",
  },
  {
    entity_id: "IN-S11-D582",
    display_name: "Ernakulam",
    lgd_code: "582",
    parent_entity_id: "IN-S11",
    parent_state_name: "Kerala",
  },
  {
    entity_id: "IN-U05-D050",
    display_name: "New Delhi",
    lgd_code: "50",
    parent_entity_id: "IN-U05",
    parent_state_name: "NCT of Delhi",
  },
  {
    entity_id: "IN-S03-D756",
    display_name: "Tamulpur",
    lgd_code: "756",
    parent_entity_id: "IN-S03",
    parent_state_name: "Assam",
  },
];

describe("loadAllDistrictEntities (taxonomy.entities, national, LGD-keyed)", () => {
  beforeEach(() => {
    mockedQuery.mockReset();
    mockedRegister.mockReset();
    mockedRegister.mockResolvedValue("noop");
    __resetDistrictEntitiesForTests();
  });

  it("registers taxonomy.entities and returns one row per district with parent state name", async () => {
    mockedQuery.mockResolvedValueOnce(districtEntityRows);
    const out = await loadAllDistrictEntities();

    expect(mockedRegister).toHaveBeenCalledWith("taxonomy.entities");
    expect(out).toHaveLength(5);
    expect(out[0]).toMatchObject({
      entity_id: "IN-S22-D567",
      display_name: "Coimbatore",
      lgd_code: "567",
      boundary_join_key: "567",
      parent_entity_id: "IN-S22",
      parent_state_name: "Tamil Nadu",
    });
  });

  it("populates boundary_join_key from lgd_code verbatim on every row", async () => {
    mockedQuery.mockResolvedValueOnce(districtEntityRows);
    const out = await loadAllDistrictEntities();
    for (const row of out) {
      expect(row.boundary_join_key).toBe(row.lgd_code);
    }
  });

  it("SQL self-joins entities to resolve parent_state_name and filters to currently-valid districts", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    await loadAllDistrictEntities();
    const sql = mockedQuery.mock.calls[0][0] as string;

    expect(sql).toMatch(/FROM\s+entities\s+d/);
    expect(sql).toMatch(/LEFT JOIN entities s ON d\.parent_entity_id = s\.entity_id/);
    expect(sql).toMatch(/s\.display_name\s+AS\s+parent_state_name/);
    expect(sql).toMatch(/d\.entity_type\s*=\s*'district'/);
    expect(sql).toMatch(/d\.entity_valid_to\s+IS\s+NULL/);
    expect(sql).toMatch(/ORDER BY d\.entity_id/);
  });

  it("drops rows where any required column is null", async () => {
    mockedQuery.mockResolvedValueOnce([
      ...districtEntityRows.slice(0, 1),
      // missing parent_state_name (orphan district — parent entity_id present
      // but the self-join failed to resolve a display_name)
      {
        entity_id: "IN-S99-D999",
        display_name: "Orphan",
        lgd_code: "999",
        parent_entity_id: "IN-S99",
        parent_state_name: null,
      },
      // missing lgd_code (cannot key the map join)
      {
        entity_id: "IN-S22-D000",
        display_name: "Unkeyable",
        lgd_code: null,
        parent_entity_id: "IN-S22",
        parent_state_name: "Tamil Nadu",
      },
    ]);
    const out = await loadAllDistrictEntities();
    expect(out).toHaveLength(1);
    expect(out[0].entity_id).toBe("IN-S22-D567");
  });

  it("caches the result so the second call does not re-query DuckDB", async () => {
    mockedQuery.mockResolvedValueOnce(districtEntityRows);
    const first = await loadAllDistrictEntities();
    const second = await loadAllDistrictEntities();
    expect(second).toBe(first);
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });

  it("propagates DuckDB-WASM errors", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("HTTP 404"));
    await expect(loadAllDistrictEntities()).rejects.toThrow(/HTTP 404/);
  });
});

describe("lgdCodeToDistrictEntityId (LGD shape normalisation)", () => {
  beforeEach(() => {
    mockedQuery.mockReset();
    mockedRegister.mockReset();
    mockedRegister.mockResolvedValue("noop");
    __resetDistrictEntitiesForTests();
    mockedQuery.mockResolvedValue(districtEntityRows);
  });

  it("resolves a plain string lgd code to the district entity_id", async () => {
    expect(await lgdCodeToDistrictEntityId("567")).toBe("IN-S22-D567");
  });

  it("resolves an integer lgd code to the district entity_id", async () => {
    expect(await lgdCodeToDistrictEntityId(571)).toBe("IN-S22-D571");
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
