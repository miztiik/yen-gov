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
from datetime import datetime
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.iced_common import IcedClient

from .parsers import parse_opperf_states, parse_rpo


API_HOST_V0 = "https://icedapi.niti.gov.in"


# ---------------------------------------------------------------------------
# Canonical CSV emission constants (B1.4.7)
# ---------------------------------------------------------------------------
#
# All four iced_discom indicators are NITI Aayog ICED endpoints; vintage =
# operator snapshot FY per ADR-0042. derive_source_id() hashes the
# (producer, title, vintage) triple at write time; the row in
# `datasets/data/entities/source.csv` is populated by B2a. variable_ids
# honour parent plan section 21.6 / 21.12 (no `__`) and ADR-0044 (no
# grain prefix). RPO splits per facet (solar/non-solar/total) because
# csv_writer does not yet accept facet columns (sub-plan B1.4.1..9 #7).
# concept_id binding is DEFERRED to B2a; recorded as DEFER marker in
# the PR body.
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"
_CSV_SOURCE_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
_CSV_SOURCE_VINTAGE = "2024-25"

_CSV_SOURCE_TITLE_TD_LOSS = (
    "ICED operational performance states: transmission and distribution loss"
)
_CSV_VARIABLE_PREFIX_TD_LOSS = "transmission-distribution-loss-pct"

_CSV_SOURCE_TITLE_BILLING = (
    "ICED operational performance states: billing efficiency"
)
_CSV_VARIABLE_PREFIX_BILLING = "distribution-billing-efficiency-pct"

_CSV_SOURCE_TITLE_COLLECTION = (
    "ICED operational performance states: collection efficiency"
)
_CSV_VARIABLE_PREFIX_COLLECTION = "distribution-collection-efficiency-pct"

_CSV_SOURCE_TITLE_RPO = "ICED RPO compliance (solar, non-solar, total)"
_CSV_VARIABLE_PREFIX_RPO = "rpo-compliance-pct"

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
        "notes": (
            "Time coverage is thin (FY19–FY21 in current upstream); "
            "most useful as a recent-cycle compliance snapshot rather "
            "than a long-arc trend. Targets themselves vary by state "
            "and rise over time, so a 95% compliance in FY21 may "
            "represent more renewables than 105% in FY19."
        ),
    }


# ---------------------------------------------------------------------------
# Canonical CSV emission helpers (B1.4.7)
# ---------------------------------------------------------------------------


def _slug_segment(text: str) -> str:
    """Kebab-case a facet segment for use inside a ``variable_id``.

    Mirrors sibling iced_* ingests (B1.4.1..6). Parent plan section
    21.6 / 21.12 ban ``__``; ADR-0044 bans grain prefixes.
    """
    out: list[str] = []
    prev_dash = True
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")


def _period_to_year_int(period: str) -> int:
    """Reduce ``YYYY-MM`` or ``YYYY`` to integer year.

    The canonical CSV column class ``datasets/data/datapoints/geo/*.csv``
    declares ``time`` as integer. iced_discom parsers emit ``YYYY-04``
    (fiscal-year start) via ``fy_to_period``. Raises on malformed input.
    """
    if not (isinstance(period, str) and len(period) >= 4 and period[:4].isdigit()):
        raise ValueError(f"unexpected time format {period!r}; expected 'YYYY' or 'YYYY-MM'")
    return int(period[:4])


def build_csv_variables(
    parsed_rows: list[dict[str, Any]],
    *,
    source_id: str,
    variable_prefix: str,
) -> dict[str, list[dict[str, Any]]]:
    """Split parser output into per-facet CSV row lists keyed by ``variable_id``.

    Faceted indicators (RPO compliance) split into one ``variable_id``
    per facet value: ``<variable_prefix>-<facet-slug>``. Non-faceted
    indicators (opperf categories) collapse to a single ``variable_id
    == variable_prefix``. Each output row carries the canonical 4
    columns declared on file class
    ``datasets/data/datapoints/geo/*.csv``: ``entity_id``, ``time``,
    ``value``, ``source_id``.
    """
    by_variable: dict[str, list[dict[str, Any]]] = {}
    for row in parsed_rows:
        facet = row.get("facet")
        if facet is None:
            variable_id = variable_prefix
        else:
            variable_id = f"{variable_prefix}-{_slug_segment(str(facet))}"
        by_variable.setdefault(variable_id, []).append({
            "entity_id": row["entity_id"],
            "time": _period_to_year_int(row["time"]),
            "value": row["value"],
            "source_id": source_id,
        })
    return by_variable


