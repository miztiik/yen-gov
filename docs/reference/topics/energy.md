# Energy

> Topic spine for the [`energy/`](../indicators/energy/) indicator family.
> Per-indicator pages link UP to this page for shared methodology that
> would otherwise repeat across siblings.

**Last Updated**: 2026-05-15
**Maintainer**: yen-gov contributors
**Plan**: [TODO/PER-INDICATOR-DOCS-PLAN.md](../../../TODO/PER-INDICATOR-DOCS-PLAN.md)

## What this topic covers

The `energy` topic is the largest in yen-gov, with ~41 indicators spanning **electricity supply** (installed capacity, generation, plant load factor), **electricity demand** (peak, sales, per-capita), **electricity distribution health** (AT&C losses, ACS-ARR gap, billing and collection efficiency, T&D losses), **non-electricity energy** (coal consumption, oil-product consumption, primary-energy supply, final-energy consumption by sector), and **renewables / climate-aligned generation** (renewable capacity, RPO compliance, rooftop solar, capacity pipeline, thermal retirements). Two upstream sources do most of the work — the IEA-NITI Aayog *India Climate & Energy Dashboard (ICED)* for long-history series, and the *Central Electricity Authority (CEA)* for the most recent monthly-snapshot capacity data.

What is **adjacent but NOT here**:

- **Power-sector CO₂ emissions** live in [`environment/`](../indicators/environment/) — the energy topic ships generation by fuel; the environment topic translates that into emissions using fuel-specific emission factors.
- **GHG inventory by sub-sector** (cement, steel, agriculture, waste) lives in [`environment/`](../indicators/environment/), not here. The energy topic ends at primary-energy supply / final-energy consumption; emissions accounting begins on the other side.
- **Petroleum subsidy and LPG consumer-price subsidy** are fiscal instruments — see [`fiscal/`](./fiscal.md) for the budget side, and [`prices/state_cpi_fuel_inflation_pct`](../indicators/prices/state_cpi_fuel_inflation_pct.md) for the consumer-price pass-through side.
- **Discom debt stocks** (UDAY bonds, RBI restructured advances exposure) — sit at the intersection of energy and fiscal but are not yet a dedicated artifact in this corpus. See `state_acs_arr_gap_inr_per_kwh` and `state_atc_losses_pct` as the closest proxies.
- **Electricity tariff orders** (per-category SERC tariffs) are regulatory artifacts; not a price index, not a stock, and not yet ingested.
- **Climate adaptation / vulnerability** sits in [`environment/`](../indicators/environment/).

## Upstream sources

