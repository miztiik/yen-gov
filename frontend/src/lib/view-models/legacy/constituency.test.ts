// Unit tests for the Constituency view-model loader (F1.3a CSV cutover
// + X1a dim_parties/sources flip).
//
// Per CLAUDE.md section 15 + parent plan section 22.4 #4: the loader's
// contract IS the SQL boundary. We mock `query` / `registerCsvFile` /
// `registerTable` / `registerCsvAsTable` (the explicit carve-out from
// Holy Law #7) and pin:
//   - happy path        - given JOINed rows + a summary row, the loader
//                         assembles the ConstituencyResult shape
//                         Constituency.svelte already renders.
//   - NOTA + tail       - NOTA splits out of `candidates` into `nota`;
//                         contestants past TOP_N collapse into `others`.
//   - not_published     - zero candidacy rows for (state, eci, year) -
//                         partial / not_published with skeleton.
//   - failed            - injected throw -> failed arm + retry callable.
//
// We mock `csvColumnsClause` from `../../canonical/csv-columns` so the
// runtime fetch of columns.json never happens. The clause shape itself
// is pinned by `csv-columns.test.ts`; here we only care that the
// loader threaded a clause string into the read_csv call.
//
// PR-W5a (2026-06-10) moved both the loader and this test to
// `view-models/legacy/`; the mock boundary became `../../duckdb` (two
// levels up) but the assertions are unchanged.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../duckdb", () => ({
  registerCsvFile: vi.fn(async () => undefined),
  registerCsvAsTable: vi.fn(async (id: string) =>
    id === "elections.dim_parties" ? "dim_parties" : "sources",
  ),
  registerTable: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

vi.mock("../../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async () => "columns={MOCKED}"),
}));

import { query, registerCsvAsTable, registerCsvFile, registerTable } from "../../duckdb";
import { csvColumnsClause } from "../../canonical/csv-columns";
import { loadConstituencyResult } from "./constituency";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsv = vi.mocked(registerCsvFile);
const mockedRegisterCsvAsTable = vi.mocked(registerCsvAsTable);
const mockedRegister = vi.mocked(registerTable);
const mockedClause = vi.mocked(csvColumnsClause);

// Two candidates + one NOTA row. Matches the per-(state, year)
// candidacies.csv shape: NOTA appears as a normal candidate row with
// `candidate_name='NOTA'` and party_id NULL.
const candidateRows = [
  {
    candidate_name: "GOVINDARAJAN T.J",
    party_id_raw: "parties.IN.DMK",
    votes: 126_452,
    vote_share_pct: 56.94,
    position: 1,
    result: "won",
    sex: "M",
    age: 60,
    education: "10th Pass",
    profession: null,
    candidate_type: "challenger",
    source_id: "src-tcpd-ae-2021",
    ac_id: "IN-AC-2008-tamil-nadu-4062",
    constituency_name: "GUMMIDIPOONDI",
    dp_short_name: "DMK",
    party_full: "Dravida Munnetra Kazhagam",
    party_eci_code: "1234",
    brand_colour_hex: "#ff0000",
    brand_colour_confidence: "high",
    election_symbol_asset_path: "party-symbols/rising-sun.svg",
  },
  {
    candidate_name: "PRAKASH M",
    party_id_raw: "parties.IN.PMK",
    votes: 75_514,
    vote_share_pct: 34.0,
    position: 2,
    result: "lost",
    sex: "M",
    age: 50,
    education: "10th Pass",
    profession: "Qualified Professional",
    candidate_type: "challenger",
    source_id: "src-tcpd-ae-2021",
    ac_id: "IN-AC-2008-tamil-nadu-4062",
    constituency_name: "GUMMIDIPOONDI",
    dp_short_name: "PMK",
    party_full: "Pattali Makkal Katchi",
    party_eci_code: "742",
    brand_colour_hex: null,
    brand_colour_confidence: null,
    election_symbol_asset_path: null,
  },
  {
    candidate_name: "NOTA",
    party_id_raw: null,
    votes: 1_783,
    vote_share_pct: 0.8,
    position: 9,
    result: "lost",
    sex: null,
    age: null,
    education: null,
    profession: null,
    candidate_type: null,
    source_id: "src-tcpd-ae-2021",
    ac_id: "IN-AC-2008-tamil-nadu-4062",
    constituency_name: "GUMMIDIPOONDI",
    dp_short_name: null,
    party_full: null,
    party_eci_code: null,
    brand_colour_hex: null,
    brand_colour_confidence: null,
    election_symbol_asset_path: null,
  },
];

const summaryRows = [
  {
    electors: 281_688,
    votes_polled: 222_069,
    turnout_pct: 78.84,
    winner_candidate: "GOVINDARAJAN T.J",
    winner_party_id: "parties.IN.DMK",
    winner_votes: 126_452,
    margin_votes: 50_938,
    margin_pct: 22.94,
    source_id: "src-tcpd-ae-2021",
  },
];

const sourceRows = [{ url_main: "https://eci.gov.in/example.xlsx" }];

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

