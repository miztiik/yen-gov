// Per-state election-results CSV reader helpers (X1a-fu2-D).
//
// The 36 datasets/elections/state=<slug>/election_results.parquet shards
// were retired on 2026-06-07 (mechanical rip per user directive). Their
// content now lives at
//   datasets/data/datapoints/electoral/<slug>_election_results.csv
// (one CSV per state, 9 columns, ~1.8M rows total). Frontend reads via
// inline DuckDB-WASM read_csv with a HAND-AUTHORED columns={...} clause -
// the shared csvColumnsClause helper only supports the =* Hive partition
// glob, not the *.csv glob this file_class uses, so we splice the clause
// literal in here rather than going through csvColumnsClause.
//
// Consumed by 3 readers (composition-bar/adapter-elections-seats.ts,
// view-models/election-seats-trend.ts, view-models/india-leading-parties.ts).
// All other consumers of the legacy elections.election_results parquet
// were either deleted in X1b or never existed (see preamble of the parent
// X1a-fu2 plan-doc).

import { DATA_BASE } from "../paths";
import { ECI_TO_LGD_SLUG } from "../boundaries/sources";

/** Inline columns clause for read_csv. 9 columns mirroring the 9-column
 *  emission shape declared in
 *  datasets/data/_schema/columns.json:datapoints/electoral/*.csv.
 *
 *  Consumers MUST splice this together with `header=true, auto_detect=false`
 *  (e.g. `read_csv(<url>, ${ELECTION_RESULTS_COLUMNS_CLAUSE}, header=true,
 *  auto_detect=false)`). These reads are a fully-typed boundary - the
 *  column shape and header are already declared here - so the DuckDB CSV
 *  sniffer has nothing left to discover and must stay out of the path.
 *  DuckDB-WASM's sniffer (1.33-dev) mis-detects the delimiter on the
 *  smaller, hyphen-dense parliament-only shards (lakshadweep: first rows
 *  are `IN-PC-...` candidate ids with an empty value_text), throwing
 *  `CSV sniffer: 1 column, expected 9` and failing the whole bulk home-map
 *  query. `auto_detect=false` pins the comma dialect and removes the
 *  sniffer entirely. Verified row-count-identical to the sniffer path
 *  across all 36 state shards. */
export const ELECTION_RESULTS_COLUMNS_CLAUSE =
  "columns={" +
  "'entity_id': 'VARCHAR', " +
  "'year': 'INTEGER', " +
  "'period_label': 'VARCHAR', " +
  "'period_seq': 'INTEGER', " +
  "'indicator_id': 'VARCHAR', " +
  "'value_numeric': 'DOUBLE', " +
  "'value_text': 'VARCHAR', " +
  "'source_id': 'VARCHAR', " +
  "'derivation': 'VARCHAR'" +
  "}";

/** Repo-relative CSV path for one state. */
export function electionResultsCsvPath(state_slug: string): string {
  return `datasets/data/datapoints/electoral/${state_slug}_election_results.csv`;
}

/** Absolute URL (Vite middleware in dev, Pages in prod). */
export function electionResultsCsvUrl(state_slug: string): string {
  return `${DATA_BASE}/data/datapoints/electoral/${state_slug}_election_results.csv`;
}

/** Resolve ECI state code -> on-disk LGD slug for the per-state CSV
 *  filename. Mirrors lib/election-partitions.ts:electionStatePartition;
 *  re-exported here so the 3 readers do not need to import from two
 *  places. */
export function electionResultsStateSlug(state_code: string): string {
  return ECI_TO_LGD_SLUG[state_code] ?? state_code.toLowerCase();
}

/** All 36 LGD slugs that have an election_results CSV on disk. Sourced
 *  from ECI_TO_LGD_SLUG values; the india-leading-parties loader unions
 *  across the subset of these named in its bulk state_event_map. */
export const ALL_ELECTION_RESULTS_STATE_SLUGS: readonly string[] = (() => {
  const seen = new Set<string>();
  for (const slug of Object.values(ECI_TO_LGD_SLUG)) seen.add(slug);
  return Array.from(seen).sort();
})();
