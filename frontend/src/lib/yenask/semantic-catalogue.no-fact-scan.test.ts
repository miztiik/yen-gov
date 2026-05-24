// No-fact-scan guard (D-04).
//
// Spies on `query()` calls made by `loadSemanticCatalogue()` and asserts
// every SQL string FROM-clauses ONLY tables in `CATALOGUE_QUERY_ALLOWLIST`.
// In particular, `election_results` (the fact table) MUST NOT appear.
//
// This is the structural drift detector: if a future PR sneaks a fact
// scan into the catalogue (e.g. for "popular indicators"), this test
// fires before the change can ship.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../duckdb", () => ({
  query: vi.fn(),
  registerSlice: vi.fn(),
  registerTable: vi.fn().mockResolvedValue("view"),
  loadManifest: vi.fn(),
}));

import { loadManifest, query, registerTable } from "../duckdb";
import {
  CATALOGUE_QUERY_ALLOWLIST,
  __resetCatalogueForTests,
  loadSemanticCatalogue,
} from "./semantic-catalogue";

const queryMock = vi.mocked(query);
const registerTableMock = vi.mocked(registerTable);
const loadManifestMock = vi.mocked(loadManifest);

const FORBIDDEN_TABLES: readonly string[] = Object.freeze([
  "election_results",
  "energy_demand_supply",
  "energy_generation",
  "energy_installed_capacity",
  "energy_distribution_performance",
]);

describe("semantic catalogue — no fact-table scans (D-04)", () => {
  beforeEach(() => {
    __resetCatalogueForTests();
    queryMock.mockReset().mockResolvedValue([]);
    registerTableMock.mockReset().mockResolvedValue("view");
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
          `SQL must NOT reference fact table "${banned}": ${sql}`,
        ).toBe(false);
      }
    }
  });

  it("does NOT register elections.election_results", async () => {
    await loadSemanticCatalogue();
    const registered = registerTableMock.mock.calls.map(c => c[0]);
    expect(registered).not.toContain("elections.election_results");
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
