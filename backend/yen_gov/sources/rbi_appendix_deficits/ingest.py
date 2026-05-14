"""Orchestrator for RBI Appendix Table 1 (Major Deficit Indicators) ingest.

No network. Reads the workbook from
``.runtime/raw/rbi/state_finances/AppT1_MajorDeficitIndicators_2026.xlsx``
(or operator-overridden via env), runs the pure parser, and writes four
canonical national indicator artifacts under
``datasets/indicators/in/fiscal/national_*_deficit.json``.

This is the cache-only sibling of ``rbi_appendix_national``: same RBI
publication (State Finances), different appendix table, different layout.
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
    DeficitSpec,
    ParsedIndicator,
    parse_workbook,
)


# Where this adapter expects the cached workbook to live, relative to
# the repo root. Same directory as the rest of the State Finances cache.
CACHE_RELPATH = (
    ".runtime/raw/rbi/state_finances/AppT1_MajorDeficitIndicators_2026.xlsx"
)

LISTING_PAGE = (
    "https://www.rbi.org.in/Scripts/AnnualPublications.aspx"
    "?head=State+Finances+%3A+A+Study+of+Budgets"
)


class RBIAppT1CacheMissing(RuntimeError):
    """No cached workbook to read.

    Carries the operator recipe so anyone (or any future agent) can
    regenerate the artifacts from a fresh download.
    """


@dataclass(frozen=True)
class IndicatorMeta:
    indicator_id: str
    title: str
    description: str
    direction: str            # higher_is_better | lower_is_better | neutral
    icon: str
    notes: str


# Sign convention notes:
#   RBI publishes deficits as POSITIVE numbers when the indicator is
#   "in deficit" (e.g. Gross Fiscal Deficit > 0 means the consolidated
#   states' borrowing requirement). Revenue Deficit can be negative,
#   meaning a revenue *surplus*; we keep the published sign so a value
#   like -42942 reads as "Rs 42942 Crore revenue surplus that year".
#   `direction` reflects citizen interpretation: lower deficit = better.
INDICATOR_META: dict[str, IndicatorMeta] = {
    "fiscal/national_gross_fiscal_deficit": IndicatorMeta(
        indicator_id="fiscal/national_gross_fiscal_deficit",
        title="Gross fiscal deficit (all states, all-India)",
        description=(
            "The consolidated borrowing requirement of all State governments "
            "combined in each fiscal year. Defined as total expenditure "
            "minus total non-debt receipts. A positive value means the "
            "states collectively had to borrow this much to fund the gap "
            "between their spending and their revenue + non-debt capital "
            "receipts. The single most-cited 'how much are states "
            "borrowing this year' indicator. RBI's Appendix Table 1, "
            "column 2 (Major Deficit Indicators of State Governments)."
        ),
        direction="lower_is_better",
        icon="trending-down",
        notes=(
            "Source: RBI 'State Finances: A Study of Budgets', Appendix "
            "Table 1 (Major Deficit Indicators of State Governments), "
            "column 'Gross Fiscal Deficit'. Values are nominal Rs Crore "
            "(1 Crore = 10 million); they are NOT inflation-adjusted, so "
            "the historical curve reflects price level changes as much as "
            "real fiscal stress. The latest two fiscal years are typically "
            "RE (Revised Estimate) / BE (Budget Estimate) — read with "
            "appropriate caution. From 2017-18 the figures include Delhi "
            "and Puducherry. The RBI publication also reports each "
            "indicator as % of GDP on alternating rows; that companion "
            "series is intentionally not ingested here (would need its "
            "own indicator family with value_kind=percent)."
        ),
    ),
    "fiscal/national_revenue_deficit": IndicatorMeta(
        indicator_id="fiscal/national_revenue_deficit",
        title="Revenue deficit (all states, all-India)",
        description=(
            "Revenue expenditure minus revenue receipts for all states "
            "combined. Positive = the states are borrowing to fund "
            "current consumption (salaries, subsidies, interest), which "
            "is widely considered the most worrying form of deficit. "
            "Negative = revenue *surplus* — current receipts exceed "
            "current spending, freeing borrowed funds for genuine capital "
            "formation. RBI Appendix Table 1, column 3."
        ),
        direction="lower_is_better",
        icon="trending-down",
        notes=(
            "Source: RBI 'State Finances: A Study of Budgets', Appendix "
            "Table 1, column 'Revenue Deficit'. Negative values mean "
            "revenue surplus. Same fiscal-year, RE/BE, and Delhi/"
            "Puducherry-from-FY18 caveats as the gross fiscal deficit "
            "indicator."
        ),
    ),
    "fiscal/national_primary_deficit": IndicatorMeta(
        indicator_id="fiscal/national_primary_deficit",
        title="Primary deficit (all states, all-India)",
        description=(
            "Gross fiscal deficit minus interest payments. Strips out the "
            "legacy interest burden from past borrowing to show whether "
            "*this year's* spending decisions are themselves adding to or "
            "subtracting from debt. Positive = this year's policy choices "
            "are widening the debt; negative = this year is running a "
            "primary surplus that pays down some inherited interest. RBI "
            "Appendix Table 1, column 4."
        ),
        direction="lower_is_better",
        icon="trending-down",
        notes=(
            "Source: RBI 'State Finances: A Study of Budgets', Appendix "
            "Table 1, column 'Primary Deficit'. Same caveats as the gross "
            "fiscal deficit indicator."
        ),
    ),
    "fiscal/national_primary_revenue_deficit": IndicatorMeta(
        indicator_id="fiscal/national_primary_revenue_deficit",
        title="Primary revenue deficit (all states, all-India)",
        description=(
            "Revenue deficit minus interest payments — the strictest "
            "fiscal-discipline indicator. Negative values (which is the "
            "norm in Indian state finances) mean that, after stripping "
            "out legacy interest payments, the states' current receipts "
            "do cover their current expenditure. Positive values would "
            "indicate genuinely unsustainable consumption-borrowing. RBI "
            "Appendix Table 1, column 5."
        ),
        direction="lower_is_better",
        icon="trending-down",
        notes=(
            "Source: RBI 'State Finances: A Study of Budgets', Appendix "
            "Table 1, column 'Primary Revenue Deficit'. Indian state "
            "finances have historically run a primary revenue *surplus* "
            "(negative deficit) for most years in the series; that is "
            "the headline that revenue and primary deficits taken in "
            "isolation can obscure."
        ),
    ),
}


def _resolve_workbook(*, repo_root: Path) -> tuple[bytes, datetime, str]:
    """Read the cached workbook bytes, returning ``(content, mtime, url)``."""
    env_path = os.environ.get("RBI_APPT1_DEFICITS_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise RBIAppT1CacheMissing(
                f"$RBI_APPT1_DEFICITS_PATH points to {path}, but that file "
                f"does not exist."
            )
    else:
        path = repo_root / CACHE_RELPATH
        if not path.exists():
            raise RBIAppT1CacheMissing(
                f"No cached RBI Appendix T1 workbook at {CACHE_RELPATH}.\n"
                f"  (a) Open {LISTING_PAGE}\n"
                f"  (b) Pick the latest 'State Finances: A Study of Budgets' "
                f"edition\n"
                f"  (c) Download the workbook labelled 'Appendix Table 1: "
                f"Major Deficit Indicators of State Governments'\n"
                f"  (d) Save it as {CACHE_RELPATH} (relative to repo root) "
                f"with the AppT1_MajorDeficitIndicators_<YYYY>.xlsx leaf "
                f"name pattern\n"
                f"  (e) Re-run this command\n"
                f"Or override the path with $RBI_APPT1_DEFICITS_PATH="
                f"<absolute path>."
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
    spec: DeficitSpec,
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
            "spatial": "India (all-states aggregate)",
            "temporal": _coverage_temporal(parsed),
            "admin_level": "national",
        },
        "indicator": {
            "id": spec.indicator_id,
            "title": meta.title,
            "description": meta.description,
            "entity_kind": "country",
            "time_grain": "fiscal_year",
            "value_kind": "currency",
            "direction": meta.direction,
            "scale_hint": "linear",
            "unit": "INR (crore)",
            "icon": meta.icon,
            "attribution_geography": "where_administered",
            "comparability": "comparable_with_normalisation",
            "funding_split": {
                "centre_pct": 0,
                "state_pct": 100,
                "source": "definition (states' own budgetary deficits)",
            },
            "implementing_authority": "state",
            "methodology_vintage": (
                f"RBI State Finances: A Study of Budgets, Appendix Table 1 "
                f"(Major Deficit Indicators); cached file mtime "
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

    content, mtime, url = _resolve_workbook(repo_root=repo_root)
    parsed_by_id = parse_workbook(content)

    results: list[IndicatorIngestResult] = []
    for spec in SHIPPED_SPECS:
        parsed = parsed_by_id[spec.indicator_id]
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
                period_count=parsed.period_count,
                row_count=len(parsed.rows),
            )
        )

    return IngestResult(indicators=tuple(results))
