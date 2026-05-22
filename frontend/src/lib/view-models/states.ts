// State / UT view-model loader (T.0e — STATE_NAME_TO_ECI retirement,
// TODO/20260517-canonical-long-format-pivot.md §0e.7).
//
// Reads `taxonomy.entities` via DuckDB-WASM to project the 35 currently-
// valid Indian states + UTs that the choropleth, ranked-bar, small-
// multiples, India-map, Home, and Compare surfaces all iterate. Replaces
// the inline `STATE_NAME_TO_ECI` constant under
// `frontend/src/lib/maplibre/sources.ts` (which masked three coexisting
// code systems behind the ECI projection alone).
//
// What is read:
//   taxonomy.entities — rows where `entity_type IN ('state','ut')` AND
//     the entity is currently valid (`entity_valid_to IS NULL`). Historic
//     entities (`IN-S09` J&K-state retired 2019, `IN-U03-OLD` DnH-pre-
//     merger, `IN-U06` Daman-and-Diu-pre-merger) are excluded so the
//     citizen surface never offers a stale chip / map polygon.
//
// What is returned:
//   `StateRow[]` with all three code systems exposed (ECI / LGD / ISO
//   3166-2) plus the citizen-readable name AND a `boundary_join_name`
//   field carrying the value the choropleth needs to join against the
//   DataMeet india-states.geojson `ST_NM` property. The two names differ
//   for three rows because DataMeet ships idiomatic English forms while
//   entities.parquet carries the publisher-stable legal forms:
//     "Andaman and Nicobar Islands"  -> "Andaman & Nicobar"
//     "NCT of Delhi"                 -> "Delhi"
//     "Jammu and Kashmir (UT)"       -> "Jammu & Kashmir"
//   The override table is the SINGLE place this divergence is encoded
//   (down from being scattered across the deleted constant's comment +
//   six call sites + IndicatorChoropleth's join logic).
//
// Why a view-model, not a constant:
//   `taxonomy.entities` carries the LGD + ISO codes alongside ECI. The
//   inline constant could only express the ECI projection, so every
//   future use (ISO-keyed external data joins, LGD-keyed boundary joins,
//   citizen-search affordance) had to either fall back to a second
//   constant or read entities.parquet ad-hoc. One reader, one source of
//   truth.

import { query, registerTable } from "../duckdb";

export interface StateRow {
  /** Canonical entity_id (e.g. "IN-S22"). */
  entity_id: string;
  /** ECI state/UT code (e.g. "S22"). Matches the legacy STATE_NAME_TO_ECI value. */
  eci_code: string;
  /** Citizen-readable name from entities.parquet (e.g. "Tamil Nadu", "NCT of Delhi"). */
  display_name: string;
  /**
   * The string the DataMeet india-states.geojson `ST_NM` property carries
   * for this entity. Equals `display_name` for 32 of 35 rows; differs for
   * the three documented above. Use this — NOT `display_name` — when
   * building fills / tooltips / outlines keyed on the geojson join key.
   */
  boundary_join_name: string;
  /** LGD numeric code (MoHA Local Government Directory), e.g. "33" for Tamil Nadu. */
  lgd_code: string | null;
  /** ISO 3166-2 code (e.g. "IN-TN"). */
  iso_3166_2: string | null;
}

/**
 * Names that differ between entities.parquet (canonical legal form) and
 * the DataMeet india-states.geojson `ST_NM` property (load-bearing for the
 * choropleth join). The list is small and stable; encoding it here
 * collapses what was previously a comment-explained discrepancy on the
 * deleted constant + per-call-site adjustments.
 */
const BOUNDARY_NAME_OVERRIDES: Record<string, string> = {
  "Andaman and Nicobar Islands": "Andaman & Nicobar",
  "NCT of Delhi": "Delhi",
  "Jammu and Kashmir (UT)": "Jammu & Kashmir",
};

interface RawStateRow {
  entity_id: string | null;
  eci_code: string | null;
  display_name: string | null;
  lgd_code: string | null;
  iso_3166_2: string | null;
}

let cached: Promise<StateRow[]> | null = null;

/**
 * Load all currently-valid Indian states + UTs from `taxonomy.entities`.
 *
 * Cached per page-load — the table is 35 rows and the data does not change
 * within a session. Call this once near the top of a `$effect` or
 * `onMount`; downstream deriveds operate on the resolved array
 * synchronously.
 *
 * Throws on DuckDB-WASM / manifest / SQL failure. Callers that need to
 * fall through to a "render nothing yet" state should keep the result
 * in a `$state` variable initialised to `null` and check for null
 * before iterating.
 */
export async function loadStates(): Promise<StateRow[]> {
  if (!cached) cached = loadStatesUncached();
  return cached;
}

async function loadStatesUncached(): Promise<StateRow[]> {
  await registerTable("taxonomy.entities");
  const sql = `
    SELECT entity_id,
           entity_code AS eci_code,
           display_name,
           lgd_code,
           iso_3166_2
    FROM entities
    WHERE entity_type IN ('state', 'ut')
      AND entity_valid_to IS NULL
    ORDER BY entity_code
  `;
  const rows = await query<RawStateRow>(sql);
  return rows
    .filter((r) => r.entity_id && r.eci_code && r.display_name)
    .map((r) => {
      const display_name = r.display_name as string;
      return {
        entity_id: r.entity_id as string,
        eci_code: r.eci_code as string,
        display_name,
        boundary_join_name: BOUNDARY_NAME_OVERRIDES[display_name] ?? display_name,
        lgd_code: r.lgd_code ?? null,
        iso_3166_2: r.iso_3166_2 ?? null,
      };
    });
}

/**
 * Test-only: reset the module-level cache so each test starts fresh.
 * NOT for production use.
 */
export function __resetForTests(): void {
  cached = null;
}

/**
 * Look up the ECI code for a DataMeet `ST_NM` string. Returns `null`
 * when the name does not match any currently-valid state/UT. Replacement
 * for the deleted `eciFromStateName` helper; the same call signature is
 * preserved but it is now async (callers in the codebase already operate
 * inside async load chains, so adding `await` at the call site is the
 * only change).
 */
export async function eciFromStateName(
  name: string | undefined | null,
): Promise<string | null> {
  if (!name) return null;
  const states = await loadStates();
  for (const s of states) {
    if (s.boundary_join_name === name) return s.eci_code;
  }
  return null;
}
