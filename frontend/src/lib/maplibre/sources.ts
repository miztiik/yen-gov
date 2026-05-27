// Boundary source resolution for the map components.
//
// Three-tier strategy (highest priority first):
//   1. datasets/boundaries/in/manifest.json (produced by tools/boundaries/
//      build.py in CI — see docs/architecture/frontend/map.md). When present,
//      use the packed PMTiles via the pmtiles:// protocol.
//   2. Local GeoJSON snapshot under datasets/boundaries/in/<kind>/... in
//      the Hive partition layout (per ADR-0031 Amendment 2026-05-22 —
//      T.0d boundaries consolidation). Produced by tools/boundaries/
//      snapshot.py + emitted via the boundary_layers.parquet ledger.
//      Loads in a single same-origin request, no public network hop
//      required.
//   3. Direct upstream GeoJSON URL (raw.githubusercontent.com or similar).
//      Last-resort fallback when no snapshot exists — used only during
//      development before snapshot.py has been run for a new layer.
//
// When PMTiles arrive, only `resolveSource()` changes; the map components
// don't care which tier wins.
//
// LGD-keyed state polygons: ramSeraph's LGD_States release tags features
// with State_LGD (numeric LGD code, e.g. 33 for Tamil Nadu) per BharatMaps
// lineage — post-2014 Telangana split, post-2019 Ladakh split, merged
// DNH-DD UT all included. Joins to taxonomy.entities.lgd_code via
// MapChoropleth's `to-number` coercion (string-key/int-property bridge).
// Replaces the DataMeet ST_NM name-string join retired in Phase D.0
// (TODO/20260524-boundary-coverage-expansion-plan.md).

export interface BoundaryEntry {
  /** Stable id used in URL paths and join keys. */
  id: string;
  /** Human-readable label for tooltips & errors. */
  label: string;
  /**
   * Optional same-origin GeoJSON snapshot path under DATA_BASE (e.g.
   * "boundaries/in/ac/state=in_s22/all.geojson"). Preferred over the
   * upstream URL when present — it's an order of magnitude faster and
   * works offline. Populated by tools/boundaries/snapshot.py; Hive
   * partition layout per ADR-0031 Amendment 2026-05-22.
   */
  geojson_local_path?: string;
  /** Direct upstream GeoJSON URL (last-resort fallback). */
  geojson_url: string;
  /** Property name on each feature carrying the join key. */
  join_property: string;
  /** License attribution shown in the map footer. */
  attribution: string;
}

// India-wide states layer. Property State_LGD = LGD numeric state code
// (e.g. 33 for Tamil Nadu, 7 for Delhi) per ramSeraph's LGD_States release
// (BharatMaps lineage). Snapshotted locally; the upstream URL points at
// the .geojsonl.7z bundle that tools/boundaries/snapshot.py extracts
// into the GeoJSON feature collection on disk. State-name joining via
// the legacy DataMeet ST_NM property retired in Phase D.0 — see
// TODO/20260524-boundary-coverage-expansion-plan.md.
export const INDIA_STATES: BoundaryEntry = {
  id: "india-states",
  label: "India — states",
  geojson_local_path: "boundaries/in/states/all.geojson",
  geojson_url:
    "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/states/LGD_States.geojsonl.7z",
  join_property: "State_LGD",
  attribution:
    '<a href="https://github.com/ramSeraph/indian_admin_boundaries" target="_blank" rel="noreferrer">ramSeraph LGD-keyed admin boundaries</a> (CC0 1.0; sourced from LGD / BharatMaps)',
};

