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

from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.sources.iced_common import load_iced_response
from yen_gov.sources.iced_metatable.parsers import parse_plf_metatable

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


# ---------------------------------------------------------------------------
# Plant-load-factor re-ingest (Tier-B: orphan -> LIVE re-ingest)
# ---------------------------------------------------------------------------
#
# ICED v1 plant-load-factor feed: per-(state, FY, fuel) Plant Load Factor (%),
# faceted by 8 fuel sources (biomass, coal, gas, hydro, nuclear, small-hydro,
# solar, wind). This is a PERCENTAGE / non-fuel-axis family that does NOT fit
# the geo_by_fuel file-class, so it stays in its existing per-facet
# `datasets/data/datapoints/geo/plant-load-factor-pct-<fuel>.csv` shape
# (Path B: emit the current shape, NO new file-class). This graduates the
# orphan family to LIVE re-ingest: the energy-adapter lift code that wrote
# these files was deleted in X1b-pt2.
#
# The (producer, title, vintage) triple below REPRODUCES the on-disk
# source_id src-7eb929cbf2d8 (idempotent re-emit). Recovered verbatim from
# the FK target row in `datasets/data/entities/source.csv`. NB: this title
# differs from the `_CSV_SOURCE_TITLE_PLF` constant above -- the on-disk
# files were written by the energy-adapter path, NOT the iced_metatable
# `_emit_csv_for` path, so the idempotent triple is the adapter's, not
# iced_metatable's legacy constant. The variable_id reuses
# `_CSV_VARIABLE_PREFIX_PLF` (== "plant-load-factor-pct").
_PLF_REINGEST_TITLE = (
    "Plant Load Factor by Fuel State API (state-wise per-fuel PLF "
    "percentage, fiscal-year, 8 fuel buckets)"
)
_PLF_REINGEST_VINTAGE = "2024-25"


@dataclass(frozen=True)
class PlantLoadFactorIngestResult:
    """Receipt for the per-fuel plant-load-factor CSV emit."""

    variable_ids: tuple[str, ...]
    artifact_paths: tuple[Path, ...]
    row_count: int
    skipped_unmapped: int


def _to_slug(eci_st_code: str) -> str:
    """ECI st_code -> LGD slug, with the country rollup passed through.

    Mirrors ``iced_fuel.ingest._to_slug``. The PLF parser emits ECI st_codes
    (``S13``); ``entities/geo.csv`` keys on LGD slugs (``maharashtra``), so
    the entity output is re-pointed through the translation. ``IN`` (national
    rollup) passes through unchanged.
    """
    if eci_st_code == "IN":
        return "IN"
    return eci_to_lgd_slug(eci_st_code)


def build_plant_load_factor_variables(
    parsed_rows: list[dict[str, Any]],
    *,
    source_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Build the per-fuel plant-load-factor geo rows, ECI st_code -> LGD slug.

    Each parser row ``{entity_id(ECI), time("YYYY-04"), value, facet(fuel)}``
    keeps its faceted shape but its ECI st_code resolves to the LGD slug
    (``IN`` country passthrough). ``time`` is left as the ``YYYY-04`` period
    because ``build_csv_variables`` reduces it to the integer fiscal-year
    start internally. Returns a ``by_variable`` map with one key per fuel
    facet (``plant-load-factor-pct-<fuel-slug>``), ready for
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
        translated, source_id=source_id, variable_prefix=_CSV_VARIABLE_PREFIX_PLF
    )


def ingest_plant_load_factor(
    *, repo_root: Path, raw_json_path: Path, decrypt: bool = True
) -> PlantLoadFactorIngestResult:
    """Read a staged plant-load-factor JSON, emit the per-fuel PLF CSVs.

    Operator-staged local file (no network). The ``/v1/plf-metatable-data``
    feed is plain JSON on the wire (the v1 metatable endpoints are not
    AES-encrypted), so ``decrypt`` is effectively a no-op here --
    ``load_iced_response`` only decrypts a body that looks like the CryptoJS
    envelope and otherwise parses plain JSON, so the default ``decrypt=True``
    loads this feed unchanged (kept for signature parity with the AES feeds).
    Emits one ``datasets/data/datapoints/geo/plant-load-factor-pct-<fuel>.csv``
    per fuel facet with LGD-slug ``entity_id`` rows. The
    (producer, title, vintage) triple reproduces the on-disk ``source_id`` so
    a re-emit is idempotent with the committed files.
    """
    decoded = load_iced_response(raw_json_path.read_bytes(), decrypt=decrypt)
    parsed_rows, skipped = parse_plf_metatable(decoded)
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _PLF_REINGEST_TITLE, _PLF_REINGEST_VINTAGE
    )
    by_variable = build_plant_load_factor_variables(
        parsed_rows, source_id=source_id
    )
    written = emit_csv_variables(repo_root=repo_root, by_variable=by_variable)
    return PlantLoadFactorIngestResult(
        variable_ids=tuple(sorted(by_variable)),
        artifact_paths=written,
        row_count=sum(len(rows) for rows in by_variable.values()),
        skipped_unmapped=skipped,
    )
