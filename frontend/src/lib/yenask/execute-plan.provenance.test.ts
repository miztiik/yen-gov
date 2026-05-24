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
  registerSlice: vi.fn().mockResolvedValue("view"),
  registerTable: vi.fn().mockResolvedValue("view"),
}));

import { query, registerSlice, registerTable } from "../duckdb";
import { executePlan } from "./execute-plan";
import type { DuckDBPlan } from "./types";

const queryMock = vi.mocked(query);
const registerSliceMock = vi.mocked(registerSlice);
const registerTableMock = vi.mocked(registerTable);

const PLAN: DuckDBPlan = {
  concept_id: "party_totals",
  slice_registrations: [
    {
      table_id: "elections.election_results",
      partition_filter: { state: "in_s22" },
      view_name: "election_results",
    },
  ],
  table_registrations: [
    { table_id: "taxonomy.sources", view_name: "sources" },
  ],
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
  title: "Constituency-wise result — Tamil Nadu AC General May 2026",
  vintage: "May 2026",
  license: "OGL-IN-1.0" as const,
  confidence_tier: "gold" as const,
  is_issuing_authority: true,
  verification_method: "live-fetch" as const,
  url_main: "https://results.eci.gov.in/AcGenMay2026/",
  citation_full: null,
  notes: null,
};

describe("executePlan — D-06 provenance discipline", () => {
  beforeEach(() => {
    queryMock.mockReset();
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
    expect(vm.source_strip[0]!.source_id).toBe("src-abcdef012345");
    expect(vm.rows).toEqual([FAKE_MAIN_ROW]);
  });

  it("synthesises the unattested row when the JOIN yields zero rows", async () => {
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([]); // empty provenance

    const vm = await executePlan(PLAN);
    expect(vm.provenance_status).toBe("missing");
    expect(vm.source_strip).toHaveLength(1);
    expect(vm.source_strip[0]!.source_id).toMatch(/^src-unattested-/);
    expect(vm.source_strip[0]!.producer).toBe("yen-gov");
    expect(vm.source_strip[0]!.verification_method).toBe("editorial");
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
      state: "in_s22",
    });
  });

  it("registers slice + table views from the plan", async () => {
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([FAKE_SOURCE_ROW]);

    await executePlan(PLAN);
    expect(registerSliceMock).toHaveBeenCalledWith(
      "elections.election_results",
      { state: "in_s22" },
      { viewName: "election_results" },
    );
    expect(registerTableMock).toHaveBeenCalledWith(
      "taxonomy.sources",
      { viewName: "sources" },
    );
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
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([{ ...FAKE_SOURCE_ROW, producer: "" }]);

    await expect(executePlan(PLAN)).rejects.toThrow();
  });
});
