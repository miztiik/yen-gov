// Unit tests for the ElectionSeatsTrend view-model loader (PR-G / Phase 1.3c).
//
// Mocks `query` / `registerTable` at the `../duckdb` boundary per Holy Law #7
// carve-out (established by PR-E, validated by PR-F). The actual Parquet
// round-trip is asserted by the Playwright golden-path spec against TN.
//
// Coverage:
//   - happy path: 2 events × 2 parties, rows assemble + sources flow through.
//   - registerTable: all three canonical tables registered once.
//   - empty event_ids → partial (no SQL fired).
//   - query returns zero rows → partial / not_published.
//   - failed: thrown error → citizen copy + callable retry.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerTable: vi.fn(async () => "noop"),
  query: vi.fn(),
}));

import { query, registerTable } from "../duckdb";
import { loadElectionSeatsTrend } from "./election-seats-trend";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);

const partyRows = [
  {
    period_label: "AcGenMay2026",
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
    period_label: "AcGenMay2026",
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
    period_label: "AcGenApr2021",
    short_name_key: "DMK",
    short_name: "DMK",
    full_name: "Dravida Munnetra Kazhagam",
    eci_code: "1234",
    seats_contested: 173,
    seats_won: 125,
    votes: 21_000_000,
    vote_share_pct: 36.7,
  },
  {
    period_label: "AcGenApr2021",
    short_name_key: "AIADMK",
    short_name: "AIADMK",
    full_name: "All India Anna Dravida Munnetra Kazhagam",
    eci_code: "742",
    seats_contested: 191,
    seats_won: 75,
    votes: 19_800_000,
    vote_share_pct: 33.3,
  },
];

const sourceRows = [
  {
    url: "https://eci.gov.in/results/tn-2021.xlsx",
    first_fetched_at: "2026-05-01T00:00:00Z",
  },
];

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegister.mockReset();
  mockedRegister.mockResolvedValue("noop");
});

describe("loadElectionSeatsTrend — happy path", () => {
  it("assembles ElectionSeatsTrendViewModel grouped by period_label", async () => {
    mockedQuery
      .mockResolvedValueOnce(partyRows)
      .mockResolvedValueOnce(sourceRows);
    const res = await loadElectionSeatsTrend("S22", [
      "AcGenMay2026",
      "AcGenApr2021",
    ]);
    expect(res.status).toBe("ok");
    if (res.status !== "ok") return;
    expect(res.data.state).toBe("S22");
    expect(res.data.events).toHaveLength(2);
    const may = res.data.events.find((e) => e.event_id === "AcGenMay2026");
    expect(may?.party_totals).toHaveLength(2);
    expect(may?.total_seats).toBe(133 + 66);
    const apr = res.data.events.find((e) => e.event_id === "AcGenApr2021");
    expect(apr?.total_seats).toBe(125 + 75);
    expect(res.data.sources).toEqual([
      {
        url: "https://eci.gov.in/results/tn-2021.xlsx",
        fetched_at: "2026-05-01T00:00:00Z",
      },
    ]);
  });

  it("registers all three canonical tables before querying", async () => {
    mockedQuery
      .mockResolvedValueOnce(partyRows)
      .mockResolvedValueOnce(sourceRows);
    await loadElectionSeatsTrend("S22", ["AcGenMay2026"]);
    const registered = mockedRegister.mock.calls.map((c) => c[0]).sort();
    expect(registered).toEqual([
      "elections.dim_parties",
      "elections.election_results",
      "taxonomy.sources",
    ]);
  });
});

describe("loadElectionSeatsTrend — partial arms", () => {
  it("returns partial without firing SQL when event_ids is empty", async () => {
    const res = await loadElectionSeatsTrend("S99", []);
    expect(res.status).toBe("partial");
    if (res.status !== "partial") return;
    expect(res.reason).toBe("not_published");
    expect(res.data.events).toEqual([]);
    expect(mockedQuery).not.toHaveBeenCalled();
    expect(mockedRegister).not.toHaveBeenCalled();
  });

  it("returns partial when SQL returns zero party rows", async () => {
    mockedQuery.mockResolvedValueOnce([]).mockResolvedValueOnce([]);
    const res = await loadElectionSeatsTrend("S22", ["AcGenMay2099"]);
    expect(res.status).toBe("partial");
    if (res.status !== "partial") return;
    expect(res.reason).toBe("not_published");
    expect(res.data.events).toEqual([]);
  });
});

describe("loadElectionSeatsTrend — failed arm", () => {
  it("maps a thrown SQL error to citizen-readable copy + retry", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("HTTP 503 service unavailable"));
    const res = await loadElectionSeatsTrend("S22", ["AcGenMay2026"]);
    expect(res.status).toBe("failed");
    if (res.status !== "failed") return;
    expect(res.reason).toBeTruthy();
    expect(res.reason.toLowerCase()).not.toMatch(/error:/);
    expect(typeof res.retry).toBe("function");
  });
});
