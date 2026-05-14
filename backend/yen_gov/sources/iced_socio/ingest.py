"""ICED socio-economic adapter — fetch + emit five indicator artifacts.

Per Hans (Governance) triage 2026-05-14:

* ``economy/state_per_capita_nsdp_constant_2011_12_inr``  — Priority 1
* ``human_development/state_hdi``                          — Priority 2
* ``economy/state_per_capita_consumption_inr``             — Priority 3
* ``demography/state_population_by_sex_count``             — Priority 5
* ``environment/india_ghg_emissions_mtco2e_by_sector``     — Priority 6

The current-price NSDP indicator (Hans Priority 4) ships separately as
``economy/state_per_capita_nsdp_current_inr`` from the
state-wise-deep-dive adapter; we do not re-emit it here.

This module is the orchestrator only — fetching via
:class:`IcedClient`, calling pure parsers from :mod:`.parsers`, building
schema-conformant payloads, and writing through the shared
``write_artifact`` chokepoint. No fetching or schema work in
``parsers.py``; no parsing or HTTP in this file.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.iced_common import IcedClient

from .parsers import (
    parse_demography_by_sex,
    parse_ghg_economy_wide,
    parse_hdi_map,
    parse_per_capita_consumption,
    parse_per_capita_income,
)


@dataclass(frozen=True)
class IndicatorEmitResult:
    indicator_id: str
    artifact_path: Path
    row_count: int
    time_min: str
    time_max: str
    skipped_unmapped: int


@dataclass(frozen=True)
class IngestSummary:
    fetched_at: datetime
    results: tuple[IndicatorEmitResult, ...]


# ---------------------------------------------------------------------------
# License — ICED publishes under GoI-OpenData (matches existing artifacts).
# ---------------------------------------------------------------------------

LICENSE_ICED = {
    "id": "GoI-OpenData",
    "name": "Government of India Open Data License",
    "url": "https://www.data.gov.in/government-open-data-license-india",
    "redistributable": True,
}

ICED_AUTHORITY = "NITI Aayog (India Climate & Energy Dashboard)"

# Per CLAUDE.md §12 + ADR-0002, sources[].url is the EXACT URL the pipeline
# fetched. The dashboard page URL goes in `sources[].name` (human-readable
# attribution) only — never in `url`.
API_HOST = "https://icedapi.niti.gov.in"


# ---------------------------------------------------------------------------
# Indicator catalogue
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _IndicatorBuild:
    """Static metadata for one indicator artifact emitted by this adapter."""

    out_topic: str
    out_leaf: str
    indicator: dict[str, Any]                 # schema's `indicator` block
    coverage_spatial: str
    coverage_admin_level: str | None
    api_path: str                             # endpoint we fetch (relative)
    page_url: str                             # human-readable dashboard URL
    source_name: str                          # Source[].name
    builder: Callable[..., Any]               # parser + selector


def _per_capita_constant_meta() -> _IndicatorBuild:
    return _IndicatorBuild(
        out_topic="economy",
        out_leaf="state_per_capita_nsdp_constant_2011_12_inr",
        indicator={
            "id": "economy/state_per_capita_nsdp_constant_2011_12_inr",
            "title": "State per-capita NSDP, inflation-adjusted (₹ per person per year)",
            "description": (
                "Net State Domestic Product per person at constant 2011-12 prices. "
                "This is the inflation-adjusted measure of state income — the only "
                "honest way to ask 'is my state catching up or falling behind' "
                "across years. The current-price companion indicator "
                "(state_per_capita_nsdp_current_inr) gives the same data without "
                "inflation adjustment, useful only for comparing states within a "
                "single year."
            ),
            "entity_kind": "state",
            "time_grain": "fiscal_year",
            "value_kind": "currency",
            "direction": "higher_is_better",
            "scale_hint": "linear",
            "unit": "INR",
            "icon": "trending-up",
            "attribution_geography": "where_resident",
            "comparability": "comparable_across_states",
            "implementing_authority": "joint",
            "methodology_vintage": "NSDP base 2011-12 (CSO re-spliced from 2004-05 base around 2014)",
            "notes": (
                "Adjusted for inflation, base year 2011-12. CSO re-spliced the series "
                "from a 2004-05 base around 2014; treat the join across that boundary "
                "as approximate. Andhra Pradesh figures before 2014 include the area "
                "now in Telangana; Jammu & Kashmir figures before 2019 include Ladakh."
            ),
            "series_breaks": [
                {"at_time": "2011-04", "kind": "rebase",
                 "note": "CSO re-based NSDP series from 2004-05 to 2011-12 base year."},
                {"at_time": "2014-04", "kind": "coverage_change",
                 "note": "Telangana bifurcated from Andhra Pradesh on 2014-06-02; pre-2014 AP rows include Telangana."},
                {"at_time": "2019-04", "kind": "coverage_change",
                 "note": "J&K bifurcated into J&K (UT) and Ladakh (UT) on 2019-10-31; pre-2019 J&K rows include Ladakh."},
            ],
        },
        coverage_spatial="India (states + UTs)",
        coverage_admin_level="state",
        api_path="/economy-demography/key-economic-indicators/per-capita-income",
        page_url="https://iced.niti.gov.in/economy-and-demography/key-economic-indicators/socio-economic",
        source_name="ICED — Per Capita Income (NITI Aayog)",
        builder=lambda d: parse_per_capita_income(d).constant,
    )


def _hdi_meta() -> _IndicatorBuild:
    return _IndicatorBuild(
        out_topic="human_development",
        out_leaf="state_hdi",
        indicator={
            "id": "human_development/state_hdi",
            "title": "Human Development Index (income + health + education, 0–1)",
            "description": (
                "Composite score combining life expectancy, years of schooling, and "
                "per-capita income, scaled 0 (lowest) to 1 (highest). Lets a citizen "
                "see two states in the same frame on something other than money — "
                "Kerala and Bihar can have similar incomes and very different HDI "
                "scores because of differences in health and schooling outcomes."
            ),
            "entity_kind": "state",
            "time_grain": "fiscal_year",
            "value_kind": "index",
            "direction": "higher_is_better",
            "scale_hint": "linear",
            "unit": "index (0–1)",
            "icon": "users",
            "attribution_geography": "where_resident",
            "comparability": "comparable_across_states",
            "implementing_authority": "joint",
            "methodology_vintage": "NITI Aayog SDG India Index sub-national HDI",
            "notes": (
                "Sub-national HDI computed by NITI Aayog using Indian survey inputs "
                "(NFHS for health, NSS / PLFS for education and income). Not directly "
                "comparable to UNDP's national HDI for India — the input series differ. "
                "ICED publishes only a small number of snapshot years; treat this as "
                "a position, not a trajectory."
            ),
        },
        coverage_spatial="India (states + UTs)",
        coverage_admin_level="state",
        api_path="/economy-demography/key-economic-indicators/hdi-map",
        page_url="https://iced.niti.gov.in/economy-and-demography/key-economic-indicators/socio-economic",
        source_name="ICED — Human Development Index map (NITI Aayog)",
        builder=lambda d: parse_hdi_map(d)[0],
    )


def _per_capita_consumption_meta() -> _IndicatorBuild:
    return _IndicatorBuild(
        out_topic="economy",
        out_leaf="state_per_capita_consumption_inr",
        indicator={
            "id": "economy/state_per_capita_consumption_inr",
            "title": "State per-capita private consumption (₹ per person per year)",
            "description": (
                "Per-capita Private Final Consumption Expenditure (PFCE) at the "
                "state level — what an average resident spends per year on goods "
                "and services. The single best welfare proxy that does not require "
                "an NSS round; complements per-capita income by capturing what "
                "households actually spend (income − savings + remittances)."
            ),
            "entity_kind": "state",
            "time_grain": "fiscal_year",
            "value_kind": "currency",
            "direction": "higher_is_better",
            "scale_hint": "linear",
            "unit": "INR",
            "icon": "shopping-bag",
            "attribution_geography": "where_resident",
            "comparability": "comparable_across_states",
            "implementing_authority": "joint",
            "methodology_vintage": "National Accounts PFCE (CSO modelled to state level)",
            "notes": (
                "This is National-Accounts PFCE per capita — modelled by CSO from "
                "national totals down to state level. Different from (and typically "
                "higher than) NSS Household Consumption Expenditure surveys; both "
                "are valid for different questions. Andhra Pradesh figures before "
                "2014 include Telangana; J&K before 2019 includes Ladakh."
            ),
            "series_breaks": [
                {"at_time": "2014-04", "kind": "coverage_change",
                 "note": "Telangana bifurcated from Andhra Pradesh; pre-2014 AP includes Telangana."},
                {"at_time": "2019-04", "kind": "coverage_change",
                 "note": "Ladakh bifurcated from J&K; pre-2019 J&K includes Ladakh."},
            ],
        },
        coverage_spatial="India (states + UTs)",
        coverage_admin_level="state",
        api_path="/economy-demography/key-economic-indicators/per-capita-consumption",
        page_url="https://iced.niti.gov.in/economy-and-demography/key-economic-indicators/socio-economic",
        source_name="ICED — Per Capita Consumption (NITI Aayog)",
        builder=lambda d: parse_per_capita_consumption(d)[0],
    )


def _population_by_sex_meta() -> _IndicatorBuild:
    return _IndicatorBuild(
        out_topic="demography",
        out_leaf="state_population_by_sex_count",
        indicator={
            "id": "demography/state_population_by_sex_count",
            "title": "State population by sex, decennial Census (number of people)",
            "description": (
                "State-level resident population at each decennial Census, "
                "faceted into Male and Female. Six Census points 1961, 1971, "
                "1981, 1991, 2001, 2011. India has not conducted a Census "
                "since 2011, so the series stops there — no projected values "
                "are mixed in. Lets the chart compute sex-ratio (females per "
                "1000 males) downstream, one of the few governance outcomes "
                "that is unambiguous, sub-national, and culturally diagnostic."
            ),
            "entity_kind": "state",
            "time_grain": "year",
            "value_kind": "count",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "people",
            "icon": "users",
            "attribution_geography": "where_resident",
            "comparability": "comparable_across_states",
            "implementing_authority": "centre",
            "methodology_vintage": "Census of India (decennial enumeration)",
            "chart_type": "stacked-trend",
            "default_mode": "absolute",
            "notes": (
                "Decennial Census enumerations only — no inter- or post-censal "
                "projections in this series. Census 2021 was postponed and has "
                "not yet been conducted, so the most recent point is 2011 — over "
                "a decade old. Pre-2014 Andhra Pradesh rows include the area now "
                "in Telangana; pre-2019 J&K rows include Ladakh."
            ),
            "series_breaks": [
                {"at_time": "2011", "kind": "frame_change",
                 "note": "Last completed Census of India was 2011; Census 2021 was postponed."},
            ],
        },
        coverage_spatial="India (states + UTs)",
        coverage_admin_level="state",
        api_path="/economy-demography/demography/demographyActual",
        page_url="https://iced.niti.gov.in/economy-and-demography/demography",
        source_name="ICED — Demography (NITI Aayog)",
        builder=lambda d: parse_demography_by_sex(d)[0],
    )


def _ghg_economy_wide_meta() -> _IndicatorBuild:
    return _IndicatorBuild(
        out_topic="environment",
        out_leaf="india_ghg_emissions_mtco2e_by_sector",
        indicator={
            "id": "environment/india_ghg_emissions_mtco2e_by_sector",
            "title": "India's greenhouse-gas emissions by sector (Gg CO₂-equivalent)",
            "description": (
                "National greenhouse-gas emissions broken down by sector "
                "(Energy, Industrial Processes & Product Use, Agriculture, "
                "Land-Use / Land-Use Change & Forestry, Waste). Reported as "
                "Gigagrams of CO₂-equivalent per year (1 Gg = 1000 tonnes; "
                "1000 Gg = 1 Mt). LULUCF is shown net (forest absorption "
                "minus deforestation) and can therefore be negative — that "
                "is real, not an error."
            ),
            "entity_kind": "country",
            "time_grain": "year",
            "value_kind": "raw",
            "direction": "lower_is_better",
            "scale_hint": "linear",
            "unit": "Gg CO2e",
            "icon": "cloud",
            "attribution_geography": "where_produced",
            "comparability": "not_comparable_across_states",
            "implementing_authority": "centre",
            "methodology_vintage": "IPCC 2006 guidelines (BUR submissions, MoEFCC)",
            "chart_type": "stacked-trend",
            "default_mode": "absolute",
            "notes": (
                "National total only — sub-national emissions accounting does not "
                "exist for India yet. Reported in India's Biennial Update Report (BUR) "
                "submissions to UNFCCC. Per-capita emissions are roughly a quarter of "
                "the OECD average; absolute totals reflect a population of 1.4 billion."
            ),
        },
        coverage_spatial="India (national)",
        coverage_admin_level=None,
        api_path="/climate-environment/ghg-emissions/economy-wide-emission",
        page_url="https://iced.niti.gov.in/climate-and-environment/ghg-emissions/economy-wide-emission",
        source_name="ICED — Economy-wide GHG Emissions (NITI Aayog)",
        builder=lambda d: parse_ghg_economy_wide(d),
    )


def _all_builds() -> tuple[_IndicatorBuild, ...]:
    return (
        _per_capita_constant_meta(),
        _hdi_meta(),
        _per_capita_consumption_meta(),
        _population_by_sex_meta(),
        _ghg_economy_wide_meta(),
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def ingest_iced_socio(
    *,
    repo_root: Path,
    client: IcedClient | None = None,
) -> IngestSummary:
    """Fetch all five socio-economic ICED endpoints and emit indicator artifacts.

    Args:
        repo_root: parent of ``datasets/`` and ``.runtime/``.
        client: pre-built :class:`IcedClient`. Defaults to a fresh one
            rooted at ``repo_root``.
    """
    if client is None:
        client = IcedClient(runtime_root=repo_root)

    builds = _all_builds()
    out_root = repo_root / "datasets" / "indicators" / "in"

    fetched_at_overall = datetime.now(timezone.utc)
    results: list[IndicatorEmitResult] = []

    for b in builds:
        resp = client.get(b.api_path)
        rows = b.builder(resp.decrypted)
        if not rows:
            raise RuntimeError(
                f"indicator {b.indicator['id']!r}: parser returned 0 rows; "
                f"check {b.api_path} response shape."
            )

        coverage = {
            "spatial": b.coverage_spatial,
            "temporal": _temporal_span(rows),
            "admin_level": b.coverage_admin_level,
        }

        payload = {
            "license": LICENSE_ICED,
            "coverage": coverage,
            "indicator": b.indicator,
            "rows": rows,
        }

        sources = [Source(url=f"{API_HOST}{b.api_path}", fetched_at=resp.fetched_at)]

        out_path = out_root / b.out_topic / f"{b.out_leaf}.json"
        write_artifact(
            path=out_path,
            schema_id=schema_id("indicator.schema.json"),
            schema_version=schema_version("indicator.schema.json"),
            payload=payload,
            sources=sources,
            schema_for_validation=schema_doc("indicator.schema.json"),
        )

        results.append(
            IndicatorEmitResult(
                indicator_id=b.indicator["id"],
                artifact_path=out_path,
                row_count=len(rows),
                time_min=min(r["time"] for r in rows),
                time_max=max(r["time"] for r in rows),
                skipped_unmapped=0,
            )
        )

    return IngestSummary(fetched_at=fetched_at_overall, results=tuple(results))


def _temporal_span(rows: list[dict[str, Any]]) -> str:
    times = sorted({r["time"] for r in rows})
    if not times:
        return "(empty)"
    if times[0] == times[-1]:
        return times[0]
    return f"{times[0]}..{times[-1]}"
