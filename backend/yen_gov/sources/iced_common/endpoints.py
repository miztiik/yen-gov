"""Catalogue of every ICED API endpoint observed in the public Angular bundle.

Recon method (2026-05-14): grep ``main.cb0bb1d44638969b.js`` (11 MB) for
every JS template literal of the form ``\\`${H}<path>\\``` (where ``H`` is
the bundle's API-host constant). 259 distinct paths returned. The literal
host strings are ``https://icedapi.niti.gov.in`` and
``https://icedapi.niti.gov.in/v1``.

The catalogue is split into three buckets per endpoint:

- **Parameter-free** (``params == ()``): a single GET reproduces the page
  data. ~140 endpoints. Safe to bulk-mirror with no per-endpoint setup.
- **Path-templated** (``path_params``): ``${i}/${m}/${u}`` style — the
  handler in the page resolves variables before calling. We do not yet
  enumerate these by default.
- **Query-templated** (``query_params``): ``?year=${i}&state=${m}`` —
  finite domains usually, but we still expand them per-page.

Each row carries:

    name        Stable Python identifier we use in code.
    path        API path verbatim from the bundle, with placeholders kept
                as ``${name}`` so the recon source is preserved.
    method      Always "GET" today; included for forward-compat.
    page_hint   The dashboard route that calls this endpoint, when known.
                Empty string when the binding wasn't found in the bundle.
    notes       Free-form one-liner — what we believe the response shape
                contains. Filled in incrementally as we mirror endpoints.

This is a *catalogue*, not a *contract*. The contract per endpoint is the
parser that consumes its decrypted JSON. Catalogue entries can be wrong
without causing artifact corruption — only parsers do that.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Endpoint:
    name: str
    path: str
    method: str = "GET"
    page_hint: str = ""
    notes: str = ""
    path_params: tuple[str, ...] = field(default_factory=tuple)
    query_params: tuple[str, ...] = field(default_factory=tuple)
    host_variant: str = "base"
    """Which API host serves this endpoint.

    The ICED bundle uses two hosts: the bare ``https://icedapi.niti.gov.in``
    (the default, ``"base"``) and the ``/v1`` sub-API
    (``https://icedapi.niti.gov.in/v1``, marked ``"v1"``). A handful of
    endpoints — e.g. ``capacity-metatable-data``, ``retired-capacity-plants``,
    ``plantPipelineInfo``, ``discoms``, ``homeMap`` — live only under v1.
    Consumers (the mirror, the client, parsers) pick the right host by
    inspecting this field; we deliberately do NOT bake ``/v1/`` into the
    ``path`` string so the path stays verbatim from the bundle.
    """


def _ep(
    name: str,
    path: str,
    page_hint: str = "",
    notes: str = "",
    *,
    host_variant: str = "base",
) -> Endpoint:
    """Helper: derive path_params / query_params from ``${...}`` placeholders."""
    import re as _re

    path_holes = tuple(_re.findall(r"\$\{([^}]+)\}", path.split("?")[0]))
    if "?" in path:
        query_holes = tuple(_re.findall(r"\$\{([^}]+)\}", path.split("?", 1)[1]))
    else:
        query_holes = ()
    return Endpoint(
        name=name,
        path=path,
        method="GET",
        page_hint=page_hint,
        notes=notes,
        path_params=path_holes,
        query_params=query_holes,
        host_variant=host_variant,
    )


# Subset of the 259 endpoints — the ones we have prioritised for ingest in
# the first wave (or that are useful for shape recon). The full 259-item
# list lives in the ADR (docs/architecture/decisions/0028-iced-api.md);
# this module only enumerates the ones we have either bound to a parser
# or actively reconned.
ENDPOINT_CATALOGUE: tuple[Endpoint, ...] = (
    # ----- Metadata ----------------------------------------------------
    _ep("website_last_updated", "/websiteLastUpdated", page_hint="(global footer)",
        notes="Returns latest data refresh timestamp the site advertises."),
    _ep("chart_title", "/chart-title", page_hint="(global)",
        notes="296 KB metadata blob: every chart's title, source attribution, footnote."),
    _ep("data_cards", "/data-cards", page_hint="(homepage)",
        notes="Headline KPI tiles shown on the home dashboard."),
    _ep("infographics", "/infographics", page_hint="(global)",
        notes="Static infographic listing."),
    # `distinct_values` was in the 2026-05-14 recon but has no parser
    # consumer and rotated away (400 on /distinct-values, 404 elsewhere)
    # by 2026-05-17. Deleted from catalogue — re-recon the bundle if a
    # dropdown-population use-case emerges.
    _ep("home_map", "/homeMap", page_hint="(homepage)",
        notes="Home-page map markers — high-level country-wide view.",
        host_variant="v1"),

    # ----- Climate / GHG -----------------------------------------------
    _ep("ghg_economy_wide", "/climate-environment/ghg-emissions/economy-wide-emission",
        page_hint="/climate-and-environment/ghg-emissions/economy-wide-emission",
        notes="GHG emissions, all sectors, full historical series."),
    _ep("ghg_energy", "/climate-environment/ghg-emissions/energy",
        page_hint="/climate-and-environment/ghg-emissions/agriculture",
        notes="Despite the name, returns the FULL GHG dataset including agriculture sub-sectors. ~150 KB JSON."),
    _ep("ghg_static_values", "/climate-environment/ghg-emissions/ghg-static-values",
        page_hint="(filters)",
        notes="Reference values used by the GHG charts (totals, baselines)."),

    # ----- Economy & demography ---------------------------------------
    _ep("economy_per_capita_consumption",
        "/economy-demography/key-economic-indicators/per-capita-consumption",
        page_hint="/economy-and-demography/key-economic-indicators/socio-economic",
        notes="Per-capita private final consumption expenditure. State-wise + All-India, 1971→2024."),
    _ep("economy_per_capita_income",
        "/economy-demography/key-economic-indicators/per-capita-income",
        page_hint="/economy-and-demography/key-economic-indicators/socio-economic",
        notes="Per-capita NSDP, current prices. State-wise, 2004-05→2023-24."),
    _ep("economy_per_capita_income_map",
        "/economy-demography/key-economic-indicators/per-capita-income-map",
        page_hint="/economy-and-demography/key-economic-indicators/socio-economic",
        notes="Per-capita NSDP rendered as choropleth-ready state map values."),
    _ep("economy_gdp_trend",
        "/economy-demography/key-economic-indicators/gdp-trend",
        page_hint="/economy-and-demography/key-economic-indicators/socio-economic",
        notes="GDP trend (national, current + constant prices)."),
    _ep("economy_gva_trend",
        "/economy-demography/key-economic-indicators/gva-trend",
        page_hint="/economy-and-demography/key-economic-indicators/socio-economic",
        notes="GVA trend (national, sectoral split)."),
    _ep("economy_hdi_map",
        "/economy-demography/key-economic-indicators/hdi-map",
        page_hint="/economy-and-demography/key-economic-indicators/socio-economic",
        notes="Sub-national HDI, choropleth-ready."),
    _ep("economy_industrial_production",
        "/economy-demography/key-economic-indicators/industrial-production",
        page_hint="/economy-and-demography/key-economic-indicators/socio-economic",
        notes="IIP (Index of Industrial Production) series."),
    _ep("economy_balance_trendline",
        "/economy-demography/key-economic-indicators/balance-trendline",
        page_hint="/economy-and-demography/key-economic-indicators/socio-economic",
        notes="Trade / current-account balance trendline."),
    _ep("demography_actual",
        "/economy-demography/demography/demographyActual",
        page_hint="/economy-and-demography/demography",
        notes="Actual demography figures (population pyramid, age distribution)."),

    # ----- Power: capacity & generation -------------------------------
    # `power_generation` (/energy/generation), `power_plants_listing`
    # (/powerPlantsListing) and `plant_list_by_source` (/plantListBySource)
    # were in the 2026-05-14 recon but had rotated away (all 404 on both
    # base and /v1 hosts) by 2026-05-17 and no parser bound them. Deleted
    # from catalogue — re-recon the bundle if these page-bindings come
    # back. Per-source generation is already covered by power_statistics's
    # `data[].generation` field; the dedicated endpoint is redundant.
    _ep("power_statistics", "/energy/powerStatistics",
        page_hint="(global)",
        notes="Power-sector summary statistics block."),
    _ep("retired_capacity_plants", "/retired-capacity-plants",
        page_hint="/energy/electricity/capacity/retired",
        notes="Retired thermal plants with state, source, capacity, year-of-retirement. "
              "Returns PLAINTEXT JSON (not the encrypted envelope) — IcedClient "
              "raises ICEDShapeError; consumer must `requests.get` directly or "
              "the client must learn the plaintext-v1 shape (see 2026-05-17 mirror).",
        host_variant="v1"),
    _ep("plant_pipeline_info", "/plantPipelineInfo",
        page_hint="/energy/electricity/capacity/upcoming",
        notes="Under-construction / pipeline plant capacity additions.",
        host_variant="v1"),
    _ep("capacity_metatable", "/capacity-metatable-data",
        page_hint="/energy/electricity/capacity",
        notes="Tabular capacity overview by state × source × year. "
              "Returns PLAINTEXT JSON (not the encrypted envelope) — IcedClient "
              "raises ICEDShapeError; consumer must `requests.get` directly or "
              "the client must learn the plaintext-v1 shape (see 2026-05-17 mirror).",
        host_variant="v1"),

    # ----- Power: consumer / discom -----------------------------------
    _ep("discoms_list", "/discoms",
        page_hint="/energy/electricity/distribution",
        notes="Master list of distribution utilities.",
        host_variant="v1"),

    # ----- Daily / monthly granular series ----------------------------
    _ep("daily_peak_demand_last_30",
        "/dailyPeakDemand/last30Days",
        page_hint="/energy/electricity/distribution/peak-demand",
        notes="Daily peak demand for last 30 days, all India."),

    # ----- Climate / air quality --------------------------------------
    # Recon 2026-05-15 via tools/iced_full_triage.py against the public
    # /climate-and-environment/environment/air-quality dashboard. Eight
    # endpoints respond OK; registered here as catalogue-only (no parser
    # binds them yet). ICED is a re-publisher of CPCB NAMP annual-mean
    # station files (the `file` column on aqi_map_markers points to
    # `data/AQ_CPCB_UTF8/AQM_<year>_Annual_mean.csv`); any artifact built
    # from these endpoints MUST list both the ICED API URL and the CPCB
    # upstream URL in its `sources` array (Hans, 2026-05-15).
    _ep("aq_aqi_map_markers",
        "/climate-environment/environment/air-quality/aqi-map-markers",
        page_hint="/climate-and-environment/environment/air-quality",
        notes="NAMP station-year rows: 8453 rows × {state, city, location, "
              "lat, lng, year, so2, no2, pm10, pm25, file}. SO2/NO2/PM10 "
              "cover 2010-2023 (14y); PM2.5 starts 2014 (9y). 37 states, "
              "532 cities, 1837 unique stations. Source-of-record for the "
              "PM2.5 indicator."),
    _ep("aq_aqm_cities",
        "/climate-environment/aqmCityWise/aqm-cities",
        page_hint="/climate-and-environment/environment/air-quality",
        notes="ICED's pre-aggregated city-year rollup (374 city-year rows). "
              "Use as a cross-check fixture only; do NOT use as the source "
              "of truth — methodology is opaque (see Fowler 2026-05-15)."),
    _ep("aq_fgd",
        "/climate-environment/environment/air-quality/fgd",
        page_hint="/climate-and-environment/environment/air-quality",
        notes="Coal thermal-plant flue-gas-desulphurisation compliance: 602 "
              "plant-units × {developer, plantName, state, unitNo, capacity, "
              "fgdStatus, fgdGroup, fgdDate}. Tracks MoEFCC's 2015 directive "
              "(deadline since pushed 2017→2027). First AQ indicator we ship."),
    _ep("aq_co2_emission",
        "/climate-environment/environment/air-quality/co2Emission",
        page_hint="/climate-and-environment/environment/air-quality",
        notes="Power-sector CO2 emissions, sector × FY. Distinct from the "
              "GHG endpoints (which are economy-wide MoEFCC inventories)."),
    _ep("aq_cpcb_dates",
        "/climate-environment/environment/air-quality/cpbc-dates",
        page_hint="/climate-and-environment/environment/air-quality",
        notes="Metadata only: vintage of the CPCB NAMP files ICED is "
              "mirroring. Use to populate methodology_vintage / data_as_of."),
    _ep("aq_sentinel_dates",
        "/climate-environment/environment/air-quality/sentinel-dates",
        page_hint="/climate-and-environment/environment/air-quality",
        notes="Metadata only: vintage of the Sentinel satellite layers."),
    _ep("aq_power_plant_list",
        "/climate-environment/environment/air-quality/power-plant-list",
        page_hint="/climate-and-environment/environment/air-quality",
        notes="322 power plants with geometry. AQ-specific subset of ICED's "
              "plant registry; the formerly-catalogued `power_plants_listing` "
              "endpoint rotated away in 2026-05-17 recon so this is now the "
              "only plant-list endpoint we use."),
    _ep("aq_coal_plant_impact",
        "/analytics/aqi-impact-due-to-coal-plants-list",
        page_hint="/climate-and-environment/environment/air-quality",
        notes="951 plant rows from ICED's modelled AQI-impact-of-coal-plants "
              "analytic. Modelled, not measured — treat with the same "
              "caution as any model output before binding to an indicator."),

    # ----- Wave-2 catalogue expansion (2026-05-17) ---------------------
    # Sourced from .runtime/iced_recon/full_triage_20260515073024.md
    # ("ok new (unbound)" list — 94 endpoints responded OK but no parser
    # was bound). The 20 below were selected against the same priority
    # criteria the doc lists in High-priority surfaces §: state-level
    # coverage, distinct topical territory (not just more power), and
    # year+state facet keys so they're citizen-renderable. Catalogue-only
    # for now — adding a parser is a separate per-indicator commit.
    # See docs/architecture/backend/sources-iced-api.md.

    # Energy: aggregate consumption / supply ---------------------------
    _ep("energy_sector_wise_consumption",
        "/energy/sectorWiseEnergyConsumption",
        page_hint="/energy/sources-and-end-use",
        notes="Sector × source × year, 360 rows / 33 KB. End-use energy "
              "consumption by sector (industry, transport, agriculture, "
              "residential, commercial). Unblocks ephemeral candidate #19 "
              "in notes/ephemeral-datasets-triage-2026-05-14.md ("
              "sectorwise_energy_consumption). MoSPI Energy Statistics."),
    _ep("energy_source_wise_supply",
        "/energy/sourceWiseEnergySupply",
        page_hint="/energy/sources-and-end-use",
        notes="Source × year, 120 rows / 8 KB. National primary energy "
              "supply by source (coal, oil, gas, nuclear, hydro, RE). "
              "Companion to sector_wise_consumption for an energy-balance "
              "view. Country-entity only — needs Phase 4 renderer."),

    # Power: state-level purchase quantum & cost -----------------------
    _ep("quantum_state_year",
        "/quantum-state-year",
        page_hint="/energy/electricity/distribution/power-purchase",
        notes="State × source × year, 2700 rows / 174 KB. Power purchased "
              "(quantum, MU) by source per state per year. Citizen "
              "question: where does my state's electricity come from?"),
    _ep("statelevel_power_purchase_quantum_and_cost",
        "/statelevel-power-purchase-quantum-and-cost",
        page_hint="/energy/electricity/distribution/power-purchase",
        notes="State × source × year, 2788 rows / 516 KB. Companion to "
              "quantum_state_year adding cost (₹/kWh). Lets a citizen "
              "ask: what does my state pay for each source it buys?"),

    # Power: discom operations ----------------------------------------
    _ep("discom_operational_performance_states",
        "/energy/electricity/distribution/operationalPerformanceStates",
        page_hint="/energy/electricity/distribution",
        notes="State × FY × category × type, 2656 rows / 427 KB. Discom "
              "operational performance (AT&C losses, ACS-ARR gap, billing "
              "efficiency). Pairs with the existing UDAY/RPO indicators."),
    _ep("discom_rpo_compliance",
        "/energy/electricity/distribution/rpo",
        page_hint="/energy/electricity/distribution/rpo",
        notes="State × FY, 106 rows / 27 KB. Renewable Purchase Obligation "
              "compliance by state and year. Citizen question: is my "
              "state meeting its mandatory RE-buying targets?"),

    # Power: transmission infrastructure ------------------------------
    _ep("transmission_substation_list",
        "/energy/electricity/transmission/substation-list",
        page_hint="/energy/electricity/transmission",
        notes="Sector × type, 2743 rows / 708 KB. National substation "
              "registry with geolocation. Useful for the eventual "
              "infrastructure layer on the map."),

    # Power: captive generation ---------------------------------------
    _ep("captive_power_industry",
        "/energy/electricity/captive-power/captive-power-industry",
        page_hint="/energy/electricity/captive-power",
        notes="State × industry × year, 15048 rows / 2.0 MB. Captive "
              "(self-generated) power capacity by industry per state. "
              "The 'shadow' grid that doesn't show up in DISCOM stats."),

    # Climate: biodiversity & climate variability ---------------------
    _ep("forest_cover_by_state",
        "/climate-environment/bio-diversity/forest-cover-by-state",
        page_hint="/climate-and-environment/biodiversity",
        notes="State × year, 330 rows / 54 KB. Forest cover by state per "
              "ISFR (India State of Forest Report). NEW topic for yen-gov "
              "(no environment/forest indicator yet). FSI biannual cadence."),
    _ep("climate_rainfall_district",
        "/climate-environment/climate-variability/rainfall",
        page_hint="/climate-and-environment/climate-variability",
        notes="State × district × type, 563 rows / 62 KB. Rainfall data "
              "at district granularity. NEW topic. IMD-sourced."),
    _ep("climate_temperature_annual",
        "/climate-environment/climate-variability/temperatureAnnual",
        page_hint="/climate-and-environment/climate-variability",
        notes="Year, 495 rows / 42 KB. National annual mean temperature "
              "anomaly series. Country-entity (needs Phase 4 renderer)."),
    _ep("land_use_by_state",
        "/climate-environment/environment/land",
        page_hint="/climate-and-environment/environment/land",
        notes="State × year, 2109 rows / 242 KB. Land-use classification "
              "(forest, cultivable waste, non-agri, etc.) per state. "
              "MoA Land Use Statistics."),

    # Fuel sources: coal ---------------------------------------------
    _ep("coal_consumption_domestic_state",
        "/energy/fuel-sources/coal/consumption-domestic-state",
        page_hint="/energy/fuel-sources/coal",
        notes="State × year × source × type, 936 rows / 89 KB. Domestic "
              "coal consumption by state (washed/raw, coking/non-coking)."),
    _ep("coal_consumption_domestic_sector_wise",
        "/energy/fuel-sources/coal/consumption-domestic-sector-wise",
        page_hint="/energy/fuel-sources/coal",
        notes="Sector × source × state × type × year, 3977 rows / 480 KB. "
              "Coal consumption split by end-use sector (power, steel, "
              "cement, sponge iron, etc.). Companion to the state view."),

    # Fuel sources: oil ----------------------------------------------
    _ep("oil_consumption_state_product_trend",
        "/energy/fuel-sources/oil/consumptionStateProductTrend",
        page_hint="/energy/fuel-sources/oil",
        notes="State × year × source × type × region, 3683 rows / 621 KB. "
              "State-level oil-product consumption (HSD, MS, LPG, ATF). "
              "PPAC-sourced."),

    # Fuel sources: RE potential (3 — finishes the renewable-potential set) -
    _ep("solar_potential_by_state",
        "/energy/fuel-sources/solar/potential",
        page_hint="/energy/fuel-sources/renewables/solar",
        notes="State × source × region × year, 67 rows / 12 KB. Solar "
              "potential by state (MNRE/NREL). Unblocks ephemeral "
              "candidate #16 (re_potential) in the triage doc."),
    _ep("wind_potential_by_state",
        "/energy/fuel-sources/wind/potential",
        page_hint="/energy/fuel-sources/renewables/wind",
        notes="State × source × region × year, 67 rows / 12 KB. Wind "
              "potential at multiple hub heights (50m/80m/100m/120m). "
              "Companion to solar_potential_by_state."),
    _ep("bio_energy_potential_by_state",
        "/energy/fuel-sources/bio-energy/potential",
        page_hint="/energy/fuel-sources/renewables/bio-energy",
        notes="State × source × region × year, 66 rows / 12 KB. Biomass "
              "and bagasse cogen potential by state."),

    # Transport / EV -------------------------------------------------
    _ep("ice_ev_vahan",
        "/analytics/ice-ev-vahan",
        page_hint="/transport/electric-vehicles",
        notes="Large blob (~6.3 MB). VAHAN-sourced ICE vs EV registration "
              "trends. Unblocks ephemeral candidate #5 (ev_trend). "
              "Filter aggressively before emitting — raw payload is huge."),

    # Cross-cutting analytic -----------------------------------------
    _ep("per_capita_gdp_vs_consumption",
        "/analytics/per-capita-gdp-vs-consumption",
        page_hint="/economy-and-demography/key-economic-indicators/socio-economic",
        notes="State × year/fyear, 432 rows / 55 KB. Pre-computed "
              "scatter: per-capita GDP vs per-capita consumption. Useful "
              "as a cross-check fixture for our independently-computed "
              "per-capita NSDP and PFCE artifacts."),
)


def by_name(name: str) -> Endpoint:
    """Look up one endpoint in :data:`ENDPOINT_CATALOGUE` by ``name``.

    Raises :class:`KeyError` with all known names listed if the lookup
    misses — easier to debug typos than ``None``.
    """
    for ep in ENDPOINT_CATALOGUE:
        if ep.name == name:
            return ep
    raise KeyError(
        f"unknown ICED endpoint name {name!r}; known: "
        f"{sorted(ep.name for ep in ENDPOINT_CATALOGUE)}"
    )


def parameter_free() -> tuple[Endpoint, ...]:
    """Endpoints with no path or query placeholders. Safe to bulk-mirror."""
    return tuple(
        ep for ep in ENDPOINT_CATALOGUE
        if not ep.path_params and not ep.query_params
    )