def emit_csv_variables(
    *, repo_root: Path, by_variable: dict[str, list[dict[str, Any]]]
) -> tuple[Path, ...]:
    """Write each ``variable_id`` to ``datasets/data/datapoints/geo/<id>.csv``."""
    written: list[Path] = []
    out_dir = repo_root / _CSV_OUT_REL_DIR
    for variable_id, rows in sorted(by_variable.items()):
        path = write_csv(
            path=out_dir / f"{variable_id}.csv",
            file_class=_CSV_FILE_CLASS,
            rows=rows,
        )
        written.append(path)
    return tuple(written)


def _emit_csv_for(
    *,
    repo_root: Path,
    parsed_rows: list[dict[str, Any]],
    title: str,
    variable_prefix: str,
) -> tuple[Path, ...]:
    """Canonical CSV emission ALONGSIDE the legacy meadow indicator JSON.

    B1.4.7 - both stores coexist (parent plan section 23.1); reader
    flip is X1a. ``source_id`` derived via ADR-0042 from
    (producer, title, vintage); one ``variable_id`` per facet (csv_writer
    facet-column support deferred).
    """
    source_id = derive_source_id(_CSV_SOURCE_PRODUCER, title, _CSV_SOURCE_VINTAGE)
    by_variable = build_csv_variables(
        parsed_rows, source_id=source_id, variable_prefix=variable_prefix
    )
    return emit_csv_variables(repo_root=repo_root, by_variable=by_variable)


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
        out_rel="datasets/energy/_meadow/iced/2024-25/state_distribution_td_loss_pct.json",
        spatial="India (states + UTs)", skipped_unmapped=op_skipped,
    ))
    _emit_csv_for(
        repo_root=repo_root,
        parsed_rows=by_cat["transmission-and-distribution-loss"],
        title=_CSV_SOURCE_TITLE_TD_LOSS,
        variable_prefix=_CSV_VARIABLE_PREFIX_TD_LOSS,
    )
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_billing_efficiency(),
        rows=by_cat["billing-efficiency"],
        sources=op_sources,
        out_rel="datasets/energy/_meadow/iced/2024-25/state_distribution_billing_efficiency_pct.json",
        spatial="India (states + UTs)",
    ))
    _emit_csv_for(
        repo_root=repo_root,
        parsed_rows=by_cat["billing-efficiency"],
        title=_CSV_SOURCE_TITLE_BILLING,
        variable_prefix=_CSV_VARIABLE_PREFIX_BILLING,
    )
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_collection_efficiency(),
        rows=by_cat["collection-efficiency"],
        sources=op_sources,
        out_rel="datasets/energy/_meadow/iced/2024-25/state_distribution_collection_efficiency_pct.json",
        spatial="India (states + UTs)",
    ))
    _emit_csv_for(
        repo_root=repo_root,
        parsed_rows=by_cat["collection-efficiency"],
        title=_CSV_SOURCE_TITLE_COLLECTION,
        variable_prefix=_CSV_VARIABLE_PREFIX_COLLECTION,
    )

    # RPO compliance.
    rpo_resp = client.get("/energy/electricity/distribution/rpo")
    rpo_rows, rpo_skipped = parse_rpo(rpo_resp.decrypted)
    results.append(_emit(
        repo_root=repo_root, schema_for_validation=schema_for_validation,
        schema_id_str=sid, schema_version_str=sver,
        indicator_meta=_indicator_rpo_compliance(), rows=rpo_rows,
        sources=[Source(url=rpo_resp.url, fetched_at=rpo_resp.fetched_at)],
        out_rel="datasets/energy/_meadow/iced/2024-25/state_rpo_compliance_pct.json",
        spatial="India (states + UTs)", skipped_unmapped=rpo_skipped,
    ))
    _emit_csv_for(
        repo_root=repo_root,
        parsed_rows=rpo_rows,
        title=_CSV_SOURCE_TITLE_RPO,
        variable_prefix=_CSV_VARIABLE_PREFIX_RPO,
    )

    # PR-A5a-tail: derive orchestrator fetched_at from upstream per-fetch
    # timestamps instead of wall-clock datetime.now().
    return IngestSummary(
        fetched_at=max(op_resp.fetched_at, rpo_resp.fetched_at),
        results=tuple(results),
    )
