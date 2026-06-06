// Unit tests for the ElectionSeatsTrend view-model loader (PR-G / Phase 1.3c).
//
// Mocks `query` / `registerSlice` / `registerTable` / `registerCsvAsTable`
// at the `../duckdb` boundary per Holy Law #7 carve-out (established by
// PR-E, validated by PR-F). The `registerCsvAsTable` entry was added by
// X1a (PR #809) when dim_parties + taxonomy.sources flipped from parquet
// to CSV; E5 corrects the test mock that stayed stuck on the pre-flip
// shape. The actual Parquet round-trip is asserted by the Playwright
// golden-path spec against TN.
//
// Coverage:
//   - happy path: 2 events x 2 parties, rows assemble + sources flow through.
//   - registerTable: all three canonical tables registered once.
//   - empty event_ids -> partial (no SQL fired).
//   - query returns zero rows -> partial / not_published.
//   - failed: thrown error -> citizen copy + callable retry.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  registerSlice: vi.fn(async () => "noop"),
  registerTable: vi.fn(async () => "noop"),
  registerCsvAsTable: vi.fn(async (id: string) =>
    id === "elections.dim_parties" ? "dim_parties" : "sources",
  ),
  query: vi.fn(),
}));

import { query, registerCsvAsTable, registerSlice, registerTable } from "../duckdb";
import { loadElectionSeatsTrend } from "./election-seats-trend";

const mockedQuery = vi.mocked(query);
const mockedRegister = vi.mocked(registerTable);
const mockedRegisterSlice = vi.mocked(registerSlice);
const mockedRegisterCsvAsTable = vi.mocked(registerCsvAsTable);

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
    party_id: "parties.IN.DMK",
    brand_colour_hex: null,
    brand_colour_confidence: null,
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
    party_id: "parties.IN.AIADMK",
    brand_colour_hex: null,
    brand_colour_confidence: null,
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
    party_id: "parties.IN.DMK",
    brand_colour_hex: null,
    brand_colour_confidence: null,
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
    party_id: "parties.IN.AIADMK",
    brand_colour_hex: null,
    brand_colour_confidence: null,
  },
];

const sourceRows = [
  {
    source_id: "src-eci2021000001",
    producer: "Election Commission of India",
    title: "Statistical Report Section 10 — Tamil Nadu",
    vintage: "AcGenApr2021",
    license: "OGL-IN-1.0",
    confidence_tier: "gold",
    is_issuing_authority: true,
    verification_method: "live-fetch",
    url_main: "https://eci.gov.in/results/tn-2021.xlsx",
    citation_full: null,
    notes: null,
  },
];

beforeEach(() => {
  mockedQuery.mockReset();
  mockedRegister.mockReset();
  mockedRegisterSlice.mockReset();
  mockedRegisterCsvAsTable.mockReset();
  mockedRegister.mockResolvedValue("noop");
  mockedRegisterSlice.mockResolvedValue("noop");
  mockedRegisterCsvAsTable.mockImplementation(async (id) =>
    id === "elections.dim_parties" ? "dim_parties" : "sources",
  );
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
        fetched_at: "",
      },
    ]);
    // v2.0 ledger projection lives alongside the legacy SourceRef[]
    // back-compat array. Mirrors the full 11-column citation ledger
    // per ADR-0032 + R-24 (no fetch telemetry).
    expect(res.data.sources_v2).toEqual([
      {
        source_id: "src-eci2021000001",
        producer: "Election Commission of India",
        title: "Statistical Report Section 10 — Tamil Nadu",
        vintage: "AcGenApr2021",
        license: "OGL-IN-1.0",
        confidence_tier: "gold",
        is_issuing_authority: true,
        verification_method: "live-fetch",
        url_main: "https://eci.gov.in/results/tn-2021.xlsx",
        citation_full: null,
        notes: null,
      },
    ]);
  });

  it("registers the state fact slice and supporting tables before querying", async () => {
    mockedQuery
      .mockResolvedValueOnce(partyRows)
      .mockResolvedValueOnce(sourceRows);
    await loadElectionSeatsTrend("S22", ["AcGenMay2026"]);
    expect(mockedRegisterSlice).toHaveBeenCalledWith(
      "elections.election_results",
      { state: "tamil-nadu" },
    );
    // dim_parties + taxonomy.sources flipped to CSV via X1a (PR #809).
    // No surviving `registerTable` calls in this loader after X1a.
    const registered = mockedRegister.mock.calls.map((c) => c[0]).sort();
    expect(registered).toEqual([]);
    const csvAsTableIds = mockedRegisterCsvAsTable.mock.calls
      .map((c) => c[0])
      .sort();
    expect(csvAsTableIds).toEqual([
      "elections.dim_parties",
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
    expect(res.data.sources_v2).toEqual([]);
    expect(mockedQuery).not.toHaveBeenCalled();
    expect(mockedRegister).not.toHaveBeenCalled();
    expect(mockedRegisterCsvAsTable).not.toHaveBeenCalled();
    expect(mockedRegisterSlice).not.toHaveBeenCalled();
  });

  it("returns partial when SQL returns zero party rows", async () => {
    mockedQuery.mockResolvedValueOnce([]).mockResolvedValueOnce([]);
    const res = await loadElectionSeatsTrend("S22", ["AcGenMay2099"]);
    expect(res.status).toBe("partial");
    if (res.status !== "partial") return;
    expect(res.reason).toBe("not_published");
    expect(res.data.events).toEqual([]);
    expect(res.data.sources_v2).toEqual([]);
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
