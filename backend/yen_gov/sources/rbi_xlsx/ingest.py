"""Orchestrator for the RBI fiscal ingest.

Network + filesystem boundary. For each shipped indicator spec:
  1. Resolve a workbook URL via :mod:`.urls` (registry → env override
     → local cache fallback).
  2. Fetch the XLSX bytes.
  3. Run the pure parser (:mod:`.parsers`) for that single indicator.
  4. Write a ``datasets/indicators/in/fiscal/<leaf>.json`` artifact
     conforming to ``datasets/schemas/indicator.schema.json``.

See ``docs/architecture/backend/sources-rbi.md`` for the per-indicator
honesty fields each artifact materialises.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.core.http import Fetcher, FetchResult
from yen_gov.core.io import Source, write_artifact

from .parsers import (
    SHIPPED_SPECS,
    IndicatorSpec,
    ParsedIndicator,
    parse_workbook,
)
from .urls import LISTING_PAGE, RBI_AUTHORITY_URL, latest_url


RBI_SOURCE_NAME = "rbi"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RBISourceUnavailable(RuntimeError):
    """No usable workbook source for an indicator: registry empty, env
    unset, no local cache."""


# ---------------------------------------------------------------------------
# Per-indicator metadata (from sources-rbi.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndicatorMeta:
    """Honesty fields for one fiscal indicator."""

    indicator_id: str
    title: str
    description: str
    direction: str            # higher_is_better | lower_is_better | neutral
    comparability: str
    attribution_geography: str
    icon: str
    funding_split_state_pct: int
    notes: str
    series_breaks: tuple[dict[str, str], ...] = ()


# Registry of shipped indicators' metadata. Currently one entry; new
# entries land alongside their spec in parsers.SHIPPED_SPECS and their
# URL pin in urls.KNOWN_URLS.
INDICATOR_META: dict[str, IndicatorMeta] = {
    "fiscal/outstanding_debt_pct_gsdp": IndicatorMeta(
        indicator_id="fiscal/outstanding_debt_pct_gsdp",
        title="Outstanding liabilities (% of GSDP)",
        description=(
            "Stock of state-government debt outstanding at the end of each "
            "fiscal year, expressed as a share of Gross State Domestic "
            "Product. Includes loans and public-account liabilities. "
            "Higher values mean a larger debt burden relative to the "
            "state's economic base. The FRBM Act 2003 imposed the first "
            "hard ceilings on state debt; pre-2003 series used different "
            "consolidation rules."
        ),
        direction="lower_is_better",
        comparability="comparable_across_states",
        attribution_geography="where_administered",
        icon="landmark",
        funding_split_state_pct=100,
        notes=(
            "Source: RBI 'State Finances: A Study of Budgets', Statement 20 "
            "(Total Outstanding Liabilities — As per cent of GSDP). The "
            "latest two periods are the State governments' Revised "
            "Estimates (RE) and Budget Estimates (BE); earlier periods are "
            "Accounts data. Telangana's series begins in 2014-15 (state "
            "formation) — pre-2014 cells are intentionally null."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Source resolution (per-indicator)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkbookBytes:
    """The XLSX bytes plus where they came from.

    ``url``: canonical RBI URL when known (registry or env), otherwise
    the listing page when bytes loaded from local cache.
    ``fetched_at``: when the bytes were retrieved (for ``sources[]``);
    for cache reads, the file's mtime — honest about real freshness.
    """

    content: bytes
    url: str
    fetched_at: datetime


def _env_var_for(indicator_id: str) -> str:
    # fiscal/outstanding_debt_pct_gsdp → RBI_OUTSTANDING_DEBT_PCT_GSDP_URL
    leaf = indicator_id.split("/")[-1]
    return f"RBI_{leaf.upper()}_URL"


def _cache_glob_for(indicator_id: str) -> str:
    """Glob pattern used when looking for a locally-downloaded copy.

    We accept any file whose name contains the indicator's leaf token —
    that lets the operator name the cached file something readable
    (e.g. ``St20_OutstandingLiabilities_pctGSDP_2026.xlsx``).
    """
    leaf = indicator_id.split("/")[-1]
    # Normalise to a token that should appear in the operator's filename.
    token = leaf.replace("_pct_gsdp", "").replace("_", "")
    return f"*{token}*.xlsx"


def _resolve_source(
    *,
    indicator_id: str,
    fetcher: Fetcher,
    repo_root: Path,
) -> WorkbookBytes:
    """Try registry → env → local cache, in that order."""
    pinned = latest_url(indicator_id)
    if pinned is not None:
        _, url = pinned
        result: FetchResult = fetcher.fetch(url)
        return WorkbookBytes(
            content=result.content,
            url=result.url,
            fetched_at=result.fetched_at,
        )

    env_url = os.environ.get(_env_var_for(indicator_id), "").strip()
    if env_url:
        result = fetcher.fetch(env_url)
        return WorkbookBytes(
            content=result.content,
            url=result.url,
            fetched_at=result.fetched_at,
        )

    cache_dir = repo_root / ".runtime" / "raw" / RBI_SOURCE_NAME / "state_finances"
    if cache_dir.exists():
        # Prefer indicator-specific filename matches; fall back to any xlsx.
        matches = sorted(cache_dir.glob(_cache_glob_for(indicator_id)))
        if not matches:
            matches = sorted(cache_dir.glob("*.xlsx"))
        if matches:
            latest = matches[-1]
            mtime = datetime.fromtimestamp(
                latest.stat().st_mtime, tz=timezone.utc
            ).replace(microsecond=0)
            return WorkbookBytes(
                content=latest.read_bytes(),
                url=LISTING_PAGE,
                fetched_at=mtime,
            )

    raise RBISourceUnavailable(
        f"No RBI workbook source available for {indicator_id!r}. Either:\n"
        f"  (a) pin a URL in backend/yen_gov/sources/rbi_xlsx/urls.py\n"
        f"  (b) set ${_env_var_for(indicator_id)} to the direct XLSX URL\n"
        f"  (c) download the workbook from {LISTING_PAGE} and save it as\n"
        f"      .runtime/raw/rbi/state_finances/<filename>.xlsx"
    )


# ---------------------------------------------------------------------------
# Indicator artifact builder
# ---------------------------------------------------------------------------


def _coverage_temporal(parsed: ParsedIndicator) -> str:
    times = sorted({r.time for r in parsed.rows})
    if not times:
        return "unknown"
    return f"{times[0]}..{times[-1]}"


def _build_indicator_payload(
    *,
    spec: IndicatorSpec,
    parsed: ParsedIndicator,
    workbook_url: str,
    workbook_fetched_at: datetime,
) -> dict[str, Any]:
    meta = INDICATOR_META[spec.indicator_id]

    rows = [
        {
            "entity_id": r.entity_id,
            "time": r.time,
            "value": r.value,
            **({"facet": r.facet} if r.facet else {}),
        }
        for r in parsed.rows
    ]

    notes_parts = [meta.notes]
    if parsed.unmatched_states:
        notes_parts.append(
            "RBI labels not mapped to ECI codes (excluded from this artifact): "
            + ", ".join(sorted(set(parsed.unmatched_states)))
        )
    if workbook_url == LISTING_PAGE:
        notes_parts.append(
            "Workbook bytes loaded from local cache; sources[].url points "
            "to the RBI listing page rather than the direct XLSX URL "
            "because no pinned URL was available at ingest time."
        )

    payload: dict[str, Any] = {
        "license": {
            "id": "GoI-Open",
            "name": "Government of India open publication",
            "url": "https://data.gov.in/government-open-data-license-india",
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
            "value_kind": "share",
            "direction": meta.direction,
            "scale_hint": "linear",
            "unit": "%",
            "icon": meta.icon,
            "attribution_geography": meta.attribution_geography,
            "comparability": meta.comparability,
            "funding_split": {
                "centre_pct": 100 - meta.funding_split_state_pct,
                "state_pct": meta.funding_split_state_pct,
                "source": "definition (own vs centrally-transferred)",
            },
            "implementing_authority": "state",
            "methodology_vintage": (
                f"RBI State Finances: A Study of Budgets, fetched "
                f"{workbook_fetched_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}"
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
    workbook_url: str
    workbook_fetched_at: datetime
    sheet_name: str
    period_columns: int
    row_count: int


@dataclass(frozen=True)
class IngestResult:
    """Summary of a successful ingest run across all shipped indicators."""

    indicators: tuple[IndicatorIngestResult, ...]


def ingest(
    *,
    fetcher: Fetcher,
    repo_root: Path,
    schema_dir: Path,
) -> IngestResult:
    """Fetch + parse + write all shipped fiscal indicators.

    Idempotent: re-runs overwrite the artifacts and re-stamp ``fetched_at``.
    Raises:
        RBISourceUnavailable: no resolvable source for an indicator.
        RBIWorkbookShapeError: workbook layout has shifted; re-run recon.
    """
    indicator_schema_path = schema_dir / "indicator.schema.json"
    indicator_schema = json.loads(indicator_schema_path.read_text(encoding="utf-8"))

    out_dir = repo_root / "datasets" / "indicators" / "in" / "fiscal"
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[IndicatorIngestResult] = []
    for spec in SHIPPED_SPECS:
        wb = _resolve_source(
            indicator_id=spec.indicator_id,
            fetcher=fetcher,
            repo_root=repo_root,
        )
        parsed = parse_workbook(wb.content, spec)

        payload = _build_indicator_payload(
            spec=spec,
            parsed=parsed,
            workbook_url=wb.url,
            workbook_fetched_at=wb.fetched_at,
        )

        leaf = spec.indicator_id.split("/")[-1] + ".json"
        path = out_dir / leaf
        write_artifact(
            path=path,
            schema_id=indicator_schema["$id"],
            schema_version=indicator_schema["x-version"],
            payload=payload,
            sources=[
                Source(url=wb.url, fetched_at=wb.fetched_at),
                Source(url=RBI_AUTHORITY_URL, fetched_at=wb.fetched_at),
            ],
            schema_for_validation=indicator_schema,
        )
        results.append(
            IndicatorIngestResult(
                indicator_id=spec.indicator_id,
                artifact_path=path,
                workbook_url=wb.url,
                workbook_fetched_at=wb.fetched_at,
                sheet_name=parsed.sheet_name,
                period_columns=parsed.period_columns,
                row_count=len(parsed.rows),
            )
        )

    return IngestResult(indicators=tuple(results))
