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

// Per-state Development Block layers (the third LGD admin tier, between
// subdistricts and panchayats). Property `block_lgd` (lowercase numeric
// LGD code) joins to taxonomy.entities.lgd_code at the block grain.
// Shipped via C.1.b (TODO/20260529-boundary-rip-and-replace-plan.md) -
// 35 state shards derived from ramSeraph's LGD_Blocks national geojsonl
// release (7,146 blocks total nationally; 670 features dropped without a
// state_lgd attribution). Lift pipeline: tools/boundaries/
// lift_blocks_national.py -> emits per-state Hive-partitioned GeoJSON
// FeatureCollections + upserts boundary_layers.parquet rows.
//
// Per A.3, no per-entry attribution field (single citizen footer link
// via boundaryFooterHtml(); per-source explanation lives at
// /about?section=maps). All 36 entries use the same upstream URL: the
// frontend reads the local snapshot via `geojson_local_path` first and
// only falls back to `geojson_url` when the snapshot is absent.
//
// Coverage: 36 of 36 elective states/UTs. S24 (Uttar Pradesh) requires
// the lift script's auto-fallback path (C.1.c): at the standard
// coord_precision=3 the per-state shard renders to 12.8 MB - 7% over
// the 12 MB SNAPSHOT_BYTE_BUDGET; the lift drops S24 to
// coord_precision=2 (~1.1 km) before SKIP, landing the shard at
// ~2.2 MB / 822 features. The fallback is uniform script behaviour
// (NOT per-state config), recorded in
// datasets/boundaries/boundary_layers.parquet as
// simplification_tolerance_deg per row.
export const BLOCK_BOUNDARY: Record<string, BoundaryEntry> = {
  S01: {
    id: "S01-block",
    label: "Andhra Pradesh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s01/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S02: {
    id: "S02-block",
    label: "Arunachal Pradesh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s02/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S03: {
    id: "S03-block",
    label: "Assam - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s03/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S04: {
    id: "S04-block",
    label: "Bihar - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s04/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S05: {
    id: "S05-block",
    label: "Goa - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s05/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S06: {
    id: "S06-block",
    label: "Gujarat - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s06/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S07: {
    id: "S07-block",
    label: "Haryana - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s07/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S08: {
    id: "S08-block",
    label: "Himachal Pradesh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s08/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S10: {
    id: "S10-block",
    label: "Karnataka - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s10/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S11: {
    id: "S11-block",
    label: "Kerala - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s11/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S12: {
    id: "S12-block",
    label: "Madhya Pradesh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s12/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S13: {
    id: "S13-block",
    label: "Maharashtra - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s13/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S14: {
    id: "S14-block",
    label: "Manipur - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s14/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S15: {
    id: "S15-block",
    label: "Meghalaya - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s15/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S16: {
    id: "S16-block",
    label: "Mizoram - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s16/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S17: {
    id: "S17-block",
    label: "Nagaland - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s17/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S18: {
    id: "S18-block",
    label: "Odisha - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s18/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S19: {
    id: "S19-block",
    label: "Punjab - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s19/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S20: {
    id: "S20-block",
    label: "Rajasthan - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s20/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S21: {
    id: "S21-block",
    label: "Sikkim - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s21/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S22: {
    id: "S22-block",
    label: "Tamil Nadu - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s22/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S23: {
    id: "S23-block",
    label: "Tripura - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s23/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  // S24 (Uttar Pradesh): block shard exceeds the 12 MB
  // SNAPSHOT_BYTE_BUDGET at the standard coord_precision=3 (~12.8 MB).
  // The lift script's auto-fallback (C.1.c) re-emits the over-budget
  // bucket at coord_precision=2 (~1.1 km) before SKIP; this lands UP
  // blocks at ~2.2 MB / 822 features. Precision heterogeneity is
  // invisible at choropleth zoom 6-10 (typical block size 10-50 km),
  // and the join_property remains the LGD id regardless of vertex
  // count, so no renderer-side special-case is needed. The actual
  // precision used per shard is recorded in
  // datasets/boundaries/boundary_layers.parquet
  // (simplification_tolerance_deg: 0.01 for S24, 0.001 elsewhere).
  S24: {
    id: "S24-block",
    label: "Uttar Pradesh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s24/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S25: {
    id: "S25-block",
    label: "West Bengal - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s25/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S26: {
    id: "S26-block",
    label: "Chhattisgarh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s26/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S27: {
    id: "S27-block",
    label: "Jharkhand - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s27/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S28: {
    id: "S28-block",
    label: "Uttarakhand - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s28/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  S29: {
    id: "S29-block",
    label: "Telangana - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_s29/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U01: {
    id: "U01-block",
    label: "Andaman & Nicobar Islands - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_u01/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U02: {
    id: "U02-block",
    label: "Chandigarh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_u02/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U03: {
    id: "U03-block",
    label: "Dadra & Nagar Haveli and Daman & Diu - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_u03/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U04: {
    id: "U04-block",
    label: "Lakshadweep - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_u04/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U05: {
    id: "U05-block",
    label: "NCT of Delhi - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_u05/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U07: {
    id: "U07-block",
    label: "Puducherry - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_u07/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U08: {
    id: "U08-block",
    label: "Jammu & Kashmir - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_u08/all.geojson",
    geojson_url:
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z",
    join_property: "block_lgd",
  },
  U09: {
    id: "U09-block",
    label: "Ladakh - Development Blocks",
    geojson_local_path: "boundaries/in/blocks/state=in_u09/all.geojson",
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
// `datasets/boundaries/in/panchayats/state=in_<lc>/district=<lgd>/all.geojson`
// (663 shards across 28 states/UTs, ramSeraph LGD_Panchayats live
// lift 2026-05-30, PR #446 C.2.b). The registry below is a compact
// construction over `PANCHAYAT_DISTRICTS_BY_STATE` - changing the
// shard corpus on disk REQUIRES re-emitting `PANCHAYAT_DISTRICTS_BY_STATE`
// to stay in sync. The `state-panchayats-registry-coverage` contract
// test locks this symmetry.
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
export const PANCHAYAT_DISTRICTS_BY_STATE: Readonly<Record<string, readonly number[]>> = {
  // Andhra Pradesh - 26 districts
  S01: [
    502, 503, 504, 505, 506, 510, 511, 515, 517, 519,
    520, 521, 523, 743, 744, 745, 746, 747, 748, 749,
    750, 751, 752, 753, 754, 755,
  ],
  // Assam - 35 districts
  S03: [
    280, 281, 282, 283, 284, 285, 286, 287, 288, 289,
    290, 291, 292, 293, 294, 295, 296, 297, 298, 299,
    300, 301, 302, 612, 616, 617, 618, 705, 706, 707,
    708, 709, 710, 739, 756,
  ],
  // Bihar - 38 districts
  S04: [
    188, 189, 190, 191, 192, 193, 194, 195, 196, 197,
    198, 199, 200, 201, 202, 203, 204, 205, 206, 207,
    208, 209, 210, 211, 212, 213, 214, 215, 216, 217,
    218, 219, 220, 221, 222, 223, 224, 611,
  ],
  // Goa - 2 districts
  S05: [551, 552],
  // Gujarat - 33 districts
  S06: [
    438, 439, 440, 441, 442, 443, 444, 445, 446, 447,
    448, 449, 450, 451, 452, 453, 454, 455, 456, 457,
    458, 459, 460, 461, 462, 641, 668, 669, 672, 673,
    674, 675, 676,
  ],
  // Haryana - 22 districts
  S07: [58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 604, 619, 701],
  // Karnataka - 31 districts
  S10: [
    524, 525, 526, 527, 528, 529, 530, 531, 532, 533,
    534, 535, 536, 537, 538, 539, 540, 541, 542, 543,
    544, 545, 546, 547, 548, 549, 550, 630, 631, 635,
    738,
  ],
  // Kerala - 14 districts
  S11: [554, 555, 556, 557, 558, 559, 560, 561, 562, 563, 564, 565, 566, 567],
  // Madhya Pradesh - 53 districts
  S12: [
    109, 390, 391, 392, 393, 394, 395, 396, 397, 398,
    399, 400, 401, 402, 403, 404, 405, 406, 407, 408,
    409, 410, 411, 412, 413, 414, 415, 416, 417, 418,
    419, 420, 421, 422, 423, 424, 425, 426, 427, 428,
    429, 430, 431, 432, 433, 434, 435, 436, 437, 638,
    639, 667, 722,
  ],
  // Maharashtra - 36 districts
  S13: [
    466, 467, 468, 469, 470, 471, 472, 473, 474, 475,
    476, 477, 478, 479, 480, 481, 482, 483, 484, 485,
    486, 487, 488, 489, 490, 491, 492, 493, 494, 495,
    496, 497, 498, 499, 500, 665,
  ],
  // Meghalaya - 1 district
  S15: [291],
  // Odisha - 30 districts
  S18: [
    344, 345, 346, 347, 348, 349, 350, 351, 352, 353,
    354, 355, 356, 357, 358, 359, 360, 361, 362, 363,
    364, 365, 366, 367, 368, 369, 370, 371, 372, 373,
  ],
  // Punjab - 23 districts
  S19: [
    27, 28, 29, 30, 31, 32, 33, 34, 35, 36,
    37, 38, 39, 40, 41, 42, 43, 605, 608, 609,
    651, 662, 737,
  ],
  // Rajasthan - 49 districts
  S20: [
    86, 87, 88, 89, 90, 91, 92, 93, 94, 95,
    96, 97, 98, 99, 100, 101, 102, 103, 104, 105,
    106, 107, 108, 109, 110, 111, 112, 113, 114, 115,
    116, 117, 629, 767, 768, 769, 770, 771, 772, 773,
    774, 775, 776, 777, 778, 780, 781, 782, 783,
  ],
  // Tamil Nadu - 38 districts
  S22: [
    568, 569, 570, 571, 572, 573, 574, 575, 576, 577,
    578, 579, 580, 581, 582, 583, 584, 585, 586, 587,
    588, 589, 590, 591, 592, 593, 594, 595, 596, 597,
    610, 634, 729, 730, 731, 732, 733, 735,
  ],
  // Tripura - 8 districts
  S23: [269, 270, 271, 272, 652, 653, 654, 655],
  // Uttar Pradesh - 75 districts
  S24: [
    118, 119, 120, 121, 122, 123, 124, 125, 126, 127,
    128, 129, 130, 131, 132, 133, 134, 135, 136, 137,
    138, 139, 140, 141, 142, 143, 144, 145, 146, 147,
    148, 149, 150, 151, 152, 153, 154, 155, 156, 157,
    158, 159, 160, 161, 162, 163, 164, 165, 166, 167,
    168, 169, 170, 171, 172, 173, 174, 175, 176, 177,
    178, 179, 180, 181, 182, 183, 184, 185, 186, 187,
    633, 640, 659, 660, 661,
  ],
  // West Bengal - 23 districts
  S25: [
    303, 304, 305, 306, 307, 308, 309, 310, 311, 312,
    313, 314, 315, 316, 317, 318, 319, 320, 321, 664,
    702, 703, 704,
  ],
  // Chhattisgarh - 33 districts
  S26: [
    374, 375, 376, 377, 378, 379, 380, 381, 382, 383,
    384, 385, 386, 387, 388, 389, 636, 637, 642, 643,
    644, 645, 646, 647, 648, 649, 650, 734, 759, 760,
    761, 762, 763,
  ],
  // Jharkhand - 24 districts
  S27: [
    322, 323, 324, 325, 326, 327, 328, 329, 330, 331,
    332, 333, 334, 335, 336, 337, 338, 339, 340, 341,
    342, 343, 606, 607,
  ],
  // Uttarakhand - 13 districts
  S28: [45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
  // Telangana - 33 districts
  S29: [
    501, 507, 508, 509, 512, 513, 514, 516, 518, 522,
    680, 681, 682, 683, 684, 685, 686, 687, 688, 689,
    690, 691, 692, 693, 694, 695, 696, 697, 698, 699,
    700, 720, 721,
  ],
  // Andaman & Nicobar Islands - 3 districts
  U01: [602, 603, 632],
  // Chandigarh - 1 district
  U02: [44],
  // Dadra & Nagar Haveli and Daman & Diu - 3 districts
  U03: [463, 464, 465],
  // Lakshadweep - 1 district
  U04: [553],
  // NCT of Delhi - 11 districts
  U05: [77, 78, 79, 80, 81, 82, 83, 84, 85, 670, 671],
  // Puducherry - 4 districts
  U07: [598, 599, 600, 601],
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

// Constructed per-(state, district) registry. Lazy at first read; the
// 663-entry Record is built once via `Object.fromEntries`. Each entry
// shape mirrors `BLOCK_BOUNDARY` (id / label / geojson_local_path /
// geojson_url / join_property) so the existing `resolveSource()` resolver
// works unchanged.
//
// Key format: `"{state_code}-{district_lgd}"` (e.g. `"S13-490"`).
// Look-up by district picker: `PANCHAYAT_BOUNDARY_BY_DISTRICT[`${stateCode}-${distLgd}`]`.
const PANCHAYAT_UPSTREAM_URL =
  "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/panchayats/LGD_Panchayats.geojsonl.7z";

export const PANCHAYAT_BOUNDARY_BY_DISTRICT: Readonly<Record<string, BoundaryEntry>> = Object.freeze(
  Object.fromEntries(
    Object.entries(PANCHAYAT_DISTRICTS_BY_STATE).flatMap(([state_code, districts]) =>
      districts.map((district_lgd): [string, BoundaryEntry] => {
        const key = `${state_code}-${district_lgd}`;
        const state_name = PANCHAYAT_STATE_NAMES[state_code] ?? state_code;
        return [
          key,
          {
            id: `${key}-panchayat`,
            label: `${state_name} \u2014 District LGD ${district_lgd} (Gram Panchayats)`,
            geojson_local_path: `boundaries/in/panchayats/state=in_${state_code.toLowerCase()}/district=${district_lgd}/all.geojson`,
            geojson_url: PANCHAYAT_UPSTREAM_URL,
            join_property: "gp_code",
          },
        ];
      }),
    ),
  ),
);

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
