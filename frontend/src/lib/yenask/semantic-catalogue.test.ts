// SemanticCatalogue loader tests.
//
// The catalogue depends on DuckDB-WASM at runtime; per CLAUDE.md §15 the
// `lib/duckdb` module is a legitimate test seam (the loader's contract IS
// the fetch boundary). Mocks here mirror the pattern in
// `lib/psephlab/canonical-loaders.test.ts` (`vi.mock("../duckdb", ...)`).
//
// YA cutover (2026-06-06): dim_acs + elections_candidacies parquet
// registerTable calls retired; state enumeration moved to an inline
// `read_csv('data/entities/electoral.csv', ...)` via `registerCsvFile`,
// and election-period enumeration moved to `fetchElectionEvents()` (a
// plain JSON fetch helper). Mocks updated accordingly.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  query: vi.fn(),
  registerSlice: vi.fn(),
  registerTable: vi.fn().mockResolvedValue("view"),
  registerCsvAsTable: vi.fn().mockResolvedValue("view"),
  registerCsvFile: vi.fn().mockResolvedValue(undefined),
  loadManifest: vi.fn(),
}));

vi.mock("../canonical/csv-columns", () => ({
  csvColumnsClause: vi.fn(async () => "columns={MOCKED}"),
}));

vi.mock("../election-events", () => ({
  fetchElectionEvents: vi.fn(),
}));

import {
  loadManifest,
  query,
  registerCsvAsTable,
  registerCsvFile,
  registerTable,
} from "../duckdb";
import { fetchElectionEvents } from "../election-events";
import {
  __resetCatalogueForTests,
  loadSemanticCatalogue,
} from "./semantic-catalogue";

const queryMock = vi.mocked(query);
const registerTableMock = vi.mocked(registerTable);
const registerCsvAsTableMock = vi.mocked(registerCsvAsTable);
const registerCsvFileMock = vi.mocked(registerCsvFile);
const loadManifestMock = vi.mocked(loadManifest);
const fetchElectionEventsMock = vi.mocked(fetchElectionEvents);

const FAKE_MANIFEST = {
  schema_version: "1.0",
  generated_at: "2026-05-25T00:00:00Z",
  tables: [
    {
      table_id: "elections.election_results",
      family: "elections",
      kind: "fact",
      partition_columns: ["state"],
      files: [],
    },
    {
      table_id: "taxonomy.sources",
      family: "taxonomy",
      kind: "dim",
      partition_columns: [],
      files: [],
    },
  ],
};

const FAKE_SOURCES = [
  { source_id: "src-abc", producer: "ECI", title: "Results TN", vintage: "May 2026" },
];
const FAKE_PARTIES = [
  { short_code: "DMK", display_name: "Dravida Munnetra Kazhagam" },
  { short_code: "AIADMK", display_name: "All India Anna Dravida Munnetra Kazhagam" },
];
// electoral.csv DISTINCT state slug (post-cutover SQL returns slug-form
// directly; the loader inverts ECI_TO_LGD_SLUG to recover eci_code).
const FAKE_ELECTORAL_STATES = [{ state_slug: "tamil-nadu" }];

// fetchElectionEvents() returns the full taxonomy/election_events.json
// payload keyed by ECI state code. The loader iterates and synthesises
// CatalogueElectionPeriod entries from the rows.
const FAKE_ELECTION_EVENTS = {
  $schema: "./election-events.schema.json",
  $schema_version: "1.0",
  sources: [],
  states: {
    S22: [
      {
        event_id: "AcGenMay2026",
        kind: "assembly" as const,
        display: "Tamil Nadu Assembly · May 2026",
        polled_on: "2026-05-08",
        term_end_estimated: "2031-05-07",
        data_status: "complete" as const,
      },
    ],
  },
};

function primeQueries(): void {
  // Order matches the Promise.all in buildCatalogue: sources, parties,
  // state-slug rows (electoral.csv), electionEvents (separate
  // fetchElectionEvents mock).
  queryMock
    .mockResolvedValueOnce(FAKE_SOURCES)
    .mockResolvedValueOnce(FAKE_PARTIES)
    .mockResolvedValueOnce(FAKE_ELECTORAL_STATES);
  fetchElectionEventsMock.mockResolvedValueOnce(FAKE_ELECTION_EVENTS);
}

