"""Orchestrator for the data.gov.in OGD CSV ingest.

Filesystem boundary only — no network. CSV downloads are operator-
fetched (one-time captcha solve on the OGD resource page) and dropped
under ``.runtime/raw/datagovin/<indicator_leaf>.csv``. This module:

  1. Resolves a CSV file from the cache for each shipped indicator.
  2. Runs the pure parser (:mod:`.parsers`) over the bytes.
  3. Writes a ``datasets/indicators/in/<country>/fiscal/<leaf>.json``
     artifact conforming to ``datasets/schemas/indicator.schema.json``.

If the CSV is missing the ingest fails LOUDLY with operator
instructions — better than emitting a partial artifact.

See ``docs/architecture/backend/sources-datagovin-ogd.md`` for the
indicator → resource mapping and the gross-vs-net methodology note.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.core.io import Source, write_artifact

from .parsers import (
    SHIPPED_SPECS,
    IndicatorSpec,
    ParsedIndicator,
    parse_csv,
)
from .urls import OGD_AUTHORITY_URL, ResourceMeta, resource_for


DATAGOVIN_SOURCE_NAME = "datagovin"


# B1.6.2 - canonical CSV citation triple for the data.gov.in OGD ingest
# (sub-plan `TODO/20260604-b1.6-misc-repoint-subplan.md`). Each shipped
# indicator binds to one resource; producer / title / vintage match the
# per-family convention declared in sub-plan section B1.6.1..7 point 8.
# Vintage per ADR-0042 is the publisher edition string: the answer-month
# of the Rajya Sabha Session 260 Unstarred Q1323 that backs the OGD
# resource (answered 1 August 2023 -> `2023-08`). The fk-validator gate
# is dark on this hash until `entities/source.csv` lands (B2a), by
# design per sub-plan section "Pre-flight - source-id + concept-id
# readiness".
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"

# Per-indicator citation + canonical variable_id mapping.
# variable_id honours parent plan section 21.6 / 21.12 (no `__`) and
# ADR-0044 (no grain prefix; kebab-case `<measure>-<unit>-<facet>`).
_INDICATOR_TO_CSV: dict[str, dict[str, str]] = {
    "fiscal/centre_transfers_gross": {
        "variable_id": "centre-transfers-inr-crore-gross",
        "producer": "Ministry of Finance, Government of India",
        "title": (
            "State-wise Details of Total Revenue Receipts, with own "
            "Receipts and Centre Transfers (FY17-FY23, Actuals)"
        ),
        "vintage": "2023-08",
    },
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DataGovInCsvMissing(RuntimeError):
    """No cached CSV for an indicator. Operator must download it from
    the OGD resource page (one-time captcha solve)."""


# ---------------------------------------------------------------------------
# Per-indicator metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndicatorMeta:
    indicator_id: str
    title: str
    description: str
    direction: str
    comparability: str
    attribution_geography: str
    icon: str
    funding_split_state_pct: int
    notes: str
    value_kind: str = "currency"
    unit: str = "INR (crore)"
    series_breaks: tuple[dict[str, str], ...] = ()


INDICATOR_META: dict[str, IndicatorMeta] = {
    "fiscal/centre_transfers_gross": IndicatorMeta(
        indicator_id="fiscal/centre_transfers_gross",
        title="Centre transfers to states (gross)",
        description=(
            "Gross transfers from the Central Government to each State / "
            "Union Territory in a fiscal year, computed as the sum of "
            "(a) the state's share in central taxes (Finance Commission "
            "devolution) and (b) Grants-in-Aid (Finance Commission "
            "grants + centrally-sponsored scheme grants + special-purpose "
            "transfers). Distinct from the 'Net' figure RBI publishes, "
            "which subtracts repayments of loans previously advanced by "
            "the Centre. This is the *gross* outflow side of fiscal "
            "federalism."
        ),
        direction="neutral",
        comparability="comparable_with_normalisation",
        attribution_geography="where_administered",
        icon="landmark",
        funding_split_state_pct=0,
        value_kind="currency",
        unit="INR (crore)",
        notes=(
            "Source: data.gov.in OGD resource "
            "1f2e77f0-6742-4671-ae29-8836d2110a5c, populated from the "
            "Rajya Sabha Session 260 Unstarred Question 1323 "
            "(answered 1 August 2023). Coverage is 7 fiscal years "
            "(2016-17 to 2022-23 Actuals), 28 states + Delhi + "
            "Puducherry. Computed as Col.(4) Share in Central Taxes "
            "+ Col.(5) Grants-in-Aid. This is a *gross* figure and is "
            "intentionally NOT merged with the RBI Statement 17 'Net "
            "transfers from Centre' indicator (FY24+) — the two have "
            "a real definitional difference (RBI subtracts loan "
            "repayments). When both indicators overlap on FY24, "
            "compare carefully."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Cache resolution
# ---------------------------------------------------------------------------


def _cache_path(repo_root: Path, indicator_id: str) -> Path:
    """Where the operator drops the CSV download."""
    leaf = indicator_id.split("/")[-1]
    return repo_root / ".runtime" / "raw" / DATAGOVIN_SOURCE_NAME / f"{leaf}.csv"


@dataclass(frozen=True)
class CachedCsv:
    content: bytes
    fetched_at: datetime  # mtime of the cached file (operator-honest)
    meta: ResourceMeta


def _resolve_csv(*, indicator_id: str, repo_root: Path) -> CachedCsv:
    meta = resource_for(indicator_id)
    if meta is None:
        raise DataGovInCsvMissing(
            f"No data.gov.in resource pinned for {indicator_id!r}. "
            f"Add an entry to backend/yen_gov/sources/datagovin_ogd/urls.py."
        )
    cache_path = _cache_path(repo_root, indicator_id)
    if not cache_path.is_file():
        raise DataGovInCsvMissing(
            f"\nNo cached CSV for {indicator_id!r}.\n\n"
            f"Operator recipe (one-time captcha solve):\n"
            f"  1. Open {meta.portal_page_url}\n"
            f"  2. Click the Download button → fill the purpose form → "
            f"solve the captcha → click Download\n"
            f"  3. Save the CSV as: "
            f"{cache_path.relative_to(repo_root).as_posix()}\n"
            f"  4. Re-run this command.\n\n"
            f"Subsequent ingests reuse the cached CSV — no re-download "
            f"unless the upstream resource is republished."
        )
    mtime = datetime.fromtimestamp(
        cache_path.stat().st_mtime, tz=timezone.utc,
    ).replace(microsecond=0)
    return CachedCsv(
        content=cache_path.read_bytes(),
        fetched_at=mtime,
        meta=meta,
    )


# ---------------------------------------------------------------------------
# Artifact builder
# ---------------------------------------------------------------------------


def _coverage_temporal(parsed: ParsedIndicator) -> str:
    times = sorted({r.time for r in parsed.rows})
    if not times:
        return "unknown"
    return f"{times[0]}..{times[-1]}"


def _build_payload(
    *,
    spec: IndicatorSpec,
    parsed: ParsedIndicator,
    cached: CachedCsv,
) -> dict[str, Any]:
    meta = INDICATOR_META[spec.indicator_id]

    rows = [
        {"entity_id": r.entity_id, "time": r.time, "value": r.value}
        for r in parsed.rows
    ]

    notes_parts = [meta.notes]
    if parsed.unmatched_states:
        notes_parts.append(
            "Labels not mapped to ECI codes (excluded from this artifact): "
            + ", ".join(sorted(set(parsed.unmatched_states)))
        )

    payload: dict[str, Any] = {
        "license": {
            "id": "GoI-OpenData",
            "name": "Government of India Open Data License",
            "url": "https://www.data.gov.in/government-open-data-license-india",
            "redistributable": True,
        },
        "coverage": {
            "spatial": "India (states + Delhi + Puducherry)",
            "temporal": _coverage_temporal(parsed),
            "admin_level": "state",
        },
        "indicator": {
            "id": spec.indicator_id,
            "title": meta.title,
            "description": meta.description,
            "entity_kind": "state",
            "time_grain": "fiscal_year",
            "value_kind": meta.value_kind,
            "direction": meta.direction,
            "scale_hint": "linear",
            "unit": meta.unit,
            "icon": meta.icon,
            "attribution_geography": meta.attribution_geography,
            "comparability": meta.comparability,
            "funding_split": {
                "centre_pct": 100 - meta.funding_split_state_pct,
                "state_pct": meta.funding_split_state_pct,
                "source": "definition (transfers from Centre)",
            },
            "implementing_authority": "centre",
            "methodology_vintage": (
                f"Rajya Sabha Session 260 Q1323 (Aug 2023) via "
                f"data.gov.in OGD CSV; cached file mtime "
                f"{cached.fetched_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}"
            ),
            "notes": " ".join(notes_parts).strip(),
        },
        "rows": rows,
    }

    if meta.series_breaks:
        payload["indicator"]["series_breaks"] = list(meta.series_breaks)

    return payload


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndicatorIngestResult:
    indicator_id: str
    artifact_path: Path
    csv_cache_path: Path
    fetched_at: datetime
    record_count: int
    row_count: int


@dataclass(frozen=True)
class IngestResult:
    indicators: tuple[IndicatorIngestResult, ...]


def _fy_period_to_time(period: str) -> int:
    """Encode a canonical FY period string ``YYYY-MM`` as integer ``YYYYMM``.

    The geo datapoints file class declares ``time`` as ``integer``.
    Parser emits ``"2016-04"`` (fy_span) or ``"2017-04"`` (fy_end_year);
    both shapes share ``YYYY-MM``. Fail-fast on shape drift - no silent
    coercion (CLAUDE.md anti-patterns).
    """
    year_str, _, month_str = period.partition("-")
    return int(year_str) * 100 + int(month_str)


def build_csv_variables(
    spec: IndicatorSpec,
    parsed: ParsedIndicator,
    *,
    source_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Build per-`variable_id` CSV row lists for one OGD indicator.

    Each row carries the four canonical columns declared on file class
    ``datasets/data/datapoints/geo/*.csv``: ``entity_id``, ``time``,
    ``value``, ``source_id``. One ``variable_id`` per indicator (the
    OGD ingest is one-resource-per-indicator by design - no facets).
    """
    csv_meta = _INDICATOR_TO_CSV[spec.indicator_id]
    variable_id = csv_meta["variable_id"]
    csv_rows: list[dict[str, Any]] = []
    for r in parsed.rows:
        csv_rows.append({
            "entity_id": r.entity_id,
            "time": _fy_period_to_time(r.time),
            "value": r.value,
            "source_id": source_id,
        })
    return {variable_id: csv_rows}


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


