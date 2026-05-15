# Handoff - state health sources and ingest plan

**For**: the next agent picking up state-level health ingest.
**From**: agent that mapped the RBI and CBHI source landscape on 2026-05-15.
**Read first**: [CLAUDE.md](../CLAUDE.md), [docs/architecture/backend/sources-health.md](../docs/architecture/backend/sources-health.md), [docs/reference/data-coverage-report.md](../docs/reference/data-coverage-report.md).

## 1. What already exists on disk

Shipped health artifacts under `datasets/indicators/in/health/`:

- `state_birth_rate_per_1000.json`
- `state_death_rate_per_1000.json`
- `state_infant_mortality_rate_per_1000.json`
- `state_public_health_expenditure_inr_crore.json`
- `state_total_fertility_rate.json`

These came from RBI HBS Tables 2, 3, 4, 6, and 18. The existing public-expenditure artifact is FY2012-13 to FY2019-20 and should be treated as the older RBI HBS lineage until a Statement 37 crosswalk says otherwise.

## 2. Reviewed plan summary

The plan was reviewed by `Hans (Governance)`, `Fowler (Engineering)`, and `Gregor Hohpe (Architect)`.

Combined verdict: **APPROVE WITH CHANGES**.

The incorporated changes are:

1. Move life expectancy ahead of infrastructure work.
2. Keep outcomes source-of-origin explicit: SRS for IMR / MMR / life expectancy where applicable.
3. Publish health budget share before absolute health spend.
4. Do not publish raw T16 / T17 counts as the citizen default; normalize on entry or keep deferred.
5. Put the Statement 37 crosswalk and the interval-series decision into canonical docs, not just code comments.
6. Add honesty metadata and denominator decisions to the handoff matrix for every proposed artifact.

## 3. The next-agent sequence

Follow this order unless the user redirects:

1. Structural seam if needed: reuse the `rbi_xlsx` wide-table parser shape, but do not jam health logic into the current fiscal-only registry without extracting the generic seam first.
2. Behavioral P0: add `health/state_health_expenditure_share_of_total_expenditure_pct` from RBI State Finances Statement 27.
3. Structural: write the Statement 37 vs Table 18 concept crosswalk in docs before touching Statement 37 rows.
4. Structural: decide the interval-row contract for T07 and T05. If no contract change is approved, keep both deferred.
5. Behavioral P1: ingest `health/state_life_expectancy_at_birth_years` from Table 7, total series first.
6. Behavioral P2: ingest `health/state_maternal_mortality_ratio_per_100000_live_births` from Table 5.
7. Behavioral P3: ingest a normalized Table 17 capacity metric, ideally `health/state_government_hospital_beds_per_lakh_population`.
8. Behavioral P4: ingest normalized or percentage-based Table 16 availability metrics, not raw staffing counts as the public default.
9. Structural research only: create a CBHI edition matrix and stable extraction recipe. Do not publish CBHI-derived artifacts in the first wave.

## 4. Source matrix you should use

Use [docs/architecture/backend/sources-health.md](../docs/architecture/backend/sources-health.md) as the canonical matrix.

Minimum source set for the next wave:

- RBI State Finances Statement 27 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23736>
- RBI State Finances Statement 27 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/27_ST23012026CC86B1004D0246F9A46EE80264885103.XLSX>
- RBI State Finances Statement 37 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23746>
- RBI State Finances Statement 37 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/37_ST230120264586107CCC1C471FA983A4AFFE7A7623.XLSX>
- RBI HBS Table 5 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23454>
- RBI HBS Table 5 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/5T_111220254548CA2016E4432288FBB97802B02561.XLSX>
- RBI HBS Table 7 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23456>
- RBI HBS Table 7 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/7T_11122025164B47839F9943F2BC176783B25CB079.XLSX>
- RBI HBS Table 16 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23465>
- RBI HBS Table 16 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/16T_11122025547AD10B7697436D9B9C4BF0C7891957.XLSX>
- RBI HBS Table 17 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23466>
- RBI HBS Table 17 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/17T_11122025EE6D7670D67644958960109D9F40FE68.XLSX>
- RBI HBS Table 18 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23467>
- RBI HBS Table 18 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/18T_11122025768C98BEB7A5493EA2E2EFFFEDDA7C46.XLSX>
- CBHI National Health Profile archive: <https://cbhidghs.mohfw.gov.in/publications/national-health-profile>

## 5. Non-negotiables

1. Do not overclaim from spend alone. Budget share is a priority signal, not a performance signal.
2. Do not publish Statement 37 until the Table 18 crosswalk is written down.
3. Do not fake interval series as point-year series.
4. Do not lead with raw hospitals, beds, or doctor counts.
5. Do not collapse financing, outcomes, and capacity into one health mega-artifact.
6. For every artifact, explicitly decide the citizen-facing denominator or comparator.

## 6. Tests the next agent must plan for

At minimum:

- parser-level unit tests for headers, grouped columns, and revision labels
- one integration test per new source surface against a real fixture workbook
- `backend/tests/test_validate.py`
- `backend/tests/test_datasets_integrity.py`
- if the interval contract changes, schema-sanity plus validator regression tests before any T05 / T07 behavioral ingest

## 7. Copy-paste prompt for the next agent

```text
You are picking up yen-gov state health ingest. Read CLAUDE.md, docs/architecture/backend/sources-health.md, and TODO/20260515-health-ingest-handover.md first.

Goal:
- Start the next safe ingest wave for health.

Required order:
1. Reuse the existing RBI wide-table parser seam safely; do not build a mega-adapter.
2. Implement health/state_health_expenditure_share_of_total_expenditure_pct from RBI State Finances Statement 27.
3. Document a concept crosswalk between RBI State Finances Statement 37 and the existing health/state_public_health_expenditure_inr_crore from RBI HBS Table 18 before touching Statement 37 rows.
4. Decide whether T07 and T05 need an interval-row contract change. If yes, do the structural contract work first; if not approved, keep them deferred.
5. Ingest life expectancy total before MMR and before infrastructure tables.
6. Do not publish raw T16 or T17 counts as the citizen default. Normalize on entry or defer.
7. Treat CBHI NHP as source-of-origin and long-run backfill research, not first-wave parser work.

Required honesty rules:
- one artifact per concept and time shape
- explicit row vintage for Accounts / RE / BE
- no merge of Statement 37 and Table 18 without written equivalence proof
- no spend-only story without outcome pairing notes
- explicit denominator decision for every capacity artifact

Deliverables:
- code and tests for the first approved behavioral step
- docs update for any structural decision
- no unrelated refactors
```