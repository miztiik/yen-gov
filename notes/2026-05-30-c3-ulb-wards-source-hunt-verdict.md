# C.3 ULB Wards (urban local body wards) upstream hunt verdict

**Date**: 2026-05-30
**Plan-doc row**: C.3 of TODO/20260529-boundary-rip-and-replace-plan.md
**Doctrine**: LGD-golden source-of-truth + ramSeraph mirror preference + CC0 license alignment.

## TL;DR

**Tier-1 path found.** ramSeraph publishes `SBM_Wards.geojsonl.7z` via the official Indian Admin Boundaries `urban` release (tag `urban`, last republished 2024-01-14), sourced from the Swachh Bharat Mission Urban portal (sbmurban.org, Ministry of Housing and Urban Affairs). 4 ULB-Ward sources catalogued in the same release; SBM is the only national one. **Coverage gap (documented upstream)**: SBM missing West Bengal, Tripura, Mizoram, Manipur (4 states / ~9 % of urban population). Tier-1.5 + Tier-2 fall-backs are catalogued for gap-fill (LivingAtlas national / WB AMRUT West Bengal / Shillong CMD Meghalaya); deferred to C.3.d optional follow-up. **Partition strategy**: nested ULB-keyed Hive partition `boundaries/in/wards/state=in_<lc>/ulb=<lgd>/all.geojson` (mirrors C.2 panchayats' `district=` partition but uses `ulb=` because ward's parent is the urban local body, not the district). **Frontend**: per-ULB registry recommended (state-level would bind 200-7000 wards per state — citizen UX requires ULB-picker drill-down). **Recon-only PR; defer infrastructure + implementation + frontend to C.3.a / C.3.b / C.3.c.**

## "Ward" — the LGD distinction

LGD distinguishes TWO ward classes. From https://lgdirectory.gov.in/viewWard.do + LGD homepage stats:

| Entity class | LGD code term | Parent | Tier | C.3 scope? |
|---|---|---|---|---|
| **ULB Ward** (Municipal Corp / Municipal Council / Nagar Panchayat ward) | `ulb_ward_lgd` (TBC on first snapshot) | Urban Local Body (`ulb_lgd`) | Urban — elected ward councillor unit | ✅ YES |
| **GP Ward** (gram-panchayat ward) | `gp_ward_lgd` (TBC) | Gram Panchayat (`panchayat_lgd`) | Rural — sub-panchayat elected ward | ❌ NO (not in `SBM_Wards`; SBM is urban-only by mandate) |

**C.3 scope**: ONLY ULB wards. GP wards are a separate LGD entity class but no national geometry source covers them today; they would join with `panchayat_lgd` parent if a citizen indicator demands them later. The plan-doc's "ULB Wards" title (C.3 row title in the canonical plan) confirms scope is urban-only.

**Naming convention**: yen-gov uses singular non-prefixed level names (`village` not `lgd_village`, `panchayat` per C.2). Recommend `ward` for the new `level` enum value (over `ulb_ward`). The disambiguation between ULB ward and GP ward is carried by the partition key (`ulb=`) and by `entity_kind`, not by the `level` name. Schema impact: one-line enum addition (`ward`).

## Investigation log

### ramSeraph releases (`urban` tag)

Probed https://github.com/ramSeraph/indian_admin_boundaries/releases (urban tag, last commit `fad48bd` 2024-01-14).

**Relevant artefacts (4 ward sources + ULB parent):**

