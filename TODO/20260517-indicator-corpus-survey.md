# Indicator corpus survey

**Last Updated**: 2026-05-17

Ground-truth enumeration of 110+ indicators in yen-gov datasets for canonical long-format Parquet contract stress-test. Six agents will debate contract fitness against this factual baseline.

---

## A. Per-Indicator Registry (110 indicators)

| Topic | ID | Name | Unit | Value Kind | Cadence | Entity | Years | Facets | Type | Srcs |
|-------|-----|------|------|------------|---------|--------|-------|--------|------|------|
| demograp | state_population_b | Census population by state,  | persons | count | decennial | state | 1961-2011 | facet | numeri | 1 |
| demograp | state_population_b | State population by sex, dec | people | count | decennial | state | 1961-2011 | facet | numeri | 1 |
| demograp | state_population_l | State population (Lakhs) | Lakhs | count | unspecified | state | 2015-04-2025 | — | numeri | 1 |
| economy | india_external_bal | India external-sector balanc | INR crore | raw | unspecified | countr | 2000-04-2023 | facet | numeri | 1 |
| economy | india_gdp_inr_cror | India GDP (₹ crore, current  | INR crore | raw | unspecified | countr | 1950-04-2024 | facet | numeri | 1 |
| economy | india_gva_by_indus | India GVA by industry (const | INR crore | raw | unspecified | countr | 2011-04-2024 | facet | numeri | 1 |
| economy | india_iip_index_20 | Index of Industrial Producti | index (201 | index | unspecified | countr | 2012-04-2024 | facet | numeri | 1 |
| economy | national_gdp_curre | National GDP at current pric | INR (lakh  | curren | unspecified | countr | 2011-04-2023 | — | numeri | 1 |
| economy | national_gva_by_in | National Gross Value Added b | INR (crore | curren | unspecified | countr | 2011-04-2025 | facet | numeri | 1 |
| economy | national_gva_by_in | National Gross Value Added b | INR (crore | curren | unspecified | countr | 2011-04-2025 | facet | numeri | 1 |
| economy | national_macro_agg | National macro aggregates at | INR (crore | curren | unspecified | countr | 2011-04-2025 | facet | numeri | 1 |
| economy | state_gdp_constant | State GDP (constant prices,  | INR (lakh  | curren | unspecified | state | 2015-04-2024 | — | numeri | 1 |
| economy | state_gdp_current_ | State GDP (current prices) | INR (lakh  | curren | unspecified | state | 2011-04-2024 | — | numeri | 1 |
| economy | state_gdp_inr_cror | State GDP (₹ crore, current  | INR crore | raw | unspecified | state | 2011-04-2024 | facet | numeri | 1 |
| economy | state_nsdp_constan | Net State Domestic Product ( | INR (crore | curren | unspecified | state | 1994-04-2024 | — | numeri | 2 |
| economy | state_nsdp_current | Net State Domestic Product ( | INR (crore | curren | unspecified | state | 1994-04-2024 | — | numeri | 2 |
| economy | state_per_capita_c | State per-capita private con | INR | curren | unspecified | state | 2009-04-2023 | — | numeri | 1 |
| economy | state_per_capita_n | State per-capita NSDP, infla | INR | curren | unspecified | state | 2004-04-2023 | — | numeri | 1 |
| economy | state_per_capita_n | State per-capita NSDP (const | INR | curren | unspecified | state | 2000-04-2024 | — | numeri | 2 |
| economy | state_per_capita_n | State per-capita Net State D | INR | curren | unspecified | state | 2004-04-2023 | — | numeri | 1 |
| economy | state_per_capita_n | State per-capita NSDP (curre | INR | curren | unspecified | state | 2000-04-2024 | — | numeri | 2 |
| economy | state_sectoral_gva | State Sectoral GVA (constant | INR (lakh  | curren | unspecified | state | 2015-04-2024 | — | numeri | 1 |
| economy | state_sectoral_gva | State Sectoral GVA (current  | INR (lakh  | curren | unspecified | state | 2015-04-2024 | — | numeri | 1 |
| energy | india_capacity_pip | India under-construction ele | GW | count | unspecified | countr | 2011-2031 | facet | numeri | 1 |
| energy | india_thermal_capa | India thermal generating cap | MW | count | unspecified | countr | 2005-04-2025 | facet | numeri | 1 |
| energy | installed_capacity | Installed capacity by source | MW | raw | unspecified | state | 2026-03-2026 | facet | numeri | 1 |
| energy | installed_capacity | Installed coal-fired capacit | MW | raw | unspecified | state | 2026-03-2026 | — | numeri | 1 |
| energy | installed_capacity | Installed gas-based capacity | MW | raw | unspecified | state | 2026-03-2026 | — | numeri | 1 |
| energy | installed_capacity | Installed hydro capacity | MW | raw | unspecified | state | 2026-03-2026 | — | numeri | 1 |
| energy | installed_capacity | Installed nuclear capacity | MW | raw | unspecified | state | 2026-03-2026 | — | numeri | 1 |
| energy | installed_capacity | Installed renewable capacity | MW | raw | unspecified | state | 2026-03-2026 | — | numeri | 1 |
| energy | installed_capacity | Installed thermal capacity ( | MW | raw | unspecified | state | 2026-03-2026 | — | numeri | 1 |
| energy | installed_capacity | Installed power-generation c | MW | raw | unspecified | state | 2026-03-2026 | — | numeri | 1 |
| energy | installed_mw_by_st | Installed power-generation c | MW | raw | unspecified | state | 2019-2019 | facet | numeri | 3 |
| energy | national_final_ene | National final energy consum | mtoe | count | unspecified | countr | 2005-04-2024 | facet | numeri | 1 |
| energy | national_primary_e | National primary energy supp | mtoe | count | unspecified | countr | 2005-04-2024 | facet | numeri | 1 |
| energy | national_renewable | Renewable energy: installed  | MW | count | unspecified | countr | 2026-05-14-2 | facet | numeri | 1 |
| energy | state_acs_arr_gap_ | ACS-ARR gap on electricity s | INR/kWh | curren | unspecified | state | 2015-04-2024 | — | numeri | 1 |
| energy | state_atc_losses_p | Aggregate Technical & Commer | % | share | unspecified | state | 2015-04-2024 | — | numeri | 1 |
| energy | state_coal_consump | State coal consumption (Mt,  | Mt | raw | unspecified | state | 2005-04-2024 | — | numeri | 1 |
| energy | state_distribution | Distribution billing efficie | percent | share | unspecified | state | 2009-04-2024 | — | numeri | 1 |
| energy | state_distribution | Distribution collection effi | percent | share | unspecified | state | 2009-04-2024 | — | numeri | 1 |
| energy | state_distribution | Transmission & Distribution  | percent | share | unspecified | state | 2009-04-2024 | — | numeri | 1 |
| energy | state_electricity_ | State electricity generation | GWh | raw | unspecified | state | 2015-04-2025 | facet | numeri | 1 |
| energy | state_electricity_ | Annual electricity generatio | MU | raw | unspecified | state | 2015-04-2025 | — | numeri | 1 |
| energy | state_electricity_ | Annual peak electricity dema | MW | raw | unspecified | state | 2017-04-2025 | — | numeri | 1 |
| energy | state_electricity_ | Annual electricity sales (by | MU | raw | unspecified | state | 2015-04-2024 | — | numeri | 1 |
| energy | state_installed_ca | State installed electricity  | MW | count | unspecified | state | 2015-04-2025 | facet | numeri | 1 |
| energy | state_installed_ca | Installed electricity capaci | MW | raw | unspecified | state | 2015-04-2025 | — | numeri | 1 |
| energy | state_installed_ca | State-wise installed capacit | MW | raw | unspecified | state | 2004-04-2024 | — | numeri | 2 |
| energy | state_installed_ca | Installed electricity capaci | MW | raw | unspecified | state | 2015-04-2025 | — | numeri | 1 |
| energy | state_oil_product_ | State oil-product consumptio | kt | raw | unspecified | state | 2010-04-2024 | facet | numeri | 1 |
| energy | state_peak_demand_ | State-wise peak power demand | MW | raw | unspecified | state | 2013-04-2024 | — | numeri | 2 |
| energy | state_peak_electri | State peak electricity deman | MW | count | unspecified | state | 2025-04-2025 | — | numeri | 1 |
| energy | state_peak_met_mw | State-wise peak power suppli | MW | raw | unspecified | state | 2013-04-2024 | — | numeri | 2 |
| energy | state_per_capita_a | State-wise per-capita availa | kWh per pe | raw | unspecified | state | 2004-04-2024 | — | numeri | 2 |
| energy | state_per_capita_e | State per-capita electricity | kWh per pe | rate | unspecified | state | 2009-04-2023 | — | numeri | 1 |
| energy | state_plant_load_f | State Plant Load Factor (PLF | percent | share | unspecified | state | 2015-04-2025 | facet | numeri | 1 |
| energy | state_power_availa | State-wise availability of p | MU (millio | raw | unspecified | state | 2004-04-2024 | — | numeri | 2 |
| energy | state_power_purcha | State power-purchase mix by  | percent | share | unspecified | state | 2015-04-2024 | facet | numeri | 1 |
| energy | state_power_requir | State-wise power requirement | MU (millio | raw | unspecified | state | 2004-04-2024 | — | numeri | 2 |
| energy | state_renewable_gr | State-wise installed grid-in | MW | raw | unspecified | state | 2007-2024 | — | numeri | 2 |
| energy | state_rooftop_sola | Rooftop solar installed capa | MW | raw | unspecified | state | 2017-04-2025 | — | numeri | 1 |
| energy | state_rpo_complian | Renewable Purchase Obligatio | percent | share | unspecified | state | 2018-04-2020 | facet | numeri | 1 |
| environm | india_ghg_emission | India's greenhouse-gas emiss | Gg CO2e | raw | ad_hoc | countr | 1994-2020 | facet | numeri | 1 |
| environm | india_ghg_emission | India's greenhouse-gas emiss | Gg CO2e | raw | ad_hoc | countr | 1994-2020 | facet | numeri | 1 |
| environm | state_no2_annual_m | NO₂ — annual mean (state) | µg/m³ | raw | unspecified | state | 2010-2023 | — | numeri | 2 |
| environm | state_pm10_annual_ | PM10 — annual mean (state) | µg/m³ | raw | unspecified | state | 2010-2023 | — | numeri | 2 |
| environm | state_pm25_annual_ | PM2.5 — annual mean (state) | µg/m³ | raw | unspecified | state | 2014-2023 | — | numeri | 2 |
| environm | state_power_sector | State CO₂ emissions from pow | Mt CO2 | raw | unspecified | state | 2008-04-2025 | facet | numeri | 1 |
| environm | state_so2_annual_m | SO₂ — annual mean (state) | µg/m³ | raw | unspecified | state | 2010-2023 | — | numeri | 2 |
| environm | state_thermal_fgd_ | Thermal-plant FGD compliance | % | share | unspecified | state | 2026-05-15-2 | — | numeri | 2 |
| fiscal | centre_transfers_g | Centre transfers to states ( | INR (crore | curren | unspecified | state | 2016-04-2022 | — | numeri | 3 |
| fiscal | centre_transfers_t | Grants from Centre to states | INR (crore | curren | unspecified | countr | 2007-04-2025 | — | numeri | 1 |
| fiscal | centre_transfers_t | Gross transfers from Centre  | INR (crore | curren | unspecified | countr | 2007-04-2025 | — | numeri | 1 |
| fiscal | centre_transfers_t | Net Centre-to-States transfe | INR (crore | curren | unspecified | countr | 2007-04-2025 | — | numeri | 1 |
| fiscal | centre_transfers_t | Devolution of central taxes  | INR (crore | curren | unspecified | countr | 2007-04-2025 | — | numeri | 1 |
| fiscal | net_transfers_from | Net transfers from the Centr | INR (crore | curren | unspecified | state | 2023-04-2025 | facet | numeri | 2 |
| fiscal | outstanding_debt_p | Outstanding liabilities (% o | % | share | unspecified | state | 2008-03-2026 | facet | numeri | 2 |
| fiscal | state_external_deb | States' total external debt  | INR (crore | curren | unspecified | state | 2026-05-14-2 | — | numeri | 1 |
| fiscal | state_grants_in_ai | Grants-in-Aid from the Centr | INR (crore | curren | unspecified | state | 2016-04-2022 | — | numeri | 1 |
| fiscal | state_non_tax_reve | States' non-tax revenue | INR (crore | curren | unspecified | state | 2016-04-2022 | — | numeri | 1 |
| fiscal | state_own_tax_reve | States' own tax revenue | INR (crore | curren | unspecified | state | 2016-04-2022 | — | numeri | 1 |
| fiscal | state_pension_expe | State pension expenditure (r | INR (crore | curren | unspecified | state | 2004-04-2024 | — | numeri | 2 |
| fiscal | state_revenue_expe | States' revenue expenditure | INR (crore | curren | unspecified | state | 2016-04-2022 | — | numeri | 1 |
| fiscal | state_share_centra | States' share in central tax | INR (crore | curren | unspecified | state | 2016-04-2022 | — | numeri | 1 |
| fiscal | states_combined_gr | Gross fiscal deficit (all st | INR (crore | curren | unspecified | countr | 2007-04-2025 | — | numeri | 1 |
| fiscal | states_combined_pr | Primary deficit (all states, | INR (crore | curren | unspecified | countr | 2007-04-2025 | — | numeri | 1 |
| fiscal | states_combined_pr | Primary revenue deficit (all | INR (crore | curren | unspecified | countr | 2007-04-2025 | — | numeri | 1 |
| fiscal | states_combined_re | Revenue deficit (all states, | INR (crore | curren | unspecified | countr | 2007-04-2025 | — | numeri | 1 |
| fiscal | union_gross_fiscal | Gross fiscal deficit (Union  | INR (crore | curren | unspecified | countr | 1986-04-2025 | — | numeri | 1 |
| fiscal | union_primary_defi | Primary deficit (Union Gover | INR (crore | curren | unspecified | countr | 1986-04-2025 | — | numeri | 1 |
| fiscal | union_primary_reve | Primary revenue deficit (Uni | INR (crore | curren | unspecified | countr | 1986-04-2025 | — | numeri | 1 |
| fiscal | union_revenue_defi | Revenue deficit (Union Gover | INR (crore | curren | unspecified | countr | 1986-04-2025 | — | numeri | 1 |
| health | state_birth_rate_p | Crude Birth Rate (per 1,000  | per 1,000  | rate | unspecified | state | 2004-2023 | — | numeri | 2 |
| health | state_death_rate_p | Crude Death Rate (per 1,000  | per 1,000  | rate | unspecified | state | 2004-2023 | — | numeri | 2 |
| health | state_health_expen | Public health spend (% of st | % of state | share | unspecified | state | 2008-04-2025 | facet | numeri | 2 |
| health | state_infant_morta | Infant Mortality Rate (per 1 | per 1,000  | rate | unspecified | state | 2004-2023 | — | numeri | 2 |
| health | state_public_healt | State public expenditure on  | INR (crore | curren | unspecified | state | 2012-04-2019 | — | numeri | 2 |
| health | state_total_fertil | Total Fertility Rate (childr | births per | rate | unspecified | state | 2003-2023 | — | numeri | 2 |
| human_de | state_hdi | Human Development Index (inc | index (0–1 | index | unspecified | state | 2011-04-2017 | — | numeri | 1 |
| prices | national_cpi_combi | Consumer Price Index — Combi | index (Bas | index | unspecified | countr | 2011-04-2024 | — | numeri | 2 |
| prices | national_cpi_iw_in | Consumer Price Index — Indus | index (reb | index | unspecified | countr | 1993-04-2024 | — | numeri | 2 |
| prices | national_wpi_all_c | Wholesale Price Index — All  | index (reb | index | unspecified | countr | 1974-04-2024 | — | numeri | 2 |
| prices | state_cpi_food_inf | State-wise CPI inflation (Fo | % YoY | rate | unspecified | state | 2014-04-2024 | — | numeri | 2 |
| prices | state_cpi_fuel_inf | State-wise CPI inflation (Fu | % YoY | rate | unspecified | state | 2014-04-2024 | — | numeri | 2 |
| prices | state_cpi_general_ | State-wise CPI inflation (Ge | % YoY | rate | unspecified | state | 2014-04-2024 | — | numeri | 2 |
| prices | state_cpi_housing_ | State-wise CPI inflation (Ho | % YoY | rate | unspecified | state | 2014-04-2024 | — | numeri | 2 |
| transpor | state_ev_registrat | EV registrations by state an | count of r | count | unspecified | state | 2000-04-2025 | facet | numeri | 1 |
| transpor | state_ev_share_tot | EV share of total vehicle re | % | share | unspecified | state | 2000-04-2025 | facet | numeri | 1 |

---

## B. Cadence Distribution (3 types across 110 indicators)

- ad_hoc: 2
- decennial: 2
- unspecified: 106

## C. Facet/Dimension Patterns (all row facets found)

- **facet**: 31 indicators across demography, economy, energy, environment, fiscal, health, transport

## D. Value Kind Distribution

- count: 11
- currency: 38
- index: 5
- rate: 9
- raw: 36
- share: 11

## E. Value Type Distribution

- Numeric only: 110
- Text: 0
- Mixed: 0

## F. Entity Granularity

- country: 30
- state: 80

## G. Top 10 Contract Stressors

(Ranked by composite stress: facets, mixed values, breaks, revisions, non-standard cadence)

1. **state_population_by_residence_count** (2.5): 1facets
2. **state_population_by_sex_count** (2.5): 1facets
3. **india_external_balance_inr_crore** (2.5): 1facets
4. **india_gdp_inr_crore** (2.5): 1facets
5. **india_gva_by_industry_constant_inr_crore** (2.5): 1facets
6. **india_iip_index_2011_12** (2.5): 1facets
7. **national_gva_by_industry_constant_2011_12_inr_crore** (2.5): 1facets
8. **national_gva_by_industry_quarterly_constant_2011_12_inr_crore** (2.5): 1facets
9. **national_macro_aggregates_constant_2011_12_inr_crore** (2.5): 1facets
10. **state_gdp_inr_crore** (2.5): 1facets

## H. Elections Artifact Shape

**Scope**: 7,279 JSON files across multiple state-level AC elections (2016-2026)

**Layout**: Hierarchical (election_id / state_code / AC_number / result.summary.json, parties.json, results/*.json)

**Key structure**:
- `party_totals[]`: party_short, seats_contested, seats_won, votes, vote_share_pct
- `totals`: electors, votes_polled, turnout_pct
- Entity grain: state-level aggregates (not AC-granular)
- Period label: election_id string (e.g. AcGenApr2016)
- All independent/NOTA collapsed into IND
- Source: 100% eci.gov.in
- Schema: 3.1

---

**Total**: 110 indicators | Factual enumeration only—no opinions on contract fitness. Agents will form conclusions next round against this baseline.