def ingest(*, repo_root: Path, schema_dir: Path) -> IngestResult:
    """Read each cached CSV → write its artifact. Idempotent."""
    indicator_schema_path = schema_dir / "indicator.schema.json"
    indicator_schema = json.loads(indicator_schema_path.read_text(encoding="utf-8"))

    out_dir = repo_root / "datasets" / "indicators" / "in" / "fiscal"
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[IndicatorIngestResult] = []
    for spec in SHIPPED_SPECS:
        cached = _resolve_csv(indicator_id=spec.indicator_id, repo_root=repo_root)
        parsed = parse_csv(cached.content, spec)

        payload = _build_payload(spec=spec, parsed=parsed, cached=cached)

        leaf = spec.indicator_id.split("/")[-1] + ".json"
        path = out_dir / leaf
        write_artifact(
            path=path,
            schema_id=indicator_schema["$id"],
            schema_version=indicator_schema["x-version"],
            payload=payload,
            sources=[
                # Portal page — canonical attribution; readers can
                # reproduce the download by visiting this URL.
                Source(url=cached.meta.portal_page_url, fetched_at=cached.fetched_at),
                # Upstream authority page — the body that produced the
                # underlying answer (Rajya Sabha question, ministry note).
                Source(url=cached.meta.authority_page_url, fetched_at=cached.fetched_at),
                # OGD platform itself (license, terms).
                Source(url=OGD_AUTHORITY_URL, fetched_at=cached.fetched_at),
            ],
            schema_for_validation=indicator_schema,
        )

        # B1.6.2 - canonical long-format CSV emission ALONGSIDE the
        # legacy indicator JSON write. Existing JSON output stays in
        # place; instead-of deletion is deferred to B3 per parent plan
        # section 23.1 and sub-plan section B1.6.1..7 point 6.
        csv_meta = _INDICATOR_TO_CSV[spec.indicator_id]
        csv_source_id = derive_source_id(
            csv_meta["producer"], csv_meta["title"], csv_meta["vintage"],
        )
        by_variable = build_csv_variables(
            spec, parsed, source_id=csv_source_id,
        )
        emit_csv_variables(repo_root=repo_root, by_variable=by_variable)

        results.append(
            IndicatorIngestResult(
                indicator_id=spec.indicator_id,
                artifact_path=path,
                csv_cache_path=_cache_path(repo_root, spec.indicator_id),
                fetched_at=cached.fetched_at,
                record_count=parsed.record_count,
                row_count=len(parsed.rows),
            )
        )

    return IngestResult(indicators=tuple(results))
