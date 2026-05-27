"""Seed the 17 energy citation rows into ``taxonomy/sources.parquet``.

P.1.A (7 sources) + P.1.B (5 sources) + P.1.C PR-Q (1 source) +
P.1.C PR-R (1 source) + P.1.C PR-S (1 source) + P.1.C PR-T (1 source) +
P.1.C PR-U (1 source) = 17 distinct upstreams.

P.1.A: 1 CEA + 3 ICED endpoints + 3 RBI Handbook tables (Table 142
peak-demand + Table 142 peak-met + Table 140 installed-capacity long-arc
added at C4.6).

P.1.B: 2 ICED distribution-dashboard endpoints (operational performance
and RPO compliance) + 3 RBI Handbook tables (141 power requirement,
139 power availability, 138 per-capita availability).

P.1.C PR-Q: 1 ICED state-coal-consumption-mt endpoint (first canonical
fuel-consumption lift; originating data: Coal Controller's Office /
Ministry of Coal; ICED is the federal aggregator, not issuing authority).
P.1.C PR-R: 1 ICED state-rooftop-solar-capacity-mw endpoint (second
canonical P.1.C lift; originating data: Ministry of New & Renewable
Energy (MNRE) / state nodal agencies. ICED is the federal aggregator,
not issuing authority).
P.1.C PR-S: 1 ICED india-thermal-capacity-retired-mw endpoint (third
canonical P.1.C lift; first Pattern A-facet in cohort; national-grain
fuel-faceted retired thermal capacity FY05-FY25; originating data:
Central Electricity Authority via ICED federal aggregator).
Each gets a citation row in the sources ledger so every emitted
observation in P.1.A, P.1.B, and P.1.C (PR-Q + PR-R + PR-S) can FK to
a real ``source_id`` per Holy Law #9 + ADR-0032.

Pattern mirrors ``boundary_layers_seed.upsert_boundary_sources`` (T.0d):
INSERT-OR-REPLACE keyed on ``source_id`` so multiple subsystems can
upsert their rows into the same in-memory ``sources`` table before the
final COPY to parquet.

``derive_source_id(producer, title, vintage)`` is the only way to compute
``source_id`` -- NEVER hand-author (CLAUDE.md §10 + ADR-0032). The 12
expected hashes are baked into ``datasets/taxonomy/indicators.json`` at
C1 commit (6 rows) + C4.6 commit (7th, RBI Table 140) + P.1.B commit
(8th-12th); if a triple is edited here, those FKs go dangling and the
catalogue compile fails closed.

P.1.A C3 seed (2026-05-22); RBI Table 140 long-arc citation added at
P.1.A C4.6 (2026-05-24); P.1.B 5-row extension (2026-05-25).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.envelope import SourceRow

__all__ = [
    "ENERGY_SOURCE_ID_BY_NICKNAME",
    "ENERGY_SOURCES",
    "SOURCE_NICKNAMES",
    "upsert_energy_sources",
    "upsert_energy_sources_to_parquet",
]


# Operator nicknames for the 21 energy sources (7 P.1.A + 5 P.1.B + 1 P.1.C
# PR-Q + 1 P.1.C PR-R + 1 P.1.C PR-S + 1 P.1.C PR-T + 1 P.1.C PR-U + 1 P.1.C
# PR-V + 1 P.1.C PR-W + 1 P.1.C PR-X + 1 P.1.C PR-Y).
# Adapters look up the materialised source_id by nickname rather than
# rebuilding the triple-hash each time.
SOURCE_NICKNAMES: tuple[str, ...] = (
    # --- P.1.A (7) -------------------------------------------------
    "cea_monthly_ic",
    "iced_capacity_metatable",
    "iced_deep_dive",
    "iced_gen_metatable",
    "rbi_hbk_142_peak_demand",
    "rbi_hbk_142_peak_met",
    "rbi_hbk_140_installed_capacity",
    # --- P.1.B (5) -------------------------------------------------
    # 2 ICED distribution-dashboard endpoints (distinct upstream
    # products from the analytics deep-dive surface; earn their own
    # ledger rows per ADR-0032 citation identity = (producer, title,
    # vintage)).
    "iced_distribution_perf",
    "iced_distribution_rpo",
    # 3 RBI Handbook tables not previously cited (state-level demand /
    # supply / per-capita-availability long-arc — CEA-originated,
    # RBI-republished, archived snapshot).
    "rbi_hbk_141_power_requirement",
    "rbi_hbk_139_power_availability",
    "rbi_hbk_138_per_capita_availability",
    # --- P.1.C PR-Q (1; first canonical fuel-consumption lift) ----
    # ICED state-coal-consumption-mt endpoint (4-grade SUM lift:
    # raw + washed + middlings + lignite; FY06-FY25; TOTAL COAL rows
    # dropped to avoid double-counting). Originating data: Coal
    # Controller's Office / Ministry of Coal. ICED is the federal
    # aggregator; not the issuing authority for the underlying fact
    # (plan-doc §3 Q-d). Same silver / not-authority / live-fetch
    # classification as other ICED endpoints.
    "iced_consumption_coal",
    # --- P.1.C PR-R (1; second canonical lift, rooftop solar) -----
    # ICED state-rooftop-solar-capacity-mw endpoint. Cumulative MW of
    # building-mounted PV across residential / commercial / industrial /
    # public categories; complements (NOT replaces) utility-scale solar
    # tracked under installed-capacity-snapshot-mw-renewable.
    # Originating data: MNRE / state nodal agencies via the National
    # Rooftop Solar Programme; ICED is the federal aggregator.
    "iced_rooftop_solar",
    # --- P.1.C PR-S (1; third canonical lift, thermal retired) ----
    # ICED retired-capacity-plants endpoint. National-only annual
    # retired generating capacity by fuel (FY05-FY25). Publisher
    # bundles "oil-gas" (oil-fired + diesel + gas) as a single facet;
    # canonical SUB_FUEL_TO_CANONICAL collapses to "gas" per Hans D33.8.
    # First Pattern A-facet indicator in P.1.C cohort. Originating
    # data: CEA-published station-level retirement records.
    "iced_thermal_retired",
    # --- P.1.C PR-T (1; fourth canonical lift, oil-product consumption) -
    # ICED oil-product consumption state-wise endpoint. Per-state per-
    # fiscal-year refined-petroleum consumption (kt), faceted on a NEW
    # ``oil_product`` axis (7 products: diesel-hsd, petrol, lpg,
    # kerosene, naphtha, petroleum-coke, others). Unlike fuel_type's
    # publisher-sub-bucket collapse, oil_product labels map 1:1 onto
    # canonical value_ids -- no SUB_FUEL_TO_CANONICAL-style step.
    # Originating data: PPAC / Ministry of Petroleum & Natural Gas.
    "iced_consumption_oil",
    # --- P.1.C PR-U (1; fifth canonical lift, primary energy supply) ----
    # ICED national primary-energy-supply endpoint. National-only annual
    # TPES (total primary energy supply) by source (FY05-FY25). Publisher
    # facets: coal, oil, gas, hydro, nuclear, renewables (+ total which
    # is filtered at adapter time as compute-on-read parent). Second
    # Pattern A-facet indicator in P.1.C cohort; reuses the EXISTING
    # ``fuel_type`` axis (extended with `oil` + `renewable` value_ids
    # in this PR). Originating data: MoSPI Energy Statistics India,
    # republished via NITI Aayog ICED dashboard.
    "iced_primary_energy_supply",
    # P.1.C PR-V (1) - Plant Load Factor (PLF) by fuel state-wise. Third
    # Pattern A-facet in P.1.C cohort with NO sub-fuel collapse: 8
    # publisher fuel buckets (bio-power, coal, hydro, nuclear, oil-gas,
    # small-hydro, solar, wind) map 1:1 to existing fuel_type axis
    # value_ids (biomass / coal / hydro / nuclear / gas / small_hydro /
    # solar / wind). PLF is a PERCENTAGE so values cannot be summed
    # across fuels -- the standard SUB_FUEL_TO_CANONICAL renewable
    # aggregation would produce nonsense. Each (state, FY, fuel) cell
    # is a passthrough observation. Lifts onto the EXISTING
    # ``energy_generation`` table stem (PLF is a generation-utilization
    # metric). Originating data: CEA per-station daily generation;
    # republished via NITI Aayog ICED dashboard.
    "iced_plant_load_factor",
    # P.1.C PR-W (1) - State power-purchase share by source. Fourth
    # Pattern A-facet in P.1.C cohort with NO sub-fuel collapse: 12
    # publisher buckets (8 PR-V-style fuels + diesel + hybrid-bundled +
    # other-res + trading-and-others). 10 map to existing fuel_type axis
    # values; 2 require NEW value_ids (hybrid_bundled + trading_other).
    # PR-W is a procurement-mix indicator -- where a state's DISCOMs
    # BUY from, not what they GENERATE. Compare with PR-Q's generation
    # mix to read the trade pattern (RE-exporters vs thermal-importers).
    # Values are percentages summing to ~100 per (state, FY); cannot
    # collapse renewable sub-fuels (same constraint as PR-V). Lifts
    # onto the EXISTING ``energy_demand_supply`` table stem (procurement
    # is a demand-side metric). Originating data: PFC / Ministry of
    # Power; republished via NITI Aayog ICED dashboard.
    "iced_power_purchase_share",
    # P.1.C PR-X (1) - National final energy consumption by sector x fuel.
    # Fifth Pattern A-facet in P.1.C cohort; introduces NEW
    # `sector_fuel_pair` facet axis with 18 publisher (sector | fuel)
    # pairs collapsed to kebab indicator-id suffixes (agriculture-oil,
    # transport-electricity, ...). National-only IN entity, FY05-FY24.
    # Originating data: MoSPI Energy Statistics India; republished via
    # NITI Aayog ICED dashboard.
    "iced_final_energy_consumption",
    # P.1.C PR-Y (1) - State-wise grid-connected renewable installed
    # capacity from RBI Handbook Table 143. Pattern A-single (scalar;
    # no facet axis). End-March cumulative MW snapshot, 2007-2024.
    # Originating data: MoSPI Energy Statistics; RBI republishes as
    # silver-tier longitudinal anchor (same Hans D33 / plan-doc §3 Q-d
    # ruling as RBI Hbk 140/141/142 -- republisher not authority).
    "rbi_hbk_143_renewable_grid_capacity",
)


# (producer, title, vintage) triples. Per ADR-0042 (source schema v3.0),
# vintage MUST be non-empty ("strongest period anchor available"):
# publisher edition when published, operator snapshot window when not.
# CEA Monthly is the March-2026 snapshot; ICED APIs are continuously
# updated by NITI Aayog so we tag the federal fiscal-year snapshot
# window ("2024-25") of when this corpus was harvested; RBI Handbook
# tables carry their explicit 2024-25 edition tag.
_TRIPLES: dict[str, tuple[str, str, str]] = {
    "cea_monthly_ic": (
        "Central Electricity Authority",
        "Monthly Executive Summary \u2014 Installed Capacity (IC) sheet",
        "2026-03",
    ),
    "iced_capacity_metatable": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Capacity Metatable API (state-wise installed capacity, by fuel)",
        "2024-25",
    ),
    "iced_deep_dive": (
        "NITI Aayog India Climate & Energy Dashboard",
        "State-wise Deep Dive API",
        "2024-25",
    ),
    "iced_gen_metatable": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Generation Metatable API (state-wise electricity generation, by fuel)",
        "2024-25",
    ),
    "rbi_hbk_142_peak_demand": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States \u2014 Table 142: State-wise Actual Power Supply Position \u2014 Peak Demand",
        "2024-25",
    ),
    "rbi_hbk_142_peak_met": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States \u2014 Table 142: State-wise Actual Power Supply Position \u2014 Peak Met",
        "2024-25",
    ),
    "rbi_hbk_140_installed_capacity": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States \u2014 Table 140: State-wise Installed Capacity of Power",
        "2024-25",
    ),
    # --- P.1.B (5) -----------------------------------------------------
    "iced_distribution_perf": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Distribution Operational Performance API (state-wise billing efficiency, collection efficiency, T&D losses)",
        "2024-25",
    ),
    "iced_distribution_rpo": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Distribution RPO Compliance API (state-wise Renewable Purchase Obligation compliance, by segment)",
        "2024-25",
    ),
    "rbi_hbk_141_power_requirement": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States \u2014 Table 141: State-wise Power Requirement",
        "2024-25",
    ),
    "rbi_hbk_139_power_availability": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States \u2014 Table 139: State-wise Availability of Power",
        "2024-25",
    ),
    "rbi_hbk_138_per_capita_availability": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States \u2014 Table 138: State-wise Per Capita Availability of Power",
        "2024-25",
    ),
    # --- P.1.C PR-Q (1) ------------------------------------------------
    "iced_consumption_coal": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Coal Consumption (Domestic) State-wise API (per-state fiscal-year coal consumption, by grade)",
        "2024-25",
    ),
    # --- P.1.C PR-R (1) ------------------------------------------------
    "iced_rooftop_solar": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Rooftop Solar Capacity (MW) State-wise API (per-state cumulative rooftop solar installed capacity)",
        "2024-25",
    ),
    # --- P.1.C PR-S (1) ------------------------------------------------
    "iced_thermal_retired": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Retired Thermal Capacity Plants Dashboard (national fiscal-year retired generating capacity by fuel)",
        "2024-25",
    ),
    # --- P.1.C PR-T (1) ------------------------------------------------
    "iced_consumption_oil": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Oil Product Consumption State-wise API (per-state fiscal-year refined-petroleum-product consumption, by product)",
        "2024-25",
    ),
    # --- P.1.C PR-U (1) ------------------------------------------------
    "iced_primary_energy_supply": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Primary Energy Supply National API (national fiscal-year primary-energy supply (TPES) by source, mtoe)",
        "2024-25",
    ),
    # --- P.1.C PR-V (1) ------------------------------------------------
    "iced_plant_load_factor": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Plant Load Factor by Fuel State API (state-wise per-fuel PLF percentage, fiscal-year, 8 fuel buckets)",
        "2024-25",
    ),
    # --- P.1.C PR-W (1) ------------------------------------------------
    "iced_power_purchase_share": (
        "NITI Aayog India Climate & Energy Dashboard",
        "State Power Purchase Quantum and Cost API (state-wise procurement-mix share by source, fiscal-year, 12 source buckets)",
        "2024-25",
    ),
    # --- P.1.C PR-X (1) ------------------------------------------------
    "iced_final_energy_consumption": (
        "NITI Aayog India Climate & Energy Dashboard",
        "Final Energy Consumption National API (national fiscal-year final-energy consumption by sector x fuel composite, mtoe)",
        "2024-25",
    ),
    # --- P.1.C PR-Y (1) ------------------------------------------------
    "rbi_hbk_143_renewable_grid_capacity": (
        "Reserve Bank of India",
        "Handbook of Statistics on Indian States, Table 143 (State-wise grid-connected renewable installed capacity, MW, end-March snapshot)",
        "2024-25",
    ),
}


# Per-source license / confidence_tier / verification_method / authority /
# url_main / notes. CEA is the issuing authority for installed-capacity
# data (gold tier). ICED is the federal aggregator over CEA-published
# station-level data (silver tier -- republisher). RBI Handbook is the
# silver-tier longitudinal republisher of CEA peak-demand series per
# plan-doc §3 Q-d (Hans 2026-05-22): "RBI is the issuing authority for
# its own analytical Handbook but NOT for the underlying electricity
# capacity numbers -- every affected file under datasets/indicators/in/
# energy/ carries the disclosure 'Originating data: Central Electricity
# Authority, Ministry of Power' verbatim. Promoting longitudinal
# republishers to gold would silently inflate every aggregator in the
# future corpus and the tier loses signal." verification_method is
# archived-snapshot because the RBI Handbook is published as a PDF
# annually; we extract the table and archive it, not poll a live API.
# All energy upstreams publish under OGL-IN-1.0 (Open Government Licence
# India).
_BY_NICKNAME: dict[str, tuple[str, str, str, bool, str, str | None]] = {
    "cea_monthly_ic": (
        "OGL-IN-1.0",
        "gold",
        "live-fetch",
        True,
        "https://cea.nic.in/monthly-installed-capacity-report/",
        "Monthly all-India + state-wise installed capacity by fuel; primary publisher for the canonical installed-capacity series.",
    ),
    "iced_capacity_metatable": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://iced.niti.gov.in/energy/electricity/generation/capacity/state-wise",
        "Federal aggregator over CEA station-level data; harmonised across fiscal years.",
    ),
    "iced_deep_dive": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://iced.niti.gov.in/energy/electricity",
        "Per-state deep-dive API; provides allocated-capacity series + per-capita consumption.",
    ),
    "iced_gen_metatable": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://iced.niti.gov.in/energy/electricity/generation",
        "Federal aggregator for state-wise electricity generation by fuel.",
    ),
    "rbi_hbk_142_peak_demand": (
        "OGL-IN-1.0",
        "silver",
        "archived-snapshot",
        False,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 142: 12-year state-wise peak demand series. Originating data: Central Electricity Authority, Ministry of Power (per the file disclosure). RBI is the longitudinal republisher; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    "rbi_hbk_142_peak_met": (
        "OGL-IN-1.0",
        "silver",
        "archived-snapshot",
        False,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 142: 12-year state-wise peak-supplied series. Originating data: Central Electricity Authority, Ministry of Power (per the file disclosure). RBI is the longitudinal republisher; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    "rbi_hbk_140_installed_capacity": (
        "OGL-IN-1.0",
        "silver",
        "archived-snapshot",
        False,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 140: long-arc state-wise installed-capacity series (FY05 onwards). Originating data: Central Electricity Authority, Ministry of Power (per the file disclosure). RBI is the longitudinal republisher; not the issuing authority for the underlying fact (plan-doc §3 Q-d). Used at P.1.A C4.6 to splice FY05-FY14 history onto state-installed-capacity-allocated-mw, whose ICED source (`iced_deep_dive`) only covers FY15-FY25.",
    ),
    # --- P.1.B (5) -----------------------------------------------------
    "iced_distribution_perf": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/energy/electricity/distribution/operationalPerformanceStates",
        "ICED distribution-dashboard endpoint covering three operational-performance series: billing efficiency, collection efficiency, T&D loss (state-wise FY09-FY24). Originating data: PFC State Distribution Utilities reports. ICED is the federal aggregator; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    "iced_distribution_rpo": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/energy/electricity/distribution/rpo",
        "ICED distribution-dashboard endpoint covering state-wise Renewable Purchase Obligation compliance (three facets: solar, non-solar, total; FY19-FY21). Originating data: MNRE / state regulators. ICED is the federal aggregator; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    "rbi_hbk_141_power_requirement": (
        "OGL-IN-1.0",
        "silver",
        "archived-snapshot",
        False,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 141: state-wise annual energy requirement (MU = GWh, FY05-FY25). Originating data: Central Electricity Authority, Ministry of Power (per the file disclosure). RBI is the longitudinal republisher; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    "rbi_hbk_139_power_availability": (
        "OGL-IN-1.0",
        "silver",
        "archived-snapshot",
        False,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 139: state-wise annual energy availability (MU = GWh, FY05-FY25). Originating data: Central Electricity Authority, Ministry of Power (per the file disclosure). Companion to Table 141 -- requirement minus availability gives the energy-not-supplied deficit. RBI is the longitudinal republisher; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    "rbi_hbk_138_per_capita_availability": (
        "OGL-IN-1.0",
        "silver",
        "archived-snapshot",
        False,
        "https://rbi.org.in/Scripts/PublicationsView.aspx?id=22512",
        "RBI Handbook of Statistics on Indian States Table 138: state-wise per-capita electricity availability (kWh per person per year, FY05-FY25). Originating data: Central Electricity Authority, Ministry of Power (per the file disclosure). Population denominator from Census 2011 + linear projection. RBI is the longitudinal republisher; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    # --- P.1.C PR-Q (1) ------------------------------------------------
    "iced_consumption_coal": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/energy/fuel-sources/coal/consumption-domestic-state",
        "ICED fuel-sources endpoint for state-wise domestic coal consumption (4 grades: raw + washed + middlings + lignite; FY06-FY25). Originating data: Coal Controller's Office / Ministry of Coal. ICED is the federal aggregator; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    # --- P.1.C PR-R (1) ------------------------------------------------
    "iced_rooftop_solar": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/energy/renewable/solar/rooftop/state",
        "ICED renewable-energy endpoint for state-wise cumulative rooftop solar capacity (FY18-FY25). Originating data: MNRE / state nodal agencies via the National Rooftop Solar Programme. ICED is the federal aggregator; not the issuing authority for the underlying fact (plan-doc §3 Q-d).",
    ),
    # --- P.1.C PR-S (1) ------------------------------------------------
    "iced_thermal_retired": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/v1/retired-capacity-plants",
        "ICED retired-capacity-plants endpoint for national fiscal-year retired thermal generating capacity by fuel (coal + oil-gas; FY05-FY25). Originating data: Central Electricity Authority station-level retirement records. ICED is the federal aggregator; not the issuing authority for the underlying fact (plan-doc §3 Q-d). National-only -- ICED does NOT publish state-level retired capacity.",
    ),
    # --- P.1.C PR-T (1) ------------------------------------------------
    "iced_consumption_oil": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/energy/fuel-sources/oil/consumptionStateProductTrend",
        "ICED fuel-sources endpoint for state-wise oil-product consumption (7 refined-petroleum products: diesel-hsd, petrol, lpg, kerosene, naphtha, petroleum-coke, others; FY11-FY25). Originating data: PPAC / Ministry of Petroleum & Natural Gas. ICED is the federal aggregator; not the issuing authority for the underlying fact (plan-doc §3 Q-d). First indicator on the NEW ``oil_product`` facet axis.",
    ),
    # --- P.1.C PR-U (1) ------------------------------------------------
    "iced_primary_energy_supply": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/analytics/state-wise-deep-dive",
        "ICED state-wise-deep-dive endpoint, primary-energy-supply national series: annual TPES (total primary energy supply) for India by source (coal + oil + gas + hydro + nuclear + renewables; FY05-FY25, mtoe). Originating data: MoSPI Energy Statistics India. ICED is the federal aggregator; not the issuing authority for the underlying fact (plan-doc §3 Q-d). National-only -- per-state TPES is NOT published by ICED. Second indicator on the EXISTING ``fuel_type`` axis (extended with `oil` + `renewable` value_ids in this PR).",
    ),
    # --- P.1.C PR-V (1) ------------------------------------------------
    "iced_plant_load_factor": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/v1/plf-metatable-data",
        "ICED plf-metatable-data endpoint: state-wise Plant Load Factor (PLF) percentages by fuel source (8 publisher buckets: bio-power / coal / hydro / nuclear / oil-gas / small-hydro / solar / wind; FY16-FY26). PLF is energy-generated / (capacity x hours-in-period) x 100. Originating data: CEA station-level daily generation. ICED is the federal aggregator; not the issuing authority for the underlying fact (plan-doc §3 Q-d). Third Pattern A-facet in P.1.C cohort -- maps 1:1 to existing fuel_type axis values (NO sub-fuel collapse because PLF is a percentage that cannot be meaningfully summed across fuels).",
    ),
    # --- P.1.C PR-W (1) ------------------------------------------------
    "iced_power_purchase_share": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/statelevel-power-purchase-quantum-and-cost",
        "ICED statelevel-power-purchase-quantum-and-cost endpoint: state-wise procurement-mix share by source (12 publisher buckets: bio-power / coal / diesel / hybrid-bundled / hydro / nuclear / oil-gas / other-res / small-hydro / solar / trading-and-others / wind; FY16-FY25). Values are percentages summing to ~100 per (state, FY). Originating data: PFC / Ministry of Power. ICED is the federal aggregator; not the issuing authority (plan-doc §3 Q-d). Fourth Pattern A-facet in P.1.C cohort -- 10 buckets map 1:1 to existing fuel_type axis values; 2 (hybrid-bundled + trading-and-others) require NEW canonical axis values (hybrid_bundled + trading_other). NO sub-fuel collapse (% values cannot be summed across fuels).",
    ),
    # --- P.1.C PR-X (1) ------------------------------------------------
    "iced_final_energy_consumption": (
        "OGL-IN-1.0",
        "silver",
        "live-fetch",
        False,
        "https://icedapi.niti.gov.in/analytics/state-wise-deep-dive",
        "ICED state-wise-deep-dive endpoint, final-energy-consumption national series: annual sectoral final-energy demand for India by (sector x fuel) composite (18 publisher pairs: agriculture / commercial / industry / non-energy / residential / transport / other / cgd-and-others x electricity / gas / oil / coal; FY05-FY24, mtoe). Originating data: MoSPI Energy Statistics India. ICED is the federal aggregator (plan-doc §3 Q-d). National-only -- per-state final-energy-consumption is NOT published by ICED. Fifth Pattern A-facet in P.1.C cohort, on the NEW `sector_fuel_pair` axis (introduced this PR). Compound suffix `{sector}-{fuel}` because the canonical-5 fuel_type axis cannot encode both dimensions in one indicator_id.",
    ),
    # --- P.1.C PR-Y (1) ------------------------------------------------
    "rbi_hbk_143_renewable_grid_capacity": (
        "OGL-IN-1.0",
        "silver",
        "archived-snapshot",
        False,
        "https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=22833",
        "RBI Handbook of Statistics on Indian States 2024-25 edition, Table 143: state-wise installed grid-connected renewable capacity (MW, end-March snapshot, 2007-2024). Combined wind + solar + small-hydro + biomass + waste-to-energy (no per-source split at this grain). Originating data: MoSPI Energy Statistics, Government of India. RBI republishes as the longitudinal anchor (silver / not-authority per Hans D33 + plan-doc §3 Q-d). National total ~10 GW in 2007 to ~144 GW in 2024 (14x). Telangana data from 2015 (state created 2014); Ladakh from 2023.",
    ),
}


def _build_energy_source_rows() -> tuple[SourceRow, ...]:
    rows: list[SourceRow] = []
    for nickname in SOURCE_NICKNAMES:
        producer, title, vintage = _TRIPLES[nickname]
        license_, tier, method, is_authority, url_main, notes = _BY_NICKNAME[nickname]
        rows.append(
            SourceRow(
                source_id=derive_source_id(producer, title, vintage),
                producer=producer,
                title=title,
                vintage=vintage,
                license=license_,  # type: ignore[arg-type]
                confidence_tier=tier,  # type: ignore[arg-type]
                is_issuing_authority=is_authority,
                verification_method=method,  # type: ignore[arg-type]
                url_main=url_main,
                citation_full=None,
                notes=notes,
            )
        )
    return tuple(rows)


ENERGY_SOURCES: tuple[SourceRow, ...] = _build_energy_source_rows()
ENERGY_SOURCE_ID_BY_NICKNAME: dict[str, str] = {
    nickname: row.source_id
    for nickname, row in zip(SOURCE_NICKNAMES, ENERGY_SOURCES, strict=True)
}


def upsert_energy_sources(con: duckdb.DuckDBPyConnection) -> int:
    """Idempotent scope-authoritative emit of the 17 energy citation rows
    into the in-memory ``sources`` DuckDB table.

    First DELETEs every row whose ``(producer, title)`` pair is owned by
    this seed (i.e. one of the 17 ``_TRIPLES`` keys); then INSERTs the
    17 current rows. This makes the seed structurally authoritative for
    its 17 ``(producer, title)`` slots: when a vintage rotates (as in
    ADR-0042 + the 5 ICED rotations of PR-B Commit 2), the previous
    ``source_id`` (derived from the previous vintage) is purged rather
    than orphaned. INSERT-OR-REPLACE alone would NOT achieve this
    because the new ``source_id`` hash differs from the old one.

    Caller is responsible for creating the ``sources`` table first and
    for emitting the table back to ``taxonomy/sources.parquet`` after.
    Returns the number of rows upserted (always 17 today: 7 P.1.A + 5
    P.1.B + 1 P.1.C PR-Q + 1 P.1.C PR-R + 1 P.1.C PR-S + 1 P.1.C PR-T +
    1 P.1.C PR-U).
    """
    owned_keys = sorted({(producer, title) for producer, title, _ in _TRIPLES.values()})
    for producer, title in owned_keys:
        con.execute(
            "DELETE FROM sources WHERE producer = ? AND title = ?",
            [producer, title],
        )
    upserted = 0
    for row in ENERGY_SOURCES:
        con.execute(
            """
            INSERT OR REPLACE INTO sources (
                source_id, producer, title, vintage,
                license, confidence_tier, is_issuing_authority,
                verification_method, url_main, citation_full, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row.source_id,
                row.producer,
                row.title,
                row.vintage,
                row.license,
                row.confidence_tier,
                row.is_issuing_authority,
                row.verification_method,
                row.url_main,
                row.citation_full,
                row.notes,
            ],
        )
        upserted += 1
    return upserted


