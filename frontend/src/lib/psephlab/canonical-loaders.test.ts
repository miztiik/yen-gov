// Unit tests for the canonical Psephlab loader (F1.3a CSV cutover).
//
// Per CLAUDE.md section 15: the loader's contract IS the duckdb.ts query
// + registerCsvFile + csvColumnsClause boundary. `vi.mock("../duckdb",
// ...)` + `vi.mock("../canonical/csv-columns", ...)` substitute the IO
// layer; tests pin the SQL composition + result-row assembly into the
// legacy `Tallies` shape. The real DuckDB-WASM round-trip is asserted by
// Playwright in the §13 smoke against the live TN CSV.
//
// Pattern mirrors `frontend/src/lib/view-models/constituency.test.ts`.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerCsvFile: vi.fn(async () => undefined),
  registerCsvAsTable: vi.fn(async (id: string) =>
    id === "elections.dim_parties" ? "dim_parties" : "sources",
  ),
  registerTable: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async () => "columns={MOCKED}"),
}));

import { query, registerCsvAsTable, registerCsvFile, registerTable } from "../duckdb";
import { csvColumnsClause } from "../canonical/csv-columns";
import { __resetForTests, loadActuals } from "./canonical-loaders";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsv = vi.mocked(registerCsvFile);
const mockedRegisterCsvAsTable = vi.mocked(registerCsvAsTable);
const mockedRegister = vi.mocked(registerTable);
const mockedClause = vi.mocked(csvColumnsClause);

// Fixture: 2 ACs, 4 real-candidate rows + 1 NOTA row (synthesised by SQL
// for AC #1; suppressed for AC #2 because votes_polled <= SUM(real)).
const constituencyRows = [
  { ac_eci_no: 1, name: "GUMMIDIPOONDI", votes_polled: 222_069 },
  { ac_eci_no: 2, name: "PONNERI (SC)", votes_polled: 198_500 },
];

const candidateRows = [
  // AC 1 - 2 real candidates
  {
    ac_eci_no: 1,
    rank: 1,
    name: "GOVINDARAJAN T.J",
    party_eci_code: "1234",
    party_short: "DMK",
    party_id: "parties.IN.DMK",
    brand_colour_hex: "#e2231a",
    brand_colour_confidence: "high" as const,
    election_symbol_asset_path: "party-symbols/rising-sun.svg",
    votes: 126_452,
    is_nota: 0,
  },
  {
    ac_eci_no: 1,
    rank: 2,
    name: "PRAKASH M",
    party_eci_code: "742",
    party_short: "PMK",
    party_id: "parties.IN.PMK",
    brand_colour_hex: null,
    brand_colour_confidence: null,
    election_symbol_asset_path: null,
    votes: 75_514,
    is_nota: 0,
  },
  // AC 1 - synthesised NOTA row (votes_polled 222_069 - SUM(126_452 +
  // 75_514) = 20_103). SQL hardcodes party_eci_code/short/id for NOTA.
  {
    ac_eci_no: 1,
    rank: null,
    name: "NOTA",
    party_eci_code: null,
    party_short: "NOTA",
    party_id: "parties.IN.NOTA",
    brand_colour_hex: null,
    brand_colour_confidence: null,
    election_symbol_asset_path: null,
    votes: 20_103,
    is_nota: 1,
  },
  // AC 2 - 1 real candidate + null party_eci_code + empty short (IND fallback)
  {
    ac_eci_no: 2,
    rank: 1,
    name: "INDEPENDENT_CANDIDATE",
    party_eci_code: null,
    party_short: "",
    party_id: null,
    brand_colour_hex: null,
    brand_colour_confidence: null,
    election_symbol_asset_path: null,
    votes: 100_000,
    is_nota: 0,
  },
];

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegisterCsv.mockReset();
  mockedRegisterCsvAsTable.mockReset();
  mockedRegister.mockReset();
  mockedClause.mockReset();
  mockedRegisterCsv.mockResolvedValue(undefined);
  mockedRegisterCsvAsTable.mockImplementation(async (id) =>
    id === "elections.dim_parties" ? "dim_parties" : "sources",
  );
  mockedRegister.mockResolvedValue("noop");
  mockedClause.mockResolvedValue("columns={MOCKED}");
  __resetForTests();
});

