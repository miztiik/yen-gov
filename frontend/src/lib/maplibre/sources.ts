// Boundary source resolution for the map components.
//
// Three-tier strategy (highest priority first):
//   1. datasets/boundaries/in/manifest.json (produced by tools/boundaries/
//      build.py in CI — see docs/architecture/frontend/map.md). When present,
//      use the packed PMTiles via the pmtiles:// protocol.
//   2. Local GeoJSON snapshot under datasets/boundaries/in/geojson/ (produced
//      by tools/boundaries/snapshot.py and committed to the repo). Loads in
//      a single same-origin request, no public network hop required.
//   3. Direct upstream GeoJSON URL (raw.githubusercontent.com or similar).
//      Last-resort fallback when no snapshot exists — used only during
//      development before snapshot.py has been run for a new layer.
//
// When PMTiles arrive, only `resolveSource()` changes; the map components
// don't care which tier wins.
//
// State-name → ECI code map: datameet/maps Admin2 tags features with ST_NM
// (post-2014 Telangana split, post-2019 Ladakh split, merged DNH-DD UT — all
// included). We need the ECI state code (S22, S25, ...) to look up per-state
// result summaries. Hand-maintained because state names are stable English
// forms and we control which state codes ship in datasets/.

export interface BoundaryEntry {
  /** Stable id used in URL paths and join keys. */
  id: string;
  /** Human-readable label for tooltips & errors. */
  label: string;
  /**
   * Optional same-origin GeoJSON snapshot path under DATA_BASE (e.g.
   * "boundaries/in/geojson/S22-ac.geojson"). Preferred over the upstream
   * URL when present — it's an order of magnitude faster and works
   * offline. Populated by tools/boundaries/snapshot.py.
   */
  geojson_local_path?: string;
  /** Direct upstream GeoJSON URL (last-resort fallback). */
  geojson_url: string;
  /** Property name on each feature carrying the join key. */
  join_property: string;
  /** License attribution shown in the map footer. */
  attribution: string;
}

// India-wide states layer. Property ST_NM = English state name (datameet).
// Snapshotted locally; the upstream URL points at the .shp (the snapshot
// script converts datameet's shapefile bundle into GeoJSON — the URL is
// kept for the manifest/sidecar and as a documentation pointer).
export const INDIA_STATES: BoundaryEntry = {
  id: "india-states",
  label: "India — states",
  geojson_local_path: "boundaries/in/geojson/india-states.geojson",
  geojson_url:
    "https://raw.githubusercontent.com/datameet/maps/master/States/Admin2.shp",
  join_property: "ST_NM",
  attribution:
    '<a href="https://github.com/datameet/maps" target="_blank" rel="noreferrer">DataMeet India Maps</a> (CC BY 4.0)',
};

