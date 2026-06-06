"""Indicator metadata + canonical CSV emission for the ICED v1 metatable family.

The legacy network-fetch + folded-indicator-JSON path (``ingest_iced_metatable``)
was retired in B4-pt2.1 per parent plan section 21.4 ("network-fetch code is
deleted; ingest reads local TCPD / source CSV"). What remains is the
indicator metadata + the B1.4.4 canonical CSV emission exercised by
``backend/tests/test_iced_metatable_csv_repoint.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv

# B1.4.4 - canonical CSV citation triples + variable_id prefixes per indicator.
# All three iced_metatable indicators are NITI Aayog ICED v1 endpoints
# (CEA-sourced upstream); vintage = operator snapshot FY per ADR-0042.
# derive_source_id() hashes the triple at write time; the row in
# `datasets/data/entities/source.csv` is populated by B2a (sub-plan
# section "Pre-flight"). variable_ids honour parent plan section 21.6 / 21.12
# (no `__`) and ADR-0044 (no grain prefix - the legacy `state_` / `_pct` /
# `_gwh` / `_mtco2` markers on the meadow id are not grain prefixes per the
# regex `^(state|district|national)-` and are preserved only inside the
# unit-bearing tail of the kebab id). Per-facet split because csv_writer
# does not yet accept facet columns (sub-plan section B1.4.1..9 point 7).
# concept_id binding for all three indicators is DEFERRED to B2a; recorded
# as a per-PR DEFER marker in the PR body.
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"
_CSV_SOURCE_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
_CSV_SOURCE_VINTAGE = "2024-25"

_CSV_SOURCE_TITLE_GEN = (
    "State electricity generation by source (gen-metatable) API"
)
_CSV_VARIABLE_PREFIX_GEN = "electricity-generation-gwh"

_CSV_SOURCE_TITLE_PLF = (
    "State plant load factor by source (plf-metatable) API"
)
_CSV_VARIABLE_PREFIX_PLF = "plant-load-factor-pct"

_CSV_SOURCE_TITLE_CO2 = (
    "State power-sector CO2 emissions by source (co-emission-metatable) API"
)
_CSV_VARIABLE_PREFIX_CO2 = "power-sector-co2-emissions-mtco2"

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
# Canonical CSV emission helpers (B1.4.4)
# ---------------------------------------------------------------------------


def _slug_segment(text: str) -> str:
    """Kebab-case a facet segment for use inside a `variable_id`.

    Plan section 21.6 / 21.12 ban `__`; ADR-0044 bans grain prefixes. We
    lower-case, replace any non-alphanumeric run with a single `-`, and
    strip leading/trailing `-`. Mirrors the helper in
    ``iced_ghg/ingest.py`` (B1.4.1, PR #635),
    ``iced_macro/ingest.py`` (B1.4.2, PR #636), and
    ``iced_fuel/ingest.py`` (B1.4.3, PR #637).
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
    """Reduce an iced_common ``YYYY-MM`` period to its fiscal-year start year.

    The iced_metatable parsers emit ``fy_to_period`` output (``YYYY-04``).
    The canonical CSV column class ``datasets/data/datapoints/geo/*.csv``
    declares ``time`` as integer. FY 2024-25 -> ``2024``. Raises
    ``ValueError`` on malformed input rather than silently truncating.
    """
    if not (isinstance(period, str) and len(period) >= 4 and period[:4].isdigit()):
        raise ValueError(f"unexpected time format {period!r}; expected 'YYYY-MM'")
    return int(period[:4])


def build_csv_variables(
    parsed_rows: list[dict[str, Any]],
    *,
    source_id: str,
    variable_prefix: str,
) -> dict[str, list[dict[str, Any]]]:
    """Split parser output into per-facet CSV row lists keyed by ``variable_id``.

    All three iced_metatable indicators carry a ``facet`` column (fuel
    source). We split into one ``variable_id`` per facet value:
    ``<variable_prefix>-<facet-slug>``. When ``facet`` is absent (defensive
    branch; not exercised by iced_metatable parsers today) the indicator
    collapses to a single ``variable_id == variable_prefix``. Each output
    row carries the canonical 4 columns declared on file class
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
    """Canonical CSV emission ALONGSIDE the legacy meadow/indicator JSON.

    B1.4.4 - both stores coexist (parent plan section 23.1); reader flip
    is X1a. ``source_id`` derived via ADR-0042 from
    (producer, title, vintage); one ``variable_id`` per facet (csv_writer
    facet-column support deferred).
    """
    source_id = derive_source_id(_CSV_SOURCE_PRODUCER, title, _CSV_SOURCE_VINTAGE)
    by_variable = build_csv_variables(
        parsed_rows, source_id=source_id, variable_prefix=variable_prefix
    )
    return emit_csv_variables(repo_root=repo_root, by_variable=by_variable)
