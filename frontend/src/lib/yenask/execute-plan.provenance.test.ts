// Executor-level provenance tests (D-06).
//
// These tests exercise `executePlan()` against a mocked `lib/duckdb`. The
// goal is the 3-case D-06 matrix:
//   1. provenance JOIN returns rows  -> provenance_status: "joined"
//   2. provenance JOIN returns zero  -> provenance_status: "missing"
//                                       + synthesised unattested row
//   3. compiler bug produces empty source_strip via direct VM build
//      -> Zod parse rejects it. (Covered in answer-viewmodel.test.ts;
//      reasserted here at the executor boundary for clarity.)

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  query: vi.fn(),
  registerCsvFile: vi.fn().mockResolvedValue(undefined),
  registerCsvAsTable: vi.fn().mockResolvedValue("view"),
  registerSlice: vi.fn().mockResolvedValue("view"),
  registerTable: vi.fn().mockResolvedValue("view"),
}));

import { query, registerCsvAsTable, registerCsvFile, registerSlice, registerTable } from "../duckdb";
import { executePlan } from "./execute-plan";
import type { DuckDBPlan } from "./types";

const queryMock = vi.mocked(query);
const registerCsvMock = vi.mocked(registerCsvFile);
const registerCsvAsTableMock = vi.mocked(registerCsvAsTable);
const registerSliceMock = vi.mocked(registerSlice);
const registerTableMock = vi.mocked(registerTable);

const PLAN: DuckDBPlan = {
  concept_id: "party_totals",
  slice_registrations: [
    {
      table_id: "elections.election_results",
      partition_filter: { state: "tamil-nadu" },
      view_name: "election_results",
    },
  ],
  table_registrations: [
    { table_id: "taxonomy.sources", view_name: "sources" },
  ],
  csv_registrations: [],
  main_sql: "SELECT party_short, seats_won, votes, vote_share_pct FROM v",
  provenance_sql: "SELECT * FROM sources",
  view_hints: {
    question: "What were the May 2026 Tamil Nadu party totals?",
    column_order: ["party_short", "seats_won", "votes", "vote_share_pct"],
    column_labels: {
      party_short: "Party",
      seats_won: "Seats won",
      votes: "Votes",
      vote_share_pct: "Vote share",
    },
    column_formats: {
      party_short: "text",
      seats_won: "integer",
      votes: "thousands",
      vote_share_pct: "percentage",
    },
  },
};

const FAKE_MAIN_ROW = {
  party_short: "DMK",
  seats_won: 133,
  votes: 18_345_678,
  vote_share_pct: 38.74,
};

const FAKE_SOURCE_ROW = {
  source_id: "src-abcdef012345",
  producer: "Election Commission of India",
  title: "Constituency-wise result - Tamil Nadu AC General May 2026",
  vintage: "May 2026",
  url: "https://results.eci.gov.in/AcGenMay2026/",
};

describe("executePlan — D-06 provenance discipline", () => {
  beforeEach(() => {
    queryMock.mockReset();
    registerCsvMock.mockReset().mockResolvedValue(undefined);
    registerCsvAsTableMock.mockReset().mockResolvedValue("view");
    registerSliceMock.mockReset().mockResolvedValue("view");
    registerTableMock.mockReset().mockResolvedValue("view");
  });

  it("returns provenance_status='joined' when the JOIN yields rows", async () => {
    // Order: main_sql + provenance_sql run in parallel; vitest's mock
    // queue serves in call order. The executor's Promise.all order is
    // [main, provenance].
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([FAKE_SOURCE_ROW]);

    const vm = await executePlan(PLAN);
    expect(vm.provenance_status).toBe("joined");
    expect(vm.source_strip).toHaveLength(1);
    // Source row is deduped into a publisher pill; label is
    // "<publisherDisplay> <seriesFamily>" or just <publisherDisplay>
    // when over the 30-char budget.
    expect(vm.source_strip[0]!.label).toContain("ECI");
    expect(vm.source_strip[0]!.vintage_summary).toBe("May 2026");
    expect(vm.rows).toEqual([FAKE_MAIN_ROW]);
  });

  it("synthesises the unattested pill when the JOIN yields zero rows", async () => {
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([]); // empty provenance

    const vm = await executePlan(PLAN);
    expect(vm.provenance_status).toBe("missing");
    expect(vm.source_strip).toHaveLength(1);
    expect(vm.source_strip[0]!.label).toBe("Source unattested");
  });

  it("threads concept_id and plan SQL into the computation block", async () => {
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([FAKE_SOURCE_ROW]);

    const vm = await executePlan(PLAN);
    expect(vm.computation.concept_id).toBe("party_totals");
    expect(vm.computation.main_sql).toBe(PLAN.main_sql);
    expect(vm.computation.provenance_sql).toBe(PLAN.provenance_sql);
    expect(vm.computation.slice_registrations[0]!.partition_filter).toEqual({
      state: "tamil-nadu",
    });
  });

  it("registers slice + table views from the plan", async () => {
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([FAKE_SOURCE_ROW]);

    await executePlan(PLAN);
    expect(registerSliceMock).toHaveBeenCalledWith(
      "elections.election_results",
      { state: "tamil-nadu" },
      { viewName: "election_results" },
    );
    // X1a: taxonomy.sources dispatches through registerCsvAsTable (not
    // registerTable) per the executor's CSV_AS_TABLE_IDS dispatch set.
    expect(registerCsvAsTableMock).toHaveBeenCalledWith("taxonomy.sources");
    expect(registerTableMock).not.toHaveBeenCalledWith(
      "taxonomy.sources",
      expect.anything(),
    );
  });

  it("registers F1.3b csv_registrations URLs via registerCsvFile", async () => {
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([FAKE_SOURCE_ROW]);

    const PLAN_WITH_CSV: DuckDBPlan = {
      ...PLAN,
      csv_registrations: [
        { url: "/data/elections/assembly/state=tamil-nadu/election=2026/candidacies.csv" },
        { url: "/data/data/entities/electoral.csv" },
      ],
    };
    await executePlan(PLAN_WITH_CSV);
    const csvUrls = registerCsvMock.mock.calls.map(c => c[0]).sort();
    expect(csvUrls).toEqual([
      "/data/data/entities/electoral.csv",
      "/data/elections/assembly/state=tamil-nadu/election=2026/candidacies.csv",
    ]);
  });

  it("coerces bigint values to JS numbers in answer rows", async () => {
    const bigintRow = {
      party_short: "AIADMK",
      seats_won: 5n,
      votes: 12_345_678n,
      vote_share_pct: 12.5,
    };
    queryMock
      .mockResolvedValueOnce([bigintRow])
      .mockResolvedValueOnce([FAKE_SOURCE_ROW]);

    const vm = await executePlan(PLAN);
    expect(vm.rows[0]!.seats_won).toBe(5);
    expect(vm.rows[0]!.votes).toBe(12345678);
    expect(typeof vm.rows[0]!.votes).toBe("number");
  });

  it("Zod-rejects a malformed source row from the executor path", async () => {
    // A producer="" raw row produces an empty publisher pill label,
    // which the strict Zod schema rejects.
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([{ ...FAKE_SOURCE_ROW, producer: "" }]);

    await expect(executePlan(PLAN)).rejects.toThrow();
  });
});
