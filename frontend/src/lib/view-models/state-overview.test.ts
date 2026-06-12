// Unit tests for the StateOverview view-model loader (F1.3a CSV cutover
// + X1a dim_parties/sources flip + X1a-fu2-C dim_party_alliances flip).
//
// Per CLAUDE.md section 15 + parent plan section 22.4 #4: the loader's
// contract IS the SQL boundary. We mock `query` / `registerCsvFile` /
// `registerCsvAsTable` (the explicit carve-out from
// Holy Law #7) + the `csvColumnsClause` helper from `../canonical/csv-columns`
// so the runtime fetch of columns.json never happens. Coverage:
//   - happy path        — assembles StateOverviewViewModel from CSV
//                          rows: party aggregation + state totals +
//                          sources + per-AC winners (DMK/AIADMK fixture).
//   - csv registration  — the 4 CSV URLs (candidacies + summary +
//                          electoral + party_alliances) + dim_parties
//                          (via registerCsvAsTable, X1a) + sources
//                          (via registerCsvAsTable, X1a) are registered;
//                          ZERO registerTable calls survive (X1a-fu2-C
//                          retired dim_party_alliances parquet); NONE
//                          of the F1.3a-decommissioned tables are
//                          (dim_acs / elections_candidacies /
//                          dim_persons / election_results).
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
  query: vi.fn(),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async () => "columns={MOCKED}"),
}));

import { query, registerCsvAsTable, registerCsvFile } from "../duckdb";
import { csvColumnsClause } from "../canonical/csv-columns";
import { loadStateOverview } from "./state-overview";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsv = vi.mocked(registerCsvFile);
const mockedRegisterCsvAsTable = vi.mocked(registerCsvAsTable);
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
    url: "https://eci.gov.in/results/tn-2021.xlsx",
  },
  {
    source_id: "src-tcpd-ae-2021",
    producer: "Trivedi Centre for Political Data",
    title: "Indian Assembly Elections - Constituency-wise candidate results",
    vintage: "2026-06-05",
    url: "https://tcpd.ashoka.edu.in/lok-dhaba/",
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
  mockedClause.mockReset();
  mockedRegisterCsv.mockResolvedValue(undefined);
  mockedRegisterCsvAsTable.mockImplementation(async (id) =>
    id === "elections.dim_parties" ? "dim_parties" : "sources",
  );
  mockedClause.mockResolvedValue("columns={MOCKED}");
});

// E5 (plan section 25.6a): runQueries now issues a SEPARATE
// `acCountSql` between partySql and stateScopeSql to source total_seats
// from COUNT(DISTINCT entity_id) over summary.csv (the canonical
// winners table). Tests inject `acCountRows` after partyRows so the
// SQL-query mock order tracks the runtime order, and the magic value
// equals sum(partyRows[].seats_won) so the invariant assertion passes.
const acCountRows = [{ ac_count: 133 + 66 + 2 }];