describe("loadConstituencyResult - happy path", () => {
  it("assembles ConstituencyResult from candidacies + summary + sources rows", async () => {
    mockedQuery
      .mockResolvedValueOnce(candidateRows)
      .mockResolvedValueOnce(summaryRows)
      .mockResolvedValueOnce(sourceRows);

    const res = await loadConstituencyResult("AcGenApr2021", "S22", 1);
    expect(res.status).toBe("ok");
    if (res.status !== "ok") return;

    expect(res.data.election).toBe("AcGenApr2021");
    expect(res.data.state).toBe("S22");
    expect(res.data.eci_no).toBe(1);
    expect(res.data.constituency_name).toBe("GUMMIDIPOONDI");

    // 2 real candidates (NOTA split out).
    expect(res.data.candidates).toHaveLength(2);
    expect(res.data.candidates[0]).toMatchObject({
      rank: 1,
      name: "GOVINDARAJAN T.J",
      party_short: "DMK",
      party_eci_code: "1234",
      votes: 126_452,
      vote_share_pct: 56.94,
      is_winner: true,
    });
    expect(res.data.candidates[1].is_winner).toBe(false);

    expect(res.data.totals.electors).toBe(281_688);
    expect(res.data.totals.votes_polled).toBe(222_069);
    expect(res.data.totals.turnout_pct).toBe(78.84);

    expect(res.data.nota.votes).toBe(1_783);
    expect(res.data.nota.vote_share_pct).toBe(0.8);

    expect(res.data.winner).toMatchObject({
      name: "GOVINDARAJAN T.J",
      party_short: "DMK",
      margin_votes: 50_938,
      margin_pct: 22.94,
      party_id: "parties.IN.DMK",
      brand_colour_hex: "#ff0000",
      brand_colour_confidence: "high",
      election_symbol_asset_path: "party-symbols/rising-sun.svg",
    });

    expect(res.data.sources).toEqual([
      { url: "https://eci.gov.in/example.xlsx", fetched_at: "" },
    ]);

    // Only 2 real contestants - no "others" tail past TOP_N=7.
    expect(res.data.candidates_total).toBe(2);
    expect(res.data.others).toBeNull();
  });

  it("projects bio columns inline from candidacies (no dim_persons join)", async () => {
    mockedQuery
      .mockResolvedValueOnce(candidateRows)
      .mockResolvedValueOnce(summaryRows)
      .mockResolvedValueOnce(sourceRows);

    const res = await loadConstituencyResult("AcGenApr2021", "S22", 1);
    if (res.status !== "ok") throw new Error("expected ok");

    expect(res.data.candidates[0].bio).toMatchObject({
      sex: "M",
      age: 60,
      education: "10th Pass",
      profession: null,
      party_type: "challenger",
    });
    expect(res.data.candidates[1].bio).toMatchObject({
      sex: "M",
      age: 50,
      education: "10th Pass",
      profession: "Qualified Professional",
      party_type: "challenger",
    });
  });

  it("collapses tail beyond TOP_N=7 into the others bucket", async () => {
    // Synthesise 10 real candidates so 3 collapse into the tail.
    const many = Array.from({ length: 10 }, (_, i) => ({
      ...candidateRows[0],
      candidate_name: `CANDIDATE ${i + 1}`,
      party_id_raw: i === 0 ? "parties.IN.DMK" : "parties.IN.UNK",
      votes: 100_000 - i * 1_000,
      vote_share_pct: 50 - i * 4,
      position: i + 1,
      dp_short_name: i === 0 ? "DMK" : null,
      party_eci_code: i === 0 ? "1234" : null,
    }));
    mockedQuery
      .mockResolvedValueOnce(many)
      .mockResolvedValueOnce(summaryRows)
      .mockResolvedValueOnce(sourceRows);

    const res = await loadConstituencyResult("AcGenApr2021", "S22", 1);
    if (res.status !== "ok") throw new Error("expected ok");

    expect(res.data.top_n_cutoff).toBe(7);
    expect(res.data.candidates).toHaveLength(7);
    expect(res.data.candidates_total).toBe(10);
    expect(res.data.others?.candidate_count).toBe(3);
    // Tail = candidates 8 + 9 + 10 (positions 8, 9, 10).
    // votes = 93_000 + 92_000 + 91_000 = 276_000.
    expect(res.data.others?.votes).toBe(276_000);
  });

  it("registers the 3 CSV URLs + dim_parties + sources before querying", async () => {
    mockedQuery
      .mockResolvedValueOnce(candidateRows)
      .mockResolvedValueOnce(summaryRows)
      .mockResolvedValueOnce(sourceRows);

    await loadConstituencyResult("AcGenApr2021", "S22", 1);

    // 3 CSV URL registrations (candidacies + summary + electoral) in
    // the Promise.all order from runQueries.
    expect(mockedRegisterCsv).toHaveBeenCalledTimes(3);
    const csvUrls = mockedRegisterCsv.mock.calls.map((c) => c[0]);
    const allUrls = csvUrls.join(" | ");
    // Vite serves datasets at /data/* in dev (BASE_URL=/), so URLs
    // start with /data/. The double "data" segment for the electoral
    // entity path is intentional: /data/ is the mount, /data/data/ is
    // the datasets/data/ subdir for long-format CSV.
    expect(allUrls).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv",
    );
    expect(allUrls).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/summary.csv",
    );
    expect(allUrls).toContain("/data/entities/electoral.csv");

    // X1a CSV-as-table registrations: dim_parties + sources flipped
    // to CSV-backed views.
    const csvAsTableIds = mockedRegisterCsvAsTable.mock.calls
      .map((c) => c[0])
      .sort();
    expect(csvAsTableIds).toEqual([
      "elections.dim_parties",
      "taxonomy.sources",
    ]);

    // ZERO parquet `registerTable` calls remain on this surface.
    const parquetTables = mockedRegister.mock.calls.map((c) => c[0]).sort();
    expect(parquetTables).toEqual([]);

    // ZERO requests for the F1.3a-decommissioned tables.
    expect(parquetTables).not.toContain("elections.elections_candidacies");
    expect(parquetTables).not.toContain("elections.dim_persons");
    expect(parquetTables).not.toContain("elections.dim_acs");
    expect(parquetTables).not.toContain("elections.election_results");
    // X1a flipped: dim_parties + sources are NO LONGER on the parquet path.
    expect(parquetTables).not.toContain("elections.dim_parties");
    expect(parquetTables).not.toContain("taxonomy.sources");
  });

  it("issues read_csv SQL against candidacies.csv (no read_parquet)", async () => {
    mockedQuery
      .mockResolvedValueOnce(candidateRows)
      .mockResolvedValueOnce(summaryRows)
      .mockResolvedValueOnce(sourceRows);

    await loadConstituencyResult("AcGenApr2021", "S22", 1);

    const sqls = mockedQuery.mock.calls.map((c) => c[0]);
    expect(sqls[0]).toContain("read_csv(");
    expect(sqls[0]).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv",
    );
    expect(sqls[0]).toContain("/entities/electoral.csv");
    expect(sqls[0]).toContain("columns={MOCKED}");
    expect(sqls[0]).not.toContain("read_parquet(");

    // Summary query also uses read_csv against summary.csv.
    expect(sqls[1]).toContain("read_csv(");
    expect(sqls[1]).toContain(
      "/elections/assembly/state=tamil-nadu/election=2021/summary.csv",
    );

    // Filter shape: state slug + ECI eci_no.
    expect(sqls[0]).toContain("e.state = 'tamil-nadu'");
    expect(sqls[0]).toContain("e.eci_no = 1");
  });
});

