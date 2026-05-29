# 2026-05-29 - Boundary rip-and-replace plan

**Scope**: User mandate 2026-05-29 (verbatim, two parts):

1. *"rip and replace pln to fix issues - consolidate dont worry about license and source provenance / htl retiremnet centrlize and fix problems"*
2. *"accept the vintage mismatch with a ribbon - NOT ACCEPTABLE - I GAVE GUIDELINES TO TAKE INFORMATION FROM WHERE IS POSSIBLE FOR LATEST DATA AND FIX THE BOX"*
3. *"THE ATTACHED BOUNDARY FILE SHOULD BE TO PULL IN AS MUCH INFO AS POSSIBLE TO OUR CODEBASE ... STYLE FROM THE ATTACHED PLAN - SECTION 4 FOR THE CONSOLIDATED BOUNDARY STRATEGY ALL SUB PHASES"*

**Outcome targets**:
- All 31 elective state/UT AC choropleths render coloured by election winners (today: 6 of 31). HTL fully retired from runtime code.
- LATEST machine-readable data wherever it exists. No stale-data + ribbon hacks. If a layer is genuinely unavailable in machine-readable form, the citizen surface shows a clean "boundaries pending" call-to-action (not coloured-stale-with-disclaimer).
- One canonical upstream for admin/electoral/postal: ramSeraph/indianopenmaps + per-state portal fallbacks where ramSeraph does not yet ship a layer. License + provenance bracketed out per user direction ("this is government data, public data").
- Breadth expansion (Phase C): blocks, panchayats, ULB wards, J&K villages, LGD PC v2, Susewind 2014 AP overlay. New ledger `level` enum values + Hive partition keys for the three new admin levels.

**Backref**: This plan folds in and supersedes [TODO/20260527-state-ac-map-universal-coverage-plan.md](20260527-state-ac-map-universal-coverage-plan.md) (its R3/R4/R5/R6 rows become **Phase A** here, with the S01/S03 "REVERT to HTL" verdict overturned per the LATEST-data-first mandate).

**Supersedes**: [notes/2026-05-29-consolidated-boundary-strategy.md](../notes/2026-05-29-consolidated-boundary-strategy.md) (the 7-PR breadth proposal there: Phase C of this plan picks up section 4a/4b/4c; the historical-districts and Census 2011 PRs are explicitly dropped per user direction).

**Authority**: Data shape decisions = Hans + Max. Contract / integration decisions = Gregor. Engineering craft (test tiers, refactor safety) = Fowler. UX (registry labels, footer copy, "pending" CTA) = Jony + Citizen. Per [CLAUDE.md](../CLAUDE.md) section 0a.

---

## LGD-golden doctrine (user mandate 2026-05-29)

> **"if it is not in scope, then normalize all codes to align with LGD that is going to be our golden source."**