describe("loadStateOverview - happy path", () => {
  it("assembles StateOverviewViewModel from CSV rows", async () => {
    mockedQuery
      .mockResolvedValueOnce(partyRows)        // party aggregation
      .mockResolvedValueOnce(acCountRows)      // E5: COUNT(DISTINCT entity_id)
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
    // Publisher pills built via dedupeToPills - 2 rows collapse to 2
    // pills (different producers). ECI + TCPD have different
    // publisherDisplay mappings.
    expect(res.data.pills.map((p) => p.label).sort()).toContainEqual(
      expect.stringContaining("ECI"),
    );
    // No 11-col v2 fields leak into the pill shape; each pill carries
    // exactly the 4-key shape (label, vintage_summary, url, count).
    for (const row of res.data.pills) {
      expect(Object.keys(row).sort()).toEqual([
        "count",
        "label",
        "url",
        "vintage_summary",
      ]);
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
      .mockResolvedValueOnce([{ ac_count: 133 + 66 }]) // E5: matches sum after OTHER dropped
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

  it("registers the 4 CSV URLs + dim_parties (via CSV-as-table) + sources (via CSV-as-table); zero registerTable survives", async () => {
    mockedQuery
      .mockResolvedValueOnce(partyRows)
      .mockResolvedValueOnce(acCountRows)
      .mockResolvedValueOnce(stateScopeRows)
      .mockResolvedValueOnce(sourceIdRows)
      .mockResolvedValueOnce(sourceRows)
      .mockResolvedValueOnce(acWinnerRows);

    await loadStateOverview("AcGenApr2021", "S22");

    // 4 CSV URL registrations (candidacies + summary + electoral +
    // party_alliances). X1a-fu2-C added party_alliances.csv.
    expect(mockedRegisterCsv).toHaveBeenCalledTimes(4);
    const csvUrls = mockedRegisterCsv.mock.calls.map((c) => c[0]);
    const allUrls = csvUrls.join(" | ");
    expect(allUrls).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv",
    );
    expect(allUrls).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/summary.csv",
    );
    expect(allUrls).toContain("/data/entities/electoral.csv");
    expect(allUrls).toContain("/data/entities/party_alliances.csv");

    // X1a CSV-as-table registrations: dim_parties + sources flipped
    // from parquet to CSV-backed views.
    const csvAsTableIds = mockedRegisterCsvAsTable.mock.calls
      .map((c) => c[0])
      .sort();
    expect(csvAsTableIds).toEqual([
      "elections.dim_parties",
      "taxonomy.sources",
    ]);
  });

  it("issues read_csv SQL against candidacies + summary + electoral (no read_parquet)", async () => {
    mockedQuery
      .mockResolvedValueOnce(partyRows)
      .mockResolvedValueOnce(acCountRows)
      .mockResolvedValueOnce(stateScopeRows)
      .mockResolvedValueOnce(sourceIdRows)
      .mockResolvedValueOnce(sourceRows)
      .mockResolvedValueOnce(acWinnerRows);

    await loadStateOverview("AcGenApr2021", "S22");

    const sqls = mockedQuery.mock.calls.map((c) => c[0]);
    // Party pivot SQL: aggregates per-party from candidacies.csv + JOINs
    // alliance via inline `read_csv(party_alliances.csv, columns=...)`
    // (X1a-fu2-C; was `LEFT JOIN dim_party_alliances dpa` on parquet).
    expect(sqls[0]).toContain("read_csv(");
    expect(sqls[0]).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv",
    );
    expect(sqls[0]).toContain("columns={MOCKED}");
    expect(sqls[0]).toContain("/data/entities/party_alliances.csv");
    expect(sqls[0]).not.toContain("read_parquet(");
    expect(sqls[0]).not.toContain("election_results");
    expect(sqls[0]).not.toContain("dim_acs");
    expect(sqls[0]).not.toContain("dim_persons");
    // X1a-fu2-C: the bare `dim_party_alliances` table name no longer
    // appears as a JOIN target; the alliance source is now an inline
    // `read_csv(party_alliances.csv, ...)` aliased to `dpa`.
    expect(sqls[0]).not.toMatch(/JOIN\s+dim_party_alliances/);
    // Phase 1 alliance fix (2026-06-12, plan TODO/20260612-): JOIN keys
    // on the canonical event_id column (was period_label) and additionally
    // filters by state (LGD slug "tamil-nadu" for S22) OR "IN" so per-
    // state cohorts disambiguate (D2 fix) while national-event rows
    // remain visible from every state page. Pin both column references
    // so a regression to the legacy column instantly fails vitest.
    expect(sqls[0]).toContain("dpa.event_id =");
    expect(sqls[0]).not.toContain("dpa.period_label");
    expect(sqls[0]).toContain("dpa.state = 'tamil-nadu'");
    expect(sqls[0]).toContain("dpa.state = 'IN'");

    // E5: distinct-AC count SQL over summary.csv (sources total_seats
    // for the invariant assertion).
    expect(sqls[1]).toContain("COUNT(DISTINCT entity_id)");
    expect(sqls[1]).toContain("read_csv(");
    expect(sqls[1]).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/summary.csv",
    );

    // State scope SQL: SUM over summary.csv.
    expect(sqls[2]).toContain("read_csv(");
    expect(sqls[2]).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/summary.csv",
    );
    expect(sqls[2]).not.toContain("read_parquet(");

    // Source-id discovery SQL: UNION ALL across candidacies + summary.
    expect(sqls[3]).toContain("read_csv(");
    expect(sqls[3]).toContain("UNION ALL");
    expect(sqls[3]).not.toContain("read_parquet(");

    // taxonomy.sources now CSV-backed via `registerCsvAsTable` view named
    // `sources` (X1a flip; the SQL still spells `FROM sources`).
    expect(sqls[4]).toContain("FROM sources");

    // AC winners SQL: read_csv on summary + electoral + candidacies; JOIN
    // dim_parties (CSV-as-table view, no read_parquet literal).
    expect(sqls[5]).toContain("read_csv(");
    expect(sqls[5]).toContain("/data/entities/electoral.csv");
    expect(sqls[5]).toContain("dim_parties dp");
    expect(sqls[5]).not.toContain("dim_acs");
    expect(sqls[5]).not.toContain("dim_persons");
    expect(sqls[5]).not.toContain("election_results");
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
    expect(res.data.pills).toEqual([]);
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
      .mockResolvedValueOnce(acCountRows)
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
