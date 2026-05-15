"""Orchestrator for the ICED v0 fuel + power-purchase endpoint family.

Fetches three v0 AES-encrypted endpoints and emits three indicator
artifacts:

- ``energy/state_coal_consumption_mt``         (state coal consumption, Mt)
- ``energy/state_oil_product_consumption_kt``  (state oil-product, kt; faceted)
- ``energy/state_power_purchase_share_pct``    (state procurement mix, %)
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
    parse_coal_consumption_state,
    parse_oil_consumption_state,
    parse_ppa_share,
)


API_HOST_V0 = "https://icedapi.niti.gov.in"

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


def _indicator_coal_consumption() -> dict[str, Any]:
    return {
        "id": "energy/state_coal_consumption_mt",
        "title": "State coal consumption (Mt, FY06–FY25)",
        "description": (
            "Per-state domestic coal consumption in million tonnes per "
            "fiscal year, summed across all coal grades produced or "
            "imported within the state (raw coal + washed coal + "
            "middlings + lignite). Coal is by far India's largest "
            "primary-energy source: states with high coal consumption "
            "are typically those that host large thermal generation "
            "fleets (Maharashtra, UP, MP, Chhattisgarh) or heavy "
            "industry (steel, cement)."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "raw",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "Mt",
        "icon": "package",
        "attribution_geography": "where_consumed",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "joint",
        "methodology_vintage": (
            "NITI Aayog ICED ``/energy/fuel-sources/coal/"
            "consumption-domestic-state`` (Coal Controller's Office / "
            "Ministry of Coal upstream). Aggregated by SUM of the 4 "
            "component grades (raw, washed, middlings, lignite); the "
            "precomputed ``TOTAL COAL`` rows are dropped to avoid "
            "double-counting (they exist for only the most-recent FYs)."
        ),
        "chart_type": "ranked",
        "default_mode": "absolute",
        "notes": (
            "Coal consumption is a *consumption* statistic — the state "
            "where coal is burned, not the state where it is mined. For "
            "the production side, see installed-capacity-by-source "
            "(coal facet) and the generation-by-source artifact."
        ),
    }


def _indicator_oil_consumption() -> dict[str, Any]:
    return {
        "id": "energy/state_oil_product_consumption_kt",
        "title": "State oil-product consumption (kt, by product)",
        "description": (
            "Per-state consumption of refined petroleum products in "
            "kilotonnes (kt) per fiscal year, faceted by product: "
            "diesel-HSD, petrol, LPG, kerosene, naphtha, petroleum-coke, "
            "others. Diesel is the largest product nationally, driven by "
            "transport (heavy vehicles, agricultural pumps); LPG is the "
            "household cooking fuel after the PMUY scheme; petroleum "
            "coke is a refinery by-product used as cheap industrial fuel "
            "(cement, glass) and is regulated heavily for air-quality "
            "reasons in some states."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "raw",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "kt",
        "icon": "fuel",
        "attribution_geography": "where_consumed",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "centre",
        "methodology_vintage": (
            "NITI Aayog ICED ``/energy/fuel-sources/oil/"
            "consumptionStateProductTrend`` (PPAC / Ministry of Petroleum "
            "& Natural Gas upstream). Per-state per-product per-FY, "
            "FY11–FY25. The ``OTHERS`` state bucket and the national "
            "aggregate row (region == ``IN``) are dropped."
        ),
        "chart_type": "ranked",
        "default_mode": "absolute",
        "notes": (
            "Like coal, oil is a *consumption* statistic — the state "
            "where the product is sold/consumed. Diesel and petrol "
            "consumption track economic activity closely; LPG tracks "
            "household-coverage policy more than wealth."
        ),
    }


def _indicator_ppa_share() -> dict[str, Any]:
    return {
        "id": "energy/state_power_purchase_share_pct",
        "title": "State power-purchase mix by source (%, by source)",
        "description": (
            "Share of total electricity purchased by a state's distribution "
            "utilities, broken down by generation source (coal, hydro, "
            "solar, wind, nuclear, gas, small-hydro, bio-power, "
            "trading-and-others). Values sum to ~100% per (state, fiscal "
            "year). This is the *procurement* mix (where a state's "
            "DISCOMs buy from), not the *generation* mix (what a state's "
            "plants produce) — many states import most of their power."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "share",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "percent",
        "icon": "shopping-cart",
        "attribution_geography": "where_consumed",
        "comparability": "comparable_across_states",
        "implementing_authority": "state",
        "methodology_vintage": (
            "NITI Aayog ICED ``/statelevel-power-purchase-quantum-and-cost`` "
            "(PFC / Ministry of Power upstream). Per-state per-source per-FY, "
            "FY16–FY25. The ``totalCost`` upstream field is not emitted "
            "(many nulls in early years and unit unclear)."
        ),
        "chart_type": "ranked",
        "default_mode": "percent",
        "notes": (
            "Compare state procurement mix vs state generation mix "
            "(``state_electricity_generation_by_source_gwh``) to see "
            "the *trade pattern*: states that produce more renewable "
            "than they procure (export RE), states that procure more "
            "coal than they produce (import thermal), etc."
        ),
    }


# ---------------------------------------------------------------------------
# Emit helper
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


def ingest_iced_fuel(*, repo_root: Path, client: IcedClient | None = None) -> IngestSummary:
    if client is None:
        client = IcedClient(host=API_HOST_V0, polite_delay=0.5)
    schema_for_validation = schema_doc("indicator.schema.json")
    sid = schema_id("indicator.schema.json")
    sver = schema_version("indicator.schema.json")

    results: list[IndicatorEmitResult] = []

    coal_resp = client.get("/energy/fuel-sources/coal/consumption-domestic-state")
    coal_rows, coal_skipped = parse_coal_consumption_state(coal_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_coal_consumption(), rows=coal_rows,
        sources=[Source(url=coal_resp.url, fetched_at=coal_resp.fetched_at)],
        out_rel="datasets/indicators/in/energy/state_coal_consumption_mt.json",
        spatial="India (states + UTs, coal-consuming states only)",
        skipped_unmapped=coal_skipped,
    ))

    oil_resp = client.get("/energy/fuel-sources/oil/consumptionStateProductTrend")
    oil_rows, oil_skipped = parse_oil_consumption_state(oil_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_oil_consumption(), rows=oil_rows,
        sources=[Source(url=oil_resp.url, fetched_at=oil_resp.fetched_at)],
        out_rel="datasets/indicators/in/energy/state_oil_product_consumption_kt.json",
        spatial="India (states + UTs)", skipped_unmapped=oil_skipped,
    ))

    ppa_resp = client.get("/statelevel-power-purchase-quantum-and-cost")
    ppa_rows, ppa_skipped = parse_ppa_share(ppa_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_ppa_share(), rows=ppa_rows,
        sources=[Source(url=ppa_resp.url, fetched_at=ppa_resp.fetched_at)],
        out_rel="datasets/indicators/in/energy/state_power_purchase_share_pct.json",
        spatial="India (states + UTs)", skipped_unmapped=ppa_skipped,
    ))

    return IngestSummary(
        fetched_at=datetime.now(timezone.utc),
        results=tuple(results),
    )
