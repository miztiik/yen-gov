# ICED authority tracing (evidence-gated producer correction)

**Last Updated**: 2026-06-19

This is the per-endpoint evidence ledger behind the **D2 producer correction**
(ingest rip-and-replace plan Row 10). It records, for every source row
currently attributed to the producer `NITI Aayog India Climate & Energy
Dashboard`, whether the NITI Aayog India Climate & Energy Dashboard (ICED) is a
pure **passthrough** of an upstream issuing authority (so the producer becomes
that authority) or **originates** a derived / harmonised analytic (so the
producer stays ICED). The machine-readable form of these decisions is
[backend/yen_gov/canonical/iced_authority_map.py](../../backend/yen_gov/canonical/iced_authority_map.py);
the Tier-B guard that keeps the corpus honest is
`tier_b_source_producer_not_a_product` in
[backend/yen_gov/validate.py](../../backend/yen_gov/validate.py).

## Why ICED is not a `producer`

`producer` is the publisher **organisation**, verbatim from OWID
`origin.producer` (CLAUDE.md section 12, Holy Law #9). `India Climate & Energy
Dashboard` is a **dashboard product** operated by NITI Aayog - a machine-readable
access surface that re-serves data issued by other authorities (CEA, CPCB,
MoEFCC, MoSPI, RBI, ...). Naming the dashboard as the producer hides the real
issuing authority and presents a product name where an organisation belongs.
D2 corrects this **per endpoint on cited in-repo evidence**, never as a blanket
sweep: a blanket "everything is CEA" sweep would bake a provenance lie onto the
analytics ICED genuinely originates.

## Decision rule (conservative)

- **Reattribute to the upstream authority** only when the in-repo adapter
  evidence names a **single issuing authority** as the source of that specific
  endpoint's numbers, and ICED merely re-serves them. The dashboard moves into
  the source `title` (suffix ` [republished via NITI Aayog India Climate &
  Energy Dashboard]`) so the access surface is not lost.
- **Keep `NITI Aayog ICED`** when ICED publishes a **harmonised / synthesised**
  series across multiple sources, when the indicator is **derived** by ICED or
  by yen-gov, when one source row aggregates **multiple upstream authorities**,
  or when no single authority is named (evidence thin). Per the brief: where
  evidence is thin, keep ICED - do not bake a guess.

The kept value is the organisation-led label `NITI Aayog ICED` (the plan's D2
keep-string), never the bare dashboard product name. Both reattributed and kept
rows therefore re-mint their `source_id` (the deterministic hash of the new
`(producer, title, vintage)` triple); no `indicator_id` ever changes.

## Summary

34 ICED-attributed source rows: **24 reattributed** to an upstream issuing
authority, **10 kept** as `NITI Aayog ICED`.

| Authority (new producer) | Reattributed endpoints |
| --- | ---: |
| Central Electricity Authority | 7 |
| Ministry of Statistics and Programme Implementation | 7 |
| Ministry of Environment, Forest and Climate Change | 2 |
| Power Finance Corporation | 2 |
| Central Pollution Control Board | 1 |
| Reserve Bank of India | 1 |
| Ministry of Coal | 1 |
| Petroleum Planning and Analysis Cell | 1 |
| Ministry of Road Transport and Highways | 1 |
| Ministry of New and Renewable Energy | 1 |
| **NITI Aayog ICED (kept)** | **10** |

## Reattributed endpoints (passthrough -> issuing authority)

| source_id | Endpoint (title) | indicator_id(s) | ICED's named upstream | passthrough vs derived | Evidence (in-repo) | New producer |
| --- | --- | --- | --- | --- | --- | --- |
| src-1240f07df0ac | Capacity Metatable API | installed-capacity-geographical-mw | CEA station-level capacity | passthrough | `sources/iced_metatable/ingest.py` "ICED capacity-metatable rollup of CEA-published station-level capacity"; `sources/iced_power/ingest.py` "(CEA-sourced upstream)" | Central Electricity Authority |
| src-ddbfadd51428 | Generation Metatable API | electricity-generation-gwh | CEA gen-metatable | passthrough | `sources/iced_power/ingest.py` "/v1/gen-metatable-data (CEA-sourced upstream)" | Central Electricity Authority |
| src-7eb929cbf2d8 | Plant Load Factor by Fuel State API | plant-load-factor-pct-{8 fuels} | CEA PLF metatable | passthrough | `sources/iced_power/ingest.py` "/v1/plf-metatable-data (CEA-sourced upstream). PLF is the standard CEA metric" | Central Electricity Authority |
| src-fd152bd3c6c6 | Retired Thermal Capacity Plants | india-thermal-capacity-retired-mw | CEA retired-capacity | passthrough | `sources/iced_metatable/ingest.py` "ICED retired-capacity-plants endpoint (CEA-sourced)" | Central Electricity Authority |
| src-3d0b1c141f6a | Captive Power (industry-wise) State-wise API | captive-power-capacity-mw, captive-power-generation-gwh | CEA captive-power returns | passthrough | `canonical/adapters/iced_captive_power/registry.py` "the underlying returns are the Central Electricity Authority's (CEA)"; "Self-reported by industry to the CEA" | Central Electricity Authority |
| src-7c3cc99a3b68 | CO Emission Metatable API | state-power-sector-co2-emissions-mtco2-{coal,oil-gas} | CEA generation x CEA emission factors (CEA CO2 Baseline Database) | passthrough (all-CEA inputs) | `sources/iced_power/ingest.py` "unit-level CO2 emissions are derived ... from CEA generation x CEA technology-specific emission factors" | Central Electricity Authority |
| src-706a26f2871e | Air Quality FGD API | thermal-fgd-installed-share-pct | CEA thermal capacity / MoEF&CC FGD directive | passthrough | `sources/iced_air_quality/ingest.py` title "re-publishing CEA / MoEF&CC"; `parsers.py` "CEA (Central Electricity Authority) and tied to the MoEF&CC" | Central Electricity Authority |
| src-263dcba882ba | AQI Map Markers API | {no2,so2,pm10,pm25}-annual-mean-ug-m3 | CPCB NAMP | passthrough | `sources/iced_air_quality/markers_ingest.py` "re-publishing CPCB NAMP" (per pollutant); `endpoints.py` "ICED is a re-publisher of CPCB NAMP annual-mean" | Central Pollution Control Board |
| src-7532e395ae91 | GHG Emissions API (by subsector, energy) | india-ghg-emissions-ggco2e-by-subsector-* (26) | MoEFCC national GHG inventory | passthrough | `sources/iced_ghg/ingest.py` "IPCC 2006 guidelines (BUR-3 / BUR-4 submissions, MoEFCC)" | Ministry of Environment, Forest and Climate Change |
| src-857e962f15f5 | GHG Emissions API (economy-wide) | india-ghg-emissions-mtco2e-by-sector-* (4) | MoEFCC national GHG inventory | passthrough | `sources/iced_socio/ingest.py` "IPCC 2006 guidelines (BUR submissions, MoEFCC)" | Ministry of Environment, Forest and Climate Change |
| src-bb7935971e98 | Key Economic Indicators - GDP / GSDP | gdp-inr-crore-{constant,current} | MoSPI / NSO national accounts | passthrough | `sources/iced_macro/ingest.py` "MoSPI / National Statistical Office national GDP back-series" | Ministry of Statistics and Programme Implementation |
| src-5c93205c875f | Key Economic Indicators - GVA constant | gva-by-industry-constant-inr-crore-* (10) | MoSPI / NSO national accounts | passthrough | `sources/iced_macro/ingest.py` "MoSPI / NSO national accounts, constant prices base 2011-12" | Ministry of Statistics and Programme Implementation |
| src-933106681441 | Key Economic Indicators - Index of Industrial Production | iip-index-* (10) | MoSPI / NSO (IIP 2011-12 base) | passthrough | `sources/iced_macro/ingest.py` module "ICED macro adapter - national/state GDP, IIP"; IIP (2011-12=100) is the MoSPI/NSO flagship index | Ministry of Statistics and Programme Implementation |
| src-b222d76f33c1 | State-wise Deep Dive - Sectoral GVA | sectoral-gva-inr-crore-{constant,current} | MoSPI / state DES under MoSPI methodology | passthrough | `sources/iced_macro/ingest.py` "State Directorates of Economics & Statistics under MoSPI methodology"; "NSO finalises that year's accounts" | Ministry of Statistics and Programme Implementation |
| src-b6b6a168517e | State-wise Deep Dive - State GDP (constant 2011-12) | state-gdp-constant-2011-12-inr-lakh-crore | MoSPI / NSO national accounts | passthrough | `sources/iced_macro/ingest.py` "MoSPI's National ... Constant Price (NSO/MoSPI underlying)" | Ministry of Statistics and Programme Implementation |
| src-1a8a6f710f23 | Key Economic Indicators - per-capita PFCE | per-capita-consumption-inr | CSO (under MoSPI) National Accounts PFCE | passthrough | `sources/iced_socio/ingest.py` "National Accounts PFCE (CSO modelled to state level)"; "modelled by CSO from national totals down to state level" | Ministry of Statistics and Programme Implementation |
| src-3155ffeddf80 | State-wise Deep Dive - Population (lakhs) | state-population-lakhs | MoSPI inter-censal estimates | passthrough | `sources/iced_state_wise/ingest.py` "Inter-censal estimates from MoSPI; the next decadal Census will reset the baseline" | Ministry of Statistics and Programme Implementation |
| src-41cb48075b72 | Key Economic Indicators - Balance of Payments | india-external-balance-inr-crore-* (6) | RBI Balance of Payments statistics | passthrough | `sources/iced_macro/ingest.py` "RBI Balance of Payments statistics, republished by NITI Aayog" | Reserve Bank of India |
| src-c222a8e2cd61 | Coal Consumption (Domestic) State-wise API | coal-consumption-mt | Ministry of Coal | passthrough | `sources/iced_fuel/ingest.py` "Ministry of Coal upstream" | Ministry of Coal |
| src-cba8334fedc5 | Oil Product Consumption State-wise API | oil-product-consumption-kt | PPAC (Ministry of Petroleum & Natural Gas) | passthrough | `sources/iced_fuel/ingest.py` "consumptionStateProductTrend (PPAC / Ministry of Petroleum & Natural Gas upstream)" | Petroleum Planning and Analysis Cell |
| src-412af3a265c8 | ICE vs EV (VAHAN) State-wise API | ev-share-of-registrations-pct | MoRTH VAHAN | passthrough | `canonical/adapters/iced_ev_share/__init__.py` "ICED republishes MoRTH VAHAN"; `registry.py` "Ministry of Road Transport & Highways VAHAN portal" | Ministry of Road Transport and Highways |
| src-650b1c25d1f7 | Distribution Operational Performance API | distribution-efficiency-pct-{billing,collection,td-loss} | PFC report card on state power utilities | passthrough | `sources/iced_discom/ingest.py` "operationalPerformanceStates (PFC report-card upstream)" | Power Finance Corporation |
| src-1401f8087b0d | State Power Purchase Quantum and Cost API | power-purchase-share-pct-* (12) | PFC report card (state power utilities) | passthrough | `sources/iced_fuel/ingest.py` "(PFC / Ministry of Power upstream). Per-state per-source per-FY" | Power Finance Corporation |
| src-018bb42f9519 | Rooftop Solar Capacity (MW) State-wise API | rooftop-solar-capacity-mw | MNRE (installed rooftop solar) | passthrough | `sources/iced_state_wise/ingest.py` notes "Source: ... row 'Rooftop Solar Capacity'. Underlying figures published by MNRE" | Ministry of New and Renewable Energy |

## Kept as `NITI Aayog ICED` (originated / harmonised / derived / multi-authority / thin)

| source_id | Endpoint (title) | indicator_id(s) | Why kept | Evidence (in-repo) |
| --- | --- | --- | --- | --- |
| src-170d3536d908 | Primary Energy Supply National API | primary-energy-supply-mtoe | ICED publishes a harmonised national energy balance synthesised across IEA/CEA/MoSPI | `canonical/adapters/iced_national_energy/registry.py` "ICED is the publisher of the harmonised national balance ... IEA/CEA/MoSPI energy-account methodology; ICED is the harmonised access surface" |
| src-29ecbb6dce9d | Final Energy Consumption National API | final-energy-consumption-mtoe | same harmonised national energy balance | `canonical/adapters/iced_national_energy/registry.py` (as above) |
| src-518795193989 | Renewable Energy Potential - Solar API | solar-potential-mw | modelled NISE estimate ICED frames as its harmonised series; reattribution to NISE/MNRE deferred (thin) | `canonical/adapters/iced_renewable_potential/registry.py` "publisher of the harmonised series ... NISE for solar" |
| src-36e84f35548b | Renewable Energy Potential - Wind API | wind-potential-mw | modelled NIWE estimate framed as ICED harmonised series; deferred (thin) | `canonical/adapters/iced_renewable_potential/registry.py` "NIWE for wind" |
| src-c0a10bb04862 | Renewable Energy Potential - Bioenergy API | bio-energy-potential-mw | modelled MNRE / Biomass Atlas estimate framed as ICED harmonised series; deferred (thin) | `canonical/adapters/iced_renewable_potential/registry.py` "MNRE / the Biomass Atlas for bio-energy" |
| src-d9484e65a17e | Transmission Substation List API | substation-capacity-commissioned-mva | yen-gov-derived rollup (sum of MVA by voltage class); no single upstream authority named | `canonical/adapters/iced_transmission_substations/registry.py` non-null `derivation`; "publisher of the harmonised series" |
| src-85c67674901f | Coal Plant AQI Impact List API | coal-capacity-fgd-share-pct | yen-gov geocodes each plant + aggregates per state from ICED's coal-plant impact list ("geocode-derived major-processing statistic") | `canonical/adapters/iced_coal_fgd/registry.py` non-null `derivation`; concept_description "A geocode-derived (major-processing) statistic" |
| src-bb1d7bec8b34 | State-wise Deep Dive API (generic) | acs-arr-gap-inr-per-kwh, atc-losses-pct, electricity-sales-mu, installed-capacity-allocated-iced-mw, peak-electricity-demand-iced-mw, per-capita-electricity-consumption-kwh | one source row aggregates 6 indicators spanning multiple upstreams (CEA capacity/consumption + PFC AT&C/ACS-ARR + state utilities); no single authority | backs 6 distinct indicators from different upstream authorities (datapoint scan) |
| src-0ea63ed47704 | Distribution RPO Compliance API | rpo-compliance-pct-{solar,non-solar,total} | RPO compliance is set/tracked by SERCs / MNRE; no single issuing authority named in-repo (thin) | `sources/iced_discom/parsers.py` "Upstream rpoCompliance"; PFC report-card citation covers only the T&D/billing/collection endpoint, not RPO |
| src-e0b2a084d204 | Plant Pipeline Info National API | under-construction-capacity-gw | under-construction capacity spans thermal (CEA) + renewable (MNRE) projects; the endpoint-specific evidence names no single authority | `sources/iced_power/ingest.py` pipeline re-ingest names only "ICED plantPipelineInfo"; module "CEA-sourced" comment scopes to the four original indicators, not the pipeline |

## Adapter constant handoff (out of Row 10 scope)

The ICED `sources/iced_*` and `canonical/adapters/iced_*` modules still carry
`_CSV_SOURCE_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"` (and
per-spec `source_producer` strings). Row 10 is a **mechanical canonical-store
migration** (no adapter re-run, per the plan); it does not rewire those
constants, and the `test_iced_*_csv_repoint.py` tests still pin the pre-D2
`source_id`s. The migrated `source.csv` + datapoints are the shipped truth (CI
consumes committed CSV; the adapters are operator-staged and never run in CI).
When an adapter is next consolidated (plan Row 11) its producer/title constant
MUST be repointed to
[backend/yen_gov/canonical/iced_authority_map.py](../../backend/yen_gov/canonical/iced_authority_map.py)
so a re-run reproduces the corrected `source_id` rather than reverting it.

## See also

- [backend/yen_gov/canonical/iced_authority_map.py](../../backend/yen_gov/canonical/iced_authority_map.py) - the machine-readable decision map + FK-lockstep migration.
- [backend/yen_gov/validate.py](../../backend/yen_gov/validate.py) - `tier_b_source_producer_not_a_product`.
- [CLAUDE.md](../../CLAUDE.md) - Holy Law #9 + section 12 (data provenance, the 5-field source ledger).
- [TODO/20260618-backend-ingest-pipeline-rip-replace-plan.md](../../TODO/20260618-backend-ingest-pipeline-rip-replace-plan.md) - D2 + Row 10.
- [docs/concepts/data-provenance.md](../concepts/data-provenance.md) - the citation-ledger doctrine.
