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


def _ep(name: str, path: str, page_hint: str = "", notes: str = "") -> Endpoint:
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
    _ep("distinct_values", "/distinct-values", page_hint="(filters)",
        notes="Distinct value catalogues for dropdowns."),
    _ep("home_map", "/homeMap", page_hint="(homepage)",
        notes="Home-page map markers — high-level country-wide view."),

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
    _ep("power_generation", "/energy/generation", page_hint="/energy/electricity/capacity",
        notes="National generation by source, time series."),
    _ep("power_statistics", "/energy/powerStatistics",
        page_hint="(global)",
        notes="Power-sector summary statistics block."),
    _ep("retired_capacity_plants", "/retired-capacity-plants",
        page_hint="/energy/electricity/capacity/retired",
        notes="Retired thermal plants with state, source, capacity, year-of-retirement."),
    _ep("plant_pipeline_info", "/plantPipelineInfo",
        page_hint="/energy/electricity/capacity/upcoming",
        notes="Under-construction / pipeline plant capacity additions."),
    _ep("power_plants_listing", "/powerPlantsListing",
        page_hint="/energy/electricity/power-plant-details",
        notes="Master plant list (search-friendly subset of plant registry)."),
    _ep("plant_list_by_source", "/plantListBySource",
        page_hint="/energy/electricity/power-plant-details",
        notes="Plant list grouped by primary energy source."),
    _ep("capacity_metatable", "/capacity-metatable-data",
        page_hint="/energy/electricity/capacity",
        notes="Tabular capacity overview by state × source × year."),

    # ----- Power: consumer / discom -----------------------------------
    _ep("discoms_list", "/discoms",
        page_hint="/energy/electricity/distribution",
        notes="Master list of distribution utilities."),

    # ----- Daily / monthly granular series ----------------------------
    _ep("daily_peak_demand_last_30",
        "/dailyPeakDemand/last30Days",
        page_hint="/energy/electricity/distribution/peak-demand",
        notes="Daily peak demand for last 30 days, all India."),
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
