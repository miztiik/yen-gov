"""Orchestrator for RBI Appendix Table 1 (Major Deficit Indicators) ingest.

No network. Reads the workbook from
``.runtime/raw/rbi/state_finances/AppT1_MajorDeficitIndicators_2026.xlsx``
(or operator-overridden via env), runs the pure parser, and writes four
canonical national indicator artifacts under
``datasets/indicators/in/fiscal/states_combined_*_deficit.json``.

This is the cache-only sibling of ``rbi_appendix_national``: same RBI
publication (State Finances), different appendix table, different layout.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv

from .parsers import (
    SHIPPED_SPECS,
    DeficitSpec,
    ParsedIndicator,
    parse_workbook,
)


# B1.5.3 - canonical CSV citation triple for RBI State Finances Appendix
# Table 1 (Major Deficit Indicators of State Governments). All four
# SHIPPED_SPECS rows share one publication; vintage per ADR-0042 is the
# publisher edition string (2025-26 = State Finances published January
# 2026, see CACHE_RELPATH leaf name). fk-validator is dark on this hash
# until entities/source.csv lands (B2a), by design per sub-plan section
# "Pre-flight - source-id + concept-id readiness".
_CSV_SOURCE_PRODUCER = "Reserve Bank of India"
_CSV_SOURCE_TITLE = (
    "State Finances: A Study of Budgets, Appendix Table 1 "
    "(Major Deficit Indicators of State Governments)"
)
_CSV_SOURCE_VINTAGE = "2025-26"
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"

# Mapping from legacy `<topic>/<leaf>` indicator_id to canonical CSV
# variable_id (kebab-case `<measure>-<unit>-<facet>` per ADR-0044; no
# `__`, no grain prefix, per parent plan section 21.6 / 21.12). The
# `states-combined-` segment is an actor qualifier (all-states aggregate
# vs Union), not a grain prefix.
_INDICATOR_TO_VARIABLE_ID: dict[str, str] = {
    "fiscal/states_combined_gross_fiscal_deficit":
        "states-combined-gross-fiscal-deficit-inr-crore",
    "fiscal/states_combined_revenue_deficit":
        "states-combined-revenue-deficit-inr-crore",
    "fiscal/states_combined_primary_deficit":
        "states-combined-primary-deficit-inr-crore",
    "fiscal/states_combined_primary_revenue_deficit":
        "states-combined-primary-revenue-deficit-inr-crore",
}


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
    "fiscal/states_combined_gross_fiscal_deficit": IndicatorMeta(
        indicator_id="fiscal/states_combined_gross_fiscal_deficit",
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
    "fiscal/states_combined_revenue_deficit": IndicatorMeta(
        indicator_id="fiscal/states_combined_revenue_deficit",
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
    "fiscal/states_combined_primary_deficit": IndicatorMeta(
        indicator_id="fiscal/states_combined_primary_deficit",
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
    "fiscal/states_combined_primary_revenue_deficit": IndicatorMeta(
        indicator_id="fiscal/states_combined_primary_revenue_deficit",
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


def _coverage_temporal(parsed: ParsedIndicator) -> str:  # pragma: no cover
    times = sorted({r.time for r in parsed.rows})
    if not times:
        return "unknown"
    return f"{times[0]}..{times[-1]}"


def _build_payload(*args: Any, **kwargs: Any) -> dict[str, Any]:  # pragma: no cover
    raise RuntimeError(
        "_build_payload retired in B4-pt3; this adapter only emits canonical CSV now"
    )


@dataclass(frozen=True)
class IndicatorIngestResult:
    """Per-CSV emit receipt."""
    indicator_id: str
    csv_path: Path
    workbook_fetched_at: datetime
    period_count: int
    row_count: int


@dataclass(frozen=True)
class IngestResult:
    indicators: tuple[IndicatorIngestResult, ...]


def _slug_segment(text: str) -> str:
    """Kebab-case a segment for use inside a `variable_id`.

    Mirrors the sibling rbi_hbs_ie_centre_deficits helper; lifted here
    verbatim to keep this family self-contained. Parent plan section
    21.6 / 21.12 ban `__`; ADR-0044 bans grain-prefixes.
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


def _fy_start_year(time_str: str) -> int:
    """Lift the fiscal-year start year (integer) from a parser time stamp.

    The shared parser emits ``"YYYY-04"`` (start-of-FY). The canonical
    CSV file class ``datasets/data/datapoints/geo/*.csv`` declares
    ``time`` as integer; we lift the FY start year as the canonical
    integer time. Raises ``ValueError`` if the stamp is malformed -
    failing fast at the boundary (CLAUDE.md anti-pattern: no silent
    coercion).
    """
    head, _, _ = time_str.partition("-")
    return int(head)


def build_csv_variables(
    spec: DeficitSpec,
    parsed: ParsedIndicator,
    *,
    source_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Build per-`variable_id` CSV row lists for one parsed indicator.

    Each row carries the four canonical columns declared on file class
    ``datasets/data/datapoints/geo/*.csv``: ``entity_id``, ``time``,
    ``value``, ``source_id``. The four SHIPPED_SPECS each map 1:1 to a
    single ``variable_id`` (no faceting on this family - one column per
    indicator on the AppT1 sheet). ``entity_id`` is ``"IN"`` per the
    parent plan F4 freeze for national-grain (all-states-combined)
    aggregate rows.
    """
    variable_id = _INDICATOR_TO_VARIABLE_ID[spec.indicator_id]
    rows: list[dict[str, Any]] = []
    for r in parsed.rows:
        if r.value is None:
            continue
        rows.append({
            "entity_id": r.entity_id,
            "time": _fy_start_year(r.time),
            "value": r.value,
            "source_id": source_id,
        })
    return {variable_id: rows}


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


def ingest(*, repo_root: Path, schema_dir: Path | None = None) -> IngestResult:
    """Read cached workbook, parse all shipped specs, emit canonical CSV variables.

    Under B4-pt3 (no strangler-fig per umbrella plan O1), only the
    canonical long-format CSV under ``datasets/data/datapoints/geo/``
    is emitted. ``schema_dir`` is accepted for back-compat but unused.
    """
    del schema_dir  # back-compat shim

    content, mtime, _url = _resolve_workbook(repo_root=repo_root)
    parsed_by_id = parse_workbook(content)

    # B1.5.3 - one citation-ledger source_id shared across all four
    # SHIPPED_SPECS (same State Finances Appendix T1 publication / edition).
    csv_source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE, _CSV_SOURCE_VINTAGE
    )

    results: list[IndicatorIngestResult] = []
    for spec in SHIPPED_SPECS:
        parsed = parsed_by_id[spec.indicator_id]
        by_variable = build_csv_variables(spec, parsed, source_id=csv_source_id)
        emitted = emit_csv_variables(repo_root=repo_root, by_variable=by_variable)
        csv_path = emitted[0] if emitted else (
            repo_root / _CSV_OUT_REL_DIR
            / f"{_INDICATOR_TO_VARIABLE_ID[spec.indicator_id]}.csv"
        )
        results.append(
            IndicatorIngestResult(
                indicator_id=spec.indicator_id,
                csv_path=csv_path,
                workbook_fetched_at=mtime,
                period_count=parsed.period_count,
                row_count=len(parsed.rows),
            )
        )

    return IngestResult(indicators=tuple(results))
