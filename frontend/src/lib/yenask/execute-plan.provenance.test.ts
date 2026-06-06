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
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([{ ...FAKE_SOURCE_ROW, producer: "" }]);

    await expect(executePlan(PLAN)).rejects.toThrow();
  });

  // -------------------------------------------------------------------
  // YA cutover (2026-06-06) - sentinel coercion at the coerceSourceRow
  // boundary for X1a-NULL'd source fields per O3 doctrine. The
  // `registerCsvAsTable("taxonomy.sources")` view projects 4 of the 6
  // strict-enum Zod fields as NULL (because the 5-field source.csv
  // contract dropped them). coerceSourceRow fills the safest enum
  // variant at the boundary so the Zod parse accepts the row.
  // -------------------------------------------------------------------

  it("coerces NULL license to 'unknown-public' sentinel (X1a 5-field source.csv)", async () => {
    const nullLicenseRow = { ...FAKE_SOURCE_ROW, license: null };
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([nullLicenseRow]);

    const vm = await executePlan(PLAN);
    expect(vm.source_strip[0]!.license).toBe("unknown-public");
  });

  it("coerces NULL confidence_tier to 'bronze' sentinel (X1a 5-field source.csv)", async () => {
    const nullTierRow = { ...FAKE_SOURCE_ROW, confidence_tier: null };
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([nullTierRow]);

    const vm = await executePlan(PLAN);
    expect(vm.source_strip[0]!.confidence_tier).toBe("bronze");
  });

  it("coerces NULL is_issuing_authority to false sentinel (X1a 5-field source.csv)", async () => {
    const nullAuthorityRow = { ...FAKE_SOURCE_ROW, is_issuing_authority: null };
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([nullAuthorityRow]);

    const vm = await executePlan(PLAN);
    expect(vm.source_strip[0]!.is_issuing_authority).toBe(false);
  });

  it("coerces NULL verification_method to 'editorial' sentinel (X1a 5-field source.csv)", async () => {
    const nullMethodRow = { ...FAKE_SOURCE_ROW, verification_method: null };
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([nullMethodRow]);

    const vm = await executePlan(PLAN);
    expect(vm.source_strip[0]!.verification_method).toBe("editorial");
  });

  it("coerces ALL X1a-NULL'd source fields in one pass (the realistic post-cutover row shape)", async () => {
    // The shape the CSV-as-table view actually returns post-X1a: only
    // source_id + producer + title + vintage + url_main carry data;
    // license / confidence_tier / is_issuing_authority /
    // verification_method / citation_full / notes all NULL.
    const x1aRealisticRow = {
      source_id: "src-x1a01234567",
      producer: "Election Commission of India",
      title: "TN Assembly results CSV",
      vintage: "May 2026",
      license: null,
      confidence_tier: null,
      is_issuing_authority: null,
      verification_method: null,
      url_main: "https://results.eci.gov.in/AcGenMay2026/",
      citation_full: null,
      notes: null,
    };
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([x1aRealisticRow]);

    const vm = await executePlan(PLAN);
    expect(vm.provenance_status).toBe("joined");
    expect(vm.source_strip).toHaveLength(1);
    const row = vm.source_strip[0]!;
    expect(row.source_id).toBe("src-x1a01234567");
    expect(row.producer).toBe("Election Commission of India");
    expect(row.license).toBe("unknown-public");
    expect(row.confidence_tier).toBe("bronze");
    expect(row.is_issuing_authority).toBe(false);
    expect(row.verification_method).toBe("editorial");
    expect(row.citation_full).toBeNull();
    expect(row.notes).toBeNull();
  });

  it("preserves non-null source fields when the executor does see a fully-populated row", async () => {
    // Pre-X1a-shaped fully-populated rows (e.g. from the
    // synthesised unattested fallback or from a future restore path)
    // still flow through coerceSourceRow without sentinel-overwrite.
    queryMock
      .mockResolvedValueOnce([FAKE_MAIN_ROW])
      .mockResolvedValueOnce([FAKE_SOURCE_ROW]);

    const vm = await executePlan(PLAN);
    expect(vm.source_strip[0]!.license).toBe("OGL-IN-1.0");
    expect(vm.source_strip[0]!.confidence_tier).toBe("gold");
    expect(vm.source_strip[0]!.is_issuing_authority).toBe(true);
    expect(vm.source_strip[0]!.verification_method).toBe("live-fetch");
  });
});
