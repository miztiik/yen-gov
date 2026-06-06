// Unit tests for the StateOverview view-model loader (F1.3a CSV cutover
// + X1a dim_parties/sources flip).
//
// Per CLAUDE.md section 15 + parent plan section 22.4 #4: the loader's
// contract IS the SQL boundary. We mock `query` / `registerCsvFile` /
// `registerTable` / `registerCsvAsTable` (the explicit carve-out from
// Holy Law #7) + the `csvColumnsClause` helper from `../canonical/csv-columns`
// so the runtime fetch of columns.json never happens. Coverage:
//   - happy path        — assembles StateOverviewViewModel from CSV
//                          rows: party aggregation + state totals +
//                          sources + per-AC winners (DMK/AIADMK fixture).
//   - csv registration  — the 3 CSV URLs + dim_parties (via
//                          registerCsvAsTable, X1a) + dim_party_alliances
//                          (still parquet, no CSV equivalent yet) +
//                          sources (via registerCsvAsTable, X1a) are
//                          registered; NONE of the F1.3a-decommissioned
//                          tables are (dim_acs / elections_candidacies
//                          / dim_persons / election_results).
//   - SQL composition   — every read_csv call uses the typed columns
//                          clause; ZERO read_parquet on the legacy
//                          tables; per-(state, year) URL substituted.
//   - partial / failed  — zero-party-rows partial + injected-throw
//                          failed arm with retry callable.

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
import { loadStateOverview } from "./state-overview";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsv = vi.mocked(registerCsvFile);
const mockedRegisterCsvAsTable = vi.mocked(registerCsvAsTable);
const mockedRegister = vi.mocked(registerTable);
const mockedClause = vi.mocked(csvColumnsClause);

const partyRows = [
  {
    short_name_key: "DMK",
    short_name: "DMK",
    full_name: "Dravida Munnetra Kazhagam",
    eci_code: "1234",
    recognition: "state",
    alliance: "SPA",
    party_id: "parties.IN.DMK",
    brand_colour_hex: "#e2231a",
    brand_colour_confidence: "high",
    seats_contested: 173,
    seats_won: 133,
    votes: 22_350_000,
    vote_share_pct: 37.7,
  },
  {
    short_name_key: "AIADMK",
    short_name: "AIADMK",
    full_name: "All India Anna Dravida Munnetra Kazhagam",
    eci_code: "742",
    recognition: "state",
    alliance: "AIADMK+",
    party_id: "parties.IN.AIADMK",
    brand_colour_hex: null,
    brand_colour_confidence: null,
    seats_contested: 191,
    seats_won: 66,
    votes: 19_300_000,
    vote_share_pct: 33.3,
  },
  {
    // Long-tail bucket: party_id NULL in candidacies.csv -> 'OTHER'.
    // Non-zero seats_won so the assembleResult filter keeps it.
    short_name_key: "OTHER",
    short_name: null,
    full_name: null,
    eci_code: null,
    recognition: null,
    alliance: null,
    party_id: null,
    brand_colour_hex: null,
    brand_colour_confidence: null,
    seats_contested: 100,
    seats_won: 2,
    votes: 1_100_000,
    vote_share_pct: 1.9,
  },
];

const stateScopeRows = [
  {
    electors: 62_700_000,
    votes_polled: 45_900_000,
    turnout_pct: 73.21,
  },
];

const sourceIdRows = [
  { source_id: "src-tcpd-ae-2021" },
  { source_id: "src-eci000000a1" },
];

