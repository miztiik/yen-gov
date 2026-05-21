// Unit tests for the districts view-model loader (Phase-0 closeout
// T.0c-ii-B.2).
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
import { loadDistricts } from "./districts";

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
