"""Indicator metadata + canonical CSV emission for the ICED power-sector family.

The legacy network-fetch + folded-indicator-JSON path (``ingest_iced_power``)
was retired in B4-pt2.1 per parent plan section 21.4 ("network-fetch code is
deleted; ingest reads local TCPD / source CSV"). What remains is the
indicator metadata + the B1.4.5 canonical CSV emission exercised by
``backend/tests/test_iced_power_csv_repoint.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.sources.iced_common import load_iced_response
from yen_gov.sources.iced_common.fuel_collapse import collapse_fuel
from yen_gov.sources.iced_power.parsers import (
    parse_capacity_metatable,
    parse_power_statistics,
)


# ---------------------------------------------------------------------------
# Canonical CSV emission constants (B1.4.5)
# ---------------------------------------------------------------------------
#
# All four iced_power indicators are NITI Aayog ICED endpoints
# (CEA-sourced upstream); vintage = operator snapshot FY per ADR-0042.
# derive_source_id() hashes the triple at write time; the row in
# `datasets/data/entities/source.csv` is populated by B2a (sub-plan
# section "Pre-flight"). variable_ids honour parent plan section 21.6 /
# 21.12 (no `__`) and ADR-0044 (no grain prefix). Per-facet split because
# csv_writer does not yet accept facet columns (sub-plan B1.4.1..9 #7).
# concept_id binding for all four indicators is DEFERRED to B2a;
# recorded as DEFER marker in the PR body.
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"
_CSV_SOURCE_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
_CSV_SOURCE_VINTAGE = "2024-25"

_CSV_SOURCE_TITLE_CAPACITY = (
    "State installed capacity by source (capacity-metatable) API"
)
_CSV_VARIABLE_PREFIX_CAPACITY = "installed-capacity-mw"

_CSV_SOURCE_TITLE_GEN = (
    "State electricity generation snapshot (powerStatistics) API"
)
_CSV_VARIABLE_PREFIX_GEN = "electricity-generation-snapshot-gwh"

_CSV_SOURCE_TITLE_PEAK = (
    "State peak electricity demand snapshot (powerStatistics) API"
)
_CSV_VARIABLE_PREFIX_PEAK = "peak-electricity-demand-mw"

_CSV_SOURCE_TITLE_RETIRED = (
    "India thermal capacity retired by source (retired-capacity-plants) API"
)
_CSV_VARIABLE_PREFIX_RETIRED = "thermal-capacity-retired-mw"


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
        "notes": (
            "National only — ICED does not publish state-level retired "
            "capacity. Captures only utility-scale thermal retirements; "
            "captive plants and renewables decommissioning are not in "
            "scope of the upstream feed."
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
    # B1.4.5 canonical CSV emission: each build also writes per-facet
    # long-format CSV via yen_gov.canonical.csv_writer.write_csv.
    csv_source_title: str
    csv_variable_prefix: str


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
            csv_source_title=_CSV_SOURCE_TITLE_CAPACITY,
            csv_variable_prefix=_CSV_VARIABLE_PREFIX_CAPACITY,
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
            csv_source_title=_CSV_SOURCE_TITLE_GEN,
            csv_variable_prefix=_CSV_VARIABLE_PREFIX_GEN,
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
            csv_source_title=_CSV_SOURCE_TITLE_PEAK,
            csv_variable_prefix=_CSV_VARIABLE_PREFIX_PEAK,
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
            csv_source_title=_CSV_SOURCE_TITLE_RETIRED,
            csv_variable_prefix=_CSV_VARIABLE_PREFIX_RETIRED,
        ),
    )


# ---------------------------------------------------------------------------
# Canonical CSV emission helpers (B1.4.5)
# ---------------------------------------------------------------------------


def _slug_segment(text: str) -> str:
    """Kebab-case a facet segment for use inside a ``variable_id``.

    Mirrors helpers in ``iced_ghg/ingest.py`` (B1.4.1, PR #635),
    ``iced_macro/ingest.py`` (B1.4.2, PR #636),
    ``iced_fuel/ingest.py`` (B1.4.3, PR #637), and
    ``iced_metatable/ingest.py`` (B1.4.4, PR #638). Parent plan
    section 21.6 / 21.12 ban ``__``; ADR-0044 bans grain prefixes.
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
    """Reduce ``YYYY-MM`` to integer fiscal-year start year.

    The canonical CSV column class ``datasets/data/datapoints/geo/*.csv``
    declares ``time`` as integer; iced_power parsers emit ``YYYY-04``
    via ``parser_kit.fy_to_period``. Raises on malformed input.
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

    Faceted indicators (capacity, generation, retired) split into one
    ``variable_id`` per facet value: ``<variable_prefix>-<facet-slug>``.
    Non-faceted indicators (peak demand) collapse to a single
    ``variable_id == variable_prefix``. Each output row carries the
    canonical 4 columns declared on file class
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

    B1.4.5 - both stores coexist (parent plan section 23.1); reader flip
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
# Faceted capacity emit (Row 3: ICED capacity-metatable -> geo_by_fuel)
# ---------------------------------------------------------------------------
#
# Per plan ruling R-D the ICED capacity-metatable state-grain feed lands as
# ONE faceted file
# datasets/data/datapoints/geo_by_fuel/installed-capacity-geographical-mw.csv
# (entity_id, time, fuel_type, value, source_id) instead of N per-fuel
# geo/*.csv files. The raw ICED sub-fuels collapse onto the closed 5-bucket
# fuel_type axis via SUB_FUEL_TO_CANONICAL (Row 1); the ECI st_code resolves
# to the LGD slug; the fiscal-year period reduces to its integer start year.

_CAPACITY_FACETED_FILE_CLASS = "datasets/data/datapoints/geo_by_fuel/*.csv"
_CAPACITY_FACETED_OUT_REL_DIR = "datasets/data/datapoints/geo_by_fuel"
_CAPACITY_FACETED_VARIABLE_ID = "installed-capacity-geographical-mw"

# Raw ICED facet labels (after kebab normalisation) that denote the
# publisher's state TOTAL rather than a fuel -- mapped to the `all`
# aggregate member. `all` is taken ONLY from such a published total, never
# synthesised as sum(parts) (the geo_by_fuel contract: `all` is the
# published aggregate, which may diverge from sum(parts)).
_PUBLISHED_TOTAL_LABELS: frozenset[str] = frozenset({"total", "all", "grand-total"})


@dataclass(frozen=True)
class CapacityFacetedResult:
    """Receipt for the single faceted capacity CSV emit."""

    variable_id: str
    artifact_path: Path
    row_count: int
    fuel_types: tuple[str, ...]
    skipped_unmapped: int


def _to_slug(eci_st_code: str) -> str:
    """ECI st_code -> LGD slug, with the country rollup passed through."""
    if eci_st_code == "IN":
        return "IN"
    return eci_to_lgd_slug(eci_st_code)


def _capacity_fuel_bucket(raw_facet: str) -> str:
    """Map a raw ICED capacity facet to its canonical fuel_type enum member."""
    norm = _slug_segment(str(raw_facet))
    if norm in _PUBLISHED_TOTAL_LABELS:
        return "all"
    return collapse_fuel(norm)


def build_capacity_faceted_rows(
    parsed_rows: list[dict[str, Any]],
    *,
    source_id: str,
) -> list[dict[str, Any]]:
    """Collapse ICED capacity-metatable rows into the faceted geo_by_fuel shape.

    Each parser row ``{entity_id(ECI), time("YYYY-04"), value, facet(raw fuel)}``
    maps to a canonical ``(slug, year, fuel_type)`` bucket: raw sub-fuels
    collapse via ``SUB_FUEL_TO_CANONICAL`` (``small-hydro``/``solar``/``wind``
    -> ``renewable``; ``oil-gas`` -> ``gas``), a publisher total label maps to
    ``all``, the ECI st_code resolves to the LGD slug, and the fiscal-year
    period reduces to its integer start year. Values colliding on the same
    ``(slug, year, fuel_type)`` bucket SUM (several renewable sub-fuels fold
    into one ``renewable`` row). ``write_csv`` sorts by the composite PK.
    """
    agg: dict[tuple[str, int, str], float] = {}
    for r in parsed_rows:
        facet = r.get("facet")
        if not isinstance(facet, str) or not facet:
            continue
        bucket = _capacity_fuel_bucket(facet)
        slug = _to_slug(str(r["entity_id"]))
        year = _period_to_year_int(str(r["time"]))
        value = float(r["value"])
        key = (slug, year, bucket)
        agg[key] = agg.get(key, 0.0) + value

    return [
        {
            "entity_id": slug,
            "time": year,
            "fuel_type": bucket,
            "value": value,
            "source_id": source_id,
        }
        for (slug, year, bucket), value in agg.items()
    ]


def emit_capacity_faceted(
    *, repo_root: Path, rows: list[dict[str, Any]]
) -> Path:
    """Write the single faceted ``geo_by_fuel/<variable_id>.csv`` file."""
    out_path = (
        repo_root / _CAPACITY_FACETED_OUT_REL_DIR / f"{_CAPACITY_FACETED_VARIABLE_ID}.csv"
    )
    return write_csv(
        path=out_path, file_class=_CAPACITY_FACETED_FILE_CLASS, rows=rows
    )


def ingest_capacity(
    *, repo_root: Path, raw_json_path: Path, decrypt: bool = False
) -> CapacityFacetedResult:
    """Read a staged capacity-metatable JSON, emit the faceted capacity CSV.

    Operator-staged local file (no network). ``/v1/capacity-metatable-data``
    is plain JSON (``decrypt=False``); the flag is accepted so an encrypted
    variant still loads via the auto-detecting ``load_iced_response``. Emits
    ONE faceted file
    ``datasets/data/datapoints/geo_by_fuel/installed-capacity-geographical-mw.csv``.
    """
    decoded = load_iced_response(
        raw_json_path.read_bytes(), decrypt=decrypt
    )
    parsed_rows, skipped = parse_capacity_metatable(decoded)
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_CAPACITY, _CSV_SOURCE_VINTAGE
    )
    rows = build_capacity_faceted_rows(parsed_rows, source_id=source_id)
    out = emit_capacity_faceted(repo_root=repo_root, rows=rows)
    return CapacityFacetedResult(
        variable_id=_CAPACITY_FACETED_VARIABLE_ID,
        artifact_path=out,
        row_count=len(rows),
        fuel_types=tuple(sorted({str(r["fuel_type"]) for r in rows})),
        skipped_unmapped=skipped,
    )


# ---------------------------------------------------------------------------
# Peak-demand entity-key fix (Row 4: single-value geo CSV, ECI -> LGD slug)
# ---------------------------------------------------------------------------
#
# Per plan ruling R-G the ICED peak-demand series stays a single-value
# geo/peak-electricity-demand-mw.csv; the only fix is re-pointing its entity
# output through the ECI -> LGD-slug translation so the rows FK-close against
# entities/geo.csv (the parser emits ECI st_codes; geo.csv keys on slugs).


@dataclass(frozen=True)
class PeakIngestResult:
    """Receipt for the single-value peak-demand CSV emit."""

    variable_id: str
    artifact_path: Path
    row_count: int
    skipped_unmapped: int


def build_peak_rows(
    parsed_rows: list[dict[str, Any]],
    *,
    source_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Build the single-value peak-demand geo rows, ECI st_code -> LGD slug.

    Each parser row ``{entity_id(ECI), time("YYYY-04"), value}`` keeps its
    single-value shape (no facet) but its ECI st_code resolves to the LGD slug
    (``IN`` country passthrough) and its fiscal-year period reduces to the
    integer start year. Returns a one-key ``by_variable`` map keyed on the
    peak variable_id, ready for ``emit_csv_variables``.
    """
    rows = [
        {
            "entity_id": _to_slug(str(r["entity_id"])),
            "time": _period_to_year_int(str(r["time"])),
            "value": r["value"],
            "source_id": source_id,
        }
        for r in parsed_rows
    ]
    return {_CSV_VARIABLE_PREFIX_PEAK: rows}


def ingest_peak(
    *, repo_root: Path, raw_json_path: Path, decrypt: bool = True
) -> PeakIngestResult:
    """Read a staged powerStatistics JSON, emit the slug-keyed peak-demand CSV.

    Operator-staged local file (no network). ``/energy/powerStatistics`` is
    AES-encrypted on the wire, so the staged blob is the CryptoJS envelope;
    ``decrypt=True`` (default) makes ``load_iced_response`` decrypt it before
    parsing (an already-plain file still loads). Emits the single-value file
    ``datasets/data/datapoints/geo/peak-electricity-demand-mw.csv`` with
    LGD-slug ``entity_id`` rows.
    """
    decoded = load_iced_response(
        raw_json_path.read_bytes(), decrypt=decrypt
    )
    _generation_rows, peak_rows, skipped = parse_power_statistics(decoded)
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_PEAK, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_peak_rows(peak_rows, source_id=source_id)
    written = emit_csv_variables(repo_root=repo_root, by_variable=by_variable)
    return PeakIngestResult(
        variable_id=_CSV_VARIABLE_PREFIX_PEAK,
        artifact_path=written[0],
        row_count=len(by_variable[_CSV_VARIABLE_PREFIX_PEAK]),
        skipped_unmapped=skipped,
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

