# Phase D.1 — AC consolidation snapshot recon (2026-05-25)

**Scope**: gating decision for Phase D.2–D.5 per [`TODO/20260524-boundary-coverage-expansion-plan.md` §D.1](../TODO/20260524-boundary-coverage-expansion-plan.md#d1--first-snapshot-recon-one-shot-gating). Read-only audit of the upstream LGD AC release vs the source-of-truth `datasets/reference/in/states/{S,U}{nn}/constituencies.json` files.

**Tool**: `tools/boundaries/recon_d1_ac.py` (new in this PR; one-shot — deletable after D.5 lands).

---

## 1. Snapshot details

| Field | Value |
| --- | --- |
| Upstream URL | `https://github.com/ramSeraph/indian_admin_boundaries/releases/download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z` |
| Asset name | `LGD_Assembly_Constituencies.geojsonl.7z` |
| Archive bytes | 35,160,079 |
| Archive SHA-256 | `5b8c64bd1ed58996e397effcd4dfc2e18d6e273c3504a7284d5e1672037cdcb4` |
| Payload member | `LGD_Assembly_Constituencies.geojsonl` (newline-delimited GeoJSON) |
| Producer | ramSeraph republisher — `indian_admin_boundaries` GitHub releases (rolling LGD mirror) |
| Underlying source | BharatMaps / LGD (Ministry of Panchayati Raj), survey-grade |
| Licence | CC0 1.0 (per ramSeraph repo `LICENSE`) |
| Vintage anchor | rolling LGD mirror; carries per-feature `status` field (see §4) |
| Fetched on | 2026-05-25 |

Recon-only artefact path lives under `.runtime/raw/` per [CLAUDE.md §2](../CLAUDE.md#2-path-rules); not referenced here verbatim.

## 2. Feature property schema (resolves `pipeline.json#staged_inputs[0]` TBDs)

100% coverage across all 4,177 features. Discovered keys (verbatim, alphabetical):

| Property | Type | Coverage | Sample values | Role |
| --- | --- | ---: | --- | --- |
| `AC_ID` | str | 100% | `'19001'`, `'19002'`, `'19011'` | **Globally-unique LGD AC code** (5 digits: 2-digit `State_LGD` + 3-digit `ac_no` zero-padded) |
| `ac_no` | int | 100% | `1`, `2`, `11` | Per-state AC number (matches SoT `eci_no` ordering for most states) |
| `ac_name` | str | 100% | `'MEKLIGANJ (SC)'`, `'MATHABHANGA (SC)'`, `'KALCHINI (ST)'` | Display name (UPPERCASE + trailing `(SC)`/`(ST)` reservation suffix) |
| `State_LGD` | int | 100% | `19`, `7`, `12` | Parent state LGD code (mixed-case property name; do not snake-case) |
| `st_code` | str | 100% | `'19'`, `'07'`, `'12'` | Census 2011 state code (zero-padded string) |
| `st_name` | str | 100% | `'WEST BENGAL'`, `'DELHI'`, `'ARUNACHAL PRADESH'` | Parent state name (UPPERCASE) |
| `Dist_LGD` | int | 100% | `308`, `664`, `313` | Parent district LGD code |
| `dt_code` | str | 100% | `'329'`, `'774'`, `'341'` | Census 2011 district code (zero-padded string) |
| `dist_name` | str | 100% | `'COOCH BEHAR'`, `'ALIPURDUAR'`, `'HOWRAH'` | Parent district name |
| `pc_id` | int | 100% | `1903`, `1901`, `1902` | Parent parliamentary constituency LGD id |
| `pc_no` | int | 100% | `3`, `1`, `2` | Parent PC number within state |
| `pc_name` | str | 100% | `'JALPAIGURI (SC)'`, `'COOCHBEHAR (SC)'`, `'ALIPURDUARS (ST)'` | Parent PC display name |
| `status` | str | 100% | `' '`, `'Pre delimitation'` | Vintage tag — `' '` = post-delim / current; `'Pre delimitation'` = stale boundary not yet refreshed upstream |
| `OBJECTID` | int | 100% | `1`, `2`, `3` | LGD-internal row id (not stable across vintages) |
| `Shape_Area` | float | 100% | — | LGD-computed area (Web Mercator projection) |
| `Shape_Length` | float | 100% | — | LGD-computed perimeter |
| `st_area_sh` | float | 100% | — | Duplicate of `Shape_Area` (different precision) |
| `st_length_` | float | 100% | — | Duplicate of `Shape_Length` (different precision) |

**Resolution for `pipeline.json#staged_inputs[0]`** (the one with `TBD_lgd_ac_code` + `TBD_ac_name` placeholders):

- `id_property` = `AC_ID` (globally unique; preferred over per-state `ac_no` for canonical join keys; mirrors Phase D.0's choice of `State_LGD` over per-state Wikipedia name).
- `name_property` = `ac_name`.
- `coord_precision` recommendation: `2` (match Phase D.0 state polygons).
- `state_filter` plan-doc example uses `State_LGD=<lgd>` — confirmed the property name is mixed-case `State_LGD`, not snake-case (same caveat as Phase D.0 state polygons).

## 3. National totals

| Metric | Value |
| --- | ---: |
| Total features in LGD release | **4,177** |
| Features routable to a current ECI state/UT | 4,176 |
| Features with `State_LGD=0` (sentinel; unmapped) | 1 |
| SoT grand total (all `constituencies.json`, 31 files) | **4,113** |
| Net LGD - SoT delta | +64 |

The +64 delta is concentrated in: Andhra Pradesh (+4), Assam (+8), Karnataka (+1), Maharashtra (+15), Rajasthan (+2), Sikkim (+6), Manipur (+8), Jharkhand (+15 — possibly pre-Bihar-bifurcation residue), J&K (+11), Ladakh (+5), with offsetting deficits in Gujarat (-18), MP (-5), Meghalaya (-1), Kerala (-1), Delhi (0), West Bengal (-1), Puducherry (-1), Telangana (-1). Plan-doc estimate "~4,123 ACs nationally pre-2026" tracks SoT, not LGD; the LGD release is ahead by ~1.5%.

## 4. Vintage interpretation

The `status` property is the per-feature vintage tag:

- `' '` (single space) — current / post-delimitation feature.
- `'Pre delimitation'` — stale boundary not yet refreshed by LGD; rare; concentrated in Assam + a few S04/S22/U07 rows.

This is the most useful single signal in the file. ramSeraph's republisher does not strip these; downstream consumers (us included) MUST decide whether to filter `status == 'Pre delimitation'` rows or render them with a warning. Phase D.2 promote PRs should make this filter decision in `pipeline.json` (e.g. an `exclude_filter=status=Pre delimitation`).

> **Empirical correction (added 2026-05-25 by Phase D.2 PR)**: when the D.2 promote PR snapshotted the 10 D.1-eligible states and applied the recommended `exclude_filter`, 9 of 10 states reported `exclude_filter kept N (dropped 0 matching)` — i.e. they carry zero Pre-delim rows — while S17 Nagaland reported `exclude_filter kept 0 (dropped 60 matching)` — i.e. ALL 60 Nagaland ACs are tagged Pre delimitation. Empirical reason: Nagaland was constitutionally exempted from the 2008 Delimitation (Article 371A); the 1976-vintage 60-AC layout is what ECI uses for current elections and what citizens see on `/s/nagaland/t/elections`. Filtering Pre-delim therefore erases Nagaland entirely from the canonical store while not affecting any of the other 9 D.2-target states. The "concentrated in Assam + S04/S22/U07" hypothesis above is INCORRECT for the current LGD release: the actual Pre-delim concentration is in S17 (100%) + likely S03 Assam (also high — un-measured for this PR since S03 is D.3 keep-current). Phase D.2 PR therefore did NOT apply the `exclude_filter` directive to any of the 10 entries; the `apply_exclude_filter` function was kept in `tools/boundaries/snapshot.py` as a general-purpose capability with 6 unit tests, but is not invoked from `pipeline.json` today. Future PRs that promote S03 / S22 / U07 should measure their per-state Pre-delim distribution before deciding whether to filter.

**Assam (S03) verdict** — does LGD reflect 2023 re-delim?

- LGD count: 134 ACs vs SoT 126.
- Name-match (with reservation-suffix stripped): **1%** — names are radically different between LGD and SoT.
- Verdict: **D.3 Outcome 3 — mixed / unclear**. The +8 feature delta + 1% name parity strongly suggests LGD carries the **pre-2023 layout PLUS the 8 newly-created post-delim ACs** without retiring the pre-delim originals, with names that don't match SoT's English-Wikipedia transliteration. NOT eligible for D.2 promote; NOT cleanly eligible for D.3 swap. Recommend: keep current source (HTL) for S03 in D.3; file an open question for Hans + Max on whether to ingest the LGD raw for an Assam-specific delim audit in a follow-up PR.

**J&K (U08) verdict** — does LGD have the 90-AC 2022 re-delim layout?

- LGD count: 101 ACs vs SoT 90.
- Name-match (with reservation-suffix stripped): **6%** — overwhelmingly different names.
- Verdict: **D.4 Outcome 3 — mixed / unclear**. The 101-feature count is 11 ahead of SoT's post-2022 90; the 6% name-match suggests LGD carries the **pre-2019-statehood 87 + extras** rather than the post-2022 90-AC layout. NOT eligible for promote. Recommend: keep current source (shijithpk) for U08 in D.4.

**Ladakh (U09)** — 5 features in LGD, SoT 0 (no legislative assembly). Verdict: keep-current (SoT-empty); recommend Phase D.2+ `exclude` LGD U09 rows or carry them as info-only.

## 5. Per-state inventory + parity verdicts

Methodology:
- LGD features grouped by `State_LGD` → mapped to ECI state code via inline state_lgd → ECI resolver (mirrors `backend.yen_gov.canonical.state_lgd_resolver.build_state_lgd_to_eci_map`; filters to currently-valid state/UT entities only).
- Name-match comparison: case-fold + NFKD diacritic-strip + trailing `(SC)`/`(ST)`/`(GEN)` reservation-suffix strip + collapse non-alphanumerics. Exact-equality after that fold.
- Verdict thresholds: `count_match == True` AND `name_match >= 95%` → `eligible-D.2`. Special-case rules for S03 (Assam D.3) and U08 (J&K D.4).

| ECI | State / UT | state_lgd | LGD count | SoT count | Count match | Name match % | Verdict |
| --- | --- | ---: | ---: | ---: | :---: | ---: | --- |
| S01 | Andhra Pradesh | 28 | 179 | 175 | N | 0% | keep-current (count mismatch + 0% names; likely pre-bifurcation residue) |
| S02 | Arunachal Pradesh | 12 | 61 | 50 | N | 92% | keep-current (count mismatch LGD 61 vs SoT 50) |
| **S03** | **Assam** | 18 | 134 | 126 | N | 1% | **Assam-D.3: parity-mismatch (keep HTL; file open question)** |
| **S04** | **Bihar** | 10 | 243 | 243 | Y | 99% | **eligible-D.2** |
| S05 | Goa | 30 | 41 | 40 | N | 100% | keep-current (count +1; investigate single extra) |
| S06 | Gujarat | 24 | 164 | 182 | N | 100% | keep-current (count -18; LGD short by 18; investigate likely upstream-incomplete release) |
| **S07** | **Haryana** | 6 | 90 | 90 | Y | 97% | **eligible-D.2** |
| **S08** | **Himachal Pradesh** | 2 | 68 | 68 | Y | 99% | **eligible-D.2** |
| S10 | Karnataka | 29 | 225 | 224 | N | 96% | keep-current (count +1; investigate) |
| S11 | Kerala | 32 | 141 | 140 | N | 82% | keep-current (count +1 + 82% names) |
| S12 | Madhya Pradesh | 23 | 225 | 230 | N | 97% | keep-current (count -5) |
| S13 | Maharashtra | 27 | 303 | 288 | N | 98% | keep-current (count +15; investigate possible pre-delim residue) |
| S14 | Manipur | 14 | 68 | 60 | N | 90% | keep-current (count +8) |
| S15 | Meghalaya | 17 | 59 | 60 | N | 100% | keep-current (count -1; investigate single missing) |
| S16 | Mizoram | 15 | 40 | 40 | Y | 88% | keep-current (name-match 88% < 95%) |
| **S17** | **Nagaland** | 13 | 60 | 60 | Y | 100% | **eligible-D.2** |
| **S18** | **Odisha** | 21 | 147 | 147 | Y | 97% | **eligible-D.2** |
| **S19** | **Punjab** | 3 | 117 | 117 | Y | 100% | **eligible-D.2** |
| S20 | Rajasthan | 8 | 202 | 200 | N | 100% | keep-current (count +2) |
| S21 | Sikkim | 11 | 38 | 32 | N | 90% | keep-current (count +6) |
| S22 | Tamil Nadu | 33 | 235 | 234 | N | 88% | keep-current (count +1 + 88% names) |
| **S23** | **Tripura** | 16 | 60 | 60 | Y | 100% | **eligible-D.2** |
| S24 | Uttar Pradesh | 9 | 404 | 403 | N | 100% | keep-current (count +1; investigate) |
| S25 | West Bengal | 19 | 293 | 294 | N | 91% | keep-current (count -1 + 91% names) |
| **S26** | **Chhattisgarh** | 22 | 90 | 90 | Y | 99% | **eligible-D.2** |
| S27 | Jharkhand | 20 | 96 | 81 | N | 98% | keep-current (count +15; investigate likely pre-bifurcation) |
| **S28** | **Uttarakhand** | 5 | 70 | 70 | Y | 100% | **eligible-D.2** |
| S29 | Telangana | 36 | 118 | 119 | N | 98% | keep-current (count -1) |
| **U05** | **NCT of Delhi** | 7 | 70 | 70 | Y | 97% | **eligible-D.2** |
| U07 | Puducherry | 34 | 29 | 30 | N | 93% | keep-current (count -1) |
| **U08** | **Jammu and Kashmir (UT)** | 1 | 101 | 90 | N | 6% | **J&K-D.4: parity-mismatch (keep shijithpk)** |
| U09 | Ladakh | 37 | 5 | 0 | N | 0% | keep-current (no legislative assembly; SoT-empty by design) |

ECI codes are NOT alphabetical (`entities.json` is the SoT for state_lgd → ECI → display-name mapping). The verdict column is based on count + name parity only; the state-name column is informational.

## 6. Roll-up

| Bucket | Count | States/UTs |
| --- | ---: | --- |
| **Eligible for D.2 promotion** | **10** | **S04** Bihar, **S07** Haryana, **S08** Himachal Pradesh, **S17** Nagaland, **S18** Odisha, **S19** Punjab, **S23** Tripura, **S26** Chhattisgarh, **S28** Uttarakhand, **U05** NCT of Delhi |
| Special-case Assam (D.3) | 1 | S03 — mixed; keep HTL |
| Special-case J&K (D.4) | 1 | U08 — mixed; keep shijithpk |
| Keep current (count mismatch or name-match < 95%) | 19 | S01 Andhra Pradesh, S02 Arunachal Pradesh, S05 Goa, S06 Gujarat, S10 Karnataka, S11 Kerala, S12 Madhya Pradesh, S13 Maharashtra, S14 Manipur, S15 Meghalaya, S16 Mizoram, S20 Rajasthan, S21 Sikkim, S22 Tamil Nadu, S24 Uttar Pradesh, S25 West Bengal, S27 Jharkhand, S29 Telangana, U07 Puducherry |
| Keep current (no assembly) | 1 | U09 Ladakh |

**National total promotable in D.2 today**: ~1,065 ACs across 10 states/UTs (out of SoT 4,113 → 26%). The remaining 74% (3,048 ACs) either require state-by-state investigation (count mismatches; mostly off-by-1 or off-by-15-with-pre-bifurcation-residue signature) or are blocked behind D.3 (Assam) / D.4 (J&K) carve-out decisions.

## 7. Implications for D.2–D.5

1. **D.2 scope is narrower than the plan's "28 states" optimistic estimate**. Realistic first-cut D.2 ships 10 states with zero parity friction. The remaining 18 keep-current rows are not blockers — they are deferred to follow-up D.2.b sub-PRs (one per state) where the count-delta root cause is investigated (pre-bifurcation residue; pre-delim/post-delim mix; LGD vintage drift).

2. **`status == 'Pre delimitation'` filter is a D.2 prerequisite**. The `status` field is the cleanest single signal to exclude stale boundaries. Phase D.2 PRs should add an `exclude_filter=status=Pre delimitation` directive in `pipeline.json` (or a new `--exclude-where` flag on `snapshot.py`). Counts above are pre-filter; post-filter counts may shift the verdict for a handful of borderline states (e.g. Assam may drop from 134 → ~126 after filter, which would change S03's count-match verdict). **[2026-05-25 D.2 PR correction: empirically NOT a D.2 prerequisite for the 10 eligible states — 9 of 10 carry zero Pre-delim rows, S17 Nagaland carries 100% (constitutional exemption from 2008 Delimitation). The directive was added to `snapshot.py` as a general-purpose capability with 6 unit tests but NOT applied to any of the 10 D.2 entries. See §4 "Empirical correction" above. Future S03/S22/U07 promote PRs should measure per-state distribution before deciding.]**

3. **D.3 Assam**: outcome 3 (mixed / unclear). The recon-paper recommendation is **keep HTL** and **defer the LGD-side audit** to a follow-up PR scoped by Hans + Max + Fowler. The 1% name parity is too poor to assert "this is the same 126 ACs with different boundaries" — names suggest fundamentally different rows.

4. **D.4 J&K**: outcome 3 (mixed / unclear). Recommendation is **keep shijithpk**. The 101-vs-90 count + 6% name parity rule out a clean swap.

5. **D.5 wrap-up scope adjusts**: instead of "update sources doc to reflect 28 promoted states", it becomes "update sources doc to reflect 10 promoted states + 20 deferred + 2 explicit-keep". `boundary-data-sources.md` inventory table needs a new "Phase D.1 verdict" column added (post-D.5).

6. **The recon script `tools/boundaries/recon_d1_ac.py` should be retired in the D.5 PR** per CLAUDE.md §10 "Don't create helpers for one-time operations". The script is intentionally a single-purpose recon tool, not a permanent fixture of the pipeline.

## 8. Open questions (for Hans + Max + Fowler in D.3 follow-up)

1. Should LGD pre-bifurcation residue rows (e.g. S01 Andhra Pradesh with LGD 179 vs SoT 175 — likely includes 4 pre-Telangana-2014 ACs; and S27 Jharkhand with LGD 96 vs SoT 81 — likely 15 pre-Bihar-2000-bifurcation ACs) be filtered upstream of D.2 promote, or carried with a `vintage_pre_bifurcation` flag for historical-election cross-reference?
2. For **S06 Gujarat** (LGD 164 vs SoT 182), what explains LGD being short by 18? This is the only state where LGD UNDERCOUNTS SoT by a large margin; either LGD has a partial release (some Gujarat ACs un-published) or SoT carries a stale row count. Worth a direct download of LGD Gujarat-only AC roster to investigate.
3. For **S13 Maharashtra** (LGD 303 vs SoT 288), is the +15 a pre-2014 / pre-some-reorg residue? Maharashtra hasn't bifurcated; suggest the LGD upstream may carry retired ACs from a 2008 delim transition.
4. For Assam, is LGD's English transliteration (1% parity) driven by a different romanisation scheme (e.g. ISO 15919 vs IAST vs Wikipedia conventional) that a phonetic-distance metric (Levenshtein on Devanagari→Latin maps) could bridge? Worth a 30-line investigation before declaring D.3 a hard "keep HTL".
5. Should the U09 Ladakh 5 LGD features be ingested as a "reserved-for-future-assembly" subset, or filtered as noise?

These do not block this recon note from landing; they are inputs to the eventual D.3 carve-out PR.

---

**Recon authored**: 2026-05-25.
**Recon tool**: `tools/boundaries/recon_d1_ac.py` (ships in same PR).
**Next phase**: D.2 (promote 10 eligible states) — separate PR. Operator MUST re-run the recon if upstream archive SHA changes (the recon is byte-deterministic against a fixed archive).
