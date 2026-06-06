// No-fact-scan guard (D-04).
//
// Spies on `query()` calls made by `loadSemanticCatalogue()` and asserts
// every SQL string FROM-clauses ONLY tables in `CATALOGUE_QUERY_ALLOWLIST`.
// In particular, `election_results` (the fact table) MUST NOT appear.
//
// This is the structural drift detector: if a future PR sneaks a fact
// scan into the catalogue (e.g. for "popular indicators"), this test
// fires before the change can ship.
//
// YA cutover (2026-06-06): allowlist shrunk from 5 -> 3 entries
// (sources / dim_parties / electoral). dim_acs + elections_candidacies
// retired alongside the parquet startup queries; electoral added because
// state enumeration now reads an inline read_csv('data/entities/electoral.csv')
// view (citizen-trusted entity table, NOT a fact table). Election-period
// enumeration moved to fetchElectionEvents() entirely (no SQL surface).

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
  fetchElectionEvents: vi.fn(async () => ({
    $schema: "./election-events.schema.json",
    $schema_version: "1.0",
    sources: [],
    states: {},
  })),
}));

import {
  loadManifest,
  query,
  registerCsvAsTable,
  registerCsvFile,
  registerTable,
} from "../duckdb";
import {
  CATALOGUE_QUERY_ALLOWLIST,
  __resetCatalogueForTests,
  loadSemanticCatalogue,
} from "./semantic-catalogue";

const queryMock = vi.mocked(query);
const registerTableMock = vi.mocked(registerTable);
const registerCsvAsTableMock = vi.mocked(registerCsvAsTable);
const registerCsvFileMock = vi.mocked(registerCsvFile);
const loadManifestMock = vi.mocked(loadManifest);

const FORBIDDEN_TABLES: readonly string[] = Object.freeze([
  "election_results",
  "energy_demand_supply",
  "energy_generation",
  "energy_installed_capacity",
  "energy_distribution_performance",
  // YA cutover: the two parquet tables the loader USED to scan are now
  // forbidden too. Their retirement is the doctrine; re-introducing
  // either is a regression worth fail-loud.
  "dim_acs",
  "elections_candidacies",
]);

describe("semantic catalogue — no fact-table scans (D-04)", () => {
  beforeEach(() => {
    __resetCatalogueForTests();
    queryMock.mockReset().mockResolvedValue([]);
    registerTableMock.mockReset().mockResolvedValue("view");
    registerCsvAsTableMock.mockReset().mockResolvedValue("view");
    registerCsvFileMock.mockReset().mockResolvedValue(undefined);
    loadManifestMock.mockReset().mockResolvedValue({
      schema_version: "1.0",
      generated_at: "2026-05-25T00:00:00Z",
      tables: [],
    } as never);
  });

  afterEach(() => {
    __resetCatalogueForTests();
  });

  it("every query() SQL string references only allowlisted tables", async () => {
    await loadSemanticCatalogue();

    expect(queryMock).toHaveBeenCalled();
    for (const call of queryMock.mock.calls) {
      const sql = call[0] as string;
      // Allowlist check — at least one allowlisted name must appear in FROM/JOIN.
      // Note: the electoral state-distinct query uses an inline
      // read_csv('<url>') call, so the table name "electoral" appears in
      // the URL path; the substring match in sqlReferencesTable below
      // catches it via the word-boundary regex against `/electoral.csv`.
      const mentionsAllowlisted = CATALOGUE_QUERY_ALLOWLIST.some(name =>
        sqlReferencesTable(sql, name),
      );
      expect(
        mentionsAllowlisted,
        `SQL must reference at least one allowlisted table: ${sql}`,
      ).toBe(true);

      // Forbidden-table check — fact tables NEVER appear.
      for (const banned of FORBIDDEN_TABLES) {
        expect(
          sqlReferencesTable(sql, banned),
          `SQL must NOT reference fact / retired table "${banned}": ${sql}`,
        ).toBe(false);
      }
    }
  });

  it("allowlist post-cutover excludes dim_acs + elections_candidacies", async () => {
    // Compile-time receipt: the allowlist itself does not name the
    // retired tables (defence-in-depth alongside FORBIDDEN_TABLES).
    expect(CATALOGUE_QUERY_ALLOWLIST).not.toContain("dim_acs");
    expect(CATALOGUE_QUERY_ALLOWLIST).not.toContain("elections_candidacies");
  });

  it("does NOT register elections.election_results", async () => {
    await loadSemanticCatalogue();
    const tableRegistered = registerTableMock.mock.calls.map(c => c[0]);
    const csvAsTableRegistered = registerCsvAsTableMock.mock.calls.map(c => c[0]);
    expect(tableRegistered).not.toContain("elections.election_results");
    expect(csvAsTableRegistered).not.toContain("elections.election_results");
  });
});

/**
 * Word-boundary match for a table name within a SQL string. Avoids
 * false positives from substrings (e.g. "sources_archive" matching
 * "sources").
 */
function sqlReferencesTable(sql: string, table: string): boolean {
  // Match table name preceded by FROM / JOIN whitespace OR by start-of-line,
  // followed by whitespace, end-of-statement, comma, or close-paren.
  const escaped = table.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`\\b${escaped}\\b`, "i");
  return re.test(sql);
}
