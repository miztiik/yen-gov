// Unit tests for the Data Explorer per-(event, state) DuckDB views
// (F1.3b CSV cutover + X1a dim_parties flip).
//
// Per CLAUDE.md section 15 + parent plan section 22.4 #4: we mock
// `getConnection` / `registerCsvFile` / `registerTable` /
// `registerCsvAsTable` / `csvColumnsClause` (the explicit carve-out
// from Holy Law #7) and pin:
//   - the 4 CREATE OR REPLACE VIEW statements still emit (parties,
//     constituencies, candidates, party_totals).
//   - each view's SQL references read_csv (NOT read_parquet) against
//     the per-(state, year) CSV paths.
//   - the registration shape: 3 CSV URLs + dim_parties via
//     registerCsvAsTable (X1a); ZERO dim_acs / dim_persons /
//     election_results / elections_candidacies.
//   - identity grammar is preserved (column names ac_eci_no / rank /
//     name / party_short / votes / is_winner / is_nota / vote_share_pct
//     / seats_won) so documented presets keep working.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  getConnection: vi.fn(),
  registerCsvFile: vi.fn(async () => undefined),
  registerCsvAsTable: vi.fn(async () => "dim_parties"),
  registerTable: vi.fn(async () => "noop"),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async () => "columns={MOCKED}"),
}));

import {
  getConnection,
  registerCsvAsTable,
  registerCsvFile,
  registerTable,
} from "../duckdb";
import { csvColumnsClause } from "../canonical/csv-columns";
import { buildExploreViews } from "./duckdb-views";

const mockedGetConnection = vi.mocked(getConnection);
const mockedRegisterCsv = vi.mocked(registerCsvFile);
const mockedRegisterCsvAsTable = vi.mocked(registerCsvAsTable);
const mockedRegister = vi.mocked(registerTable);
const mockedClause = vi.mocked(csvColumnsClause);

const mockQuery = vi.fn<(sql: string) => Promise<unknown>>(async () => undefined);

beforeEach(() => {
  mockedGetConnection.mockReset();
  mockedRegisterCsv.mockReset();
  mockedRegisterCsvAsTable.mockReset();
  mockedRegister.mockReset();
  mockedClause.mockReset();
  mockQuery.mockReset();
  mockedRegisterCsv.mockResolvedValue(undefined);
  mockedRegisterCsvAsTable.mockResolvedValue("dim_parties");
  mockedRegister.mockResolvedValue("noop");
  mockedClause.mockResolvedValue("columns={MOCKED}");
  mockQuery.mockResolvedValue(undefined);
  // The connection only needs `query` for buildExploreViews.
  mockedGetConnection.mockResolvedValue({
    query: mockQuery,
  } as unknown as Awaited<ReturnType<typeof getConnection>>);
});

