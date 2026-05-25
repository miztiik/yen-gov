// Districts view-model loader (Phase-0 closeout T.0c-ii-B.2 +
// PR B.05 C1 — national LGD-keyed loader for district-grain choropleth).
//
// Reads the canonical Parquet store via DuckDB-WASM (see lib/duckdb.ts).
// Two complementary projections of the same `taxonomy.entities` rows
// live here:
//
//   loadDistricts(state)         per-state, keyed on `legacy_id`
//                                (Wikipedia/ECI 3-letter code, e.g.
//                                "TAL"). Used by StateOverview to
//                                group constituencies under their
//                                parent district.
//
//   loadAllDistrictEntities()    nation-wide, keyed on `lgd_code` (MoHA
//                                numeric district code as a string).
//                                Used by IndicatorChoropleth's
//                                district branch (PR B.05) to project
//                                fills + tooltips + click drill-down
//                                against the LGD_Districts national
//                                boundary layer.
//
// The two projections deliberately do not share a row type — they
// answer different questions and citizens never see the difference.
// `legacy_id` is the constituency-grouping joinable; `lgd_code` is
// the map-polygon joinable.
//
// What is read (both projections):
//   taxonomy.entities — country/state/UT/district dimension. District
//     rows carry `parent_entity_id = 'IN-<state>'`,
//     `entity_type = 'district'`, `legacy_id` = the Wikipedia/ECI
//     3-letter code that constituencies.json#/constituencies[].district_id
//     joins on, `lgd_code` = the MoHA numeric code that the
//     LGD_Districts boundary layer carries as `dist_lgd`, and
//     `display_name` = the citizen-readable name.

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

// ----------------------------------------------------------------------
// PR B.05 C1 — nation-wide LGD-keyed district loader for choropleth
// ----------------------------------------------------------------------

/**
 * National-scope district row carrying the columns needed by the
 * district branch of IndicatorChoropleth (PR B.05): LGD-keyed
 * map-join key + parent state name for the tooltip.
 *
 * Distinct from {@link District} because it answers a different
 * question (national choropleth fill keying), reads different
 * columns from the same table, and adds a self-joined
 * `parent_state_name` field required by Jony's B.05 tooltip
 * constraint.
 */
export interface DistrictEntity {
  /** Canonical district entity_id (e.g. "IN-S22-D567"). */
  entity_id: string;
  /** Citizen-readable district name from entities.parquet (e.g. "Coimbatore"). */
  display_name: string;
  /** LGD numeric code (MoHA Local Government Directory), e.g. "567". */
  lgd_code: string;
  /**
   * Map-join key. LGD numeric code as a string. USE THIS — NOT
   * `display_name` — when keying fills / tooltips / highlight dicts
   * in the district branch of IndicatorChoropleth. Matches the
   * `dist_lgd` integer property carried in the LGD_Districts
   * national boundary layer via MapChoropleth's `keys_are_numeric`
   * + `to-number` coercion (same bridge the state-grain side uses
   * for `State_LGD`).
   */
  boundary_join_key: string;
  /** Parent state/UT canonical id (e.g. "IN-S22" for Tamil Nadu). */
  parent_entity_id: string;
  /**
   * Parent state/UT display_name (e.g. "Tamil Nadu"). Required by
   * Jony's B.05 tooltip constraint — district tooltip must render
   * district name AND parent state name so the citizen can anchor
   * the place ("Coimbatore — Tamil Nadu").
   */
  parent_state_name: string;
}

interface RawDistrictEntityRow {
  entity_id: string | null;
  display_name: string | null;
  lgd_code: string | null;
  parent_entity_id: string | null;
  parent_state_name: string | null;
}

let cachedDistrictEntities: Promise<DistrictEntity[]> | null = null;

/**
 * Load all currently-valid Indian districts from `taxonomy.entities`,
 * with each row's parent state/UT name resolved by self-join. Returns
 * 784 rows today (verified 2026-05-25; all carry `lgd_code` and a
 * resolvable `parent_entity_id`).
 *
 * Cached per page-load — the table is 784 rows and the data does not
 * change within a session. Call once near the top of a `$effect` or
 * `onMount`; downstream deriveds operate on the resolved array
 * synchronously.
 *
 * Throws on DuckDB-WASM / manifest / SQL failure. Callers that need
 * to fall through to a "render nothing yet" state should keep the
 * result in a `$state` variable initialised to `null` and check for
 * null before iterating.
 */
export async function loadAllDistrictEntities(): Promise<DistrictEntity[]> {
  if (!cachedDistrictEntities)
    cachedDistrictEntities = loadAllDistrictEntitiesUncached();
  return cachedDistrictEntities;
}

async function loadAllDistrictEntitiesUncached(): Promise<DistrictEntity[]> {
  await registerTable("taxonomy.entities");
  const sql = `
    SELECT d.entity_id,
           d.display_name,
           d.lgd_code,
           d.parent_entity_id,
           s.display_name AS parent_state_name
    FROM entities d
    LEFT JOIN entities s ON d.parent_entity_id = s.entity_id
    WHERE d.entity_type = 'district'
      AND d.entity_valid_to IS NULL
    ORDER BY d.entity_id
  `;
  const rows = await query<RawDistrictEntityRow>(sql);
  return rows
    .filter(
      (r) =>
        r.entity_id != null &&
        r.display_name != null &&
        r.lgd_code != null &&
        r.parent_entity_id != null &&
        r.parent_state_name != null,
    )
    .map((r) => {
      const lgd_code = r.lgd_code as string;
      return {
        entity_id: r.entity_id as string,
        display_name: r.display_name as string,
        lgd_code,
        boundary_join_key: lgd_code,
        parent_entity_id: r.parent_entity_id as string,
        parent_state_name: r.parent_state_name as string,
      };
    });
}

/**
 * Test-only: reset the module-level cache for {@link loadAllDistrictEntities}
 * so each test starts fresh. NOT for production use.
 */
export function __resetDistrictEntitiesForTests(): void {
  cachedDistrictEntities = null;
}

/**
 * Look up the canonical district entity_id for a district LGD numeric
 * code. Accepts the LGD value in any of its common shapes — integer
 * (`567`), zero-padded string (`"0567"`), or plain string (`"567"`) —
 * and normalises before matching. Returns `null` when the code does
 * not resolve to any currently-valid district (typical when a feature
 * carries a dissolved code or the polygon predates the taxonomy
 * snapshot).
 *
 * Mirrors `lgdCodeToEci` from states.ts. The district branch of
 * IndicatorChoropleth's `handleSelect` (PR B.05 C3) calls this helper
 * to resolve the clicked feature's `dist_lgd` to a district entity_id
 * (no-op when there is no district landing page yet).
 */
export async function lgdCodeToDistrictEntityId(
  lgdCode: number | string | null | undefined,
): Promise<string | null> {
  if (lgdCode === null || lgdCode === undefined) return null;
  const raw = String(lgdCode).trim();
  if (!raw) return null;
  const normalized = String(parseInt(raw, 10));
  if (normalized === "NaN") return null;
  const districts = await loadAllDistrictEntities();
  for (const d of districts) {
    if (!d.lgd_code) continue;
    if (String(parseInt(d.lgd_code, 10)) === normalized) return d.entity_id;
  }
  return null;
}

