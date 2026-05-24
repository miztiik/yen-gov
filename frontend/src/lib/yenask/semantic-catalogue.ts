// Semantic catalogue loader — derives the lab's vocabulary from the
// canonical manifest + taxonomy/dim Parquets at startup.
//
// Per plan-doc §17 D-04: this module MUST NOT scan any fact table. The
// allowlist (`CATALOGUE_QUERY_ALLOWLIST`) is exported so the no-fact-scan
// vitest can assert every SQL string starts with a regex match against it.
// Adding a new source for the catalogue = update the allowlist + ship a
// new test case.
//
// The catalogue is built once per page load (cached via module-level
// promise). Subsequent loads short-circuit.

import {
  loadManifest,
  query,
  registerTable,
  type Manifest,
} from "../duckdb";
import type {
  CatalogueElectionPeriod,
  CatalogueParty,
  CatalogueSource,
  CatalogueState,
  CatalogueTable,
  SemanticCatalogue,
} from "./types";

/**
 * Allowlist of table names that catalogue queries may FROM. Used by the
 * no-fact-scan test to fail if the catalogue ever tries to scan a fact
 * table. Add new entries only with a paired vitest case proving the new
 * query stays inside the catalogue contract (per D-04).
 */
export const CATALOGUE_QUERY_ALLOWLIST: readonly string[] = Object.freeze([
  "sources",
  "dim_acs",
  "dim_parties",
  "elections_candidacies",
  "entities",
]);

let cached: Promise<SemanticCatalogue> | null = null;

/**
 * Load (or return cached) semantic catalogue. Safe to call from anywhere
 * in the lab; the first call boots DuckDB-WASM via the underlying
 * `lib/duckdb.ts` singleton.
 */
export function loadSemanticCatalogue(): Promise<SemanticCatalogue> {
  if (cached) return cached;
  cached = buildCatalogue();
  cached.catch(() => {
    cached = null;
  });
  return cached;
}

/**
 * Test-only reset hook. NOT for production use.
 */
export function __resetCatalogueForTests(): void {
  cached = null;
}

async function buildCatalogue(): Promise<SemanticCatalogue> {
  const manifest = await loadManifest();

  // Register the 4 dim/taxonomy views the catalogue queries reference.
  // election_results is INTENTIONALLY not registered here — D-04.
  await Promise.all([
    registerTable("taxonomy.sources"),
    registerTable("elections.dim_acs"),
    registerTable("elections.dim_parties"),
    registerTable("elections.elections_candidacies"),
  ]);

  const tables = manifestToCatalogueTables(manifest);
  const [sources, parties, electionPeriods] = await Promise.all([
    query<CatalogueSourceRow>(SQL_SOURCES),
    query<CatalogueParty>(SQL_PARTIES),
    query<CatalogueElectionPeriodRow>(SQL_ELECTION_PERIODS),
  ]);

  // States derived from dim_acs DISTINCT state_code — only states with
  // election data appear here. Display name is fetched from
  // taxonomy/entities.json via `lib/states.svelte` lazily; for the
  // catalogue we keep the eci_code raw and let the renderer humanise.
  const stateCodes = await query<{ state_code: string }>(SQL_DISTINCT_STATES);
  const states: CatalogueState[] = stateCodes.map(r => ({
    partition_id: `in_${r.state_code.toLowerCase()}`,
    eci_code: r.state_code,
    display_name: r.state_code, // renderer enriches via states.svelte
  }));

  return {
    tables,
    states,
    election_periods: electionPeriods.map(r => ({
      period_label: String(r.period_label),
      display_name: String(r.period_label),
      state_partition_id: `in_${String(r.state_code).toLowerCase()}`,
    })),
    parties: parties.map(p => ({
      short_code: String(p.short_code),
      display_name: String(p.display_name ?? p.short_code),
    })),
    sources: sources.map(s => ({
      source_id: String(s.source_id),
      producer: String(s.producer),
      title: String(s.title),
      vintage: String(s.vintage ?? ""),
    })),
    manifest,
  };
}

interface CatalogueSourceRow {
  source_id: string;
  producer: string;
  title: string;
  vintage: string | null;
}

interface CatalogueElectionPeriodRow {
  period_label: string;
  state_code: string;
}

// ---------- SQL composition ------------------------------------------------
//
// Every query below references ONLY tables in CATALOGUE_QUERY_ALLOWLIST.
// The no-fact-scan vitest spies on `query()` and asserts the SQL strings
// honour that boundary.

const SQL_SOURCES = `
  SELECT source_id, producer, title, vintage
  FROM sources
  ORDER BY producer, title
`;

const SQL_PARTIES = `
  SELECT
    short_name AS short_code,
    full_name  AS display_name
  FROM dim_parties
  WHERE short_name IS NOT NULL
  ORDER BY short_name
`;

const SQL_ELECTION_PERIODS = `
  SELECT DISTINCT
    election_id  AS period_label,
    da.state_code
  FROM elections_candidacies ec
  JOIN dim_acs da ON da.ac_id = ec.ac_id
  ORDER BY period_label, da.state_code
`;

const SQL_DISTINCT_STATES = `
  SELECT DISTINCT state_code
  FROM dim_acs
  WHERE state_code IS NOT NULL
  ORDER BY state_code
`;

function manifestToCatalogueTables(m: Manifest): CatalogueTable[] {
  return m.tables.map(t => ({
    table_id: t.table_id,
    family: t.family,
    kind: t.kind ?? "other",
    partition_columns: t.partition_columns,
  }));
}
