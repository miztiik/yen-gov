"""Orchestrator for the ICED v0 DISCOM endpoint family.

Fetches two v0 AES-encrypted endpoints and emits four indicator artifacts:

- ``energy/state_distribution_td_loss_pct``               (T&D loss, %)
- ``energy/state_distribution_billing_efficiency_pct``    (billing eff, %)
- ``energy/state_distribution_collection_efficiency_pct`` (collection eff, %)
- ``energy/state_rpo_compliance_pct``                     (RPO compliance, %)

The 4th opperf category (``aggregate-technical-and-commercial-loss``) is
intentionally NOT emitted as a new artifact because a state-level ATC
artifact already exists at ``energy/state_atc_losses_pct.json`` (sourced
from the ICED ``state-wise-deep-dive`` page) and includes an all-India
aggregate row that the opperf endpoint does not.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.iced_common import IcedClient

from .parsers import parse_opperf_states, parse_rpo


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


def _indicator_td_loss() -> dict[str, Any]:
    return {
        "id": "energy/state_distribution_td_loss_pct",
        "title": "Transmission & Distribution losses (%, by state)",
        "description": (
            "Energy lost between the point of generation/import into the "
            "state grid and the point of metered sale to consumers, as a "
            "percentage of total energy input. T&D losses are the *technical* "
            "component — heat in conductors, transformer losses, ageing "
            "infrastructure — and exclude commercial losses (theft, "
            "billing/collection failure). Compare against ``state_atc_losses_pct`` "
            "which adds the commercial component on top: AT&C ≈ T&D + "
            "commercial losses."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "share",
        "direction": "lower_is_better",
        "scale_hint": "linear",
        "unit": "percent",
        "icon": "trending-down",
        "attribution_geography": "where_administered",
        "comparability": "comparable_across_states",
        "implementing_authority": "state",
        "methodology_vintage": (
            "NITI Aayog ICED ``/energy/electricity/distribution/"
            "operationalPerformanceStates`` (PFC report-card upstream). "
            "Category ``transmission-and-distribution-loss``."
        ),
        "chart_type": "ranked",
        "default_mode": "absolute",
        "notes": (
            "Indian central-government targets envision T&D losses below 12% "
            "by FY26; the all-India figure has historically been ~17–20%. "
            "Big spreads across states reflect grid age, consumer mix, and "
            "agricultural pumping share more than utility competence alone."
        ),
    }


def _indicator_billing_efficiency() -> dict[str, Any]:
    return {
        "id": "energy/state_distribution_billing_efficiency_pct",
        "title": "Distribution billing efficiency (%, by state)",
        "description": (
            "Share of energy actually billed to a consumer, out of total "
            "energy input to the distribution system. Billing efficiency = "
            "(energy billed) ÷ (energy input). The complement of "
            "billing-side losses (theft, unmetered consumption, "
            "under-billing). 100% = every kWh that enters the grid was "
            "billed to someone."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "share",
        "direction": "higher_is_better",
        "scale_hint": "linear",
        "unit": "percent",
        "icon": "file-text",
        "attribution_geography": "where_administered",
        "comparability": "comparable_across_states",
        "implementing_authority": "state",
        "methodology_vintage": (
            "NITI Aayog ICED ``/energy/electricity/distribution/"
            "operationalPerformanceStates``. Category ``billing-efficiency``."
        ),
        "chart_type": "ranked",
        "default_mode": "absolute",
        "notes": (
            "Together with collection efficiency, billing efficiency "
            "decomposes the commercial half of AT&C losses: "
            "AT&C loss ≈ 1 − (billing × collection / 100)."
        ),
    }


def _indicator_collection_efficiency() -> dict[str, Any]:
    return {
        "id": "energy/state_distribution_collection_efficiency_pct",
        "title": "Distribution collection efficiency (%, by state)",
        "description": (
            "Share of billed revenue that was actually collected from "
            "consumers. Collection efficiency = (revenue collected) ÷ "
            "(amount billed). 100% = every rupee billed was paid; lower "
            "values indicate consumer arrears, government-department "
            "non-payment, or collection-process gaps."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "share",
        "direction": "higher_is_better",
        "scale_hint": "linear",
        "unit": "percent",
        "icon": "credit-card",
        "attribution_geography": "where_administered",
        "comparability": "comparable_across_states",
        "implementing_authority": "state",
        "methodology_vintage": (
            "NITI Aayog ICED ``/energy/electricity/distribution/"
            "operationalPerformanceStates``. Category ``collection-efficiency``."
        ),
        "chart_type": "ranked",
        "default_mode": "absolute",
        "notes": (
            "State government departments (irrigation, street-lighting, "
            "panchayats) are often the largest delinquent consumer "
            "category — chronic non-payment by the state on its own bills."
        ),
    }


def _indicator_rpo_compliance() -> dict[str, Any]:
    return {
        "id": "energy/state_rpo_compliance_pct",
        "title": "Renewable Purchase Obligation compliance (%, by state)",
        "description": (
            "Share of the state's regulatory Renewable Purchase Obligation "
            "(RPO) target actually met in a given fiscal year, faceted by "
            "solar, non-solar, and total. Each state regulator sets a "
            "year-by-year RPO target as a % of total energy procurement; "
            "this indicator measures how close the state came to that "
            "target, expressed as ``compliance ÷ target × 100``. 100% = "
            "target exactly met; values above 100% indicate "
            "over-compliance (renewable procurement above the regulatory "
            "floor)."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "share",
        "direction": "higher_is_better",
        "scale_hint": "linear",
        "unit": "percent",
        "icon": "sun",
        "attribution_geography": "where_administered",
        "comparability": "comparable_across_states",
        "implementing_authority": "state",
        "methodology_vintage": (
            "NITI Aayog ICED ``/energy/electricity/distribution/rpo`` "
            "(MNRE / state-regulator data). Three facets: ``solar`` "
            "(solarCompliance), ``non-solar`` (nonSolarCompliance), "
            "``total`` (totalCompliance). The unbounded ``rpoCompliance`` "
            "field is intentionally not emitted — citizen-readable "
            "interpretation requires the bounded percentage form."
        ),
        "chart_type": "ranked",
        "default_mode": "absolute",
        "notes": (
            "Time coverage is thin (FY19–FY21 in current upstream); "
            "most useful as a recent-cycle compliance snapshot rather "
            "than a long-arc trend. Targets themselves vary by state "
            "and rise over time, so a 95% compliance in FY21 may "
            "represent more renewables than 105% in FY19."
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


def ingest_iced_discom(*, repo_root: Path, client: IcedClient | None = None) -> IngestSummary:
    if client is None:
        client = IcedClient(host=API_HOST_V0, polite_delay=0.5)
    schema_for_validation = schema_doc("indicator.schema.json")
    sid = schema_id("indicator.schema.json")
    sver = schema_version("indicator.schema.json")

    results: list[IndicatorEmitResult] = []

    # Operational performance — split into 3 indicator artifacts.
    op_resp = client.get("/energy/electricity/distribution/operationalPerformanceStates")
    by_cat, op_skipped = parse_opperf_states(op_resp.decrypted)
    op_sources = [Source(url=op_resp.url, fetched_at=op_resp.fetched_at)]

    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_td_loss(),
        rows=by_cat["transmission-and-distribution-loss"],
        sources=op_sources,
        out_rel="datasets/indicators/in/energy/state_distribution_td_loss_pct.json",
        spatial="India (states + UTs)", skipped_unmapped=op_skipped,
    ))
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_billing_efficiency(),
        rows=by_cat["billing-efficiency"],
        sources=op_sources,
        out_rel="datasets/indicators/in/energy/state_distribution_billing_efficiency_pct.json",
        spatial="India (states + UTs)",
    ))
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_collection_efficiency(),
        rows=by_cat["collection-efficiency"],
        sources=op_sources,
        out_rel="datasets/indicators/in/energy/state_distribution_collection_efficiency_pct.json",
        spatial="India (states + UTs)",
    ))

    # RPO compliance.
    rpo_resp = client.get("/energy/electricity/distribution/rpo")
    rpo_rows, rpo_skipped = parse_rpo(rpo_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_rpo_compliance(), rows=rpo_rows,
        sources=[Source(url=rpo_resp.url, fetched_at=rpo_resp.fetched_at)],
        out_rel="datasets/indicators/in/energy/state_rpo_compliance_pct.json",
        spatial="India (states + UTs)", skipped_unmapped=rpo_skipped,
    ))

    return IngestSummary(
        fetched_at=datetime.now(timezone.utc),
        results=tuple(results),
    )
