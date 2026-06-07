// Unit tests for the states view-model loader.
// X1a-fu2-A (2026-06-07): the loader flipped from
// `registerTable("taxonomy.entities")` (parquet) to
// `read_csv('datasets/data/entities/geo.csv', columns=...)` via the typed
// CSV seam. Mocks `query` + `registerCsvFile` + `csvColumnsClause` per the
// pattern established by `view-models/ac-crosswalk.ts` (X1a-followup).
// `RawStateRow` shape unchanged - the SQL projection still emits
// {entity_id, eci_code, display_name, lgd_code, iso_3166_2} columns
// even though the underlying read source is geo.csv.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerCsvFile: vi.fn(async () => undefined),
  query: vi.fn(),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async () => "columns={'entity_id': 'VARCHAR'}"),
}));

import { query, registerCsvFile } from "../duckdb";
import { csvColumnsClause } from "../canonical/csv-columns";
import {
  loadStates,
  eciFromStateName,
  lgdCodeToEci,
  __resetForTests,
} from "./states";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerCsvFile);
const mockedClause = vi.mocked(csvColumnsClause);

// Shape returned by the geo.csv SQL projection. The aliases extraction
// happens in DuckDB, so the loader sees the already-projected row.
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
    display_name: "Delhi",
    lgd_code: "7",
    iso_3166_2: "IN-DL",
  },
  {
    entity_id: "IN-U01",
    eci_code: "U01",
    display_name: "Andaman & Nicobar",
    lgd_code: "35",
    iso_3166_2: "IN-AN",
  },
  {
    entity_id: "IN-U08",
    eci_code: "U08",
    display_name: "Jammu & Kashmir",
    lgd_code: "1",
    iso_3166_2: "IN-JK",
  },
];

