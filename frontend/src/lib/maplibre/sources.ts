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
}

// Single citizen-facing footer for ALL boundary layers (A.3 - attribution
// centralization per TODO/20260529-boundary-rip-and-replace-plan.md).
//
// Previously each BoundaryEntry carried a multi-sentence per-source
// `attribution` HTML string that maplibre rendered into the bottom-right
// info pill. Long strings (especially the S03 Tier-4 district-fallback
// caveat) overflowed into the map canvas and read as noise to the
// citizen. The full per-source licensing + provenance now lives at
// `/about?section=maps`, and every map renders one short link instead.
//
// BASE_URL accommodates GitHub Pages deployment under a sub-path; in
// dev BASE_URL is `/` so the link resolves to `/about?section=maps`.
export function boundaryFooterHtml(base_url: string = "/"): string {
  const base = base_url.replace(/\/$/, "");
  return `<a href="${base}/about?section=maps">Boundary sources &amp; licensing</a>`;
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
};

// Per-state AC layers. Property `ac_no` (lowercase) = 1-based per-state
// constituency number, joins to candidates.constituency_eci_no in
// results.sqlite (= ECI eci_no). Post-D.7 (PR #431) the ramSeraph
// LGD release is the default for states where LGD's post-2023 slice
// passes the safety-net rule.
//
// S01 Andhra Pradesh swap landed via A.1.a (TODO/20260529-boundary-rip-
// and-replace-plan.md): LGD bundles legacy AP+TG ac_no 1-294 with names
// that don't 1:1 against the post-2014 AP-only SoT (eci_no 1-175), but
// reservation suffix on LGD ac_name + compound (name, reservation) join
// resolves it (175/175 name parity per verify_ac_parity --state S01).
// The snapshot pipeline rewrites LGD's pre-bifurcation ac_no -> SoT's
// post-bifurcation eci_no via tools/boundaries/snapshot.py
// `ac_no_rewrite.by_name_to_sot_eci_no`; LGD identity preserved on each
// feature as `lgd_legacy_ac_no` + `lgd_ac_id`. 3 LGD features dropped
// (no SoT match) but no SoT entry orphaned.
//
// S03 Assam swapped to T4 district fallback via A.1.b: Tier-1 LGD was
// pre-2023 (0.8% name parity to post-2023 SoT - silent citizen
// mis-binding); Tier-3 Aug 2023 Delimitation Order PDF
// (S.O. 3553(E), https://egazette.gov.in/WriteReadData/2023/248037.pdf)
// is text-only with 40-60h manual QGIS vectorisation effort (deferred
// to a future follow-up PR per
// notes/2026-05-29-s03-pdf-probe-verdict.md). T4 ships 126 features
// where each post-2023 AC carries its parent district's polygon as
// fallback geometry (parent_district_id + parent_district_lgd preserved
// on each feature). Citizen UX concession: map highlight is the parent
// district outline (coarser than AC cell), but heading + election
// results bind correctly to post-2023 SoT names. Generated by
// tools/boundaries/s03_t4_district_fallback.py.
//
// U08 (J&K) keeps `seat_id` because LGD has not yet published the
// post-2022 90-AC delimitation as of 2026-05-27.
export const STATE_AC: Record<string, BoundaryEntry> = {
  S01: {
    id: "S01-ac",
    label: "Andhra Pradesh — Assembly constituencies (post-2014 bifurcation)",
    geojson_local_path: "boundaries/in/ac/state=in_s01/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S22: {
    id: "S22-ac",
    label: "Tamil Nadu — Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s22/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S11: {
    id: "S11-ac",
    label: "Kerala — Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s11/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S25: {
    id: "S25-ac",
    label: "West Bengal — Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s25/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S03: {
    id: "S03-ac",
    label:
      "Assam - Assembly constituencies (post-2023 delimitation; district-fallback geometry)",
    geojson_local_path: "boundaries/in/ac/state=in_s03/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/districts/LGD_Districts.geojsonl.7z",
    join_property: "ac_no",
  },
  U07: {
    id: "U07-ac",
    label: "Puducherry — Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_u07/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  // A.2 (TODO/20260529-boundary-rip-and-replace-plan.md) - 24 additional
  // LGD-keyed AC layers covering the remaining states + UTs where the AC
  // shard exists under datasets/boundaries/in/ac/state=in_<lc>/all.geojson.
  // All entries below are post-D.7 R1 (PR #431) ramSeraph LGD release;
  // each feature carries `ac_no` (lowercase) + `State_LGD` per the
  // snapshot.py normalisation pipeline. No per-state caveat in the label
  // (none of these needed an A.1.b-style fallback - the LGD slice matched
  // SoT names within the safety-net threshold). Per A.3, attribution
  // string is NOT carried on the entry (one citizen footer link applies
  // to all maps; per-source explanation lives at /about?section=maps).
  // Listed in numerical state-code order for review-ability.
  S02: {
    id: "S02-ac",
    label: "Arunachal Pradesh - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s02/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S04: {
    id: "S04-ac",
    label: "Bihar - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s04/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S05: {
    id: "S05-ac",
    label: "Goa - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s05/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S06: {
    id: "S06-ac",
    label: "Gujarat - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s06/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S07: {
    id: "S07-ac",
    label: "Haryana - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s07/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S08: {
    id: "S08-ac",
    label: "Himachal Pradesh - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s08/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S10: {
    id: "S10-ac",
    label: "Karnataka - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s10/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S12: {
    id: "S12-ac",
    label: "Madhya Pradesh - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s12/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S13: {
    id: "S13-ac",
    label: "Maharashtra - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s13/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S14: {
    id: "S14-ac",
    label: "Manipur - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s14/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S15: {
    id: "S15-ac",
    label: "Meghalaya - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s15/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S16: {
    id: "S16-ac",
    label: "Mizoram - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s16/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S17: {
    id: "S17-ac",
    label: "Nagaland - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s17/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S18: {
    id: "S18-ac",
    label: "Odisha - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s18/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S19: {
    id: "S19-ac",
    label: "Punjab - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s19/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S20: {
    id: "S20-ac",
    label: "Rajasthan - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s20/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S21: {
    id: "S21-ac",
    label: "Sikkim - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s21/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S23: {
    id: "S23-ac",
    label: "Tripura - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s23/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S24: {
    id: "S24-ac",
    label: "Uttar Pradesh - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s24/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S26: {
    id: "S26-ac",
    label: "Chhattisgarh - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s26/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S27: {
    id: "S27-ac",
    label: "Jharkhand - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s27/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S28: {
    id: "S28-ac",
    label: "Uttarakhand - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s28/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  S29: {
    id: "S29-ac",
    label: "Telangana - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_s29/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
  },
  U05: {
    id: "U05-ac",
    label: "NCT of Delhi - Assembly constituencies",
    geojson_local_path: "boundaries/in/ac/state=in_u05/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "ac_no",
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
