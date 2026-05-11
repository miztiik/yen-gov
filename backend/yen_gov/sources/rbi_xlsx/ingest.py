"""Orchestrator for the RBI fiscal ingest.

Network + filesystem boundary. Pulls the State Finances workbook
(URL → env → local cache fallback chain), runs the pure parser
(:mod:`.parsers`), and writes one indicator artifact per indicator id
under ``datasets/indicators/in/fiscal/``.

See ``docs/architecture/backend/sources-rbi.md`` for the per-indicator
honesty fields each artifact materialises.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.core.http import Fetcher, FetchResult
from yen_gov.core.io import Source, write_artifact
from .parsers import (
    INDICATOR_SPECS,
    IndicatorSpec,
    ParsedIndicator,
    parse_state_finances_workbook,
)
from .urls import LISTING_PAGE, latest_known_url


RBI_AUTHORITY_URL = "https://www.rbi.org.in/"
RBI_SOURCE_NAME = "rbi"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RBISourceUnavailable(RuntimeError):
    """No usable workbook source: registry empty, env unset, no local cache."""


# ---------------------------------------------------------------------------
# Per-indicator metadata (from sources-rbi.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndicatorMeta:
    """Honesty fields for one fiscal indicator. One-to-one with the spec."""

    indicator_id: str
    title: str
    description: str
    direction: str            # higher_is_better | lower_is_better | neutral
    comparability: str        # comparable_across_states | comparable_with_normalisation | not_comparable_across_states
    attribution_geography: str
    icon: str
    funding_split_state_pct: int
    notes: str
    series_breaks: tuple[dict[str, str], ...] = ()


# Same order as INDICATOR_SPECS so we can zip by index.
INDICATOR_META: dict[str, IndicatorMeta] = {
    m.indicator_id: m
    for m in (
        IndicatorMeta(
            indicator_id="in.fiscal.own_tax_revenue_pct_gsdp",
            title="Own-tax revenue (% of GSDP)",
            description=(
                "Share of state GSDP that the state government collects as its "
                "own tax revenue. Proxy for state fiscal capacity."
            ),
            direction="higher_is_better",
            comparability="comparable_across_states",
            attribution_geography="where_administered",
            icon="coins",
            funding_split_state_pct=100,
            notes=(
                "RBI re-classification (Statement 6, Revenue Receipts). "
                "Pre-GST own-tax includes central sales tax, entry tax, "
                "entertainment tax; post-GST these subsume into SGST. "
                "Treat the 2017-18 step as a regime shift, not a behaviour shift."
            ),
            series_breaks=(
                {
                    "at_time": "2017-04",
                    "kind": "definition_change",
                    "note": "GST introduction subsumed CST, entry tax, entertainment tax into SGST.",
                },
            ),
        ),
        IndicatorMeta(
            indicator_id="in.fiscal.revenue_deficit_pct_gsdp",
            title="Revenue deficit (% of GSDP)",
            description=(
                "Excess of revenue expenditure over revenue receipts as a share of GSDP. "
                "Positive = the state borrows to pay current expenses (salaries, pensions, "
                "interest), not to build assets. FRBM target = 0."
            ),
            direction="lower_is_better",
            comparability="comparable_across_states",
            attribution_geography="where_administered",
            icon="trending-up",
            funding_split_state_pct=100,
            notes="RBI Statement (Key Deficit Indicators). Sign convention: positive = deficit.",
        ),
        IndicatorMeta(
            indicator_id="in.fiscal.gross_fiscal_deficit_pct_gsdp",
            title="Gross fiscal deficit (% of GSDP)",
            description=(
                "Total borrowing requirement of the state as a share of GSDP. "
                "FRBM ceiling is 3% for states (with conditional flexibility)."
            ),
            direction="lower_is_better",
            comparability="comparable_across_states",
            attribution_geography="where_administered",
            icon="trending-up",
            funding_split_state_pct=100,
            notes="Sign convention: positive = deficit. FRBM Act ceiling = 3% of GSDP for states.",
        ),
        IndicatorMeta(
            indicator_id="in.fiscal.outstanding_debt_pct_gsdp",
            title="Outstanding liabilities (% of GSDP)",
            description=(
                "Stock of state-government debt outstanding at year-end as a share of "
                "GSDP. The FRBM Act 2003 imposed the first hard ceilings; pre-2003 "
                "series used different consolidation rules."
            ),
            direction="lower_is_better",
            comparability="comparable_across_states",
            attribution_geography="where_administered",
            icon="landmark",
            funding_split_state_pct=100,
            notes="Includes loans + public account liabilities + small savings.",
            series_breaks=(
                {
                    "at_time": "2003-04",
                    "kind": "frame_change",
                    "note": "FRBM Act 2003 imposed first hard ceiling on state debt.",
                },
            ),
        ),
        IndicatorMeta(
            indicator_id="in.fiscal.interest_payments_pct_revenue_receipts",
            title="Interest payments (% of revenue receipts)",
            description=(
                "Share of state revenue receipts consumed by debt servicing. "
                "First-order proxy for fiscal stress: when this exceeds ~20%, "
                "interest payments crowd out development spending."
            ),
            direction="lower_is_better",
            comparability="comparable_across_states",
            attribution_geography="where_administered",
            icon="trending-up",
            funding_split_state_pct=100,
            notes="Denominator is revenue receipts, not GSDP — captures debt-service burden on the cash-flow side.",
        ),
        IndicatorMeta(
            indicator_id="in.fiscal.capital_outlay_pct_gsdp",
            title="Capital outlay (% of GSDP)",
            description=(
                "State spending on creation of fixed assets (schools, roads, "
                "irrigation, hospitals) as a share of GSDP. Per-capita matters more "
                "than per-GSDP for some uses — use the small-multiples view to "
                "see trajectory."
            ),
            direction="higher_is_better",
            comparability="comparable_with_normalisation",
            attribution_geography="where_administered",
            icon="factory",
            funding_split_state_pct=100,
            notes="Excludes capital receipts (loans, recoveries). Capital outlay = actual asset creation.",
        ),
        IndicatorMeta(
            indicator_id="in.fiscal.own_non_tax_revenue_pct_gsdp",
            title="Own non-tax revenue (% of GSDP)",
            description=(
                "Royalties (notably mineral royalties), state-PSU dividends, user "
                "charges, and interest receipts as a share of GSDP. Mineral-royalty-"
                "heavy states (Odisha, Jharkhand, Chhattisgarh) sit on a different "
                "fiscal posture than manufacturing/services states."
            ),
            direction="higher_is_better",
            comparability="comparable_with_normalisation",
            attribution_geography="where_produced",
            icon="coins",
            funding_split_state_pct=100,
            notes=(
                "Mineral-royalty-heavy states should not be ranked head-to-head "
                "with manufacturing/services states without a per-capita or "
                "per-GSDP-ex-mining caveat."
            ),
        ),
        IndicatorMeta(
            indicator_id="in.fiscal.central_transfers_pct_revenue_receipts",
            title="Central transfers (% of revenue receipts)",
            description=(
                "Share of state revenue receipts coming from the centre — Finance "
                "Commission devolution + central grants. By Constitutional design, "
                "this is HIGHER for states with weaker own-revenue capacity. A high "
                "value is not a state failure."
            ),
            direction="neutral",
            comparability="not_comparable_across_states",
            attribution_geography="where_administered",
            icon="scale",
            funding_split_state_pct=0,
            notes=(
                "Suppress ranked-table rank: the Finance Commission's horizontal "
                "devolution formula deliberately raises this share for poorer/"
                "lower-capacity states. Read as fiscal context, not performance."
            ),
        ),
    )
}

assert set(INDICATOR_META.keys()) == {s.indicator_id for s in INDICATOR_SPECS}, (
    "INDICATOR_META and INDICATOR_SPECS must cover the same indicator ids"
)


# ---------------------------------------------------------------------------
# Source resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkbookBytes:
    """The XLSX bytes plus what we know about where they came from.

    ``url`` is the canonical RBI URL when known (registry or env var).
    ``fetched_at`` is when the bytes were retrieved (for the ``sources[]``
    array); when bytes were loaded from the local cache, this is the
    file's mtime — honest about the actual freshness.
    """

    content: bytes
    url: str
    fetched_at: datetime


def _resolve_source(*, fetcher: Fetcher, repo_root: Path) -> WorkbookBytes:
    """Try registry → env → local cache, in that order."""
    # 1. Pinned registry.
    pinned = latest_known_url()
    if pinned is not None:
        _, url = pinned
        result: FetchResult = fetcher.fetch(url)
        return WorkbookBytes(content=result.content, url=result.url, fetched_at=result.fetched_at)

    # 2. Env override.
    env_url = os.environ.get("RBI_STATE_FINANCES_URL", "").strip()
    if env_url:
        result = fetcher.fetch(env_url)
        return WorkbookBytes(content=result.content, url=result.url, fetched_at=result.fetched_at)

    # 3. Local cache (operator manually downloaded).
    cache_dir = repo_root / ".runtime" / "raw" / RBI_SOURCE_NAME / "state_finances"
    if cache_dir.exists():
        candidates = sorted(cache_dir.glob("*.xlsx"))
        if candidates:
            latest = candidates[-1]
            mtime = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).replace(
                microsecond=0
            )
            return WorkbookBytes(
                content=latest.read_bytes(),
                # No real URL — surface the listing page as best-effort
                # provenance so the citizen can find the source.
                url=LISTING_PAGE,
                fetched_at=mtime,
            )

    raise RBISourceUnavailable(
        "No RBI workbook source available. Either:\n"
        f"  (a) pin a URL in {Path('backend/yen_gov/sources/rbi_xlsx/urls.py').as_posix()}\n"
        "  (b) set RBI_STATE_FINANCES_URL to the direct XLSX URL\n"
        f"  (c) download the workbook from {LISTING_PAGE}\n"
        "      and save it as .runtime/raw/rbi/state_finances/<year>.xlsx"
    )


# ---------------------------------------------------------------------------
# Indicator artifact builder
# ---------------------------------------------------------------------------


def _build_indicator_payload(
    *,
    spec: IndicatorSpec,
    parsed: ParsedIndicator,
    workbook_url: str,
    workbook_fetched_at: datetime,
) -> dict[str, Any]:
    meta = INDICATOR_META[spec.indicator_id]

    # The parser emits one row per (state, year_span, qualifier-as-facet).
    # Schema requires non-empty rows; the parser already guarantees this
    # by raising RBIWorkbookShapeError on empty matches.
    rows = [
        {
            "entity_id": r.entity_id,
            "time": r.time,
            "value": r.value,
            "facet": r.facet,
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
            "Workbook bytes loaded from local cache; ``sources[].url`` points "
            "to the RBI listing page rather than the direct XLSX URL because "
            "no pinned URL was available at ingest time."
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
            "unit": spec.denominator,
            "denominator": _denominator_id(spec.denominator),
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


def _denominator_id(unit: str) -> str:
    if "GSDP" in unit:
        return "gsdp_current_prices"
    if "revenue receipts" in unit.lower():
        return "revenue_receipts"
    return "unknown"


def _coverage_temporal(parsed: ParsedIndicator) -> str:
    times = sorted({r.time for r in parsed.rows})
    if not times:
        return "unknown"
    return f"{times[0]}..{times[-1]}"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IngestResult:
    """Summary of a successful ingest run."""

    indicator_paths: tuple[Path, ...]
    workbook_url: str
    workbook_fetched_at: datetime
    sheet_names: tuple[str, ...]


def ingest(
    *,
    fetcher: Fetcher,
    repo_root: Path,
    schema_dir: Path,
) -> IngestResult:
    """Fetch the RBI workbook, parse all 8 fiscal indicators, write artifacts.

    Idempotent: re-runs overwrite the artifacts and re-stamp ``fetched_at``.
    Raises:
        RBISourceUnavailable: no resolvable source.
        RBIWorkbookShapeError: workbook layout has shifted; re-run recon.
    """
    wb_bytes = _resolve_source(fetcher=fetcher, repo_root=repo_root)
    parsed = parse_state_finances_workbook(wb_bytes.content)

    # One row per spec, in the same order they appear in INDICATOR_SPECS.
    parsed_by_id: dict[str, ParsedIndicator] = {p.indicator_id: p for p in parsed.indicators}

    indicator_schema_path = schema_dir / "indicator.schema.json"
    indicator_schema = json.loads(indicator_schema_path.read_text(encoding="utf-8"))

    out_dir = repo_root / "datasets" / "indicators" / "in" / "fiscal"
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for spec in INDICATOR_SPECS:
        parsed_indicator = parsed_by_id[spec.indicator_id]
        payload = _build_indicator_payload(
            spec=spec,
            parsed=parsed_indicator,
            workbook_url=wb_bytes.url,
            workbook_fetched_at=wb_bytes.fetched_at,
        )
        # Filename strips the "in.fiscal." prefix for path-readability.
        leaf = spec.indicator_id.removeprefix("in.fiscal.") + ".json"
        path = out_dir / leaf
        write_artifact(
            path=path,
            schema_id=indicator_schema["$id"],
            schema_version=indicator_schema["x-version"],
            payload=payload,
            sources=[
                Source(url=wb_bytes.url, fetched_at=wb_bytes.fetched_at),
                Source(url=RBI_AUTHORITY_URL, fetched_at=wb_bytes.fetched_at),
            ],
            schema_for_validation=indicator_schema,
        )
        written.append(path)

    return IngestResult(
        indicator_paths=tuple(written),
        workbook_url=wb_bytes.url,
        workbook_fetched_at=wb_bytes.fetched_at,
        sheet_names=tuple(parsed.workbook_sheet_names),
    )


# Local-cache loader for offline parser tests / operator dry runs.
def load_local_cached_bytes(repo_root: Path) -> bytes | None:
    """Return the most recent locally-cached workbook bytes, or None."""
    cache_dir = repo_root / ".runtime" / "raw" / RBI_SOURCE_NAME / "state_finances"
    if not cache_dir.exists():
        return None
    candidates = sorted(cache_dir.glob("*.xlsx"))
    return candidates[-1].read_bytes() if candidates else None
