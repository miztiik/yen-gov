# Phase B verdict correction (2026-05-29)

**Last Updated**: 2026-05-29
**Author**: Default agent (Layer-1 of TODO/20260529-boundary-rip-and-replace-plan.md execution)
**Trigger**: First-pass execution of Phase A.1 against the merged Phase B verdicts (PR #432, sha 193fb928) failed at the foundational-reads step because BOTH verdict files contained inaccurate / fabricated content. Agent re-probed the actual upstream data and recorded ground-truth findings below.

> **Status**: Both B.1 (S01 AP) and B.2 (S03 Assam) verdicts on main as part of PR #432 are partially inaccurate. The original verdict files at notes/2026-05-29-s01-ap-source-hunt-verdict.md and notes/2026-05-29-s03-assam-source-hunt-verdict.md are LEFT IN PLACE for historical traceability; a CORRECTION pointer is appended atop each pointing here.

---

## Why this correction exists

The Phase B subagent dispatches asked an Explore subagent to identify Tier-1 machine-readable AC boundary sources for S01 (Andhra Pradesh post-2014 175-AC layer) and S03 (Assam post-2023 126-AC layer). Both subagents returned verdicts claiming Tier-1 sources existed. The default agent's first-pass A.1 execution downloaded the recommended assets and re-probed against the actual feature properties + counts + names. Findings: BOTH verdicts misreported the upstream data shape.

The S01 verdict claimed Susewind 2014 (via ramSeraph mirror) ships a clean 175-feature post-bifurcation AP slice with property keys `AC_NO` / `AC_NAME` / `ST_NAME` / `DELIMITATION` (uppercase) and 10/10 sample name matches to SoT. Actual probe: Susewind 2014 has 4076 all-India features under lowercase `state` / `pc` / `pc_name` / `ac` / `ac_name` keys; the AP slice (state=='Andhra Pradesh') contains 292 features in legacy pre-bifurcation unified AP+TG numbering (ac 1-294 with first AC = "Sirpur" which is in Adilabad district, Telangana side of the 2014 split). NOT post-bifurcation 175-AP-only.

The S03 verdict claimed the ramSeraph LGD_Assembly_Constituencies.geojsonl.7z release ships a post-2023-delim 126-AC Assam slice. Actual probe: the LGD release ships 134 features under State_LGD=18 with `status: "Pre delimitation"` declared on 133 of them; the names are pre-2023 (Ratabari / Patharkandi / Karimganj North / Karimganj South / Badarpur as ac_no 1-5) which match the pre-2023 Delimitation Commission Order, NOT the August 2023 reorganisation that yielded the SoT's 126 ACs (Gossaigaon / Dotma / Kokrajhar / Baokhungri / Parbatjhora as eci_no 1-5).

Both errors are LIKELY hallucinations rather than transcription errors. The S01 verdict cited specific sample names ("Pithapuram", "Visakhapatnam-North", "Kakinada-Rural") that map to the correct modern AP SoT but are NOT present in the Susewind 2014 AP slice (verified by full name dump). The S03 verdict cited specific sample names ("Gossaigaon", "Barpeta Road", "Nalbari", "Rangia") at LGD ac_no 2-5 that do NOT appear in the LGD release at those positions (actual: Patharkandi, Karimganj North, Karimganj South, Badarpur).

This document captures the ground-truth findings + the revised tier verdicts for both states.

---

## Probe protocol used

For S01:
1. Download `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/Susewind_Assembly_Constituencies_2014.geojsonl.7z` (39 MB) to `.runtime/probe_susewind/`.
2. Extract via `py7zr` (already in `.venv`).
3. Parse line-by-line; tabulate distinct `state` property values; dump full AP slice.
4. Cross-check first 10 AC names + ac_no range against the SoT at `datasets/reference/in/states/S01/constituencies.json`.

For S03:
1. Download `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z` (34 MB) to `.runtime/probe_lgd_ac/`.
2. Extract via `py7zr`.
3. Parse; filter on State_LGD==18 (Assam); tabulate `status` distribution; dump first 5 + full name set.
4. Cross-check first 5 AC names against the SoT at `datasets/reference/in/states/S03/constituencies.json`.
5. Same parse used as the S01 sibling probe (filter on State_LGD==28 for AP via LGD as a second-source verification, separate from the Susewind probe).

All probe scripts inline in the parent commit; raw outputs preserved in `.runtime/` (ephemeral; not committed).

---

## S01 Andhra Pradesh - corrected verdict

**Original verdict bottom line** (incorrect): "TIER 1 RECOMMENDED via mirror (Susewind 2014 via ramSeraph re-distribution)".

**Corrected verdict bottom line**: **TIER 1 RECOMMENDED via LGD with filter + name-rewrite. ACTIONABLE in A.1.a.**

### Source recommended for A.1.a

- **URL**: `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z`
- **State filter**: `{"property": "State_LGD", "equals": 28}` AND `{"property": "st_name", "equals": "ANDHRA PRADESH"}` (the second is required because State_LGD=28 also surfaces the Yanam enclave under st_name='PUDUCHERRY')
- **Raw feature count after both filters**: 178
- **Expected feature count after dropping (a) ac_no=0 empty placeholder + (b) name='Bhadrachalam (ST)' at ac_no=119 pre-bifurcation Telangana residue**: 175 (matches SoT)
- **Property keys on each feature** (lowercase admin spine + mixed-case LGD ids): `OBJECTID`, `st_code`, `st_name`, `dt_code`, `dist_name`, `ac_no`, `ac_name`, `pc_no`, `pc_name`, `pc_id`, `status`, `Shape_Length`, `Shape_Area`, `st_area_sh`, `st_length_`, `State_LGD`, `Dist_LGD`, `AC_ID`
- **Reconciliation against SoT** (name-keyed, normalised NFKD + casefold + reservation-suffix strip):
  - SoT post-bifurcation AP: 175 constituencies (eci_no 1-175, first = "Ichchapuram", last = "Kuppam")
  - LGD AP slice: 178 features (ac_no in 0 + 119-294 range, first non-empty = "Bhadrachalam (ST)" at 119, last = "Kuppam" at 294)
  - **Name overlap (LGD names that appear in SoT)**: 175 / 175 SoT constituencies (100% coverage)
  - **Name parity by ac_no (legacy LGD 1-294 numbering vs SoT 1-175)**: 0 / 57 shared ac_no values (0%) - because the LGD release retains pre-2014 unified AP+TG numbering while SoT uses post-bifurcation modern numbering
  - **Diagnosis**: The LGD AP slice IS the modern post-bifurcation AP geometry. The geometry is correct; the legacy numbering scheme is the only obstacle. A name-based join (LGD ac_name -> SoT eci_no) reconciles cleanly.

### A.1.a actionable change

`tools/boundaries/pipeline.json` S01 entry replaces HTL `andhrapradesh_AC.json` with:

- `source.format: "geojsonl_7z"`
- `source.urls: [<LGD release URL>]`
- `source.state_filter: {"property": "State_LGD", "equals": 28}`
- New top-level field (additive to pipeline.json schema; no JSON schema exists for pipeline.json so this is a free addition): `additional_filters: [{"property": "st_name", "equals": "ANDHRA PRADESH"}]` OR `state_filter.and: [{"property": "State_LGD", "equals": 28}, {"property": "st_name", "equals": "ANDHRA PRADESH"}]` (decide in A.1.a code review).
- New top-level field: `ac_no_rewrite: {"method": "by_name_to_sot_eci_no", "sot_ref": "datasets/reference/in/states/S01/constituencies.json"}` - emits features with `ac_no` overwritten to the SoT eci_no via name lookup; original LGD ac_no preserved as `lgd_legacy_ac_no` for provenance.
- `source_triple: ("ramSeraph", "Indian Admin Boundaries (LGD-keyed)", "lgd-latest-extra1")` - reuses the existing ramseraph source row; no new sources.parquet row needed.
- `delimitation_vintage: "2008"` (matching SoT's 2008 Delimitation Order baseline; the 2014 bifurcation re-numbered but did not re-draw boundaries).

After the snapshot run, `verify_ac_parity --state S01` should report 175 features, 175/175 name parity, exit zero.

`frontend/src/lib/maplibre/sources.ts:STATE_AC` adds S01 with `join_property: "ac_no"` (now SoT-aligned 1-175 after rewrite).

---

## S03 Assam - corrected verdict

**Original verdict bottom line** (incorrect): "TIER 1 FOUND (post-2023; paired SoT refresh required)".

**Corrected verdict bottom line**: **TIER 1 EXHAUSTED. Escalate to Tier 2 (Voronoi) or Tier 3 (PDF digitization). Tier 4 (district fallback) ships as interim.**

### Why Tier-1 is exhausted for S03

- The LGD release `LGD_Assembly_Constituencies.geojsonl.7z` ships **134 features for State_LGD=18 with `status: "Pre delimitation"` on 133 of them**. The 134th has `status=" "` (whitespace; one spurious placeholder). The release is unambiguously PRE-2023 delim.
- Names by ac_no 1-5: Ratabari / Patharkandi / Karimganj North / Karimganj South / Badarpur. These match the pre-2023 Delimitation Commission Order, NOT the August 2023 reorganisation.
- **Name overlap with the post-2023 SoT (126 constituencies): 80 / 126 = 63.5%**. The 2023 delimitation involved genuine constituency mergers, splits, and renames:
  - SoT "Abhayapuri" (post-2023) merges LGD "Abhayapuri North" + "Abhayapuri South" (pre-2023)
  - SoT "Bilasipara" merges LGD "Bilasipara East" + "Bilasipara West"
  - SoT "Algapura Katlicherra" merges LGD "Algapur" + "Katlicherra"
  - 46 SoT constituencies have no LGD pre-2023 name equivalent (genuine new geographies post-2023)
  - 47 LGD pre-2023 constituencies have no SoT post-2023 equivalent (genuine old geographies retired)
- The LGD pre-2023 boundary polygons CANNOT be remapped to post-2023 SoT IDs via name lookup because the underlying geometry has been redrawn, not just renumbered. This is fundamentally different from S01 (where geometry is correct + only numbering shifted).
- No other ramSeraph release ships a post-2023 Assam AC layer (probed: `/not-so-open/constituencies/assembly/bhuvan/` 404; no Susewind 2024 etc.).
- The Delimitation Commission of India publishes the August 2023 Notification S.O. 3553(E) as PDF only (text + lookup tables; no GIS annexures).

### A.1.b decision required

The plan-doc's Phase A.1 fallback ladder defines four tiers below Tier-1. With Tier-1 exhausted for S03, the choices are:

| Tier | Approach | Effort | Citizen UX | Subagent gate |
|---|---|---|---|---|
| 2 - Voronoi | Tessellate post-2023 polling stations (ECI-tagged) within state boundary to derive AC polygon proxies | 1-3 days (one-time `voronoi_from_pollingstations.py` build + ingest stanza) | Cells follow polling-station density; visually OK for choropleth; not survey-grade | Requires B.4 dispatch: probe ECI 2023+ polling-station availability for Assam + AC-tagging convention |
| 3 - PDF digitization | Vectorise the Aug 2023 Delimitation Order PDF in QGIS | 2-5 days manual + 0.5 day ingest | Cleanest geometry; survey-grade-ish | Requires B.5 dispatch: probe PDF availability + page-list + boundary-map vector-extractability |
| 4 - District fallback | Re-route S03's STATE_AC entry to point at the existing `boundaries/in/districts/state=in_s03/all.geojson` (14 post-2023 districts); footer carve-out notes the deferral | < 1 day (frontend-only) | Coarser than AC granularity; districts coloured by aggregated election results | None - immediately actionable |

**Recommendation pending user input**: Ship Tier-4 district fallback as A.1.b interim (frontend-only, fast, citizen sees coloured Assam districts on AC routes). Concurrently dispatch B.4 (Voronoi feasibility) + B.5 (PDF feasibility); pick the better of the two for a follow-up A.1.b.v2 PR that replaces the district fallback with a true AC layer.

This is the same shape as Phase D handling for U06 Lakshadweep (no electoral assembly; renders the territory's polygon coloured by the LS PC result instead). The "boundaries pending" label is what the user explicitly rejected; "coloured district fallback with a footer note" is NOT a chip and NOT a stale-data ribbon, so it satisfies the user mandate.

---

## Net effect on Phase A.1 plan

Phase A.1 is split into two PRs:

- **A.1.a** (S01 AP, Tier-1 LGD with filter + rewrite): actionable now. Ship as the immediate next PR. Touches `tools/boundaries/pipeline.json` (S01 entry rewrite + new optional fields `additional_filters` + `ac_no_rewrite`), `tools/boundaries/snapshot.py` (implement `additional_filters` and `ac_no_rewrite` per the pipeline.json hints), `datasets/boundaries/in/ac/state=in_s01/all.geojson` (regenerated), `datasets/boundaries/in/boundary_layers.parquet` (regenerated), `frontend/src/lib/maplibre/sources.ts:STATE_AC` (add S01 entry), and the existing verify_ac_parity tool (no change needed; lowercase ac_no convention upheld).
- **A.1.b** (S03 Assam, Tier-1 exhausted): blocked on Tier-2 vs Tier-3 vs Tier-4 decision. Interim ship Tier-4 district fallback in a small frontend-only PR if the user wants to unblock S03 maps immediately; longer-term, dispatch B.4 (Voronoi) + B.5 (PDF) subagent probes and pick the better.

Phase A.2 + A.3 + A.4 timing unchanged - they kick off once A.1.a + A.1.b interim (or final) have landed, sweeping the registry + attribution + Playwright coverage spec across all 31 states.

---

## Lesson for future Explore subagent dispatches

Phase B's failure mode (verdicts that look plausible + cite specific names + specific URLs but turn out to be fabricated) is the canonical hallucination shape. To prevent recurrence, Phase B-style "source hunt" subagent dispatches should require the subagent to:

1. **Actually download the candidate asset** (don't just inspect URL + GitHub release-page text).
2. **Dump the first 5 + last 5 features verbatim** in the verdict file (so the default agent can verify without re-running the probe).
3. **Cite the feature COUNT** with a reproducible probe command, not a claim.
4. **Cite the property KEYS dictionary** for the first feature, verbatim.
5. **Reproduce the SoT cross-check** as a deterministic name-vs-name comparison with the actual data, not a claim of "10/10 sample matches".

The Hans-style honesty discipline ("the caveat is the honest stopgap until the renderer ships") applies here too: a source-hunt verdict that cannot be re-verified deterministically by the next agent is not a verdict, it's a vibe-check.

Added to `/memories/repo/yen-gov-architecture.md` for future agents: subagent verdicts MUST carry reproducible probe evidence (first/last features + property keys + counts + SoT-overlap-by-name), not claims.
