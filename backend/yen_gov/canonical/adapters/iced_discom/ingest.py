"""Indicator metadata + canonical CSV emission for the ICED v0 DISCOM family.

The legacy network-fetch + folded-indicator-JSON path (``ingest_iced_discom``)
was retired in B4-pt2.1 per parent plan section 21.4 ("network-fetch code is
deleted; ingest reads local TCPD / source CSV"). What remains is the
indicator metadata + the B1.4.7 canonical CSV emission exercised by
``backend/tests/test_iced_discom_csv_repoint.py``.

Four indicators were emitted by the retired path:

- ``energy/state_distribution_td_loss_pct``               (T&D loss, %)
- ``energy/state_distribution_billing_efficiency_pct``    (billing eff, %)
- ``energy/state_distribution_collection_efficiency_pct`` (collection eff, %)
- ``energy/state_rpo_compliance_pct``                     (RPO compliance, %)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.canonical.adapters.iced_common import load_iced_response
from yen_gov.canonical.adapters.iced_discom.parsers import parse_rpo


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
# RPO-compliance re-ingest (Tier-B: orphan -> LIVE re-ingest)
# ---------------------------------------------------------------------------
#
# ICED distribution RPO feed: per-(state, FY, segment) Renewable Purchase
# Obligation compliance (% of target), faceted by 3 segments (solar,
# non-solar, total). This is a PERCENTAGE / non-fuel-axis family that does
# NOT fit the geo_by_fuel file-class, so it stays in its existing per-facet
# `datasets/data/datapoints/geo/rpo-compliance-pct-<segment>.csv` shape
# (Path B: emit the current shape, NO new file-class). This graduates the
# orphan family to LIVE re-ingest: the energy-adapter lift code that wrote
# these files was deleted in X1b-pt2.
#
# The (producer, title, vintage) triple below REPRODUCES the on-disk
# source_id src-0ea63ed47704 (idempotent re-emit). Recovered verbatim from
# the FK target row in `datasets/data/entities/source.csv`. NB: this title
# differs from the `_CSV_SOURCE_TITLE_RPO` constant above -- the on-disk
# files were written by the energy-adapter path, NOT the iced_discom
# `_emit_csv_for` path, so the idempotent triple is the adapter's, not
# iced_discom's legacy constant. The variable_id reuses
# `_CSV_VARIABLE_PREFIX_RPO` (== "rpo-compliance-pct").
_RPO_REINGEST_TITLE = (
    "Distribution RPO Compliance API (state-wise Renewable Purchase "
    "Obligation compliance, by segment)"
)
_RPO_REINGEST_VINTAGE = "2024-25"


@dataclass(frozen=True)
class RpoComplianceIngestResult:
    """Receipt for the per-segment RPO-compliance CSV emit."""

    variable_ids: tuple[str, ...]
    artifact_paths: tuple[Path, ...]
    row_count: int
    skipped_unmapped: int


def _to_slug(eci_st_code: str) -> str:
    """ECI st_code -> LGD slug, with the country rollup passed through.

    Mirrors ``iced_fuel.ingest._to_slug``. The RPO parser emits ECI st_codes
    (``S13``); ``entities/geo.csv`` keys on LGD slugs (``maharashtra``), so
    the entity output is re-pointed through the translation. ``IN`` (national
    rollup) passes through unchanged.
    """
    if eci_st_code == "IN":
        return "IN"
    return eci_to_lgd_slug(eci_st_code)


def build_rpo_compliance_variables(
    parsed_rows: list[dict[str, Any]],
    *,
    source_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Build the per-segment RPO-compliance geo rows, ECI st_code -> LGD slug.

    Each parser row ``{entity_id(ECI), time("YYYY-04"), value, facet(segment)}``
    keeps its faceted shape but its ECI st_code resolves to the LGD slug
    (``IN`` country passthrough). ``time`` is left as the ``YYYY-04`` period
    because ``build_csv_variables`` reduces it to the integer fiscal-year
    start internally. Returns a ``by_variable`` map with one key per segment
    facet (``rpo-compliance-pct-<segment-slug>``), ready for
    ``emit_csv_variables``.
    """
    translated = [
        {
            "entity_id": _to_slug(str(r["entity_id"])),
            "time": r["time"],
            "value": r["value"],
            "facet": r["facet"],
        }
        for r in parsed_rows
    ]
    return build_csv_variables(
        translated, source_id=source_id, variable_prefix=_CSV_VARIABLE_PREFIX_RPO
    )


def ingest_rpo_compliance(
    *, repo_root: Path, raw_json_path: Path, decrypt: bool = True
) -> RpoComplianceIngestResult:
    """Read a staged RPO-compliance JSON, emit the per-segment RPO CSVs.

    Operator-staged local file (no network). The
    ``/energy/electricity/distribution/rpo`` feed is AES-encrypted on the
    wire, so the staged blob is the CryptoJS envelope; ``decrypt=True``
    (default) makes ``load_iced_response`` decrypt it before parsing (an
    already-plain file still loads). Emits one
    ``datasets/data/datapoints/geo/rpo-compliance-pct-<segment>.csv`` per
    segment facet (solar, non-solar, total) with LGD-slug ``entity_id`` rows.
    The (producer, title, vintage) triple reproduces the on-disk ``source_id``
    so a re-emit is idempotent with the committed files.
    """
    decoded = load_iced_response(raw_json_path.read_bytes(), decrypt=decrypt)
    parsed_rows, skipped = parse_rpo(decoded)
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _RPO_REINGEST_TITLE, _RPO_REINGEST_VINTAGE
    )
    by_variable = build_rpo_compliance_variables(
        parsed_rows, source_id=source_id
    )
    written = emit_csv_variables(repo_root=repo_root, by_variable=by_variable)
    return RpoComplianceIngestResult(
        variable_ids=tuple(sorted(by_variable)),
        artifact_paths=written,
        row_count=sum(len(rows) for rows in by_variable.values()),
        skipped_unmapped=skipped,
    )
