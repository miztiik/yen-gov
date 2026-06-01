// AC crosswalk loader — per-state `eci_no -> lgd_ac_id` map (Row B2, ADR-0049).
//
// The eci_no <-> LGD AC code binding lives in the canonical
// `taxonomy.ac_crosswalk` Parquet (harvested in PR-A2 from the boundary
// AC_ID property). This loader reads the covered subset for one state so the
// AC choropleth can resolve boundary features on the canonical `lgd_ac_id`
// while the citizen-facing eci_no stays the display/URL label.
//
// Why a separate loader (not a column on the AcWinner query): the election
// view-model query is owned by another in-flight surface; the crosswalk is
// the Canonical Data Model "Message Translator" the migration plan calls for,
// so the join is resolved here from the shared crosswalk table rather than by
// widening the winners query. lgd_ac_id is INTERNAL-ONLY and never reaches a
// URL.
//
// What is read:
//   taxonomy.ac_crosswalk — (state_code, eci_no, lgd_ac_id, ...). Rows whose
//     `lgd_ac_id` is NULL (uncovered states like S03/Assam, U08/J&K) are
//     skipped, so those states fall through to the eci_no/ac_no join.

import { query, registerTable } from "../duckdb";

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

interface CrosswalkRow {
  eci_no: number | null;
  lgd_ac_id: number | null;
}

/**
 * Load the `eci_no -> lgd_ac_id` lookup for one state (e.g. "S22") from the
 * canonical `taxonomy.ac_crosswalk` table. Only mapped rows
 * (`lgd_ac_id IS NOT NULL`) are returned, so an uncovered state yields an
 * empty map and the choropleth keeps its eci_no/ac_no join.
 *
 * Throws on DuckDB-WASM / manifest / SQL failure — callers wrap in
 * `.catch(() => null)` so a missing crosswalk degrades to the legacy join
 * rather than blanking the map.
 */
export async function loadAcLgdLookup(state: string): Promise<Map<number, number>> {
  await registerTable("taxonomy.ac_crosswalk");
  const sc = sqlString(state);
  const sql = `
    SELECT eci_no, lgd_ac_id
    FROM ac_crosswalk
    WHERE state_code = ${sc}
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
