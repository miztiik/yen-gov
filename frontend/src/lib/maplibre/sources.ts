// Boundary source resolution for the map components.
//
// Two-tier strategy:
//   1. Try datasets/boundaries/in/manifest.json (produced by tools/boundaries/
//      in CI — see docs/architecture/frontend/map.md). When present, use the
//      packed PMTiles via the pmtiles:// protocol.
//   2. Fall back to fetching the raw upstream GeoJSON directly. This keeps
//      the map functional during development (Windows can't run tippecanoe)
//      and before the boundaries workflow has run for the first time.
//
// When the manifest arrives, only the resolution function changes; the map
// components don't care which tier is in play.
//
// State-name → ECI code map: GADM-derived india_state.geojson tags features
// with NAME_1. We need the ECI state code (S22, S25, ...) to look up
// per-state result summaries. Hand-maintained because GADM names are stable
// English forms and we control which state codes ship in datasets/.

export interface BoundaryEntry {
  /** Stable id used in URL paths and join keys. */
  id: string;
  /** Human-readable label for tooltips & errors. */
  label: string;
  /** Direct GeoJSON URL (fallback path). */
  geojson_url: string;
  /** Property name on each feature carrying the join key. */
  join_property: string;
  /** License attribution shown in the map footer. */
  attribution: string;
}

// India-wide states layer. Property NAME_1 = English state name (GADM).
export const INDIA_STATES: BoundaryEntry = {
  id: "india-states",
  label: "India — states",
  geojson_url:
    "https://raw.githubusercontent.com/geohacker/india/master/state/india_state.geojson",
  join_property: "NAME_1",
  attribution:
    '<a href="https://gadm.org/" target="_blank" rel="noreferrer">GADM</a> via geohacker/india (CC BY 4.0)',
};

// Per-state AC layers. Property AC_NO = 1-based per-state constituency number,
// joins to candidates.constituency_eci_no in results.sqlite (= ECI eci_no).
export const STATE_AC: Record<string, BoundaryEntry> = {
  S22: {
    id: "S22-ac",
    label: "Tamil Nadu — Assembly constituencies",
    geojson_url:
      "https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/master/state_ut/tamilnadu/assembly/tamilnadu_AC.json",
    join_property: "AC_NO",
    attribution:
      '<a href="https://github.com/HindustanTimesLabs/shapefiles" target="_blank" rel="noreferrer">HTL shapefiles</a> (MIT)',
  },
  S11: {
    id: "S11-ac",
    label: "Kerala — Assembly constituencies",
    geojson_url:
      "https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/master/state_ut/kerala/assembly/kerala_AC.json",
    join_property: "AC_NO",
    attribution:
      '<a href="https://github.com/HindustanTimesLabs/shapefiles" target="_blank" rel="noreferrer">HTL shapefiles</a> (MIT)',
  },
  S25: {
    id: "S25-ac",
    label: "West Bengal — Assembly constituencies",
    geojson_url:
      "https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/master/state_ut/westbengal/assembly/westbengal_AC.json",
    join_property: "AC_NO",
    attribution:
      '<a href="https://github.com/HindustanTimesLabs/shapefiles" target="_blank" rel="noreferrer">HTL shapefiles</a> (MIT)',
  },
  S03: {
    id: "S03-ac",
    label: "Assam — Assembly constituencies (pre-2026 delimitation)",
    geojson_url:
      "https://raw.githubusercontent.com/HindustanTimesLabs/shapefiles/master/state_ut/assam/assembly/assam_AC.json",
    join_property: "AC_NO",
    attribution:
      '<a href="https://github.com/HindustanTimesLabs/shapefiles" target="_blank" rel="noreferrer">HTL shapefiles</a> (MIT) — boundaries predate the 2023 delimitation; AC_NO ↔ eci_no may not align for some seats',
  },
};

// GADM NAME_1 → ECI state code. Only states we currently have data for.
// When new states ship, append entries here (additive change).
export const STATE_NAME_TO_ECI: Record<string, string> = {
  "Tamil Nadu": "S22",
  "Kerala": "S11",
  "West Bengal": "S25",
  "Assam": "S03",
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
 * Resolve a boundary entry to a concrete URL, preferring PMTiles from the
 * manifest when available. Returns the GeoJSON fallback otherwise.
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
  return { kind: "geojson", url: entry.geojson_url };
}