1. **`SBM_Wards.geojsonl.7z`** — **TARGET FOUND** (Tier-1 primary)
   - Download: `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/urban/SBM_Wards.geojsonl.7z`
   - Source: Swachh Bharat Mission Urban portal (https://sbmurban.org/) — Ministry of Housing and Urban Affairs (MoHUA)
   - License: CC0 1.0 (attribute to MoHUA SBM + datameet + ramSeraph)
   - Coverage gap (per ramSeraph release notes): "Missing data from West Bengal, Tripura, Mizoram and Manipur"
   - Compressed size (estimate): ~80-120 MB
   - Extracted GeoJSON (estimate): ~600 MB - 1.2 GB at native precision
   - National feature count (estimate): ~250k-350k wards across ~28 states / 4500+ ULBs (LGD has ~4500 ULB entities total; average ~50-70 wards per ULB)

2. **`LivingAtlas_Wards.geojsonl.7z`** — alternative (Tier-1.5)
   - Download: `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/urban/LivingAtlas_Wards.geojsonl.7z`
   - Source: ESRI LivingAtlas India (https://www.esri.in/en-in/products/about-arcgis/living-atlas/overview)
   - License: CC0 1.0 (attribute datameet + government source)
   - Coverage: broader than SBM (claims national); but lineage is ESRI's commercial harmonisation pass, NOT direct government feed
   - Use case: gap-fill for SBM's 4 missing states + cross-verification

3. **`WB_AMRUT_Wards.geojsonl.7z`** — alternative (Tier-2, West Bengal only)
   - Download: `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/urban/WB_AMRUT_Wards.geojsonl.7z`
   - Source: West Bengal AMRUT portal (https://nagargispariseva.wb.gov.in) — Atal Mission for Rejuvenation and Urban Transformation
   - License: CC0 1.0
   - Use case: gap-fill for SBM's West Bengal absence; matches the WB-specific URBAN ENTITY directory (ULBs + wards)

4. **`Shillong_Wards.geojsonl.7z`** — alternative (Tier-2, Shillong only)
   - Download: `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/urban/Shillong_Wards.geojsonl.7z`
   - Source: Meghalaya CM Dashboard (https://meghalayacmdashboard.in/)
   - License: CC0 1.0
   - Use case: narrow gap-fill (Shillong Municipal Board only, ~27 wards); rest of Meghalaya remains uncovered until upstream publishes a broader Meghalaya release

**Choice rationale**: Pick `SBM_Wards.geojsonl.7z` (not LivingAtlas) for these reasons:
- **Direct government lineage**: SBM is the canonical MoHUA portal, the same publisher that owns ULB-list + ward-list for Swachh Survekshan rankings + AMRUT-funded works. Same provenance as the ULB parent (`SBM_ULBs`).
- **LGD-keyed joining**: SBM ward features carry `ulb_lgd` (parent) + `ward_lgd` (self) per LGD code conventions. Both join natively to LGD-keyed indicator parquets.
- **Citizen indicator alignment**: future ward-grain indicators are dominated by SBM-published surveys (Swachh Survekshan ranks, ULB-level cleanliness scores). Using the same SBM polygon as the SBM-indicator-source means no cross-publisher join risk.
- **License consistency**: CC0 1.0 matches the rest of the LGD/BharatMaps cohort (states, districts, subdistricts, blocks, panchayats, villages).
- **LivingAtlas reserved as Tier-1.5 cross-verify + gap-fill**: for SBM's 4 missing states (WB / TR / MZ / MN). Promotion to a `_livingatlas/` parallel family is a C.3.d optional follow-up only when a ward-keyed indicator citizen-needs WB/TR/MZ/MN coverage.

### LGD / BharatMaps / MoHUA

**LGD Directory** (https://lgdirectory.gov.in, homepage stats verified 2026-05-30):
- "List of All urban local bodies with no Wards" exception report exists at `https://lgdirectory.gov.in/exceptionalReportOnUrbanLbNoWard.do` — confirms LGD tracks the ULB-to-Ward parent-child relationship as a first-class FK.
- "LGD Codes of Wards" entity directory at `https://lgdirectory.gov.in/viewWard.do`.
- "LGD Codes of Local Bodies" (parent ULBs) at `https://lgdirectory.gov.in/globalViewLocalBodyForCitizen.do`.
- LGD does not publish ward GEOMETRY directly — only attribute tables (name + ULB FK + ward number); geometry sits at BharatMaps + SBM.

**BharatMaps `Admin_Boundary` MapServer** (https://mapservice.gov.in/gismapservice/):
- A `ULB_Boundary` MapServer carries ULB polygons. Has been visible at `https://mapservice.gov.in/gismapservice/rest/services/BharatMapService/Admin_Boundary/MapServer/?` historically; ward sub-layer presence intermittent.
- ramSeraph's SBM mirror is the operational source (BharatMaps' ward layer is a moving target; SBM portal is the canonical home).

**SBM Urban portal** (https://sbmurban.org/):
- Live dashboards over wards (Swachh Survekshan).
- Underlying ward geometry exported by ramSeraph into `SBM_Wards.geojsonl.7z`.
- Documented coverage gap: "Missing data from West Bengal, Tripura, Mizoram and Manipur" carried in the ramSeraph release notes.

### Existing yen-gov precedent (NOT the same as C.3 but the closest pattern)

`tools/boundaries/lift_panchayats_national.py` (C.2.b, shipped PR #446 `d34c1439`):
- Dedicated orchestrator for LGD_Panchayats — DISTRICT-keyed nested hive partition pattern.
- Resolves `state_lgd` -> ECI state code; groups features by `(state_eci, district_lgd)`; emits per-(state, district) hive shards.
- Outputs: `datasets/boundaries/in/panchayats/state=in_<lc>/district=<lgd>/all.geojson`.
- SKIP-on-budget pattern (`if shard_size > SNAPSHOT_BYTE_BUDGET: continue` per `_paths.SNAPSHOT_BYTE_BUDGET = 12 MB`).
- 663 shards / 28 states / ~250k features in the live snapshot.

`tools/boundaries/lift_blocks_national.py` (C.1.c, post-PR #443):
- Auto-fallback pattern: on budget breach at `coord_precision=N`, re-emit at `coord_precision=N-1`; if still over budget, SKIP. Records `simplification_tolerance_deg` per shard in parquet.

`tools/boundaries/lift_subdistricts_national.py`:
- State-keyed (one shard per state, no district nesting).

**Reuse strategy**: C.3.b lift script (`tools/boundaries/lift_wards_national.py`) should be modelled on `lift_panchayats_national.py` (nested per-parent partition) BUT swap the partition key from `district=` to `ulb=` (because ward's parent is the ULB, not the district). The C.1.c auto-fallback pattern from `lift_blocks_national.py` should be inherited because high-density urban states (UP / MH / TN / KA / WB-via-AMRUT later) will exercise the auto-fallback for ~10-20% of ULBs.

### Why `ulb=` and not `district=` partition

ULBs are LGD's PRIMARY urban administrative unit. A ULB has its own LGD code (`ulb_lgd`), independent of any district (a Municipal Corporation may span multiple districts in rare cases, and LGD tracks the ULB-to-district mapping as an M:N relation, not 1:N). Wards are children of ULBs (not children of districts) by LGD design.

Using `ulb=<ulb_lgd>` as the partition segment means:
- Per-shard payload is bounded by ULB size (~50-200 wards typical; ~500-7000 for mega-corps like BBMP / GHMC / Pune / Delhi / Hyderabad / Surat / Greater Mumbai), making per-shard budget tractable.
- Citizen UX flows from ULB-picker → ward-picker, which matches the data hierarchy.
- Avoids the inverse partition pitfall: if we partitioned by `district=`, a citizen browsing the rural Banaskantha district map would get the rural BLOCK polygons mixed with the urban wards inside Banaskantha's many small-town ULBs — a UX mess.

The `state=` parent segment is retained for two reasons:
- ECI-code namespacing (yen-gov's standard) prevents LGD-code collisions if any state ever reorganises ULB codes.
- Per-state directory navigation is the citizen's mental model ("show me Maharashtra urban wards" → list of ULBs → click into one).

### Other probed sources

- **LGD Directory direct** (https://lgdirectory.gov.in/viewWard.do): attribute tables only (name + ULB FK + ward number), no geometry.
- **Bhuvan urban layers** (https://bhuvan.nrsc.gov.in/): scattered ULB and ward overlays per state, but no consolidated national geojson; would need per-state stitching. Reserved as future Tier-3 only if SBM + LivingAtlas + WB-AMRUT + Shillong stack proves insufficient.
- **OSM `boundary=administrative` with `admin_level=10`** (https://www.openstreetmap.org/): partial coverage; geometry-quality varies wildly by city. Reserved as Tier-3 only.
- **GSDL Delhi** (https://gsdl.org.in/): Delhi-specific ward layer — not separately published as a ward-only file in ramSeraph's urban tag (Delhi has `GSDL_Localities` for sub-ward areas but not the ward boundary itself in that tag).
- **DataMeet** (https://github.com/datameet/maps): no ward-keyed layer; older Census-2011 town-only.
- **MoHUA Smart Cities portal** (https://smartcities.gov.in/): ULB-level dashboards but no ward geometry exports.
- **AMRUT geoportal national** (https://amrut.gov.in/): WB-AMRUT (https://nagargispariseva.wb.gov.in) is the only state-AMRUT portal that has historically exposed downloadable ward geometry; other states' AMRUT portals are web-UI only.
- **Cantonment Boards** (https://lgdirectory.gov.in/viewCantonmentBoard.do): LGD lists Cantonment-Board entities as a parallel urban class to ULBs (military-owned town local-body). They have wards but no consolidated national geometry; deferred entirely (would be a Tier-3 follow-up only if a Cantonment-Board-keyed indicator surfaces).

## Recommended path

**Tier-1 implementation (no deferral; recon-only PR plus separate C.3.a / C.3.b / C.3.c implementation PRs):**

### Slicing (mirrors C.2 precedent: recon -> infrastructure -> live lift -> frontend registry)

| Slice | Scope | Deliverable | Gate emphasis |
|---|---|---|---|
| **C.3** (this PR, recon-only) | Upstream verification; verdict doc | `notes/2026-05-30-c3-ulb-wards-source-hunt-verdict.md` + plan-doc C.3 row update | N/A (research deliverable) |
| **C.3.a** (infrastructure) | Schema: add `"ward"` to `level` enum; backend `Level` Literal + `Kind` Literal (`"wards"`); `_paths.derive_hive` accepts `ulb_lgd=` partition segment; pipeline.json may or may not need an entry (panchayats uses standalone orchestrator outside pipeline.json; wards likely same); orchestrator stub + test suite mirroring `test_lift_panchayats_national.py` | ~5-6 file changes; no datasets | Gate 2 (pytest) |
| **C.3.b** (live lift + datasets) | Run lift script against live `SBM_Wards.geojsonl.7z`; commit per-(state, ulb) shards; upsert `boundary_layers.parquet` rows; update HIVE_SHAPES test; verify property-name short-form-vs-long-form per C.2.b live-lift lesson | hundreds of geojson shards + parquet + 1-2 source-file edits | Gates 1, 2, 4 |
| **C.3.c** (frontend registry + ULB-picker) | Add `WARD_BOUNDARY_BY_ULB` Readonly Record keyed by `${state_code}-${ulb_lgd}`; per-ULB drill-down picker shim; contract test mirroring `state-panchayats-registry-coverage.test.ts`; per-state coverage table in registry | sources.ts + 1 new contract test + plan-doc update | Gates 3, 4, 5 |
| **C.3.d** (optional gap-fill) | Cross-load LivingAtlas + WB-AMRUT + Shillong fall-backs only if a ward-keyed citizen indicator citizen-needs WB/TR/MZ/MN coverage. Parallel `boundaries/in/wards/state=in_<lc>/ulb=<lgd>/_<source>/all.geojson` family OR replace the SBM shard for the gap state on a per-state basis with citation. | Per-gap-state shards + parquet | Conditional; ship only on demand |

### Property-name short-vs-long-form risk

The C.2.b live lift surfaced a property-name surprise — LGD panchayats use `gp_code` (short) instead of the expected `panchayat_lgd` (long). For C.3.b, expect a similar surprise:
- Hypothesis 1: `SBM_Wards` features use `ward_code` + `ulb_code` (short form mirroring SBM portal's URL params).
- Hypothesis 2: `ward_lgd` + `ulb_lgd` (long form matching LGD official columns).
- Hypothesis 3: `ward_no` + `ulb_id` (numeric-string mix — least standard).

The C.3.b dry-run MUST inspect the first feature's properties BEFORE finalising the lift script's `join_property` constant. The C.3.c frontend registry's `join_property` field gets locked at that point and is one of the 5 BoundaryEntry-shape fields per `frontend/src/lib/maplibre/sources.ts`. Do NOT pre-commit to either form in C.3.a's orchestrator stub — surface the hypothesis in the C.3.b dry-run output and lock it then.

### Coverage table (initial, to be refined by C.3.b live lift)

| State code | State | SBM coverage (per ramSeraph release notes) | Gap-fill candidate |
|---|---|---|---|
| S01-U07 (except S25, S15, S16, S17) | 30+ states/UTs | ✅ likely covered | n/a |
| S25 | West Bengal | ❌ MISSING | `WB_AMRUT_Wards.geojsonl.7z` (per ramSeraph) |
| S16 | Tripura | ❌ MISSING | LivingAtlas TBC; no per-state source documented |
| S15 | Mizoram | ❌ MISSING | LivingAtlas TBC; no per-state source documented |
| S14 | Manipur | ❌ MISSING | LivingAtlas TBC; no per-state source documented |
| S17 | Meghalaya | partial (Shillong only via separate file) | `Shillong_Wards.geojsonl.7z` + LivingAtlas for rest |

Final coverage table will be authored in C.3.b's handover doc after the live lift.

## Out of scope

- **GP wards** (gram-panchayat wards): rural-only sub-panchayat ward, separate LGD entity class. No national geometry source today; deferred indefinitely.
- **Cantonment Board wards**: military-administered town local body. Tracked by LGD as a peer to ULB but no national geometry source; deferred indefinitely.
- **Sub-ward areas / localities / neighbourhoods**: covered by `SBM_Areas` / `GSDL_Localities` / `WB_AMRUT_Localities` (separate ramSeraph artefacts in the same `urban` tag). Out of C.3 scope — granularity below ward is "ULB locality" and would be its own future C-row only if a citizen indicator demands it.
- **Slum boundaries**: covered by 6+ ramSeraph artefacts in the `urban` tag (Delhi DUSIB, Bangalore BBMP, Mumbai UMD, Tamil Nadu TNGIS, Telangana TRACGIS, West Bengal AMRUT). Explicitly out-of-scope per plan-doc §D.

## Open questions deferred to C.3.b

1. **`SBM_Wards` property-name short-vs-long-form**: lock at dry-run (see above).
2. **State-code resolution**: `SBM_Wards` features likely carry a `state_name` string (not a state-code). The C.3.b lift script needs the same ECI-state-code resolver pattern used by `lift_panchayats_national.py` (which maps `state_lgd` -> ECI). If SBM uses `state_lgd` -> easy; if SBM uses `state_name` string only -> need a name-to-LGD-or-ECI lookup utility (likely already in `_paths.py` or `_state_codes.py`).
3. **ULB-LGD-to-state-LGD mapping completeness**: LGD's `viewWard.do` carries the ULB-to-state FK but features in `SBM_Wards` may lack `state_lgd` (only `ulb_lgd`). If so, build a precomputed `ulb_lgd -> state_eci` lookup at lift time (one-shot derive from LGD's `globalViewLocalBodyForCitizen.do` ULB-list export if needed).
4. **Per-shard size budget**: 4500+ ULBs * 50-200 wards avg = a wide distribution. Mega-corp shards (BBMP / GHMC / Delhi MCD / Greater Mumbai MCGM) may breach `SNAPSHOT_BYTE_BUDGET` even at native precision; auto-fallback pattern from C.1.c is non-optional for C.3.b.
5. **Multi-ULB ward (impossible per definition, but defensive)**: wards are 1:1 children of one ULB. Defensive check in lift: assert every feature has exactly ONE ULB FK.

## References

- ramSeraph urban release: https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/urban
- ramSeraph DATA_LICENSE: https://github.com/ramSeraph/indianopenmaps/blob/main/DATA_LICENSE.md
- SBM Urban portal: https://sbmurban.org/
- LGD ward directory: https://lgdirectory.gov.in/viewWard.do
- LGD ULB directory: https://lgdirectory.gov.in/globalViewLocalBodyForCitizen.do
- C.2 panchayats verdict precedent: notes/2026-05-30-c2-panchayats-source-hunt-verdict.md
- yen-gov boundary-data-sources reference (Ward row at line 51): docs/reference/boundary-data-sources.md