// Per-state AC layers. Property `ac_no` (lowercase) = 1-based per-state
// constituency number, joins to candidates.constituency_eci_no in
// results.sqlite (= ECI eci_no). Post-D.7 (PR #_pending_) the ramSeraph
// LGD release is the default; 2 states stay on HTL because LGD's slice
// fails the safety-net rule: S01 Andhra Pradesh (LGD bundles legacy
// AP+TG ac_no 1-294 with names that don't match the post-2014 AP-only
// SoT; ac_no=30 → LGD 'Yanam' vs SoT 'Anakapalle') and S03 Assam (LGD
// ships pre-2023 delim names; SoT carries post-2023 delim — 0.8% name
// parity). Both keep HTL `AC_NO` (uppercase) until upstream catches up.
// U08 (J&K) keeps `seat_id` because LGD has not yet published the
// post-2022 90-AC delimitation as of 2026-05-27.
export const STATE_AC: Record<string, BoundaryEntry> = {
  S22: {
    id: "S22-ac",
    label: "Tamil Nadu — Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s22/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
    attribution:
      '<a href="https://github.com/ramSeraph/indian_admin_boundaries" target="_blank" rel="noreferrer">ramSeraph LGD-keyed admin boundaries</a> (CC0 1.0; sourced from LGD / BharatMaps)',
  },
  S11: {
    id: "S11-ac",
    label: "Kerala — Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s11/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
    attribution:
      '<a href="https://github.com/ramSeraph/indian_admin_boundaries" target="_blank" rel="noreferrer">ramSeraph LGD-keyed admin boundaries</a> (CC0 1.0; sourced from LGD / BharatMaps)',
  },
  S25: {
    id: "S25-ac",
    label: "West Bengal — Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s25/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
    attribution:
      '<a href="https://github.com/ramSeraph/indian_admin_boundaries" target="_blank" rel="noreferrer">ramSeraph LGD-keyed admin boundaries</a> (CC0 1.0; sourced from LGD / BharatMaps)',
  },
  S03: {
    id: "S03-ac",
    label: "Assam — Assembly constituencies (pre-2026 delimitation)",
    geojson_local_path: "boundaries/in/ac/state=in_s03/all.geojson",
    geojson_url:
      "https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/master/state_ut/assam/assembly/assam_AC.json",
    join_property: "AC_NO",
    attribution:
      '<a href="https://github.com/HindustanTimesLabs/shapefiles" target="_blank" rel="noreferrer">HTL shapefiles</a> (MIT) — boundaries predate the 2023 delimitation; AC_NO ↔ eci_no may not align for some seats',
  },
  U07: {
    id: "U07-ac",
    label: "Puducherry — Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_u07/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
    attribution:
      '<a href="https://github.com/ramSeraph/indian_admin_boundaries" target="_blank" rel="noreferrer">ramSeraph LGD-keyed admin boundaries</a> (CC0 1.0; sourced from LGD / BharatMaps)',
  },
  // J&K post-2022 delimitation (90 ACs). HTL/datameet still ship the
  // pre-delimitation 87-AC layer for J&K; shijithpk/2024_maps_supplement
  // georeferenced the J&K CEO official AC map PDF + an NIC map server into
  // a fresh GeoJSON. Property schema is non-HTL: join key is `seat_id`
  // (matches eci_no in datasets/reference/in/states/U08/constituencies.json,
  // cross-validated 2026-05-13). The file also contains one extra feature
  // with seat_id 9999 for PoK areas; renderers should ignore it for the
  // 90-AC choropleth.
  U08: {
    id: "U08-ac",
    label: "Jammu & Kashmir — Assembly constituencies (post-2022 delimitation)",
    geojson_local_path: "boundaries/in/ac/state=in_u08/all.geojson",
    geojson_url:
      "https://raw.githubusercontent.com/shijithpk/2024_maps_supplement/main/j_and_k_assembly_new_borders.geojson",
    join_property: "seat_id",
    attribution:
      '<a href="https://github.com/shijithpk/2024_maps_supplement" target="_blank" rel="noreferrer">shijithpk/2024_maps_supplement</a> (Unlicense), georeferenced from the <a href="https://ceojk.nic.in/pdf/J&K%20AC%20map%20new.pdf" target="_blank" rel="noreferrer">J&K CEO official AC map PDF</a>',
  },
};

// Note: the legacy `STATE_NAME_TO_ECI` constant + `eciFromStateName` helper
// that previously lived here were retired in T.0e (TODO/20260517-canonical-
// long-format-pivot.md §0e.7). Both are now served by the view-model under
// `frontend/src/lib/view-models/states.ts`, which reads the canonical
// `taxonomy.entities` Parquet via DuckDB-WASM and exposes all three code
// systems (ECI / LGD / ISO 3166-2) alongside the citizen-readable name,
// the citizen-display shortform (`boundary_join_name`), and the
// `boundary_join_key` projection used for map joining post-D.0.
export { eciFromStateName, lgdCodeToEci } from "../view-models/states";

export interface ResolvedSource {
  /** Either 'pmtiles' (production) or 'geojson' (fallback). */
  kind: "pmtiles" | "geojson";
  /** URL the map source should load from. */
  url: string;
  /** Layer name inside a PMTiles container; ignored for GeoJSON. */
  source_layer?: string;
}

interface ManifestFile {
  path: string;
  kind: string;
  state?: string;
  ac_no_property?: string;
  name_property?: string;
}

interface BoundaryManifest {
  generated_at: string;
  files: ManifestFile[];
}

import { DATA_BASE } from "../paths";

let manifest_cache: Promise<BoundaryManifest | null> | null = null;

/** Fetch and cache the boundary manifest. Resolves to null when absent. */
export function fetchBoundaryManifest(): Promise<BoundaryManifest | null> {
  if (!manifest_cache) {
    manifest_cache = fetch(`${DATA_BASE}/boundaries/in/manifest.json`)
      .then(async r => (r.ok ? ((await r.json()) as BoundaryManifest) : null))
      .catch(() => null);
  }
  return manifest_cache;
}

/**
 * Resolve a boundary entry to a concrete URL. Resolution order matches the
 * three-tier strategy at the top of this file: PMTiles (manifest) → local
 * GeoJSON snapshot → upstream GeoJSON URL.
 */
export async function resolveSource(entry: BoundaryEntry): Promise<ResolvedSource> {
  const m = await fetchBoundaryManifest();
  if (m) {
    const match = m.files.find(f =>
      // Manifest paths look like 'datasets/boundaries/in/<id>.pmtiles'
      f.path.endsWith(`/${entry.id}.pmtiles`),
    );
    if (match) {
      return {
        kind: "pmtiles",
        url: `pmtiles://${DATA_BASE}/${match.path.replace(/^datasets\//, "")}`,
        source_layer: entry.id,
      };
    }
  }
  if (entry.geojson_local_path) {
    // We trust the path was wired up alongside a real snapshot under
    // datasets/boundaries/in/ in the Hive partition layout (ADR-0031
    // Amendment 2026-05-22). The dev server middleware (and the
    // production Pages deploy) both serve datasets/ at /data/. If the file
    // is missing, the map will surface a load error rather than silently
    // fall through to the upstream URL — surfaceable bugs are better than
    // hidden ones (CLAUDE.md §10 anti-patterns).
    return { kind: "geojson", url: `${DATA_BASE}/${entry.geojson_local_path}` };
  }
  return { kind: "geojson", url: entry.geojson_url };
}