const sourceRows = [
  {
    source_id: "src-eci000000a1",
    producer: "Election Commission of India",
    title: "Statistical Report Section 10 (Detailed Results) - TN",
    vintage: "AcGenApr2021",
    license: "OGL-IN-1.0",
    confidence_tier: "gold",
    is_issuing_authority: true,
    verification_method: "live-fetch",
    url_main: "https://eci.gov.in/results/tn-2021.xlsx",
    citation_full: null,
    notes: null,
  },
  {
    source_id: "src-tcpd-ae-2021",
    producer: "Trivedi Centre for Political Data",
    title: "Indian Assembly Elections - Constituency-wise candidate results",
    vintage: "2026-06-05",
    license: "OGL-IN-1.0",
    confidence_tier: "silver",
    is_issuing_authority: false,
    verification_method: "archived-snapshot",
    url_main: "https://tcpd.ashoka.edu.in/lok-dhaba/",
    citation_full: null,
    notes: null,
  },
];

const acWinnerRows = [
  {
    ac_eci_no: 1,
    ac_name: "GUMMIDIPOONDI",
    party_id: "parties.IN.DMK",
    party_eci_code: "1234",
    party_short: "DMK",
    brand_colour_hex: "#e63329",
    brand_colour_confidence: "high",
    symbol_asset_path: "party-symbols/rising-sun.svg",
    margin_pct: 12.5,
    turnout_pct: 78.84,
    winner_age: 60,
    winner_candidate_name: "GOVINDARAJAN T.J",
  },
  {
    ac_eci_no: 2,
    ac_name: "PONNERI",
    party_id: "parties.IN.AIADMK",
    party_eci_code: null,
    party_short: "AIADMK",
    brand_colour_hex: null,
    brand_colour_confidence: null,
    symbol_asset_path: null,
    margin_pct: 3.4,
    turnout_pct: 74.2,
    winner_age: null,
    winner_candidate_name: null,
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
});

