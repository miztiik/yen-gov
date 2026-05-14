"""Orchestrator for RBI HBS-IE Table 89 (Key Deficit Indicators of the Central Government).

No network. Reads the workbook from
``.runtime/raw/rbi/hbs_ie/T89_KeyDeficitIndicators_Centre_<YYYY>.xlsx``
(or operator-overridden via ``$RBI_HBS_IE_T89_PATH``), reuses the
:mod:`yen_gov.sources.rbi_appendix_deficits.parsers` parser, and writes
four canonical national indicator artifacts under
``datasets/indicators/in/fiscal/union_*_deficit.json``.

Cache-only sibling of ``rbi_appendix_deficits`` — same XLSX shape, but
the **Centre** (Union Government) is the actor instead of the
states-combined.

Edition pinned at ingest-time (see ``HBS_IE_EDITION_NOTE`` below).
The pinned XLSX URL changes per edition; only the listing page URL is
written into ``sources`` (matches the AppT1 sibling's convention).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.core.io import Source, write_artifact
from yen_gov.sources.rbi_appendix_deficits.parsers import (
    DeficitSpec,
    ParsedIndicator,
    parse_workbook,
)


# Where this adapter expects the cached workbook to live, relative to
# the repo root. Distinct from the State Finances cache: this is HBS-IE.
CACHE_RELPATH = (
    ".runtime/raw/rbi/hbs_ie/T89_KeyDeficitIndicators_Centre_2025.xlsx"
)

LISTING_PAGE = (
    "https://www.rbi.org.in/Scripts/AnnualPublications.aspx"
    "?head=Handbook+of+Statistics+on+Indian+Economy"
)

# The pinned direct-download URL for the 2024-25 edition (HBS-IE published
# 2025-08-29). Recorded for operator reproducibility — NOT used as the
# `sources` URL in emitted artifacts (we use LISTING_PAGE there to match
# the AppT1 sibling and stay edition-agnostic).
PINNED_XLSX_URL_2024_25 = (
    "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/"
    "89T_29082025E8B3FAE53E854131998A98825CE0DAEA.XLSX"
)

HBS_IE_EDITION_NOTE = (
    "Verified against HBS-IE 2024-25 (published 2025-08-29). "
    "Workbook ships 8 indicator columns; we ship 4 to mirror the "
    "states-combined sibling family. The latest two fiscal years are "
    "RE/BE per the workbook's own footnote 1."
)


class RBIHBSIET89CacheMissing(RuntimeError):
    """No cached workbook to read.

    Carries the operator recipe so the next agent or human can rebuild
    the artifacts from a fresh download.
    """


@dataclass(frozen=True)
class IndicatorMeta:
    indicator_id: str
    title: str
    description: str
    direction: str
    icon: str
    notes: str


# Ship the four citizen-facing Centre-actor deficit indicators. The
# workbook also publishes Net Fiscal Deficit, Net Primary Deficit,
# Drawdown of Cash Balances, and Net RBI Credit; those are intentionally
# NOT shipped from this source family — Net variants are derivable from
# the gross variant minus the financing-side adjustments and are not the
# headline numbers citizens encounter, while Drawdown / RBI Credit are
# monetary-policy series outside the deficit-indicator scope.
SHIPPED_SPECS: tuple[DeficitSpec, ...] = (
    DeficitSpec(
        indicator_id="fiscal/union_gross_fiscal_deficit",
        column_label_match="gross fiscal deficit",
    ),
    DeficitSpec(
        indicator_id="fiscal/union_revenue_deficit",
        column_label_match="revenue deficit",
    ),
    DeficitSpec(
        # T89 labels the standard "Primary Deficit" as "Gross Primary
        # Deficit" (vs Net Primary Deficit which adjusts for financing).
        # Standard Indian fiscal usage = Primary Deficit = GFD minus
        # interest payments; that IS HBS-IE's "Gross Primary Deficit".
        indicator_id="fiscal/union_primary_deficit",
        column_label_match="gross primary deficit",
    ),
    DeficitSpec(
        indicator_id="fiscal/union_primary_revenue_deficit",
        column_label_match="primary revenue deficit",
    ),
)


INDICATOR_META: dict[str, IndicatorMeta] = {
    "fiscal/union_gross_fiscal_deficit": IndicatorMeta(
        indicator_id="fiscal/union_gross_fiscal_deficit",
        title="Gross fiscal deficit (Union Government)",
        description=(
            "The Union (Central) Government's own borrowing requirement "
            "in each fiscal year. Defined as total expenditure minus "
            "total non-debt receipts. The single most-cited 'how much is "
            "the Centre borrowing this year' indicator — the headline "
            "fiscal deficit number that dominates Union Budget commentary "
            "every February. RBI HBS-IE Table 89, column 'Gross Fiscal "
            "Deficit'. Distinct from `fiscal/states_combined_gross_fiscal_deficit` "
            "which measures the all-states combined borrowing; the two "
            "are independent fiscal envelopes and are usefully compared "
            "side-by-side rather than added."
        ),
        direction="lower_is_better",
        icon="trending-down",
        notes=(
            "Source: RBI Handbook of Statistics on Indian Economy, "
            "Table 89 (Key Deficit Indicators of the Central Government), "
            "column 'Gross Fiscal Deficit'. Values are nominal Rs Crore "
            "(1 Crore = 10 million); NOT inflation-adjusted, so the "
            "historical curve reflects price level changes as much as "
            "real fiscal stress. The latest two fiscal years are "
            "typically RE (Revised Estimate) / BE (Budget Estimate) — "
            "read with appropriate caution. Coverage starts FY1986-87 "
            "in the 2024-25 edition. The RBI workbook also reports Net "
            "Fiscal Deficit, Net Primary Deficit, Drawdown of Cash "
            "Balances, and Net RBI Credit on the same sheet; those are "
            "intentionally not ingested here."
        ),
    ),
    "fiscal/union_revenue_deficit": IndicatorMeta(
        indicator_id="fiscal/union_revenue_deficit",
        title="Revenue deficit (Union Government)",
        description=(
            "Revenue expenditure minus revenue receipts for the Union "
            "Government. Positive = the Centre is borrowing to fund "
            "current consumption (salaries, subsidies, interest "
            "payments), widely considered the most worrying form of "
            "deficit. Negative = revenue *surplus* — current receipts "
            "exceed current spending. RBI HBS-IE Table 89, column "
            "'Revenue Deficit'."
        ),
        direction="lower_is_better",
        icon="trending-down",
        notes=(
            "Source: RBI Handbook of Statistics on Indian Economy, "
            "Table 89, column 'Revenue Deficit'. Negative values mean "
            "revenue surplus. Same fiscal-year and RE/BE caveats as the "
            "Union gross fiscal deficit indicator."
        ),
    ),
    "fiscal/union_primary_deficit": IndicatorMeta(
        indicator_id="fiscal/union_primary_deficit",
        title="Primary deficit (Union Government)",
        description=(
            "Gross fiscal deficit minus interest payments. Strips out "
            "the legacy interest burden from past borrowing to show "
            "whether *this year's* spending decisions are themselves "
            "adding to or subtracting from debt. Positive = this year's "
            "policy choices are widening the debt; negative = this year "
            "is running a primary surplus that pays down some inherited "
            "interest. RBI HBS-IE Table 89, column 'Gross Primary "
            "Deficit' (which RBI labels 'Gross' to distinguish from the "
            "financing-adjusted Net Primary Deficit; in standard Indian "
            "fiscal language without modifier this IS the Primary "
            "Deficit)."
        ),
        direction="lower_is_better",
        icon="trending-down",
        notes=(
            "Source: RBI Handbook of Statistics on Indian Economy, "
            "Table 89, column 'Gross Primary Deficit'. The workbook also "
            "publishes Net Primary Deficit (financing-side adjusted); "
            "we ship Gross only because it is the standard 'Primary "
            "Deficit' citizens encounter in Budget commentary."
        ),
    ),
    "fiscal/union_primary_revenue_deficit": IndicatorMeta(
        indicator_id="fiscal/union_primary_revenue_deficit",
        title="Primary revenue deficit (Union Government)",
        description=(
            "Revenue deficit minus interest payments — the strictest "
            "fiscal-discipline indicator for the Union Government. "
            "Negative values mean that, after stripping out legacy "
            "interest payments, the Centre's current receipts do cover "
            "its current expenditure; positive values indicate genuinely "
            "unsustainable consumption-borrowing. RBI HBS-IE Table 89, "
            "column 'Primary Revenue Deficit'."
        ),
        direction="lower_is_better",
        icon="trending-down",
        notes=(
            "Source: RBI Handbook of Statistics on Indian Economy, "
            "Table 89, column 'Primary Revenue Deficit'. Has been "
            "negative (i.e. primary revenue surplus) for substantial "
            "stretches of the historical series, including most of the "
            "1986-2007 period and 2013-2019."
        ),
    ),
}


def _resolve_workbook(*, repo_root: Path) -> tuple[bytes, datetime, str]:
    """Read the cached workbook bytes, returning ``(content, mtime, url)``."""
    env_path = os.environ.get("RBI_HBS_IE_T89_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise RBIHBSIET89CacheMissing(
                f"$RBI_HBS_IE_T89_PATH points to {path}, but that file "
                f"does not exist."
            )
    else:
        path = repo_root / CACHE_RELPATH
        if not path.exists():
            raise RBIHBSIET89CacheMissing(
                f"No cached RBI HBS-IE Table 89 workbook at {CACHE_RELPATH}.\n"
                f"  (a) Open {LISTING_PAGE}\n"
                f"  (b) Pick the latest 'Handbook of Statistics on the "
                f"Indian Economy' edition (currently 2024-25)\n"
                f"  (c) Download Table 89 'Key Deficit Indicators of the "
                f"Central Government' (XLSX, ~13 KB)\n"
                f"  (d) Save it as {CACHE_RELPATH} (relative to repo root) "
                f"with the T89_KeyDeficitIndicators_Centre_<YYYY>.xlsx leaf "
                f"name pattern\n"
                f"  (e) Re-run this command\n"
                f"Or override the path with $RBI_HBS_IE_T89_PATH=<absolute "
                f"path>.\n"
                f"For convenience, the 2024-25 edition direct URL is "
                f"recorded in this module as PINNED_XLSX_URL_2024_25 and "
                f"can be fetched via tools/rbi_download.py."
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
            "spatial": "India (Union Government)",
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
                "centre_pct": 100,
                "state_pct": 0,
                "source": "definition (Union Government's own budgetary deficit)",
            },
            "implementing_authority": "centre",
            "methodology_vintage": (
                f"RBI Handbook of Statistics on Indian Economy, Table 89 "
                f"(Key Deficit Indicators of the Central Government); "
                f"cached file mtime "
                f"{workbook_fetched_at.isoformat(timespec='seconds').replace('+00:00', 'Z')}. "
                f"{HBS_IE_EDITION_NOTE}"
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
    parsed_by_id = parse_workbook(content, specs=SHIPPED_SPECS)

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
