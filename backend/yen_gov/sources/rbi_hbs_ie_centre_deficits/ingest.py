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

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.sources.rbi_appendix_deficits.parsers import (
    DeficitSpec,
    ParsedIndicator,
    parse_workbook,
)


# B1.5.2 - canonical CSV citation triple for RBI HBS-IE Table 89 (Union
# Government deficit indicators). All four SHIPPED_SPECS rows share one
# publication; vintage per ADR-0042 is the publisher edition string
# (2024-25 = HBS-IE published 2025-08-29, see HBS_IE_EDITION_NOTE).
# fk-validator is dark on this hash until entities/source.csv lands (B2a),
# by design per sub-plan section "Pre-flight - source-id + concept-id
# readiness".
_CSV_SOURCE_PRODUCER = "Reserve Bank of India"
_CSV_SOURCE_TITLE = (
    "Handbook of Statistics on Indian Economy, Table 89 "
    "(Key Deficit Indicators of the Central Government)"
)
_CSV_SOURCE_VINTAGE = "2024-25"
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"

# Mapping from legacy `<topic>/<leaf>` indicator_id to canonical CSV
# variable_id (kebab-case `<measure>-<unit>-<facet>` per ADR-0044; no
# `__`, no grain prefix, per parent plan section 21.6 / 21.12). The
# `union-` segment is an actor qualifier (Union vs states-combined), not
# a grain prefix.
_INDICATOR_TO_VARIABLE_ID: dict[str, str] = {
    "fiscal/union_gross_fiscal_deficit":
        "union-gross-fiscal-deficit-inr-crore",
    "fiscal/union_revenue_deficit":
        "union-revenue-deficit-inr-crore",
    "fiscal/union_primary_deficit":
        "union-primary-deficit-inr-crore",
    "fiscal/union_primary_revenue_deficit":
        "union-primary-revenue-deficit-inr-crore",
}


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
                f"recorded in this module as PINNED_XLSX_URL_2024_25."
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

    Mirrors the sibling rbi_appendix_national helper; lifted here
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
    indicator on the HBS-IE Table 89 sheet). ``entity_id`` is ``"IN"``
    per the parent plan F4 freeze for national-grain rows.
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
    parsed_by_id = parse_workbook(content, specs=SHIPPED_SPECS)

    # B1.5.2 - one citation-ledger source_id shared across all four
    # SHIPPED_SPECS (same HBS-IE Table 89 publication / edition).
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
