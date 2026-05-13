"""Orchestrator for RBI Appendix Table national-aggregate ingest.

No network. Reads the workbook from
``.runtime/raw/rbi/state_finances/02_APP_devolution_transfers.xlsx``
(or operator-overridden via env), runs the pure parser, and writes a
canonical national indicator artifact under
``datasets/indicators/in/fiscal/<leaf>.json``.

Why no network in this adapter:
The State Finances appendix workbook is the same publication as the
per-Statement files already used by ``rbi_xlsx``; an operator who has
fetched the per-state Statements has the appendix locally too. We
prefer the cache-only path here to keep this adapter trivially
re-runnable in CI without re-fetching RBI's CDN.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.core.io import Source, write_artifact

from .parsers import (
    SHIPPED_SPECS,
    AppendixSpec,
    ParsedIndicator,
    parse_workbook,
)


RBI_SOURCE_NAME = "rbi"

# Where this adapter expects the cached workbook to live, relative to
# the repository root. Same directory as rbi_xlsx so a single recon
# fills both adapters.
CACHE_RELPATH = (
    ".runtime/raw/rbi/state_finances/02_APP_devolution_transfers.xlsx"
)

# RBI listing page (cited as the canonical attribution since the
# direct XLSX URL is edition-specific and rotates).
LISTING_PAGE = (
    "https://www.rbi.org.in/Scripts/AnnualPublications.aspx"
    "?head=State+Finances+%3A+A+Study+of+Budgets"
)


class RBIAppendixCacheMissing(RuntimeError):
    """No cached workbook to read.

    Carries the operator recipe: download from the RBI listing page
    and drop into the expected cache path.
    """


@dataclass(frozen=True)
class IndicatorMeta:
    indicator_id: str
    title: str
    description: str
    direction: str            # higher_is_better | lower_is_better | neutral
    comparability: str
    attribution_geography: str
    icon: str
    funding_split_state_pct: int
    notes: str
    value_kind: str = "currency"
    unit: str = "INR (crore)"


INDICATOR_META: dict[str, IndicatorMeta] = {
    "fiscal/national_centre_transfers_total": IndicatorMeta(
        indicator_id="fiscal/national_centre_transfers_total",
        title="Net Centre-to-States transfers (all-India)",
        description=(
            "Total resources transferred from the Central Government to all "
            "State governments combined in each fiscal year, net of loan "
            "repayments and interest payments back to the Centre. The "
            "all-India aggregate equivalent of the per-state transfers "
            "indicators — useful for the macro question 'how big is the "
            "Centre's transfer envelope, and how has it grown?'. The number "
            "RBI publishes is Item VI of Appendix Table 2 ('Net Transfer of "
            "Resources from the Centre = Gross Transfer minus Repayments "
            "and Interest Liabilities')."
        ),
        direction="neutral",
        # National-level series: not state-comparable by definition;
        # comparable across years for the same nation.
        comparability="comparable_with_normalisation",
        attribution_geography="where_administered",
        icon="landmark",
        funding_split_state_pct=0,
        value_kind="currency",
        unit="INR (crore)",
        notes=(
            "Source: RBI 'State Finances: A Study of Budgets', Appendix "
            "Table 2 ('Devolution and Transfer of Resources from the "
            "Centre'), Item VI 'Net Transfer of Resources from the "
            "Centre'. Values are in nominal ₹ Crore (1 Crore = 10 million); "
            "they are NOT inflation-adjusted, so the historical curve "
            "reflects price level changes as much as real flows. For "
            "fiscal years that appear in the workbook with multiple "
            "qualifiers (e.g. 2023-24 ships as both 'Accounts' and "
            "'Budget Estimates'), the Accounts (actual) figure is "
            "preferred. The latest two years are RE / BE only. From "
            "2017-18 onwards the figures include Delhi and Puducherry."
        ),
    ),
}


def _resolve_workbook(
    *, repo_root: Path, indicator_id: str
) -> tuple[bytes, datetime, str]:
    """Read the cached workbook bytes, returning ``(content, mtime, url)``.

    ``url`` is the RBI listing page (canonical attribution); the
    edition-specific direct URL is intentionally not pinned here
    because this adapter's contract is "what the operator already
    cached".
    """
    env_var = f"RBI_APPENDIX_NATIONAL_{indicator_id.split('/')[-1].upper()}_PATH"
    env_path = os.environ.get(env_var, "").strip()
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise RBIAppendixCacheMissing(
                f"${env_var} points to {path}, but that file does not exist."
            )
    else:
        path = repo_root / CACHE_RELPATH
        if not path.exists():
            raise RBIAppendixCacheMissing(
                f"No cached RBI Appendix workbook at {CACHE_RELPATH}.\n"
                f"  (a) Download the appendix workbook from {LISTING_PAGE}\n"
                f"  (b) Save it as {CACHE_RELPATH} (relative to repo root)\n"
                f"  (c) Re-run this command\n"
                f"Or override the path with ${env_var}=<absolute path>."
            )
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(
        microsecond=0
    )
    return path.read_bytes(), mtime, LISTING_PAGE


def _coverage_temporal(parsed: ParsedIndicator) -> str:
    times = sorted({r.time for r in parsed.rows})
    if not times:
        return "unknown"
    return f"{times[0]}..{times[-1]}"


def _build_payload(
    *,
    spec: AppendixSpec,
    parsed: ParsedIndicator,
    workbook_fetched_at: datetime,
) -> dict[str, Any]:
    meta = INDICATOR_META[spec.indicator_id]

    rows = [
        {"entity_id": r.entity_id, "time": r.time, "value": r.value}
        for r in parsed.rows
    ]

    return {
        "license": {
            "id": "GoI-Open",
            "name": "Government of India open publication",
            "url": "https://data.gov.in/government-open-data-license-india",
            "redistributable": True,
        },
        "coverage": {
            "spatial": "India (national aggregate)",
            "temporal": _coverage_temporal(parsed),
            "admin_level": "national",
        },
        "indicator": {
            "id": spec.indicator_id,
            "title": meta.title,
            "description": meta.description,
            "entity_kind": "country",
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
                "source": "definition (own vs centrally-transferred)",
            },
            "implementing_authority": "centre",
            "methodology_vintage": (
                f"RBI State Finances: A Study of Budgets, Appendix Table 2; "
                f"cached file mtime "
                f"{workbook_fetched_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}"
            ),
            "notes": meta.notes,
        },
        "rows": rows,
    }


@dataclass(frozen=True)
class IndicatorIngestResult:
    indicator_id: str
    artifact_path: Path
    workbook_fetched_at: datetime
    sheet_count: int
    period_count: int
    row_count: int


@dataclass(frozen=True)
class IngestResult:
    indicators: tuple[IndicatorIngestResult, ...]


def ingest(*, repo_root: Path, schema_dir: Path) -> IngestResult:
    """Read cached workbook, parse all shipped specs, write artifacts."""
    indicator_schema_path = schema_dir / "indicator.schema.json"
    indicator_schema = json.loads(indicator_schema_path.read_text(encoding="utf-8"))

    out_dir = repo_root / "datasets" / "indicators" / "in" / "fiscal"
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[IndicatorIngestResult] = []
    for spec in SHIPPED_SPECS:
        content, mtime, url = _resolve_workbook(
            repo_root=repo_root, indicator_id=spec.indicator_id
        )
        parsed = parse_workbook(content, spec)
        payload = _build_payload(
            spec=spec, parsed=parsed, workbook_fetched_at=mtime
        )

        leaf = spec.indicator_id.split("/")[-1] + ".json"
        path = out_dir / leaf
        write_artifact(
            path=path,
            schema_id=indicator_schema["$id"],
            schema_version=indicator_schema["x-version"],
            payload=payload,
            sources=[Source(url=url, fetched_at=mtime)],
            schema_for_validation=indicator_schema,
        )
        results.append(
            IndicatorIngestResult(
                indicator_id=spec.indicator_id,
                artifact_path=path,
                workbook_fetched_at=mtime,
                sheet_count=parsed.sheet_count,
                period_count=parsed.period_count,
                row_count=len(parsed.rows),
            )
        )

    return IngestResult(indicators=tuple(results))
