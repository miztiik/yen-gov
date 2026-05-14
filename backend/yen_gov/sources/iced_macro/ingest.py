"""Orchestrator for the ICED macro adapter.

Fetches three endpoints and emits four indicator artifacts under
``datasets/indicators/in/`` (economy + demography).
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
    parse_gdp_trend,
    parse_industrial_production,
    parse_population_by_residence,
)


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


LICENSE_ICED = {
    "id": "GoI-OpenData",
    "name": "Government of India Open Data License",
    "url": "https://www.data.gov.in/government-open-data-license-india",
    "redistributable": True,
}

API_HOST = "https://icedapi.niti.gov.in"


# ---------------------------------------------------------------------------
# Indicator metadata
# ---------------------------------------------------------------------------


def _indicator_india_gdp() -> dict[str, Any]:
    return {
        "id": "economy/india_gdp_inr_crore",
        "title": "India GDP (₹ crore, current and constant prices)",
        "description": (
            "National Gross Domestic Product, ₹ crore, faceted by price "
            "basis: 'current' (nominal, contemporaneous prices) and "
            "'constant' (real, base 2011-12). Use the constant series for "
            "growth-rate analysis; the current series for nominal-share "
            "comparisons (e.g. fiscal-deficit ÷ GDP). Annual series 1950-51 "
            "to 2024-25 (75 fiscal years)."
        ),
        "entity_kind": "country",
        "time_grain": "fiscal_year",
        "value_kind": "raw",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "INR crore",
        "icon": "trending-up",
        "attribution_geography": "where_produced",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "centre",
        "methodology_vintage": (
            "MoSPI / National Statistical Office back-series. Constant prices "
            "rebased to 2011-12. Pre-2011 constant series is the back-cast "
            "MoSPI publishes; methodology shifted in 2015 (NSS68 → 2011-12 "
            "base) — treat the pre-2011 back-cast as a chained estimate."
        ),
        "chart_type": "stacked-trend",
        "default_mode": "absolute",
        "notes": (
            "ICED's upstream priceType field has values 'gross', 'export', "
            "'import' — only 'gross' is the GDP headline number we ship; "
            "the other two are deflator-calculation auxiliaries not used in "
            "policy framing."
        ),
        "series_breaks": [
            {
                "at_time": "2011-04",
                "kind": "rebase",
                "note": "Constant-price base year switches to 2011-12; pre-2011 figures are back-cast.",
            }
        ],
    }


def _indicator_state_gdp() -> dict[str, Any]:
    return {
        "id": "economy/state_gdp_inr_crore",
        "title": "State GDP (₹ crore, current and constant prices)",
        "description": (
            "Per-state GSDP (Gross State Domestic Product) in ₹ crore, "
            "faceted by price basis. Use 'current' for share-of-national "
            "rankings, 'constant' for state-level growth-rate analysis. "
            "Coverage varies by state — small states/UTs only enter the "
            "series after they were carved out (Telangana from 2014-15, "
            "Ladakh from 2019-20)."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "raw",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "INR crore",
        "icon": "trending-up",
        "attribution_geography": "where_produced",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "joint",
        "methodology_vintage": (
            "MoSPI per-state GSDP series. Constant prices rebased to 2011-12. "
            "Compiled by State Directorates of Economics & Statistics with "
            "MoSPI methodology guidance."
        ),
        "chart_type": "ranked",
        "default_mode": "absolute",
        "notes": (
            "GSDP is the within-state production view; for who-consumes-what, "
            "see per-capita consumption. State totals will not sum exactly to "
            "national GDP because of differences in base years and revision "
            "timing across the 36 state-level series."
        ),
        "series_breaks": [
            {
                "at_time": "2011-04",
                "kind": "rebase",
                "note": "Constant-price base year switches to 2011-12.",
            },
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


def _indicator_iip() -> dict[str, Any]:
    return {
        "id": "economy/india_iip_index_2011_12",
        "title": "Index of Industrial Production (IIP), base 2011-12 = 100",
        "description": (
            "National Index of Industrial Production, faceted by category "
            "(sectoral: Mining/Manufacturing/Electricity, plus the General "
            "all-industry index, plus use-based: Capital, Consumer "
            "durables, Consumer non-durables, Intermediate, Infrastructure, "
            "Primary). All values relative to 2011-12 = 100. Annual 2012-13 "
            "to 2024-25."
        ),
        "entity_kind": "country",
        "time_grain": "fiscal_year",
        "value_kind": "index",
        "direction": "higher_is_better",
        "scale_hint": "linear",
        "unit": "index (2011-12=100)",
        "icon": "factory",
        "attribution_geography": "where_produced",
        "comparability": "not_comparable_across_states",
        "implementing_authority": "centre",
        "methodology_vintage": "MoSPI Central Statistics Office, base 2011-12.",
        "chart_type": "stacked-trend",
        "default_mode": "absolute",
        "notes": (
            "Mixed sectoral + use-based facets in one indicator — ICED ships "
            "them in the same payload. Renderers should let the user pick "
            "which classification (sectoral vs use-based) to compare within."
        ),
    }


def _indicator_population_residence() -> dict[str, Any]:
    return {
        "id": "demography/state_population_by_residence_count",
        "title": "Census population by state, faceted Rural / Urban",
        "description": (
            "Decennial census headcounts per state (and All-India), split "
            "by residence: Rural vs Urban. Census years 1961, 1971, 1981, "
            "1991, 2001, 2011 (the 2021 census has been postponed). Use as "
            "the rural-urban share denominator and as a long-run "
            "urbanisation-trend series."
        ),
        "entity_kind": "state",
        "time_grain": "year",
        "value_kind": "count",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "persons",
        "icon": "users",
        "attribution_geography": "where_resident",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "centre",
        "methodology_vintage": (
            "Registrar General & Census Commissioner of India — decennial "
            "census, complete enumeration."
        ),
        "chart_type": "stacked-trend",
        "default_mode": "absolute",
        "notes": (
            "Companion to the existing Male/Female-faceted "
            "`state_population_by_sex_count`. Both come from the same census "
            "operation and share the 1961-2011 coverage. State boundaries "
            "shifted across the period (Andhra/Telangana 2014; J&K/Ladakh "
            "2019; Chhattisgarh/Jharkhand/Uttarakhand 2000) — pre-bifurcation "
            "rows reflect the older boundary and are tagged vintage='actual'."
        ),
    }


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
    coverage_temporal = f"{times[0]}..{times[-1]}" if times else "unknown"
    payload = {
        "coverage": {
            "spatial": spatial,
            "temporal": coverage_temporal,
            "admin_level": None if indicator_meta["entity_kind"] == "country" else "state",
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


def ingest_iced_macro(*, repo_root: Path, client: IcedClient | None = None) -> IngestSummary:
    if client is None:
        client = IcedClient(host=API_HOST, polite_delay=0.5)
    schema_for_validation = schema_doc("indicator.schema.json")
    sid = schema_id("indicator.schema.json")
    sver = schema_version("indicator.schema.json")

    results: list[IndicatorEmitResult] = []

    # GDP (split into national + state)
    gdp_resp = client.get("/economy-demography/key-economic-indicators/gdp-trend")
    gdp_src = [Source(url=gdp_resp.url, fetched_at=gdp_resp.fetched_at)]
    gdp_parsed = parse_gdp_trend(gdp_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_india_gdp(), rows=gdp_parsed.national,
        sources=gdp_src, out_rel="datasets/indicators/in/economy/india_gdp_inr_crore.json",
        spatial="India (national)",
    ))
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_state_gdp(), rows=gdp_parsed.state,
        sources=gdp_src, out_rel="datasets/indicators/in/economy/state_gdp_inr_crore.json",
        spatial="India (states + UTs)", skipped_unmapped=gdp_parsed.skipped_unmapped,
    ))

    # IIP
    iip_resp = client.get("/economy-demography/key-economic-indicators/industrial-production")
    iip_rows = parse_industrial_production(iip_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_iip(), rows=iip_rows,
        sources=[Source(url=iip_resp.url, fetched_at=iip_resp.fetched_at)],
        out_rel="datasets/indicators/in/economy/india_iip_index_2011_12.json",
        spatial="India (national)",
    ))

    # Census population by Rural/Urban
    dem_resp = client.get("/economy-demography/demography/demographyActual")
    pop_rows, pop_skipped = parse_population_by_residence(dem_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_population_residence(), rows=pop_rows,
        sources=[Source(url=dem_resp.url, fetched_at=dem_resp.fetched_at)],
        out_rel="datasets/indicators/in/demography/state_population_by_residence_count.json",
        spatial="India (states + UTs)", skipped_unmapped=pop_skipped,
    ))

    return IngestSummary(
        fetched_at=datetime.now(timezone.utc),
        results=tuple(results),
    )
