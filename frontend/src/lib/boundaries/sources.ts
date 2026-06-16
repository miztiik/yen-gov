// Boundary source resolution for the map components.
//
// Three-tier strategy (highest priority first):
//   1. datasets/boundaries/in/manifest.json (produced by tools/boundaries/
//      build.py in CI — see docs/architecture/frontend/map.md). When present,
//      use the packed PMTiles via the pmtiles:// protocol.
//   2. Local GeoJSON snapshot under datasets/boundaries/in/<kind>/... in
//      the Hive partition layout (per ADR-0031 Amendment 2026-05-22 —
//      T.0d boundaries consolidation). Produced by tools/boundaries/
//      snapshot.py + emitted via the boundary_layer.csv ledger.
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
   * "boundaries/electoral/delim=2008/ac/state=tamil-nadu/all.geojson"
   * for the per-state electoral layers; "boundaries/in/states/all.geojson"
   * for the admin-spine layers). Preferred over the
   * upstream URL when present — it's an order of magnitude faster and
   * works offline. Populated by tools/boundaries/snapshot.py; Hive
   * partition layout per ADR-0031 Amendment 2026-05-22, with the
   * electoral subtree added by G10 of TODO/20260603-data-and-charting-
   * platform-reset-plan.md section 4 EL2.
   */
  geojson_local_path?: string;
  /** Direct upstream GeoJSON URL (last-resort fallback). */
  geojson_url: string;
  /**
   * Property name on each feature carrying the CANONICAL join key. As of
   * Row B3 (ADR-0049) this is `lgd_ac_id` for every covered AC state; the
   * map selection/highlight read this property and the citizen-facing
   * eci_no is recovered from the crosswalk (lgd_ac_id -> eci_no) by the
   * AC route wrapper. Unmapped states (S03 Assam district-fallback, U08
   * J&K seat_id) still ride their own non-canonical property.
   */
  join_property: string;
  /**
   * Optional eci_no-valued LABEL property (`ac_no`) retained beside the
   * canonical `join_property` after the Row B3 flip. The choropleth COLOUR
   * fill falls back to this label for the brief window before the
   * crosswalk lookup resolves (so covered polygons never flash blank) and
   * for features the crosswalk does not cover. Present on every covered AC
   * state; absent on the unmapped states whose `join_property` is already
   * the eci-valued/seat property.
   */
  join_property_label?: string;
  /**
   * Parallel join key carrying the canonical INTERNAL AC identifier
   * `lgd_ac_id` (ADR-0049, Row B1). Retained as an explicit contract
   * marker after Row B3 made `lgd_ac_id` the primary `join_property`;
   * present on every covered AC state (all except S03 Assam
   * district-fallback and U08 J&K seat_id).
   */
  join_property_lgd?: string;
}