describe("loadStateOverview - happy path", () => {
  it("assembles StateOverviewViewModel from CSV rows", async () => {
    mockedQuery
      .mockResolvedValueOnce(partyRows)        // party aggregation
      .mockResolvedValueOnce(stateScopeRows)   // state totals
      .mockResolvedValueOnce(sourceIdRows)     // source id discovery
      .mockResolvedValueOnce(sourceRows)       // taxonomy.sources rows
      .mockResolvedValueOnce(acWinnerRows);    // per-AC winners

    const res = await loadStateOverview("AcGenApr2021", "S22");
    expect(res.status).toBe("ok");
    if (res.status !== "ok") return;

    expect(res.data.election).toBe("AcGenApr2021");
    expect(res.data.state).toBe("S22");
    expect(res.data.party_totals).toHaveLength(3);
    expect(res.data.party_totals[0]).toMatchObject({
      party_short: "DMK",
      party_full: "Dravida Munnetra Kazhagam",
      party_eci_code: "1234",
      recognition: "state",
      alliance: "SPA",
      party_id: "parties.IN.DMK",
      brand_colour_hex: "#e2231a",
      brand_colour_confidence: "high",
      seats_contested: 173,
      seats_won: 133,
      votes: 22_350_000,
      vote_share_pct: 37.7,
    });
    // 'OTHER' bucket survives because seats_won > 0; falls back to the
    // synthetic short_name_key for display.
    expect(res.data.party_totals[2]).toMatchObject({
      party_short: "OTHER",
      party_full: null,
      party_eci_code: null,
      party_id: null,
      recognition: null,
      alliance: null,
      seats_won: 2,
    });
    expect(res.data.total_seats).toBe(133 + 66 + 2);
    expect(res.data.totals).toEqual({
      electors: 62_700_000,
      votes_polled: 45_900_000,
      turnout_pct: 73.21,
    });
    expect(res.data.sources).toEqual([
      {
        url: "https://eci.gov.in/results/tn-2021.xlsx",
        fetched_at: "",
      },
      {
        url: "https://tcpd.ashoka.edu.in/lok-dhaba/",
        fetched_at: "",
      },
    ]);
    // v2 ledger projection: 2 rows from sources, sorted by trust
    // (live-fetch rank 0 before archived-snapshot rank 1).
    expect(res.data.sources_v2.map((s) => s.source_id)).toEqual([
      "src-eci000000a1",
      "src-tcpd-ae-2021",
    ]);
    // R-24 enforcement - no fetch-telemetry field leaks into v2 row.
    for (const row of res.data.sources_v2) {
      for (const forbidden of [
        "url",
        "fetched_at",
        "first_fetched_at",
        "last_seen_at",
        "date_accessed",
        "content_hash",
        "url_download",
      ]) {
        expect(row).not.toHaveProperty(forbidden);
      }
    }
    expect(res.data.ac_winners).toHaveLength(2);
    expect(res.data.ac_winners[0]).toMatchObject({
      ac_eci_no: 1,
      ac_name: "GUMMIDIPOONDI",
      party_id: "parties.IN.DMK",
      party_eci_code: "1234",
      party_short: "DMK",
      margin_pct: 12.5,
      turnout_pct: 78.84,
      winner_age: 60,
      winner_candidate_name: "GOVINDARAJAN T.J",
      symbol_asset_path: "party-symbols/rising-sun.svg",
    });
  });

  it("drops the OTHER long-tail bucket when seats_won is zero", async () => {
    const rowsNoOtherWins = [
      ...partyRows.slice(0, 2),
      { ...partyRows[2], seats_won: 0 },
    ];
    mockedQuery
      .mockResolvedValueOnce(rowsNoOtherWins)
      .mockResolvedValueOnce(stateScopeRows)
      .mockResolvedValueOnce(sourceIdRows)
      .mockResolvedValueOnce(sourceRows)
      .mockResolvedValueOnce(acWinnerRows);
    const res = await loadStateOverview("AcGenApr2021", "S22");
    if (res.status !== "ok") throw new Error("expected ok");
    expect(res.data.party_totals).toHaveLength(2);
    expect(res.data.party_totals.map((p) => p.party_short)).toEqual([
      "DMK",
      "AIADMK",
    ]);
  });

  it("registers the 3 CSV URLs + dim_parties (via CSV-as-table) + dim_party_alliances (parquet) + sources (via CSV-as-table)", async () => {
    mockedQuery
      .mockResolvedValueOnce(partyRows)
      .mockResolvedValueOnce(stateScopeRows)
      .mockResolvedValueOnce(sourceIdRows)
      .mockResolvedValueOnce(sourceRows)
      .mockResolvedValueOnce(acWinnerRows);

    await loadStateOverview("AcGenApr2021", "S22");

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

    // X1a CSV-as-table registrations: dim_parties + sources flipped
    // from parquet to CSV-backed views.
    const csvAsTableIds = mockedRegisterCsvAsTable.mock.calls
      .map((c) => c[0])
      .sort();
    expect(csvAsTableIds).toEqual([
      "elections.dim_parties",
      "taxonomy.sources",
    ]);

    // Parquet tables that stay registered (alliance CSV not emitted yet):
    const parquetTables = mockedRegister.mock.calls.map((c) => c[0]).sort();
    expect(parquetTables).toEqual([
      "elections.dim_party_alliances",
    ]);

    // ZERO requests for the F1.3a-decommissioned tables.
    expect(parquetTables).not.toContain("elections.dim_acs");
    expect(parquetTables).not.toContain("elections.dim_persons");
    expect(parquetTables).not.toContain("elections.elections_candidacies");
    expect(parquetTables).not.toContain("elections.election_results");
    // X1a flipped: dim_parties + sources are NO LONGER on the parquet path.
    expect(parquetTables).not.toContain("elections.dim_parties");
    expect(parquetTables).not.toContain("taxonomy.sources");
  });

  it("issues read_csv SQL against candidacies + summary + electoral (no read_parquet)", async () => {
    mockedQuery
      .mockResolvedValueOnce(partyRows)
      .mockResolvedValueOnce(stateScopeRows)
      .mockResolvedValueOnce(sourceIdRows)
      .mockResolvedValueOnce(sourceRows)
      .mockResolvedValueOnce(acWinnerRows);

    await loadStateOverview("AcGenApr2021", "S22");

    const sqls = mockedQuery.mock.calls.map((c) => c[0]);
    // Party pivot SQL: aggregates per-party from candidacies.csv.
    expect(sqls[0]).toContain("read_csv(");
    expect(sqls[0]).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv",
    );
    expect(sqls[0]).toContain("columns={MOCKED}");
    expect(sqls[0]).not.toContain("read_parquet(");
    expect(sqls[0]).not.toContain("election_results");
    expect(sqls[0]).not.toContain("dim_acs");
    expect(sqls[0]).not.toContain("dim_persons");

    // State scope SQL: SUM over summary.csv.
    expect(sqls[1]).toContain("read_csv(");
    expect(sqls[1]).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/summary.csv",
    );
    expect(sqls[1]).not.toContain("read_parquet(");

    // Source-id discovery SQL: UNION ALL across candidacies + summary.
    expect(sqls[2]).toContain("read_csv(");
    expect(sqls[2]).toContain("UNION ALL");
    expect(sqls[2]).not.toContain("read_parquet(");

    // taxonomy.sources still parquet (deferred to X1a).
    expect(sqls[3]).toContain("FROM sources");

    // AC winners SQL: read_csv on summary + electoral + candidacies; JOIN
    // dim_parties (parquet table, no read_parquet literal).
    expect(sqls[4]).toContain("read_csv(");
    expect(sqls[4]).toContain("/data/entities/electoral.csv");
    expect(sqls[4]).toContain("dim_parties dp");
    expect(sqls[4]).not.toContain("dim_acs");
    expect(sqls[4]).not.toContain("dim_persons");
    expect(sqls[4]).not.toContain("election_results");
  });
});

