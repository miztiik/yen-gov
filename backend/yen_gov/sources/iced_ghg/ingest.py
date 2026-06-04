"""Orchestrator for the ICED GHG sub-sector adapter.

Fetches the GHG energy-full endpoint (one HTTP call, one cached
response) and emits a single sub-sector drill-down indicator under
``datasets/indicators/in/environment/``.
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

from .parsers import parse_ghg_subsector

# B1.4.1 - canonical CSV citation triple for the GHG sub-sector indicator.
# Producer / title / vintage match the ICED-family convention established in
# `canonical/adapters/energy/_shared.py` (NITI Aayog ICED endpoints share the
# producer string; vintage = operator snapshot FY per ADR-0042). The triple
# is hashed at write time via `derive_source_id`; the actual row in
# `datasets/data/entities/source.csv` is populated by B2a. Until then the
# fk-validator gate is dark on this hash; that is by design (sub-plan
# "Pre-flight - source-id + concept-id readiness").
_CSV_SOURCE_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
_CSV_SOURCE_TITLE = (
    "GHG Emissions by Sub-sector (Energy endpoint, full coverage) API"
)
_CSV_SOURCE_VINTAGE = "2024-25"
_CSV_VARIABLE_PREFIX = "ghg-emissions-ggco2e"
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"


@dataclass(frozen=True)
class IndicatorEmitResult:
    indicator_id: str
    artifact_path: Path
    row_count: int
    time_min: str
    time_max: str


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
GHG_PATH = "/climate-environment/ghg-emissions/energy"


def _indicator_subsector() -> dict[str, Any]:
    return {
        "id": "environment/india_ghg_emissions_by_subsector_ggco2e",
        "title": "India's greenhouse-gas emissions by sub-sector (Gg CO₂-equivalent)",
        "description": (
            "National greenhouse-gas emissions one level deeper than the "
            "headline by-sector view: each row is a (sector, sub-sector) "
            "pair, e.g. 'Energy / Transport' or 'Agriculture / Rice "
            "Cultivation'. Reported as Gigagrams of CO₂-equivalent per year "
            "(1 Gg = 1 kt = 1000 tonnes). Drawn from the same India BUR "
            "submissions to UNFCCC as the parent sector indicator; the "
            "sector totals here will reconcile to "
            "`environment/india_ghg_emissions_mtco2e_by_sector` when summed "
            "within each sector."
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
        "methodology_vintage": (
            "IPCC 2006 guidelines (BUR-3 / BUR-4 submissions, MoEFCC). "
            "Coverage: 1994, 2000, 2007, then annual 2010-2020."
        ),
        "chart_type": "stacked-trend",
        "notes": (
            "Facets are encoded as 'Sector|SubSector' strings. The 'Energy "
            "Sector / Total' row is present for back-compat with the older "
            "ICED endpoint shape but duplicates the sum of the five 'Energy "
            "/ ...' sub-sectors — renderers should pick one or the other. "
            "Land-Use, Land-Use Change & Forestry sub-sector coverage is "
            "uneven (Harvested Wood Products has only 2020; Fuelwood use "
            "only 2000 + 2007) — that reflects when MoEFCC began reporting "
            "each line, not data loss."
        ),
        "series_breaks": [
            {
                "at_time": "2010",
                "kind": "coverage_change",
                "note": "Reporting becomes annual from 2010; before 2010 only 1994, 2000, 2007 are published.",
            }
        ],
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
    coverage_temporal: str,
    out_rel: str,
) -> IndicatorEmitResult:
    payload = {
        "coverage": {
            "spatial": "India (national)",
            "temporal": coverage_temporal,
            "admin_level": None,
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
    times = [r["time"] for r in rows]
    return IndicatorEmitResult(
        indicator_id=indicator_meta["id"],
        artifact_path=artifact_path,
        row_count=len(rows),
        time_min=min(times) if times else "",
        time_max=max(times) if times else "",
    )


def _slug_segment(text: str) -> str:
    """Kebab-case a facet segment for use inside a `variable_id`.

    Plan section 21.6 / 21.12 ban `__`; ADR-0044 bans grain-prefixes. We
    lower-case, replace any non-alphanumeric run with a single `-`, and
    strip leading/trailing `-`. The result is always non-empty for
    non-blank input (the parser already drops blank facet segments).
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


def build_csv_variables(
    parsed_rows: list[dict[str, Any]], *, source_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Split parser output into per-facet CSV row lists keyed by `variable_id`.

    The GHG indicator carries a `Sector|SubSector` facet column (parser
    output). The B1.2 `write_csv` does not yet support facet columns
    (sub-plan §B1.4.1..9 point 7), so we split into one `variable_id`
    per facet pair: `ghg-emissions-ggco2e-<sector>-<subsector>`. Each
    output row carries the canonical 4 columns declared on file class
    `datasets/data/datapoints/geo/*.csv`: `entity_id`, `time`, `value`,
    `source_id`. `time` is the integer year; `value` is the numeric Gg
    CO2e emission.
    """
    by_variable: dict[str, list[dict[str, Any]]] = {}
    for row in parsed_rows:
        facet = row["facet"]
        sector, _, subsector = facet.partition("|")
        variable_id = (
            f"{_CSV_VARIABLE_PREFIX}-"
            f"{_slug_segment(sector)}-{_slug_segment(subsector)}"
        )
        by_variable.setdefault(variable_id, []).append({
            "entity_id": row["entity_id"],
            "time": int(row["time"]),
            "value": row["value"],
            "source_id": source_id,
        })
    return by_variable


def emit_csv_variables(
    *, repo_root: Path, by_variable: dict[str, list[dict[str, Any]]]
) -> tuple[Path, ...]:
    """Write each `variable_id` to `datasets/data/datapoints/geo/<id>.csv`."""
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


def ingest_iced_ghg(
    *, repo_root: Path, client: IcedClient | None = None
) -> IngestSummary:
    if client is None:
        client = IcedClient(host=API_HOST, polite_delay=0.5)
    schema_for_validation = schema_doc("indicator.schema.json")
    schema_id_str = schema_id("indicator.schema.json")
    schema_version_str = schema_version("indicator.schema.json")

    response = client.get(GHG_PATH)
    rows = parse_ghg_subsector(response.decrypted)
    sources = [Source(url=response.url, fetched_at=response.fetched_at)]
    times = sorted({r["time"] for r in rows})
    coverage = f"{times[0]}..{times[-1]}" if times else "unknown"

    result = _emit(
        repo_root=repo_root,
        schema_for_validation=schema_for_validation,
        schema_id_str=schema_id_str,
        schema_version_str=schema_version_str,
        indicator_meta=_indicator_subsector(),
        rows=rows,
        sources=sources,
        coverage_temporal=coverage,
        out_rel="datasets/indicators/in/environment/india_ghg_emissions_by_subsector_ggco2e.json",
    )

    # B1.4.1 - canonical long-format CSV emission ALONGSIDE the legacy
    # meadow/indicator JSON write. Existing JSON output stays in place
    # (instead-of deletion is deferred to B3 per parent plan §23.1 and
    # sub-plan per-family point 6). Reader flip is X1a; until then both
    # stores live on disk side-by-side.
    csv_source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(rows, source_id=csv_source_id)
    emit_csv_variables(repo_root=repo_root, by_variable=by_variable)

    # PR-A5a-tail: derive orchestrator fetched_at from upstream per-fetch
    # timestamp instead of wall-clock datetime.now().
    return IngestSummary(
        fetched_at=response.fetched_at,
        results=(result,),
    )
