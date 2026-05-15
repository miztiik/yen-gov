# State Health Sources And Ingest Boundaries

**Last Updated**: 2026-05-15
**Status**: SPEC - source recon and handoff plan only; no new ingest implemented in this change.

See also:
- [sources-rbi.md](sources-rbi.md)
- [data-sources.md](../../reference/data-sources.md)
- [data-coverage-report.md](../../reference/data-coverage-report.md)
- [cross-state-comparison.md](../../concepts/cross-state-comparison.md)
- [20260515-health-ingest-handover.md](../../../TODO/20260515-health-ingest-handover.md)

This note fixes the source hierarchy and ingest boundaries for state-level health indicators before another agent starts downloading and parsing more files. The key design choice is concept-first, not publisher-first: health financing, health outcomes, and health system capacity are separate contract families and should not be merged just because RBI and CBHI surface them on adjacent pages.

## Source hierarchy

### 1. Financing

RBI **State Finances: A Study of Budgets** is the canonical source for state-budget health prioritisation.

- Statement 27 is the cleanest first health-financing indicator because it answers "what share of the state budget went to health?"
- Statement 37 is more recent for absolute rupee amounts, but it is not pure health: it bundles Medical and Public Health, Family Welfare, and Water Supply and Sanitation.
- No Statement 37 rows should be merged into the existing RBI HBS Table 18 artifact until a written concept crosswalk proves they represent the same concept.

### 2. Outcomes

RBI **Handbook of Statistics on Indian States** is acceptable as the machine-readable translator surface for health outcomes, but the source-of-origin must remain explicit.

- Birth rate, death rate, infant mortality rate, and total fertility rate already ship through RBI HBS.
- Maternal Mortality Ratio and Life Expectancy are the next outcome candidates, but both are interval-style series rather than ordinary annual points.
- Outcome artifacts must name the underlying authority in notes and documentation: SRS / Office of the Registrar General where applicable.

### 3. Infrastructure and capacity

CBHI / MoHFW **National Health Profile** is the canonical source family for hospitals, beds, doctors, and specialists.

- RBI HBS Tables 16 and 17 are useful bridge surfaces and cross-checks because they expose the same concepts in friendlier XLSX form.
- The long-run infrastructure story should still be anchored in the CBHI archive, not in RBI alone.
- Public-facing capacity indicators should default to normalized metrics, not raw counts.

## Coverage matrix

### Already shipped health surfaces

| Surface | Role | What it contains | Coverage shape | Shipped artifacts |
| --- | --- | --- | --- | --- |
| RBI HBS Table 2 | Outcome | Crude Birth Rate | 35 entities, CY2004-CY2023, annual point series | `health/state_birth_rate_per_1000` |
| RBI HBS Table 3 | Outcome | Crude Death Rate | 35 entities, CY2004-CY2023, annual point series | `health/state_death_rate_per_1000` |
| RBI HBS Table 4 | Outcome | Infant Mortality Rate | 35 entities, CY2004-CY2023, annual point series | `health/state_infant_mortality_rate_per_1000` |
| RBI HBS Table 6 | Outcome | Total Fertility Rate | 22 entities, CY2003-CY2023, annual point series | `health/state_total_fertility_rate` |
| RBI HBS Table 18 | Financing input | State public expenditure on health | 34 entities, FY2012-13 to FY2019-20, annual point series in INR crore | `health/state_public_health_expenditure_inr_crore` |

### Candidate and deferred health surfaces

| Surface | Family | What it contains | Coverage shape | Current status | Why it matters |
| --- | --- | --- | --- | --- | --- |
| RBI State Finances Statement 27 | Financing | Expenditure on Medical and Public Health and Family Welfare as % of aggregate expenditure | 28 states + Delhi + Puducherry, FY2008-09 to FY2025-26, annual point series with Accounts / RE / BE tail rows | Recommended P0 | Honest budget-priority signal; avoids large-state size bias of raw INR crore |
| RBI State Finances Statement 37 | Financing | Expenditure on Medical and Public Health, Family Welfare and Water Supply and Sanitation in INR crore | 28 states + Delhi + Puducherry, FY2023-24 A, FY2024-25 RE, FY2025-26 BE | Crosswalk required before publication | Latest absolute rupee context, but concept is broader than pure health |
| RBI HBS Table 5 | Outcome | Maternal Mortality Ratio | 19 large states + `Others` + `ALL INDIA`, rolling multi-year windows from 1999-01 through 2021-23 | Deferred | High-value outcome, but windowed series needs an interval contract |
| RBI HBS Table 7 | Outcome | Life Expectancy at Birth, Male / Female / Total | Major states + `ALL INDIA`, overlapping multi-year windows, three parallel sexes | Deferred, but should move ahead of infrastructure work | Best next citizen-facing complement to IMR; total can land before sex splits |
| RBI HBS Table 16 | Capacity | PHC doctors and CHC specialists with Required / Sanctioned / In Position / Vacant / Shortfall sections | Multi-section sparse snapshot workbook; visible sections include 2005, 2015, 2020, 2021 | Deferred | Critical service-capacity story, but should publish normalized metrics rather than raw counts |
| RBI HBS Table 17 | Capacity | Government hospitals and beds, Rural / Urban / Total | Single reference-date stock table across 36 entities | Deferred | Bed capacity is useful, but public-facing default should be per population |
| CBHI / MoHFW National Health Profile archive | Capacity + source-of-origin | PDF archive with health finance, human resources, hospitals, beds, and other system tables | Confirmed editions: 2011, 2012, 2013, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2023 | Recon only | Long-run source-of-origin archive; needed for infrastructure history and for validating RBI-translated surfaces |

## Confirmed source links

### RBI State Finances

