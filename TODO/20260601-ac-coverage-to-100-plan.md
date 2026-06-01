# Plan: Drive AC crosswalk coverage to 100% lgd_direct + unblock D1

**Status:** PROPOSED
**Author:** GitHub Copilot (orchestrator)
**Last Updated:** 2026-06-01
**Level:** 3 (multi-file structural; 4 execution rows; ships as 4 small PRs)
**Supersedes:** `TODO/20260530-eci-to-lgd-acid-migration-plan.md` Row D1 (DEFERRED) - this plan provides the path to UN-DEFER D1.

## Mandate

Close the 253-row `unmapped` gap in `datasets/taxonomy/ac_crosswalk.parquet` (today: 93.8% lgd_direct, 6.2% unmapped) by ingesting authoritative ECI AC boundaries (mirrored at `https://github.com/GarudadevDataServices/indian_mlas`) and stamping LGD codes per-AC into Source-of-Truth (SoT) files for states where in-repo boundary data is sufficient. Once coverage reaches effectively 100% lgd_direct AND S01/AP frontend is reworked off the `ac_no == eci_no` assumption, ship D1 (delete `apply_ac_no_rewrite_by_name`).

## Today's gap

253 unmapped, 12 states/UTs:

| State | Unmapped | Garuda has |
| --- | --- | --- |
| S03 Assam | 126 | 133 (full coverage) |
| U08 J&K | 90 | 94 (PRE-2022, NOT usable) |
| S06 Gujarat | 22 | 166 (vs SoT 182; partial close) |
| S12 Kerala | 6 | 141 (full coverage) |
| U07 Delhi | 2 | 70 (full coverage) |
| S15 Maharashtra | 1 | 302 (full coverage) |
| S20 Punjab | 1 | 117 (full coverage) |
| S21 Rajasthan | 1 | 201 (full coverage) |
| S22 Sikkim | 1 | 38 (close but verify) |
| S24 Tripura | 1 | 60 (full coverage) |
| S25 Uttar Pradesh | 1 | 403 (full coverage) |
| S29 Telangana | 1 | 121 (full coverage) |
| **Total** | **253** | |

Projected post-execution: **~90 unmapped (J&K only, deferred to user-sourced post-2022 file)**, i.e. ~98% lgd_direct on all states with a sourced AC boundary in-repo.

## Source

- **Producer:** Election Commission of India (AC boundaries are public-domain Government of India works).
- **Mirror:** `https://github.com/GarudadevDataServices/indian_mlas` `raw_data/india_asm.geojson` (commit `179806f`, 2025-12 vintage).
- **License:** public-domain (Government of India works).
- **Probe verified (2026-06-01):** 4,164 features, clean property shape `{st_code, st_name, pc_no, pc_name, pc_id, ac_no, ac_name, ac_id}` with `ac_id = st_code * 1000 + ac_no` matching the boundary harvester's expected `AC_ID` convention.
- **`sources.parquet` row to add:** `producer="Election Commission of India"`, `title="India Assembly Constituency boundaries"`, `vintage="2025-12"`, `license="public-domain (GoI works)"`, `url_main="https://eci.gov.in"`, `url_mirror="https://github.com/GarudadevDataServices/indian_mlas"`, `confidence_tier=2`, `is_issuing_authority=true`.

## Status reckoner

| # | Description | Status | PR | Risk |
| :-: | --- | --- | --- | :-: |
| I0 | This plan-doc + coverage doc + sources row spec | [ ] PENDING | _pending_ | L |
| I1 | Ingest Garuda for S03/S12/U07 (full-state new boundary files) + recompile crosswalk | [ ] PENDING | _pending_ | M |
| I2 | SoT lgd_ac_id stamps for 7 singletons (S15, S20, S21, S22, S24, S25, S29) + S06 Gujarat partial (22 LGD lookups) | [ ] PENDING | _pending_ | L |
| I3 | S01 AP frontend rework (replace `join_property_label: "ac_no"` + `sel.properties.ac_no` fallback with crosswalk reverse-map lookup); regenerate S01 boundary snapshot without `ac_no_rewrite` directive; visual smoke | [ ] PENDING | _pending_ | M |
| D1' | Delete `apply_ac_no_rewrite_by_name` + wiring + `ac_no_rewrite` directive + `test_boundary_snapshot_ac_no_rewrite.py`; parity oracle on S01 | [ ] BLOCKED-on-I3 | _pending_ | L |
| U08 | J&K post-2022 boundary ingest | [ ] BLOCKED-on-user-source | n/a | M |

## Execution rows

### Row I0 - Plan-doc + coverage doc + sources spec (this PR)

- Author this plan-doc.
- Author/update `docs/architecture/data/ac-boundary-coverage.md` enumerating current coverage state, the gap, the ingest plan, and the U08 J&K user-source requirement.
- Update `TODO/20260530-eci-to-lgd-acid-migration-plan.md` to cross-reference this plan as the un-defer path for D1.
- No data, no schema, no code change.

### Row I1 - Garuda ingest, full-state for S03 / S12 / U07

- Add the `sources.parquet` row per Source section above (`source_id` derived via `backend.yen_gov.canonical.citation.derive_source_id`).
- Slice `india_asm.geojson` per state, emit `datasets/boundaries/in/ac/state=in_<code>/all.geojson` for S03, S12, U07 (3 new files).
- Recompile `datasets/taxonomy/ac_crosswalk.parquet` via `tools/migrate/build_ac_crosswalk.py`.
- Expected delta: 134 ACs flip from `unmapped` to `lgd_direct` (S03 126 + S12 6 + U07 2).
- Gates: pytest `test_build_ac_crosswalk.py`, validate, boundaries-conform contract.
- **No frontend smoke required** (these states gain rendering coverage; render-quality verification is separate work).