// Per-state AC layers. Property AC_NO = 1-based per-state constituency number,
// joins to candidates.constituency_eci_no in results.sqlite (= ECI eci_no).
export const STATE_AC: Record<string, BoundaryEntry> = {
  S22: {
    id: "S22-ac",
    label: "Tamil Nadu — Assembly constituencies",
    geojson_local_path: "boundaries/in/geojson/S22-ac.geojson",
    geojson_url:
      "https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/master/state_ut/tamilnadu/assembly/tamilnadu_AC.json",
    join_property: "AC_NO",
    attribution:
      '<a href="https://github.com/HindustanTimesLabs/shapefiles" target="_blank" rel="noreferrer">HTL shapefiles</a> (MIT)',
  },
  S11: {
    id: "S11-ac",
    label: "Kerala — Assembly constituencies",
    geojson_local_path: "boundaries/in/geojson/S11-ac.geojson",
    geojson_url:
      "https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/master/state_ut/kerala/assembly/kerala_AC.json",
    join_property: "AC_NO",
    attribution:
      '<a href="https://github.com/HindustanTimesLabs/shapefiles" target="_blank" rel="noreferrer">HTL shapefiles</a> (MIT)',
  },
  S25: {
    id: "S25-ac",
    label: "West Bengal — Assembly constituencies",
    geojson_local_path: "boundaries/in/geojson/S25-ac.geojson",
    geojson_url:
      "https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/master/state_ut/westbengal/assembly/westbengal_AC.json",
    join_property: "AC_NO",
    attribution:
      '<a href="https://github.com/HindustanTimesLabs/shapefiles" target="_blank" rel="noreferrer">HTL shapefiles</a> (MIT)',
  },
  S03: {
    id: "S03-ac",
    label: "Assam — Assembly constituencies (pre-2026 delimitation)",
    geojson_local_path: "boundaries/in/geojson/S03-ac.geojson",
    geojson_url:
      "https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/master/state_ut/assam/assembly/assam_AC.json",
    join_property: "AC_NO",
    attribution:
      '<a href="https://github.com/HindustanTimesLabs/shapefiles" target="_blank" rel="noreferrer">HTL shapefiles</a> (MIT) — boundaries predate the 2023 delimitation; AC_NO ↔ eci_no may not align for some seats',
  },
  U07: {
    id: "U07-ac",
    label: "Puducherry — Assembly constituencies",
    geojson_local_path: "boundaries/in/geojson/U07-ac.geojson",
    geojson_url:
      "https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/master/state_ut/puducherry/assembly/puducherry_AC.json",
    join_property: "AC_NO",
    attribution:
      '<a href="https://github.com/HindustanTimesLabs/shapefiles" target="_blank" rel="noreferrer">HTL shapefiles</a> (MIT)',
  },
};

// datameet ST_NM → ECI state code. Covers all 36 states/UTs so the India
// choropleth can highlight any state that has a /s/<state> route, even if
// per-AC boundary tiles for that state aren't yet shipped. Two name
// adjustments vs datasets/reference/in/states.json (which uses the legal
// names): "Andaman and Nicobar Islands" → "Andaman & Nicobar" and
// "NCT of Delhi" → "Delhi", to match the datameet india-states.geojson.
export const STATE_NAME_TO_ECI: Record<string, string> = {
  "Andhra Pradesh": "S01",
  "Arunachal Pradesh": "S02",
  "Assam": "S03",
  "Bihar": "S04",
  "Goa": "S05",
  "Gujarat": "S06",
  "Haryana": "S07",
  "Himachal Pradesh": "S08",
  "Karnataka": "S10",
  "Kerala": "S11",
  "Madhya Pradesh": "S12",
  "Maharashtra": "S13",
  "Manipur": "S14",
  "Meghalaya": "S15",
  "Mizoram": "S16",
  "Nagaland": "S17",
  "Odisha": "S18",
  "Punjab": "S19",
  "Rajasthan": "S20",
  "Sikkim": "S21",
  "Tamil Nadu": "S22",
  "Tripura": "S23",
  "Uttar Pradesh": "S24",
  "West Bengal": "S25",
  "Chhattisgarh": "S26",
  "Jharkhand": "S27",
  "Uttarakhand": "S28",
  "Telangana": "S29",
  "Andaman & Nicobar": "U01",
  "Chandigarh": "U02",
  "Dadra and Nagar Haveli and Daman and Diu": "U03",
  "Lakshadweep": "U04",
  "Delhi": "U05",
  "Puducherry": "U07",
  "Jammu & Kashmir": "U08",
  "Ladakh": "U09",
};

// Reverse, for India-map tooltips that want the ECI code from feature props.
export function eciFromStateName(name: string | undefined | null): string | null {
  if (!name) return null;
  return STATE_NAME_TO_ECI[name] ?? null;
}

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
    // We trust the path was wired up alongside a real snapshot in
    // datasets/boundaries/in/geojson/. The dev server middleware (and the
    // production Pages deploy) both serve datasets/ at /data/. If the file
    // is missing, the map will surface a load error rather than silently
    // fall through to the upstream URL — surfaceable bugs are better than
    // hidden ones (CLAUDE.md §10 anti-patterns).
    return { kind: "geojson", url: `${DATA_BASE}/${entry.geojson_local_path}` };
  }
  return { kind: "geojson", url: entry.geojson_url };
}