- Landing page: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State+Finances+%3A+A+Study+of+Budgets>
- Statement 27 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23736>
- Statement 27 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/27_ST23012026CC86B1004D0246F9A46EE80264885103.XLSX>
- Statement 37 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23746>
- Statement 37 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/37_ST230120264586107CCC1C471FA983A4AFFE7A7623.XLSX>

### RBI Handbook of Statistics on Indian States

- Landing page: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+States>
- Table 5 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23454>
- Table 5 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/5T_111220254548CA2016E4432288FBB97802B02561.XLSX>
- Table 7 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23456>
- Table 7 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/7T_11122025164B47839F9943F2BC176783B25CB079.XLSX>
- Table 16 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23465>
- Table 16 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/16T_11122025547AD10B7697436D9B9C4BF0C7891957.XLSX>
- Table 17 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23466>
- Table 17 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/17T_11122025EE6D7670D67644958960109D9F40FE68.XLSX>
- Table 18 page: <https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23467>
- Table 18 workbook: <https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/18T_11122025768C98BEB7A5493EA2E2EFFFEDDA7C46.XLSX>

### CBHI / MoHFW National Health Profile

- Archive page: <https://cbhidghs.mohfw.gov.in/publications/national-health-profile>
- NHP 2023 PDF: <https://cbhidghs.mohfw.gov.in/sites/default/files/NHP/NHP-2023-Last-Final.pdf>
- NHP 2021 PDF: <https://cbhidghs.mohfw.gov.in/sites/default/files/NHP/National-health-2021.pdf>
- NHP 2020 PDF: <https://cbhidghs.mohfw.gov.in/sites/default/files/NHP/National-health-2020.pdf>
- NHP 2019 PDF: <https://cbhidghs.mohfw.gov.in/sites/default/files/NHP/National-health-2019.pdf>
- NHP 2018 page: <https://cbhidghs.mohfw.gov.in/node/555>
- NHP 2017 page: <https://cbhidghs.mohfw.gov.in/node/556>
- NHP 2016 page: <https://cbhidghs.mohfw.gov.in/node/557>
- NHP 2015 page: <https://cbhidghs.mohfw.gov.in/node/559>
- NHP 2013 page: <https://cbhidghs.mohfw.gov.in/node/561>
- NHP 2012 page: <https://cbhidghs.mohfw.gov.in/node/562>
- NHP 2011 page: <https://cbhidghs.mohfw.gov.in/node/563>

## Recommended indicator order

| Priority | Proposed indicator | Canonical source | Why this order | Notes |
| --- | --- | --- | --- | --- |
| P0 | `health/state_health_expenditure_share_of_total_expenditure_pct` | RBI State Finances Statement 27 | Smallest safe new artifact, high citizen value, no schema change | Public story = budget priority, not system performance |
| P0.5 | Written crosswalk: Statement 37 vs existing Table 18 concept | RBI State Finances + RBI HBS | Prevents a dishonest merge of near-duplicate spend concepts | Structural decision, not parser work |
| P1 | `health/state_life_expectancy_at_birth_years` | RBI HBS Table 7 | Best next outcome after IMR; Hans review moved this ahead of infrastructure | Total first, male/female later |
| P2 | `health/state_maternal_mortality_ratio_per_100000_live_births` | RBI HBS Table 5 | High-value outcome, but still windowed and sparse | Requires the same interval contract decision as T07 |
| P3 | `health/state_government_hospital_beds_per_lakh_population` | RBI HBS Table 17 with declared denominator | Best first capacity metric if normalized on entry | Do not publish raw bed counts as the citizen default |
| P4 | `health/state_phc_doctor_availability_pct` and/or `health/state_chc_specialist_availability_pct` | RBI HBS Table 16 | Strong service-capacity metrics once section routing is proven | Availability / shortfall is better than raw counts |
| P5 | CBHI NHP long-run infrastructure and finance backfill | CBHI / MoHFW NHP archive | Source-of-origin extension path after easier RBI XLSX work is stable | PDF extraction stays out of the first wave |

## Contract rules for the next ingest wave

1. One artifact per concept, unit, and time shape.
2. Do not blend fiscal-year financing, calendar-year outcomes, and reference-date stock counts.
3. Accounts / RE / BE belongs in row-level vintage, not in fake year labels.
4. T05 and T07 are interval or overlapping-window series. Either add an explicit interval contract first or keep them deferred.
5. Statement 37 and Table 18 do not merge until equivalence is documented.
6. Absolute spend and raw capacity counts are valid source translations but not honest citizen defaults. The handoff must declare the public comparator or denominator for each family.
7. Every health artifact should explicitly set or justify `attribution_geography`, `comparability`, `implementing_authority`, and `funding_split`.
8. Outcome artifacts translated through RBI HBS should still call out the underlying source-of-origin in notes and docs.

## Known traps

- **Spend is input, not outcome.** More spending does not prove a better health system.
- **Absolute INR crore is size-biased.** Uttar Pradesh and Maharashtra dominate raw totals because they are large.
- **Statement 37 is broader than pure health.** It includes water supply and sanitation.
- **T05 and T07 are not point-year series.** Encoding them as ordinary annual rows would muddy the contract.
- **T16 and T17 are public-system-only.** They do not describe the private sector health system.
- **Calendar-year vs fiscal-year pairings need explicit caveats.** Pairing IMR or life expectancy with budget share without stating the grain difference invites overclaiming.

## Download starting points

- For RBI HBS workbooks, reuse the existing Handbook download workflow and browser-like headers rather than ad hoc raw requests.
- For RBI State Finances workbooks, reuse the existing RBI fetch path and per-edition pinned URLs rather than manual browser copy/paste in production code.
- For CBHI NHP, begin with an edition matrix and extraction spike only. Do not publish any CBHI-derived artifact until repeated table extraction is stable across multiple editions.