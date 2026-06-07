// State / UT view-model loader.
//
// History: T.0e (STATE_NAME_TO_ECI retirement, TODO/20260517-canonical-
// long-format-pivot.md section 0e.7) lifted this loader off the inline
// `STATE_NAME_TO_ECI` constant onto the canonical `taxonomy.entities`
// Parquet via DuckDB-WASM. D.0 (TODO/20260524-boundary-coverage-
// expansion-plan.md section D.0) reshaped the projection for the
// ramSeraph LGD_States boundary swap. X1a-fu2-A (2026-06-07) flipped
// the reader off `taxonomy.entities.parquet` (RETIRED) onto
// `datasets/data/entities/geo.csv` via the typed-read seam
// (`registerCsvFile` + `csvColumnsClause` + `read_csv(columns=...)`).
//
// What is read:
//   datasets/data/entities/geo.csv -
//     entity_kind='state' rows. geo.csv folds the pre-pivot
//     ('state', 'ut') split into a single `entity_kind='state'`
//     enumeration (the ECI code's S-vs-U prefix already encodes the
//     state/UT distinction citizen-side). Historic entities are not
//     present in geo.csv (the LGD register only carries currently-
//     valid jurisdictions), so the pre-flip `entity_valid_to IS NULL`
//     guard is implicit.
//
// Where the legacy parquet columns come from now:
//   - entity_id (e.g. "IN-S22")    synthesised in SQL as
//                                  'IN-' || <eci_code>; the eci_code
//                                  is extracted from the geo.csv
//                                  `aliases` pipe-list (token
//                                  matching `[SU][0-9]+`).
//   - eci_code (e.g. "S22")        extracted from `aliases` as above.
//   - display_name                 the geo.csv `name` column verbatim;
//                                  this is already the citizen-facing
//                                  shortform ("Delhi", "Andaman &
//                                  Nicobar", "Jammu & Kashmir") so the
//                                  pre-flip BOUNDARY_NAME_OVERRIDES
//                                  table is no longer needed.
//   - lgd_code (e.g. "33")         extracted from `aliases` (token
//                                  matching `lgd:[0-9]+`).
//   - iso_3166_2 (e.g. "IN-TN")    extracted from `aliases` (token
//                                  matching `IN-[A-Z]{2,3}`).
//
// What is returned:
//   `StateRow[]` with all three code systems exposed (ECI / LGD / ISO
//   3166-2) plus two name-shaped fields:
//     - `display_name`        citizen-readable shortform from geo.csv
//                             (e.g. "Delhi", "Tamil Nadu"). USE THIS
//                             in chips, tooltips, ranked-bar rows.
//     - `boundary_join_name`  alias for `display_name` post-X1a-fu2-A
//                             (geo.csv already publishes the shortform
//                             as the `name` column, so the pre-flip
//                             shortening overrides retire). Kept on the
//                             interface for call-site stability.
//     - `boundary_join_key`   the value the choropleth fills/tooltips
//                             dicts MUST be keyed on so they match the
//                             ramSeraph LGD_States `State_LGD` integer
//                             property carried in the geojson features.
//                             LGD numeric code as a STRING (e.g. "33"
//                             for Tamil Nadu, "7" for Delhi - geo.csv
//                             does NOT zero-pad). MapChoropleth's
//                             `keys_are_numeric` + `to-number` coercion
//                             bridges the string-key/int-property gap
//                             automatically.

import { query, registerCsvFile } from "../duckdb";
import { DATA_BASE } from "../paths";
import { csvColumnsClause } from "../canonical/csv-columns";

