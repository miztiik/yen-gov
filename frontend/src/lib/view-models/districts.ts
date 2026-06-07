// Districts view-model loader.
//
// History: Phase-0 closeout T.0c-ii-B.2 + PR B.05 C1 lifted these
// loaders onto the canonical `taxonomy.entities` Parquet via DuckDB-WASM
// (national LGD-keyed loader for district-grain choropleth + per-state
// legacy-id loader for AC grouping). X1a-fu2-A (2026-06-07) flipped the
// reader off the now-RETIRED `taxonomy.entities.parquet` onto the
// hand-authored `datasets/taxonomy/entities.json` SoT.
//
// Why entities.json (not geo.csv): the sub-row A reader-flip prompt's
// preferred surface for entity-grain reads is
// `datasets/data/entities/geo.csv`, but the loaders here need two
// columns that geo.csv does not carry:
//
//   1. `legacy_id` (Wikipedia/ECI 3-letter code, e.g. "CHN" for
//      Chennai). 145 of the 784 currently-valid districts carry one;
//      `StateOverview.svelte` joins constituencies.json's
//      `district_id` against `District.id` on this column to group
//      ACs under their parent district. geo.csv has no `legacy_id`
//      analogue (the slug-compound entity_id `tamil-nadu/chennai`
//      replaces it for general-purpose joining but the legacy 3-letter
//      code is the contract surface for constituencies.json).
//
//   2. `entity_id` / `parent_entity_id` in the legacy
//      `IN-S22-D567` / `IN-S22` shape. geo.csv publishes them as the
//      LGD-slug-compound `tamil-nadu/chennai` / `tamil-nadu`. The
//      out-of-scope consumers (`routes/District.svelte`) compare
//      against the `IN-${state_eci}` form, so preserving the legacy
//      shape avoids a cascade rewrite this PR's scope forbids.
//
// entities.json is the canonical SoT (`entities.parquet` was its
// compiled form, RETIRED here). It carries every field these loaders
// need natively in the right shape - so this loader reads the JSON
// once, caches in-memory, and serves both view-models off the same
// rowset. The 376 KB JSON gzips to ~80 KB and is fetched at most once
// per session.
//
// Two complementary projections of the same entities.json rows live
// here:
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
// The two projections deliberately do not share a row type - they
// answer different questions and citizens never see the difference.
// `legacy_id` is the constituency-grouping joinable; `lgd_code` is
// the map-polygon joinable.

import { DATA_BASE } from "../paths";

export interface District {
  /** Wikipedia/ECI 3-letter code - joins on constituencies[].district_id. */
  id: string;
  /** Citizen-readable district name. */
  name: string;
}

/**
 * National-scope district row carrying the columns needed by the
 * district branch of IndicatorChoropleth (PR B.05): LGD-keyed
 * map-join key + parent state name for the tooltip.
 *
 * Distinct from {@link District} because it answers a different
 * question (national choropleth fill keying), reads different
 * columns from the same table, and adds a parent_state_name field
 * required by Jony's B.05 tooltip constraint.
 */
export interface DistrictEntity {
  /** Canonical district entity_id (e.g. "IN-S22-D567"). */
  entity_id: string;
  /** Citizen-readable district name from entities.json (e.g. "Coimbatore"). */
  display_name: string;
  /** LGD numeric code (MoHA Local Government Directory), e.g. "567". */
  lgd_code: string;
  /**
   * Map-join key. LGD numeric code as a string. USE THIS - NOT
   * `display_name` - when keying fills / tooltips / highlight dicts
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
   * Jony's B.05 tooltip constraint - district tooltip must render
   * district name AND parent state name so the citizen can anchor
   * the place ("Coimbatore - Tamil Nadu").
   */
  parent_state_name: string;
}

interface RawEntity {
  entity_id: string;
  entity_type: string;
  entity_level?: string;
  entity_code?: string;
  display_name: string;
  parent_entity_id?: string | null;
  entity_valid_from?: number;
  entity_valid_to?: number | null;
  iso_3166_2?: string | null;
  lgd_code?: string | null;
  legacy_id?: string | null;
}

interface EntitiesJson {
  $schema?: string;
  $schema_version?: string;
  entities: RawEntity[];
}

const ENTITIES_JSON_PATH = "taxonomy/entities.json";

let entitiesPromise: Promise<RawEntity[]> | null = null;

/**
 * Fetch entities.json once and cache. Both loaders share the same
 * rowset so a single network fetch serves the whole session.
 *
 * Path: served by Vite middleware `serveDatasets()` at
 * `/data/taxonomy/entities.json` (dev) and copied into
 * `_site/data/taxonomy/entities.json` by the Pages workflow (prod).
 */
