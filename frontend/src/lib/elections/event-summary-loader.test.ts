// PR-E3 vitest for `lib/elections/event-summary-loader.ts`.
//
// Per CLAUDE.md section 15: mocking the DuckDB-WASM boundary
// (`query` + `registerCsvFile`) + the column-contract clause is the
// approved carve-out from Holy Law #7 for view-model tests.

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  query: vi.fn(),
  registerCsvFile: vi.fn(async () => undefined),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async () => "columns={}"),
}));

import { query, registerCsvFile } from "../duckdb";
import {
  EVENT_SUMMARY_REL,
  EVENT_SUMMARY_URL,
  _resetEventSummaryCacheForTests,
  loadEventSummary,
} from "./event-summary-loader";

const mockedQuery = vi.mocked(query);
const mockedRegisterCsvFile = vi.mocked(registerCsvFile);

beforeEach(() => {
  _resetEventSummaryCacheForTests();
  mockedQuery.mockReset();
  mockedRegisterCsvFile.mockReset();
  mockedRegisterCsvFile.mockResolvedValue(undefined);
});

describe("loadEventSummary", () => {
  it("registers the CSV and reads via read_csv on first call", async () => {
    mockedQuery.mockResolvedValue([]);
    await loadEventSummary();
    expect(mockedRegisterCsvFile).toHaveBeenCalledWith(EVENT_SUMMARY_URL);
    const sql = mockedQuery.mock.calls[0]?.[0] as string;
    expect(sql).toContain(`read_csv('${EVENT_SUMMARY_URL}'`);
    expect(sql).toContain("CAST(seats_won AS BIGINT) AS seats_won");
    expect(sql).toContain("CAST(seats_contested AS BIGINT) AS seats_contested");
  });

  it("normalises bigint seats to plain number; null leading_party preserved", async () => {
    mockedQuery.mockResolvedValue([
      {
        event_id: "general-2024",
        state_code: null,
        scope: "national",
        kind: "parliament",
        polled_on: "2024-06-01",
        leading_party_id: "parties.IN.BJP",
        seats_won: 240n as unknown as bigint,
        seats_contested: 543n as unknown as bigint,
        turnout_pct: 66.1,
        runner_up_party_id: "parties.IN.INC",
        runner_up_seats: 99n as unknown as bigint,
        source_id: "src-abc",
      },
      {
        event_id: "assembly-2026",
        state_code: "S22",
        scope: "state",
        kind: "assembly",
        polled_on: "2026-05-08",
        leading_party_id: null,
        seats_won: 0,
        seats_contested: 234,
        turnout_pct: null,
        runner_up_party_id: null,
        runner_up_seats: null,
        source_id: "src-xyz",
      },
    ]);
    const rows = await loadEventSummary();
    expect(rows).toHaveLength(2);
    expect(rows[0].seats_won).toBe(240);
    expect(rows[0].seats_contested).toBe(543);
    expect(typeof rows[0].seats_won).toBe("number");
    expect(rows[0].runner_up_seats).toBe(99);
    expect(rows[1].leading_party_id).toBeNull();
    expect(rows[1].state_code).toBe("S22");
    expect(rows[1].turnout_pct).toBeNull();
    expect(rows[1].runner_up_seats).toBeNull();
  });

  it("caches the promise across concurrent + serial calls", async () => {
    mockedQuery.mockResolvedValue([]);
    const a = loadEventSummary();
    const b = loadEventSummary();
    await Promise.all([a, b]);
    expect(mockedQuery).toHaveBeenCalledTimes(1);
    await loadEventSummary();
    expect(mockedQuery).toHaveBeenCalledTimes(1);
  });

  it("resets the cache when the underlying query rejects", async () => {
    mockedQuery.mockRejectedValueOnce(new Error("network down"));
    await expect(loadEventSummary()).rejects.toThrow("network down");
    mockedQuery.mockResolvedValueOnce([]);
    const rows = await loadEventSummary();
    expect(rows).toEqual([]);
    expect(mockedQuery).toHaveBeenCalledTimes(2);
  });

  it("exposes the file-class rel for csv-columns lookups", () => {
    expect(EVENT_SUMMARY_REL).toBe(
      "datasets/data/marts/elections/event_summary.csv",
    );
  });
});
