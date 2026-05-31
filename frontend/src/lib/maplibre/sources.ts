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
  // A.2 (docs/archive/plans/20260529-boundary-rip-and-replace-plan.md) - 24 additional
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
// Shipped via C.1.b (docs/archive/plans/20260529-boundary-rip-and-replace-plan.md) -
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

// TODO(C.2.c): wire district-picker on state selection. Citizen surface
// must let the user pick a state -> then a district within that state's
// PANCHAYAT_DISTRICTS_BY_STATE[stateCode] list -> then resolve the entry
// here. Tracked in docs/archive/plans/20260530-boundary-plan-followups.md Category 3
// (UX follow-up, Value MED, effort M); marker shipped via Row 4.1.
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
// `datasets/boundaries/in/wards/state=in_<lc>/ulb=<ulb_lgd>/all.geojson`
// (3,300 shards across 29 states/UTs, ramSeraph SBM_Wards live
// lift 2026-05-30, PR #450 C.3.b). The registry below is a compact
// construction over `WARDS_BY_STATE` - changing the shard corpus
// on disk REQUIRES re-emitting `WARDS_BY_STATE` to stay in sync. The
// `state-wards-registry-coverage` contract test locks this symmetry.
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
export const WARDS_BY_STATE: Readonly<Record<string, readonly number[]>> = {
  // Andhra Pradesh - 104 ULBs
  S01: [
    802938, 802940, 802941, 802942, 802943, 802944, 802945, 802946, 802947, 802950,
    802951, 802952, 802953, 802954, 802955, 802956, 802957, 802958, 802959, 802960,
    802961, 802962, 802963, 802964, 802965, 802966, 802967, 802969, 802970, 802971,
    802972, 802973, 802974, 802977, 802978, 802979, 802980, 802981, 802982, 802983,
    802984, 802985, 802986, 802987, 802988, 802989, 802990, 802991, 802992, 802993,
    802994, 802995, 802996, 802997, 802998, 802999, 803000, 803001, 803002, 803003,
    803004, 803005, 803006, 803007, 803009, 803010, 803011, 803012, 803013, 803014,
    803015, 803016, 803017, 803018, 803019, 803020, 900001, 900063, 900064, 900076,
    900077, 900078, 900080, 900081, 900082, 900084, 900087, 900088, 900089, 900090,
    900092, 900093, 900094, 900095, 900098, 900099, 900100, 900101, 900102, 900104,
    900129, 900148, 900149, 900153,
  ],
  // Assam - 58 ULBs
  S03: [
    801546, 801548, 801549, 801550, 801551, 801552, 801553, 801556, 801557, 801558,
    801559, 801560, 801561, 801563, 801570, 801571, 801572, 801575, 801576, 801577,
    801578, 801579, 801580, 801581, 801582, 801583, 801584, 801585, 801587, 801588,
    801597, 801598, 801599, 801600, 801601, 801602, 801603, 801606, 801607, 801608,
    801609, 801610, 801611, 801613, 801615, 801617, 801619, 801621, 801624, 801625,
    801632, 801633, 900008, 900073, 900074, 900075, 900323, 900324,
  ],
  // Bihar - 58 ULBs
  S04: [
    801281, 801285, 801295, 801301, 801310, 801312, 801314, 801318, 801319, 801320,
    801324, 801329, 801332, 801333, 801335, 801336, 801338, 801339, 801340, 801344,
    801345, 801346, 801349, 801351, 801353, 801354, 801356, 801357, 801358, 801360,
    801363, 801364, 801365, 801367, 801369, 801370, 801372, 801373, 801374, 801378,
    801379, 801381, 801382, 801383, 801385, 801390, 801391, 801392, 801397, 801398,
    801401, 801404, 801406, 801407, 801411, 801413, 801415, 900096,
  ],
  // Goa - 7 ULBs
  S05: [
    803241, 803243, 803246, 803247, 803248, 803250, 803254,
  ],
  // Gujarat - 164 ULBs
  S06: [
    802442, 802443, 802444, 802445, 802446, 802447, 802448, 802449, 802450, 802451,
    802452, 802453, 802454, 802455, 802456, 802457, 802458, 802459, 802460, 802461,
    802462, 802463, 802464, 802465, 802466, 802467, 802468, 802469, 802470, 802471,
    802472, 802473, 802475, 802477, 802479, 802480, 802481, 802482, 802483, 802484,
    802485, 802486, 802487, 802488, 802489, 802490, 802491, 802492, 802493, 802495,
    802496, 802497, 802498, 802499, 802500, 802501, 802503, 802504, 802505, 802506,
    802507, 802508, 802510, 802511, 802512, 802513, 802516, 802517, 802518, 802519,
    802520, 802521, 802522, 802524, 802525, 802526, 802527, 802528, 802529, 802530,
    802531, 802532, 802533, 802534, 802535, 802536, 802537, 802538, 802539, 802540,
    802541, 802542, 802543, 802544, 802545, 802546, 802547, 802548, 802549, 802550,
    802551, 802552, 802553, 802554, 802555, 802557, 802558, 802559, 802560, 802561,
    802562, 802563, 802564, 802566, 802567, 802568, 802570, 802571, 802572, 802573,
    802574, 802575, 802576, 802577, 802578, 802579, 802580, 802581, 802582, 802583,
    802584, 802585, 802586, 802588, 802589, 802590, 802591, 802592, 802596, 802599,
    802600, 802601, 802602, 802603, 802604, 802605, 802607, 802608, 802614, 802616,
    802617, 802618, 802620, 802621, 802622, 802625, 802627, 802628, 802629, 802634,
    802635, 802636, 900198, 900605,
  ],
  // Haryana - 81 ULBs
  S07: [
    800363, 800364, 800365, 800366, 800367, 800369, 800370, 800371, 800372, 800373,
    800374, 800375, 800376, 800377, 800378, 800379, 800380, 800381, 800382, 800383,
    800384, 800385, 800386, 800387, 800388, 800389, 800390, 800391, 800392, 800393,
    800394, 800395, 800396, 800397, 800398, 800399, 800400, 800401, 800402, 800404,
    800405, 800406, 800407, 800408, 800409, 800410, 800411, 800413, 800414, 800415,
    800416, 800417, 800418, 800419, 800420, 800421, 800422, 800423, 800424, 800425,
    800426, 800427, 800428, 800429, 800430, 800431, 800432, 800433, 800434, 800435,
    800436, 800437, 800438, 800440, 900115, 900116, 900117, 900227, 900228, 900322,
    900513,
  ],
  // Himachal Pradesh - 58 ULBs
  S08: [
    800088, 800090, 800091, 800092, 800093, 800095, 800096, 800097, 800098, 800099,
    800100, 800101, 800102, 800103, 800104, 800105, 800106, 800107, 800108, 800109,
    800110, 800111, 800112, 800113, 800114, 800115, 800116, 800117, 800118, 800119,
    800120, 800121, 800122, 800123, 800124, 800126, 800128, 800130, 800131, 800132,
    800134, 800137, 800138, 800139, 800140, 800141, 800142, 900134, 900238, 900460,
    900470, 900805, 900806, 900807, 900808, 900809, 900810, 900811,
  ],
  // Karnataka - 231 ULBs
  S10: [
    803021, 803023, 803025, 803026, 803027, 803028, 803030, 803032, 803033, 803036,
    803037, 803038, 803039, 803041, 803042, 803043, 803044, 803045, 803046, 803048,
    803050, 803051, 803052, 803053, 803054, 803055, 803056, 803057, 803059, 803060,
    803061, 803062, 803063, 803064, 803066, 803067, 803068, 803069, 803070, 803071,
    803072, 803073, 803074, 803075, 803076, 803077, 803078, 803079, 803080, 803081,
    803082, 803083, 803085, 803086, 803087, 803088, 803089, 803090, 803091, 803092,
    803093, 803094, 803095, 803096, 803097, 803098, 803099, 803100, 803101, 803102,
    803103, 803104, 803105, 803106, 803107, 803109, 803110, 803111, 803112, 803113,
    803114, 803115, 803116, 803117, 803118, 803119, 803120, 803121, 803122, 803123,
    803124, 803126, 803127, 803128, 803129, 803131, 803132, 803133, 803134, 803135,
    803136, 803137, 803138, 803139, 803140, 803143, 803144, 803145, 803146, 803147,
    803148, 803150, 803152, 803153, 803154, 803155, 803156, 803157, 803158, 803159,
    803161, 803162, 803163, 803164, 803166, 803167, 803168, 803169, 803172, 803173,
    803174, 803175, 803176, 803177, 803178, 803179, 803180, 803181, 803183, 803185,
    803186, 803187, 803188, 803189, 803190, 803191, 803192, 803193, 803194, 803195,
    803196, 803197, 803198, 803199, 803200, 803201, 803202, 803203, 803204, 803205,
    803207, 803208, 803209, 803210, 803212, 803213, 803214, 803215, 803217, 803218,
    803219, 803220, 803221, 803222, 803223, 803226, 803227, 803228, 803229, 803230,
    803231, 803233, 803234, 803235, 803236, 803237, 803238, 803239, 803240, 900360,
    900361, 900374, 900375, 900376, 900383, 900384, 900386, 900387, 900388, 900389,
    900390, 900392, 900393, 900396, 900398, 900399, 900400, 900401, 900402, 900407,
    900409, 900411, 900412, 900416, 900420, 900422, 900423, 900424, 900425, 900426,
    900427, 900428, 900429, 900430, 900434, 900435, 900436, 900608, 900666, 900668,
    900777,
  ],
  // Kerala - 75 ULBs
  S11: [
    803256, 803257, 803261, 803262, 803263, 803264, 803265, 803266, 803267, 803268,
    803270, 803271, 803272, 803273, 803274, 803275, 803276, 803277, 803278, 803279,
    803280, 803281, 803282, 803283, 803284, 803285, 803286, 803287, 803288, 803289,
    803290, 803291, 803292, 803293, 803294, 803295, 803297, 803298, 803299, 803300,
    803302, 803304, 803305, 803306, 803307, 803309, 803310, 803311, 803312, 803313,
    900009, 900011, 900130, 900151, 900175, 900199, 900201, 900202, 900205, 900206,
    900207, 900208, 900209, 900211, 900212, 900213, 900216, 900218, 900219, 900221,
    900222, 900223, 900224, 900225, 900235,
  ],
  // Madhya Pradesh - 335 ULBs
  S12: [
    801579, 802078, 802079, 802080, 802081, 802082, 802083, 802084, 802085, 802086,
    802087, 802088, 802089, 802090, 802091, 802092, 802093, 802094, 802095, 802096,
    802097, 802098, 802099, 802100, 802102, 802103, 802104, 802105, 802106, 802107,
    802108, 802109, 802110, 802111, 802112, 802113, 802114, 802115, 802116, 802117,
    802118, 802124, 802127, 802128, 802129, 802130, 802132, 802133, 802134, 802137,
    802138, 802139, 802141, 802142, 802143, 802144, 802145, 802146, 802147, 802148,
    802149, 802150, 802151, 802152, 802153, 802154, 802155, 802156, 802157, 802159,
    802161, 802162, 802163, 802164, 802165, 802166, 802167, 802168, 802169, 802170,
    802171, 802172, 802173, 802174, 802175, 802176, 802177, 802178, 802179, 802180,
    802181, 802182, 802183, 802184, 802185, 802186, 802187, 802188, 802189, 802190,
    802191, 802192, 802193, 802194, 802195, 802196, 802197, 802198, 802199, 802200,
    802201, 802202, 802203, 802204, 802205, 802206, 802207, 802208, 802209, 802210,
    802211, 802212, 802213, 802214, 802215, 802216, 802217, 802218, 802219, 802220,
    802221, 802222, 802223, 802224, 802225, 802226, 802227, 802228, 802230, 802231,
    802232, 802233, 802234, 802235, 802236, 802237, 802238, 802239, 802240, 802241,
    802243, 802244, 802245, 802246, 802247, 802248, 802249, 802250, 802251, 802252,
    802253, 802254, 802255, 802256, 802257, 802258, 802259, 802260, 802261, 802262,
    802263, 802264, 802265, 802266, 802267, 802268, 802270, 802271, 802272, 802273,
    802274, 802275, 802276, 802279, 802280, 802281, 802282, 802284, 802285, 802286,
    802287, 802288, 802289, 802290, 802291, 802293, 802298, 802301, 802303, 802308,
    802310, 802312, 802314, 802316, 802318, 802319, 802320, 802321, 802322, 802323,
    802325, 802327, 802329, 802330, 802333, 802334, 802335, 802336, 802337, 802338,
    802339, 802340, 802342, 802343, 802344, 802345, 802346, 802349, 802350, 802351,
    802352, 802353, 802354, 802356, 802358, 802359, 802360, 802361, 802362, 802363,
    802366, 802368, 802371, 802373, 802376, 802377, 802378, 802379, 802382, 802384,
    802386, 802387, 802388, 802389, 802390, 802391, 802393, 802395, 802396, 802397,
    802399, 802401, 802402, 802403, 802404, 802405, 802406, 802407, 802408, 802409,
    802410, 802411, 802412, 802413, 802414, 802415, 802416, 802417, 802418, 802419,
    802420, 802421, 802422, 802423, 802424, 802425, 802426, 802427, 802428, 802429,
    802430, 802431, 802432, 802433, 802434, 802435, 802437, 802438, 802439, 802440,
    802441, 900154, 900155, 900156, 900157, 900159, 900160, 900161, 900162, 900164,
    900165, 900166, 900167, 900168, 900169, 900170, 900171, 900172, 900680, 900681,
    900682, 900683, 900684, 900685, 900686, 900687, 900688, 900689, 900690, 900691,
    900692, 900693, 900694, 900695, 900703,
  ],
  // Maharashtra - 410 ULBs
  S13: [
    802640, 802641, 802642, 802643, 802644, 802645, 802646, 802647, 802648, 802649,
    802650, 802651, 802652, 802653, 802654, 802655, 802656, 802657, 802658, 802659,
    802660, 802661, 802662, 802663, 802664, 802665, 802666, 802667, 802668, 802669,
    802670, 802671, 802672, 802673, 802674, 802675, 802676, 802677, 802678, 802679,
    802680, 802681, 802682, 802683, 802684, 802685, 802686, 802687, 802688, 802689,
    802690, 802691, 802692, 802693, 802694, 802695, 802696, 802697, 802698, 802699,
    802700, 802701, 802702, 802703, 802704, 802705, 802706, 802707, 802708, 802709,
    802710, 802711, 802712, 802713, 802714, 802715, 802716, 802717, 802718, 802719,
    802720, 802721, 802722, 802723, 802724, 802725, 802726, 802727, 802728, 802729,
    802730, 802731, 802732, 802733, 802734, 802735, 802736, 802737, 802738, 802739,
    802740, 802741, 802743, 802744, 802745, 802746, 802747, 802748, 802749, 802750,
    802751, 802752, 802753, 802754, 802755, 802756, 802757, 802758, 802759, 802760,
    802761, 802762, 802763, 802764, 802765, 802766, 802767, 802768, 802769, 802770,
    802771, 802772, 802773, 802774, 802775, 802776, 802777, 802778, 802779, 802780,
    802781, 802782, 802783, 802784, 802785, 802786, 802787, 802788, 802789, 802790,
    802791, 802792, 802793, 802794, 802795, 802796, 802797, 802798, 802799, 802800,
    802801, 802802, 802803, 802804, 802805, 802806, 802807, 802808, 802809, 802810,
    802811, 802814, 802815, 802816, 802817, 802818, 802819, 802820, 802821, 802822,
    802823, 802824, 802825, 802826, 802827, 802828, 802829, 802830, 802831, 802832,
    802833, 802834, 802835, 802836, 802837, 802838, 802839, 802840, 802841, 802842,
    802843, 802844, 802845, 802846, 802847, 802848, 802849, 802850, 802851, 802852,
    802853, 802854, 802855, 802856, 802857, 802858, 802859, 802860, 802861, 802862,
    802863, 802864, 802865, 802866, 802867, 802868, 802869, 802870, 802871, 802872,
    802873, 802874, 802875, 802876, 802877, 802878, 802879, 802880, 802881, 802882,
    802883, 802884, 802885, 802886, 802887, 802888, 802889, 802890, 802891, 802892,
    802893, 802894, 802895, 900013, 900025, 900026, 900027, 900131, 900132, 900133,
    900143, 900152, 900178, 900182, 900184, 900185, 900194, 900226, 900233, 900236,
    900237, 900252, 900253, 900254, 900255, 900256, 900257, 900258, 900259, 900260,
    900261, 900262, 900263, 900264, 900266, 900267, 900268, 900269, 900271, 900272,
    900273, 900275, 900276, 900277, 900278, 900279, 900280, 900281, 900282, 900283,
    900284, 900285, 900286, 900287, 900288, 900289, 900290, 900291, 900292, 900293,
    900294, 900295, 900296, 900297, 900298, 900299, 900300, 900301, 900302, 900303,
    900304, 900305, 900306, 900307, 900308, 900309, 900310, 900311, 900312, 900313,
    900314, 900315, 900316, 900317, 900318, 900319, 900320, 900321, 900326, 900327,
    900328, 900329, 900330, 900331, 900332, 900333, 900334, 900336, 900337, 900338,
    900339, 900340, 900341, 900342, 900343, 900344, 900345, 900346, 900347, 900348,
    900349, 900350, 900351, 900352, 900353, 900354, 900355, 900356, 900357, 900358,
    900359, 900362, 900363, 900366, 900367, 900370, 900371, 900372, 900373, 900377,
    900378, 900379, 900385, 900461, 900490, 900584, 900585, 900586, 900587, 900588,
    900589, 900590, 900591, 900592, 900593, 900594, 900749, 900750, 900751, 900752,
    900753, 900858, 900859, 900860, 900861, 900862, 900863, 900866, 900867, 900868,
  ],
  // Nagaland - 7 ULBs
  S17: [
    801455, 801456, 801459, 900796, 900797, 900798, 900803,
  ],
  // Odisha - 99 ULBs
  S18: [
    801803, 801804, 801806, 801807, 801808, 801809, 801813, 801814, 801815, 801816,
    801818, 801819, 801821, 801822, 801823, 801824, 801826, 801827, 801828, 801831,
    801832, 801833, 801835, 801836, 801837, 801838, 801839, 801841, 801842, 801843,
    801844, 801845, 801846, 801847, 801848, 801849, 801850, 801851, 801852, 801854,
    801855, 801856, 801857, 801858, 801859, 801860, 801861, 801862, 801863, 801864,
    801865, 801866, 801867, 801868, 801869, 801870, 801871, 801872, 801873, 801874,
    801876, 801877, 801878, 801879, 801880, 801881, 801882, 801883, 801884, 801885,
    801886, 801887, 801888, 801889, 801890, 801891, 801892, 801893, 801894, 801895,
    801896, 801897, 801898, 801899, 801900, 801901, 801902, 801904, 801906, 801909,
    900079, 900085, 900180, 900186, 900187, 900190, 900191, 900493, 900495,
  ],
  // Punjab - 164 ULBs
  S19: [
    800143, 800144, 800145, 800146, 800147, 800148, 800149, 800150, 800151, 800152,
    800153, 800154, 800155, 800156, 800157, 800158, 800159, 800160, 800161, 800162,
    800163, 800164, 800165, 800166, 800167, 800168, 800169, 800170, 800171, 800172,
    800173, 800174, 800175, 800176, 800177, 800178, 800179, 800180, 800181, 800182,
    800183, 800184, 800185, 800186, 800187, 800188, 800189, 800190, 800191, 800192,
    800193, 800194, 800195, 800196, 800197, 800198, 800199, 800200, 800201, 800202,
    800203, 800204, 800205, 800206, 800207, 800209, 800210, 800211, 800212, 800213,
    800214, 800215, 800216, 800217, 800218, 800219, 800220, 800221, 800222, 800223,
    800224, 800225, 800226, 800227, 800228, 800229, 800230, 800231, 800232, 800233,
    800234, 800235, 800236, 800237, 800238, 800239, 800240, 800241, 800242, 800243,
    800244, 800245, 800246, 800247, 800248, 800249, 800251, 800252, 800253, 800254,
    800255, 800256, 800257, 800258, 800259, 800260, 800261, 800262, 800263, 800264,
    800265, 800266, 800267, 800268, 800269, 800270, 800271, 800272, 800273, 800274,
    800275, 800276, 800277, 800278, 800279, 800280, 800281, 800282, 800283, 800284,
    800285, 900024, 900043, 900044, 900045, 900046, 900047, 900048, 900052, 900053,
    900054, 900055, 900056, 900057, 900058, 900059, 900060, 900061, 900062, 900107,
    900176, 900482, 900483, 900485,
  ],
  // Rajasthan - 202 ULBs
  S20: [
    800444, 800445, 800446, 800448, 800449, 800450, 800451, 800452, 800453, 800454,
    800455, 800456, 800457, 800458, 800459, 800460, 800461, 800462, 800463, 800464,
    800466, 800467, 800468, 800470, 800471, 800472, 800473, 800474, 800475, 800476,
    800478, 800479, 800480, 800481, 800482, 800483, 800484, 800485, 800486, 800487,
    800488, 800489, 800490, 800491, 800492, 800493, 800494, 800495, 800496, 800497,
    800498, 800499, 800500, 800501, 800502, 800503, 800504, 800505, 800506, 800507,
    800508, 800509, 800510, 800511, 800512, 800513, 800514, 800515, 800516, 800517,
    800518, 800519, 800520, 800521, 800522, 800523, 800524, 800525, 800526, 800527,
    800528, 800529, 800530, 800531, 800532, 800533, 800534, 800535, 800536, 800537,
    800538, 800543, 800544, 800545, 800546, 800547, 800548, 800549, 800550, 800551,
    800552, 800553, 800554, 800555, 800556, 800557, 800558, 800559, 800560, 800561,
    800562, 800563, 800564, 800565, 800566, 800567, 800568, 800569, 800570, 800571,
    800572, 800573, 800574, 800575, 800576, 800577, 800578, 800579, 800580, 800581,
    800582, 800583, 800584, 800585, 800586, 800587, 800588, 800589, 800590, 800591,
    800592, 800593, 800594, 800595, 800596, 800597, 800598, 800599, 800600, 800601,
    800602, 800603, 800604, 800605, 800606, 800607, 800608, 800609, 800610, 800611,
    800612, 800613, 800614, 800615, 800616, 800617, 800618, 800619, 800620, 800621,
    800622, 800623, 800624, 800625, 800626, 800627, 800628, 900137, 900192, 900380,
    900382, 900496, 900595, 900596, 900597, 900598, 900599, 900600, 900705, 900707,
    900708, 900709, 900710, 900712, 900713, 900714, 900715, 900716, 900717, 900719,
    900720, 900721,
  ],
  // Sikkim - 6 ULBs
  S21: [
    801416, 801417, 801419, 801421, 801422, 801423,
  ],
  // Tamil Nadu - 128 ULBs
  S22: [
    803323, 803339, 803361, 803365, 803375, 803376, 803382, 803384, 803385, 803386,
    803387, 803392, 803398, 803404, 803406, 803409, 803410, 803412, 803413, 803414,
    803415, 803422, 803427, 803431, 803435, 803440, 803446, 803452, 803454, 803458,
    803463, 803473, 803474, 803482, 803484, 803486, 803493, 803495, 803497, 803505,
    803509, 803517, 803523, 803542, 803558, 803560, 803564, 803570, 803576, 803579,
    803595, 803602, 803604, 803623, 803629, 803634, 803635, 803639, 803643, 803645,
    803648, 803649, 803652, 803657, 803678, 803684, 803686, 803687, 803688, 803698,
    803702, 803709, 803711, 803712, 803718, 803724, 803733, 803734, 803736, 803738,
    803741, 803749, 803753, 803760, 803767, 803769, 803770, 803777, 803783, 803784,
    803801, 803802, 803805, 803810, 803812, 803813, 803814, 803821, 803839, 803841,
    803842, 803843, 803863, 803864, 803886, 803907, 803917, 803927, 803942, 803948,
    803954, 803961, 803962, 803964, 803969, 803971, 803972, 803984, 803994, 803996,
    804002, 804010, 804012, 804013, 804018, 804022, 804028, 804029,
  ],
  // Uttar Pradesh - 638 ULBs
  S24: [
    800629, 800630, 800631, 800632, 800633, 800634, 800635, 800636, 800637, 800638,
    800639, 800640, 800641, 800642, 800643, 800644, 800645, 800646, 800647, 800648,
    800649, 800650, 800651, 800652, 800653, 800654, 800655, 800656, 800657, 800658,
    800659, 800660, 800661, 800662, 800663, 800664, 800665, 800666, 800667, 800668,
    800669, 800670, 800671, 800672, 800673, 800674, 800676, 800677, 800679, 800680,
    800681, 800682, 800683, 800684, 800685, 800686, 800687, 800688, 800689, 800690,
    800691, 800692, 800695, 800698, 800699, 800700, 800701, 800702, 800703, 800705,
    800706, 800707, 800708, 800709, 800710, 800711, 800712, 800713, 800714, 800715,
    800716, 800717, 800718, 800719, 800720, 800721, 800722, 800723, 800724, 800725,
    800727, 800729, 800730, 800731, 800733, 800734, 800735, 800736, 800737, 800738,
    800739, 800740, 800741, 800742, 800743, 800744, 800745, 800746, 800747, 800748,
    800750, 800751, 800752, 800753, 800754, 800755, 800756, 800757, 800758, 800759,
    800760, 800761, 800763, 800764, 800765, 800766, 800767, 800768, 800769, 800770,
    800771, 800772, 800773, 800774, 800775, 800776, 800777, 800778, 800779, 800780,
    800781, 800782, 800783, 800784, 800785, 800786, 800787, 800788, 800789, 800790,
    800791, 800792, 800793, 800794, 800796, 800797, 800798, 800799, 800801, 800802,
    800803, 800804, 800805, 800806, 800808, 800809, 800810, 800811, 800812, 800813,
    800814, 800816, 800817, 800818, 800819, 800821, 800822, 800823, 800824, 800825,
    800826, 800827, 800828, 800829, 800832, 800834, 800838, 800840, 800841, 800842,
    800843, 800844, 800846, 800847, 800848, 800853, 800854, 800855, 800856, 800857,
    800858, 800859, 800860, 800861, 800862, 800863, 800864, 800865, 800866, 800867,
    800868, 800869, 800870, 800871, 800872, 800873, 800874, 800875, 800876, 800877,
    800878, 800880, 800881, 800882, 800883, 800884, 800887, 800889, 800894, 800895,
    800896, 800897, 800898, 800899, 800900, 800901, 800902, 800903, 800904, 800906,
    800907, 800908, 800909, 800910, 800911, 800912, 800913, 800914, 800915, 800916,
    800917, 800918, 800919, 800920, 800921, 800922, 800923, 800924, 800925, 800926,
    800927, 800928, 800929, 800930, 800931, 800932, 800933, 800934, 800935, 800936,
    800937, 800938, 800939, 800940, 800941, 800942, 800943, 800944, 800945, 800946,
    800947, 800948, 800950, 800951, 800952, 800953, 800954, 800956, 800957, 800958,
    800959, 800960, 800961, 800962, 800963, 800964, 800965, 800966, 800967, 800968,
    800969, 800970, 800971, 800973, 800974, 800975, 800977, 800978, 800979, 800980,
    800981, 800982, 800983, 800984, 800985, 800986, 800988, 800992, 800994, 800995,
    800997, 800998, 800999, 801000, 801001, 801002, 801003, 801004, 801005, 801007,
    801008, 801009, 801010, 801011, 801012, 801013, 801014, 801015, 801016, 801017,
    801018, 801019, 801020, 801021, 801022, 801023, 801024, 801025, 801026, 801027,
    801028, 801029, 801030, 801031, 801034, 801035, 801036, 801037, 801038, 801039,
    801040, 801041, 801042, 801044, 801045, 801046, 801047, 801048, 801049, 801050,
    801051, 801052, 801053, 801054, 801055, 801056, 801057, 801058, 801059, 801060,
    801061, 801062, 801063, 801064, 801065, 801066, 801067, 801068, 801069, 801070,
    801071, 801072, 801073, 801074, 801075, 801076, 801077, 801078, 801079, 801080,
    801081, 801082, 801083, 801085, 801086, 801087, 801088, 801089, 801090, 801091,
    801092, 801096, 801097, 801098, 801101, 801105, 801106, 801109, 801110, 801111,
    801113, 801114, 801115, 801116, 801117, 801119, 801120, 801121, 801122, 801123,
    801124, 801125, 801126, 801127, 801128, 801129, 801130, 801131, 801132, 801133,
    801134, 801135, 801136, 801138, 801149, 801150, 801152, 801153, 801154, 801155,
    801157, 801158, 801159, 801160, 801161, 801162, 801163, 801164, 801165, 801166,
    801167, 801168, 801169, 801170, 801171, 801172, 801173, 801174, 801175, 801176,
    801177, 801178, 801179, 801180, 801181, 801182, 801183, 801184, 801186, 801188,
    801191, 801193, 801194, 801195, 801196, 801197, 801198, 801200, 801201, 801202,
    801203, 801205, 801207, 801208, 801209, 801210, 801211, 801212, 801213, 801214,
    801215, 801216, 801217, 801218, 801219, 801220, 801221, 801222, 801223, 801224,
    801225, 801226, 801227, 801229, 801230, 801231, 801232, 801233, 801235, 801237,
    801238, 801239, 801240, 801241, 801242, 801243, 801244, 801245, 801246, 801247,
    801248, 801249, 801250, 801251, 801252, 801253, 801254, 801257, 801258, 801259,
    801260, 801261, 801262, 801263, 801265, 801266, 801268, 801269, 801270, 801271,
    801272, 801273, 801274, 801275, 801276, 900145, 900193, 900195, 900196, 900364,
    900441, 900442, 900443, 900445, 900446, 900447, 900448, 900449, 900450, 900451,
    900452, 900453, 900455, 900456, 900457, 900458, 900459, 900491, 900617, 900623,
    900624, 900626, 900627, 900628, 900633, 900634, 900637, 900638, 900640, 900641,
    900642, 900644, 900645, 900646, 900647, 900648, 900652, 900654, 900662, 900663,
    900670, 900739, 900740, 900741, 900742, 900743, 900747, 900755, 900756, 900757,
    900758, 900759, 900763, 900764, 901017, 901019, 901020, 901021, 901022, 901023,
    901024, 901025, 901026, 901027, 901028, 901029, 901032, 901033, 901034, 901035,
    901036, 901037, 901040, 901041, 901042, 901043, 901044, 901047,
  ],
  // West Bengal - 7 ULBs
  S25: [
    801682, 801694, 801697, 801708, 801718, 801727, 801728,
  ],
  // Chhattisgarh - 169 ULBs
  S26: [
    801910, 801911, 801912, 801913, 801914, 801915, 801916, 801917, 801918, 801919,
    801920, 801921, 801922, 801923, 801924, 801925, 801926, 801927, 801928, 801929,
    801930, 801931, 801932, 801933, 801934, 801935, 801936, 801937, 801938, 801939,
    801940, 801941, 801942, 801943, 801944, 801945, 801946, 801947, 801948, 801949,
    801950, 801951, 801952, 801953, 801954, 801955, 801956, 801957, 801958, 801959,
    801960, 801961, 801962, 801963, 801964, 801965, 801966, 801967, 801968, 801969,
    801970, 801971, 801972, 801973, 801975, 801978, 801979, 801980, 801981, 801982,
    801983, 801984, 801985, 801986, 801987, 801988, 801989, 801990, 801991, 801992,
    801993, 801994, 801995, 801996, 801997, 801998, 801999, 802000, 802002, 802003,
    802004, 802005, 802006, 802007, 802008, 802009, 802010, 802011, 802012, 802013,
    802014, 802015, 802016, 802017, 802018, 802019, 802020, 802021, 802022, 802023,
    802024, 802025, 802026, 802027, 802028, 802029, 802030, 802031, 802032, 802033,
    802034, 802035, 802036, 802037, 802038, 802039, 802040, 802041, 802042, 802043,
    802044, 802045, 802046, 802047, 802048, 802049, 802050, 802051, 802052, 802053,
    802054, 802055, 802056, 802057, 802058, 802059, 802060, 802062, 802063, 802064,
    802065, 802066, 802067, 802068, 802069, 802070, 802071, 802072, 802073, 802074,
    802075, 802076, 802077, 900006, 900105, 900507, 900601, 900602, 900603,
  ],
  // Jharkhand - 39 ULBs
  S27: [
    801763, 801764, 801765, 801766, 801767, 801768, 801769, 801770, 801771, 801772,
    801773, 801774, 801775, 801776, 801777, 801778, 801779, 801780, 801781, 801782,
    801783, 801784, 801785, 801786, 801787, 801788, 801789, 801790, 801791, 801792,
    801793, 801794, 801795, 801796, 801797, 801798, 801799, 801800, 801802,
  ],
  // Uttarakhand - 74 ULBs
  S28: [
    800290, 800292, 800294, 800297, 800298, 800299, 800301, 800302, 800303, 800305,
    800306, 800308, 800309, 800310, 800312, 800313, 800317, 800318, 800319, 800320,
    800321, 800322, 800323, 800325, 800327, 800328, 800329, 800330, 800331, 800333,
    800334, 800335, 800336, 800337, 800338, 800339, 800340, 800343, 800344, 800345,
    800346, 800347, 800348, 800349, 800350, 800351, 800352, 800353, 800354, 800356,
    800357, 800359, 800360, 900030, 900035, 900036, 900037, 900038, 900109, 900110,
    900111, 900113, 900114, 900240, 900241, 900243, 900244, 900246, 900248, 900250,
    900251, 900439, 900604, 900844,
  ],
  // Telangana - 114 ULBs
  S29: [
    802896, 802897, 802898, 802900, 802901, 802903, 802904, 802905, 802906, 802907,
    802908, 802909, 802910, 802912, 802913, 802914, 802917, 802918, 802919, 802920,
    802921, 802922, 802924, 802925, 802926, 802927, 802928, 802929, 802931, 802932,
    802933, 802934, 802935, 802936, 802937, 900012, 900016, 900017, 900018, 900019,
    900020, 900021, 900022, 900039, 900040, 900041, 900066, 900067, 900068, 900069,
    900070, 900071, 900072, 900103, 900106, 900147, 900475, 900476, 900477, 900479,
    900514, 900516, 900517, 900518, 900520, 900521, 900522, 900523, 900524, 900525,
    900526, 900527, 900528, 900530, 900531, 900532, 900533, 900534, 900537, 900538,
    900539, 900540, 900541, 900542, 900544, 900545, 900546, 900548, 900550, 900551,
    900552, 900553, 900554, 900555, 900556, 900559, 900560, 900561, 900562, 900565,
    900567, 900568, 900569, 900571, 900572, 900573, 900576, 900577, 900578, 900579,
    900580, 900581, 900732, 900733,
  ],
  // Andaman & Nicobar Islands - 1 ULBs
  U01: [
    804041,
  ],
  // Chandigarh - 1 ULBs
  U02: [
    800286,
  ],
  // Dadra & Nagar Haveli and Daman & Diu - 1 ULBs
  U03: [
    800047,
  ],
  // NCT of Delhi - 3 ULBs
  U05: [
    800441, 800442, 800443,
  ],
  // Puducherry - 2 ULBs
  U07: [
    804036, 804037,
  ],
  // Jammu & Kashmir - 64 ULBs
  U08: [
    800001, 800002, 800003, 800004, 800005, 800006, 800007, 800008, 800009, 800010,
    800011, 800012, 800015, 800017, 800018, 800019, 800020, 800021, 800022, 800023,
    800024, 800025, 800026, 800027, 800028, 800029, 800032, 800034, 800035, 800037,
    800040, 800042, 800043, 800046, 800049, 800050, 800051, 800052, 800054, 800055,
    800057, 800059, 800061, 800062, 800063, 800065, 800066, 800067, 800068, 800069,
    800070, 800071, 800073, 800074, 800076, 800077, 800078, 800080, 800081, 800083,
    800085, 800086, 900173, 900181,
  ],
};

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

