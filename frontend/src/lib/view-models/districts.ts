// Districts view-model loader (Phase-0 closeout T.0c-ii-B.2).
//
// Reads the canonical Parquet store via DuckDB-WASM (see lib/duckdb.ts)
// to project the per-state district list — the legacy 3-letter district
// code (e.g. "TAL", "CHN") + citizen-readable name — that StateOverview
// uses to group constituencies under their parent district.
//
// What is read:
//   taxonomy.entities — country/state/UT/district dimension. District rows
//     carry `parent_entity_id = 'IN-<state>'`, `entity_type = 'district'`,
//     `legacy_id` = the Wikipedia/ECI 3-letter code that
//     `constituencies.json#/constituencies[].district_id` joins on, and
//     `display_name` = the citizen-readable name.
//
// Why a separate loader (not added to lib/data.ts):
//   PR-E / PR-F / PR-G / PR-H established that any consumer reading the
//   canonical Parquet store via DuckDB-WASM lives under `view-models/`.
//   `lib/data.ts` is the legacy JSON-fetch surface; the Phase-0 closeout
//   sweep ports each remaining JSON consumer to a view-model and retires
//   the legacy fetcher.
//
// Return shape — minimal: `{id, name}[]`. The legacy `DistrictEntry`
// interface declared 5 extra fields (`id_source`, `headquarters`,
// `created_on`, `split_from`, `notes`) but no consumer reads them; this
// loader drops them to keep the surface honest about what's actually
// queryable from the canonical store.

import { query, registerTable } from "../duckdb";

export interface District {
  /** Wikipedia/ECI 3-letter code — joins on constituencies[].district_id. */
  id: string;
  /** Citizen-readable district name. */
  name: string;
}

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

interface DistrictRow {
  id: string | null;
  name: string | null;
}

/**
 * Load the district list for a state (e.g. "S22") from the canonical
 * `taxonomy.entities` table. Returns rows ordered by display name.
 *
 * Throws on DuckDB-WASM / manifest / SQL failure — the caller is expected
 * to wrap in `.catch(() => null)` if a missing district list should
 * fall through to the existing "(unmapped)" rendering path (which is
 * exactly what StateOverview.svelte does).
 */
export async function loadDistricts(state: string): Promise<District[]> {
  await registerTable("taxonomy.entities");
  const parent = sqlString(`IN-${state}`);
  const sql = `
    SELECT legacy_id   AS id,
           display_name AS name
    FROM entities
    WHERE entity_type = 'district'
      AND parent_entity_id = ${parent}
      AND legacy_id IS NOT NULL
    ORDER BY display_name
  `;
  const rows = await query<DistrictRow>(sql);
  return rows
    .filter((r) => r.id != null && r.name != null)
    .map((r) => ({ id: r.id as string, name: r.name as string }));
}