describe("loadSemanticCatalogue", () => {
  beforeEach(() => {
    __resetCatalogueForTests();
    queryMock.mockReset();
    registerTableMock.mockReset().mockResolvedValue("view");
    registerCsvAsTableMock.mockReset().mockResolvedValue("view");
    registerCsvFileMock.mockReset().mockResolvedValue(undefined);
    fetchElectionEventsMock.mockReset();
    loadManifestMock.mockReset().mockResolvedValue(FAKE_MANIFEST as never);
  });

  afterEach(() => {
    __resetCatalogueForTests();
  });

  it("assembles a catalogue from manifest + CSV-backed queries + election-events", async () => {
    primeQueries();
    const cat = await loadSemanticCatalogue();

    expect(cat.states).toHaveLength(1);
    expect(cat.states[0]!.partition_id).toBe("tamil-nadu");
    expect(cat.states[0]!.eci_code).toBe("S22");

    expect(cat.parties.map(p => p.short_code)).toEqual(["DMK", "AIADMK"]);
    expect(cat.sources[0]!.producer).toBe("ECI");
    expect(cat.election_periods[0]!.period_label).toBe("AcGenMay2026");
    expect(cat.election_periods[0]!.state_partition_id).toBe("tamil-nadu");
    expect(cat.election_periods[0]!.display_name).toBe(
      "Tamil Nadu Assembly · May 2026",
    );
    expect(cat.tables.map(t => t.table_id)).toContain("elections.election_results");
  });

  it("registers the X1a CSV-as-table views + electoral.csv file (NOT dim_acs / elections_candidacies parquet)", async () => {
    primeQueries();
    await loadSemanticCatalogue();

    const csvAsTableRegistered = registerCsvAsTableMock.mock.calls.map(c => c[0]);
    expect(csvAsTableRegistered).toContain("taxonomy.sources");
    expect(csvAsTableRegistered).toContain("elections.dim_parties");

    // YA cutover: dim_acs + elections_candidacies parquet reads are RETIRED.
    const tableRegistered = registerTableMock.mock.calls.map(c => c[0]);
    expect(tableRegistered).not.toContain("elections.dim_acs");
    expect(tableRegistered).not.toContain("elections.elections_candidacies");

    // electoral.csv URL is registered via registerCsvFile so the
    // embedded read_csv(<url>, columns=...) inside the state-distinct
    // query can HTTP-fetch it.
    const csvFilesRegistered = registerCsvFileMock.mock.calls.map(c => c[0]);
    expect(
      csvFilesRegistered.some(u => /\/data\/entities\/electoral\.csv$/.test(u)),
      `expected an electoral.csv registerCsvFile call; got ${JSON.stringify(csvFilesRegistered)}`,
    ).toBe(true);

    // D-04: the fact table MUST NOT be registered by the catalogue loader.
    expect(tableRegistered).not.toContain("elections.election_results");
    expect(csvAsTableRegistered).not.toContain("elections.election_results");
  });

  it("invokes fetchElectionEvents for election-period enumeration (NOT a SQL scan)", async () => {
    primeQueries();
    await loadSemanticCatalogue();

    expect(fetchElectionEventsMock).toHaveBeenCalledTimes(1);
    // The election-periods SQL is GONE post-cutover; only the 3 SQL
    // queries (sources, parties, electoral states) hit query().
    expect(queryMock).toHaveBeenCalledTimes(3);
  });

  it("caches the catalogue across calls", async () => {
    primeQueries();
    const first = await loadSemanticCatalogue();
    const second = await loadSemanticCatalogue();
    expect(second).toBe(first);
    // Only 3 query() calls happened (sources, parties, electoral states)
    // + 1 fetchElectionEvents.
    expect(queryMock).toHaveBeenCalledTimes(3);
    expect(fetchElectionEventsMock).toHaveBeenCalledTimes(1);
  });

  it("clears cache on failure so the next call can retry", async () => {
    queryMock.mockRejectedValueOnce(new Error("boom"));
    await expect(loadSemanticCatalogue()).rejects.toThrow("boom");
    // Next call should re-attempt — prime fresh mocks.
    primeQueries();
    const cat = await loadSemanticCatalogue();
    expect(cat.states[0]!.partition_id).toBe("tamil-nadu");
  });
});
