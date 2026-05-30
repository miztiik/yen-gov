# Boundary Data Sources

**Last Updated**: 2026-05-26

This is the catalogue and decision record for **geographic boundary data** — country / state / district / sub-district / village / Assembly Constituency / Parliamentary Constituency / postal polygons — that the frontend renders as choropleth maps. It is the boundary-data counterpart to [`data-sources.md`](data-sources.md) (which covers election *results* sources). The LGD identifier tables (the registry that issues `lgd_code` for the boundaries to join on) live in [`lgd-opendata.md`](lgd-opendata.md).

The **"why" behind the choices** below — why polygons not topographic raster, why not GADM, why TopoJSON is queued not shipped, why DIGIPIN is deferred, why 20 states are still on HTL on purpose — lives in [docs/concepts/boundary-data-philosophy.md](../concepts/boundary-data-philosophy.md). This catalogue records the "what"; the philosophy doc records the recurring "why".

The pipeline that consumes these sources lives in [`tools/boundaries/`](../../tools/boundaries/README.md); the file-by-file selection is encoded in [`tools/boundaries/pipeline.json`](../../tools/boundaries/pipeline.json); the on-disk ledger of what landed is [`datasets/boundaries/boundary_layers.parquet`](../../datasets/boundaries/boundary_layers.parquet) — the SoT for "what's currently shipping" and the right place to verify the count + producer for any layer.

## Terminology