describe("loadConstituencyResult - partial / not_published", () => {
  it("returns partial when candidacies has zero rows for (state, eci, event)", async () => {
    mockedQuery.mockResolvedValueOnce([]); // candidates query returns nothing
    const res = await loadConstituencyResult("AcGenApr2021", "S22", 999);
    expect(res.status).toBe("partial");
    if (res.status !== "partial") return;
    expect(res.reason).toBe("not_published");
    expect(res.data.candidates).toEqual([]);
    expect(res.data.eci_no).toBe(999);
    // Skeleton carries the structural fields so the renderer does not NPE.
    expect(res.data.totals.votes_polled).toBe(0);
    expect(res.data.winner.votes).toBe(0);
  });

  it("does not run summary or sources queries when candidates is empty", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    await loadConstituencyResult("AcGenApr2021", "S22", 999);
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });
});

describe("loadConstituencyResult - failed arm", () => {
  it("maps a thrown SQL error to citizen-readable copy + a retry callable", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("HTTP 503 service unavailable"));
    const res = await loadConstituencyResult("AcGenApr2021", "S22", 1);
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    expect(res.reason).toBeTruthy();
    expect(res.reason.toLowerCase()).not.toMatch(/error:/);
    expect(res.reason.toLowerCase()).not.toMatch(/\.js:/);
    expect(typeof res.retry).toBe("function");
  });

  it("retry callable re-invokes the loader (and can now succeed)", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("transient wasm boot fail"));
    const first = await loadConstituencyResult("AcGenApr2021", "S22", 1);
    expect(first.status).toBe("failed");

    mockedQuery
      .mockResolvedValueOnce(candidateRows)
      .mockResolvedValueOnce(summaryRows)
      .mockResolvedValueOnce(sourceRows);
    if (first.status !== "failed" || !first.retry) throw new Error("no retry");
    const retry = first.retry as () => ReturnType<typeof loadConstituencyResult>;
    const second = await retry();
    expect(second.status).toBe("ok");
  });

  it("maps a CSV-file registration failure to a citizen-readable arm", async () => {
    mockedRegisterCsv.mockRejectedValueOnce(new Error("ENOENT: no such file"));
    const res = await loadConstituencyResult("AcGenApr2021", "S22", 1);
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    expect(res.reason).toBeTruthy();
  });
});
