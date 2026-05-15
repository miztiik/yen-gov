"""Orchestrator for the ICED v1 ``*-metatable-data`` triplet.

Fetches three v1 endpoints (plain JSON, ``decrypt=False``) and emits three
indicator artifacts:

- ``energy/state_electricity_generation_by_source_gwh``  — UPGRADES the
  prior single-FY snapshot to an 11-year (FY16–FY26) per-fuel series.
- ``energy/state_plant_load_factor_pct``                — NEW.
- ``environment/state_power_sector_co2_emissions_mtco2`` — NEW (aggregated
  from the plant-unit-level upstream).
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
    parse_co_emission_metatable,
    parse_gen_metatable,
    parse_plf_metatable,
)


API_HOST_V1 = "https://icedapi.niti.gov.in/v1"

LICENSE_ICED = {
    "id": "GoI-OpenData",
    "name": "Government of India Open Data License",
    "url": "https://www.data.gov.in/government-open-data-license-india",
    "redistributable": True,
}


@dataclass(frozen=True)
class IndicatorEmitResult:
    indicator_id: str
    artifact_path: Path
    row_count: int
    time_min: str
    time_max: str
    skipped_unmapped: int = 0


@dataclass(frozen=True)
class IngestSummary:
    fetched_at: datetime
    results: tuple[IndicatorEmitResult, ...]


# ---------------------------------------------------------------------------
# Indicator metadata
# ---------------------------------------------------------------------------


def _indicator_state_generation_by_source() -> dict[str, Any]:
    return {
        "id": "energy/state_electricity_generation_by_source_gwh",
        "title": "State electricity generation, by fuel source (GWh, FY16–FY26)",
        "description": (
            "Per-state actual electricity generated, broken down by fuel "
            "source (coal, oil-gas, hydro, nuclear, wind, solar, "
            "small-hydro, bio-power). Eleven fiscal years (FY16–FY26) per "
            "state. Generation is the *delivered* counterpart to installed "
            "capacity — capacity is potential, generation is what plants "
            "actually produced. Replaces the prior single-FY snapshot from "
            "``/energy/powerStatistics`` with the multi-year history from "
            "the ICED ``/v1/gen-metatable-data`` endpoint. 1 MU "
            "(million unit) = 1 GWh."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "raw",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "GWh",
        "icon": "zap",
        "attribution_geography": "where_produced",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "joint",
        "methodology_vintage": (
            "NITI Aayog ICED ``/v1/gen-metatable-data`` (CEA-sourced upstream). "
            "Most-recent FY (FY26) is partial-year-actuals + forecast and may "
            "revise; treat the most-recent two FYs as preliminary."
        ),
        "chart_type": "stacked-trend",
        "default_mode": "absolute",
        "notes": (
            "ICED publishes one bucket called ``Others`` that aggregates "
            "generation not attributable to any single state (interstate/"
            "central plants pre-allocation); we drop it because it cannot "
            "be mapped to a state choropleth honestly."
        ),
    }


def _indicator_state_plf() -> dict[str, Any]:
    return {
        "id": "energy/state_plant_load_factor_pct",
        "title": "State Plant Load Factor (PLF), by fuel source (%)",
        "description": (
            "Plant Load Factor — the share of nameplate capacity actually "
            "delivered as energy over a fiscal year. Per state, per fuel "
            "source (coal, oil-gas, hydro, nuclear, wind, solar, "
            "small-hydro, bio-power), FY16–FY26. PLF answers 'how hard is "
            "this fleet being run?' — coal PLFs near 60% indicate healthy "
            "merit-order despatch, near 40% indicates structural underuse "
            "(stranded assets); renewable PLFs are bounded by resource "
            "availability and inherently lower (solar ~20%, wind ~25%)."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "share",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "percent",
        "icon": "activity",
        "attribution_geography": "where_produced",
        "comparability": "comparable_across_states",
        "implementing_authority": "joint",
        "methodology_vintage": (
            "NITI Aayog ICED ``/v1/plf-metatable-data`` (CEA-sourced "
            "upstream). PLF is the standard CEA metric (energy generated ÷ "
            "(capacity × hours-in-period) × 100)."
        ),
        "chart_type": "ranked",
        "default_mode": "absolute",
        "notes": (
            "PLF is dimensionless (%) and directly comparable across states "
            "WITHIN a fuel — but NOT across fuels (a 25% solar PLF is "
            "excellent, a 25% coal PLF is a stranded asset). The renderer "
            "should keep facets visually distinct."
        ),
    }


def _indicator_state_co2_power() -> dict[str, Any]:
    return {
        "id": "environment/state_power_sector_co2_emissions_mtco2",
        "title": "State CO₂ emissions from power generation (MtCO₂/yr)",
        "description": (
            "Per-state CO₂ emissions from electricity generation, faceted "
            "by fuel source (coal vs oil-gas — only fossil-fired generation "
            "is in the upstream dataset). Aggregated from plant-unit-level "
            "ICED data (~280 plants × ~18 fiscal years × {coal, oil-gas}) "
            "summed to state × year × source. Million tonnes of CO₂ per "
            "year. FY09–FY26 coverage; the most recent two FYs are "
            "preliminary."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "raw",
        "direction": "lower_is_better",
        "scale_hint": "linear",
        "unit": "Mt CO2",
        "icon": "cloud",
        "attribution_geography": "where_produced",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "joint",
        "methodology_vintage": (
            "NITI Aayog ICED ``/v1/co-emission-metatable-data``. Plant-"
            "unit-level CO₂ emissions are derived upstream from CEA "
            "generation × CEA technology-specific emission factors "
            "(subcritical / supercritical / ultra-supercritical for coal). "
            "We aggregate by SUM per (state, fiscal year, fuel source)."
        ),
        "chart_type": "ranked",
        "default_mode": "absolute",
        "notes": (
            "Emissions follow the *siting* of the plant, not the consumer "
            "— ``attribution_geography=where_produced``. Renewables/nuclear/"
            "hydro/large-hydro are absent from the upstream dataset by "
            "design (operational CO₂ ≈ 0 for those). For per-capita / per-"
            "GSDP normalisation, divide by the matching demography / "
            "economy artifact."
        ),
    }


# ---------------------------------------------------------------------------
# Emit helper (mirrors iced_macro)
# ---------------------------------------------------------------------------


def _emit(
    *,
    repo_root: Path,
    schema_for_validation: dict,
    schema_id_str: str,
    schema_version_str: str,
    indicator_meta: dict[str, Any],
    rows: list[dict[str, Any]],
    sources: list[Source],
    out_rel: str,
    spatial: str,
    skipped_unmapped: int = 0,
) -> IndicatorEmitResult:
    times = sorted({r["time"] for r in rows})
    coverage_temporal = (
        f"{times[0]}..{times[-1]}" if len(times) > 1 else (times[0] if times else "unknown")
    )
    payload = {
        "coverage": {
            "spatial": spatial,
            "temporal": coverage_temporal,
            "admin_level": "state",
        },
        "license": LICENSE_ICED,
        "indicator": indicator_meta,
        "rows": rows,
    }
    artifact_path = repo_root / out_rel
    write_artifact(
        path=artifact_path,
        schema_id=schema_id_str,
        schema_version=schema_version_str,
        payload=payload,
        sources=sources,
        schema_for_validation=schema_for_validation,
    )
    return IndicatorEmitResult(
        indicator_id=indicator_meta["id"],
        artifact_path=artifact_path,
        row_count=len(rows),
        time_min=times[0] if times else "",
        time_max=times[-1] if times else "",
        skipped_unmapped=skipped_unmapped,
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def ingest_iced_metatable(*, repo_root: Path, client: IcedClient | None = None) -> IngestSummary:
    if client is None:
        client = IcedClient(host=API_HOST_V1, polite_delay=0.5)
    schema_for_validation = schema_doc("indicator.schema.json")
    sid = schema_id("indicator.schema.json")
    sver = schema_version("indicator.schema.json")

    results: list[IndicatorEmitResult] = []

    # Generation (replaces prior single-FY snapshot)
    gen_resp = client.get("/gen-metatable-data", decrypt=False)
    gen_rows, gen_skipped = parse_gen_metatable(gen_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_state_generation_by_source(), rows=gen_rows,
        sources=[Source(url=gen_resp.url, fetched_at=gen_resp.fetched_at)],
        out_rel="datasets/indicators/in/energy/state_electricity_generation_by_source_gwh.json",
        spatial="India (states + UTs)", skipped_unmapped=gen_skipped,
    ))

    # PLF
    plf_resp = client.get("/plf-metatable-data", decrypt=False)
    plf_rows, plf_skipped = parse_plf_metatable(plf_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_state_plf(), rows=plf_rows,
        sources=[Source(url=plf_resp.url, fetched_at=plf_resp.fetched_at)],
        out_rel="datasets/indicators/in/energy/state_plant_load_factor_pct.json",
        spatial="India (states + UTs)", skipped_unmapped=plf_skipped,
    ))

    # CO2 (aggregated from plant-unit-level upstream)
    co2_resp = client.get("/co-emission-metatable-data", decrypt=False)
    co2_rows, co2_skipped = parse_co_emission_metatable(co2_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_state_co2_power(), rows=co2_rows,
        sources=[Source(url=co2_resp.url, fetched_at=co2_resp.fetched_at)],
        out_rel="datasets/indicators/in/environment/state_power_sector_co2_emissions_mtco2.json",
        spatial="India (states + UTs, fossil-fired plants only)",
        skipped_unmapped=co2_skipped,
    ))

    return IngestSummary(
        fetched_at=datetime.now(timezone.utc),
        results=tuple(results),
    )