# DDL identical to boundary_layers_seed.py's `sources` shape (mirrors
# source.schema.json). PRIMARY KEY on source_id makes INSERT OR REPLACE
# work cleanly across re-runs.
_SOURCES_DDL = """
CREATE TABLE sources (
    source_id VARCHAR PRIMARY KEY,
    producer VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    vintage VARCHAR NOT NULL,
    license VARCHAR NOT NULL,
    confidence_tier VARCHAR NOT NULL,
    is_issuing_authority BOOLEAN NOT NULL,
    verification_method VARCHAR NOT NULL,
    url_main VARCHAR,
    citation_full VARCHAR,
    notes VARCHAR
)
"""


def upsert_energy_sources_to_parquet(sources_parquet: Path) -> int:
    """Read-modify-write wrapper around :func:`upsert_energy_sources`.

    Opens an in-memory DuckDB, loads the existing
    ``taxonomy/sources.parquet`` (if any), upserts the 17 energy
    citation rows, writes the parquet back. Used by the
    ``emit-taxonomy`` orchestrator after office_holdings_seed has
    already written the wiki citation rows for the CM offices.

    Returns the number of rows upserted (always 17 today: 7 P.1.A + 5
    P.1.B + 1 P.1.C PR-Q + 1 P.1.C PR-R + 1 P.1.C PR-S + 1 P.1.C PR-T +
    1 P.1.C PR-U). Idempotent --
    re-running yields byte-identical output.
    """
    sources_parquet = Path(sources_parquet)
    sources_parquet.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(":memory:")
    try:
        con.execute(_SOURCES_DDL)
        if sources_parquet.is_file():
            con.execute(
                f"INSERT INTO sources SELECT * FROM read_parquet('{sources_parquet.as_posix()}')"
            )
        n = upsert_energy_sources(con)
        con.execute(
            f"""
            COPY (
                SELECT * FROM sources ORDER BY source_id
            ) TO '{sources_parquet.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()

    return n