| Term | Meaning |
| --- | --- |
| **Assembly Constituency (AC)** | The electoral district that elects **one MLA** to a state legislative assembly. Same shape ECI publishes results against. The map layer is `kind=ac` in [`boundary_layers.parquet`](../../datasets/boundaries/boundary_layers.parquet). |
| **Parliamentary Constituency (PC)** | Same idea, one level up — the electoral district that elects **one MP** to the national lower house. Map layer is `kind=pc`. |
| **LGD code** | The numeric identifier issued by the [Local Government Directory](https://lgdirectory.gov.in) for every administrative unit below the state — district, sub-district, block, gram panchayat, ULB, ward, village, AC, PC. The yen-gov join key for all non-electoral layers (district/subdistrict/village). See [identifiers.md](identifiers.md). |
| **HASC / ISO** | International coding schemes (`IN.TN`, `IN.AP`) used by some upstream sources (GADM, OSM). We do **not** use these as identifiers — name-normalisation would be required and they don't carry below state level cleanly. |

## Current inventory (753 shards on disk)

Resolved from the ledger ([`datasets/boundaries/boundary_layers.parquet`](../../datasets/boundaries/boundary_layers.parquet)) + producer/license join against [`datasets/taxonomy/sources.parquet`](../../datasets/taxonomy/sources.parquet) as of 2026-05-25.

| Level | Coverage | Producer | License | Join key | Vintage |
| --- | --- | --- | --- | --- | --- |
| `country` | 1 IND outline | [yashveeeeeeer/india-geodata](https://github.com/yashveeeeeeer/india-geodata) (SoI-derived) | CC-BY-4.0 | — | current (post-Telangana, post-Ladakh, post-DNH/DD) |
| `state` | 36 states + UTs | ramSeraph [`LGD_States`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/states) | CC0-1.0 | `State_LGD` | LGD `lgd-latest-extra1` |
| `district` | 785 districts (national) | ramSeraph [`LGD_Districts`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/districts) | CC-BY-4.0 (see note) | `dist_lgd` | LGD `lgd-latest-extra1` (rolling ~3 mo) |
| `subdistrict` | 36 states + UTs (36 per-state shards) | ramSeraph [`LGD_Subdistricts`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/subdistricts) | CC-BY-4.0 (see note) | `subdist_lgd` | LGD `lgd-latest-extra1` |
| `village` | 27/36 states + UTs (645 per-(state, district) shards) | ramSeraph [`LGD_Villages`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/villages) | CC-BY-4.0 (see note) | `village_lgd` | LGD `lgd-latest-extra1` |
| `ac` (Assembly Constituency) | 10 states from [ramSeraph/indian_admin_boundaries](https://github.com/ramSeraph/indian_admin_boundaries) `LGD_Assembly_Constituencies` (BharatMaps/LGD lineage; Phase D.2 promote, 2026-05-25) + 20 states from [HindustanTimesLabs/shapefiles](https://github.com/HindustanTimesLabs/shapefiles) | ramSeraph (CC0-1.0) for 10; HTL (MIT, treated as `unknown-public` in sources ledger) for 20 | `AC_ID` (5-digit LGD code) on ramSeraph; `AC_NO` on HTL | LGD rolling vintage on ramSeraph; 2008 Delimitation Order on HTL |
| `ac` — J&K (U08) | 1 file (90 ACs) | [shijithpk/2024_maps_supplement](https://github.com/shijithpk/2024_maps_supplement) `j_and_k_assembly_new_borders` | Unlicense | `seat_id` | 2022 J&K Delimitation Commission |
| `pc` (Parliamentary Constituency) | 545 features (national, 1 file) | [shijithpk/2024_maps_supplement](https://github.com/shijithpk/2024_maps_supplement) `india_ls_seats_545` | Unlicense | `ls_seat_code` | 2024 General Election delimitation |
| `postal` | 36 per-state shards + 1 `scope=unkeyed` shard | Department of Posts via data.gov.in OGD All-India Pincode Boundary | GODL-IN | 6-digit pincode | 2025 |

¹ ramSeraph upstream license is CC0-1.0 with attribution requested for datameet + the original government publisher. We record it as CC-BY-4.0 in the sources ledger because the attribution chain is the binding constraint. See [`indianopenmaps/DATA_LICENSE.md`](https://github.com/ramSeraph/indianopenmaps/blob/main/DATA_LICENSE.md).

## Cross-walk to the LGD ⇔ Census ⇔ Constituency ⇔ PIN code alignment matrix

The administrative-hierarchy matrix that civic-data work usually starts from (LGD revenue, LGD rural local government, LGD urban local government, Census 2011, Constituency, PIN code) maps onto the layers above as follows. Coverage status is "✅ live" / "⚠️ partial" / "❌ gap" relative to the level — **not** the matrix as a whole.

| Matrix row | Layer | Status | Source if/when adopted |
| --- | --- | --- | --- |
| **National** | `country` | ✅ live | yashveeeeeeer/india-geodata (SoI-derived) |
| **State / UT** | `state` | ✅ live | datameet `Admin2` |
| **District (LGD revenue district / Census 2011 district)** | `district` | ✅ live | ramSeraph `LGD_Districts` |
| **Sub-district (Tehsil / Taluk / Mandal / Block - LGD revenue unit)** | `subdistrict` | live | ramSeraph `LGD_Subdistricts`; countrywide rollout ships one shard per state/UT under `subdistricts/state=in_<sNN>/all.geojson` |
| **LGD Block (rural development block — distinct from sub-district)** | — | ❌ gap | ramSeraph [`blocks`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/blocks) release (catalogued, not adopted) |
| **Rural local body — Zila / Block / Gram Panchayat** | — | ❌ gap | ramSeraph [`panchayats`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/panchayats) release (catalogued, not adopted) |
| **Urban local body — Municipal Corp / Municipality / Town Panchayat** | — | ❌ gap | ramSeraph [`urban`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/urban) release: `SBM_ULBs` (national; gaps in TR/MZ/MN) + `WB_AMRUT_ULBs` (WB) |
| **Ward (GP ward / ULB ward)** | — | ❌ gap | ramSeraph `urban`: `SBM_Wards` (national, gaps in WB/TR/MZ/MN) + `LivingAtlas_Wards` + `WB_AMRUT_Wards` + `Shillong_Wards` |
| **Village (rural land unit, LGD-coded)** | `village` | partial: 27/36 states + UTs | ramSeraph `LGD_Villages`; countrywide rollout ships one shard per `(state, district)` under `villages/state=in_<sNN>/district=<lgd>/all.geojson`; 9 states/UTs are missing upstream (table below) |
| **Town (urban land unit, Census 2011)** | — | ❌ gap | ramSeraph census-2011 `PC11_TV_DIR.csv.7z` (town + village directory, CSV-only) |
| **Assembly Constituency (AC)** | `ac` | ✅ 31 of 31 elective states/UTs (10 ramSeraph LGD post-Phase-D.2 + 20 HTL + 1 J&K shijithpk) | mixed (HTL + ramSeraph + shijithpk J&K); ramSeraph `LGD_Assembly_Constituencies` is the consolidation target for the remaining HTL states **where D.1 recon authorises** — Phase D of the plan |
| **Parliamentary Constituency (PC)** | `pc` | ✅ national, 1 file | shijithpk 2024 delim today; ramSeraph `LGD_Parliament_Constituencies` is the upgrade candidate when survey-grade geometry is needed |
| **PIN code (postal zone)** | `postal` | live | Department of Posts via data.gov.in OGD All-India Pincode Boundary; 36 `postal/state=in_<sNN>/all.geojson` shards plus `postal/scope=unkeyed/all.geojson` |
| **Census 2011 District / Sub-district / Village** | indirect — `entities.json` district rows carry `census_2011_code` | ⚠️ no polygons | ramSeraph census-2011: `Districts_2011` + `SubDistricts_2011` (CC0-1.0 polygons), `Census_Villages` (CC0 **points**, not polygons). SHRUG variants are **CC-BY-NC-SA — non-commercial, NOT safe for our static-site redistribution**. See Phase E. |
| **DIGIPIN (4 m × 4 m grid)** | — | out of scope | Not a polygon family — needs a separate point/grid handler. Not on the roadmap. |

For the historical / methodology-break dimension (state + district boundaries 1941–2001 decadal series, plus the District_Timeseries_1951-2024 CSV that records every split, merger, and carve-out), ramSeraph's [`historical`](https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/historical) release is the candidate. Not currently adopted — relevant when a methodology-break-aware trend visualisation ships (see [`docs/architecture/data/boundaries.md` §"Methodology breaks"](../architecture/data/boundaries.md#methodology-breaks)).

## Coverage status — what we have, what we don't have

This section is the **canonical, live ledger** for boundary-coverage gaps. It supersedes any one-off `notes/` files on the same subject (the 2026-05-25 9-state village gap note was folded in here). When a gap closes, edit this section in the same PR as the ingest.

Three numbers govern district-level reasoning and routinely confuse new agents — resolve them once, here:

| Source | Count | What it represents |
| --- | :---: | --- |
| [`datasets/taxonomy/lgd/districts-latest.csv`](../../datasets/taxonomy/lgd/districts-latest.csv) | **784 districts** | Current modern district list per LGD master, refreshed via `tools/lgd/snapshot.py`. Carries `Census 2001 Code` + `Census 2011 Code` columns — i.e. the LGD CSV ALREADY cross-enriches each modern district with its Census-2011 ancestor. |
| [`datasets/boundaries/in/districts/all.geojson`](../../datasets/boundaries/in/districts/all.geojson) | 785 polygons | One row per shard in [`boundary_layers.parquet`](../../datasets/boundaries/boundary_layers.parquet); polygons keyed by `dist_lgd`. The +1 over the LGD CSV is a known cosmetic delta we will reconcile in the same PR that ships Phase 0.2 (likely a bifurcation-bookkeeping row). |
| [`datasets/taxonomy/entities.parquet`](../../datasets/taxonomy/entities.parquet) (where `entity_type='district' AND entity_valid_to IS NULL`) | **145 districts** | The subset hand-curated into `entities.json` so far — Assam (35), Haryana (33), Kerala (14), TN (38), West Bengal (23), Puducherry (2). Every district in this list has a confirmed display name + parent + `entity_valid_from`. |
| Census 2011 (frozen vintage) | ~640 districts | Historical anchor; ~144 modern districts (Telangana split 2014, Ladakh split 2019, Mayiladuthurai 2020, Tenkasi/Tirupathur/Chengalpattu/Kallakurichi/Ranipet 2019, plus ~140 more nationally) did NOT exist in 2011. Useful as a methodology-break oracle, NOT as a substitute for the modern LGD list. |

**Gap: 784 − 145 = 639 modern districts have polygons + LGD codes on disk but no curated entity row.** Closing this gap is **Phase 0.2** of the [boundary-coverage-expansion plan](../../TODO/20260524-boundary-coverage-expansion-plan.md) — see that doc's §0.2 for the cross-enrichment plan (combine LGD master + Census-2011 cross-references already on the LGD CSV + entities.json conventions).

### Per-level gaps

| Level | What ships today | What is missing | Closes via |
| --- | --- | --- | --- |
| country | 1 IND outline live | - | - |
| state / UT | 36/36 live | - | D.0 ramSeraph `LGD_States` swap landed |
| district polygons | 785 polygons (1 cosmetic over the 784-row LGD master) | 1 row reconcile | follow-up data cleanup |
| **district entity rows** (`taxonomy/entities.json`) | **784/784 live** | - | Phase 0.2 landed in PR #267 |
| subdistrict | 36/36 states + UTs live (countrywide rollout in PR #257) | - | - |
| village | 27/36 states + UTs live (PR #259, 645 per-(state, district) shards) | **9 states/UTs missing upstream** - see table below | bhuvan fall-back (per-state, gated on first village-keyed indicator); not in active sprint |
| AC | 31/31 elective states live (10 ramSeraph LGD + 20 HTL + 1 J&K shijithpk) | survey-grade consolidation onto ramSeraph `LGD_Assembly_Constituencies` for the remaining HTL states where D.1 recon authorises | **Plan Phase D.2 partial (10 states landed 2026-05-25); D.5 wrap-up closes the loop**. S03 Assam + U08 J&K remain on HTL/shijithpk per D.1 section 4 Outcome-3 mixed verdicts (LGD upstream does not cleanly reflect the post-2023 Assam or post-2022 J&K re-delim layouts). |
| PC | 545 features live (shijithpk, 2024 delim) | survey-grade `LGD_Parliament_Constituencies` is the upgrade target | **Plan Phase D.6** |
| pincode polygons | 36 per-state shards + 1 unkeyed shard live (PR #254) | - | - |
| pincode directory CSV | 165,627 rows live (PR #250) | - | - |

### Village gap — the 9 states/UTs missing from upstream `LGD_Villages`

The ramSeraph `LGD_Villages.geojsonl` upstream extract (used by Phase C) carries village polygons for 27 of India's 36 states/UTs. The 9 missing states:

| ECI | State / UT | Notes |
| --- | --- | --- |
| S02 | Arunachal Pradesh | Upstream absent |
| S08 | Himachal Pradesh | Upstream absent |
| S14 | Manipur | Upstream absent |
| S15 | Meghalaya | Upstream absent |
| S16 | Mizoram | Upstream absent |
| S17 | Nagaland | Upstream absent |
| S21 | Sikkim | Upstream absent |
| U08 | Jammu and Kashmir (UT) | Upstream absent. `Bhuvan_JK_Villages.geojsonl.7z` exists as a J&K-specific fall-back. |
| U09 | Ladakh | Upstream absent. In the post-2019 entity geometry J&K and Ladakh are two separate UTs; both need geometry. |

**Today this is NOT citizen-visible** — no citizen surface in the codebase currently consumes village-level geometry beyond Tamil Nadu's smoke pages. The gap becomes visible only when (a) a village-keyed indicator ships AND (b) the frontend renders that indicator on a village-drilled choropleth for a gap state.

**Decision logic when (if) a village-keyed indicator ships for a gap state**:

1. **First check**: does the surface render at district zoom, NOT village zoom? If yes, the existing district polygons (all 9 gap states have those) are sufficient and no fall-back is needed.
2. **If village zoom is unavoidable**: open a follow-up PR that adopts the bhuvan fall-back for ONLY the requested gap state(s), with explicit `boundary_layers.parquet` rows carrying a separate `source_id` (so the citation panel is honest about provenance: "bhuvan, not LGD"). Add a join-discipline test asserting the village-keyed indicator's join logic handles BOTH `village_lgd` (canonical) and `bhuvan_village_id` (fall-back) without ambiguity.
3. **Only adopt bhuvan for the specific gap states** — do NOT replace the 27 LGD-keyed states. Mixing is acceptable per-state; mixing within a state is not.

Why bhuvan is NOT pre-emptively adopted: it uses bhuvan-internal village identifiers, not `village_lgd`. Pivoting before a concrete consumer ships would introduce a mixed-key ledger that would propagate into every village-keyed indicator's join logic — a join-discipline change with downstream blast radius, deferred until justified. See [ADR-0031](../architecture/decisions/0031-boundary-geometry-strategy.md).

### District entity backfill — the cross-enrichment plan (Phase 0.2)

The 639 missing district entity rows are hand-curated, but the hand-curation is **assisted** — three sources already carry the raw data and we cross-enrich at write time:

1. **LGD master CSV** (`datasets/taxonomy/lgd/districts-latest.csv`) supplies the `District Code` (LGD), `District Name (In English)`, parent state code, AND already carries `Census 2001 Code` + `Census 2011 Code` columns. So the LGD CSV is itself a pre-joined LGD ⇔ Census table.
2. **Census-2011 polygons** (`Districts_2011` from ramSeraph; CC0-1.0) provide an independent name + geometry cross-check for any district that existed in 2011. ~640 of the 784 modern districts have a Census-2011 ancestor row; the remaining ~144 are post-2011 carve-outs (Mayiladuthurai 2020, Telangana split 2014, Ladakh 2019, etc.) and need `entity_valid_from` set to the gazette date rather than 1947.
3. **`entities.json` conventions** define the row shape (`entity_id` = `IN-S{nn}-D{lgd_code}`, `entity_type="district"`, `parent_entity_id`, `legacy_id` NULL for non-ECI-mapped districts).

The generator script (`tools/lgd/backfill_entities_districts.py`, NEW) reads the LGD CSV, diffs against `entities.json#/entities`, emits a JSON patch with all three cross-references populated. The operator hand-reviews for (a) display-name casing/hyphenation quirks, (b) `entity_valid_from` for post-2011 carve-outs, (c) any LGD ↔ Census name mismatches that flag a real entity event vs a transliteration drift. Per ADR-0033, `entities.json` is hand-curated; the generator suggests, the operator confirms.

Why this matters for citizen choropleths: financial-inclusion data (banks per pincode rolled up by district), agricultural data (rainfall/water/soil rolled up by district), social-sector tracker data (PMAY/JJM coverage) all key by district LGD code. Without 784 district entity rows, choropleth views for those families cannot label, tooltip, or hub-link the missing 639 districts — the polygon paints but no metadata-driven UI hangs off it.

## In use today (per-state AC catalogue)

The current inventory above gives the high-level shape. This table is the per-state AC catalogue for the 31 elective states/UTs (10 ramSeraph LGD + 20 HTL + 1 J&K shijithpk) that actually ship an Assembly Constituency layer today (the remainder of `boundary_layers.parquet` is summarised in the inventory above).

| Layer | Upstream | License | Notes |
| --- | --- | --- | --- |
| India state outlines (z 0–6) | [datameet/maps](https://github.com/datameet/maps) `States/Admin2.{shp,dbf,shx,prj,cpg}` | CC-BY 4.0 | 36 features. Reflects the Telangana split (2014), Ladakh split (2019), and merged Dadra-and-Nagar-Haveli-and-Daman-and-Diu UT. Frontend joins on `ST_NM` via the `boundary_join_name` field of the states view-model ([`frontend/src/lib/view-models/states.ts`](../../frontend/src/lib/view-models/states.ts)) — three overrides handle the legal-form ↔ DataMeet idiomatic-form gap (Andaman & Nicobar, Delhi, Jammu & Kashmir). |
| AC polygons — TN (S22) | [HindustanTimesLabs/shapefiles](https://github.com/HindustanTimesLabs/shapefiles) `state_ut/tamilnadu/assembly/tamilnadu_AC.json` | MIT | `AC_NO` 1–234. Matches the 2008 Delimitation Order numbering used by ECI for the 2026 cycle. |
| AC polygons — KL (S11) | same repo, `kerala_AC.json` | MIT | `AC_NO` 1–140 |
| AC polygons — WB (S25) | same repo, `westbengal_AC.json` | MIT | `AC_NO` 1–294 |
| AC polygons — AS (S03) | same repo, `assam_AC.json` | MIT | `AC_NO` 1–126. Open question — see [Assam delimitation note](#assam-delimitation-note). Phase D.3 kept AS on HTL per D.1 recon §4 Outcome 3 verdict (LGD count 134 vs SoT 126, 1% name parity — LGD release does not cleanly reflect the post-2023 layout). |
| AC polygons — 10 ramSeraph LGD states (S04 Bihar, S07 Haryana, S08 HP, S17 Nagaland, S18 Odisha, S19 Punjab, S23 Tripura, S26 Chhattisgarh, S28 Uttarakhand, U05 NCT of Delhi) | [ramSeraph/indian_admin_boundaries](https://github.com/ramSeraph/indian_admin_boundaries) `LGD_Assembly_Constituencies.geojsonl.7z` | CC0-1.0 (BharatMaps/LGD lineage) | `AC_ID` (5-digit LGD; 2-digit `State_LGD` + 3-digit `ac_no`) on the upstream feature; per-state slices filtered via `state_filter={State_LGD: <int>}` in [`pipeline.json`](../../tools/boundaries/pipeline.json). Phase D.2 swap landed 2026-05-25; D.1 recon authorised these 10 only (100% AC_NO coverage + ≥95% name parity). Post-snapshot the per-state shards re-assert the same invariants via [`tools/boundaries/verify_ac_parity.py`](../../tools/boundaries/verify_ac_parity.py); all 10 states verified at 97.3–100% name parity (1015 ACs total). Note: an `apply_exclude_filter` directive is available in `snapshot.py` for general use (drops features whose tagged status matches a sentinel value) but is NOT applied to these 10 entries — empirical inspection of the raw upstream during D.2 found 9 of 10 states carry zero `status="Pre delimitation"` rows, while S17 Nagaland carries 100% (constitutionally exempted from 2008 Delimitation; the 1976-vintage 60-AC layout is what ECI uses today). Filtering Pre-delim would erase Nagaland; see `docs/archive/notes/2026-05-25-d1-ac-consolidation-recon.md` §4 for the empirical correction to the recon-time hypothesis. |
| AC polygons — J&K (U08) | [shijithpk/2024_maps_supplement](https://github.com/shijithpk/2024_maps_supplement) `j_and_k_assembly_new_borders` | Unlicense (treated as public-domain dedication) | 90 ACs. 2022 J&K Delimitation Commission layout. Phase D.4 kept U08 on shijithpk per D.1 recon §4 Outcome 3 verdict (LGD count 101 vs SoT 90, 6% name parity — LGD release carries pre-2019-statehood layout rather than post-2022). |
| PC polygons — national (2024 delimitation) | [shijithpk/2024_maps_supplement](https://github.com/shijithpk/2024_maps_supplement) `india_ls_seats_545.geojson` | Unlicense (treated as public-domain dedication) | 545 features. Source: shijithpk's QGIS georeferencing of ECI [Press Note No. 23](https://elections24.eci.gov.in/docs/press-note-no-23.pdf) PDF images. Underlying boundary decisions issued by the Election Commission of India per Delimitation Commission Orders 1976 + 2008 + 2022 (J&K) + 2023 (Assam). Researcher-quality, **not survey-grade** — suitable for choropleth visualisation, **not** for area/distance calculation. 2 features carry `ls_seat_code=999` (J&K territory claimed by India but administered by Pakistan/China) and MUST be rendered with a distinct treatment (e.g. diagonal hatch overlay), never tinted with election colours. See [ADR-0031 Amendment 2026-05-24](../architecture/decisions/0031-boundary-geometry-strategy.md#amendment-2026-05-24-pc-layer-ingest--delimyyyy-partition-key). |

## Why these choices

### Boundaries are delimitation-bound, not vintage-bound

State and AC polygons change **only when a delimitation order is gazetted**. They do not need refreshing on a calendar cadence. The relevant change events for our scope:

- **Assembly constituencies** for Tamil Nadu, Kerala, and West Bengal were last redrawn by the **2008 Delimitation Order** and have not changed since. Any source publishing those boundaries — whether published in 2017 or 2024 — represents the same gazetted geometry.
- **State boundaries** for India have changed three times since 2010: Telangana (2014), Jammu & Kashmir / Ladakh (2019), and DNH-DD merger (2020). The datameet `States/Admin2` layer reflects all three.
- **Assam ACs** were redrawn by the **2023 Delimitation Commission**; this is the one open boundary question in our scope (see below).

Because of this, "is the upstream still being committed to?" is not the right selection criterion. The right criterion is: "does this file represent the currently-gazetted delimitation, with the property names (`AC_NO`, `ST_NM`) we join on?"

### The Election Commission of India does not publish shapefiles

ECI's interactive results map renders constituency boundaries server-side; it does not expose downloadable shapefiles or GeoJSON. Every open AC dataset on GitHub — including the ones we use and the ones we evaluated — ultimately traces back to scrapes of ECI's polling-station-locator pages, the Local Government Directory (LGD), or academic releases (Susewind 2014). There is no first-party ECI vector boundary feed to switch to.

### Per-state files beat single-India files

HTL ships one file per state, ~1 MB each. A single all-India AC file is ~10 MB and forces every state page to download every state's geometry. Per-state PMTiles also let CI rebuild only the changed state when one needs replacing.

## Source-selection policy: gap-fill, not bulk-swap

The yen-gov rule for any third-party boundary catalogue we evaluate (ramSeraph, yashveeeeeeer/india-geodata, etc.) is the same:

1. **Keep what already works.** State outlines (datameet, swapped to ramSeraph `LGD_States` in Phase D.0 2026-05-24) and the 19 HTL AC layers we still ship today are correct for the gazetted geometry they cover. We do not wholesale-replace them just because a newer aggregator exists — every swap is a regression risk and an attribution churn for zero functional gain. Parity-gated promotions ARE allowed: Phase D.2 (10 states 2026-05-25) and Phase D.0 (state polygons) both used D.1-style per-state recon as the swap gate, **not** "ramSeraph exists, ship it everywhere".
2. **Adopt only to fill a real gap.** A "gap" is one of: (a) a layer we don't have at all (e.g. district polygons), (b) a state where the layer we have is known stale against current delimitation (e.g. Assam post-2023), or (c) an identifier registry we need but haven't ingested (e.g. LGD codes for districts).
3. **Track the rest as catalogue.** Layers a third-party publishes that overlap our existing coverage are recorded below for the record, with explicit "why we don't switch" notes — so the next person asking "shouldn't we use X?" finds the answer.

The two `pipeline.json` arrays codify this: `inputs` is what actually builds today; `staged_inputs` (added 2026-05-13) holds gap-fill entries that are ready to drop into `inputs` when the corresponding feature ships and any required format handler exists.

## Sources evaluated, not adopted (yet)

We track these alternatives so the next "is there a better source?" question has a reusable answer.

### [ramSeraph/indian_admin_boundaries](https://github.com/ramSeraph/indian_admin_boundaries)

A single, actively-maintained catalogue of Indian administrative boundary data, organised as one GitHub Release per layer. Every release ships `.geojsonl.7z` (newline-delimited GeoJSON inside a 7z archive); the LGD-derived ones carry stable LGD codes as feature properties. License across all releases: **CC0 1.0 with attribution requested for datameet and the original government publisher** ([`indianopenmaps/DATA_LICENSE.md`](https://github.com/ramSeraph/indianopenmaps/blob/main/DATA_LICENSE.md)).

Decision per release tag, applying the gap-fill policy above:

| Release | Lineage / source URL | yen-gov use today | Decision |
| --- | --- | --- | --- |
| `states` (`LGD_States`, `bhuvan_states`, `SOI_States`) | LGD/BharatMaps (survey-grade), Bhuvan, Survey of India | datameet `Admin2` today | **Phase D.0 swap target (user-approved override 2026-05-24).** ramSeraph `LGD_States` is survey-grade BharatMaps lineage vs DataMeet's curated GIS lineage — the upgrade is a citizen-visible quality lift at coastlines + disputed borders and aligns the state layer with the LGD code system used everywhere else (districts, subdistricts, villages). Mechanically `~1 hour`: `taxonomy.entities` already carries all three code systems (`legacy_id`=ECI `S22`, `lgd_code`=`33`, `iso_3166_2`=`IN-TN`) per the T.0e port, so the swap is property repoint (`join_property` `ST_NM` → whatever `LGD_States` carries) + add `lgdCodeToEci` view-model helper + re-validate the 3-entry `boundary_join_name` override map (expect most/all to drop). See Phase D.0 of [the coverage-expansion plan](../../TODO/20260524-boundary-coverage-expansion-plan.md). |
| `districts` (`LGD_Districts`, `bhuvan_districts`, `SOI_Districts`) | same three lineages | **none — no district polygon layer in `pipeline.json`** | **Adopt to fill the gap.** `LGD_Districts` is the natural pick (carries LGD codes — joins directly to our `district.lgd_code` field per [ADR-0015](../architecture/decisions/0015-constituency-hierarchy-fields.md)). Staged entry in `pipeline.json#staged_inputs`; activate when the first district choropleth ships. |
| `constituencies` (`LGD_Assembly_Constituencies`, `LGD_Parliament_Constituencies`, Susewind 2014 AC/PC) | BharatMaps `mapservice.gov.in/.../AC_PC/MapServer/2` (AC) + `/MapServer/1` (PC) for LGD; Susewind 2014 academic dataset | 29 states from HTL per-state files; J&K from shijithpk; PC national from shijithpk (2024 delimitation) | **Adopt — AC + PC consolidation targets.** `LGD_Assembly_Constituencies.geojsonl.7z` (CC0-1.0, BharatMaps lineage) is the canonical AC source going forward (Phase D.1–D.5; per-state parity-gated promotion). `LGD_Parliament_Constituencies` is the **survey-grade swap target for `pc`** (Phase D.6, user-approved override 2026-05-24) — replaces today's GIS-traced shijithpk file (where a person digitised polygons manually in QGIS, an open-source desktop GIS tool, over the 2024 delimitation PDF). Recon gate: verify the LGD file reflects the 2024 General Election delim (post-J&K UT + post-Telangana, 545 PCs); if pre-2024, defer. **Susewind 2014 files are CC-BY-SA-NC 4.0 (non-commercial) — NOT safe for our static-site redistribution; tracked for reference only.** |
| `subdistricts` | LGD/Bharatmaps | 36 states/UTs live | Adopted in Phase B. Countrywide rollout ships one shard per state/UT under `subdistricts/state=in_<sNN>/all.geojson`. |
| `villages` | LGD/Bharatmaps | 27/36 states/UTs live | Adopted in Phase C. Countrywide rollout ships 645 per-(state, district) shards under `villages/state=in_<sNN>/district=<lgd>/all.geojson`. The 9 missing states/UTs are tracked in the village gap table above. Run `python tools/boundaries/simplify.py --dry-run --skip-parquet` for the gzip budget check. |
| `blocks` / `panchayats` / `habitations` | LGD/Bharatmaps | none | **Catalogue only.** Adopt when first PRI / scheme-delivery panel ships. |
| `urban` (`SBM_ULBs`, `WB_AMRUT_ULBs`, `SBM_Wards`, `LivingAtlas_Wards`, `WB_AMRUT_Wards`, `Shillong_Wards`, plus slum subtree) | Swachh Bharat Mission, WB AMRUT, ESRI LivingAtlas | none | **Catalogue only.** ULB-level governance data is the natural unlock — adopt when first such indicator ships. Note SBM gaps: TR, MZ, MN missing; WB missing on wards specifically. |
| `forests` / `coastal` / `goa_crz` | Forest Survey of India, MoEFCC CRZ, Goa CRZ georef | none | **Out of scope** for the governance-indicators surface. |
| `postal` | India Post / BharatMaps pincode polygons - see [§ Postal (pincode) sources](#postal-pincode-sources) | 36 state shards + 1 unkeyed shard live | Adopted in Phase A.2 from Department of Posts via data.gov.in OGD; search-affordance UI remains future work. |
| `police` | State police jurisdictions | none | **Out of scope.** |
| `census-2011` (`Districts_2011`, `SubDistricts_2011`, `Census_Villages`, `PC11_TV_DIR.csv`) | LGD/BharatMaps Population_Density layer + Census India TV directory | none today | **Catalogue.** Polygons are CC0-1.0 (safe) — `Districts_2011` and `SubDistricts_2011` are usable polygons; `Census_Villages` is **points**, not polygons. **SHRUG variants (`shrug-district-pc11`, `shrug-subdistrict-pc11`, `shrug-village-pc11`) are CC-BY-NC-SA 4.0 (non-commercial) — NOT safe for redistribution; do not adopt.** Phase E of the plan ships when the first Census-2011 indicator needs polygon joins. |
| `historical` | India State Stories — decadal state + district series 1941, 1951, 1961, 1971, 1981, 1991, 2001 + `District_Timeseries_1951-2024.csv` + `District_name_changes_1951_to_2021.csv` + `District_splits_and_carveouts_1951_to_2024.csv` + `New_districts_created_1951_to_2024.csv` | none | **Catalogue (high value, latent).** The four CSV timeseries files are the canonical record of every district split/merger/rename 1951→2024 — once a methodology-break-aware trend visualisation ships ([`docs/architecture/data/boundaries.md` §"Methodology breaks"](../architecture/data/boundaries.md#methodology-breaks)), these are the joinable source. License attribution chain: India State Stories → CC0-1.0 via ramSeraph. |

What we are explicitly **not** doing: bulk-importing every release "because it's there." Each adoption is a separate `pipeline.json` change in the same PR as the consuming feature, with its own provenance sidecar.

#### Format gap: `geojsonl.7z`

ramSeraph ships `.geojsonl.7z`, which `tools/boundaries/snapshot.py` does not yet handle (it knows `geojson` and `shp_bundle`). Activating any entry from `pipeline.json#staged_inputs` requires a one-time addition to `materialize_input()`: 7z-extract → NDJSON → wrap features into a `FeatureCollection`. Tracked here rather than as a separate ticket so it's discovered when someone tries to activate a staged entry.

### [yashveeeeeeer/india-geodata](https://github.com/yashveeeeeeer/india-geodata)

A unified, actively-maintained catalogue of openly-licensed Indian geospatial data — administrative boundaries, electoral boundaries, census, environment, water, infrastructure, healthcare, education, urban data. Ships in modern formats (Parquet, PMTiles, GeoJSONL, Shapefile) via GitHub Releases. Browsable at <https://yashveeeeeeer.github.io/india-geodata/>.

For our **boundary** use case it is a candidate, not a switch. The reasons we have not adopted it for ACs **today** are operational, not qualitative:

1. **The upstream chain ends at the same places we already use.** Their AC release aggregates DataMeet's national `India_AC.shp` (national/) and a per-state ECI scrape (eci-statewise/`S{nn}_AC.{shp,dbf,shx}`) plus an LGD-derived release. The eci-statewise files are the same family as the HTL per-state files we already consume, repackaged. There is no third-party redraw happening; only re-aggregation.
2. **Their per-state AC files do not document a property schema.** We join the frontend choropleth on `AC_NO` (HTL) and `ST_NM` (datameet states). Switching requires confirming the property names and the AC numbering convention in each `S{nn}_AC.dbf` match what `frontend/src/lib/maplibre/sources.ts` and `pipeline.json` expect. Until that audit happens, swapping is a regression risk for zero functional gain on TN/KL/WB.
3. **The Assam decision can move first.** The one place a switch is *worth* doing is Assam (S03), where HTL likely predates the 2023 Delimitation Commission redraw. Their LGD release (see next section) is the candidate worth checking.

When we adopt it, the natural integration is per-layer (e.g. only Assam ACs) by adding a new entry to [`pipeline.json`](../../tools/boundaries/pipeline.json) — not a wholesale swap.

#### What "LGD release" means

LGD = **Local Government Directory**, the public registry of administrative units maintained by the Ministry of Panchayati Raj (<https://lgdirectory.gov.in/>). It assigns stable numeric codes to every state, district, sub-district, block, panchayat, village, and assembly constituency in India. Where LGD publishes geometry for an AC, that geometry is *the* government-of-India administrative reference for that constituency.

The yashveeeeeeer/india-geodata electoral release packages an `LGD_Assembly_Constituencies.{parquet,pmtiles,geojsonl.7z}` artifact under CC0. This is a different lineage from the HTL files we use today (which trace to ECI scrapes). For a state where the two disagree — like post-redraw Assam — LGD is the authoritative tiebreaker.

This **does not** mean LGD is silently better for states whose boundaries have not changed. For TN/KL/WB the two lineages should produce geometrically identical polygons modulo simplification.

### Other repositories evaluated

| Repo | What it offers | Why not adopted now |
| --- | --- | --- |
| [datameet/maps](https://github.com/datameet/maps) `assembly-constituencies/India_AC.shp` | Single all-India AC shapefile | Per-state HTL files give better request granularity and frontend joins. We already use datameet for state outlines. |
| [datta07/INDIAN-SHAPEFILES](https://github.com/datta07/INDIAN-SHAPEFILES) | Pan-India admin and constituency GeoJSON; actively maintained | Repo's own README states "Data Vintage: Primarily 2019". For TN/KL/WB this is the same gazetted geometry as our current source; for Assam it predates the 2023 redraw. No advantage at present. |
| [GaneshKathar/india-geojson](https://github.com/GaneshKathar/india-geojson) | Listed in GitHub search | Repository is empty. |
| OpenStreetMap relations | Live, community-edited | AC coverage uneven across states; would require validation per state per delimitation cycle. Worth keeping as a cross-check, not a primary source. |
| Survey of India digital products | Authoritative national mapping | Not openly licensed for redistribution in our context. |

### GADM (rejected on principle)

[GADM](https://gadm.org/) is a widely catalogued international boundary dataset. yen-gov does **not** adopt it. Four structural reasons: (1) the India dataset encodes China/Pakistan-claimed slices in five of its state-level `_1.json` polygons -- non-starter for an Indian-citizen-facing site; (2) the license reserves redistribution rights in a way that does not cleanly satisfy our static-bundle ship path under Holy Law #1; (3) GADM keys on HASC codes (`IN.TN`, `IN.AP`) which forces a name-normalisation translator the rest of the pipeline does not need (we key everything on LGD or ECI per [identifiers.md](identifiers.md)); (4) GADM v4.1 has not been refreshed for the post-2019 Ladakh split, the post-2014 Telangana split, or the merged DNH-DD UT, while the datameet `Admin2` layer we ship today carries all three. Full rationale + per-level recommended replacements: [docs/concepts/boundary-data-philosophy.md#gadm-rejection-rationale](../concepts/boundary-data-philosophy.md#gadm-rejection-rationale).

## Other yashveeeeeeer/india-geodata datasets worth tracking

The same project catalogues many non-boundary datasets that are out of scope for the *boundary* pipeline but may be relevant to future yen-gov features (constituency-level enrichment, contextual layers, etc.). Recording them here so we don't re-research:

| Category | Datasets of likely interest |
| --- | --- |
| Healthcare | NIC HealthGIS public health facility locations (PHCs, CHCs, hospitals) |
| Education | Schools, colleges, universities, kindergartens (OSM-derived, ODbL) |
| Census | 2011 admin units; historical district series 1951–2024 |
| Remote sensing | District-level VIIRS nighttime lights (2012–2024); WorldPop 2020 1 km population density |
| Infrastructure | National highways, railways, PMGSY rural roads, ML-detected roads (Microsoft + Facebook) |
| Urban | Municipal ward boundaries for 28 cities; AMRUT slum boundaries |
| External link | SHRUG — socioeconomic data for 500K+ villages |

These are listed for awareness, not as decisions. Any future use of them goes through the same path as boundary sources: schema, license, identifier-join story, then a `pipeline.json`-equivalent entry under the appropriate tool.

## Assam delimitation note

The Assam Legislative Assembly was redelimited by the Delimitation Commission's order of 2023 (effective for elections after that date). Our current Assam AC source predates that order; it carries the older `AC_NO` 1..126 numbering and may have boundary differences against the 2023 layout.

The mitigation in [`pipeline.json`](../../tools/boundaries/pipeline.json) is the `delimitation_warning` field on the `S03` entry, plus the cross-check requirement in [`tools/boundaries/README.md`](../../tools/boundaries/README.md#assam-delimitation-caveat) — every `AC_NO` 1..126 in the simplified GeoJSON must match the corresponding constituency name in [`datasets/reference/in/states/S03/constituencies.json`](../../datasets/reference/in/states/S03/constituencies.json) before the boundaries PR can merge.

When Assam falls inside an election cycle yen-gov is publishing, the LGD AC release is the first candidate to evaluate for replacement — see Phase D of the [boundary coverage-expansion plan](../../TODO/20260524-boundary-coverage-expansion-plan.md), which generalises the Assam fix into the consolidation pattern (snapshot ramSeraph `LGD_Assembly_Constituencies` once, per-state parity-check against `constituencies.json`, promote on match). The Assam-specific gate: confirm `AC_NO`/`lgd_ac_code` count is **126 (pre-2023)** or **126 (post-2023, same count)** AND every name resolves against the S03 SoT before merging.

## Postal (pincode) sources

Pincode ingest splits into **two independent shapes** — a directory CSV (table; the citizen-volunteers-their-pincode use case) and polygons (the choropleth-style "shade the pincode region" use case). The directory is the priority; polygons are deferred until a consumer surface needs them.

### Directory CSV (citizen lookup — primary, Phase A.1)

[**All India Pincode Directory**](https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month) — Department of Posts (issuing authority, **gold** tier), data.gov.in, GODL-IN, monthly cadence, CSV. Columns: `circlename, regionname, divisionname, officename, pincode`. ~165k rows.

Ingest reuses the existing [`backend/yen_gov/sources/datagovin_ogd/`](../../backend/yen_gov/sources/datagovin_ogd/) adapter (operator-CSV-cache pattern proven on `fiscal/centre_transfers_gross`). UUID discovery via [`tools/datagovin_recon.py`](../../tools/datagovin_recon.py). One-time captcha-solve by the operator → cached CSV → emit reference table. **The OGD JSON API was probed and rejected for production** (demo key 10-rows/request + 429s; real keys gated on SMS-OTP); see [`urls.py` docstring](../../backend/yen_gov/sources/datagovin_ogd/urls.py).

### Polygons (search geometry - live data, no UI consumer yet, Phase A.2)

The live yen-gov polygon source is the Department of Posts All-India Pincode Boundary dataset from data.gov.in OGD, ingested in Phase A.2. It emits 36 per-state shards under `datasets/boundaries/in/postal/state=in_<sNN>/all.geojson` plus `datasets/boundaries/in/postal/scope=unkeyed/all.geojson` for the 17 pincode polygons whose state could not be resolved from the pincode directory table. These are data-ready search geometries; no citizen UI consumes them yet.

Alternative polygon sources remain useful catalogue entries for future quality comparisons:

| File | Producer | License | Coverage | Verdict |
| --- | --- | --- | --- | --- |
| [`PincodeBoundaries.geojsonl.7z`](https://github.com/ramSeraph/indian_cadastrals/releases/download/postal/PincodeBoundaries.geojsonl.7z) | India Post - PostalGIS (`post.nic.in/postalgis/master.aspx`) | CC0-1.0 (see note) | National **minus 8 states**: HP, J&K, Sikkim, ML, MZ, MN, NL, AR. Upstream notes: many polygons missing pincode value; urban polygons not granular enough. | Catalogue alternative. Compare against the live data.gov.in source only if pincode search quality requires a second geometry lineage. |
| [`Datagov_Pincode_Boundaries.geojsonl.7z`](https://github.com/ramSeraph/indian_admin_boundaries/releases/download/postal/Datagov_Pincode_Boundaries.geojsonl.7z) | data.gov.in (`catalog/all-india-pincode-boundary-geo-json`) | [GODL-IN](https://www.data.gov.in/Godl) | All-India | **Catalogue / alternative.** GODL-IN is a permitted license under our `sources.parquet` enum, so this is usable as a tiebreaker if PostalGIS quality issues bite. |
| [`GSDL_Pincodes.geojsonl.7z`](https://github.com/ramSeraph/indian_cadastrals/releases/download/postal/GSDL_Pincodes.geojsonl.7z) | Geospatial Delhi Limited (`gsdl.org.in`) | CC0-1.0 (see note) | Delhi only | Catalogue alternative for Delhi if the live all-India source is too coarse for the NCT search experience. |

¹ CC0-1.0 with attribution requested for datameet + the original government publisher.

The yen-gov design treats pincode as an **orthogonal search-only layer** (per [`docs/architecture/data/boundaries.md` §"Postal"](../architecture/data/boundaries.md#postal-pincode--search-only-orthogonal-layer)). Pincode is **never** a clickable choropleth layer and **never** a drill rung. The data is now present; the Jony + Citizen search-affordance UI is the remaining consumer-side work.

## Adding a new boundary source — the bar

Before any new source is added to [`pipeline.json`](../../tools/boundaries/pipeline.json):

1. **License compatibility.** MIT, CC-BY 4.0, CC0, GODL-India, India OGL — all fine. Check the upstream `LICENSE` file directly, not a third-party summary.
2. **Property schema.** Document which property carries the join key (`AC_NO`, `ST_NM`, etc.) and confirm `frontend/src/lib/maplibre/sources.ts` already handles it (or add a mapping). Boundary files with no stable join key are not usable.
3. **Delimitation alignment.** State which delimitation order's geometry the file represents. If unknown, treat as unverified.
4. **Provenance.** The `manifest.json` carries one `{ url, fetched_at }` per packed file (CLAUDE.md §12). Permanent URLs only — no signed/time-limited links.
5. **Size sanity.** A simplified per-state AC PMTiles file should land in the low hundreds of kB. If it balloons, revisit `coord_precision` and the tippecanoe simplification settings before committing.

## Related ecosystem sources (not boundary-pipeline)

The two siblings of `ramSeraph/indian_admin_boundaries` are tracked here so the next "can we use this?" question has a recorded answer.

### LGD identifier registry — [`ramseraph.github.io/opendata/lgd/`](https://ramseraph.github.io/opendata/lgd/)

Daily 7z archives of every Local Government Directory entity table (37 components — states, districts, sub-districts, blocks, ACs, PCs, PRI/ULB bodies and wards, villages, pincode mappings, etc.). The mirror's tables side, sibling to the geometry-side `ramSeraph/indian_admin_boundaries` catalogued above. **Not a boundary source — no geometry — but the canonical issuer of `lgd_code`** which our [`datasets/taxonomy/entities.json`](../../datasets/taxonomy/entities.json) district rows and [ADR-0015](../architecture/decisions/0015-constituency-hierarchy-fields.md) treat as the preferred district id.

Full component catalogue, URL pattern, archive lifecycle, and per-component adoption verdict: **[lgd-opendata.md](lgd-opendata.md)**. Ingestion will live under `tools/lgd/`, not `tools/boundaries/`; out of scope for `pipeline.json`. Listed here because the user-facing question ("what about ramSeraph?") spans both.

### Topographic raster basemaps — [`ramSeraph/india_topo_maps`](https://github.com/ramSeraph/india_topo_maps)

Survey of India 1:50k (Open Series Maps), 1:25k (NHP), 1:5k (CMPDI) topographic sheets, georeferenced and packed as raster PMTiles + tile-server URLs. **Out of scope for yen-gov.** We render administrative-boundary choropleths, not terrain — these PMTiles are raster basemap tiles (hillshade / contours), not the vector polygons our renderer joins to indicator data. Pulling them would balloon the static bundle for zero citizen-visible value. Recorded here so the question is answered.

## See also

- [`docs/concepts/boundary-data-philosophy.md`](../concepts/boundary-data-philosophy.md) -- the "why" behind every choice in this catalogue (polygons vs topographic raster, GADM rejection, TopoJSON adoption status, DIGIPIN deferral, HTL kept on purpose)
- [`tools/boundaries/README.md`](../../tools/boundaries/README.md) -- operational reference (how to run the pipeline, source format dispatch)
- [`docs/architecture/frontend/map.md`](../architecture/frontend/map.md) -- how the frontend consumes the PMTiles
- [`docs/architecture/data/boundaries.md`](../architecture/data/boundaries.md) -- subsystem doc (disk topology, identifier discipline, methodology breaks)
- [`TODO/20260524-boundary-coverage-expansion-plan.md`](../../TODO/20260524-boundary-coverage-expansion-plan.md) -- phased plan for Phase A (pincode), B (national subdistricts), C (national villages), D (AC consolidation onto ramSeraph), E (Census 2011 polygons)
- [`TODO/20260525-topojson-frontend-perf-plan.md`](../../TODO/20260525-topojson-frontend-perf-plan.md) -- queued TopoJSON adoption plan for the national states + districts shards
- [`docs/concepts/disclaimer.md`](../concepts/disclaimer.md) -- user-facing wording for boundary attribution
- [`docs/reference/data-sources.md`](data-sources.md) -- election-results sources (sister catalogue)
- [`docs/reference/lgd-opendata.md`](lgd-opendata.md) -- LGD tables (identifier registry) catalogue
- CLAUDE.md section 11 (schema versioning), section 12 (provenance)
