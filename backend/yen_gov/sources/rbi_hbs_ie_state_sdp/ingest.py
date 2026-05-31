"""Adapter for RBI HBS-IE state SDP tables.

No network. Reads the cached HBS-IE 2024-25 state SDP workbooks from
``.runtime/raw/rbi/handbook_economy_2024_25/`` and writes the legacy folded
indicator artifacts under ``datasets/indicators/in/economy/`` through the
backend artifact writer.

This replaces the retired ``tools/rbi_hbs_ingest_state_gdp.py`` script. The
adapter keeps the source-specific workbook walker here while reusing the shared
RBI primitives for state-name mapping, value coercion, and fiscal-year parsing.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import openpyxl

from yen_gov.core.io import Source, write_artifact
from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
from yen_gov.sources.rbi_hbs import (
    ALL_INDIA_NAMES,
    HBS_IE_LANDING,
    LICENSE_RBI,
    NAME_TO_ECI,
    coerce_value,
    fy_label_to_time,
)

INDICATOR_SCHEMA_FILE = "indicator.schema.json"

CACHE_RELDIR = Path(".runtime/raw/rbi/handbook_economy_2024_25")

SNAPSHOT_URLS: dict[str, str] = {
    "T05": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/05T_2908202556D0D1A9FA0C4615A7889EC1F025BACE.XLSX",
    "T06": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/06T_290820258621D22235014AC19EE27C859382FEAF.XLSX",
    "T09": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/09T_2908202582956A1D380840F5870B18841EEEF815.XLSX",
    "T10": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/10T_290820257B1763CF72624007ABF4F4E48CC941B3.XLSX",
}

BASE_PRIORITY = ("2011-12", "2004-05", "1999-2000", "1993-94")

SERIES_BREAKS_NSDP: list[dict[str, str]] = [
    {
        "at_time": "1999-04",
        "kind": "rebase",
        "note": "MoSPI rebase: 1993-94 -> 1999-2000 base.",
    },
    {
        "at_time": "2004-04",
        "kind": "rebase",
        "note": "MoSPI rebase: 1999-2000 -> 2004-05 base.",
    },
    {
        "at_time": "2011-04",
        "kind": "definition_change",
        "note": (
            "MoSPI rebase to 2011-12 base and switched headline aggregate "
            "from NSDP at factor cost to NSDP at basic prices. Growth rates "
            "spanning 2010-11 -> 2011-12 are not strictly comparable."
        ),
    },
    {
        "at_time": "2014-04",
        "kind": "coverage_change",
        "note": (
            "Telangana carved out of Andhra Pradesh on 2 June 2014. RBI "
            "back-projects S29 to 2011-12 by carving from undivided AP; "
            "pre-2014-15 S29 values are MoSPI back-estimates."
        ),
    },
    {
        "at_time": "2019-04",
        "kind": "coverage_change",
        "note": (
            "J&K reorganisation in August 2019: U08 series from 2019-20 "
            "onwards covers the UT of Jammu and Kashmir only; Ladakh is not "
            "separately reported in this RBI table."
        ),
    },
]


class RBIHBSIEStateSDPCacheMissing(RuntimeError):
    """No cached HBS-IE state SDP workbook to read."""


@dataclass(frozen=True)
class TableSpec:
    table_key: str
    filename: str
    table_label: str


@dataclass(frozen=True)
class IndicatorSpec:
    indicator_id: str
    title: str
    table: TableSpec
    value_kind: str
    unit: str
    short_unit: str | None
    description: str
    notes: str
    denominator: dict[str, str] | None = None


@dataclass(frozen=True)
class WorkbookData:
    content: bytes
    fetched_at: datetime
    url: str


@dataclass(frozen=True)
class IndicatorIngestResult:
    indicator_id: str
    artifact_path: Path
    row_count: int
    entity_count: int
    period_start: str
    period_end: str


@dataclass(frozen=True)
class IngestResult:
    indicators: tuple[IndicatorIngestResult, ...]


TABLE_T05 = TableSpec(
    table_key="T05",
    filename="T05_NSDP_Statewise_Current.xlsx",
    table_label="Table 5: Net State Domestic Product - State-wise (At Current Prices)",
)
TABLE_T06 = TableSpec(
    table_key="T06",
    filename="T06_NSDP_Statewise_Constant.xlsx",
    table_label="Table 6: Net State Domestic Product - State-wise (At Constant Prices)",
)
TABLE_T09 = TableSpec(
    table_key="T09",
    filename="T09_PCNSDP_Statewise_Current.xlsx",
    table_label="Table 9: Per Capita Net State Domestic Product - State-wise (At Current Prices)",
)
TABLE_T10 = TableSpec(
    table_key="T10",
    filename="T10_PCNSDP_Statewise_Constant.xlsx",
    table_label="Table 10: Per Capita Net State Domestic Product - State-wise (At Constant Prices)",
)

PER_CAPITA_SPECS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        indicator_id="economy/per_capita_nsdp_current_inr",
        title="Per-capita NSDP (current prices, by state)",
        table=TABLE_T09,
        value_kind="currency",
        unit="INR",
        short_unit="INR",
        description=(
            "Per-capita Net State Domestic Product at current prices, spliced "
            "across MoSPI's 1999-2000, 2004-05, and 2011-12 base years. "
            "The most recent base is kept for overlapping years; each row's "
            "vintage records which base produced the value."
        ),
        notes=(
            "Source: RBI Handbook of Statistics on Indian Economy 2024-25 "
            "edition, Table 9. RBI's per-capita series begins in 2000-01. "
            "All-India per-capita NNI is included as the national reference "
            "line when the workbook publishes it."
        ),
        denominator={
            "what": "state mid-year population (MoSPI / RGI)",
            "price_basis": "current",
            "source_artifact": "demography/state_population_lakhs",
            "note": "Per-capita = NSDP divided by state mid-year population estimate",
        },
    ),
    IndicatorSpec(
        indicator_id="economy/per_capita_nsdp_constant_inr",
        title="Per-capita NSDP (constant prices, spliced)",
        table=TABLE_T10,
        value_kind="currency",
        unit="INR",
        short_unit="INR",
        description=(
            "Real per-capita NSDP, spliced across MoSPI's 1999-2000, "
            "2004-05, and 2011-12 base years. The most recent base is kept "
            "for overlapping years; each row's vintage records the chosen "
            "base year."
        ),
        notes=(
            "Source: RBI Handbook of Statistics on Indian Economy 2024-25 "
            "edition, Table 10. Pre-2011-12 figures are real per-capita "
            "NSDP at factor cost; 2011-12 onwards are at basic prices. "
            "Cross-base growth rates are not strictly comparable."
        ),
        denominator={
            "what": "state mid-year population (MoSPI / RGI)",
            "price_basis": "constant",
            "source_artifact": "demography/state_population_lakhs",
            "note": "Per-capita = real NSDP divided by state mid-year population estimate",
        },
    ),
)


def _is_year(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    label = value.strip()
    if len(label) == 7 and label[4] == "-" and label[:4].isdigit() and label[5:].isdigit():
        return label
    return None


def _is_base_marker(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if "Base Year" not in value and "Base :" not in value:
        return None
    inside = value.replace("(", "").replace(")", "").strip()
    parts = inside.split(":")
    if len(parts) < 2:
        return None
    return parts[-1].strip()


def parse_workbook(content: bytes) -> dict[str, dict[str, dict[str, float]]]:
    """Return ``{entity_id: {time: {base: value}}}`` for every state column."""
    out: dict[str, dict[str, dict[str, float]]] = {}
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    try:
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            header_idx = None
            for idx, row in enumerate(rows[:8]):
                cell = row[1] if len(row) > 1 else None
                if isinstance(cell, str) and cell.strip() in (
                    "Year",
                    "State / Union Territory",
                ):
                    header_idx = idx
                    break
            if header_idx is None:
                continue

            header = rows[header_idx]
            col_to_entity: dict[int, str] = {}
            for col_idx, cell in enumerate(header):
                if not isinstance(cell, str):
                    continue
                name = cell.strip()
                if name in NAME_TO_ECI:
                    col_to_entity[col_idx] = NAME_TO_ECI[name]
                elif name in ALL_INDIA_NAMES:
                    col_to_entity[col_idx] = "IN"

            current_base: str | None = None
            for row in rows[header_idx + 1 :]:
                label = row[1] if len(row) > 1 else None
                base = _is_base_marker(label)
                if base:
                    current_base = base
                    continue
                year = _is_year(label)
                if not year or current_base is None:
                    continue
                time = fy_label_to_time(year)
                if time is None:
                    continue
                for col_idx, entity_id in col_to_entity.items():
                    value = coerce_value(row[col_idx]) if col_idx < len(row) else None
                    if value is None:
                        continue
                    out.setdefault(entity_id, {}).setdefault(time, {})[
                        current_base
                    ] = value
    finally:
        wb.close()
    return out


def collapse_to_long(parsed: dict[str, dict[str, dict[str, float]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity_id in sorted(parsed):
        for time in sorted(parsed[entity_id]):
            by_base = parsed[entity_id][time]
            chosen_base = next((base for base in BASE_PRIORITY if base in by_base), None)
            if chosen_base is None:
                continue
            rows.append(
                {
                    "entity_id": entity_id,
                    "time": time,
                    "value": by_base[chosen_base],
                    "vintage": f"Base {chosen_base}",
                }
            )
    return rows


def _resolve_workbook(*, repo_root: Path, table: TableSpec) -> WorkbookData:
    relpath = CACHE_RELDIR / table.filename
    path = repo_root / relpath
    if not path.exists():
        raise RBIHBSIEStateSDPCacheMissing(
            f"No cached RBI HBS-IE state SDP workbook at {relpath.as_posix()}.\n"
            f"  (a) Open {HBS_IE_LANDING}\n"
            f"  (b) Pick the latest Handbook of Statistics on Indian Economy edition.\n"
            f"  (c) Download {table.table_label} as XLSX.\n"
            f"  (d) Save it as {relpath.as_posix()} relative to the repo root.\n"
            f"For the 2024-25 edition, the pinned direct URL is {SNAPSHOT_URLS[table.table_key]}."
        )
    fetched_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(
        microsecond=0
    )
    return WorkbookData(
        content=path.read_bytes(),
        fetched_at=fetched_at,
        url=SNAPSHOT_URLS[table.table_key],
    )


def _coverage(rows: list[dict[str, Any]]) -> tuple[str, str, int]:
    times = sorted({str(row["time"]) for row in rows})
    entities = sorted({str(row["entity_id"]) for row in rows})
    if not times:
        raise ValueError("cannot build coverage for empty row set")
    return times[0], times[-1], len(entities)


def _common_indicator_fields() -> dict[str, Any]:
    return {
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "direction": "higher_is_better",
        "scale_hint": "linear",
        "icon": "trending-up",
        "attribution_geography": "where_resident",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "state",
        "methodology_vintage": (
            "MoSPI multi-base spliced (1993-94 / 1999-2000 / 2004-05 / "
            "2011-12); RBI Handbook 2024-25 edition"
        ),
        "series_breaks": SERIES_BREAKS_NSDP,
    }


def _source_entries(workbooks: list[WorkbookData]) -> list[Source]:
    sources = [Source(url=workbook.url, fetched_at=workbook.fetched_at) for workbook in workbooks]
    latest = max(workbook.fetched_at for workbook in workbooks)
    sources.append(Source(url=HBS_IE_LANDING, fetched_at=latest))
    return sources


def _write_indicator(
    *,
    repo_root: Path,
    indicator_id: str,
    payload: dict[str, Any],
    sources: list[Source],
    indicator_schema: dict[str, Any],
) -> IndicatorIngestResult:
    out_dir = repo_root / "datasets" / "indicators" / "in" / "economy"
    leaf = indicator_id.split("/")[-1] + ".json"
    path = out_dir / leaf
    written = write_artifact(
        path=path,
        schema_id=schema_id(INDICATOR_SCHEMA_FILE),
        schema_version=schema_version(INDICATOR_SCHEMA_FILE),
        payload=payload,
        sources=sources,
        schema_for_validation=indicator_schema,
    )
    start, end, entity_count = _coverage(payload["rows"])
    return IndicatorIngestResult(
        indicator_id=indicator_id,
        artifact_path=written,
        row_count=len(payload["rows"]),
        entity_count=entity_count,
        period_start=start,
        period_end=end,
    )


def _build_per_capita_payload(
    *,
    spec: IndicatorSpec,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    start, end, entity_count = _coverage(rows)
    indicator = {
        "id": spec.indicator_id,
        "title": spec.title,
        "description": spec.description,
        "value_kind": spec.value_kind,
        "unit": spec.unit,
        "notes": spec.notes,
        **_common_indicator_fields(),
    }
    if spec.short_unit is not None:
        indicator["short_unit"] = spec.short_unit
    if spec.denominator is not None:
        indicator["denominator"] = spec.denominator
    return {
        "license": LICENSE_RBI,
        "coverage": {
            "spatial": f"India (states + UTs); {entity_count} entities",
            "temporal": f"{start}..{end}",
            "admin_level": "state",
        },
        "indicator": indicator,
        "rows": rows,
    }


def _build_nsdp_payload(
    *,
    current_rows: list[dict[str, Any]],
    constant_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for facet, source_rows in (("current", current_rows), ("constant", constant_rows)):
        for row in source_rows:
            rows.append({**row, "facet": facet})
    rows.sort(key=lambda row: (row["entity_id"], row["time"], row["facet"]))
    start, end, entity_count = _coverage(rows)
    return {
        "license": LICENSE_RBI,
        "coverage": {
            "spatial": f"India (states + UTs); {entity_count} entities",
            "temporal": f"{start}..{end}",
            "admin_level": "state",
        },
        "indicator": {
            "id": "economy/nsdp_inr_crore",
            "title": "Net State Domestic Product (INR crore, current and constant prices)",
            "description": (
                "Net State Domestic Product of each state and union territory "
                "in INR crore, faceted by price basis. Use current prices for "
                "tax-base sizing and constant prices for state-level real "
                "growth analysis."
            ),
            "value_kind": "currency",
            "unit": "INR (crore)",
            "short_unit": "INR cr",
            "notes": (
                "Source: RBI Handbook of Statistics on Indian Economy 2024-25 "
                "edition, Tables 5 and 6. Pre-2011-12 figures are NSDP at "
                "factor cost; 2011-12 onwards are at basic prices. Cross-base "
                "growth rates are not strictly comparable."
            ),
            **_common_indicator_fields(),
        },
        "rows": rows,
    }


def ingest(*, repo_root: Path) -> IngestResult:
    """Read cached workbooks and write the three state SDP artifacts."""
    indicator_schema = schema_doc(INDICATOR_SCHEMA_FILE)

    current_workbook = _resolve_workbook(repo_root=repo_root, table=TABLE_T05)
    constant_workbook = _resolve_workbook(repo_root=repo_root, table=TABLE_T06)
    current_rows = collapse_to_long(parse_workbook(current_workbook.content))
    constant_rows = collapse_to_long(parse_workbook(constant_workbook.content))
    if not current_rows or not constant_rows:
        raise ValueError("empty rows for economy/nsdp_inr_crore")

    results = [
        _write_indicator(
            repo_root=repo_root,
            indicator_id="economy/nsdp_inr_crore",
            payload=_build_nsdp_payload(
                current_rows=current_rows,
                constant_rows=constant_rows,
            ),
            sources=_source_entries([current_workbook, constant_workbook]),
            indicator_schema=indicator_schema,
        )
    ]

    for spec in PER_CAPITA_SPECS:
        workbook = _resolve_workbook(repo_root=repo_root, table=spec.table)
        rows = collapse_to_long(parse_workbook(workbook.content))
        if not rows:
            raise ValueError(f"empty rows for {spec.indicator_id}")
        results.append(
            _write_indicator(
                repo_root=repo_root,
                indicator_id=spec.indicator_id,
                payload=_build_per_capita_payload(spec=spec, rows=rows),
                sources=_source_entries([workbook]),
                indicator_schema=indicator_schema,
            )
        )

    return IngestResult(indicators=tuple(results))