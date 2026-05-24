// SemanticCatalogue loader tests.
//
// The catalogue depends on DuckDB-WASM at runtime; per CLAUDE.md §15 the
// `lib/duckdb` module is a legitimate test seam (the loader's contract IS
// the fetch boundary). Mocks here mirror the pattern in
// `lib/psephlab/canonical-loaders.test.ts` (`vi.mock("../duckdb", ...)`).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  query: vi.fn(),
  registerSlice: vi.fn(),
  registerTable: vi.fn().mockResolvedValue("view"),
  loadManifest: vi.fn(),
}));

import {
  loadManifest,
  query,
  registerTable,
} from "../duckdb";
import {
  __resetCatalogueForTests,
  loadSemanticCatalogue,
} from "./semantic-catalogue";

const queryMock = vi.mocked(query);
const registerTableMock = vi.mocked(registerTable);
const loadManifestMock = vi.mocked(loadManifest);

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
const FAKE_PERIODS = [{ period_label: "AcGenMay2026", state_code: "S22" }];
const FAKE_STATES = [{ state_code: "S22" }];

function primeQueries(): void {
  // Order matches the Promise.all in buildCatalogue: sources, parties,
  // election-periods. The DISTINCT-states query is awaited separately
  // (4th mock return).
  queryMock
    .mockResolvedValueOnce(FAKE_SOURCES)
    .mockResolvedValueOnce(FAKE_PARTIES)
    .mockResolvedValueOnce(FAKE_PERIODS)
    .mockResolvedValueOnce(FAKE_STATES);
}

describe("loadSemanticCatalogue", () => {
  beforeEach(() => {
    __resetCatalogueForTests();
    queryMock.mockReset();
    registerTableMock.mockReset().mockResolvedValue("view");
    loadManifestMock.mockReset().mockResolvedValue(FAKE_MANIFEST as never);
  });

  afterEach(() => {
    __resetCatalogueForTests();
  });

  it("assembles a catalogue from manifest + dim queries", async () => {
    primeQueries();
    const cat = await loadSemanticCatalogue();

    expect(cat.states).toHaveLength(1);
    expect(cat.states[0]!.partition_id).toBe("in_s22");
    expect(cat.states[0]!.eci_code).toBe("S22");

    expect(cat.parties.map(p => p.short_code)).toEqual(["DMK", "AIADMK"]);
    expect(cat.sources[0]!.producer).toBe("ECI");
    expect(cat.election_periods[0]!.period_label).toBe("AcGenMay2026");
    expect(cat.election_periods[0]!.state_partition_id).toBe("in_s22");
    expect(cat.tables.map(t => t.table_id)).toContain("elections.election_results");
  });

  it("registers the 4 dim/taxonomy tables (NOT election_results)", async () => {
    primeQueries();
    await loadSemanticCatalogue();

    const registered = registerTableMock.mock.calls.map(c => c[0]);
    expect(registered).toContain("taxonomy.sources");
    expect(registered).toContain("elections.dim_acs");
    expect(registered).toContain("elections.dim_parties");
    expect(registered).toContain("elections.elections_candidacies");
    // D-04: the fact table MUST NOT be registered by the catalogue loader.
    expect(registered).not.toContain("elections.election_results");
  });

  it("caches the catalogue across calls", async () => {
    primeQueries();
    const first = await loadSemanticCatalogue();
    const second = await loadSemanticCatalogue();
    expect(second).toBe(first);
    // Only 4 query() calls happened (sources, parties, periods, states).
    expect(queryMock).toHaveBeenCalledTimes(4);
  });

  it("clears cache on failure so the next call can retry", async () => {
    queryMock.mockRejectedValueOnce(new Error("boom"));
    await expect(loadSemanticCatalogue()).rejects.toThrow("boom");
    // Next call should re-attempt — prime fresh mocks.
    primeQueries();
    const cat = await loadSemanticCatalogue();
    expect(cat.states[0]!.partition_id).toBe("in_s22");
  });
});
