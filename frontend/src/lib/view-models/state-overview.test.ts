// Unit tests for the StateOverview view-model loader (PR-F / Phase 1.3b).
//
// Per CLAUDE.md §15 + Holy Law #7 carve-out (established by PR-E): the
// loader's contract IS the DuckDB-WASM boundary, so mocking `query` /
// `registerTable` at `../duckdb` is the sanctioned pattern. The real
// Parquet round-trip is asserted by the Playwright golden-path spec
// (frontend/e2e/golden-path.spec.ts) against the live TN shard.
//
// Coverage:
//   - happy path: assembles StateOverviewViewModel from party pivot +
//     state-scope facts + sources (DMK / AIADMK fixture).
//   - registerTable: all three canonical tables registered once.
//   - partial / not_published: zero party rows -> skeleton.
//   - failed: thrown SQL error -> citizen copy + callable retry.
//   - retry: re-invokes the loader; second attempt can succeed.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerTable: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

import { query, registerTable } from "../duckdb";
import { loadStateOverview } from "./state-overview";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);

const partyRows = [
  {
    short_name_key: "DMK",
    short_name: "DMK",
    full_name: "Dravida Munnetra Kazhagam",
    eci_code: "1234",
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
    seats_contested: 191,
    seats_won: 66,
    votes: 19_300_000,
    vote_share_pct: 33.3,
  },
  {
    // dim_parties has no row for CPIM today — LEFT JOIN yields null cols.
    short_name_key: "CPIM",
    short_name: null,
    full_name: null,
    eci_code: null,
    seats_contested: 6,
    seats_won: 2,
    votes: 1_100_000,
    vote_share_pct: 1.9,
  },
];

const stateScopeRows = [
  { indicator_id: "state-electors-total", value_numeric: 62_700_000 },
  { indicator_id: "state-votes-polled", value_numeric: 45_900_000 },
  { indicator_id: "state-turnout-pct", value_numeric: 72.81 },
];

const sourceRows = [
  {
    url: "https://eci.gov.in/results/tn-2021.xlsx",
    first_fetched_at: "2026-05-01T00:00:00Z",
  },
  {
    url: "https://eci.gov.in/results/tn-2021-parties.xlsx",
    first_fetched_at: "2026-05-02T00:00:00Z",
  },
];

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegister.mockReset();
  mockedRegister.mockResolvedValue("noop");
});

describe("loadStateOverview — happy path", () => {
  it("assembles StateOverviewViewModel from JOINed rows", async () => {
    mockedQuery
      .mockResolvedValueOnce(partyRows)
      .mockResolvedValueOnce(stateScopeRows)
      .mockResolvedValueOnce(sourceRows);

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
      seats_contested: 173,
      seats_won: 133,
      votes: 22_350_000,
      vote_share_pct: 37.7,
    });
    // CPIM falls back to the extracted short_name_key when dim row absent.
    expect(res.data.party_totals[2]).toMatchObject({
      party_short: "CPIM",
      party_full: null,
      party_eci_code: null,
      seats_won: 2,
    });
    // total_seats is derived in-loader, not a fourth query.
    expect(res.data.total_seats).toBe(133 + 66 + 2);
    expect(res.data.totals).toEqual({
      electors: 62_700_000,
      votes_polled: 45_900_000,
      turnout_pct: 72.81,
    });
    expect(res.data.sources).toEqual([
      {
        url: "https://eci.gov.in/results/tn-2021.xlsx",
        fetched_at: "2026-05-01T00:00:00Z",
      },
      {
        url: "https://eci.gov.in/results/tn-2021-parties.xlsx",
        fetched_at: "2026-05-02T00:00:00Z",
      },
    ]);
  });

  it("registers all three canonical tables before querying", async () => {
    mockedQuery
      .mockResolvedValueOnce(partyRows)
      .mockResolvedValueOnce(stateScopeRows)
      .mockResolvedValueOnce(sourceRows);
    await loadStateOverview("AcGenApr2021", "S22");
    const registered = mockedRegister.mock.calls.map((c) => c[0]).sort();
    expect(registered).toEqual([
      "elections.dim_parties",
      "elections.observations",
      "taxonomy.sources",
    ]);
  });
});

describe("loadStateOverview — partial / not_published", () => {
  it("returns partial when zero party rows for (state, event)", async () => {
    mockedQuery.mockResolvedValueOnce([]); // party pivot returns nothing
    const res = await loadStateOverview("AcGenMay2099", "S22");
    expect(res.status).toBe("partial");
    if (res.status !== "partial") return;
    expect(res.reason).toBe("not_published");
    expect(res.data.party_totals).toEqual([]);
    expect(res.data.sources).toEqual([]);
    expect(res.data.totals).toBeNull();
    expect(res.data.total_seats).toBe(0);
    expect(res.data.election).toBe("AcGenMay2099");
    expect(res.data.state).toBe("S22");
  });

  it("does not run state-scope or sources queries when party rows empty", async () => {
    mockedQuery.mockResolvedValueOnce([]);
    await loadStateOverview("AcGenMay2099", "S22");
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });
});

describe("loadStateOverview — failed arm", () => {
  it("maps a thrown SQL error to citizen-readable copy + retry", async () => {
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
      .mockResolvedValueOnce(sourceRows);
    if (first.status !== "failed" || !first.retry) throw new Error("no retry");
    const second = await first.retry();
    expect(second.status).toBe("ok");
  });

  it("maps a manifest fetch failure to the catalogue-unavailable copy", async () => {
    mockedRegister.mockRejectedValueOnce(new Error("manifest fetch failed: 404"));
    const res = await loadStateOverview("AcGenApr2021", "S22");
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    expect(res.reason).toMatch(/catalogue/i);
  });
});