describe("buildExploreViews", () => {
  it("issues exactly 4 CREATE OR REPLACE VIEW statements (parties / constituencies / candidates / party_totals)", async () => {
    await buildExploreViews("AcGenApr2021", "S22");

    expect(mockQuery).toHaveBeenCalledTimes(4);
    const sqls = mockQuery.mock.calls.map((c) => c[0] as string);
    expect(sqls[0]).toMatch(/CREATE OR REPLACE VIEW parties\b/);
    expect(sqls[1]).toMatch(/CREATE OR REPLACE VIEW constituencies\b/);
    expect(sqls[2]).toMatch(/CREATE OR REPLACE VIEW candidates\b/);
    expect(sqls[3]).toMatch(/CREATE OR REPLACE VIEW party_totals\b/);
  });

  it("registers 3 CSV URLs + dim_parties (CSV-as-table, X1a); drops all 4 F1.3b parquets", async () => {
    await buildExploreViews("AcGenApr2021", "S22");

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

    // X1a CSV-as-table: dim_parties flipped from parquet to CSV-backed view.
    const csvAsTableIds = mockedRegisterCsvAsTable.mock.calls
      .map((c) => c[0])
      .sort();
    expect(csvAsTableIds).toEqual(["elections.dim_parties"]);

    // ZERO parquet `registerTable` calls remain on this surface.
    const parquetTables = mockedRegister.mock.calls.map((c) => c[0]).sort();
    expect(parquetTables).toEqual([]);

    expect(parquetTables).not.toContain("elections.election_results");
    expect(parquetTables).not.toContain("elections.dim_acs");
    expect(parquetTables).not.toContain("elections.dim_persons");
    expect(parquetTables).not.toContain("elections.elections_candidacies");
    // X1a flipped: dim_parties is NO LONGER on the parquet path.
    expect(parquetTables).not.toContain("elections.dim_parties");
  });

  it("preserves the documented preset column shapes per view", async () => {
    await buildExploreViews("AcGenApr2021", "S22");
    const sqls = mockQuery.mock.calls.map((c) => c[0] as string);

    // parties: party_id / eci_code / short_name / full_name / recognition
    expect(sqls[0]).toContain("party_id");
    expect(sqls[0]).toContain("eci_code");
    expect(sqls[0]).toContain("short_name");
    expect(sqls[0]).toContain("full_name");
    expect(sqls[0]).toContain("recognition");

    // constituencies: ac_eci_no / name / votes_polled / total_electors / turnout_pct
    expect(sqls[1]).toContain("AS ac_eci_no");
    expect(sqls[1]).toContain("AS name");
    expect(sqls[1]).toContain("AS votes_polled");
    expect(sqls[1]).toContain("AS total_electors");
    expect(sqls[1]).toContain("AS turnout_pct");

    // candidates: ac_eci_no / rank / name / party_eci_code / party_short / votes / vote_share_pct / is_winner / is_nota
    expect(sqls[2]).toContain("AS ac_eci_no");
    expect(sqls[2]).toContain("AS rank");
    expect(sqls[2]).toContain("AS name");
    expect(sqls[2]).toContain("AS party_eci_code");
    expect(sqls[2]).toContain("AS party_short");
    expect(sqls[2]).toContain("AS votes");
    expect(sqls[2]).toContain("AS vote_share_pct");
    expect(sqls[2]).toContain("AS is_winner");
    expect(sqls[2]).toContain("AS is_nota");

    // party_totals: party_short / seats_won / votes / vote_share_pct
    expect(sqls[3]).toContain("AS party_short");
    expect(sqls[3]).toContain("AS seats_won");
    expect(sqls[3]).toContain("AS votes");
    expect(sqls[3]).toContain("AS vote_share_pct");
  });

  it("every view that needs election data uses read_csv (no read_parquet)", async () => {
    await buildExploreViews("AcGenApr2021", "S22");
    const sqls = mockQuery.mock.calls.map((c) => c[0] as string);
    // parties: reads dim_parties (parquet); OK.
    expect(sqls[0]).not.toContain("read_csv(");
    expect(sqls[0]).not.toContain("read_parquet(");
    expect(sqls[0]).toContain("FROM dim_parties");

    // constituencies + candidates + party_totals: all CSV-only.
    for (const sql of [sqls[1], sqls[2], sqls[3]]) {
      expect(sql).toContain("read_csv(");
      expect(sql).not.toContain("read_parquet(");
      expect(sql).toContain("columns={MOCKED}");
      // Hardened election read options (fix/election-csv-read-hardening):
      // pin the dialect sniffer off + NULL-pad the 20-vs-24-column
      // candidacies schema on every election read.
      expect(sql).toContain("auto_detect=false");
      expect(sql).toContain("null_padding=true");
      expect(sql).toContain(
        "/elections/assembly/state=tamil-nadu/election=2021/",
      );
    }
  });

  it("filters every state-scoped view by the LGD state slug", async () => {
    await buildExploreViews("AcGenApr2021", "S22");
    const sqls = mockQuery.mock.calls.map((c) => c[0] as string);
    // constituencies + candidates + party_totals all filter e.state = 'tamil-nadu'.
    for (const sql of [sqls[1], sqls[2], sqls[3]]) {
      expect(sql).toContain("e.state = 'tamil-nadu'");
    }
  });

  it("synthesises is_winner from candidacies.position = 1 (no separate winner indicator)", async () => {
    await buildExploreViews("AcGenApr2021", "S22");
    const sqls = mockQuery.mock.calls.map((c) => c[0] as string);
    // candidates view: position = 1 maps to is_winner = 1 (skipping NOTA).
    expect(sqls[2]).toMatch(/ec\.position = 1[^,]*UPPER\(ec\.candidate_name\) <> 'NOTA'/);
  });

  it("synthesises is_nota from UPPER(candidate_name) = 'NOTA' (no separate NOTA indicator)", async () => {
    await buildExploreViews("AcGenApr2021", "S22");
    const sqls = mockQuery.mock.calls.map((c) => c[0] as string);
    expect(sqls[2]).toMatch(/UPPER\(ec\.candidate_name\) = 'NOTA'/);
  });
});
