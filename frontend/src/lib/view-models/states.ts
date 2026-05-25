// State / UT view-model loader (T.0e — STATE_NAME_TO_ECI retirement,
// TODO/20260517-canonical-long-format-pivot.md §0e.7; D.0 — DataMeet →
// ramSeraph LGD_States swap, TODO/20260524-boundary-coverage-expansion-plan.md
// §D.0).
//
// Reads `taxonomy.entities` via DuckDB-WASM to project the 36 currently-
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
//   3166-2) plus two name-shaped fields:
//     - `display_name`        citizen-readable name verbatim from
//                             taxonomy.entities (publisher-stable legal
//                             form, e.g. "NCT of Delhi"). USE THIS as
//                             the user-facing string in any chip,
//                             tooltip body, ranked-bar row, etc.
//     - `boundary_join_name`  citizen-display SHORTFORM kept for legacy
//                             call sites that prefer the compact form
//                             (Delhi vs NCT of Delhi). Three rows
//                             differ from `display_name`. NOT used for
//                             map joining post-D.0 — see
//                             `boundary_join_key` instead.
//     - `boundary_join_key`   the value the choropleth fills/tooltips
//                             dicts MUST be keyed on so they match the
//                             ramSeraph LGD_States `State_LGD` integer
//                             property carried in the geojson features.
//                             It is the LGD numeric code as a STRING
//                             (e.g. "33" for Tamil Nadu, "07" for
//                             Delhi). MapChoropleth's `keys_are_numeric`
//                             + `to-number` coercion bridges the
//                             string-key/int-property gap automatically
//                             — `Number("07") === 7` matches the
//                             `State_LGD: 7` feature property.
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
   * Citizen-display SHORTFORM. Equals `display_name` for 33 of 36 rows;
   * differs for three rows where the publisher-stable legal form is
   * verbose and the citizen-facing shortform reads better in chips,
   * ranked-bar rows, small-multiples panel labels:
   *   - "Andaman and Nicobar Islands"            → "Andaman & Nicobar"
   *   - "NCT of Delhi"                           → "Delhi"
   *   - "Jammu and Kashmir (UT)"                 → "Jammu & Kashmir"
   * Use `boundary_join_name` for the citizen-display strings the
   * pre-D.0 codebase was already pointing at. Map joining post-D.0 goes
   * through `boundary_join_key` instead — see below.
   */
  boundary_join_name: string;
  /**
   * Map-join key. LGD numeric code as a string (e.g. "33" for Tamil
   * Nadu, "07" for Delhi). USE THIS — NOT `boundary_join_name` — when
   * keying fills/tooltips/highlight dicts in IndicatorChoropleth /
   * IndiaMap. Matches the ramSeraph LGD_States `State_LGD` integer
   * property carried in `datasets/boundaries/in/states/all.geojson`
   * via MapChoropleth's `keys_are_numeric` + `to-number` coercion.
   *
   * Why a separate field from `lgd_code`: `lgd_code` is the raw
   * taxonomy column (nullable, padded). `boundary_join_key` is its
   * always-present, ready-to-use-as-map-join-key projection. Callers
   * that want the LGD value for any other purpose (display, URL slug,
   * external data join) should keep using `lgd_code`.
   */
  boundary_join_key: string;
  /** LGD numeric code (MoHA Local Government Directory), e.g. "33" for Tamil Nadu. */
  lgd_code: string | null;
  /** ISO 3166-2 code (e.g. "IN-TN"). */
  iso_3166_2: string | null;
}

/**
 * Three rows where the citizen-display shortform differs from the
 * publisher-stable legal form carried in entities.parquet. The list is
 * small and stable; encoding it here keeps the shortening in one place.
 * Pre-D.0 this table also served as the map-join overrides (DataMeet
 * ST_NM published "Delhi" / "Andaman & Nicobar" / "Jammu & Kashmir"
 * verbatim, so the same shortened strings doubled as the join keys).
 * Post-D.0 the map joins on `boundary_join_key` (LGD code), so this
 * table is purely a display-readability convenience.
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
 * Cached per page-load — the table is 36 rows and the data does not change
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
    .filter((r) => r.entity_id && r.eci_code && r.display_name && r.lgd_code)
    .map((r) => {
      const display_name = r.display_name as string;
      const lgd_code = r.lgd_code as string;
      return {
        entity_id: r.entity_id as string,
        eci_code: r.eci_code as string,
        display_name,
        boundary_join_name: BOUNDARY_NAME_OVERRIDES[display_name] ?? display_name,
        boundary_join_key: lgd_code,
        lgd_code,
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
 * Look up the ECI code for a state/UT name. Returns `null` when the
 * name does not match any currently-valid state/UT. Matches against
 * both `display_name` AND `boundary_join_name` (the shortform) so
 * callers can pass either the legal form or the citizen shortform.
 *
 * Retained for back-compat with pre-D.0 call sites that resolved
 * clicked-feature ST_NM values to ECI codes. Post-D.0 the click
 * handler joins on LGD codes via `lgdCodeToEci` — this helper is now
 * for citizen-search and other name-keyed lookups only.
 */
export async function eciFromStateName(
  name: string | undefined | null,
): Promise<string | null> {
  if (!name) return null;
  const states = await loadStates();
  for (const s of states) {
    if (s.boundary_join_name === name) return s.eci_code;
    if (s.display_name === name) return s.eci_code;
  }
  return null;
}

/**
 * Look up the ECI code for a state LGD numeric code. Accepts the LGD
 * value in any of its common shapes — integer (`7`), zero-padded
 * string (`"07"`), or plain string (`"7"`) — and normalises before
 * matching. Returns `null` when the code does not resolve to any
 * currently-valid state/UT (typical when a feature carries a
 * dissolved code or the polygon predates the taxonomy snapshot).
 *
 * Post-D.0 IndicatorChoropleth's `handleSelect` calls this helper to
 * resolve the clicked feature's `State_LGD` to an ECI code for
 * drill-down. Stable LGD codes (single source of truth, no string
 * normalization) replace the brittle ST_NM name-string matching the
 * pre-D.0 codebase relied on.
 */
export async function lgdCodeToEci(
  lgdCode: number | string | null | undefined,
): Promise<string | null> {
  if (lgdCode === null || lgdCode === undefined) return null;
  const raw = String(lgdCode).trim();
  if (!raw) return null;
  const normalized = String(parseInt(raw, 10));
  if (normalized === "NaN") return null;
  const states = await loadStates();
  for (const s of states) {
    if (!s.lgd_code) continue;
    if (String(parseInt(s.lgd_code, 10)) === normalized) return s.eci_code;
  }
  return null;
}
