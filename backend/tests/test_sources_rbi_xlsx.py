"""Pure-parser tests for backend/yen_gov/sources/rbi_xlsx/parsers.py.

Uses a hand-crafted in-memory openpyxl workbook so the test suite needs
no real RBI bytes (and stays runnable offline). The workbook mirrors the
shape pattern of RBI's State Finances Excel companion: per-sheet
state-name header rows followed by item rows, with year-period column
headers like ``2022-23``, ``2023-24 (RE)``, ``2024-25 (BE)``.
"""
from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from yen_gov.sources.rbi_xlsx.parsers import (
    INDICATOR_SPECS,
    IndicatorSpec,
    RBIWorkbookShapeError,
    normalise_state_label,
    parse_state_finances_workbook,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wb_to_bytes(wb: Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_synthetic_workbook(
    *,
    sheet_name: str,
    item_label: str,
    state_blocks: list[tuple[str, dict[str, float | None]]],
) -> bytes:
    """Build an RBI-shaped workbook with one sheet.

    Each ``state_blocks`` entry is ``(state_name, {year_header: value})``.
    The sheet layout is::

        Row 0:  ["",      "Item",       "2022-23",  "2023-24 (RE)",  "2024-25 (BE)"]
        Row 1:  ["TamilNadu", "",        "",         "",              ""]
        Row 2:  ["",      "<item>",     <val>,      <val>,           <val>]
        Row 3:  ["Kerala", ...]
        ...
    """
    wb = Workbook()
    sheet = wb.active
    assert sheet is not None
    sheet.title = sheet_name

    # Header row.
    year_headers = ["2022-23", "2023-24 (RE)", "2024-25 (BE)"]
    sheet.append(["", "Item", *year_headers])

    for state_name, year_to_val in state_blocks:
        # State header row (state name in the FIRST cell, nothing else).
        sheet.append([state_name, "", "", "", ""])
        # Item row (item label in the second cell — first non-empty cell).
        sheet.append(["", item_label, *(year_to_val.get(y) for y in year_headers)])

    return _wb_to_bytes(wb)


# ---------------------------------------------------------------------------
# normalise_state_label
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Tamil Nadu", "S22"),
        ("tamil nadu", "S22"),
        ("  TAMIL  NADU  ", "S22"),
        ("Orissa", "S18"),
        ("Odisha", "S18"),
        ("J&K", "S09"),
        ("Jammu and Kashmir", "S09"),
        ("Uttaranchal", "S28"),
        ("NCT of Delhi", "U05"),
        ("", None),
        ("Atlantis", None),
        (None, None),
    ],
)
def test_normalise_state_label(raw, expected):
    assert normalise_state_label(raw) == expected


# ---------------------------------------------------------------------------
# parse_state_finances_workbook — happy path
# ---------------------------------------------------------------------------


def test_parse_emits_one_row_per_state_year_facet():
    spec = IndicatorSpec(
        indicator_id="in.fiscal.test_metric",
        sheet_match="own tax",
        row_label="own tax revenue",
        denominator="% of GSDP",
    )
    xlsx = _make_synthetic_workbook(
        sheet_name="States Own Tax Revenue",
        item_label="Own Tax Revenue",
        state_blocks=[
            ("Tamil Nadu", {"2022-23": 7.1, "2023-24 (RE)": 7.3, "2024-25 (BE)": 7.5}),
            ("Kerala", {"2022-23": 6.4, "2023-24 (RE)": 6.6, "2024-25 (BE)": 6.8}),
        ],
    )
    parsed = parse_state_finances_workbook(xlsx, specs=(spec,))
    assert len(parsed.indicators) == 1
    ind = parsed.indicators[0]
    assert ind.indicator_id == "in.fiscal.test_metric"

    # 2 states × 3 year columns = 6 rows.
    assert len(ind.rows) == 6
    rows_by_key = {(r.entity_id, r.time, r.facet): r.value for r in ind.rows}
    assert rows_by_key[("S22", "2022-04", "Accounts")] == 7.1
    assert rows_by_key[("S22", "2023-04", "RE")] == 7.3
    assert rows_by_key[("S22", "2024-04", "BE")] == 7.5
    assert rows_by_key[("S11", "2022-04", "Accounts")] == 6.4
    assert rows_by_key[("S11", "2024-04", "BE")] == 6.8