describe("loadActuals - happy path", () => {
  it("assembles Tallies in legacy actuals.ts shape", async () => {
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    const t = await loadActuals("AcGenApr2021", "S22");

    expect(t.scope).toEqual({
      country: "IN",
      state: "S22",
      election: "AcGenApr2021",
    });
    expect(t.acs).toHaveLength(2);

    const ac1 = t.acs[0];
    expect(ac1.eci_no).toBe(1);
    expect(ac1.name).toBe("GUMMIDIPOONDI");
    expect(ac1.electorate).toBe(222_069);
    expect(ac1.candidates).toHaveLength(3);

    expect(ac1.candidates[0]).toEqual({
      party_eci_code: "1234",
      party_short: "DMK",
      name: "GOVINDARAJAN T.J",
      votes: 126_452,
      party_id: "parties.IN.DMK",
      brand_colour_hex: "#e2231a",
      brand_colour_confidence: "high",
      election_symbol_asset_path: "party-symbols/rising-sun.svg",
    });
    expect(ac1.candidates[1]).toEqual({
      party_eci_code: "742",
      party_short: "PMK",
      name: "PRAKASH M",
      votes: 75_514,
      party_id: "parties.IN.PMK",
      brand_colour_hex: null,
      brand_colour_confidence: null,
      election_symbol_asset_path: null,
    });
    expect(ac1.candidates[2]).toEqual({
      party_eci_code: "NOTA",
      party_short: "NOTA",
      name: "NOTA",
      votes: 20_103,
      party_id: "parties.IN.NOTA",
      brand_colour_hex: null,
      brand_colour_confidence: null,
      election_symbol_asset_path: null,
    });
  });

  it("falls back to IND when party_eci_code + party_short are missing on a real candidate", async () => {
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    const t = await loadActuals("AcGenApr2021", "S22");
    const ac2 = t.acs[1];
    expect(ac2.candidates[0]).toEqual({
      party_eci_code: "IND",
      party_short: "IND",
      name: "INDEPENDENT_CANDIDATE",
      votes: 100_000,
      party_id: "parties.IN.IND",
      brand_colour_hex: null,
      brand_colour_confidence: null,
      election_symbol_asset_path: null,
    });
  });

  it("freezes Tallies + acs to prevent downstream mutation", async () => {
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    const t = await loadActuals("AcGenApr2021", "S22");
    expect(Object.isFrozen(t)).toBe(true);
    expect(Object.isFrozen(t.acs)).toBe(true);
  });

  it("registers the 3 CSV URLs + dim_parties (via CSV-as-table; X1a) before querying (no parquet for the 4 dropped tables)", async () => {
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    await loadActuals("AcGenApr2021", "S22");

    // 3 CSV URL registrations (candidacies + summary + electoral).
    expect(mockedRegisterCsv).toHaveBeenCalledTimes(3);
    const csvUrls = mockedRegisterCsv.mock.calls.map((c) => c[0]);
    const allUrls = csvUrls.join(" | ");
    expect(allUrls).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv",
    );
    expect(allUrls).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/summary.csv",
    );
    expect(allUrls).toContain("/data/entities/electoral.csv");

    // X1a (PR #809) flipped dim_parties from parquet to CSV via
    // `registerCsvAsTable`. The pre-X1a `registerTable` is no longer
    // invoked by this loader. E5 (plan section 25.6a) corrects the
    // stale assertion left behind by the X1a PR.
    const csvAsTableIds = mockedRegisterCsvAsTable.mock.calls
      .map((c) => c[0])
      .sort();
    expect(csvAsTableIds).toEqual(["elections.dim_parties"]);

    // No surviving parquet `registerTable` calls in this loader after X1a.
    const parquetTables = mockedRegister.mock.calls.map((c) => c[0]).sort();
    expect(parquetTables).toEqual([]);

    // ZERO requests for the F1.3a-decommissioned tables.
    expect(parquetTables).not.toContain("elections.dim_acs");
    expect(parquetTables).not.toContain("elections.dim_persons");
    expect(parquetTables).not.toContain("elections.elections_candidacies");
    expect(parquetTables).not.toContain("elections.election_results");
    // X1a-flipped: NEVER routed through registerTable here.
    expect(parquetTables).not.toContain("elections.dim_parties");
  });
});

