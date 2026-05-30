# C.4 Bhuvan J&K Villages (gap-fill) upstream hunt verdict

**Date**: 2026-05-30
**Plan-doc row**: C.4 of TODO/20260529-boundary-rip-and-replace-plan.md
**Doctrine**: LGD-golden source-of-truth + ramSeraph mirror preference + CC0 license alignment. C.4 is a **single-state gap-fill** for one of the 8 states/UTs absent from `LGD_Villages.geojsonl` (the national LGD villages release shipped in C — currently routed via `tools/boundaries/lift_villages_national.py` at PR #444 vintage).

## TL;DR

**Tier-1 path found.** ramSeraph publishes `Bhuvan_JK_Villages.geojsonl.7z` via the official Indian Admin Boundaries `villages` release (tag `villages`, last republished 2023-12-10), sourced from Bhuvan / ISRO / NRSC (https://bhuvan.nrsc.gov.in/). License CC0 1.0 matches the cohort. Tile URL `/not-so-open/villages/jammu-and-kashmir/bhuvan/{z}/{x}/{y}.pbf` is exactly the URL the C.4 plan-doc row references. **Property-name convention TBC at first-snapshot probe** — Bhuvan-lineage releases predate LGD's column convention; hypothesis 1 mirrors `LGD_Villages` long-form (`state_lgd` / `dist_lgd` / `village_lgd`), hypothesis 2 mirrors Bhuvan portal short-form (`state_code` / `dist_code` / `vil_code` or similar). Lock at lift dry-run (3-convention rule from C.3.b applies). Expected output: ~22 per-district shards under `datasets/boundaries/in/villages/state=in_u08/district=<lgd>/all.geojson` (J&K has 20 districts post-2019 UT reorg; LGD currently lists 22 entries including Reasi + Kishtwar bifurcations). Estimated feature count: ~6,000-7,500 villages. **Single implementation PR recommended** (no slicing): no schema change, no infrastructure change, no frontend change — only a parallel orchestrator (`lift_villages_jk_bhuvan.py`) + tests + live lift + parquet upsert + plan-doc stamp.

## Why C.4 is single-state gap-fill (not a fresh entity class)

C.1/C.2/C.3 each introduced a NEW LGD entity class (block / panchayat / ward) requiring schema + infrastructure + lift + tests + frontend registry across 4 sub-PRs. C.4 is fundamentally different:

- **Entity class already exists**: `"village"` is already in the `level` enum (added pre-C.4, via the original TN-only village adoption work referenced by `lift_villages_national.py:1-10` docstring).
- **Lift orchestrator already exists**: `tools/boundaries/lift_villages_national.py` (15.5 KB) handles the LGD national release; C.4 just adds a parallel orchestrator for the Bhuvan single-state source.
- **Partition shape already defined**: `boundaries/in/villages/state=in_<lc>/district=<lgd>/all.geojson` (27 states/UTs already populated via the LGD national lift in C). C.4 adds `state=in_u08/district=<lgd>/` shards alongside.
- **No frontend registry needed**: villages are NOT currently surfaced in the frontend (`Select-String -Path frontend/src/lib/maplibre/sources.ts -Pattern "village"` returns zero matches; no `VILLAGE_BOUNDARY_BY_DISTRICT` registry exists; no `state-villages-*` contract test exists). The C.4 scope per the plan-doc row is purely "populate `boundaries/in/villages/state=in_u08/...`" — frontend surfacing is a separate concern not part of any current row.

The recon's slicing recommendation reflects this: **C.4 (this PR, recon-only) + C.4.a (single impl PR)**. No C.4.b / C.4.c / C.4.d.

## "Village" — what Bhuvan publishes for J&K

J&K became a Union Territory on 2019-10-31 (the J&K Reorganisation Act 2019); Ladakh separated as its own UT (LGD state code `U09`). LGD's J&K territory (`U08`) carries 20 districts in current LGD vintage (2024) with revenue-village geometry historically managed by the J&K Revenue Department + Survey of India, not by LGD's central village registry. This is the structural reason J&K is absent from `LGD_Villages.geojsonl` — LGD never received the geometry hand-off from the state.

**Bhuvan / NRSC's role**: Bhuvan is ISRO's national geoportal that hosts village-level revenue boundary layers per state, supplied by State Revenue Departments under NSDI (National Spatial Data Infrastructure) MoUs. For J&K, the layer Bhuvan publishes comes from the J&K Revenue Department's village cadastre (legacy "Jamabandi" boundaries) and is updated when Bhuvan receives a refresh from the state. The tile path `/not-so-open/villages/jammu-and-kashmir/bhuvan/{z}/{x}/{y}.pbf` confirms Bhuvan is the underlying serving infrastructure that ramSeraph mirrors into a static `.geojsonl.7z` artefact.

**Naming convention**: yen-gov uses singular `village` for the level (already in the enum). No additional schema work needed. The disambiguation between LGD-lineage and Bhuvan-lineage is carried by the SOURCE row in `sources.parquet` (new `ramseraph_bhuvan_jk_villages` or similar source id), not by the level name. The shard contents themselves remain `village` features regardless of upstream.

## Investigation log

### ramSeraph releases (`villages` tag)

Probed https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/villages (last republished 2023-12-10, commit pinned to the `villages` tag).

**Relevant artefacts (2 villages sources in this tag):**

1. **`LGD_Villages.geojsonl.7z`** — Tier-1 national (already adopted in C, pre-C.4)
   - Download: `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/villages/LGD_Villages.geojsonl.7z`
   - Source: LGD (https://lgdirectory.gov.in/) — Ministry of Panchayati Raj
   - License: CC0 1.0
   - Coverage gap (per ramSeraph release notes): "Missing villages data from Himachal Pradesh, Jammu and Kashmir, Sikkim, Meghalaya, Mizoram, Manipur, Nagaland and Arunachal Pradesh" — **8 states/UTs absent**.
   - Already live: 27 states/UTs populated under `datasets/boundaries/in/villages/state=in_*/district=*/all.geojson`.

2. **`Bhuvan_JK_Villages.geojsonl.7z`** — **TARGET FOUND** (Tier-1 single-state gap-fill for J&K)
   - Download: `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/villages/Bhuvan_JK_Villages.geojsonl.7z`
   - Source: Bhuvan (https://bhuvan.nrsc.gov.in/) — ISRO / NRSC, sourced from J&K Revenue Department
   - License: CC0 1.0 (attribute Bhuvan + datameet + ramSeraph)
   - Coverage: J&K UT only (state code `U08`); does NOT cover Ladakh (`U09`).
   - Compressed size (estimate, from ramSeraph release-page typical Bhuvan-state artefact): ~5-12 MB
   - Extracted GeoJSON (estimate): ~40-90 MB at native precision (J&K has fewer villages than Punjab/HP because much of the territory is high-altitude / non-revenue land)
   - National feature count (estimate): ~6,000-7,500 features across ~22 districts (J&K has 20 LGD-current districts as of 2024; Bhuvan's vintage may include 22 entries if it predates a bifurcation rollback or includes legacy district codes — first-snapshot probe will confirm).
   - Tile URL referenced in C.4 plan-doc row: `/not-so-open/villages/jammu-and-kashmir/bhuvan/{z}/{x}/{y}.pbf` (the Bhuvan tile-server path).

**Choice rationale**: `Bhuvan_JK_Villages.geojsonl.7z` is the ONLY ramSeraph-mirrored village geometry for J&K. No alternative Tier-1 source exists today (no second J&K-villages publisher catalogued in the ramSeraph villages release; LGD itself is missing J&K). This is a single-option Tier-1 pick.

### Why NOT defer to a future LGD-J&K release

LGD has not received the J&K Revenue Department's village geometry in 4+ years of waiting; there is no published timeline. The 7 other gap states (HP, Sikkim, ML, MZ, MN, NL, AR) face the same structural blocker (each state's revenue department owns the geometry; LGD's central village registry is opt-in). C.4 takes the pragmatic path: ship the Bhuvan-lineage J&K layer NOW (citizen wins on J&K village granularity), and the day LGD ever publishes J&K, we replace the source on the existing shards (same partition, same level, swap the `source_id` in parquet). This is the same pattern C.2 / C.3 used for SBM-missing states — Tier-1.5 gap-fill goes live, Tier-1 swap happens IFF upstream eventually publishes.

### Existing yen-gov precedent (closest pattern)

`tools/boundaries/lift_villages_national.py` (LGD national, pre-C.4):
- Resolves `state_lgd` -> ECI state code via `state_lgd_resolver`; groups features by `(state_lgd, dist_lgd)`; emits per-(state, district) hive shards.
- Outputs: `datasets/boundaries/in/villages/state=in_<lc>/district=<lgd>/all.geojson`.
- SKIP-on-budget pattern (`if shard_size > SNAPSHOT_BYTE_BUDGET: continue` per `SNAPSHOT_BYTE_BUDGET = 12 MB`).
- 27 states/UTs / ~330k+ features in current live snapshot.

`tools/boundaries/lift_panchayats_national.py` (C.2.b, PR #446):
- 3-convention surprise surfaced: panchayats use SHORT-form `st_lgd` / `dt_lgd` / `gp_code` (NOT the long-form expected). Patched to read property names via module-level constants `STATE_PROPERTY` / `DISTRICT_PROPERTY` / `ID_PROPERTY` / `NAME_PROPERTY`.

`tools/boundaries/lift_wards_national.py` (C.3.b, PR #450):
- 3-convention surprise: wards use a THIRD distinct convention `statecode` / `ulbcode` / `wardcode` / `wardname` (concatenated lowercase). 3-convention rule LOCKED IN — every new ramSeraph admin-level layer needs a first-snapshot property-name probe.

**Reuse strategy**: C.4 implementation will author a NEW orchestrator `tools/boundaries/lift_villages_jk_bhuvan.py` modelled on `lift_villages_national.py` but specialised for the single-source-single-state case:
- Hardcoded URL: `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/villages/Bhuvan_JK_Villages.geojsonl.7z`
- Hardcoded ECI state code `U08` (no state-resolver lookup needed — every feature is J&K by upstream definition).
- Reads `dist_lgd` (or whatever the Bhuvan first-snapshot probe reveals) per feature; groups by district; emits `boundaries/in/villages/state=in_u08/district=<lgd>/all.geojson`.
- Source row in `sources.parquet`: new `ramseraph_bhuvan_jk_villages` nickname → URL + license CC0 1.0 + lineage chain (Bhuvan → NRSC → J&K Revenue Department).
- Reuses ALL of `snapshot.py`'s primitives (`fetch_geojsonl_7z`, `emit_feature_collection`, `_round_coords_geom`, `SNAPSHOT_BYTE_BUDGET`) for byte-identical format with the LGD lift.

### Why a parallel orchestrator (not augment lift_villages_national.py)

Two clean alternatives:
- **Option A (chosen)**: New parallel orchestrator `lift_villages_jk_bhuvan.py` — single-source, single-state, single-purpose. Diff stays small, no risk to existing LGD lift behaviour, no parametrisation overhead.
- **Option B (rejected)**: Augment `lift_villages_national.py` to accept `--source {lgd | bhuvan-jk}` and per-source URL/property-name constants. More elegant in the long run BUT introduces multi-source complexity into a script that has been stable since pre-C.4; the property-name divergence between LGD and Bhuvan would force conditional property reads everywhere. Defer this consolidation to a future C.4.b OR a generic "villages multi-source consolidation" PR only if a 2nd Bhuvan-state lift lands (HP / ML / MZ / etc.).

Generalisable rule: when adding a SECOND upstream source for an entity class that already has a national orchestrator, prefer a parallel orchestrator UNLESS the new source covers a substantial overlap (>50% feature-count delta) with the existing source. Bhuvan-JK adds 0% overlap with LGD national (J&K is missing from LGD entirely) → parallel script is clean.

### Other probed sources

- **LGD Directory direct** (https://lgdirectory.gov.in/viewVillage.do): attribute tables only for the 27 LGD-covered states; J&K has zero village entries in LGD. No geometry.
- **OSM `place=village` + `boundary=administrative` with `admin_level=10`** (https://www.openstreetmap.org/): J&K coverage is sparse and inconsistent — OSM contributors map prominent settlements but the full revenue-village cadastre is not crowdsourceable at that granularity. Reserved as Tier-3 only.
- **DataMeet** (https://github.com/datameet/maps): no J&K-villages layer.
- **Survey of India OSM topo sheets** (https://onlinemaps.surveyofindia.gov.in/): village locations as POINTS, not polygons; not a substitute for boundary geometry.
- **J&K Revenue Department direct** (https://landrecords.jk.gov.in/, https://jk.gov.in/jammukashmir/?q=revenue-department): the canonical owner of the J&K village cadastre. Likely has internal geometry but no public downloadable file. The Bhuvan release IS the public surface for this data.
- **HP / Sikkim / Meghalaya / Mizoram / Manipur / Nagaland / Arunachal villages** (the other 7 LGD-gap states): each has its own ramSeraph entry in the `villages` tag if Bhuvan publishes the state. Probe scope: separate recon per state; deferred until a citizen indicator demands village granularity in that state.

## Recommended path

**Tier-1 implementation (single PR after recon):**

### Slicing (mirrors C.2/C.3 recon-first pattern but with simpler impl)

| Slice | Scope | Deliverable | Gate emphasis |
|---|---|---|---|
| **C.4** (this PR, recon-only) | Upstream verification; verdict doc | `notes/2026-05-30-c4-jk-villages-source-hunt-verdict.md` + plan-doc C.4 row update (mark "Recon shipped; C.4.a queued") + plan-doc C.4.a row added | N/A (research deliverable) |
| **C.4.a** (live lift + impl) | New `tools/boundaries/lift_villages_jk_bhuvan.py`; `backend/tests/test_lift_villages_jk_bhuvan.py` (mirrors `test_lift_villages_national.py` shape); live lift against `Bhuvan_JK_Villages.geojsonl.7z`; commit per-district shards under `datasets/boundaries/in/villages/state=in_u08/district=<lgd>/all.geojson`; parquet upsert (+~22 rows in `boundary_layers.parquet`; +1 source row in `sources.parquet` for `ramseraph_bhuvan_jk_villages`); `boundaries-conform.test.ts` HIVE_SHAPES already accepts the partition shape (no extension needed — same as LGD villages); plan-doc C.4.a stamp | ~5-7 file changes (1 new lift script + 1 new test + ~22 new shards + parquet + sources + plan-doc) | Gates 1, 2, 4 |

**No C.4.b / C.4.c / C.4.d**: no frontend registry change (villages aren't surfaced in the frontend), no schema change, no infrastructure change.

### Property-name short-vs-long-form risk

Per the 3-convention rule (C.3.b lesson): EVERY new ramSeraph admin-level layer needs a first-snapshot property-name probe BEFORE finalising the lift script's property constants. For Bhuvan_JK_Villages:
- **Hypothesis 1**: long-form `state_lgd` / `dist_lgd` / `village_lgd` / `vlgname` (mirrors `LGD_Villages` — same maintainer, same conventions). 60% likely.
- **Hypothesis 2**: short-form Bhuvan-portal-style `state_code` / `dist_code` / `vil_code` / `vil_name` or similar. 25% likely.
- **Hypothesis 3**: Bhuvan native columns from the J&K Revenue Department shape (e.g. `STATE_NAME` / `DIST_NAME` / `VIL_NAME` / `VIL_CODE` uppercase). 15% likely.

The C.4.a dry-run MUST inspect the first feature's properties BEFORE finalising the lift script's `STATE_PROPERTY` / `DISTRICT_PROPERTY` / `ID_PROPERTY` / `NAME_PROPERTY` constants. Surface the hypothesis in the C.4.a dry-run output and lock it then. The 3-convention rule from C.3.b also predicts a 25%+ chance that Bhuvan uses a 4TH convention specific to the J&K Revenue Department cadastre — be defensive.

### Expected coverage (initial, to be refined by C.4.a live lift)

| State code | State | Bhuvan_JK_Villages coverage | Notes |
|---|---|---|---|
| U08 | Jammu & Kashmir UT | ✅ FULL (Bhuvan TBC ~6,000-7,500 features across ~22 districts) | LGD currently lists 20 districts as of 2024; Bhuvan vintage may include 22 entries pending district-reorg lag |
| U09 | Ladakh UT | ❌ NOT covered by this artefact | Separate gap-fill needed; no `Bhuvan_Ladakh_Villages.geojsonl.7z` in current ramSeraph villages tag; deferred indefinitely |

Final coverage table will be authored in C.4.a's handover doc after the live lift.

### Per-shard size budget

J&K has ~6,000-7,500 villages spread across ~22 districts → average ~300 villages per district. At `coord_precision=4` (the LGD national default), expected per-shard size ~500 KB - 2 MB. Well under the 12 MB `SNAPSHOT_BYTE_BUDGET`. Auto-fallback unlikely to trigger; the auto-fallback wiring from C.1.c is in place as defence-in-depth.

## Out of scope

- **HP / Sikkim / Meghalaya / Mizoram / Manipur / Nagaland / Arunachal villages** (the other 7 LGD-gap states): each may eventually warrant a parallel Bhuvan-state gap-fill (C.4.x rows), gated on (a) ramSeraph publishing a `Bhuvan_<STATE>_Villages.geojsonl.7z` artefact, and (b) a citizen indicator demanding village granularity in that state. Deferred until both gates flip.
- **Ladakh UT villages** (U09): no current ramSeraph artefact; deferred indefinitely until upstream publishes OR an alternative Tier-1 source surfaces.
- **Frontend villages surfacing**: villages aren't currently exposed in `sources.ts` or any contract test. Adding a `VILLAGE_BOUNDARY_BY_DISTRICT` registry is a separate UX concern not part of C.4. May land later as a separate row only if a village-keyed indicator citizen-needs it.
- **GP wards (gram-panchayat sub-ward)**: covered separately by C.3 doctrine (out of scope for villages family).
- **Revenue village vs census village**: Bhuvan publishes the REVENUE-village cadastre (legal land-record boundary). Census villages (the Census of India enumeration unit) may differ in some states. C.4 scope is revenue-villages only — citizen indicators that ride on Census village codes would need a separate join layer.
- **Frontend surfacing of villages** (UI / picker / drill-down): not part of C.4 scope. Tracked as future UX work.

## Open questions deferred to C.4.a

1. **Property-name convention**: lock at dry-run (see above).
2. **State-code resolution**: `Bhuvan_JK_Villages` features likely lack `state_lgd` (single-state file by definition). Lift script hardcodes `entity_state="U08"` per shard; no resolver call needed.
3. **District-LGD-to-state-LGD mapping completeness**: Bhuvan-J&K district codes may NOT match LGD's current J&K district codes — Bhuvan vintage could carry pre-2019 district codes or legacy revenue district codes. Defensive check in lift: cross-reference against `datasets/taxonomy/entities.json` U08 district list; WARN on any unmatched `dist_lgd`.
4. **Per-shard byte budget**: as noted, expected to be well under 12 MB; auto-fallback unlikely. Document in handover.
5. **First-feature sample probe**: before finalising the lift script, extract `head -1 Bhuvan_JK_Villages.geojsonl | jq '.properties'` to lock property names + verify license metadata if upstream embeds it.
6. **Multi-polygon villages**: defensive check — some revenue villages span discontiguous parcels. Emit each as a MultiPolygon Feature (preserve upstream geometry; do not split).
7. **22 vs 20 district count reconciliation**: J&K LGD currently lists 20 districts (2024 vintage); Bhuvan may carry 22 entries (legacy pre-2019 codes OR Reasi+Kishtwar split lineage). Surface the count delta in handover; do NOT auto-merge legacy codes — preserve Bhuvan's keying.

## References

- ramSeraph villages release: https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/villages
- ramSeraph DATA_LICENSE: https://github.com/ramSeraph/indianopenmaps/blob/main/DATA_LICENSE.md
- Bhuvan geoportal: https://bhuvan.nrsc.gov.in/
- J&K Revenue Department: https://landrecords.jk.gov.in/
- C.2 panchayats verdict precedent: notes/2026-05-30-c2-panchayats-source-hunt-verdict.md
- C.3 ULB Wards verdict precedent: notes/2026-05-30-c3-ulb-wards-source-hunt-verdict.md
- yen-gov boundary-data-sources reference: docs/reference/boundary-data-sources.md
- Existing villages lift orchestrator: tools/boundaries/lift_villages_national.py
- LGD villages national release notes (documents the 8-state gap): https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/villages