async function loadEntities(): Promise<RawEntity[]> {
  if (entitiesPromise) return entitiesPromise;
  const url = `${DATA_BASE}/${ENTITIES_JSON_PATH}`;
  entitiesPromise = fetch(url).then(async (res) => {
    if (!res.ok) {
      throw new Error(
        `entities.json fetch failed: ${res.status} ${res.statusText}`,
      );
    }
    const payload = (await res.json()) as EntitiesJson;
    if (!Array.isArray(payload?.entities)) {
      throw new Error("entities.json: malformed (missing entities array)");
    }
    return payload.entities;
  });
  entitiesPromise.catch(() => {
    entitiesPromise = null;
  });
  return entitiesPromise;
}

/**
 * Load the district list for a state (e.g. "S22") from the hand-
 * authored `taxonomy/entities.json` SoT. Returns rows ordered by
 * display name. Only districts that carry a `legacy_id` (Wikipedia/
 * ECI 3-letter code) are included - the ~640 districts without one
 * cannot back-join to `constituencies.json#/constituencies[].district_id`
 * and would surface as silent dropouts in `StateOverview`'s grouping.
 * They fall through to the "(unmapped)" bucket via the consumer's
 * `district_id ?? ""` fallback (pre-flip behaviour preserved).
 *
 * Throws on fetch / JSON failure - the caller is expected to wrap in
 * `.catch(() => null)` if a missing district list should fall through
 * to the existing "(unmapped)" rendering path (which is exactly what
 * StateOverview.svelte does).
 */
export async function loadDistricts(state: string): Promise<District[]> {
  const entities = await loadEntities();
  const parent_eid = `IN-${state}`;
  return entities
    .filter(
      (e) =>
        e.entity_type === "district" &&
        e.parent_entity_id === parent_eid &&
        e.entity_valid_to == null &&
        e.legacy_id != null &&
        e.legacy_id !== "" &&
        e.display_name != null,
    )
    .map((e) => ({ id: e.legacy_id as string, name: e.display_name }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

// ----------------------------------------------------------------------
// PR B.05 C1 - nation-wide LGD-keyed district loader for choropleth
// ----------------------------------------------------------------------

let cachedDistrictEntities: Promise<DistrictEntity[]> | null = null;

/**
 * Load all currently-valid Indian districts from
 * `taxonomy/entities.json`, with each row's parent state/UT name
 * resolved by in-memory join against the same rowset's
 * `entity_type IN ('state', 'ut')` rows. Returns 784 rows today
 * (verified 2026-06-07; all carry `lgd_code` and a resolvable
 * `parent_entity_id`).
 *
 * Cached per page-load - the table is 784 rows and the data does not
 * change within a session. Call once near the top of a `$effect` or
 * `onMount`; downstream deriveds operate on the resolved array
 * synchronously.
 *
 * Throws on fetch / JSON failure. Callers that need to fall through
 * to a "render nothing yet" state should keep the result in a
 * `$state` variable initialised to `null` and check for null before
 * iterating.
 */
export async function loadAllDistrictEntities(): Promise<DistrictEntity[]> {
  if (!cachedDistrictEntities)
    cachedDistrictEntities = loadAllDistrictEntitiesUncached();
  return cachedDistrictEntities;
}

async function loadAllDistrictEntitiesUncached(): Promise<DistrictEntity[]> {
  const entities = await loadEntities();
  // In-memory self-join: collect every state/UT row's display_name
  // keyed on entity_id, then attach to each district row via
  // parent_entity_id. Mirrors the SQL `LEFT JOIN entities s ON
  // d.parent_entity_id = s.entity_id` the pre-X1a-fu2-A SQL did.
  const stateNameByEid = new Map<string, string>();
  for (const e of entities) {
    if (
      (e.entity_type === "state" || e.entity_type === "ut") &&
      e.display_name != null
    ) {
      stateNameByEid.set(e.entity_id, e.display_name);
    }
  }
  return entities
    .filter(
      (e) =>
        e.entity_type === "district" &&
        e.entity_valid_to == null &&
        e.lgd_code != null &&
        e.lgd_code !== "" &&
        e.parent_entity_id != null &&
        e.display_name != null &&
        stateNameByEid.has(e.parent_entity_id),
    )
    .map((e) => {
      const lgd_code = e.lgd_code as string;
      const parent_entity_id = e.parent_entity_id as string;
      return {
        entity_id: e.entity_id,
        display_name: e.display_name,
        lgd_code,
        boundary_join_key: lgd_code,
        parent_entity_id,
        parent_state_name: stateNameByEid.get(parent_entity_id) as string,
      };
    })
    .sort((a, b) => a.entity_id.localeCompare(b.entity_id));
}

/**
 * Test-only: reset the module-level cache for {@link loadAllDistrictEntities}
 * and the underlying entities.json fetch so each test starts fresh.
 * NOT for production use.
 */
export function __resetDistrictEntitiesForTests(): void {
  cachedDistrictEntities = null;
  entitiesPromise = null;
}

/**
 * Look up the canonical district entity_id for a district LGD numeric
 * code. Accepts the LGD value in any of its common shapes - integer
 * (`567`), zero-padded string (`"0567"`), or plain string (`"567"`) -
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


