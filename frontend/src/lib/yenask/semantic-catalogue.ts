// Semantic catalogue loader - derives the lab's vocabulary from the
// canonical CSV taxonomy + the hand-curated election-events catalogue.
//
// Per plan-doc section 17 D-04: this module MUST NOT scan any fact
// table. The allowlist (`CATALOGUE_QUERY_ALLOWLIST`) is exported so the
// no-fact-scan vitest can assert every SQL string starts with a regex
// match against it. Adding a new source for the catalogue = update the
// allowlist + ship a new test case.
//
// YA cutover (2026-06-06) per parent plan section 22.5 YA row + Andre
// deviation: the previous startup queries SQL_DISTINCT_STATES + SQL_-
// ELECTION_PERIODS scanned `dim_acs` + `elections_candidacies` parquet.
// They are replaced by:
//   - inline `read_csv('datasets/data/entities/electoral.csv',
//     columns={...}) WHERE entity_kind='ac'` for state enumeration.
//   - `fetchElectionEvents()` (the existing
//     `frontend/src/lib/election-events.ts` helper reading
//     `datasets/taxonomy/election_events.json`) for election-period
//     enumeration. This is the citizen-trusted hand-curated catalogue
//     of which elections happened where; sourcing election periods from
//     the catalogue rather than from a fact-table aggregate honours
//     D-04 (the catalogue IS the catalogue; no fact-scan) more cleanly
//     than the literal "UNION ALL of N candidacies.csv URLs"
//     interpretation in the plan-doc.
//
// The catalogue is built once per page load (cached via module-level
// promise). Subsequent loads short-circuit.

import { csvColumnsClause } from "../canonical/csv-columns";
import { fetchElectionEvents } from "../election-events";
import {
  loadManifest,
  query,
  registerCsvAsTable,
  registerCsvFile,
  type Manifest,
} from "../duckdb";
import { ECI_TO_LGD_SLUG } from "../maplibre/sources";
import { DATA_BASE } from "../paths";
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
 *
 * YA cutover (2026-06-06): `dim_acs` + `elections_candidacies` removed -
 * state + election-period enumeration moved to CSV (`electoral.csv`) +
 * the `fetchElectionEvents()` JSON helper respectively, neither of which
 * is a SQL-allowlisted view (the JSON helper bypasses SQL entirely; the
 * inline `read_csv(...)` on `electoral.csv` reads a citizen-trusted
 * entity table, not a fact table). The remaining 3 entries cover the
 * SQL surface only.
 */
export const CATALOGUE_QUERY_ALLOWLIST: readonly string[] = Object.freeze([
  "sources",
  "dim_parties",
  "electoral",
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

  // Register the 2 X1a-flipped CSV-as-table views the catalogue queries
  // reference. election_results is INTENTIONALLY not registered here
  // (D-04). dim_acs + elections_candidacies parquet reads RETIRED in
  // the YA cutover - state + election-period enumeration now come from
  // electoral.csv (inline read_csv) + fetchElectionEvents() respectively.
  const electoralCsvRel = "data/entities/electoral.csv";
  const electoralCsvUrl = `${DATA_BASE}/${electoralCsvRel}`;
  await Promise.all([
    registerCsvAsTable("taxonomy.sources"),
    registerCsvAsTable("elections.dim_parties"),
    registerCsvFile(electoralCsvUrl),
  ]);

  const tables = manifestToCatalogueTables(manifest);

  // electoral.csv has 4113 rows (ac + pc); the catalogue surface is
  // assembly states, so filter to entity_kind='ac' and take DISTINCT
  // state slug. Typed via csvColumnsClause so the F1.3a contract
  // (every read_csv carries an explicit columns={...} map) is honoured.
  const electoralColumns = await csvColumnsClause(
    `datasets/${electoralCsvRel}`,
  );
  const sqlDistinctStates = `
    SELECT DISTINCT state AS state_slug
    FROM read_csv('${electoralCsvUrl}', ${electoralColumns})
    WHERE entity_kind = 'ac'
    ORDER BY state_slug
  `;

  const [sources, parties, stateSlugRows, electionEvents] = await Promise.all([
    query<CatalogueSourceRow>(SQL_SOURCES),
    query<CatalogueParty>(SQL_PARTIES),
    query<{ state_slug: string }>(sqlDistinctStates),
    fetchElectionEvents(),
  ]);

  // Invert ECI_TO_LGD_SLUG once so each state slug can resolve back to
  // its ECI code (S22, U05, ...). States missing from the mapping fall
  // back to the slug itself uppercased (defensive; today every slug in
  // electoral.csv has an ECI mapping).
  const slugToEci = invertEciSlugMap(ECI_TO_LGD_SLUG);
  const states: CatalogueState[] = stateSlugRows.map(r => ({
    partition_id: r.state_slug,
    eci_code: slugToEci[r.state_slug] ?? r.state_slug.toUpperCase(),
    display_name: r.state_slug, // renderer enriches via states.svelte
  }));

  // Flatten the per-state election-events catalogue into per-period
  // entries the lab compiler can address. The slug stays in sync with
  // electoral.csv via ECI_TO_LGD_SLUG so a catalogue period and its
  // matching state share the same partition_id.
  const electionPeriods: CatalogueElectionPeriod[] = [];
  for (const [eciCode, rows] of Object.entries(electionEvents.states)) {
    const slug = ECI_TO_LGD_SLUG[eciCode] ?? eciCode.toLowerCase();
    for (const row of rows) {
      electionPeriods.push({
        period_label: row.event_id,
        display_name: row.display,
        state_partition_id: slug,
      });
    }
  }

  return {
    tables,
    states,
    election_periods: electionPeriods,
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

// ---------- SQL composition ------------------------------------------------
//
// Every SQL query below references ONLY tables in
// CATALOGUE_QUERY_ALLOWLIST. The no-fact-scan vitest spies on `query()`
// and asserts the SQL strings honour that boundary. fetchElectionEvents
// is not a SQL surface (it fetches taxonomy/election_events.json over
// plain HTTP) and so is exempt from the allowlist.

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

function invertEciSlugMap(
  map: Readonly<Record<string, string>>,
): Readonly<Record<string, string>> {
  const inverted: Record<string, string> = {};
  for (const [eci, slug] of Object.entries(map)) {
    inverted[slug] = eci;
  }
  return Object.freeze(inverted);
}

function manifestToCatalogueTables(m: Manifest): CatalogueTable[] {
  return m.tables.map(t => ({
    table_id: t.table_id,
    family: t.family,
    kind: t.kind ?? "other",
    partition_columns: t.partition_columns,
  }));
}