def test_parse_treats_blank_and_dash_as_null():
    spec = IndicatorSpec(
        indicator_id="in.fiscal.test_metric",
        sheet_match="own tax",
        row_label="own tax revenue",
        denominator="% of GSDP",
    )
    xlsx = _make_synthetic_workbook(
        sheet_name="States Own Tax Revenue",
        item_label="Own Tax Revenue",
        state_blocks=[
            ("Tamil Nadu", {"2022-23": None, "2023-24 (RE)": 7.3, "2024-25 (BE)": 7.5}),
        ],
    )
    parsed = parse_state_finances_workbook(xlsx, specs=(spec,))
    rows = parsed.indicators[0].rows
    null_row = next(r for r in rows if r.time == "2022-04")
    assert null_row.value is None


def test_parse_records_unmatched_state_labels():
    spec = IndicatorSpec(
        indicator_id="in.fiscal.test_metric",
        sheet_match="own tax",
        row_label="own tax revenue",
        denominator="% of GSDP",
    )
    xlsx = _make_synthetic_workbook(
        sheet_name="States Own Tax Revenue",
        item_label="Own Tax Revenue",
        state_blocks=[
            ("Tamil Nadu", {"2022-23": 7.1, "2023-24 (RE)": 7.3, "2024-25 (BE)": 7.5}),
            ("Atlantis", {"2022-23": 99.0, "2023-24 (RE)": 99.0, "2024-25 (BE)": 99.0}),
        ],
    )
    parsed = parse_state_finances_workbook(xlsx, specs=(spec,))
    ind = parsed.indicators[0]
    assert "Atlantis" in ind.unmatched_states
    # Atlantis rows must NOT appear; only Tamil Nadu's 3 rows survive.
    assert {r.entity_id for r in ind.rows} == {"S22"}
    assert len(ind.rows) == 3


# ---------------------------------------------------------------------------
# parse_state_finances_workbook — fail-loud paths
# ---------------------------------------------------------------------------


def test_parse_raises_on_missing_sheet():
    spec = IndicatorSpec(
        indicator_id="in.fiscal.test_metric",
        sheet_match="nonexistent",
        row_label="own tax revenue",
        denominator="% of GSDP",
    )
    xlsx = _make_synthetic_workbook(
        sheet_name="States Own Tax Revenue",
        item_label="Own Tax Revenue",
        state_blocks=[("Tamil Nadu", {"2022-23": 7.1, "2023-24 (RE)": 7.3, "2024-25 (BE)": 7.5})],
    )
    with pytest.raises(RBIWorkbookShapeError, match="no sheet matched"):
        parse_state_finances_workbook(xlsx, specs=(spec,))


def test_parse_raises_on_missing_row_label():
    spec = IndicatorSpec(
        indicator_id="in.fiscal.test_metric",
        sheet_match="own tax",
        row_label="phantom item that does not exist",
        denominator="% of GSDP",
    )
    xlsx = _make_synthetic_workbook(
        sheet_name="States Own Tax Revenue",
        item_label="Own Tax Revenue",
        state_blocks=[("Tamil Nadu", {"2022-23": 7.1, "2023-24 (RE)": 7.3, "2024-25 (BE)": 7.5})],
    )
    with pytest.raises(RBIWorkbookShapeError, match="no row matched"):
        parse_state_finances_workbook(xlsx, specs=(spec,))


def test_parse_raises_when_no_state_resolves():
    """Sheet exists, row label matches, but no state name maps to ECI →
    no rows materialise → fail loud."""
    spec = IndicatorSpec(
        indicator_id="in.fiscal.test_metric",
        sheet_match="own tax",
        row_label="own tax revenue",
        denominator="% of GSDP",
    )
    xlsx = _make_synthetic_workbook(
        sheet_name="States Own Tax Revenue",
        item_label="Own Tax Revenue",
        state_blocks=[("Atlantis", {"2022-23": 1.0, "2023-24 (RE)": 1.0, "2024-25 (BE)": 1.0})],
    )
    with pytest.raises(RBIWorkbookShapeError, match="no data rows materialised"):
        parse_state_finances_workbook(xlsx, specs=(spec,))


# ---------------------------------------------------------------------------
# Specs sanity
# ---------------------------------------------------------------------------


def test_indicator_specs_cover_all_eight_documented_ids():
    expected = {
        "in.fiscal.own_tax_revenue_pct_gsdp",
        "in.fiscal.revenue_deficit_pct_gsdp",
        "in.fiscal.gross_fiscal_deficit_pct_gsdp",
        "in.fiscal.outstanding_debt_pct_gsdp",
        "in.fiscal.interest_payments_pct_revenue_receipts",
        "in.fiscal.capital_outlay_pct_gsdp",
        "in.fiscal.own_non_tax_revenue_pct_gsdp",
        "in.fiscal.central_transfers_pct_revenue_receipts",
    }
    assert {s.indicator_id for s in INDICATOR_SPECS} == expected
