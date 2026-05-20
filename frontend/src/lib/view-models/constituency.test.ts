// Unit tests for the Constituency view-model loader (PR-E / Phase 1.3a).
//
// Per CLAUDE.md §15: the loader's contract IS the SQL boundary — mocking
// `query`/`registerTable` is the explicit carve-out from Holy Law #7. We
// don't boot DuckDB-WASM here; the round-trip is asserted in Playwright
// against a real Parquet shard.
//
// What we pin:
//   - "happy path" — given JOINed rows, the loader assembles the
//     ConstituencyResult shape Constituency.svelte already renders.
//   - "not_published" — zero candidate rows -> partial / not_published.
//   - "failed" — an injected throw -> failed arm with citizen-readable
//     reason + a callable retry that re-invokes the loader.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerTable: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

import { query, registerTable } from "../duckdb";
import { loadConstituencyResult } from "./constituency";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);

const candidateRows = [
  {
    candidate_id: "IN-S22-AC-2008-1-AcGenApr2021-C01",
    ac_id: "IN-S22-AC-2008-1",
    constituency_name: "GUMMIDIPOONDI",
    candidate_name: "GOVINDARAJAN T.J",
    rank: 1,
    party_id: "parties.IN.DMK",
    party_short: "DMK",
    party_full: "Dravida Munnetra Kazhagam",
    party_eci_code: "1234",
    votes: 126_452,
    vote_share_pct: 56.94,
  },
  {
    candidate_id: "IN-S22-AC-2008-1-AcGenApr2021-C02",
    ac_id: "IN-S22-AC-2008-1",
    constituency_name: "GUMMIDIPOONDI",
    candidate_name: "PRAKASH M",
    rank: 2,
    party_id: "parties.IN.PMK",
    party_short: "PMK",
    party_full: "Pattali Makkal Katchi",
    party_eci_code: "742",
    votes: 75_514,
    vote_share_pct: 34.0,
  },
];

const acScopeRows = [
  { indicator_id: "ac-total-electors", value_numeric: 281_688, value_text: null },
  { indicator_id: "ac-votes-polled", value_numeric: 222_069, value_text: null },
  { indicator_id: "ac-turnout-pct", value_numeric: 78.84, value_text: null },
  { indicator_id: "ac-nota-votes", value_numeric: 1783, value_text: null },
  { indicator_id: "ac-nota-pct", value_numeric: 0.8, value_text: null },
  { indicator_id: "ac-margin-votes", value_numeric: 50_938, value_text: null },
  { indicator_id: "ac-margin-pct", value_numeric: 22.94, value_text: null },
  { indicator_id: "ac-candidates-total", value_numeric: 9, value_text: null },
  { indicator_id: "ac-others-votes", value_numeric: 17_882, value_text: null },
  { indicator_id: "ac-others-pct", value_numeric: 8.05, value_text: null },
  {
    indicator_id: "ac-winner-candidate-id",
    value_numeric: null,
    value_text: "IN-S22-AC-2008-1-AcGenApr2021-C01",
  },
  {
    indicator_id: "ac-winner-party-id",
    value_numeric: null,
    value_text: "parties.IN.DMK",
  },
];

const sourceRows = [
  { url_main: "https://eci.gov.in/example.xlsx" },
];

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegister.mockReset();
  mockedRegister.mockResolvedValue("noop");
});

describe("loadConstituencyResult — happy path", () => {
  it("assembles ConstituencyResult from JOINed rows", async () => {
    mockedQuery
      .mockResolvedValueOnce(candidateRows)
      .mockResolvedValueOnce(acScopeRows)
      .mockResolvedValueOnce(sourceRows);

    const res = await loadConstituencyResult("AcGenApr2021", "S22", 1);
    expect(res.status).toBe("ok");
    if (res.status !== "ok") return;

    expect(res.data.election).toBe("AcGenApr2021");
    expect(res.data.state).toBe("S22");
    expect(res.data.eci_no).toBe(1);
    expect(res.data.constituency_name).toBe("GUMMIDIPOONDI");
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
    expect(res.data.totals.votes_polled).toBe(222_069);
    expect(res.data.totals.turnout_pct).toBe(78.84);
    expect(res.data.nota.votes).toBe(1783);
    expect(res.data.winner).toMatchObject({
      name: "GOVINDARAJAN T.J",
      party_short: "DMK",
      margin_votes: 50_938,
      margin_pct: 22.94,
    });
    expect(res.data.sources).toEqual([
      { url: "https://eci.gov.in/example.xlsx", fetched_at: "" },
    ]);
    expect(res.data.candidates_total).toBe(9);
    expect(res.data.others).toEqual({
      candidate_count: 7,
      votes: 17_882,
      vote_share_pct: 8.05,
    });
  });

  it("registers all five canonical tables before querying", async () => {
    mockedQuery
      .mockResolvedValueOnce(candidateRows)
      .mockResolvedValueOnce(acScopeRows)
      .mockResolvedValueOnce(sourceRows);
    await loadConstituencyResult("AcGenApr2021", "S22", 1);
    const registered = mockedRegister.mock.calls.map((c) => c[0]).sort();
    expect(registered).toEqual([
      "elections.dim_acs",
      "elections.dim_candidates",
      "elections.dim_parties",
      "elections.election_results",
      "taxonomy.sources",
    ]);
  });
});

describe("loadConstituencyResult — partial / not_published", () => {
  it("returns partial when dim_candidates has zero rows for (state, eci, event)", async () => {
    mockedQuery.mockResolvedValueOnce([]); // candidates query returns nothing
    const res = await loadConstituencyResult("AcGenApr2021", "S22", 999);
    expect(res.status).toBe("partial");
    if (res.status !== "partial") return;
    expect(res.reason).toBe("not_published");
    expect(res.data.candidates).toEqual([]);
    expect(res.data.eci_no).toBe(999);
    // Skeleton carries the structural fields so the renderer doesn't NPE.
    expect(res.data.totals.votes_polled).toBe(0);
    expect(res.data.winner.votes).toBe(0);
  });

  it("does not run AC-scope or sources queries when candidates is empty", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    await loadConstituencyResult("AcGenApr2021", "S22", 999);
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });
});

describe("loadConstituencyResult — failed arm", () => {
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
      .mockResolvedValueOnce(acScopeRows)
      .mockResolvedValueOnce(sourceRows);
    if (first.status !== "failed" || !first.retry) throw new Error("no retry");
    const second = await first.retry();
    expect(second.status).toBe("ok");
  });

  it("maps a manifest fetch failure to the catalogue-unavailable copy", async () => {
    mockedRegister.mockRejectedValueOnce(new Error("manifest fetch failed: 404"));
    const res = await loadConstituencyResult("AcGenApr2021", "S22", 1);
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    expect(res.reason).toMatch(/catalogue/i);
  });
});
