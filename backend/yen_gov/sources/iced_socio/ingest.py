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

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.iced_common import IcedClient

from .parsers import (
    parse_ghg_economy_wide,
    parse_per_capita_consumption,
)


# ---------------------------------------------------------------------------
# Canonical CSV emission constants (B1.4.6)
# ---------------------------------------------------------------------------
#
# Both iced_socio indicators are NITI Aayog ICED endpoints; vintage =
# operator snapshot FY per ADR-0042. derive_source_id() hashes the
# triple at write time; the row in `datasets/data/entities/source.csv`
# is populated by B2a (sub-plan section "Pre-flight"). variable_ids
# honour parent plan section 21.6 / 21.12 (no `__`) and ADR-0044 (no
# grain prefix). Per-facet split because csv_writer does not yet accept
# facet columns (sub-plan B1.4.1..9 #7). concept_id binding is
# DEFERRED to B2a; recorded as DEFER marker in the PR body.
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"
_CSV_SOURCE_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
_CSV_SOURCE_VINTAGE = "2024-25"

_CSV_SOURCE_TITLE_PCC = (
    "State per-capita private consumption (per-capita-consumption) API"
)
_CSV_VARIABLE_PREFIX_PCC = "per-capita-consumption-inr"

# Distinct from iced_ghg's `ghg-emissions-ggco2e-<sector>-<subsector>`
# (energy-only subsector breakdown). This series is the economy-wide
# national total faceted by sector only (no subsector).
_CSV_SOURCE_TITLE_GHG = (
    "India economy-wide GHG emissions by sector (economy-wide-emission) API"
)
_CSV_VARIABLE_PREFIX_GHG = "ghg-emissions-by-sector-ggco2e"


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
    # B1.4.6 canonical CSV emission: each build also writes long-format
    # CSV via yen_gov.canonical.csv_writer.write_csv.
    csv_source_title: str
    csv_variable_prefix: str


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
        csv_source_title=_CSV_SOURCE_TITLE_PCC,
        csv_variable_prefix=_CSV_VARIABLE_PREFIX_PCC,
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
        csv_source_title=_CSV_SOURCE_TITLE_GHG,
        csv_variable_prefix=_CSV_VARIABLE_PREFIX_GHG,
    )


def _all_builds() -> tuple[_IndicatorBuild, ...]:
    return (
        _per_capita_consumption_meta(),
        _ghg_economy_wide_meta(),
    )


# ---------------------------------------------------------------------------
# Canonical CSV emission helpers (B1.4.6)
# ---------------------------------------------------------------------------


def _slug_segment(text: str) -> str:
    """Kebab-case a facet segment for use inside a ``variable_id``.

    Mirrors helpers in sibling iced_* ingests (B1.4.1..5). Parent plan
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
    """Reduce ``YYYY`` or ``YYYY-MM`` to integer year.

    The canonical CSV column class ``datasets/data/datapoints/geo/*.csv``
    declares ``time`` as integer. iced_socio parsers emit ``YYYY-04``
    (fiscal_year) for per-capita consumption and bare ``YYYY`` (calendar
    year) for GHG economy-wide. Raises on malformed input.
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

    Faceted indicators (GHG by sector) split into one ``variable_id``
    per facet value: ``<variable_prefix>-<facet-slug>``. Non-faceted
    indicators (per-capita consumption) collapse to a single
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

    B1.4.6 - both stores coexist (parent plan section 23.1); reader flip
    is X1a. ``source_id`` derived via ADR-0042 from
    (producer, title, vintage); one ``variable_id`` per facet
    (csv_writer facet-column support deferred).
    """
    source_id = derive_source_id(_CSV_SOURCE_PRODUCER, title, _CSV_SOURCE_VINTAGE)
    by_variable = build_csv_variables(
        parsed_rows, source_id=source_id, variable_prefix=variable_prefix
    )
    return emit_csv_variables(repo_root=repo_root, by_variable=by_variable)


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

        # B1.4.6 - canonical CSV emission alongside legacy artifact.
        _emit_csv_for(
            repo_root=repo_root,
            parsed_rows=rows,
            title=b.csv_source_title,
            variable_prefix=b.csv_variable_prefix,
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
