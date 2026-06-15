// DuckDB-WASM loader for `datasets/elections/parliament/election=*/mcc_seizures.csv`.
//
// Consumed by ElectionSeizuresCard.svelte. Returns rows shaped per
// `SeizuresRow` in election-seizures-model.ts. Cached per event_id
// because the source file is small (~360 rows for the 2019 vintage)
// and the data does not change within a session.
//
// Schema-of-schemas wiring: the typed columns clause is fetched from
// `datasets/data/_schema/columns.json` via `csvColumnsClause(...)` so
// the read NEVER sniffs (per CLAUDE.md Holy Law #3 + the F1.3a seam).

import { query, registerCsvFile } from "../duckdb";
import { DATA_BASE } from "../paths";
import { csvColumnsClause } from "../canonical/csv-columns";
import type { SeizuresRow } from "./election-seizures-model";

const CACHE = new Map<string, Promise<readonly SeizuresRow[]>>();

/** Path-builder. Kept as a pure helper so the test file can assert
 *  the exact URL shape without going through DuckDB-WASM. */
export function seizuresCsvPath(event_id: string): string {
  // event_id shape: `general-2019` -> election=2019. We extract the
  // trailing year token; future events would carry the same shape.
  const m = event_id.match(/-(\d{4})$/);
  if (!m) throw new Error(`seizuresCsvPath: cannot parse year from ${event_id}`);
  const year = m[1];
  return `datasets/elections/parliament/election=${year}/mcc_seizures.csv`;
}

/** Load the MCC-period seizures rows for one LS general election.
 *  Cached per event_id. Throws on fetch / SQL failure; callers that
 *  need a graceful no-data state should catch and fall through to
 *  an empty render. */
export async function loadSeizures(
  event_id: string,
): Promise<readonly SeizuresRow[]> {
  const cached = CACHE.get(event_id);
  if (cached) return cached;
  const p = loadSeizuresUncached(event_id);
  CACHE.set(event_id, p);
  p.catch(() => CACHE.delete(event_id));
  return p;
}

async function loadSeizuresUncached(
  event_id: string,
): Promise<readonly SeizuresRow[]> {
  const csvPath = seizuresCsvPath(event_id);
  const url = `${DATA_BASE}/${csvPath.replace(/^datasets\//, "")}`;
  const [clause] = await Promise.all([
    csvColumnsClause(csvPath),
    registerCsvFile(url),
  ]);
  const sql = `
    SELECT
      state_slug,
      date::VARCHAR AS date,
      cash_inr_crore,
      liquor_qty_lakh_litres,
      liquor_value_inr_crore,
      drugs_qty_kg,
      drugs_value_inr_crore,
      precious_metals_qty_kg,
      precious_metals_value_inr_crore,
      other_items_seizure_value_inr_crore,
      total_seizure_inr_crore,
      source_id,
      processing_level
    FROM read_csv('${url}', ${clause})
    ORDER BY state_slug, date
  `;
  const rows = await query<SeizuresRow>(sql);
  return rows;
}

/** Test-only: reset the module-level cache so each test starts fresh.
 *  NOT for production use. */
export function __resetForTests(): void {
  CACHE.clear();
}