// Single citizen-facing footer for ALL boundary layers (A.3 - attribution
// centralization per docs/archive/plans/20260529-boundary-rip-and-replace-plan.md;
// icon-only refinement per docs/archive/plans/20260530-boundary-followups-execution-plan.md
// Row 0.2).
//
// Previously each BoundaryEntry carried a multi-sentence per-source
// `attribution` HTML string that maplibre rendered into the bottom-right
// info pill. Long strings (especially the S03 Tier-4 district-fallback
// caveat) overflowed into the map canvas and read as noise to the
// citizen. The full per-source licensing + provenance now lives at
// `/about?section=maps`, and every map renders one short link instead.
//
// 2026-05-30: refined to icon-only. The visible label `Boundary sources
// & licensing` shifts to the `title` attribute (native HTML tooltip on
// hover) so the bottom-right pill stays a single unobtrusive glyph.
// One click on the glyph still navigates to `/about?section=maps` (the
// docs surface for boundary provenance). The text is preserved in
// `title` so a citizen who hovers gets the full label without having
// to click first.
//
// BASE_URL accommodates GitHub Pages deployment under a sub-path; in
// dev BASE_URL is `/` so the link resolves to `/about?section=maps`.
export function boundaryFooterHtml(base_url: string = "/"): string {
  const base = base_url.replace(/\/$/, "");
  return `<a href="${base}/about?section=maps" title="Boundary sources &amp; licensing">&#9432;</a>`;
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
// docs/archive/notes/2026-05-29-s03-pdf-probe-verdict.md). T4 ships 126 features
// where each post-2023 AC carries its parent district's polygon as
// fallback geometry (parent_district_id + parent_district_lgd preserved
// on each feature). Citizen UX concession: map highlight is the parent
// district outline (coarser than AC cell), but heading + election
// results bind correctly to post-2023 SoT names. Generated 2026-05-29 by
// a now-retired one-shot under tools/boundaries/ (G6 prune 2026-06-08).
//
// U08 (J&K) keeps `seat_id` because LGD has not yet published the
// post-2022 90-AC delimitation as of 2026-05-27.
export const STATE_AC: Record<string, BoundaryEntry> = {
  S01: {
    id: "S01-ac",
    label: "Andhra Pradesh — Assembly constituencies (post-2014 bifurcation)",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=andhra-pradesh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S22: {
    id: "S22-ac",
    label: "Tamil Nadu — Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=tamil-nadu/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S11: {
    id: "S11-ac",
    label: "Kerala — Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=kerala/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S25: {
    id: "S25-ac",
    label: "West Bengal — Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=west-bengal/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S03: {
    id: "S03-ac",
    label:
      "Assam - Assembly constituencies (post-2023 delimitation; district-fallback geometry)",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=assam/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/districts/LGD_Districts.geojsonl.7z",
    join_property: "ac_no",
  },
  U07: {
    id: "U07-ac",
    label: "Puducherry — Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=puducherry/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  // A.2 (docs/archive/plans/20260529-boundary-rip-and-replace-plan.md) - 24 additional
  // LGD-keyed AC layers covering the remaining states + UTs where the AC
  // shard exists under datasets/boundaries/electoral/delim=2008/ac/state=<lgd_slug>/all.geojson
  // (per G10 of TODO/20260603-data-and-charting-platform-reset-plan.md section 4 EL2;
  // previously under datasets/boundaries/electoral/delim=2008/ac/state=<lgd_slug>/all.geojson).
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
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=arunachal-pradesh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S04: {
    id: "S04-ac",
    label: "Bihar - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=bihar/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S05: {
    id: "S05-ac",
    label: "Goa - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=goa/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S06: {
    id: "S06-ac",
    label: "Gujarat - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=gujarat/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S07: {
    id: "S07-ac",
    label: "Haryana - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=haryana/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S08: {
    id: "S08-ac",
    label: "Himachal Pradesh - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=himachal-pradesh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S10: {
    id: "S10-ac",
    label: "Karnataka - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=karnataka/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S12: {
    id: "S12-ac",
    label: "Madhya Pradesh - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=madhya-pradesh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S13: {
    id: "S13-ac",
    label: "Maharashtra - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=maharashtra/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S14: {
    id: "S14-ac",
    label: "Manipur - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=manipur/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S15: {
    id: "S15-ac",
    label: "Meghalaya - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=meghalaya/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S16: {
    id: "S16-ac",
    label: "Mizoram - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=mizoram/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S17: {
    id: "S17-ac",
    label: "Nagaland - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=nagaland/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S18: {
    id: "S18-ac",
    label: "Odisha - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=odisha/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S19: {
    id: "S19-ac",
    label: "Punjab - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=punjab/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S20: {
    id: "S20-ac",
    label: "Rajasthan - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=rajasthan/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S21: {
    id: "S21-ac",
    label: "Sikkim - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=sikkim/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S23: {
    id: "S23-ac",
    label: "Tripura - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=tripura/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S24: {
    id: "S24-ac",
    label: "Uttar Pradesh - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=uttar-pradesh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S26: {
    id: "S26-ac",
    label: "Chhattisgarh - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=chhattisgarh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S27: {
    id: "S27-ac",
    label: "Jharkhand - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=jharkhand/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S28: {
    id: "S28-ac",
    label: "Uttarakhand - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=uttarakhand/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  S29: {
    id: "S29-ac",
    label: "Telangana - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=telangana/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  U05: {
    id: "U05-ac",
    label: "NCT of Delhi - Assembly constituencies",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=delhi/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z",
    join_property: "lgd_ac_id",
    join_property_label: "ac_no",
    join_property_lgd: "lgd_ac_id",
  },
  // J&K post-2022 delimitation (90 ACs). HTL/datameet still ship the
  // pre-delimitation 87-AC layer for J&K; shijithpk/2024_maps_supplement
  // georeferenced the J&K CEO official AC map PDF + an NIC map server into
  // a fresh GeoJSON. Property schema is non-HTL: join key is `seat_id`
  // (matches eci_no in datasets/data/entities/boundaries_sot/U08/constituencies.json,
  // cross-validated 2026-05-13). The file also contains one extra feature
  // with seat_id 9999 for PoK areas; renderers should ignore it for the
  // 90-AC choropleth.
  U08: {
    id: "U08-ac",
    label: "Jammu & Kashmir — Assembly constituencies (post-2022 delimitation)",
    geojson_local_path: "boundaries/electoral/delim=2008/ac/state=jammu-and-kashmir/all.geojson",
    geojson_url:
      "https://raw.githubusercontent.com/shijithpk/2024_maps_supplement/main/j_and_k_assembly_new_borders.geojson",
    join_property: "seat_id",
  },
};

// Per-state Development Block layers (the third LGD admin tier, between
// subdistricts and panchayats). Property `block_lgd` (lowercase numeric
// LGD code) joins to taxonomy.entities.lgd_code at the block grain.
// Shipped via C.1.b (docs/archive/plans/20260529-boundary-rip-and-replace-plan.md) -
// 35 state shards derived from ramSeraph's LGD_Blocks national geojsonl
// release (7,146 blocks total nationally; 670 features dropped without a
// state_lgd attribution). Lift pipeline: tools/boundaries/
// lift_blocks_national.py -> emits per-state Hive-partitioned GeoJSON
// FeatureCollections + upserts boundary_layer.csv rows.
//
// Per A.3, no per-entry attribution field (single citizen footer link
// via boundaryFooterHtml(); per-source explanation lives at
// /about?section=maps). All 36 entries use the same upstream URL: the
// frontend reads the local snapshot via `geojson_local_path` first and
// only falls back to `geojson_url` when the snapshot is absent.
//
// Coverage: 36 of 36 elective states/UTs. S24 (Uttar Pradesh) requires
// the lift script's auto-fallback path (C.1.c): at the standard
// coord_precision=3 the per-state shard renders to 12.8 MB — historically
// over the (then) 12 MB SNAPSHOT_BYTE_BUDGET (raised to 16 MB on
// 2026-06-12 for the AC coord_precision bump; the block-layer fallback
// remains in place because re-running the lift at coord_precision=3 has
// not been re-validated against the new ceiling). The lift drops S24 to
// coord_precision=2 (~1.1 km) before SKIP, landing the shard at
// ~2.2 MB / 822 features. The fallback is uniform script behaviour
// (NOT per-state config), recorded in
// datasets/data/entities/boundary_layer.csv as
// simplification_tolerance_deg per row.
export const BLOCK_BOUNDARY: Record<string, BoundaryEntry> = {
  S01: {
    id: "S01-block",
    label: "Andhra Pradesh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=andhra-pradesh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S02: {
    id: "S02-block",
    label: "Arunachal Pradesh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=arunachal-pradesh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S03: {
    id: "S03-block",
    label: "Assam - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=assam/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S04: {
    id: "S04-block",
    label: "Bihar - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=bihar/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S05: {
    id: "S05-block",
    label: "Goa - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=goa/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S06: {
    id: "S06-block",
    label: "Gujarat - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=gujarat/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S07: {
    id: "S07-block",
    label: "Haryana - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=haryana/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S08: {
    id: "S08-block",
    label: "Himachal Pradesh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=himachal-pradesh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S10: {
    id: "S10-block",
    label: "Karnataka - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=karnataka/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S11: {
    id: "S11-block",
    label: "Kerala - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=kerala/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S12: {
    id: "S12-block",
    label: "Madhya Pradesh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=madhya-pradesh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S13: {
    id: "S13-block",
    label: "Maharashtra - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=maharashtra/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S14: {
    id: "S14-block",
    label: "Manipur - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=manipur/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S15: {
    id: "S15-block",
    label: "Meghalaya - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=meghalaya/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S16: {
    id: "S16-block",
    label: "Mizoram - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=mizoram/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S17: {
    id: "S17-block",
    label: "Nagaland - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=nagaland/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S18: {
    id: "S18-block",
    label: "Odisha - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=odisha/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S19: {
    id: "S19-block",
    label: "Punjab - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=punjab/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S20: {
    id: "S20-block",
    label: "Rajasthan - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=rajasthan/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S21: {
    id: "S21-block",
    label: "Sikkim - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=sikkim/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S22: {
    id: "S22-block",
    label: "Tamil Nadu - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=tamil-nadu/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S23: {
    id: "S23-block",
    label: "Tripura - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=tripura/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  // S24 (Uttar Pradesh): block shard exceeds the (historical 12 MB,
  // raised to 16 MB on 2026-06-12 for the AC coord_precision bump)
  // SNAPSHOT_BYTE_BUDGET at the standard coord_precision=3 (~12.8 MB).
  // The lift script's auto-fallback (C.1.c) re-emits the over-budget
  // bucket at coord_precision=2 (~1.1 km) before SKIP; this lands UP
  // blocks at ~2.2 MB / 822 features. Precision heterogeneity is
  // invisible at choropleth zoom 6-10 (typical block size 10-50 km),
  // and the join_property remains the LGD id regardless of vertex
  // count, so no renderer-side special-case is needed. The actual
  // precision used per shard is recorded in
  // datasets/data/entities/boundary_layer.csv
  // (simplification_tolerance_deg: 0.01 for S24, 0.001 elsewhere).
  S24: {
    id: "S24-block",
    label: "Uttar Pradesh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=uttar-pradesh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S25: {
    id: "S25-block",
    label: "West Bengal - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=west-bengal/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S26: {
    id: "S26-block",
    label: "Chhattisgarh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=chhattisgarh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S27: {
    id: "S27-block",
    label: "Jharkhand - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=jharkhand/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S28: {
    id: "S28-block",
    label: "Uttarakhand - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=uttarakhand/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S29: {
    id: "S29-block",
    label: "Telangana - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=telangana/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U01: {
    id: "U01-block",
    label: "Andaman & Nicobar Islands - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=andaman-and-nicobar/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U02: {
    id: "U02-block",
    label: "Chandigarh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=chandigarh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U03: {
    id: "U03-block",
    label: "Dadra & Nagar Haveli and Daman & Diu - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=dadra-and-nagar-haveli-and-daman-and-diu/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U04: {
    id: "U04-block",
    label: "Lakshadweep - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=lakshadweep/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U05: {
    id: "U05-block",
    label: "NCT of Delhi - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=delhi/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U07: {
    id: "U07-block",
    label: "Puducherry - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=puducherry/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U08: {
    id: "U08-block",
    label: "Jammu & Kashmir - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=jammu-and-kashmir/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U09: {
    id: "U09-block",
    label: "Ladakh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=ladakh/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
};

// Per-(state, district) Gram-Panchayat layers - C.2.c registry.
//
// Panchayats sit one level BELOW blocks in the LGD admin hierarchy
// (gram-panchayat = elected village-cluster local body, 255k entities
// nationally per LGD homepage stats). Registry is keyed by
// `"{state_code}-{district_lgd}"` (e.g. `"S13-490"`) because the per-state
// shard size (UP: ~72k panchayats; MP: ~36k) would overwhelm the
// MapLibre GeoJSON source - district granularity bounds the render
// load to a few hundred polygons per layer at typical block-level zoom.
//
// Source-of-truth list of shards lives at
// `datasets/boundaries/in/panchayats/state=<lgd_slug>/district=<lgd>/all.geojson`
// (663 shards across 28 states/UTs, ramSeraph LGD_Panchayats live
// lift 2026-05-30, PR #446 C.2.b). The high-cardinality inventory is
// generated from `datasets/data/entities/boundary_encoding.csv` into
// `generated-sources.ts`; changing the shard corpus requires rerunning
// `tools/boundaries/generate_frontend_registry.py`.
//
// Coverage gap (9 states/UTs reserved for C.2.d Bhuvan gap-fill):
// S02 Arunachal Pradesh, S08 Himachal Pradesh, S14 Manipur, S16 Mizoram,
// S17 Nagaland, S21 Sikkim, U08 Jammu & Kashmir, U09 Ladakh (+ U06 not elective).
//
// Per-feature `gp_code` (lowercase, short-form) carries the LGD
// gram-panchayat numeric ID per the C.2.b live snapshot - distinct
// from blocks' `block_lgd` long-form (cross-layer schema divergence
// within the same ramSeraph maintainer; see
// `tools/boundaries/lift_panchayats_national.py` module-level constants).
// Panchayat shard inventory is generated in generated-sources.ts from boundary_encoding.csv.

// ECI state_code -> LGD-name slug map. Low-cardinality hand-authored
// registries use this to emit partition paths under the canonical
// `state=<lgd-slug>/` shape mandated by ADR-0050. The authoritative source is
// `datasets/taxonomy/lgd_states.json` (PR #555). Keep this constant in
// sync with that file whenever a state slug changes (rare; the LGD
// English name is the slug source).
export const ECI_TO_LGD_SLUG: Readonly<Record<string, string>> = {
  S01: "andhra-pradesh",
  S02: "arunachal-pradesh",
  S03: "assam",
  S04: "bihar",
  S05: "goa",
  S06: "gujarat",
  S07: "haryana",
  S08: "himachal-pradesh",
  S10: "karnataka",
  S11: "kerala",
  S12: "madhya-pradesh",
  S13: "maharashtra",
  S14: "manipur",
  S15: "meghalaya",
  S16: "mizoram",
  S17: "nagaland",
  S18: "odisha",
  S19: "punjab",
  S20: "rajasthan",
  S21: "sikkim",
  S22: "tamil-nadu",
  S23: "tripura",
  S24: "uttar-pradesh",
  S25: "west-bengal",
  S26: "chhattisgarh",
  S27: "jharkhand",
  S28: "uttarakhand",
  S29: "telangana",
  U01: "andaman-and-nicobar",
  U02: "chandigarh",
  U03: "dadra-and-nagar-haveli-and-daman-and-diu",
  U04: "lakshadweep",
  U05: "delhi",
  U07: "puducherry",
  U08: "jammu-and-kashmir",
  U09: "ladakh",
};

// State-name lookup for `PANCHAYAT_BOUNDARY_BY_DISTRICT` labels.
// Mirrors the citizen-readable names used by `BLOCK_BOUNDARY` above so
// the eventual district-picker UI (post-C.2.c, scope TBD) can render
// consistent state labels. Only the 28 covered states are listed; gap
// states are intentionally absent (any registry lookup for a
// non-covered state returns undefined - the contract test pins this).
export const PANCHAYAT_STATE_NAMES: Readonly<Record<string, string>> = {
  S01: "Andhra Pradesh",
  S03: "Assam",
  S04: "Bihar",
  S05: "Goa",
  S06: "Gujarat",
  S07: "Haryana",
  S10: "Karnataka",
  S11: "Kerala",
  S12: "Madhya Pradesh",
  S13: "Maharashtra",
  S15: "Meghalaya",
  S18: "Odisha",
  S19: "Punjab",
  S20: "Rajasthan",
  S22: "Tamil Nadu",
  S23: "Tripura",
  S24: "Uttar Pradesh",
  S25: "West Bengal",
  S26: "Chhattisgarh",
  S27: "Jharkhand",
  S28: "Uttarakhand",
  S29: "Telangana",
  U01: "Andaman & Nicobar Islands",
  U02: "Chandigarh",
  U03: "Dadra & Nagar Haveli and Daman & Diu",
  U04: "Lakshadweep",
  U05: "NCT of Delhi",
  U07: "Puducherry",
};

// Generated panchayat inventory is re-exported here so downstream imports
// keep the historical sources.ts public API.
export { PANCHAYAT_BOUNDARY_BY_DISTRICT, PANCHAYAT_DISTRICTS_BY_STATE } from "./generated-sources";

// Per-(state, ulb) ward layers - C.3.c registry.
//
// Wards sit one level BELOW the ULB (Urban Local Body) in the LGD admin
// hierarchy (a ward = electoral subdivision within a municipal corp /
// municipality / nagar panchayat, 70,419 entities nationally per the SBM
// Urban 2026-05 snapshot). Registry is keyed by `"{state_code}-{ulb_lgd}"`
// (e.g. `"S13-802640"`) because the per-state shard size (UP: ~30k wards
// across 638 ULBs; MH: ~25k across 410 ULBs) would overwhelm the
// MapLibre GeoJSON source - ULB granularity bounds the render load to a
// few hundred ward polygons per layer at typical municipal-zoom.
//
// Source-of-truth list of shards lives at
// `datasets/boundaries/in/wards/state=<lgd_slug>/ulb=<ulb_lgd>/all.geojson`
// (3,300 shards across 29 states/UTs, ramSeraph SBM_Wards live
// lift 2026-05-30, PR #450 C.3.b). The high-cardinality inventory is
// generated from `datasets/data/entities/boundary_encoding.csv` into
// `generated-sources.ts`; changing the shard corpus requires rerunning
// `tools/boundaries/generate_frontend_registry.py`.
//
// Coverage gap (7 states/UTs absent from SBM Urban, reserved for C.3.d
// gap-fill via LivingAtlas + WB AMRUT + Shillong Tier-1.5/Tier-2 sources):
// S02 Arunachal Pradesh, S14 Manipur, S15 Meghalaya, S16 Mizoram,
// S23 Tripura, U04 Lakshadweep, U09 Ladakh.
//
// Per-feature `wardcode` (concatenated-lowercase, MoHUA pre-LGD-era
// schema) carries the ward identifier per the C.3.b live snapshot -
// HETEROGENEOUS (mostly numeric strings + minority free-text like
// "Ward No 5"); the join uses the raw `wardcode` value as-is. The 3-
// convention rule LOCKED in C.3.b: blocks use long-form `block_lgd`,
// panchayats use short-form `gp_code`, wards use concatenated-lowercase
// `wardcode` (cross-layer schema divergence at the same ramSeraph
// maintainer; see `tools/boundaries/lift_wards_national.py` module-
// level constants).
// Ward shard inventory is generated in generated-sources.ts from boundary_encoding.csv.

// State-name lookup for `WARD_BOUNDARY_BY_ULB` labels.
// Mirrors the citizen-readable names used by `BLOCK_BOUNDARY` /
// `PANCHAYAT_STATE_NAMES` above so the eventual ULB-picker UI
// (post-C.3.c, scope TBD) can render consistent state labels. Only the
// 29 covered states/UTs are listed; gap states (S02 / S14 / S15 / S16 /
// S23 / U04 / U09) are intentionally absent (any registry lookup for a
// non-covered state returns undefined - the contract test pins this).
export const WARD_STATE_NAMES: Readonly<Record<string, string>> = {
  S01: "Andhra Pradesh",
  S03: "Assam",
  S04: "Bihar",
  S05: "Goa",
  S06: "Gujarat",
  S07: "Haryana",
  S08: "Himachal Pradesh",
  S10: "Karnataka",
  S11: "Kerala",
  S12: "Madhya Pradesh",
  S13: "Maharashtra",
  S17: "Nagaland",
  S18: "Odisha",
  S19: "Punjab",
  S20: "Rajasthan",
  S21: "Sikkim",
  S22: "Tamil Nadu",
  S24: "Uttar Pradesh",
  S25: "West Bengal",
  S26: "Chhattisgarh",
  S27: "Jharkhand",
  S28: "Uttarakhand",
  S29: "Telangana",
  U01: "Andaman & Nicobar Islands",
  U02: "Chandigarh",
  U03: "Dadra & Nagar Haveli and Daman & Diu",
  U05: "NCT of Delhi",
  U07: "Puducherry",
  U08: "Jammu & Kashmir",
};

// Generated ward inventory is re-exported here so downstream imports
// keep the historical sources.ts public API.
export { WARD_BOUNDARY_BY_ULB, WARDS_BY_STATE } from "./generated-sources";

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
  /**
   * 'pmtiles' (production vector tiles), 'geojson' (URL-based fetch
   * deferred to maplibre's internal source loader), or 'geojson-inline'
   * (yen-gov-fetched FeatureCollection — used when the topojson-first /
   * geojson-fallback contract in `boundaries.ts#loadBoundaryFromPath`
   * has already decoded the data, e.g. when a `.topojson` sibling won
   * the fallback race).
   */
  kind: "pmtiles" | "geojson" | "geojson-inline";
  /** URL the map source should load from. Empty string when kind = 'geojson-inline'. */
  url: string;
  /** Layer name inside a PMTiles container; ignored for GeoJSON. */
  source_layer?: string;
  /**
   * Pre-fetched FeatureCollection when kind = 'geojson-inline'. The
   * MapChoropleth source spec uses `{type: 'geojson', data: <this>}`
   * directly (instead of `data: <url>`) so maplibre does NOT re-fetch.
   * Populated by resolveSource() when the loader's topojson-first
   * fallback decoded the partition; absent otherwise.
   */
  data?: BoundaryFeatureCollection;
  /**
   * Wire encoding that fed the inline data ('topojson' | 'geojson').
   * Surfaced for instrumentation / bench harness diagnostics; ignored
   * by the map render path.
   */
  format?: "topojson" | "geojson";
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
import {
  loadBoundaryFromPath,
  type BoundaryFeatureCollection,
} from "../boundaries";

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
    // Route through the topojson-first / geojson-fallback contract
    // (boundaries.ts#loadBoundaryFromPath, P2.3 of the TopoJSON
    // migration plan). When a `.topojson` sibling exists, the loader
    // decodes it via topojson-client and returns the inline
    // FeatureCollection so maplibre does NOT re-fetch the `.geojson`
    // sibling. Falls through to a URL-based geojson source on any
    // failure (matches the prior contract; an absent file still
    // surfaces a load error on the map).
    //
    // geojson_local_path is rooted at `boundaries/in/...`; strip that
    // prefix to match loadBoundaryFromPath's expected relative shape.
    const relUnderBoundaries = entry.geojson_local_path.replace(
      /^boundaries\/in\//,
      "",
    );
    const { fc, format } = await loadBoundaryFromPath(relUnderBoundaries, entry.id);
    if (fc) {
      return {
        kind: "geojson-inline",
        url: "",
        data: fc,
        format: format ?? undefined,
      };
    }
    // Fallback to the URL form when the loader returned null (neither
    // sibling fetched cleanly). Preserves the prior surfaceable-error
    // behaviour at the maplibre layer.
    return { kind: "geojson", url: `${DATA_BASE}/${entry.geojson_local_path}` };
  }
  return { kind: "geojson", url: entry.geojson_url };
}

// ---------------------------------------------------------------------------
// National Parliament Parliamentary Constituency layer (PR-B4 of the UK-style
// elections experience plan). APPEND-ONLY — added at EOF so the topojson /
// boundary migration running in sibling worktrees never conflicts on the
// per-state AC entries above.
//
// 545 features (543 numbered PCs + 2 J&K-territory placeholders at
// ls_seat_code=999). shijithpk georeferenced the ECI Press Note No. 23 PDF
// images; researcher-grade, choropleth-only (see tools/boundaries/pipeline.json
// `kind:"pc"` $comment for the survey-grade caveat).
//
// JOIN KEY = `unique_id` (e.g. `S07_8`), NOT `ls_seat_code`. ECI numbers PCs
// per-state (Tamil Nadu 1..39, Karnataka 1..28, ...), so `ls_seat_code` alone
// collides across states for a NATIONAL choropleth. `unique_id` =
// `<state_ut_code>_<ls_seat_code>` is globally unique and matches the
// `join_key` the national loader emits (national-elections.ts
// `<state_code>_<pc_no>`). This deviates from the plan's `ls_seat_code` +
// int-coercion note, which assumed a globally-numbered key that the upstream
// GeoJSON does not carry (pipeline.json id_property_note: "Joining election
// results to geometry requires the (st_name, pc_no) tuple, not pc_no alone").
//
// CARTOGRAPHY CONTRACT: the 2 `ls_seat_code=999` placeholders cover J&K
// territory administered by Pakistan/China and MUST be rendered with a
// distinct treatment (diagonal hatch) and NEVER tinted with election colours.
// They carry no election winner, so they fall outside the choropleth `fills`
// map; renderers MUST pass `hatch_unmapped` to MapChoropleth so these features
// hatch instead of taking `default_fill`.
//
// No permalinked upstream release exists (the supplement repo ships per-state
// shards + reconstruction scripts, not a consolidated 545-feature artifact),
// so the local snapshot under DATA_BASE is the canonical source; `geojson_url`
// points at the supplement repo only as a provenance pointer of last resort.
//
// THIS IS THE delim=2024 ENTRY; the delim=2008 sibling lives at
// `INDIA_PC_2008` below. Route selects via `event.delim_year` in
// StateElection / NationalElection (LS 2024 -> INDIA_PC; LS 2019/2014/2009
// -> INDIA_PC_2008; pre-2009 -> placeholder card, no geometry on disk).
export const INDIA_PC: BoundaryEntry = {
  id: "india-pc",
  label: "India — Parliamentary Constituencies (2024 delimitation)",
  geojson_local_path: "boundaries/electoral/delim=2024/pc/all.geojson",
  geojson_url:
    "https://github.com/shijithpk/2024_maps_supplement",
  join_property: "unique_id",
};

// PC boundaries under the 2008 Delimitation Commission Order - operative for
// the 17th / 16th / 15th Parliament general elections (2019, 2014, 2009). 543
// features. Upstream: datameet/maps `india_pc_2019_simplified.geojson` (CC0
// 1.0, authored by Arun Ganesh as a simplified derivative of the DataMeet
// Trust raw shapefile under CC-BY-SA 2.5). Staged via
// `tools/boundaries/_prep_datameet_pc_2008.py` and emitted by
// `tools/boundaries/snapshot.py` to the on-disk path below; see
// `tools/boundaries/pipeline.json` for the per-entry $comment with the
// "Pre delimitation" carve-out narrative (the 6 states exempted from
// re-delimitation by the 2008 Order retain their 1976 boundaries; ECI
// conducted LS 2009 / 2014 / 2019 against those boundaries; honest to cite
// as delim=2008 because 2008 IS the operative Order).
//
// JOIN KEY differs from `INDIA_PC` (the delim=2024 sibling). Both use
// `unique_id` as the property NAME, but the SHAPE differs:
//   - INDIA_PC (delim=2024):   `<state_ut_code>_<ls_seat_code>` (numeric)
//   - INDIA_PC_2008:           `<state_ut_code>_<pc_name_slug>` (slugged)
// The delim=2008 layer is name-slug based because canonical
// `datasets/data/entities/electoral.csv` carries unreliable `eci_no` values
// for delim=2008 PCs (22 of 544 are zero; many of the populated values are
// misaligned with ECI's actual 2009 LS numbering — verified for HP, Kerala,
// Bihar, Tamil Nadu in the V6 pre-flight of plan
// TODO/20260612-pc-delim-2008-boundary-ingest-plan.md). The kebab-case PC
// name slug derived via `slugify(pc_name)` is the stable cross-source key.
// Frontend builders (StateElection / NationalElection PC winners) construct
// the matching key as `${state_code}_${slugify(row.name)}` for delim=2008
// events. The components stay grain-agnostic — they read
// `feature.properties[boundary.join_property]` and `row.unique_id` without
// caring about the underlying shape.
//
// SPECIAL CASE — Ladakh: the upstream datameet feature carries
// `st_name='Jammu & Kashmir'` for pc_no=4 "Ladakh" (the pre-2019 J&K state
// composite included Ladakh). At preprocessor time the Ladakh PC alone is
// split to `state_ut_code='U09'` while the other 5 J&K PCs map to `'U08'`
// (post-2019 J&K UT). This matches the temporal modelling in canonical
// `electoral.csv` where Ladakh is a separate `state=ladakh` entity.
export const INDIA_PC_2008: BoundaryEntry = {
  id: "india-pc-2008",
  label: "India — Parliamentary Constituencies (2008 delimitation)",
  geojson_local_path: "boundaries/electoral/delim=2008/pc/all.geojson",
  geojson_url:
    "https://github.com/datameet/maps/tree/master/parliamentary-constituencies",
  join_property: "unique_id",
};
