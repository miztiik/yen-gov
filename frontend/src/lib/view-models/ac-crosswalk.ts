// AC crosswalk loader — per-state `eci_no -> lgd_ac_id` map (Row B2, ADR-0049).
//
// The eci_no <-> LGD AC code binding lives in the canonical AC crosswalk
// CSV (harvested in PR-A2 from the boundary AC_ID property). This loader
// reads the covered subset for one state so the AC choropleth can resolve
// boundary features on the canonical `lgd_ac_id` while the citizen-facing
// eci_no stays the display/URL label.
//
// X1a-followup flip (2026-06-06): switched from
// `registerTable("taxonomy.ac_crosswalk")` (parquet) to a typed
// `read_csv('datasets/data/entities/ac_crosswalk.csv', columns={...})`
// against the canonical CSV per parent plan section 21.3. The on-disk
// shape changed at the same time: the parquet's `state_code` (ECI form
// like "S22") is now the slug-form `state_entity_id` (e.g. "tamil-nadu");
// translate via `electionStatePartition(state)` at the WHERE clause.
//
// Why a separate loader (not a column on the AcWinner query): the
// election view-model query is owned by another in-flight surface; the
// crosswalk is the Canonical Data Model "Message Translator" the
// migration plan calls for, so the join is resolved here from the
// shared crosswalk table rather than by widening the winners query.
// lgd_ac_id is INTERNAL-ONLY and never reaches a URL.
//
// What is read:
//   datasets/data/entities/ac_crosswalk.csv -
//     (state_entity_id, delim_year, eci_no, lgd_ac_id, ...). Rows whose
//     `lgd_ac_id` is NULL (uncovered states like S03/Assam, U08/J&K)
//     are skipped, so those states fall through to the eci_no/ac_no
//     join.

import { query, registerCsvFile } from "../duckdb";
import { electionStatePartition } from "../election-partitions";
import { DATA_BASE } from "../paths";
import { csvColumnsClause } from "../canonical/csv-columns";

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

interface CrosswalkRow {
  eci_no: number | null;
  lgd_ac_id: number | null;
}

const AC_CROSSWALK_CSV_PATH = "datasets/data/entities/ac_crosswalk.csv";

/**
 * Load the `eci_no -> lgd_ac_id` lookup for one state (e.g. "S22") from
 * the canonical `ac_crosswalk.csv` file. Only mapped rows
 * (`lgd_ac_id IS NOT NULL`) are returned, so an uncovered state yields
 * an empty map and the choropleth keeps its eci_no/ac_no join.
 *
 * Throws on DuckDB-WASM / fetch / SQL failure — callers wrap in
 * `.catch(() => null)` so a missing crosswalk degrades to the legacy join
 * rather than blanking the map.
 */
export async function loadAcLgdLookup(state: string): Promise<Map<number, number>> {
  const url = `${DATA_BASE}/${AC_CROSSWALK_CSV_PATH.replace(/^datasets\//, "")}`;
  const [clause] = await Promise.all([
    csvColumnsClause(AC_CROSSWALK_CSV_PATH),
    registerCsvFile(url),
  ]);
  const slug = sqlString(electionStatePartition(state));
  const sql = `
    SELECT eci_no, lgd_ac_id
    FROM read_csv('${url}', ${clause})
    WHERE state_entity_id = ${slug}
      AND eci_no IS NOT NULL
      AND lgd_ac_id IS NOT NULL
  `;
  const rows = await query<CrosswalkRow>(sql);
  const out = new Map<number, number>();
  for (const r of rows) {
    if (r.eci_no != null && r.lgd_ac_id != null) {
      out.set(Number(r.eci_no), Number(r.lgd_ac_id));
    }
  }
  return out;
}