### Row I2 - SoT lgd_ac_id stamps for singletons + S06 partial

- For each of the 7 singletons + the 22 Gujarat ACs not covered by Garuda's 166-feature file, look up LGD ac_no via `https://lgdirectory.gov.in/` and stamp `"lgd_ac_id": <int>` into the matching `datasets/elections/state=in_<code>/ac_<year>/sot.json` entry.
- Schema bump in same commit if needed (C1 #539 machinery already accepts `lgd_ac_id` on SoT).
- Recompile crosswalk.
- Expected delta: 29 ACs flip to `lgd_direct` via C1's SoT-precedence path.
- **Manual lookup tax** (~30 ACs): user-in-the-loop OR agent prepares candidate codes with reasoning, user confirms.

### Row I3 - S01 AP frontend rework + boundary regen

- Rework `IndicatorChoropleth` fill arm: replace `join_property_label: "ac_no"` with a crosswalk reverse-map lookup keyed on `lgd_ac_id` so AP fills work without the `ac_no == eci_no` assumption.
- Rework `StateAcMap` nav fallback: replace `sel.properties.ac_no` with `crosswalk.reverse(lgd_ac_id).eci_no`.
- Regenerate `datasets/boundaries/in/ac/state=in_s01/all.geojson` from Garuda (S01 has full 175 features in Garuda; replaces the LGD pre-bifurcation 1-294 numbering currently corrected by `apply_ac_no_rewrite_by_name`).
- Visual smoke: click 5 ACs on `/s/andhra-pradesh`, confirm correct seat highlights. **Human-in-the-loop verification required.**
- Gates: svelte-check, vitest, browser smoke per section 13.

### Row D1' - Retire apply_ac_no_rewrite_by_name (UN-DEFERRED)

- Delete `apply_ac_no_rewrite_by_name` from `tools/boundaries/snapshot.py` (L694) and its wiring at L1084.
- Remove the `ac_no_rewrite` directive from `config/elections.json` S01 entry.
- Delete `backend/tests/test_boundary_snapshot_ac_no_rewrite.py`.
- Parity oracle: render `/s/andhra-pradesh` before vs after; must be byte-identical because (a) I3 reworked the dependent frontend, (b) Row I1's S01 boundary regen already established the canonical-join rendering as the truth.
- Mark D1 in the parent migration plan-doc as DONE-by-supersession; cross-link this plan.

### Gap: U08 J&K (NOT covered)

The 90 J&K ACs CANNOT be closed by Garuda (its J&K is pre-2022 delim with 94 ACs covering different boundaries). Acceptable sources for a future ingest PR:

1. **Wikimedia Furfur SVG** (post-2022 delim, CC-BY-4.0, georeferenced) - convert SVG to GeoJSON via the `docs/how-to/digitize-ac-from-pdf.md` ladder.
2. **ECI delim notification PDF** (post-2022) - digitise via T3 QGIS path in same how-to doc.
3. **J&K Election Department release** if/when published.

Whoever sources the file: 90 features, each with `ac_no` 1-90 and `ac_name`, post-2022 delim. Plan opens a follow-up row when source is in hand.

## Distillation (per `docs/how-to/distill-a-plan.md`)

When each row closes, durable findings lift into:

| Row | Distillation target |
| --- | --- |
| I0 | `docs/architecture/data/ac-boundary-coverage.md` (NEW; per-state coverage matrix + gap-fill recipe). |
| I1 | `docs/architecture/data/canonical-store.md` (sources row schema for ECI AC boundaries); `docs/how-to/add-new-boundary-layer.md` (Garuda-style multi-state slicing pattern). |
| I2 | `docs/how-to/distill.md` "SoT lgd_ac_id stamping" subsection (manual LGD lookup workflow); inline note in `ac-boundary-coverage.md` table. |
| I3 | `docs/architecture/frontend/data-loading.md` (crosswalk reverse-map join pattern, retires `ac_no == eci_no` assumption); update `ADR-0049` "Status: superseded by I3+D1' execution" with back-pointer. |
| D1' | Append "Retirement" section to `ADR-0029`-style status on `apply_ac_no_rewrite_by_name` (the function gets deleted but its rationale lives on in the parent migration plan's archived form). |

At plan close, archive `TODO/20260601-ac-coverage-to-100-plan.md` to `docs/archive/plans/` with "Plan complete" block listing per-row PR + distillation target.

## Anti-patterns to avoid

- Do not ingest the pre-2022 J&K slice from Garuda; would ship wrong AP boundaries.
- Do not delete `apply_ac_no_rewrite_by_name` before I3 frontend rework lands; would break S01/AP rendering.
- Do not stamp speculative LGD codes in I2; cite LGD portal URL in commit message per stamp.
- Do not mint a new schema version for `lgd_ac_id` (C1 #539 schema 4.2 already covers it).
- Do not register a new ramSeraph mirror as the "producer"; producer is ECI, Garuda is `url_mirror`.

## See also

- `TODO/20260530-eci-to-lgd-acid-migration-plan.md` (parent; D1 deferred there, un-deferred here).
- `docs/architecture/decisions/0049-lgd-ac-id-internal-key.md` (canonical join contract).
- `docs/architecture/decisions/0047-schema-version-compatibility-contract.md` (reader-before-writer).
- `tools/migrate/build_ac_crosswalk.py` (C1 machinery; SoT precedence path already supports I2).