describe("loadStateOverview - partial / not_published", () => {
  it("returns partial when zero party rows for (state, event)", async () => {
    mockedQuery.mockResolvedValueOnce([]); // party pivot returns nothing
    const res = await loadStateOverview("AcGenMay2099", "S22");
    expect(res.status).toBe("partial");
    if (res.status !== "partial") return;
    expect(res.reason).toBe("not_published");
    expect(res.data.party_totals).toEqual([]);
    expect(res.data.sources).toEqual([]);
    expect(res.data.sources_v2).toEqual([]);
    expect(res.data.totals).toBeNull();
    expect(res.data.total_seats).toBe(0);
  });

  it("skips state-scope / sources / ac_winners queries when party rows empty", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    await loadStateOverview("AcGenMay2099", "S22");
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });
});

describe("loadStateOverview - failed arm", () => {
  it("maps a thrown SQL error to citizen-readable copy + retry callable", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("HTTP 503 service unavailable"));
    const res = await loadStateOverview("AcGenApr2021", "S22");
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    expect(res.reason).toBeTruthy();
    expect(res.reason.toLowerCase()).not.toMatch(/error:/);
    expect(res.reason.toLowerCase()).not.toMatch(/\.js:/);
    expect(typeof res.retry).toBe("function");
  });

  it("retry callable re-invokes the loader (and can now succeed)", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("transient wasm boot fail"));
    const first = await loadStateOverview("AcGenApr2021", "S22");
    expect(first.status).toBe("failed");

    mockedQuery
      .mockResolvedValueOnce(partyRows)
      .mockResolvedValueOnce(stateScopeRows)
      .mockResolvedValueOnce(sourceIdRows)
      .mockResolvedValueOnce(sourceRows)
      .mockResolvedValueOnce(acWinnerRows);
    if (first.status !== "failed" || !first.retry) throw new Error("no retry");
    const retry = first.retry as () => ReturnType<typeof loadStateOverview>;
    const second = await retry();
    expect(second.status).toBe("ok");
  });

  it("maps a CSV-file registration failure to a citizen-readable arm", async () => {
    mockedRegisterCsv.mockRejectedValueOnce(new Error("ENOENT: no such file"));
    const res = await loadStateOverview("AcGenApr2021", "S22");
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    expect(res.reason).toBeTruthy();
  });
});