| Source | What they publish | Cadence | License |
| --- | --- | --- | --- |
| IEA–NITI Aayog India Climate & Energy Dashboard (ICED) ([iced.niti.gov.in](https://iced.niti.gov.in/)) | Long-history time series for installed capacity (FY05+), generation (FY16+), peak demand, sales, per-capita availability, distribution-health metrics (FY09+), coal & oil consumption, primary energy supply, final energy consumption by sector | Monthly portal refresh; annual data with ~6-month lag | NITI Aayog publication |
| Central Electricity Authority (CEA), Power Sector at a Glance ([cea.nic.in](https://cea.nic.in/)) | Latest-month installed capacity by fuel and state (the IC sheet); plant-wise generation; PLF; capacity pipeline; thermal retirements | Monthly | Government publication |
| CEA Executive Summary (monthly) | Power-system snapshot: peak demand met, peak demand shortage, energy met, energy shortage by region and state | Monthly | Government publication |
| Ministry of New & Renewable Energy (MNRE) ([mnre.gov.in](https://mnre.gov.in/)) | Renewable installed capacity, target progress, PLI scheme allocations | Monthly / annual | Government publication |
| Power Finance Corporation (PFC), *Report on Performance of Power Utilities* | Discom-level financial metrics: ACS-ARR gap, AT&C losses, billing & collection efficiency | Annual | PFC publication |

The yen-gov pipeline pulls long-history series from ICED for stability and re-anchors latest-month snapshots to CEA's IC and Executive Summary publications. PFC's annual discom-performance report is the upstream for the discom-finance artifacts (AT&C, ACS-ARR gap, billing/collection efficiency, T&D loss).

## Series anchors (what to read for which question)

| Question | Canonical answer | Why |
| --- | --- | --- |
| "How big is this state's power system?" | [`energy/state_installed_capacity_total_mw`](../indicators/energy/state_installed_capacity_total_mw.md) | Total nameplate generation capacity, end-of-fiscal-year, FY05 onwards. The cleanest single size summary. |
| "What is the latest-month installed capacity mix?" | [`energy/installed_capacity_by_source_mw`](../indicators/energy/installed_capacity_by_source_mw.md) | CEA monthly snapshot — coal / gas / nuclear / hydro / renewable / other-thermal split. Use this for any *current* fuel-mix chart; use `state_installed_capacity_by_source_mw` for the longer-history fuel-mix split. |
| "What did this state actually generate (electrons), not just have capacity for?" | [`energy/state_electricity_generation_by_source_gwh`](../indicators/energy/state_electricity_generation_by_source_gwh.md) (fuel-broken) or [`energy/state_electricity_generation_mu`](../indicators/energy/state_electricity_generation_mu.md) (total) | Capacity is not generation — coal still dominates electrons delivered (PLF ~65%) even where solar+wind dominate MW added. |
| "How much electricity did consumers actually buy?" | [`energy/state_electricity_sales_mu`](../indicators/energy/state_electricity_sales_mu.md) | Sales = billed energy, the demand-side counterpart to generation. The gap between generation and sales is loss + transmission to other states. |
| "How much electricity does the average resident consume?" | [`energy/state_per_capita_electricity_consumption_kwh`](../indicators/energy/state_per_capita_electricity_consumption_kwh.md) | Cleanest single development proxy. Distorted by industrial-heavy states (Gujarat, Chhattisgarh, Odisha) where industry takes most of the electrons. Pair with `state_per_capita_availability_kwh`. |
| "How much electricity did the state need vs how much was delivered?" | [`energy/state_power_requirement_mu`](../indicators/energy/state_power_requirement_mu.md) (need) and [`energy/state_power_availability_mu`](../indicators/energy/state_power_availability_mu.md) (delivered); the gap is energy shortage | The classic "shortage / surplus" lens. India shifted from a chronic-shortage system (FY10) to a near-zero-shortage system (FY24); state-level pockets remain. |
| "What was peak load this year?" | [`energy/state_electricity_peak_demand_mw`](../indicators/energy/state_electricity_peak_demand_mw.md) (most recent FY snapshot) or [`energy/state_peak_demand_mw`](../indicators/energy/state_peak_demand_mw.md) (long history) | Distinguish demand (the need) from peak met ([`energy/state_peak_met_mw`](../indicators/energy/state_peak_met_mw.md)) — the gap is peak-load shortage. |
| "How healthy are this state's discoms?" | [`energy/state_atc_losses_pct`](../indicators/energy/state_atc_losses_pct.md) and [`energy/state_acs_arr_gap_inr_per_kwh`](../indicators/energy/state_acs_arr_gap_inr_per_kwh.md) | The two discom-distress headlines. AT&C folds technical loss with billing+collection failure; ACS-ARR gap measures whether each kWh sold is making or losing money. |
| "How much of the loss is technical vs commercial?" | [`energy/state_distribution_td_loss_pct`](../indicators/energy/state_distribution_td_loss_pct.md) (technical), [`energy/state_distribution_billing_efficiency_pct`](../indicators/energy/state_distribution_billing_efficiency_pct.md) (billing), [`energy/state_distribution_collection_efficiency_pct`](../indicators/energy/state_distribution_collection_efficiency_pct.md) (collection) | Decomposes the AT&C headline. A state with low T&D loss and bad collection is a different policy problem from a state with high T&D loss and good collection. |
| "How much renewable does this state have, and is it on the RPO trajectory?" | [`energy/state_renewable_grid_capacity_mw`](../indicators/energy/state_renewable_grid_capacity_mw.md) and [`energy/state_rpo_compliance_pct`](../indicators/energy/state_rpo_compliance_pct.md) | Capacity stock + regulatory compliance. RPO data is sparse (FY19-FY21 only); regulatory enforcement has been historically weak. |
| "Is rooftop solar taking off?" | [`energy/state_rooftop_solar_capacity_mw`](../indicators/energy/state_rooftop_solar_capacity_mw.md) | The PM Surya Ghar (Feb 2024) subsidy push is the leading-edge policy lever; this artifact is the leading indicator. |
| "How much non-fossil capacity does India have on the road to 500 GW by 2030?" | [`energy/installed_capacity_renewable_mw`](../indicators/energy/installed_capacity_renewable_mw.md) (MNRE bucket — excludes large hydro) + [`energy/installed_capacity_hydro_mw`](../indicators/energy/installed_capacity_hydro_mw.md) (large hydro) + [`energy/installed_capacity_nuclear_mw`](../indicators/energy/installed_capacity_nuclear_mw.md) | India's NDC target uses the *non-fossil* basket, broader than MNRE's RES bucket. Reading MNRE-only undersells the climate-aligned share by ~50 GW. |

## Conceptual taxonomy

### ICED vs CEA division of labour

The two main upstream sources are not redundant; they have a clean division of labour that the artifact split mirrors:

- **ICED (long series)** — the IEA-NITI Aayog dashboard re-publishes CEA / MNRE / PFC data with a stable, multi-decade time-series structure. Use ICED-sourced artifacts when the question is "how has X evolved over FY05-FY24?" — installed capacity by state by year, generation by fuel by state by year, peak demand by state by year, discom AT&C loss trajectories. ICED's revision discipline is good but the latest-month value typically lags by 3–6 months.
- **CEA (freshness snapshot)** — the Central Electricity Authority's monthly Installed Capacity report and Executive Summary are the *current-month* snapshot. Use CEA-sourced artifacts when the question is "what is the fuel mix *today*?" or "what was peak demand met *last month*?" — these have a 30–45 day lag rather than 3–6 months. The trade-off: no long history, just the latest snapshot.

When a state-level chart needs both depth and freshness, the right pattern is a long-history ICED series with a CEA-sourced "latest snapshot" callout, not a single mixed series. yen-gov keeps these as separate artifacts on purpose.

### Generation vs procurement vs installed capacity vs siting basis

Five distinct measurement bases for "how much electricity does state X have" all show up in this corpus and conflating them is the dominant mis-read trap:

1. **Installed capacity (geographical / siting basis)** — [`energy/state_installed_capacity_geographical_mw`](../indicators/energy/state_installed_capacity_geographical_mw.md), [`energy/installed_mw_by_state`](../indicators/energy/installed_mw_by_state.md). Plants *physically located* in the state. Maharashtra and Chhattisgarh look different on this basis than on procurement basis because each hosts large generators that ship electrons elsewhere.
2. **Installed capacity (with allocated shares)** — [`energy/state_installed_capacity_with_alloc_mw`](../indicators/energy/state_installed_capacity_with_alloc_mw.md). Same plants, but each state credited its share of central-sector and joint-sector plants per the regional-allocation formula. This is the basis under which "Maharashtra's share of NTPC" actually counts toward Maharashtra. The right view if the question is "how much capacity does this state's grid have access to."
3. **Procurement / purchase mix** — [`energy/state_power_purchase_share_pct`](../indicators/energy/state_power_purchase_share_pct.md). What the state's distribution utilities actually bought, by source. Reflects PPA structure plus spot purchases.
4. **Actual generation** — [`energy/state_electricity_generation_mu`](../indicators/energy/state_electricity_generation_mu.md), [`energy/state_electricity_generation_by_source_gwh`](../indicators/energy/state_electricity_generation_by_source_gwh.md). Electrons that actually came out of plants in the state. Different from installed-capacity * 8760 because PLF varies by fuel (coal ~65%, hydro ~35%, solar ~20%, wind ~25%).
5. **Sales / consumption** — [`energy/state_electricity_sales_mu`](../indicators/energy/state_electricity_sales_mu.md), [`energy/state_per_capita_electricity_consumption_kwh`](../indicators/energy/state_per_capita_electricity_consumption_kwh.md). Energy actually billed to (or consumed by) end-customers in the state.

A coal-heavy generating state (Chhattisgarh, Odisha) will have:

> generation_geographical >> sales_in_state

because most of its generation goes to Maharashtra / Delhi / Gujarat through inter-state transmission. A demand-heavy importing state (Delhi) will have:

> sales >> generation_geographical

because it imports almost everything. The right number for *"how much power does state X consume"* is sales; for *"how much does state X generate"* is generation; for *"how much capacity is allocated to state X"* is the with-allocation measure; for *"how big is state X's physical generation infrastructure"* is the geographical basis.

### Renewable: MNRE bucket vs CEA non-fossil bucket vs IEA renewable

Three legitimate definitions of "renewable" appear in this topic:

- **MNRE RES bucket** ([`energy/installed_capacity_renewable_mw`](../indicators/energy/installed_capacity_renewable_mw.md)). What CEA reports under the "RES (MNRE)" column: solar (ground + rooftop + hybrid + off-grid + KUSUM) + wind + small hydro (≤25 MW) + biomass + waste-to-energy. **Excludes large hydro.**
- **CEA non-fossil basket.** RES (MNRE) + large hydro + nuclear. The basket India's 50%-non-fossil-by-2030 NDC uses. Roughly 10–12 GW larger than RES alone because of large hydro.
- **IEA renewable basket.** Includes all hydro (small and large) plus solar, wind, biomass, geothermal, marine. Larger than MNRE because large hydro is included.

A chart that compares "India's renewable share" with another country's should be explicit about which definition. The yen-gov corpus uses MNRE's RES bucket as the default `installed_capacity_renewable_mw` because that's the column CEA / MNRE actually publish; large hydro and nuclear are tracked as separate per-fuel artifacts and can be added downstream when the chart needs the broader non-fossil view.

### Discom finances: AT&C, T&D, ACS-ARR — three numbers, one story

The discom (electricity distribution company) is the loss-making layer of India's power sector. Three artifacts together describe its health:

- **T&D losses** ([`energy/state_distribution_td_loss_pct`](../indicators/energy/state_distribution_td_loss_pct.md)) — pure technical loss (heat in conductors, transformer ageing). 5–8% in well-run systems; up to 15% in poorly-maintained.
- **AT&C losses** ([`energy/state_atc_losses_pct`](../indicators/energy/state_atc_losses_pct.md)) — *aggregate technical and commercial*. Folds T&D loss with billing failure (energy delivered but not billed, including theft and meter-tampering) and collection failure (billed but not paid). Always ≥ T&D. The single most-cited discom-distress number.
- **ACS-ARR gap** ([`energy/state_acs_arr_gap_inr_per_kwh`](../indicators/energy/state_acs_arr_gap_inr_per_kwh.md)) — Average Cost of Supply minus Average Revenue Realised, ₹ per kWh sold. The financial bottom line: positive means each kWh loses money. Closed by tariff hike, loss reduction, or state-budget subsidy transfer (which then shows up in [`fiscal/state_revenue_expenditure_inr_crore`](../indicators/fiscal/state_revenue_expenditure_inr_crore.md)).

The decomposition into [`energy/state_distribution_billing_efficiency_pct`](../indicators/energy/state_distribution_billing_efficiency_pct.md) and [`energy/state_distribution_collection_efficiency_pct`](../indicators/energy/state_distribution_collection_efficiency_pct.md) is what tells policy-makers *which* lever to pull. The two state-level reform programmes — **UDAY (2015)** and the current **Revamped Distribution Sector Scheme (RDSS, 2021–FY26, ₹3.04 lakh crore)** — both glide-path AT&C and ACS-ARR gap, with Centre disbursements tied to loss-reduction milestones. UDAY missed across most states; RDSS is mid-execution.

### Tier-1 / Tier-2 / Tier-3 batch context

The energy ingest landed in three batches with different breadth-vs-depth trade-offs:

- **Tier 1** — the must-have headline indicators (installed capacity total, generation total, peak demand met, AT&C, ACS-ARR gap, per-capita consumption). Long history, top quality.
- **Tier 2** — the fuel-disaggregated and policy-fine-grain indicators (capacity by source, generation by source, plant load factor by fuel, billing/collection efficiency, T&D loss, RPO compliance, capacity pipeline, thermal retirements).
- **Tier 3** — the recent / one-shot snapshots (latest-month CEA capacity, rooftop solar by state, renewable potential vs installed). Higher freshness, sometimes single-period coverage.

The artifact's `coverage.temporal` field tells you which tier you're reading: a multi-decade temporal span is Tier 1; a 5-10 year span with fuel break is Tier 2; a single-month or single-year snapshot is Tier 3. A citizen-facing chart should default to Tier 1 for the headline and reach for Tier 2 only when the question genuinely needs the disaggregation.

## Vintage and revision discipline

- **CEA monthly snapshot.** The IC sheet is published by the 7th-10th of each month for the previous month-end. yen-gov re-pulls monthly; values rarely revise but can update if CEA corrects a state's installed-capacity classification (small hydro reclassified between hydro and RES is a recurring case).
- **ICED long-series revision.** Annual values are typically firm 6–9 months after fiscal-year close. Revisions of ±1-3% on capacity numbers and ±5% on PLF / loss numbers are common as PFC's discom-performance report cycles in. The artifact's `methodology_vintage` field records the ICED snapshot date.
- **PFC discom-performance report**, the upstream for discom-finance artifacts, is published with ~12-month lag (FY24 numbers in early FY26). AT&C / ACS-ARR data for the most recent year is therefore *typically a year stale* relative to the rest of the energy corpus. A "latest data" chart that puts FY25 generation alongside FY23 AT&C is not wrong but should be honest about the lag.
- **Renewable capacity revisions.** MNRE periodically reclassifies plants (rooftop / KUSUM / bundled vs unbundled solar) and the historical series can shift slightly. The state-level renewable capacity series ([`energy/state_renewable_grid_capacity_mw`](../indicators/energy/state_renewable_grid_capacity_mw.md)) has the smoothest revision history; rooftop ([`energy/state_rooftop_solar_capacity_mw`](../indicators/energy/state_rooftop_solar_capacity_mw.md)) the choppiest because the under-counting in the rooftop / behind-the-meter space is real.
- **Methodology vintage tag.** Most artifacts carry "ICED YYYY-MM snapshot" or "CEA YYYY-MM IC sheet" in `methodology_vintage`. Re-pulling under a newer snapshot can refresh latest-month values without touching the historical tail.

## Comparability gotchas

- **Capacity is not generation.** A state can have 50% renewable on the installed-capacity chart and still be coal-fired in practice (because PLF for coal ~65% vs solar ~20%). Always pair a capacity chart with a generation chart in any "fuel mix" framing.
- **Free-power and unmetered supply distort discom artifacts.** Punjab agri pumpset, Tamil Nadu agri, Telangana agri, Delhi 100-200 unit free, Karnataka — unmetered free supply is booked by the discom as "loss" until the state-budget subsidy reimbursement closes the gap. So AT&C and ACS-ARR optically blow up the year a free-power scheme is announced even if the underlying utility performance is unchanged. Read the gross numbers with this caveat or use the post-subsidy "tariff subsidy received" view (not yet ingested).
- **Installed capacity, geographical vs allocated.** As above — Maharashtra's footprint changes by 30%+ depending on which basis. Charts that compare states should pick one basis and stay with it; an "all-India" total can use either since the inter-state allocations net to zero.
- **Per-capita consumption is industrial-load distorted.** Gujarat, Chhattisgarh, Odisha look very high on per-capita because industry takes most of the electrons; the household experience does not match the headline. A separate "per-capita household consumption" view would correct for this; not yet ingested.
- **PLF interpretation.** Plant Load Factor is generation as a share of nameplate capacity over a year. Coal PLF declined from ~78% (FY10) to ~65% (FY24) for two reasons: rising solar/wind (must-run) preempts coal, and discom payment defaults make some coal plants stranded. The two have very different policy implications; PLF alone cannot tell you which is dominant in a given state.
- **State-vs-state ranking on most energy artifacts is at level 2 or 3 on the Hans comparability ladder.** Industrial structure, climate, and resource endowment differ enough that a raw rank without context is misleading. Per-capita normalisation, share-of-fuel-mix faceting, or year-on-year-change ranks are usually more honest than absolute-level ranks.

## Related topic spines

- **[Environment](../indicators/environment/)** — power-sector CO₂ emissions are derived from this topic's generation-by-fuel artifacts via fuel emission factors. Air-quality (PM2.5, NO₂, SO₂) is downstream of thermal-plant operations.
- **[Fiscal](./fiscal.md)** — discom subsidy transfers from state budgets land in `state_revenue_expenditure_inr_crore`. The 15th FC's 0.5%-of-GSDP power-reform-conditional borrowing window is the explicit fiscal-energy cross-edge.
- **[Prices](./prices.md)** — fuel inflation in CPI is driven by LPG subsidy resets, electricity-tariff orders (SERC), ATF excise pass-through. The state-level fuel-CPI ([`prices/state_cpi_fuel_inflation_pct`](../indicators/prices/state_cpi_fuel_inflation_pct.md)) is the household-side counterpart to the energy topic's tariff-and-subsidy data.
- **[Demography](../indicators/demography/)** — per-capita electricity consumption needs population denominators; state-level demand projections need both population and economic-structure inputs.
- **[Economy](../indicators/economy/)** — per-capita NSDP and per-capita electricity consumption track each other tightly; reads of one without the other miss half the story.

## Indicator pages in this topic

- [`energy/india_capacity_pipeline_gw`](../indicators/energy/india_capacity_pipeline_gw.md) — National under-construction capacity pipeline by year of expected commissioning, FY11–FY31. Forward-looking.
- [`energy/india_thermal_capacity_retired_mw`](../indicators/energy/india_thermal_capacity_retired_mw.md) — National thermal capacity retired per year, by fuel, FY06–FY25.
- [`energy/installed_capacity_by_source_mw`](../indicators/energy/installed_capacity_by_source_mw.md) — CEA monthly snapshot: per-state capacity broken into coal / gas / nuclear / hydro / renewable / other-thermal.
- [`energy/installed_capacity_coal_mw`](../indicators/energy/installed_capacity_coal_mw.md) — Per-state coal-fired capacity, latest CEA snapshot.
- [`energy/installed_capacity_gas_mw`](../indicators/energy/installed_capacity_gas_mw.md) — Per-state gas-based capacity, latest CEA snapshot.
- [`energy/installed_capacity_hydro_mw`](../indicators/energy/installed_capacity_hydro_mw.md) — Per-state conventional hydro (incl. PSPs, excl. small-hydro), latest snapshot.
- [`energy/installed_capacity_nuclear_mw`](../indicators/energy/installed_capacity_nuclear_mw.md) — Per-state nuclear capacity, latest snapshot.
- [`energy/installed_capacity_renewable_mw`](../indicators/energy/installed_capacity_renewable_mw.md) — Per-state MNRE RES bucket (solar + wind + small-hydro + biomass + WtE), latest snapshot. Excludes large hydro.
- [`energy/installed_capacity_thermal_mw`](../indicators/energy/installed_capacity_thermal_mw.md) — Per-state total thermal (coal + lignite + gas + diesel), latest snapshot.
- [`energy/installed_capacity_total_mw`](../indicators/energy/installed_capacity_total_mw.md) — Per-state total nameplate capacity, latest CEA snapshot.
- [`energy/installed_mw_by_state`](../indicators/energy/installed_mw_by_state.md) — Per-state installed capacity (siting basis), 2019.
- [`energy/national_final_energy_consumption_by_sector_mtoe`](../indicators/energy/national_final_energy_consumption_by_sector_mtoe.md) — National final energy by sector (agri / industry / transport / residential / commercial / others) and source (oil / gas / coal / electricity / biomass), FY06–FY25.
- [`energy/national_primary_energy_supply_mtoe`](../indicators/energy/national_primary_energy_supply_mtoe.md) — National primary energy supply by source (coal / oil / gas / nuclear / hydro / renewables), FY06–FY25.
- [`energy/national_renewable_potential_vs_installed_mw`](../indicators/energy/national_renewable_potential_vs_installed_mw.md) — Installed renewable vs assessed potential, by source.
- [`energy/state_acs_arr_gap_inr_per_kwh`](../indicators/energy/state_acs_arr_gap_inr_per_kwh.md) — Per-state ACS-ARR gap (cost-vs-realised), ₹/kWh, FY16–FY25.
- [`energy/state_atc_losses_pct`](../indicators/energy/state_atc_losses_pct.md) — Per-state Aggregate Technical & Commercial loss %, FY16–FY25.
- [`energy/state_coal_consumption_mt`](../indicators/energy/state_coal_consumption_mt.md) — Per-state coal consumption, Mt, FY06–FY25.
- [`energy/state_distribution_billing_efficiency_pct`](../indicators/energy/state_distribution_billing_efficiency_pct.md) — Per-state billing efficiency %, FY10–FY25.
- [`energy/state_distribution_collection_efficiency_pct`](../indicators/energy/state_distribution_collection_efficiency_pct.md) — Per-state collection efficiency %, FY10–FY25.
- [`energy/state_distribution_td_loss_pct`](../indicators/energy/state_distribution_td_loss_pct.md) — Per-state pure T&D loss %, FY10–FY25.
- [`energy/state_electricity_generation_by_source_gwh`](../indicators/energy/state_electricity_generation_by_source_gwh.md) — Per-state generation by fuel source, GWh, FY16–FY26.
- [`energy/state_electricity_generation_mu`](../indicators/energy/state_electricity_generation_mu.md) — Per-state gross generation, MU, FY16–FY26.
- [`energy/state_electricity_peak_demand_mw`](../indicators/energy/state_electricity_peak_demand_mw.md) — Per-state peak instantaneous demand met, latest FY snapshot.
- [`energy/state_electricity_sales_mu`](../indicators/energy/state_electricity_sales_mu.md) — Per-state electricity sales (billed), MU, FY16–FY25.
- [`energy/state_installed_capacity_by_source_mw`](../indicators/energy/state_installed_capacity_by_source_mw.md) — Per-state capacity by fuel source (coal / hydro / large-hydro / small-hydro / wind / solar / bio-power / oil-gas / nuclear), FY16–FY26.
- [`energy/state_installed_capacity_geographical_mw`](../indicators/energy/state_installed_capacity_geographical_mw.md) — Per-state capacity by physical-location basis, FY16–FY26.
- [`energy/state_installed_capacity_total_mw`](../indicators/energy/state_installed_capacity_total_mw.md) — Per-state total installed capacity, FY05–FY25.
- [`energy/state_installed_capacity_with_alloc_mw`](../indicators/energy/state_installed_capacity_with_alloc_mw.md) — Per-state capacity with central+joint sector allocation shares included, FY16–FY26.
- [`energy/state_oil_product_consumption_kt`](../indicators/energy/state_oil_product_consumption_kt.md) — Per-state oil-product consumption (HSD, petrol, LPG, kerosene, naphtha, pet-coke), kt, FY11–FY25.
- [`energy/state_peak_demand_mw`](../indicators/energy/state_peak_demand_mw.md) — Per-state peak demand, MW, FY14–FY25 (long history).
- [`energy/state_peak_electricity_demand_mw`](../indicators/energy/state_peak_electricity_demand_mw.md) — Per-state peak demand, latest-FY snapshot.
- [`energy/state_peak_met_mw`](../indicators/energy/state_peak_met_mw.md) — Per-state peak supply actually delivered, MW, FY14–FY25.
- [`energy/state_per_capita_availability_kwh`](../indicators/energy/state_per_capita_availability_kwh.md) — Per-capita energy availability, kWh/person/year, FY05–FY25 (requirement-side denominator).
- [`energy/state_per_capita_electricity_consumption_kwh`](../indicators/energy/state_per_capita_electricity_consumption_kwh.md) — Per-capita electricity consumption (sales-side), kWh/person/year, FY10–FY24.
- [`energy/state_plant_load_factor_pct`](../indicators/energy/state_plant_load_factor_pct.md) — Per-state PLF by fuel source, FY16–FY26.
- [`energy/state_power_availability_mu`](../indicators/energy/state_power_availability_mu.md) — Per-state energy availability, MU, FY05–FY25.
- [`energy/state_power_purchase_share_pct`](../indicators/energy/state_power_purchase_share_pct.md) — Per-state power-purchase mix by source %, FY16–FY25.
- [`energy/state_power_requirement_mu`](../indicators/energy/state_power_requirement_mu.md) — Per-state energy requirement, MU, FY05–FY25.
- [`energy/state_renewable_grid_capacity_mw`](../indicators/energy/state_renewable_grid_capacity_mw.md) — Per-state grid-interactive renewable capacity, MW, 2007–2024 (calendar-year, end-March).
- [`energy/state_rooftop_solar_capacity_mw`](../indicators/energy/state_rooftop_solar_capacity_mw.md) — Per-state cumulative rooftop solar, MW, FY18–FY26.
- [`energy/state_rpo_compliance_pct`](../indicators/energy/state_rpo_compliance_pct.md) — Per-state Renewable Purchase Obligation compliance %, FY19–FY21 (sparse).

## Further reading

- **Central Electricity Authority — *Power Sector at a Glance, All India***. Monthly snapshot of capacity, generation, peak demand, energy met. The reference for any current-month statement. <https://cea.nic.in/>.
- **CEA — *National Electricity Plan***, latest version. The 5+5-year capacity-and-transmission planning document; coal-retirement schedule and renewable build-out trajectory anchor any forward-looking energy chart. <https://cea.nic.in/national-electricity-plan/>.
- **NITI Aayog — *India Climate & Energy Dashboard (ICED)***. The long-series re-publishing portal; methodology notes per indicator. <https://iced.niti.gov.in/>.
- **Power Finance Corporation — *Report on Performance of State Power Utilities***, annual. The discom-finance bible; AT&C, ACS-ARR, debt and tariff-subsidy detail by discom. <https://pfcindia.com/Home/VS/27>.
- **Ministry of New & Renewable Energy — *Annual Report***. Renewable target progress, scheme-wise allocations, RPO compliance overview. <https://mnre.gov.in/>.
- **IEA, *India Energy Outlook 2021***. The most-cited international long-term Indian energy projection; the anchor for any "India still has runway" framing on per-capita consumption. <https://www.iea.org/reports/india-energy-outlook-2021>.