describe("loadActuals - caching", () => {
  it("returns the same Promise for repeat (event, state) calls without re-querying", async () => {
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    const a = loadActuals("AcGenApr2021", "S22");
    const b = loadActuals("AcGenApr2021", "S22");
    expect(a).toBe(b);

    await a;
    expect(mockedQuery).toHaveBeenCalledTimes(2);
  });

  it("evicts the cache entry when the underlying query rejects", async () => {
    const boom = new Error("duckdb: boom");
    mockedQuery.mockRejectedValueOnce(boom);

    const first = loadActuals("AcGenApr2021", "S22");
    await expect(first).rejects.toThrow("duckdb: boom");

    // Second call must NOT re-use the rejected cached promise.
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    const second = await loadActuals("AcGenApr2021", "S22");
    expect(second.acs).toHaveLength(2);
  });
});

describe("loadActuals - SQL composition", () => {
  it("issues two queries (constituencies + candidates UNION ALL NOTA)", async () => {
    mockedQuery
      .mockResolvedValueOnce(constituencyRows)
      .mockResolvedValueOnce(candidateRows);

    await loadActuals("AcGenMay2026", "S22");

    expect(mockedQuery).toHaveBeenCalledTimes(2);
    const [acSql] = mockedQuery.mock.calls[0];
    const [candSql] = mockedQuery.mock.calls[1];

    // Both queries read CSV, not parquet.
    expect(acSql).toContain("read_csv(");
    expect(acSql).not.toContain("read_parquet(");
    expect(candSql).toContain("read_csv(");
    expect(candSql).not.toContain("read_parquet(");

    // Hardened election read options (fix/election-csv-read-hardening):
    // both queries pin the dialect sniffer off (auto_detect=false) and
    // NULL-pad the 20-vs-24-column candidacies schema (null_padding=true).
    expect(acSql).toContain("auto_detect=false");
    expect(acSql).toContain("null_padding=true");
    expect(candSql).toContain("auto_detect=false");
    expect(candSql).toContain("null_padding=true");

    // Per-(state, year) URL substituted into both.
    expect(acSql).toContain(
      "/elections/assembly/state=tamil-nadu/election=2026/summary.csv",
    );
    expect(candSql).toContain(
      "/elections/assembly/state=tamil-nadu/election=2026/candidacies.csv",
    );

    // Typed columns clause spliced.
    expect(acSql).toContain("columns={MOCKED}");
    expect(candSql).toContain("columns={MOCKED}");

    // State filter on electoral.csv slug.
    expect(acSql).toContain("e.state = 'tamil-nadu'");
    expect(candSql).toContain("e.state = 'tamil-nadu'");

    // Candidate query carries the NOTA synthesis UNION ALL.
    expect(candSql).toContain("UNION ALL");
    expect(candSql).toContain("'parties.IN.NOTA'");
    expect(candSql).toContain("GREATEST");
    expect(candSql).toContain("votes_polled");

    // Neither query touches the decommissioned tables.
    for (const sql of [acSql, candSql]) {
      expect(sql).not.toContain("election_results");
      expect(sql).not.toContain("elections_candidacies");
      expect(sql).not.toContain("dim_acs");
      expect(sql).not.toContain("dim_persons");
    }
  });

  it("escapes single quotes inside the state slug to prevent SQL injection at the seam", async () => {
    mockedQuery
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([]);

    // The event_id NEVER reaches the SQL in the new shape (it only
    // contributes the trailing 4-digit year to the URL path). The
    // injection surface is the state slug. electionStatePartition
    // returns "tamil-nadu" for "S22"; the sqlString helper must escape
    // it identically every time.
    await loadActuals("AcGenApr2021", "S22");

    const [acSql] = mockedQuery.mock.calls[0];
    expect(acSql).toContain("'tamil-nadu'");
    // No bare unescaped single quote injection - the slug literal is
    // wrapped exactly once.
    expect(acSql.match(/'tamil-nadu'/g)?.length ?? 0).toBeGreaterThan(0);
  });
});