// Constructed per-(state, ulb) registry. Lazy at first read; the
// 3,300-entry Record is built once via `Object.fromEntries`. Each entry
// shape mirrors `BLOCK_BOUNDARY` / `PANCHAYAT_BOUNDARY_BY_DISTRICT`
// (id / label / geojson_local_path / geojson_url / join_property) so
// the existing `resolveSource()` resolver works unchanged.
//
// Key format: `"{state_code}-{ulb_lgd}"` (e.g. `"S13-802640"`).
// Look-up by ULB picker: `WARD_BOUNDARY_BY_ULB[`${stateCode}-${ulbLgd}`]`.
const WARD_UPSTREAM_URL =
  "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/urban/SBM_Wards.geojsonl.7z";

// TODO(C.3.c): wire ULB-picker on state selection. Citizen surface must
// let the user pick a state -> then a ULB within that state's
// WARDS_BY_STATE[stateCode] list -> then resolve the entry here. Tracked
// in docs/archive/plans/20260530-boundary-plan-followups.md Category 3 (UX follow-up,
// Value MED, effort M); marker shipped via Row 4.1.
export const WARD_BOUNDARY_BY_ULB: Readonly<Record<string, BoundaryEntry>> = Object.freeze(
  Object.fromEntries(
    Object.entries(WARDS_BY_STATE).flatMap(([state_code, ulbs]) =>
      ulbs.map((ulb_lgd): [string, BoundaryEntry] => {
        const key = `${state_code}-${ulb_lgd}`;
        const state_name = WARD_STATE_NAMES[state_code] ?? state_code;
        return [
          key,
          {
            id: `${key}-ward`,
            label: `${state_name} \u2014 ULB LGD ${ulb_lgd} (Wards)`,
            geojson_local_path: `boundaries/in/wards/state=in_${state_code.toLowerCase()}/ulb=${ulb_lgd}/all.geojson`,
            geojson_url: WARD_UPSTREAM_URL,
            join_property: "wardcode",
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
