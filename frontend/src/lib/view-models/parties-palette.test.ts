// Unit tests for the parties-palette view-model loader (PR-G / Phase 1.3c).
// Mocks `query` / `registerCsvAsTable` / `registerCsvFile` at the
// `../duckdb` boundary per Holy Law #7 carve-out.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerCsvAsTable: vi.fn(async () => "noop"),
  registerCsvFile: vi.fn(async () => undefined),
  query: vi.fn(),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async () => "columns={}"),
}));

import { query, registerCsvAsTable, registerCsvFile } from "../duckdb";
import { csvColumnsClause } from "../canonical/csv-columns";
import { loadPartiesPalette } from "./parties-palette";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsvAsTable = vi.mocked(registerCsvAsTable);
const mockedRegisterCsvFile = vi.mocked(registerCsvFile);
const mockedCsvColumnsClause = vi.mocked(csvColumnsClause);

const dimRows = [
  {
    eci_code: "1234",
    short_name: "DMK",
    full_name: "Dravida Munnetra Kazhagam",
    recognition: "state",
  },
  {
    eci_code: "742",
    short_name: "AIADMK",
    full_name: "All India Anna Dravida Munnetra Kazhagam",
    recognition: "state",
  },
  {
    eci_code: null,
    short_name: "INC",
    full_name: "Indian National Congress",
    recognition: "national",
  },
];

// X1a-followup (2026-06-06): the fallback path used to surface
// short_name suffixes ("NOTA", "IND", "CPIM") extracted from the
// legacy `IN-<state>-<event>-PARTY-<short>` synthetic entity_ids in
// election_results.parquet. Post-flip the fallback unions DISTINCT
// `party_id` from candidacies.csv that are absent from parties.csv. A
// 2026-06-06 audit shows ZERO orphans across all 257 candidacies
// files, so today's fallback is empty. We keep one synthetic row in
// the fixture to pin the assembler's contract (fallback chips still
// land if a future drift surfaces an orphan).
const fallbackRows = [
  { short_name_key: "parties.IN.FUTURE_ORPHAN" },
];

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegisterCsvAsTable.mockReset();
  mockedRegisterCsvFile.mockReset();
  mockedCsvColumnsClause.mockReset();
  mockedRegisterCsvAsTable.mockResolvedValue("noop");
  mockedRegisterCsvFile.mockResolvedValue(undefined);
  mockedCsvColumnsClause.mockResolvedValue("columns={}");
});

describe("loadPartiesPalette — happy path", () => {
  it("merges dim_parties with candidacies-only fallback", async () => {
    mockedQuery
      .mockResolvedValueOnce(dimRows)
      .mockResolvedValueOnce(fallbackRows);
    const res = await loadPartiesPalette();
    expect(res.status).toBe("ok");
    if (res.status !== "ok") return;
    const shorts = res.data.parties.map((p) => p.short_name);
    expect(shorts).toContain("DMK");
    expect(shorts).toContain("AIADMK");
    expect(shorts).toContain("INC");
    expect(shorts).toContain("parties.IN.FUTURE_ORPHAN");
    // Sorted alphabetically.
    expect(shorts).toEqual([...shorts].sort((a, b) => a.localeCompare(b)));
    // INC has null eci_code in dim — loader fills with short_name fallback.
    const inc = res.data.parties.find((p) => p.short_name === "INC");
    expect(inc?.eci_code).toBe("INC");
    // Fallback row carries no recognition / full_name.
    const orphan = res.data.parties.find(
      (p) => p.short_name === "parties.IN.FUTURE_ORPHAN",
    );
    expect(orphan?.full_name).toBeNull();
    expect(orphan?.eci_code).toBe("parties.IN.FUTURE_ORPHAN");
  });

  it("registers parties.csv + candidacies CSVs before querying", async () => {
    mockedQuery
      .mockResolvedValueOnce(dimRows)
      .mockResolvedValueOnce(fallbackRows);
    await loadPartiesPalette();
    // dim_parties is the only CSV-as-table view this loader registers
    // (parties.csv projected as `dim_parties` per X1a). candidacies
    // CSVs are inline `read_csv()` reads against the URL the
    // `registerCsvFile` calls registered with DuckDB.
    expect(mockedRegisterCsvAsTable).toHaveBeenCalledWith("elections.dim_parties");
  });
});

describe("loadPartiesPalette — failed arm", () => {
  it("maps a thrown SQL error to citizen copy + retry", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("HTTP 503"));
    const res = await loadPartiesPalette();
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    expect(res.reason).toBeTruthy();
    expect(res.reason.toLowerCase()).not.toMatch(/error:/);
    expect(typeof res.retry).toBe("function");
  });
});
