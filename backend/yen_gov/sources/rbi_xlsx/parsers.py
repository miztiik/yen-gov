"""Pure parser for the RBI ``State Finances: A Study of Budgets`` Excel companion.

This module is layout-driven and fail-loud. The exact column headers in
each annual edition of the workbook drift slightly (RBI tweaks the
Statement numbering and adds/removes derived sheets every December), so
we never hard-code a column index. Instead each ``IndicatorSpec``
declares:

  - ``sheet_match``    — substring search across sheet names
  - ``row_label``      — substring of the row's first cell (item name)
  - ``year_pattern``   — regex over column headers; each match becomes one row
  - ``state_aliases``  — extra raw labels mapping to canonical ECI state codes

A spec that matches no sheet, no row, or no year columns raises
``RBIWorkbookShapeError`` with a descriptive message. We never silently
emit zero rows — that would lie to the citizen about coverage.

Entirely pure: the orchestrator in ``ingest.py`` does network + writes.
This module is exercised in ``tests/test_sources_rbi_xlsx.py`` against a
hand-crafted in-memory workbook (no real RBI bytes in the test suite).

See ``docs/architecture/backend/sources-rbi.md`` for the indicator
contracts each spec materialises.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

from openpyxl import load_workbook
from openpyxl.workbook import Workbook


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RBIWorkbookShapeError(ValueError):
    """Raised when the workbook's shape no longer matches the parser's
    expectations (sheet renamed, row label gone, headers reformatted).
    Carries enough context for a maintainer to update the spec or
    re-run recon."""


# ---------------------------------------------------------------------------
# State-name normalisation
# ---------------------------------------------------------------------------


# RBI uses a mix of "Tamil Nadu", "TamilNadu", "Tamil  Nadu" depending
# on year/sheet. Normalise to canonical ECI state name. Keys are
# lowercased + whitespace-collapsed.
_STATE_NAME_TO_ECI: dict[str, str] = {
    "andhra pradesh": "S01",
    "arunachal pradesh": "S02",
    "assam": "S03",
    "bihar": "S04",
    "chhattisgarh": "S26",
    "goa": "S05",
    "gujarat": "S06",
    "haryana": "S07",
    "himachal pradesh": "S08",
    "jammu and kashmir": "S09",
    "j&k": "S09",
    "jharkhand": "S27",
    "karnataka": "S10",
    "kerala": "S11",
    "madhya pradesh": "S12",
    "maharashtra": "S13",
    "manipur": "S14",
    "meghalaya": "S15",
    "mizoram": "S16",
    "nagaland": "S17",
    "odisha": "S18",
    "orissa": "S18",
    "punjab": "S19",
    "rajasthan": "S20",
    "sikkim": "S21",
    "tamil nadu": "S22",
    "telangana": "S29",
    "tripura": "S23",
    "uttar pradesh": "S24",
    "uttarakhand": "S28",
    "uttaranchal": "S28",
    "west bengal": "S25",
    # Union territories with legislatures (kept here so RBI's "all states
    # + 2 UTs" tables do not crash; the indicator-emit side decides
    # whether to publish them — see sources-rbi.md honesty register).
    "delhi": "U05",
    "nct of delhi": "U05",
    "puducherry": "U07",
}


def normalise_state_label(raw: str | None) -> str | None:
    """Return the ECI state code for a raw RBI state label, or ``None``."""
    if not raw:
        return None
    key = " ".join(str(raw).strip().lower().split())
    return _STATE_NAME_TO_ECI.get(key)


# ---------------------------------------------------------------------------
# Spec + parsed-row dataclasses
# ---------------------------------------------------------------------------


# Recognise period labels like "2022-23", "2023-24 (RE)", "2024-25 (BE)",
# "2024-25 BE", "2024 - 25  Accounts". Group 1 captures the year span;
# group 2 (optional) the qualifier.
_YEAR_RE = re.compile(
    r"(?P<span>\d{4}\s*-\s*\d{2,4})\s*(?:\(?\s*(?P<qual>RE|BE|Accounts|A|B|R)\s*\)?)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IndicatorSpec:
    """Locate one indicator within an RBI workbook.

    Args:
        indicator_id: stable id, e.g. ``in.fiscal.own_tax_revenue_pct_gsdp``.
        sheet_match: case-insensitive substring of the sheet name.
        row_label: case-insensitive substring of the row's first non-empty cell
            (the "Item" column).
        denominator: human label for the denominator (drives suffix on the
            indicator's ``unit`` field). One of "% of GSDP" or
            "% of revenue receipts".
        sign: +1 normally; -1 when the workbook reports the value with
            opposite sign convention to our schema (e.g. some sheets give
            ``surplus`` where we want ``deficit``).
    """

    indicator_id: str
    sheet_match: str
    row_label: str
    denominator: str
    sign: int = 1


@dataclass(frozen=True)
class ParsedRow:
    """One indicator-schema row: (entity, time, value, facet)."""

    entity_id: str
    time: str
    value: float | None
    facet: str | None = None


@dataclass
class ParsedIndicator:
    indicator_id: str
    rows: list[ParsedRow] = field(default_factory=list)
    unmatched_states: list[str] = field(default_factory=list)


@dataclass
class ParsedFiscals:
    """All indicators parsed in one pass."""

    indicators: list[ParsedIndicator] = field(default_factory=list)
    workbook_sheet_names: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# The 8 specs from sources-rbi.md
# ---------------------------------------------------------------------------


# NOTE: ``sheet_match`` and ``row_label`` strings here are best-effort
# starting guesses. Phase B's recon may shift them as we see the actual
# workbook structure; updating a string here is the only change needed
# (no parser-logic edit) — exactly the design intent.
INDICATOR_SPECS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        indicator_id="in.fiscal.own_tax_revenue_pct_gsdp",
        sheet_match="own tax",
        row_label="own tax revenue",
        denominator="% of GSDP",
    ),
    IndicatorSpec(
        indicator_id="in.fiscal.revenue_deficit_pct_gsdp",
        sheet_match="revenue deficit",
        row_label="revenue deficit",
        denominator="% of GSDP",
    ),
    IndicatorSpec(
        indicator_id="in.fiscal.gross_fiscal_deficit_pct_gsdp",
        sheet_match="gross fiscal deficit",
        row_label="gross fiscal deficit",
        denominator="% of GSDP",
    ),
    IndicatorSpec(
        indicator_id="in.fiscal.outstanding_debt_pct_gsdp",
        sheet_match="outstanding liabilities",
        row_label="outstanding liabilities",
        denominator="% of GSDP",
    ),
    IndicatorSpec(
        indicator_id="in.fiscal.interest_payments_pct_revenue_receipts",
        sheet_match="interest payments",
        row_label="interest payments",
        denominator="% of revenue receipts",
    ),
    IndicatorSpec(
        indicator_id="in.fiscal.capital_outlay_pct_gsdp",
        sheet_match="capital outlay",
        row_label="capital outlay",
        denominator="% of GSDP",
    ),
    IndicatorSpec(
        indicator_id="in.fiscal.own_non_tax_revenue_pct_gsdp",
        sheet_match="non-tax",
        row_label="own non-tax revenue",
        denominator="% of GSDP",
    ),
    IndicatorSpec(
        indicator_id="in.fiscal.central_transfers_pct_revenue_receipts",
        sheet_match="central transfers",
        row_label="central transfers",
        denominator="% of revenue receipts",
    ),
)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _normalise_year(span_text: str, qualifier: str | None) -> str:
    """Turn "2022-23" + "RE" into "2022-23"; the qualifier is dropped from
    the time field since it lives in the indicator's notes/methodology
    vintage, not in time.

    The schema's ``time`` accepts ``YYYY``, ``YYYY-MM``, ``YYYY-MM-DD``
    — RBI fiscal years are ``YYYY-MM`` style ("2022-04" would be wrong;
    we keep the RBI canonical form ``2022-23`` which the schema's
    pattern accepts as long as it parses; defer formal validation to
    ``write_artifact``).

    The schema's ``time`` pattern is ``YYYY``, ``YYYY-MM``, or
    ``YYYY-MM-DD`` (see indicator.schema.json). RBI's ``2022-23`` is
    none of those, so we map fiscal-year span ``YYYY-YY`` to
    ``YYYY-04`` (April-start fiscal year) — preserving sortability and
    schema-compatibility while still being honest about the period.
    """
    del qualifier  # captured upstream; not encoded in time
    digits = re.findall(r"\d+", span_text)
    if not digits:
        raise RBIWorkbookShapeError(f"unparseable year span: {span_text!r}")
    start = digits[0]
    if len(start) != 4:
        raise RBIWorkbookShapeError(f"year span did not start with 4 digits: {span_text!r}")
    return f"{start}-04"  # April = start of Indian fiscal year


def _qualifier_facet(qualifier: str | None) -> str | None:
    """RBI columns are Accounts (T-2), RE (T-1), BE (T-0). We surface the
    distinction as a facet so the citizen sees revised vs budgeted.
    """
    if not qualifier:
        return "Accounts"
    q = qualifier.strip().upper()
    if q in {"A", "ACCOUNTS"}:
        return "Accounts"
    if q in {"R", "RE"}:
        return "RE"
    if q in {"B", "BE"}:
        return "BE"
    return q


def _coerce_value(raw: Any, sign: int) -> float | None:
    """Best-effort numeric coercion. Returns ``None`` on RBI's blank /
    em-dash / "N.A." sentinels. Treats negatives faithfully."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        v = float(raw)
        return v * sign
    s = str(raw).strip()
    if not s or s in {"—", "-", "–", "N.A.", "NA", "n.a.", "na"}:
        return None
    # Strip commas, parens-as-negative.
    s = s.replace(",", "").replace("\xa0", "")
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    try:
        v = float(s)
    except ValueError:
        return None
    if neg:
        v = -v
    return v * sign


def _find_sheet(wb: Workbook, sheet_match: str) -> str:
    needle = sheet_match.lower().strip()
    for name in wb.sheetnames:
        if needle in name.lower():
            return name
    raise RBIWorkbookShapeError(
        f"no sheet matched {sheet_match!r}; saw {wb.sheetnames!r}"
    )


def _find_year_columns(header_row: list[Any]) -> list[tuple[int, str, str | None]]:
    """Return ``(column_index, year_span, qualifier)`` for every header
    cell that looks like an RBI fiscal-year period.
    """
    out: list[tuple[int, str, str | None]] = []
    for idx, cell in enumerate(header_row):
        if cell is None:
            continue
        text = str(cell)
        m = _YEAR_RE.search(text)
        if m:
            out.append((idx, m.group("span"), m.group("qual")))
    return out


def _find_data_rows(
    sheet_rows: list[list[Any]],
    row_label: str,
) -> list[int]:
    """Return all row indices whose first non-empty cell contains
    ``row_label`` (case-insensitive substring). Multiple matches are
    allowed — RBI's per-state sub-tables repeat the row label per state.
    """
    needle = row_label.lower().strip()
    hits: list[int] = []
    for i, row in enumerate(sheet_rows):
        for cell in row:
            if cell is None:
                continue
            s = str(cell).strip()
            if not s:
                continue
            if needle in s.lower():
                hits.append(i)
            break  # first non-empty cell only
    return hits


def _state_label_for_data_row(
    sheet_rows: list[list[Any]],
    data_row_idx: int,
) -> str | None:
    """Walk back from a data row to the nearest state-name header row.

    A "header row" is the most recent row above whose first cell is
    non-empty (RBI sheets put the state name in column 0 of a header
    row, then leave column 0 blank on the item rows that follow). The
    returned string is the raw header text — the caller decides whether
    it normalises to a known ECI state.

    This shape lets the orchestrator record unknown labels (e.g. a row
    titled "All States" or a typo) without mis-attributing them to the
    most recent KNOWN state above.
    """
    for i in range(data_row_idx - 1, -1, -1):
        row = sheet_rows[i]
        if not row:
            continue
        first = row[0]
        if first is None:
            continue
        s = str(first).strip()
        if not s:
            continue
        return s
    return None


def _parse_one_indicator(
    wb: Workbook,
    spec: IndicatorSpec,
) -> ParsedIndicator:
    sheet_name = _find_sheet(wb, spec.sheet_match)
    sheet = wb[sheet_name]
    rows: list[list[Any]] = [list(r) for r in sheet.iter_rows(values_only=True)]

    # Header row = first row with at least 2 year-pattern hits.
    year_columns: list[tuple[int, str, str | None]] = []
    header_idx = -1
    for i, r in enumerate(rows):
        cols = _find_year_columns(r)
        if len(cols) >= 2:
            year_columns = cols
            header_idx = i
            break
    if not year_columns:
        raise RBIWorkbookShapeError(
            f"no year-pattern header row in sheet {sheet_name!r} "
            f"for {spec.indicator_id}"
        )

    data_row_idxs = [i for i in _find_data_rows(rows, spec.row_label) if i > header_idx]
    if not data_row_idxs:
        raise RBIWorkbookShapeError(
            f"no row matched label {spec.row_label!r} in sheet {sheet_name!r} "
            f"for {spec.indicator_id}"
        )

    out = ParsedIndicator(indicator_id=spec.indicator_id)
    seen_states: set[str] = set()
    for data_idx in data_row_idxs:
        raw_state = _state_label_for_data_row(rows, data_idx)
        eci = normalise_state_label(raw_state)
        if not eci:
            if raw_state and raw_state not in seen_states:
                out.unmatched_states.append(raw_state)
                seen_states.add(raw_state)
            continue
        for col_idx, span, qual in year_columns:
            try:
                cell = rows[data_idx][col_idx]
            except IndexError:
                continue
            value = _coerce_value(cell, spec.sign)
            time = _normalise_year(span, qual)
            facet = _qualifier_facet(qual)
            out.rows.append(
                ParsedRow(entity_id=eci, time=time, value=value, facet=facet)
            )

    if not out.rows:
        raise RBIWorkbookShapeError(
            f"no data rows materialised for {spec.indicator_id} "
            f"(sheet {sheet_name!r}, row {spec.row_label!r}); workbook layout "
            "may have shifted — re-run recon."
        )
    return out


def parse_state_finances_workbook(
    xlsx_bytes: bytes,
    specs: tuple[IndicatorSpec, ...] = INDICATOR_SPECS,
) -> ParsedFiscals:
    """Parse all 8 fiscal indicators from one RBI Excel workbook.

    Raises:
        RBIWorkbookShapeError: when any spec fails to locate its
            sheet/row/year-columns. Failure of one indicator aborts the
            whole parse — half-shipped fiscal data is worse than none.
    """
    wb = load_workbook(io.BytesIO(xlsx_bytes), data_only=True, read_only=True)
    try:
        out = ParsedFiscals(workbook_sheet_names=list(wb.sheetnames))
        for spec in specs:
            out.indicators.append(_parse_one_indicator(wb, spec))
        return out
    finally:
        wb.close()
