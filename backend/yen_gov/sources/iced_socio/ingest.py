"""ICED socio-economic adapter — fetch + emit two indicator artifacts.

Per Hans (Governance) triage 2026-05-14:

* ``economy/state_per_capita_consumption_inr``             — Priority 3
* ``environment/india_ghg_emissions_mtco2e_by_sector``     — Priority 6

The sex-faceted population shard (Hans Priority 5 —
``demography/state_population_by_sex_count``) was retired in PR-D4
— Census 2011 was the last completed enumeration and the 2021 round
was postponed; six decennial points was a position not a trajectory and
no canonical successor is planned.

The HDI indicator (Hans Priority 2 — ``human_development/state_hdi``) was
retired in PR-D3 — ICED publishes only two snapshot years (2011-12 and
2017-18) which is a position not a trajectory; no canonical successor is
planned (UNDP NHDR re-onboard deferred indefinitely).

The constant-price per-capita NSDP indicator (Hans Priority 1) was retired
in PR-B6-row8 — the canonical source for that fact is now the RBI Handbook
spliced shard ``economy/per_capita_nsdp_constant_inr`` (longer history,
multi-base splice). The current-price NSDP indicator (Hans Priority 4)
ships separately as ``economy/per_capita_nsdp_current_inr`` from the
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
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.iced_common import IcedClient

from .parsers import (
    parse_ghg_economy_wide,
    parse_per_capita_consumption,
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
        _per_capita_consumption_meta(),
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

    fetched_at_overall: datetime | None = None
    results: list[IndicatorEmitResult] = []

    for b in builds:
        resp = client.get(b.api_path)
        # PR-A5a: track max upstream fetched_at instead of wall-clock now().
        if fetched_at_overall is None or resp.fetched_at > fetched_at_overall:
            fetched_at_overall = resp.fetched_at
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

    if fetched_at_overall is None:
        raise RuntimeError("ingest_iced_socio: no builds executed; cannot derive fetched_at.")
    return IngestSummary(fetched_at=fetched_at_overall, results=tuple(results))


def _temporal_span(rows: list[dict[str, Any]]) -> str:
    times = sorted({r["time"] for r in rows})
    if not times:
        return "(empty)"
    if times[0] == times[-1]:
        return times[0]
    return f"{times[0]}..{times[-1]}"
