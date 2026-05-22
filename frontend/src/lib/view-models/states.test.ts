// Unit tests for the states view-model loader (T.0e — STATE_NAME_TO_ECI
// retirement). Mirrors the pattern established by districts.test.ts:
// mock `query` + `registerTable` at `../duckdb`, assert SQL shape,
// returned shape, and null-row filtering. The real Parquet round-trip is
// asserted by the Playwright golden-path spec.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerTable: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

import { query, registerTable } from "../duckdb";
import {
  loadStates,
  eciFromStateName,
  __resetForTests,
} from "./states";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);

const sampleRows = [
  {
    entity_id: "IN-S22",
    eci_code: "S22",
    display_name: "Tamil Nadu",
    lgd_code: "33",
    iso_3166_2: "IN-TN",
  },
  {
    entity_id: "IN-S11",
    eci_code: "S11",
    display_name: "Kerala",
    lgd_code: "32",
    iso_3166_2: "IN-KL",
  },
  {
    entity_id: "IN-U05",
    eci_code: "U05",
    display_name: "NCT of Delhi",
    lgd_code: "07",
    iso_3166_2: "IN-DL",
  },
  {
    entity_id: "IN-U01",
    eci_code: "U01",
    display_name: "Andaman and Nicobar Islands",
    lgd_code: "35",
    iso_3166_2: "IN-AN",
  },
  {
    entity_id: "IN-U08",
    eci_code: "U08",
    display_name: "Jammu and Kashmir (UT)",
    lgd_code: "01",
    iso_3166_2: "IN-JK",
  },
];

describe("loadStates (taxonomy.entities)", () => {
  beforeEach(() => {
    mockedQuery.mockReset();
    mockedRegister.mockReset();
    mockedRegister.mockResolvedValue("noop");
    __resetForTests();
  });

  it("registers taxonomy.entities and returns one row per state/UT", async () => {
    mockedQuery.mockResolvedValueOnce(sampleRows);
    const out = await loadStates();

    expect(mockedRegister).toHaveBeenCalledWith("taxonomy.entities");
    expect(out).toHaveLength(5);
    expect(out[0]).toMatchObject({
      entity_id: "IN-S22",
      eci_code: "S22",
      display_name: "Tamil Nadu",
      boundary_join_name: "Tamil Nadu",
      lgd_code: "33",
      iso_3166_2: "IN-TN",
    });
  });

  it("SQL filters to currently-valid states + UTs only", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    await loadStates();
    const sql = mockedQuery.mock.calls[0][0] as string;

    expect(sql).toMatch(/FROM\s+entities/);
    expect(sql).toMatch(/entity_type\s+IN\s*\(\s*'state',\s*'ut'\s*\)/);
    expect(sql).toMatch(/entity_valid_to\s+IS\s+NULL/);
    expect(sql).toMatch(/ORDER BY entity_code/);
  });

  it("applies the three boundary_join_name overrides for DataMeet ST_NM compatibility", async () => {
    mockedQuery.mockResolvedValueOnce(sampleRows);
    const out = await loadStates();

    const byEci = new Map(out.map((s) => [s.eci_code, s]));
    expect(byEci.get("U05")?.boundary_join_name).toBe("Delhi");
    expect(byEci.get("U01")?.boundary_join_name).toBe("Andaman & Nicobar");
    expect(byEci.get("U08")?.boundary_join_name).toBe("Jammu & Kashmir");
    // Names without an override pass through unchanged.
    expect(byEci.get("S22")?.boundary_join_name).toBe("Tamil Nadu");
    expect(byEci.get("S11")?.boundary_join_name).toBe("Kerala");
  });

  it("caches the result across calls within a session", async () => {
    mockedQuery.mockResolvedValueOnce(sampleRows);
    const first = await loadStates();
    const second = await loadStates();
    expect(first).toBe(second);
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });

  it("__resetForTests clears the cache", async () => {
    mockedQuery.mockResolvedValueOnce(sampleRows);
    await loadStates();
    __resetForTests();
    mockedQuery.mockResolvedValueOnce(sampleRows);
    await loadStates();
    expect(mockedQuery).toHaveBeenCalledTimes(2);
  });

  it("drops rows where entity_id, eci_code, or display_name is null", async () => {
    mockedQuery.mockResolvedValueOnce([
      ...sampleRows,
      { entity_id: null, eci_code: "X99", display_name: "Broken", lgd_code: null, iso_3166_2: null },
      { entity_id: "IN-X99", eci_code: null, display_name: "Broken", lgd_code: null, iso_3166_2: null },
      { entity_id: "IN-X99", eci_code: "X99", display_name: null, lgd_code: null, iso_3166_2: null },
    ]);
    const out = await loadStates();
    expect(out).toHaveLength(5);
  });

  it("preserves nullable LGD / ISO fields verbatim", async () => {
    mockedQuery.mockResolvedValueOnce([
      {
        entity_id: "IN-S99",
        eci_code: "S99",
        display_name: "Mystery",
        lgd_code: null,
        iso_3166_2: null,
      },
    ]);
    const out = await loadStates();
    expect(out[0]).toMatchObject({
      eci_code: "S99",
      lgd_code: null,
      iso_3166_2: null,
    });
  });

  it("propagates DuckDB-WASM errors", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("HTTP 404"));
    await expect(loadStates()).rejects.toThrow(/HTTP 404/);
  });
});

describe("eciFromStateName", () => {
  beforeEach(() => {
    mockedQuery.mockReset();
    mockedRegister.mockReset();
    mockedRegister.mockResolvedValue("noop");
    __resetForTests();
    mockedQuery.mockResolvedValue(sampleRows);
  });

  it("returns the ECI code for an exact DataMeet ST_NM match", async () => {
    expect(await eciFromStateName("Tamil Nadu")).toBe("S22");
    expect(await eciFromStateName("Kerala")).toBe("S11");
  });

  it("resolves the three overridden boundary names", async () => {
    expect(await eciFromStateName("Delhi")).toBe("U05");
    expect(await eciFromStateName("Andaman & Nicobar")).toBe("U01");
    expect(await eciFromStateName("Jammu & Kashmir")).toBe("U08");
  });

  it("returns null for an unknown name", async () => {
    expect(await eciFromStateName("Atlantis")).toBeNull();
  });

  it("does NOT resolve the canonical legal form when an override exists", async () => {
    // "NCT of Delhi" is the display_name; the boundary join uses "Delhi".
    // Callers that pass the legal form by mistake get null back, which is
    // the honest answer ("this string is not a DataMeet ST_NM match").
    expect(await eciFromStateName("NCT of Delhi")).toBeNull();
  });

  it.each([null, undefined, ""])("returns null for %s", async (input) => {
    expect(await eciFromStateName(input as string | null | undefined)).toBeNull();
  });
});