describe("loadStates (geo.csv via read_csv)", () => {
  beforeEach(() => {
    mockedQuery.mockReset();
    mockedRegister.mockReset();
    mockedClause.mockReset();
    mockedRegister.mockResolvedValue(undefined);
    mockedClause.mockResolvedValue("columns={'entity_id': 'VARCHAR'}");
    __resetForTests();
  });

  it("registers the geo.csv URL and returns one row per state/UT", async () => {
    mockedQuery.mockResolvedValueOnce(sampleRows);
    const out = await loadStates();

    expect(mockedRegister).toHaveBeenCalledTimes(1);
    const registeredUrl = mockedRegister.mock.calls[0][0] as string;
    expect(registeredUrl).toContain("data/entities/geo.csv");
    expect(mockedClause).toHaveBeenCalledWith("datasets/data/entities/geo.csv");
    expect(out).toHaveLength(5);
    expect(out[0]).toMatchObject({
      entity_id: "IN-S22",
      eci_code: "S22",
      display_name: "Tamil Nadu",
      boundary_join_name: "Tamil Nadu",
      boundary_join_key: "33",
      lgd_code: "33",
      iso_3166_2: "IN-TN",
    });
  });

  it("populates boundary_join_key from lgd_code verbatim on every row", async () => {
    mockedQuery.mockResolvedValueOnce(sampleRows);
    const out = await loadStates();
    for (const row of out) {
      expect(row.boundary_join_key).toBe(row.lgd_code);
    }
  });

  it("SQL reads geo.csv filtered to entity_kind='state' (geo.csv folds UT into state)", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    await loadStates();
    const sql = mockedQuery.mock.calls[0][0] as string;

    expect(sql).toMatch(/FROM\s+read_csv\(/);
    expect(sql).toContain("data/entities/geo.csv");
    expect(sql).toMatch(/entity_kind\s*=\s*'state'/);
    // The geo.csv aliases column carries the ECI / LGD / ISO codes;
    // assert each regex extraction is present in the projection.
    expect(sql).toMatch(/regexp_extract\(aliases,\s*'\(\[SU\]\[0-9\]\+\)'/);
    expect(sql).toMatch(/regexp_extract\(aliases,\s*'lgd:\(\[0-9\]\+\)'/);
    expect(sql).toMatch(/regexp_extract\(aliases,\s*'\(IN-\[A-Z\]\{2,3\}\)'/);
    expect(sql).toMatch(/ORDER BY eci_code/);
  });

  it("boundary_join_name equals display_name post-X1a-fu2-A (geo.csv publishes shortform directly)", async () => {
    mockedQuery.mockResolvedValueOnce(sampleRows);
    const out = await loadStates();

    // The pre-flip BOUNDARY_NAME_OVERRIDES table is retired because
    // geo.csv `name` column already carries the citizen-display shortform
    // ("Delhi" not "NCT of Delhi", "Andaman & Nicobar" not "Andaman and
    // Nicobar Islands", "Jammu & Kashmir" not "Jammu and Kashmir (UT)").
    // boundary_join_name therefore equals display_name on every row.
    for (const row of out) {
      expect(row.boundary_join_name).toBe(row.display_name);
    }
  });

  it("drops rows where lgd_code is null (post-D.0 LGD-keyed join requires it)", async () => {
    mockedQuery.mockResolvedValueOnce([
      ...sampleRows,
      { entity_id: "IN-S99", eci_code: "S99", display_name: "Untagged", lgd_code: null, iso_3166_2: null },
    ]);
    const out = await loadStates();
    // The 5 sample rows all have lgd_code; the 6th (null) is dropped.
    expect(out).toHaveLength(5);
    expect(out.every((r) => r.lgd_code !== null && r.lgd_code !== "")).toBe(true);
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
      { entity_id: null, eci_code: "X99", display_name: "Broken", lgd_code: "99", iso_3166_2: null },
      { entity_id: "IN-X99", eci_code: null, display_name: "Broken", lgd_code: "99", iso_3166_2: null },
      { entity_id: "IN-X99", eci_code: "X99", display_name: null, lgd_code: "99", iso_3166_2: null },
    ]);
    const out = await loadStates();
    expect(out).toHaveLength(5);
  });

  it("preserves nullable ISO field verbatim (lgd_code is required for boundary join)", async () => {
    mockedQuery.mockResolvedValueOnce([
      {
        entity_id: "IN-S99",
        eci_code: "S99",
        display_name: "Mystery",
        lgd_code: "99",
        iso_3166_2: null,
      },
    ]);
    const out = await loadStates();
    expect(out[0]).toMatchObject({
      eci_code: "S99",
      lgd_code: "99",
      boundary_join_key: "99",
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
    mockedClause.mockReset();
    mockedRegister.mockResolvedValue(undefined);
    mockedClause.mockResolvedValue("columns={'entity_id': 'VARCHAR'}");
    __resetForTests();
    mockedQuery.mockResolvedValue(sampleRows);
  });

  it("returns the ECI code for an exact display_name match", async () => {
    expect(await eciFromStateName("Tamil Nadu")).toBe("S22");
    expect(await eciFromStateName("Kerala")).toBe("S11");
  });

  it("resolves the shortform UT names that geo.csv publishes directly", async () => {
    // geo.csv `name` column carries the shortform verbatim - so the
    // legal long forms ("NCT of Delhi" / "Andaman and Nicobar Islands"
    // / "Jammu and Kashmir (UT)") that the pre-X1a-fu2-A parquet
    // exposed no longer resolve here. The citizen-facing shortforms
    // remain the canonical name.
    expect(await eciFromStateName("Delhi")).toBe("U05");
    expect(await eciFromStateName("Andaman & Nicobar")).toBe("U01");
    expect(await eciFromStateName("Jammu & Kashmir")).toBe("U08");
  });

  it("returns null for an unknown name", async () => {
    expect(await eciFromStateName("Atlantis")).toBeNull();
  });

  it.each([null, undefined, ""])("returns null for %s", async (input) => {
    expect(await eciFromStateName(input as string | null | undefined)).toBeNull();
  });
});

describe("lgdCodeToEci", () => {
  beforeEach(() => {
    mockedQuery.mockReset();
    mockedRegister.mockReset();
    mockedClause.mockReset();
    mockedRegister.mockResolvedValue(undefined);
    mockedClause.mockResolvedValue("columns={'entity_id': 'VARCHAR'}");
    __resetForTests();
    mockedQuery.mockResolvedValue(sampleRows);
  });

  it("resolves an integer LGD code to the ECI code", async () => {
    expect(await lgdCodeToEci(33)).toBe("S22");
    expect(await lgdCodeToEci(32)).toBe("S11");
  });

  it("resolves a zero-padded VARCHAR LGD code (back-compat with padded callers)", async () => {
    // geo.csv does not zero-pad lgd codes any more (Delhi is "7" not
    // "07"), but `lgdCodeToEci` parseInt-normalises both sides so a
    // zero-padded caller still resolves.
    expect(await lgdCodeToEci("07")).toBe("U05");
    expect(await lgdCodeToEci("35")).toBe("U01");
    expect(await lgdCodeToEci("01")).toBe("U08");
  });

  it("resolves a plain unpadded string LGD code (post-parseInt normalisation)", async () => {
    expect(await lgdCodeToEci("7")).toBe("U05");
    expect(await lgdCodeToEci("33")).toBe("S22");
  });

  it("returns null for null / undefined / empty / non-numeric input", async () => {
    expect(await lgdCodeToEci(null)).toBeNull();
    expect(await lgdCodeToEci(undefined)).toBeNull();
    expect(await lgdCodeToEci("")).toBeNull();
    expect(await lgdCodeToEci("not-a-number")).toBeNull();
  });

  it("returns null for an unknown LGD code", async () => {
    expect(await lgdCodeToEci(999)).toBeNull();
    expect(await lgdCodeToEci("999")).toBeNull();
  });
});