**Interpretation**: LGD (Local Government Directorate, via ramSeraph's BharatMaps-lineage releases) is the authoritative identifier system for Indian admin and electoral geography going forward. Every snapshot/ingest in this plan defaults to a ramSeraph LGD release. Where LGD already aligns naturally with state-of-truth (SoT) numbering (the 4 already-LGD states S22 / S11 / S25 / U07 + new states in A.2), the snapshot's `ac_no` IS LGD's `ac_no` IS SoT's `eci_no`. No transform layer.

**Carve-out for upstream LGD legacy numbering**: where LGD's `ac_no` carries pre-redelimitation legacy numbering that does NOT match the post-redelimitation SoT (today: S01 AP from the 2014 bifurcation; tomorrow potentially S07 Delhi / S29 Telangana / others as bifurcations and redelims accumulate), the snapshot projects LGD's `ac_no` to SoT-aligned numbering via a NAME-BASED rewrite. The original LGD `ac_no` is preserved as `lgd_legacy_ac_no` AND LGD's globally-unique `AC_ID` is preserved as `lgd_ac_id` on every feature. This is NOT a violation of LGD-golden; it is an honest transform documented on the feature itself, auditable by any future agent and reversible if a corpus-wide migration to LGD `AC_ID` as the primary join key is undertaken.

**Out-of-scope (for any single PR in this plan)**: a full corpus-wide migration from `eci_no` to LGD `AC_ID` as the primary join key for election results, SoT files, URL routing, and indicator FKs. That is a Level-5 design checkpoint (CLAUDE.md section 6) requiring its own plan-doc and user signoff. The doctrine here commits to LGD-golden DIRECTIONALITY (every new snapshot anchors on LGD; every feature preserves LGD identifiers); the full normalization sweep is queued for a successor plan.

**Concrete implications for this plan**:
- A.1.a (S01 AP): LGD source + name-based `ac_no` rewrite + preserve `lgd_legacy_ac_no` + `lgd_ac_id`. In-scope.
- A.2 (registry sync 25 new states): pure LGD `ac_no` for all states where LGD aligns natively. In-scope.
- A.1.b (S03 Assam): if Tier-3 PDF digitization wins, the digitized output is keyed by SoT `eci_no` but should still record LGD's pre-2023 `ac_no` + `AC_ID` where the digitized polygon overlaps with a pre-2023 LGD polygon (best-effort historical traceability). Tier-4 district fallback inherits LGD `Dist_LGD` natively. In-scope.
- Full eci-to-AC_ID migration: deferred to successor plan.

---

## Status ready reckoner (UPDATE AFTER EVERY PR)

| Row | Phase | PR scope | PR | Status | SHA | Notes |
|---|---|---|---|---|---|---|
| **A.1.a** | A | Backend snapshot + pipeline.json: re-flip **S01 AP only** to LATEST machine-readable source. Uses LGD release with `(State_LGD=28 AND st_name='ANDHRA PRADESH')` filter + name-based `ac_no` rewrite to align legacy LGD 119-294 numbering with post-bifurcation SoT 1-175. Re-emit `boundary_layers.parquet`. | #434 | Done | `b5b6ce94` | 175/175 = 100% SoT name parity confirmed via `verify_ac_parity --state S01`. Browser smoke at `/s/andhra-pradesh/ac/1` renders ICHCHAPURAM heading + TDP/Ashok Bendalam election results + 175 AP polygons with AC#1 highlighted. LGD identity preserved on every feature as `lgd_legacy_ac_no` + `lgd_ac_id` (LGD-golden doctrine first instance). |
| **A.1.b** | A | Backend + frontend: **S03 Assam only**. Tier 1 exhausted (LGD release is pre-2023 with status='Pre delimitation'; name overlap to post-2023 SoT is 63.5%, geometry redrawn not just renumbered). Ladder per user mandate 2026-05-29: **T3 PDF digitization first** (sub-PR if Aug 2023 Delimitation Order PDF probes feasible via B.5 dispatch), **else T4 district fallback** (frontend-only interim), **else T2 Voronoi** (last resort via B.4 dispatch). | #435 | **T4 shipped (T3 deferred)** | `d191638c` | B.5 verdict at [notes/2026-05-29-s03-pdf-probe-verdict.md](../notes/2026-05-29-s03-pdf-probe-verdict.md): T3 PDF (S.O. 3553(E), https://egazette.gov.in/WriteReadData/2023/248037.pdf) IS feasible but text-only - vectorisation requires 40-60h manual QGIS work (deferred-feasible, NOT session-feasible). Ladder fallthrough to T4 per verdict's pair-recommendation. T4 ships 126 features at `datasets/boundaries/in/ac/state=in_s03/all.geojson` where each post-2023 AC carries its parent district polygon (35 unique Assam district geometries, generated by `tools/boundaries/s03_t4_district_fallback.py`). Each feature carries `parent_district_id` (SoT 3-letter mnemonic) + `parent_district_lgd` (numeric LGD code) + `derivation_method='district-fallback-t4'`. Citizen UX: heading shows post-2023 SoT name (e.g. Gossaigaon for AC#1); map highlight is the parent district outline (Kokrajhar for AC#1); election results bind to post-2023 SoT eci_no. T3 follow-up arc: future PR to vectorise the PDF per the 40-60h estimate or absorb a community release (ramSeraph post-2023 slice, DataMeet, OSM Assam mapping). |
| **A.2** | A | Frontend STATE_AC registry sync 6 -> 31: add 25 new entries to `frontend/src/lib/maplibre/sources.ts:STATE_AC`. All LGD-keyed entries use `join_property: "ac_no"` lowercase. S01 entry reflects A.1.a's LGD-with-rewrite outcome. S03 entry reflects A.1.b's chosen tier (T4 district fallback OR T2 Voronoi OR T3 PDF). U08 stays on shijithpk (post-2022 90-AC). | _planned_ | Not started | - | Gated on A.1.a + A.1.b (interim). New contract test `state-ac-registry-coverage.test.ts` asserts the 31-state set + per-entry shape conformance. |
| **A.3** | A | Attribution centralization: replace 31 per-state `attribution` HTML strings with one `BOUNDARY_FOOTER_ATTRIBUTION` constant rendered once by the map footer; add carve-out footnotes (S03 "boundaries pending" if applicable + U08 shijithpk J&K supplement). | _planned_ | Not started | - | Bundle with A.2 or ship as a follow-up cleanup PR. |
| **A.4** | A | Playwright per-state AC coverage spec: new `frontend/e2e/state-ac-coverage.spec.ts` iterates 31 states (incl. U08), navigates to `/s/<slug>/ac/1?event=<recent-eci-event>`, asserts >= 90% coloured polygons. Per-state report at `notes/2026-05-29-state-ac-coverage-report.md`. | _planned_ | Not started | - | Gated on A.2 merge. S03's row in the report reflects A.1.b's interim tier (T4 district fallback flagged as such; not held to the 90% AC-cell bar). |
| **B.1** | B | **Subagent dispatch** (Explore, thorough): hunt LATEST machine-readable AP post-2014 AC boundaries. Confirm Susewind 2014 175-feature shape; also probe Bhuvan, AP State GIS portal, ECI 2014 polling-station overlay rollup, OSM 2024 tags. Deliverable: verdict file at `notes/2026-05-29-s01-ap-source-hunt-verdict.md` with one of: (a) recommended source URL + feature count + sample names + join key, OR (b) exhaustion report with all probed URLs. | _shipped (with correction)_ | **DONE (corrected 2026-05-29)** | 193fb928 (original verdict) + see correction note | Original verdict was inaccurate (Susewind 2014 schema + feature count + sample names misreported; actual AP slice is 292 features in pre-bifurcation unified AP+TG numbering). Corrected verdict at `notes/2026-05-29-phase-b-verdict-correction.md` identifies LGD release with filter+rewrite as the actionable Tier-1 path (100% SoT name parity). |
| **B.2** | B | **Subagent dispatch** (Explore, thorough): hunt LATEST machine-readable Assam post-2023 AC boundaries. Probe: ramSeraph display-server post-2023 routes, Bhuvan, Assam State GIS portal (ASDMA, Assam Forest Dept, NRC Assam), ECI Delimitation Commission GIS exports, OSM 2024 tags for `boundary=political + admin_level=*`, DataMeet community, gazette PDF availability. Deliverable: verdict file at `notes/2026-05-29-s03-assam-source-hunt-verdict.md`. | _shipped (with correction)_ | **DONE (corrected 2026-05-29)** | 193fb928 (original verdict) + see correction note | Original verdict was inaccurate (LGD release is pre-2023 with status='Pre delimitation'; 80/126 name overlap to post-2023 SoT; geometry redrawn not just renumbered). Corrected verdict at `notes/2026-05-29-phase-b-verdict-correction.md` declares Tier-1 EXHAUSTED for S03; A.1.b needs user decision on T2/T3/T4 escalation. |
| **C.1** | C | LGD Blocks - new `level: "block"` enum value (schema v1.x bump); add `/not-so-open/blocks/lgd/` to `pipeline.json`; new Hive partition `boundaries/in/blocks/state=in_<lc>/all.geojson`. | _planned_ | Not started | - | Phase C kickoff: section 4a pattern proof for a NEW level. Citizen need: rural-development indicators (PMGSY, MGNREGA) bind at block granularity. |
| **C.2** | C | LGD Panchayats (gram-panchayat) - new `level: "panchayat"` enum value; partition `boundaries/in/panchayats/state=in_<lc>/district=<lgd>/all.geojson`; pipeline.json + snapshot.py reuse. | _planned_ | Not started | - | Citizen need: governance-quality indicators (panchayat is the most-local elected body). Simplification budget likely needed - panchayat count is village-scale. |
| **C.3** | C | ULB Wards - new `level: "ward"` enum value; partition `boundaries/in/wards/state=in_<lc>/ulb=<lgd>/all.geojson`; pipeline.json includes SBM (national) + per-state fallbacks (WB AMRUT, Shillong, GSDL Delhi). | _planned_ | Not started | - | Citizen need: urban-governance indicators (Swachh Survekshan, AMRUT, municipal corp data). Coverage uneven at upstream - ingest SBM nation-wide first; per-state in follow-ups. |
| **C.4** | C | Bhuvan J&K Villages (gap-fill) - add `/not-so-open/villages/jammu-and-kashmir/bhuvan/` to pipeline.json; populate `boundaries/in/villages/state=in_u08/...`. | _planned_ | Not started | - | Closes 1 of 9 missing-village-coverage states. Other 8 (S02/S08/S14/S15/S16/S17/S21/U09) get follow-up PRs only when a village-keyed citizen indicator demands them. |
| **C.5** | C | LGD PC v2 - add `/not-so-open/constituencies/parliament/lgd/` to pipeline.json; new partition `boundaries/in/pc/delim=2024/lgd/all.geojson` parallel to current shijithpk source; cross-verify; switch upstream when clean. | _planned_ | Not started | - | Drops the shijithpk PC dependency. Bundle with A.2/A.3 attribution centralization if scheduling allows. |
| **C.6** | C | Susewind 2014 AP overlay (optional) - if B.1 verdict confirms Susewind 2014 ships post-2014 175-feature AP-only shape AND ramSeraph LGD has cleaner coverage, Susewind 2014 lives at `boundaries/in/ac/state=in_s01/_susewind2014/all.geojson` as a v2 cross-verification source (NOT the live source). | _planned_ | Not started | - | Decided by B.1 verdict. May be a no-op if LGD beats Susewind on coverage. |
| **D.1.A** | D | Retire per-entity side-fixes for offshore / small / no-assembly UTs (Lakshadweep extractor + chip-strip + coverage exclusion + ADR-0029 if it exists). All entities render on the map at true geographic location; data-table / CSV / ranking-list rendering is a Jony-owned UX concern (NOT prescribed here). | _planned_ | Not started | - | Cleanup sweep PR. Sequenced AFTER A.1-A.4 to avoid coupling with registry-sync work. See section D.1 + section D.1.A below for file list. |

---

## Browser-smoke routes (pre-PR gate per CLAUDE.md section 13)

Every PR in this plan MUST be browser-smoked BEFORE `gh pr create`, not after merge. Smoke is RUN via `open_browser_page` + `screenshot_page` + `read_page` per [CLAUDE.md](../CLAUDE.md) section 13; verdict is recorded in the PR body. A PR opened without a passing smoke is a DoD violation.

| PR row | Pre-PR smoke routes | Pass criteria |
|---|---|---|
| A.1.a (S01 Tier 1 LGD with filter+rewrite) | `/s/andhra-pradesh/ac/1` | Map renders 175 AP polygons (post-bifurcation modern AP); rendered polygon count matches snapshot; no console errors; verify_ac_parity --state S01 reports 175/175 name parity; each feature carries `lgd_legacy_ac_no` + `lgd_ac_id` for LGD-golden provenance. |
| A.1.b (S03 Tier 3 - PDF, deferred per B.5 verdict) | `/s/assam/ac/1` | (Future arc.) Map renders 126 post-2023 AC polygons digitized from Aug 2023 Delimitation Order (S.O. 3553(E)); each feature carries `derivation_method='pdf-vectorisation'`; LGD pre-2023 `ac_no` + `AC_ID` preserved per LGD-golden where polygon overlap exists. Deferred because T3 vectorisation is ~40-60h manual QGIS work (NOT session-feasible). |
| A.1.b (S03 Tier 4 - district fallback, **SHIPPED** as interim) | `/s/assam/ac/1` | Map renders 126 features at `datasets/boundaries/in/ac/state=in_s03/all.geojson` where each AC carries its parent district's polygon as fallback geometry (35 unique Assam district shapes); page heading shows post-2023 SoT name (Gossaigaon for AC#1); highlight is the parent district outline (Kokrajhar for AC#1); election results bind to post-2023 SoT eci_no; each feature carries `parent_district_id` + `parent_district_lgd` + `derivation_method='district-fallback-t4'`. |
| A.1.b (S03 Tier 2 - Voronoi, LAST RESORT if T3 + T4 both blocked) | `/s/assam/ac/1` | (Not pursued.) Map renders 126 Voronoi cells derived from ECI polling stations; tooltip declares `derivation_method: polling-station-voronoi`. T4 makes this unnecessary. |
| A.2 | All 31 elective state slugs at `/s/<slug>/ac/1` | Each renders the STATE_AC layer at the correct polygon count (no fallback gray fill). |
| A.3 | Any 1 state at `/s/<slug>` (covers footer) | Footer renders exactly one attribution string (centralized constant); carve-out footnote present only where applicable. |
| A.4 | n/a (this PR IS the Playwright spec; running the spec on all 31 states IS the smoke). | Spec passes on all 31 states with >= 90% coloured polygons each. |
| B.1, B.2 | n/a (subagent verdict files, no UI change). | Verdict file exists at expected path with required sections. |
| C.0 | n/a (schema + boundaries.ts type extension; no UI route binds yet). | `python -m yen_gov validate --root .` succeeds; vitest passes the new boundaries-conform invariants. |
| C.1 - C.5 | n/a until a renderer + indicator binds the new level (deferred to follow-up PRs). | Validate succeeds on the new partition; ledger row appears with correct level enum. |
| C.6 (if shipped) | `/s/andhra-pradesh/ac/1` with `?source=susewind2014` toggle | Overlay renders; underlying live layer still primary. |
| D.1.A | `/s/lakshadweep`, `/s/andaman-and-nicobar-islands`, `/s/dadra-and-nagar-haveli-and-daman-and-diu`, `/s/ladakh`, plus any 1 national-map route | (a) Each UT polygon renders at true geographic location (no chip), (b) no console errors from removed extractor, (c) Playwright golden-path spec no longer references the chip selectors. |

---

## Phase A - AC universal coverage + HTL retirement (section 4b applied)

**Folds in**: R3/R4/R5/R6 of [TODO/20260527-state-ac-map-universal-coverage-plan.md](20260527-state-ac-map-universal-coverage-plan.md). The R1.7 REVERT verdict for S01 + S03 is overturned per the LATEST-data-first mandate (Phase B drives the source hunt; A.1 lands whatever B finds).

> **Phase B correction (2026-05-29)**: The original Phase B verdicts merged in PR #432 (sha 193fb928) for both S01 (AP) and S03 (Assam) were found to be inaccurate during the first-pass A.1 execution. Full probe transcript + revised tier verdicts at [notes/2026-05-29-phase-b-verdict-correction.md](../notes/2026-05-29-phase-b-verdict-correction.md). Net effect: A.1 is split into A.1.a (S01 actionable now via LGD with filter+rewrite) and A.1.b (S03 Tier-1 exhausted; awaiting user decision on T2/T3/T4 escalation; recommended interim = T4 district fallback). The B.1 + B.2 verdict files on main are left in place with CORRECTION pointers atop; the correction note is the authoritative source.

### A.1 Pipeline + snapshot

**Inputs**: B.1 + B.2 subagent verdicts as corrected per [notes/2026-05-29-phase-b-verdict-correction.md](../notes/2026-05-29-phase-b-verdict-correction.md).

**Split since Phase B correction (2026-05-29)**: A.1 ships as two PRs reflecting per-state tier outcomes:
- **A.1.a (S01 AP)** lands at Tier 1 via LGD with `(State_LGD=28 AND st_name='ANDHRA PRADESH')` filter + name-based `ac_no` rewrite. Actionable now; no user input needed.
- **A.1.b (S03 Assam)** is Tier-1 exhausted; ladder per user mandate 2026-05-29 is **T3 PDF -> T4 district fallback -> T2 Voronoi** (PDF tried first because the Aug 2023 Delimitation Order is the authoritative source the citizen would recognise; district fallback is the fast-ship interim if PDF probe fails; Voronoi is last resort).

The fallback ladder below describes the GENERAL tier mechanics for any state landing at that tier; per-state allocation lives in the status table at the top of this doc.

**Fallback ladder (user-mandated order 2026-05-29: T1 -> T3 -> T4 -> T2)**: The chip/pending-CTA path is RETIRED per user mandate 2026-05-29 ("chip is unacceptable, we need to find other fallbacks if other sources fail"). The T2 / T3 ordering is REVERSED from typical effort-first thinking because the user explicitly chose authoritativeness (PDF = the citizen-recognisable Delimitation Commission Order document) over speed-of-implementation. T4 (district fallback) is the always-available citizen-visible interim while T3 work proceeds.

| Tier | Source class | A.1 action | Subagent gate |
|---|---|---|---|
| **1 - Preferred** | LATEST machine-readable upstream (ramSeraph LGD post-2014/2023 slice, Susewind 2014, Bhuvan, State GIS portal, OSM 2024) | Switch `pipeline.json` block to LATEST source; re-snapshot; lowercase-normalise `join_key_property` to `ac_no`. Apply LGD-golden doctrine: name-based `ac_no` rewrite + `lgd_legacy_ac_no` + `lgd_ac_id` preservation where LGD carries legacy numbering. | B.1 (S01) / B.2 (S03) |
| **3 - Authoritative-fallback (user-preferred when T1 exhausted)** | One-time vector digitization from gazette PDF (Delimitation Commission August 2023 Order for S03; ECI 2014 notification for S01). Output ships clean GeoJSON at `boundaries/in/ac/state=in_<lc>/_pdf2024/all.geojson` with `derivation_method: pdf-vectorisation` on the ledger row. The PDF IS the source-of-record the citizen recognises ("the Delimitation Commission Order"). | Tracked as a separate sub-PR `feat/boundary-digitize-<state>-from-pdf` since this is a manual QGIS effort, NOT a subagent task. | B.5 (PDF availability + page-list + vector-extractability + license probe; dispatched FIRST per user mandate 2026-05-29 when T1 exhausted) |
| **4 - Graceful degradation (always-available interim)** | Render the state at DISTRICT granularity for the AC route: re-use the existing `boundaries/in/districts/state=in_<lc>/all.geojson`; citizen sees coloured districts instead of coloured ACs. Tooltip / map footnote: "AC-level boundaries pending; showing district outlines as interim." | Frontend STATE_AC registry entry points at the district layer for that one state; map join key switches to district LGD. Pure routing decision in `frontend/src/lib/maplibre/sources.ts`; no pipeline change. | No subagent; ships as the default interim render while T3 work proceeds in parallel. |
| **2 - Last-resort approximation** | Polling-station Voronoi rollup: ECI publishes polling-station lat/lon with `AC_NO` tags post-redelim; tessellate within state boundary to derive AC polygon proxies. Lives at `boundaries/in/ac/state=in_<lc>/_voronoi/all.geojson` with `derivation_method: polling-station-voronoi` declared on the ledger row. NOT survey-grade; cells follow polling-station density. | Build `tools/boundaries/voronoi_from_pollingstations.py` (one-time); ingest the derived layer as a parallel source. | B.4 (ECI polling-station availability + AC-tagging probe; dispatched only if T1 + T3 + T4 all exhausted for that state) |
| **NEVER** | Chip strip / "boundaries pending" CTA with no map render / ribbon-on-stale-pre-redelim-data | Rejected per user mandate 2026-05-29. | n/a |

**Escalation discipline**: A.1 only commits Tier-2/3/4 code if B.1/B.2 verdicts confirm Tier 1 is exhausted FOR THAT STATE. User-mandated escalation order 2026-05-29: try T3 (PDF) first when T1 fails; if PDF probe (B.5) returns viable, ship T3 sub-PR. If PDF probe is blocked or non-viable, ship T4 (district fallback) as citizen-visible interim. T2 (Voronoi) is reserved for the case where T3 AND T4 both fail (e.g. district boundaries also pre-delimitation and not refreshable). The state map ALWAYS renders something coloured for the citizen; never a blank pending placeholder.

**Files touched (Tier 1 path)**: `tools/boundaries/pipeline.json`, 2 regenerated GeoJSONs at `datasets/boundaries/in/ac/state=in_s01/all.geojson` + `state=in_s03/all.geojson`, `datasets/boundaries/in/boundary_layers.parquet`.

**Files touched (Tier 2 path, if escalated)**: New `tools/boundaries/voronoi_from_pollingstations.py`, ECI polling-station ingest stanza added to `pipeline.json`, Voronoi-derived GeoJSON at `datasets/boundaries/in/ac/state=in_<lc>/_voronoi/all.geojson`, ledger row + `derivation_method` column bump on `datasets/schemas/boundary-layers.schema.json` (minor v1.x bump).

**Files touched (Tier 4 path, if escalated)**: Only `frontend/src/lib/maplibre/sources.ts:STATE_AC` entry for that state points at the district layer's `geojson_local_path`; map footer carve-out note added per A.3.

### A.2 Frontend STATE_AC registry sync

**Files touched**: `frontend/src/lib/maplibre/sources.ts` (extend `STATE_AC` from 6 to 29-31 entries depending on A.1 outcome). New contract test `frontend/src/contracts/state-ac-registry-coverage.test.ts`.

**Per-entry shape** (uniform across 28-30 LGD-keyed entries):

```ts
"<eci>": {
  id: "<eci>-ac",
  label: "<state name> - Assembly constituencies",
  geojson_local_path: "boundaries/in/ac/state=in_<eci_lc>/all.geojson",
  geojson_url: "<ramSeraph LGD release URL>",
  join_property: "ac_no",
  attribution: BOUNDARY_FOOTER_ATTRIBUTION, // see A.3
}
```

U08 J&K stays on shijithpk (different identifier scheme: `seat_id` vs `ac_no`). S01/S03 entries reflect A.1 outcome - either same shape as the LGD-keyed entries (LATEST found) or omitted entirely from the registry (exhausted - state-page renders "pending" surface from a new `/s/<slug>` fallback branch).

### A.3 Attribution centralization

**Files touched**: `frontend/src/lib/maplibre/sources.ts` (introduce `BOUNDARY_FOOTER_ATTRIBUTION` constant), `frontend/src/lib/maplibre/<MapFooter>.svelte` (render the constant once per map), new test asserting the footer renders exactly one attribution string.

**Footer copy** (Jony + Citizen pass):

> "Admin boundaries: ramSeraph LGD-keyed (CC0 / Unlicense; LGD / BharatMaps lineage). Carve-outs: U08 Jammu & Kashmir from shijithpk (post-2022 90-AC). [S03 Assam: boundaries pending post-2023 delimitation - we are working on this.]"

The bracketed S03 sentence appears only if A.1 ships S03 as "pending". If A.1 finds a LATEST source for S03, the sentence is omitted.

### A.4 Playwright per-state coverage spec

**Files touched**: `frontend/e2e/state-ac-coverage.spec.ts` (new), `notes/2026-05-29-state-ac-coverage-report.md` (auto-generated report).

**Spec shape**: parameterised over the 28-30 STATE_AC entries (whichever A.2 ships). For each state, navigate to `/s/<slug>/ac/1?event=<latest-eci-event>`, wait for map idle, query rendered polygon fills, assert >= 90% non-default-fill. Failing states fail the suite (no `.skip()` carve-outs).

---

## Phase B - LATEST-data source hunt (no ribbons, no compromises)

**Trigger for this phase**: the user 2026-05-29 explicitly rejected the ribbon-on-stale-data workaround for S03 Assam (and by extension S01 AP). The plan must hunt LATEST machine-readable boundaries from every plausible source BEFORE deciding the state's fate. Subagents do the hunting; deliverables are verdict files this plan + Phase A consume.

### B.1 S01 AP post-2014 source hunt

**Dispatch**: Explore subagent, thoroughness=`thorough`.

**Prompt scope**:
- File-inspect ramSeraph display-server route `/constituencies/assembly/2014/susewind/` (header bytes + feature-count probe) to confirm whether it ships a post-2014 175-feature AP-only shape with named anchors (Pithapuram, Visakhapatnam-North, Kakinada-Rural).
- File-inspect ramSeraph `/not-so-open/constituencies/assembly/lgd/` - does the bulk LGD AC release have a state_filter route that returns the AP post-2014 slice cleanly? Cross-check against `state_lgd_resolver.load_state_lgd_to_eci_map` (S01 -> LGD 28).
- Probe AP State GIS portal (apsac.in or similar) for officially-published AC shapefiles.
- Probe Bhuvan (bhuvan-app1.nrsc.gov.in) for AP AC release.
- Probe OSM 2024 via Overpass with `boundary=political + admin_level=4 + state=Andhra Pradesh` and check if any user has tagged AP AC boundaries (likely zero but worth confirming).
- DataMeet (datameet.org) community-maintained shapefile collections.

**Deliverable**: `notes/2026-05-29-s01-ap-source-hunt-verdict.md` with one of:
1. **Recommended source** (URL + license + feature count + sample feature property names + the `ac_no` field name + sample geometry validity confirmation).
2. **Exhaustion report** (every probed URL with the rejection reason - 404, wrong vintage, malformed, no AC granularity).

**Gate**: Drives A.1 + A.2 for S01.

### B.2 S03 Assam post-2023 source hunt

**Dispatch**: Explore subagent, thoroughness=`thorough`.

**Prompt scope**:
- File-inspect ramSeraph display-server `/constituencies/assembly/lgd/` with state_filter=18 (Assam LGD code) - what vintage does it ship? If pre-2023, what's the most-recent release?
- ramSeraph Bhuvan-sourced routes (`/not-so-open/constituencies/assembly/bhuvan/`) - does Bhuvan have post-2023 Assam?
- Assam State Disaster Management Authority (ASDMA, asdma.gov.in) GIS portal - does it host post-2023 AC shapefiles for emergency-planning purposes?
- Assam Election Commission (ceoassam.nic.in) - any GIS downloads alongside the 2026 election rolls?
- Delimitation Commission of India (delimitation-commission.gov.in) - did they publish a GIS export alongside the August 2023 order, or only PDF?
- OSM 2024 via Overpass with `boundary=political + admin_level=* + state=Assam` filtered to post-Aug-2023 changeset timestamps - has any contributor added the new 126-AC boundaries?
- DataMeet community - is anyone tracking Assam 2023 redelim?
- ESRI India / Bhuvan / NESDR Manipur-style state-specific GIS feeds.
- If nothing in machine-readable form: confirm whether the Aug 2023 Delimitation Order PDF has vector-extractable boundary maps (would feed a future digitization PR, NOT this plan).

**Deliverable**: `notes/2026-05-29-s03-assam-source-hunt-verdict.md` with the same shape as B.1.

**Gate**: Drives A.1 + A.2 for S03. If the verdict is "exhausted", S03 ships as a "boundaries pending" surface - NO ribbon on stale data.

### B.3 Subagent dispatch protocol (reusable)

For each B-phase hunt:

1. Invoke `runSubagent` with `agentName: "Explore"`, `description: "<state> AC source hunt"`, `prompt: <full prompt scope above + workspace context anchors>`.
2. Subagent returns verdict text; agent writes it to `notes/2026-05-29-<state>-source-hunt-verdict.md`.
3. Agent reads verdict; updates this plan-doc's row (B.1/B.2) Status column from `Not started` to `done` with the SHA of the verdict-file commit.
4. Agent posts a one-line summary in the PR-A1 body so the reviewer can trace the source decision.

---

## Phase C - Breadth wins (section 4a + section 4c applied)

The architecture is already in place (Hive partitions + ledger + LGD-keyed joins). Phase C extends it to three new admin levels + one PC source + one J&K village gap-fill.

### C.0 Unified upstream contract (section 4a, reused for all of C.1-C.6)

For every new layer Phase C ingests:

1. **Upstream**: ramSeraph release URL (one of the 12 sub-repos). Use the display-server JSON route for discovery; the underlying `.7z` GeoJSONL artifact for ingestion. Display-server paths (e.g. `/not-so-open/blocks/lgd/`) map directly to ramSeraph release tags (`lgd-blocks-latest`).
2. **Pipeline config**: append a stanza to [tools/boundaries/pipeline.json](../tools/boundaries/pipeline.json) declaring `from[].url`, `out`, `join_key_property`, `level`. No `delimitation_warning` for admin levels (only AC/PC carry it).
3. **Adapter**: ramSeraph rows already carry LGD codes natively. Existing `tools/boundaries/snapshot.py` + `simplify.py` chain works without modification.
4. **Storage**: Hive partition matching the new `level`:
   - block: `boundaries/in/blocks/state=in_<lc>/all.geojson`
   - panchayat: `boundaries/in/panchayats/state=in_<lc>/district=<lgd>/all.geojson`
   - ward: `boundaries/in/wards/state=in_<lc>/ulb=<lgd>/all.geojson`
5. **Ledger schema bump**: `datasets/schemas/boundary-layers.schema.json` `level` enum extended from current 8 values (`country|state|district|ac|pc|subdistrict|village|postal`) to 11 (`+block|panchayat|ward`). Schema x-version `1.1` -> `1.2` (minor, additive). Add an `x-changelog` entry in the same commit.
6. **Source row on `taxonomy/sources.parquet`**: one new row per ramSeraph release URL via `backend.yen_gov.canonical.citation.derive_source_id` per [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md).
7. **`frontend/src/lib/boundaries.ts:GeoLevel` type extension**: add the 3 new literals; extend `boundaryRelPath()` switch with the 3 new path templates; extend `JOIN_KEYS` map.
8. **Discipline guardrails** (carried over from `notes/2026-05-29-consolidated-boundary-strategy.md` section 7):
   - Join key = official LGD code (`state_lgd`, `dist_lgd`, `block_lgd`, `gp_lgd`, `ulb_lgd` + `ward_no`). Postal uses `pincode`. No exceptions.
   - One canonical live layer per (level, vintage). Variants live under `_<vintage>/` siblings, never co-mingled.
   - Simplification budget per `tools/boundaries/simplify.py:LAYER_TUNING`. Record tolerance + algorithm + feature-count delta on the ledger row.
   - Methodology breaks (delim-vintage) declared via `delimitation_vintage` column on the ledger row.
   - No mocks. No bridges. No `_pending_` placeholder fields.

### C.1 LGD Blocks

**Files touched**:
- `datasets/schemas/boundary-layers.schema.json` (enum bump to v1.2)
- `tools/boundaries/pipeline.json` (new block stanza, per-state state_filter pattern)
- `frontend/src/lib/boundaries.ts` (extend `GeoLevel`, `JOIN_KEYS`, `boundaryRelPath()` switch)
- `frontend/src/contracts/boundaries-conform.test.ts` (add block-level path conformance assertions)
- N regenerated GeoJSONs at `datasets/boundaries/in/blocks/state=in_<lc>/all.geojson`
- Regenerated `boundary_layers.parquet`

**Out of scope** (deferred to follow-up PRs): citizen-facing map renderer for block layer (no current indicator needs it; ingest only to make the layer available for downstream indicator PRs).

### C.2 LGD Panchayats

Same shape as C.1 but partition is `state + district` (per-(state, district) shards like villages). File volume warning: panchayat count is approximately village-scale (~250k); simplification likely needed before any browser-side rendering. Per-shard size budget tracked on the ledger row.

### C.3 ULB Wards

Same shape as C.0. Partition is `state + ulb_lgd`. Coverage uneven at upstream (SBM is the only national source; per-state fallbacks at WB AMRUT, Shillong, Delhi GSDL). Ingest SBM nation-wide first; per-state fallbacks in follow-up PRs only when SBM coverage gap blocks a specific citizen indicator.

### C.4 Bhuvan J&K Villages

Same shape as existing LGD Villages but upstream is Bhuvan (J&K-specific). Path: `boundaries/in/villages/state=in_u08/district=<lgd>/all.geojson`. Closes 1 of 9 missing-village-state gaps (S02/S08/S14/S15/S16/S17/S21/U08/U09). Other 8 get follow-up PRs only when a village-keyed citizen indicator demands them.

### C.5 LGD PC v2

Parallel source to existing shijithpk PC layer. Path: `boundaries/in/pc/delim=2024/lgd/all.geojson`. Cross-verify against shijithpk. If clean (>= 95% feature-count + name parity), switch upstream and drop shijithpk dependency. If drift, ship both and prefer LGD for joins.

### C.6 Susweind 2014 AP overlay (conditional)

Decided by B.1 verdict. If B.1 confirms Susewind 2014 ships a post-2014 175-feature AP-only shape, and ramSeraph LGD coverage is cleaner, Susewind 2014 lives at `boundaries/in/ac/state=in_s01/_susewind2014/all.geojson` as a v2 cross-verification source (NOT the live source). May be a no-op if LGD beats Susewind.

---

## Phase D - Out of scope (explicit non-goals)

Per user direction 2026-05-29 ("focus on future not historical accuracy"), the following are EXPLICITLY NOT in this plan or any near-term plan:

- **Historical districts 1941-2001** (8 decadal snapshots). Earlier session memory had this as a "cheap breadth win"; dropped.
- **Census 2011 polygon snapshot** (parallel `_census2011/` family). Earlier session memory had this for "Mayiladuthurai didn't exist in 2011" handling; dropped. If a Census 2011 indicator surfaces later and a renderer needs the 2011 shape, re-scope at that point.
- **SHRUG Census 2011** harmonized variant. Dropped.
- **Habitations** (sub-village SoI hut + PMGSY + ESRI built-up). Granularity below village; out of doctrine.
- **Polling stations** (7 ramSeraph sources covering ECI 2014/2017/2022/2025 + Bhuvan AP 2014 + Punjab 2020 + NESDR Manipur). Election-renderer concern, not citizen-page surface. Defer until /e/ event pages need them.
- **Slums** (8 sources covering WB AMRUT, Hyderabad GHMC, Telangana, TN, Bangalore BBMP, Mumbai MCGM, Delhi GSDL). Out of scope for governance-data v1.
- **ULB cadastrals** (52 ramSeraph sources). Out of scope.
- **Post Offices** (PostalGIS, point layer). No indicator joins on PostalGIS code.
- **Cadastrals / water / transport / power / buildings / industries / floods / DEM / mining / forest / geomorphology / lithology / SOI topo / lineament**. These are indicator-family concerns (energy, water, fiscal) - if/when needed they go into `datasets/<family>/_meadow/...` per [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md), NOT under `datasets/boundaries/`.
- **`_historical/districts/year=YYYY/` partition family**. User correction 2026-05-29: "THIS MAY NOT BE REQUIRED". Confirmed dropped.

### D.1 No per-entity side-fixes for offshore / small / no-assembly UTs (user mandate 2026-05-29)

> *"REMOVE ANY SIDE FIXES FOR LAKSHADWEEP AS DATA TABLE, IF THE MAPS INCLUDE IT, EVEN IF THE CHOROPLETH IS UNVISIBLE LETS JUST KEEP IT IN THE MAP."*

Generalised rule (applies to U04 Lakshadweep, U01 A&N, U06 DNH-DD, U09 Ladakh, and any future small/offshore/no-elected-assembly UT):

- **No per-state polygon extractors.** `frontend/src/lib/lakshadweep.ts:extractLakshadweepGeometry` and any similar named "extract<UT>Geometry" helper are RETIRED. The boundary file is the source of truth: if a UT's polygon is present in `boundaries/in/states/all.geojson` or any other layer, it stays on the rendered map untouched.
- **No "unmapped regions" chip strip.** The ADR-0029 chip strip pattern (per [docs/concepts/unmapped-regions.md](../docs/concepts/unmapped-regions.md)) is retired as Phase D.1.A below. The MAP renders the polygon at true geographic location; if a polygon is geographically too small to colour at the current zoom level, that is the correct citizen experience (zoom in to see). Downstream surfaces (data tables, CSV exports, ranking lists, tooltip rollups, winner-name panels) are a UI/UX concern owned by **Jony + Citizen** per [CLAUDE.md](../CLAUDE.md) section 0a and are NOT enshrined in this plan  -  they naturally render one row per entity since they are built from entity-keyed observation rows; if a value is absent the cell renders ` - ` (the same null-render any state with a data gap gets). Whether AC-winner names appear as a tooltip vs a side panel vs a table column is a Jony deliverable, not a boundary-plan decision.
- **No per-state "exclude from coverage" filters.** `backend/yen_gov/coverage.py` and any similar coverage-report code that special-cases UTs ("intentionally excluded") gets the UT carve-out removed. UTs appear in coverage reports exactly like states; if a programme doesn't operate in a given UT, the row simply shows zero / NA  -  which is the truthful citizen-readable signal.
- **No per-state Playwright assertions.** `frontend/e2e/golden-path.spec.ts:74-87` asserts the Lakshadweep chip; this assertion is retired with the chip strip.
- **Genuine multi-entity bundling stays in data, not in rendering.** Where an upstream publisher bundles two entities into one row (e.g. CEA "Jammu & Kashmir and Ladakh" combined capacity attributed to U08 only  -  see `datasets/energy/_meadow/cea/2026-03/installed_capacity_*.json:37`), that is a DATA decision documented in the meadow file's notes; the MAP still renders both U08 and U09 polygons at their true location, with U09 simply showing the "no data" render-state (same as any state with a missing observation).

#### D.1.A - Retire the Lakshadweep chip-strip + extractor (follow-up sweep PR)

Out of immediate-fix scope (Phase A is the bug-fix cohort), but called out so the next pass picks it up. Files to touch:

| File | Action |
|---|---|
| `frontend/src/lib/lakshadweep.ts` | DELETE (and any similar extractor files for other UTs). |
| `frontend/src/lib/lakshadweep.test.ts` | DELETE. |
| `docs/concepts/unmapped-regions.md` | DELETE or mark superseded by [docs/concepts/boundary-data-philosophy.md](../docs/concepts/boundary-data-philosophy.md) addendum "all entities render on the map at true location". |
| `docs/architecture/frontend/map.md` | Remove the "legacy Lakshadweep inset" reference; add note that all UTs render at true geographic location. |
| `frontend/e2e/golden-path.spec.ts` lines 74-87 | Remove the chip-strip + Lakshadweep-label assertions. |
| `backend/yen_gov/coverage.py` lines 77, 667 (and any "intentionally excluded" UT carve-outs) | Remove the UT-exclusion clause; coverage rows reflect actual data presence/absence, not editor-curated allow-lists. |
| Any ADR (ADR-0029 if it exists) that codifies the chip-strip pattern | Amend with a 2026-05-29 "retired per user mandate: all entities render on the map at true location" entry. |

Sequenced AFTER Phase A (A.1 -> A.2 -> A.3 -> A.4) to avoid coupling the registry-sync work with the chip-strip teardown. The two should not bundle.

---

## PR sequence (small, sequential)

```
B.1 + B.2 (subagent dispatches, parallel)
   |
   v
A.1 (pipeline + snapshot, gated on B verdicts)
   |
   v
A.2 + A.3 (registry sync + attribution centralization, can bundle into one PR)
   |
   v
A.4 (Playwright per-state coverage spec)
   |
   v
D.1.A (retire Lakshadweep extractor + chip-strip + coverage UT-exclusion - independent sweep PR)
   |
   v
C.0 (schema enum bump + boundaries.ts type extension - shared groundwork)
   |
   v
C.1 (Blocks - first new level, proves the section 4a pattern end-to-end)
   |
   v
C.2 (Panchayats) || C.3 (ULB Wards) || C.4 (J&K Villages) || C.5 (PC v2 LGD)
   (these 4 are mutually independent after C.0 + C.1; can ship in any order)
   |
   v
C.6 (Susewind 2014 AP overlay - conditional on B.1)
```

Each PR is one row of the ready-reckoner; mark the row `In progress -> done -> SHA stamped` after each merge.

---

## Subagent dispatch summary (for the next agent to invoke)

The agent on the next turn should immediately dispatch B.1 + B.2 in parallel via `runSubagent`:

**B.1 dispatch**:
```
agentName: "Explore"
description: "S01 AP post-2014 AC source hunt"
prompt: <Phase B.1 prompt scope text above + worker path C:\Users\kumarsnaveen\Downloads\NawiN\personal\gitrepos\yen-gov-r0-d7-recon + upstream canonical reference https://github.com/ramSeraph/indianopenmaps display-server JSON routes + writes verdict to notes/2026-05-29-s01-ap-source-hunt-verdict.md>
```

**B.2 dispatch**:
```
agentName: "Explore"
description: "S03 Assam post-2023 AC source hunt"
prompt: <Phase B.2 prompt scope text above + same worker path + same upstream reference + writes verdict to notes/2026-05-29-s03-assam-source-hunt-verdict.md>
```

After both verdicts return, the agent updates this plan-doc rows B.1 + B.2 from `Not started` to `done` with the verdict-file SHAs, then opens PR-A1 against the verdict outcomes.

---

## Handover

Worker worktree: `C:\Users\kumarsnaveen\Downloads\NawiN\personal\gitrepos\yen-gov-r0-d7-recon` on `feat/d7-ac-lgd-universal` (currently 3 commits ahead of `origin/main`; B.1/B.2 verdicts land first as a separate `feat/boundary-source-hunt-verdicts` branch; A.1 onwards rebase or branch fresh from `origin/main` post-B-merge).

**Upstream canonical references** (subagents probe these fresh; no ephemeral recon artifacts are referenced from this plan per [CLAUDE.md](../CLAUDE.md) section 2):
- ramSeraph display-server JSON route catalogue: https://github.com/ramSeraph/indianopenmaps (574 routes across 21 buckets; B.1 + B.2 subagents enumerate fresh from the canonical upstream)
- Bhuvan portal: https://bhuvan-app1.nrsc.gov.in/
- Delimitation Commission of India: https://delimitation-commission.gov.in/
- DataMeet community: https://github.com/datameet

The 5-gate DoD applies to every PR in this plan. Phase A and Phase C share the same gates (validate + pytest + svelte-check + vitest + browser-smoke per [CLAUDE.md](../CLAUDE.md) section 9 + section 13). **Browser-smoke is a PRE-PR gate, not a post-merge verification**  -  see section Browser-smoke routes below.