export interface StateRow {
  /** Canonical entity_id (e.g. "IN-S22"). Synthesised as 'IN-' || eci_code. */
  entity_id: string;
  /** ECI state/UT code (e.g. "S22"). Matches the legacy STATE_NAME_TO_ECI value. */
  eci_code: string;
  /** Citizen-readable shortform from geo.csv (e.g. "Tamil Nadu", "Delhi"). */
  display_name: string;
  /**
   * Citizen-display shortform. Equal to `display_name` for every row
   * post-X1a-fu2-A because geo.csv publishes the shortform directly as
   * its `name` column (the pre-flip override table that mapped the
   * legal long form "NCT of Delhi" / "Andaman and Nicobar Islands" /
   * "Jammu and Kashmir (UT)" down to the shortform is no longer
   * needed). Kept on the interface so existing call sites keep
   * compiling.
   */
  boundary_join_name: string;
  /**
   * Map-join key. LGD numeric code as a string. USE THIS - NOT
   * `boundary_join_name` - when keying fills/tooltips/highlight dicts
   * in IndicatorChoropleth / IndiaMap. Matches the ramSeraph LGD_States
   * `State_LGD` integer property carried in
   * `datasets/boundaries/in/states/all.geojson` via MapChoropleth's
   * `keys_are_numeric` + `to-number` coercion.
   *
   * Why a separate field from `lgd_code`: `lgd_code` is the raw
   * extracted token. `boundary_join_key` is its always-present,
   * ready-to-use-as-map-join-key projection. Callers that want the LGD
   * value for any other purpose (display, URL slug, external data
   * join) should keep using `lgd_code`.
   */
  boundary_join_key: string;
  /** LGD numeric code (MoHA Local Government Directory), e.g. "33" for Tamil Nadu. */
  lgd_code: string | null;
  /** ISO 3166-2 code (e.g. "IN-TN"). */
  iso_3166_2: string | null;
}

interface RawStateRow {
  entity_id: string | null;
  eci_code: string | null;
  display_name: string | null;
  lgd_code: string | null;
  iso_3166_2: string | null;
}

const GEO_CSV_PATH = "datasets/data/entities/geo.csv";

let cached: Promise<StateRow[]> | null = null;

/**
 * Load all currently-valid Indian states + UTs from
 * `datasets/data/entities/geo.csv`.
 *
 * Cached per page-load - the table is 36 rows and the data does not change
 * within a session. Call this once near the top of a `$effect` or
 * `onMount`; downstream deriveds operate on the resolved array
 * synchronously.
 *
 * Throws on DuckDB-WASM / CSV fetch / SQL failure. Callers that need to
 * fall through to a "render nothing yet" state should keep the result
 * in a `$state` variable initialised to `null` and check for null
 * before iterating.
 */
export async function loadStates(): Promise<StateRow[]> {
  if (!cached) cached = loadStatesUncached();
  return cached;
}

async function loadStatesUncached(): Promise<StateRow[]> {
  const url = `${DATA_BASE}/${GEO_CSV_PATH.replace(/^datasets\//, "")}`;
  const [clause] = await Promise.all([
    csvColumnsClause(GEO_CSV_PATH),
    registerCsvFile(url),
  ]);
  // `regexp_extract(aliases, '<re>', 1)` pulls the matched capture group
  // out of the geo.csv pipe-delimited aliases column. ECI matches
  // `[SU][0-9]+` (no other token has this shape); LGD matches the
  // `lgd:` prefix; ISO matches `IN-` followed by 2-3 uppercase letters
  // (the long-form name tokens never start with `IN-`). NULLIF '' guards
  // against rows whose aliases column is empty.
  const sql = `
    SELECT
      'IN-' || regexp_extract(aliases, '([SU][0-9]+)', 1)        AS entity_id,
      NULLIF(regexp_extract(aliases, '([SU][0-9]+)', 1), '')     AS eci_code,
      name                                                        AS display_name,
      NULLIF(regexp_extract(aliases, 'lgd:([0-9]+)', 1), '')     AS lgd_code,
      NULLIF(regexp_extract(aliases, '(IN-[A-Z]{2,3})', 1), '')  AS iso_3166_2
    FROM read_csv('${url}', ${clause})
    WHERE entity_kind = 'state'
    ORDER BY eci_code
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
        boundary_join_name: display_name,
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
 * `display_name` (which is also the shortform post-X1a-fu2-A, since
 * geo.csv publishes the shortform as its `name` column - the pre-flip
 * legal-long-form lookups like "NCT of Delhi" no longer resolve).
 *
 * Retained for back-compat with pre-D.0 call sites that resolved
 * clicked-feature ST_NM values to ECI codes. Post-D.0 the click
 * handler joins on LGD codes via `lgdCodeToEci` - this helper is now
 * for citizen-search and other name-keyed lookups only.
 */
export async function eciFromStateName(
  name: string | undefined | null,
): Promise<string | null> {
  if (!name) return null;
  const states = await loadStates();
  for (const s of states) {
    if (s.display_name === name) return s.eci_code;
    if (s.boundary_join_name === name) return s.eci_code;
  }
  return null;
}

/**
 * Look up the ECI code for a state LGD numeric code. Accepts the LGD
 * value in any of its common shapes - integer (`7`), zero-padded
 * string (`"07"`), or plain string (`"7"`) - and normalises before
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

