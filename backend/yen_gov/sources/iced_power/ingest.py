"""Orchestrator for the ICED power-sector adapter.

Fetches each upstream once (some live on the bare host, some under
``/v1``; a couple are AES-encrypted, two are JSON-direct), routes each
response through the matching pure parser in :mod:`.parsers`, and emits
five schema-conformant indicator artifacts under
``datasets/indicators/in/energy/``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.iced_common import IcedClient

from .parsers import (
    parse_capacity_metatable,
    parse_pipeline,
    parse_power_statistics,
    parse_retired_capacity,
)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


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
# Constants
# ---------------------------------------------------------------------------


LICENSE_ICED = {
    "id": "GoI-OpenData",
    "name": "Government of India Open Data License",
    "url": "https://www.data.gov.in/government-open-data-license-india",
    "redistributable": True,
}

ICED_AUTHORITY = "NITI Aayog (India Climate & Energy Dashboard)"

API_HOST = "https://icedapi.niti.gov.in"
API_HOST_V1 = "https://icedapi.niti.gov.in/v1"


# ---------------------------------------------------------------------------
# Indicator metadata blocks (one builder per artifact)
# ---------------------------------------------------------------------------


def _indicator_state_capacity_by_source() -> dict[str, Any]:
    return {
        "id": "energy/state_installed_capacity_by_source_mw",
        "title": "State installed electricity capacity, by fuel source (MW)",
        "description": (
            "Per-state installed electricity-generation capacity broken down "
            "by fuel source — coal, hydro, large-hydro, small-hydro, wind, "
            "solar, bio-power, oil-gas, nuclear. The capacity is sited in "
            "the state but the electricity it generates may flow elsewhere "
            "via the national grid; read this as a 'where assets sit' map, "
            "not 'where service reaches'. Long-history (FY 2015-16 onward) "
            "companion to the CEA single-month snapshot already in the "
            "site."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "count",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "MW",
        "icon": "zap",
        "attribution_geography": "where_produced",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "joint",
        "methodology_vintage": (
            "ICED capacity-metatable rollup of CEA-published station-level "
            "capacity, harmonised across fiscal years 2015-16 → 2025-26."
        ),
        "chart_type": "stacked-trend",
        "default_mode": "absolute",
        "notes": (
            "Andhra Pradesh figures before FY2014-15 include the area now in "
            "Telangana; Jammu & Kashmir before FY2019-20 includes Ladakh. "
            "Sub-fuel buckets ('large-hydro' vs 'small-hydro', 'bio-power' "
            "vs 'waste-to-energy') follow ICED's labelling and may shift "
            "year-on-year as CEA refines its source taxonomy."
        ),
        "series_breaks": [
            {
                "at_time": "2014-04",
                "kind": "coverage_change",
                "note": "Telangana bifurcated from Andhra Pradesh; pre-2014 AP rows include Telangana.",
            },
            {
                "at_time": "2019-04",
                "kind": "coverage_change",
                "note": "Ladakh bifurcated from J&K; pre-2019 J&K rows include Ladakh.",
            },
        ],
    }


def _indicator_state_generation_by_source() -> dict[str, Any]:
    return {
        "id": "energy/state_electricity_generation_by_source_gwh",
        "title": "State electricity generation, by fuel source (GWh, latest year snapshot)",
        "description": (
            "Per-state actual electricity generated, broken down by fuel "
            "source, for the most recent fiscal year ICED publishes. This "
            "is the 'service' counterpart to installed capacity — capacity "
            "is potential, generation is delivered. Unlike capacity, ICED "
            "does not yet expose a long historical time series for this "
            "field at the state level; we ship a single-year snapshot until "
            "an upstream long-history endpoint becomes available."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "count",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "GWh",
        "icon": "zap",
        "attribution_geography": "where_produced",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "joint",
        "methodology_vintage": (
            "ICED powerStatistics endpoint, latest fiscal-year snapshot "
            "(refresh per upstream cadence)."
        ),
        "chart_type": "stacked-trend",
        "default_mode": "absolute",
        "notes": (
            "Single-year snapshot — comparison across states for one year "
            "is meaningful, year-on-year reading is not (only one period "
            "ships). Pair with installed_capacity_by_source for "
            "utilisation analysis."
        ),
    }


def _indicator_state_peak_demand() -> dict[str, Any]:
    return {
        "id": "energy/state_peak_electricity_demand_mw",
        "title": "State peak electricity demand (MW, latest year snapshot)",
        "description": (
            "Per-state peak instantaneous electricity demand met during the "
            "most recent fiscal year. Tells the citizen how much power the "
            "state's grid had to supply at its busiest moment — a "
            "service-side counterpart to nameplate capacity."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "count",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "MW",
        "icon": "activity",
        "attribution_geography": "where_consumed",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "joint",
        "methodology_vintage": (
            "ICED powerStatistics endpoint, latest fiscal-year snapshot."
        ),
        "notes": (
            "Single-year snapshot. Larger states will read higher even "
            "when per-capita demand is similar — pair with state population "
            "for a per-capita view."
        ),
    }


def _indicator_india_retired_capacity() -> dict[str, Any]:
    return {
        "id": "energy/india_thermal_capacity_retired_mw",
        "title": "India thermal generating capacity retired, by fuel (MW per year)",
        "description": (
            "National total of generating capacity retired each fiscal year, "
            "broken down by fuel source (largely coal and oil-gas). A "
            "key signal in the energy-transition story: coal retirements "
            "rising over time means the fleet is being replaced rather "
            "than just expanded. Pair with installed_capacity additions "
            "to read net change."
        ),
        "entity_kind": "country",
        "time_grain": "fiscal_year",
        "value_kind": "count",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "MW",
        "icon": "trash-2",
        "attribution_geography": "where_produced",
        "comparability": "comparable_across_states",
        "implementing_authority": "joint",
        "methodology_vintage": "ICED retired-capacity-plants endpoint (CEA-sourced).",
        "chart_type": "stacked-trend",
        "default_mode": "absolute",
        "notes": (
            "National only — ICED does not publish state-level retired "
            "capacity. Captures only utility-scale thermal retirements; "
            "captive plants and renewables decommissioning are not in "
            "scope of the upstream feed."
        ),
    }


def _indicator_india_pipeline() -> dict[str, Any]:
    return {
        "id": "energy/india_capacity_pipeline_gw",
        "title": "India under-construction electricity capacity pipeline (GW per year)",
        "description": (
            "National total of generating capacity that is either under "
            "construction and on track, or under construction but on hold, "
            "by year of expected commissioning. Reads forward in time as "
            "well as backward — the citizen sees what is in the pipeline "
            "for the rest of the decade, not just what already exists."
        ),
        "entity_kind": "country",
        "time_grain": "year",
        "value_kind": "count",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "GW",
        "icon": "construction",
        "attribution_geography": "where_produced",
        "comparability": "comparable_across_states",
        "implementing_authority": "joint",
        "methodology_vintage": (
            "ICED plantPipelineInfo endpoint (CEA monthly status review). "
            "Forward-year values are expectations and revise frequently."
        ),
        "chart_type": "stacked-trend",
        "default_mode": "absolute",
        "notes": (
            "National only. Faceted by status — 'Under Construction and "
            "likely to be commissioned' vs 'Under Construction but on "
            "Hold'. Forward-year values move month to month as projects "
            "slip schedule; treat anything beyond CY+2 as planning, not "
            "forecast."
        ),
    }


# ---------------------------------------------------------------------------
# Build descriptors — one per indicator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _IndicatorBuild:
    out_leaf: str
    indicator: dict[str, Any]
    coverage_spatial: str
    coverage_admin_level: str | None
    api_host: str
    api_path: str
    decrypt: bool
    page_url: str
    source_name: str
    # Extractor: takes the (decrypted | parsed-JSON) response and returns
    # ``list[dict]`` of canonical rows. For the powerStatistics endpoint
    # we share one fetch between two artifacts via a wrapper.
    extract: Any


def _all_builds() -> tuple[_IndicatorBuild, ...]:
    return (
        _IndicatorBuild(
            out_leaf="state_installed_capacity_by_source_mw",
            indicator=_indicator_state_capacity_by_source(),
            coverage_spatial="India (states + UTs)",
            coverage_admin_level="state",
            api_host=API_HOST_V1,
            api_path="/capacity-metatable-data",
            decrypt=False,
            page_url="https://iced.niti.gov.in/energy/electricity/capacity",
            source_name="ICED — Capacity Metatable (NITI Aayog / CEA)",
            extract=lambda d: parse_capacity_metatable(d)[0],
        ),
        _IndicatorBuild(
            out_leaf="state_electricity_generation_by_source_gwh",
            indicator=_indicator_state_generation_by_source(),
            coverage_spatial="India (states + UTs)",
            coverage_admin_level="state",
            api_host=API_HOST,
            api_path="/energy/powerStatistics",
            decrypt=True,
            page_url="https://iced.niti.gov.in/energy/electricity/power-statistics",
            source_name="ICED — Power Statistics (NITI Aayog)",
            extract=lambda d: parse_power_statistics(d)[0],
        ),
        _IndicatorBuild(
            out_leaf="state_peak_electricity_demand_mw",
            indicator=_indicator_state_peak_demand(),
            coverage_spatial="India (states + UTs)",
            coverage_admin_level="state",
            api_host=API_HOST,
            api_path="/energy/powerStatistics",
            decrypt=True,
            page_url="https://iced.niti.gov.in/energy/electricity/power-statistics",
            source_name="ICED — Power Statistics (NITI Aayog)",
            extract=lambda d: parse_power_statistics(d)[1],
        ),
        _IndicatorBuild(
            out_leaf="india_thermal_capacity_retired_mw",
            indicator=_indicator_india_retired_capacity(),
            coverage_spatial="India (national)",
            coverage_admin_level=None,
            api_host=API_HOST_V1,
            api_path="/retired-capacity-plants",
            decrypt=False,
            page_url="https://iced.niti.gov.in/energy/electricity/capacity/retired",
            source_name="ICED — Retired Capacity Plants (NITI Aayog / CEA)",
            extract=lambda d: parse_retired_capacity(d),
        ),
        _IndicatorBuild(
            out_leaf="india_capacity_pipeline_gw",
            indicator=_indicator_india_pipeline(),
            coverage_spatial="India (national)",
            coverage_admin_level=None,
            api_host=API_HOST_V1,
            api_path="/plantPipelineInfo",
            decrypt=True,
            page_url="https://iced.niti.gov.in/energy/electricity/capacity/upcoming",
            source_name="ICED — Plant Pipeline Info (NITI Aayog / CEA)",
            extract=lambda d: parse_pipeline(d),
        ),
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def ingest_iced_power(
    *,
    repo_root: Path,
    client_v0: IcedClient | None = None,
    client_v1: IcedClient | None = None,
) -> IngestSummary:
    """Fetch + emit all five energy indicator artifacts."""
    if client_v0 is None:
        client_v0 = IcedClient(host=API_HOST, runtime_root=repo_root)
    if client_v1 is None:
        client_v1 = IcedClient(host=API_HOST_V1, runtime_root=repo_root)

    builds = _all_builds()
    out_root = repo_root / "datasets" / "indicators" / "in" / "energy"

    fetched_at_overall = datetime.now(timezone.utc)
    results: list[IndicatorEmitResult] = []

    # Cache responses keyed by (host, path) so powerStatistics is only
    # fetched once even though two indicators consume it.
    cache: dict[tuple[str, str], Any] = {}
    cache_fetched_at: dict[tuple[str, str], datetime] = {}

    for b in builds:
        client = client_v1 if b.api_host == API_HOST_V1 else client_v0
        key = (b.api_host, b.api_path)
        if key not in cache:
            resp = client.get(b.api_path, decrypt=b.decrypt)
            cache[key] = resp.decrypted
            cache_fetched_at[key] = resp.fetched_at
        decrypted = cache[key]
        fetched_at = cache_fetched_at[key]

        rows = b.extract(decrypted)
        if not rows:
            raise RuntimeError(
                f"indicator {b.indicator['id']!r}: parser returned 0 rows; "
                f"check {b.api_host}{b.api_path} response shape."
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

        sources = [
            Source(url=f"{b.api_host}{b.api_path}", fetched_at=fetched_at),
        ]

        out_path = out_root / f"{b.out_leaf}.json"
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
