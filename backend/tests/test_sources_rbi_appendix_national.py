"""Pure-parser tests for the RBI Appendix Table 2 (national) adapter.

Synthetic in-memory workbooks model the layout documented in
``tools/rbi_appendix_recon.py`` output for ``02_APP_devolution_transfers.xlsx``:

  row 1: title text
  row 2: unit annotation ("(₹ Crore)")
  row 3: header row — col 1 = "Item", cols 2..N = fiscal-year periods
         (some periods carry qualifiers like "(Accounts)", "(Budget Estimates)")
  row 4: column-index row ("1 2 3 …") — skipped
  rows 5..: item rows — col 1 = "<roman/arabic>. <Item Name>", cols 2..N = values
  trailer rows: "Note: …", "Source: …", "*: …"

No real RBI bytes touch the test suite.
"""
from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from yen_gov.sources.rbi_appendix_national.parsers import (
    AppendixSpec,
    RBIAppendixShapeError,
    SHIPPED_SPECS,
    _coerce_value,
    _parse_period_header,
    parse_workbook,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _build_workbook(sheets: list[tuple[str, list[list[object]]]]) -> bytes:
    wb = Workbook()
    # Drop the default first sheet.
    wb.remove(wb.active)
    for name, rows in sheets:
        ws = wb.create_sheet(title=name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# A canonical 3-sheet appendix matching the FY08–FY26 layout.
_HEADER_S1 = ["Item", "2007-08", "2008-09", "2009-10"]
_HEADER_S2 = ["Item", "2010-11", "2011-12", "2012-13"]
_HEADER_S3 = ["Item", "2023-24 (Accounts)", "2023-24 (Budget Estimates)", "2024-25 (Revised Estimates)"]

_TITLE = "Appendix Table 2: Devolution and Transfer of Resources from the Centre"
_UNIT = "(₹ Crore)"
_COLIDX_S1 = [None, 1, 2, 3]
_COLIDX_S2 = [None, 4, 5, 6]
_COLIDX_S3 = [None, 7, 8, 9]


def _canonical_workbook() -> bytes:
    return _build_workbook([
        ("APPT_1", [
            [None],
            [_TITLE],
            [_UNIT],
            _HEADER_S1,
            _COLIDX_S1,
            ["I. States' Share in Central Taxes", 100, 110, 120],
            ["VI. Net Transfer of Resources from the Centre (IV-V)", 247.2, 279.1, 303.0],
        ]),
        ("APPT_2", [
            [_TITLE + " (Contd.)"],
            [_UNIT],
            _HEADER_S2,
            _COLIDX_S2,
            ["I. States' Share in Central Taxes", 130, 140, 150],
            ["VI. Net Transfer of Resources from the Centre (IV-V)", 373.8, 432.5, 472.2],
        ]),
        ("APPT_3", [
            [_TITLE + " (Concld.)"],
            [_UNIT],
            _HEADER_S3,
            _COLIDX_S3,
            ["I. States' Share in Central Taxes", 1129.7, 1223.9, 1288.5],
            ["VI. Net Transfer of Resources from the Centre (IV-V)", 1735.6, 2052.7, 2080.7],
            ["Note: Data from 2017-18 onwards include Delhi and Puducherry also."],
            ["Source: Budget documents of the State governments."],
        ]),
    ])


# ---------------------------------------------------------------------------
# _parse_period_header
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2007-08", (2007, None)),
        ("  2015-16  ", (2015, None)),
        ("2023-24 (Accounts)", (2023, "accounts")),
        ("2025-26 (Budget Estimates)", (2025, "budget estimates")),
        ("Item", None),
        ("(Contd.)", None),
        (None, None),
        ("", None),
        (2007, None),  # bare int — no FY suffix, not a period
    ],
)
def test_parse_period_header(raw, expected):
    assert _parse_period_header(raw) == expected


# ---------------------------------------------------------------------------
# _coerce_value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,sign,expected",
    [
        (123.4, 1, 123.4),
        (123, 1, 123.0),
        ("1,234.5", 1, 1234.5),
        ("-50", 1, -50.0),
        ("(2.9)", 1, -2.9),  # paren-wrapped negative
        ("(-2.9)", 1, -2.9),
        ("100", -1, -100.0),
        ("—", 1, None),
        ("-", 1, None),
        ("..", 1, None),
        (None, 1, None),
        ("garbage", 1, None),
    ],
)
def test_coerce_value(raw, sign, expected):
    assert _coerce_value(raw, sign) == expected


# ---------------------------------------------------------------------------
# parse_workbook — happy path
# ---------------------------------------------------------------------------


_NET_TRANSFER_SPEC = AppendixSpec(
    indicator_id="fiscal/national_centre_transfers_total",
    item_label_match="net transfer of resources",
    prefer_qualifier=("accounts",),
)


def test_parse_workbook_canonical_layout():
    parsed = parse_workbook(_canonical_workbook(), _NET_TRANSFER_SPEC)

    assert parsed.indicator_id == "fiscal/national_centre_transfers_total"
    assert parsed.sheet_count == 3
    # 3 + 3 + 3 period cells across the 3 sheets.
    assert parsed.period_count == 9
    # 9 - 1 (2023-24 dedupe Accounts wins) = 8 emitted years.
    assert len(parsed.rows) == 8

    times = [r.time for r in parsed.rows]
    assert times == [
        "2007-04", "2008-04", "2009-04", "2010-04",
        "2011-04", "2012-04", "2023-04", "2024-04",
    ]
    assert all(r.entity_id == "IN" for r in parsed.rows)

    by_time = {r.time: r.value for r in parsed.rows}
    assert by_time["2007-04"] == 247.2
    # 2023-24 (Accounts) preferred over (Budget Estimates).
    assert by_time["2023-04"] == 1735.6
    # 2024-25 (Revised Estimates) — only candidate, kept.
    assert by_time["2024-04"] == 2080.7


def test_parse_workbook_picks_correct_item_row():
    # "I. States' Share in Central Taxes" exists in every sheet but
    # must not be picked when matching "net transfer of resources".
    parsed = parse_workbook(_canonical_workbook(), _NET_TRANSFER_SPEC)
    for r in parsed.rows:
        assert r.value not in (100, 110, 120, 130, 140, 150)  # taxes row values


def test_parse_workbook_handles_null_tokens():
    wb_bytes = _build_workbook([
        ("APPT_1", [
            [_TITLE],
            [_UNIT],
            ["Item", "2020-21", "2021-22"],
            [None, 1, 2],
            ["VI. Net Transfer of Resources", 100.0, "—"],
        ]),
    ])
    parsed = parse_workbook(wb_bytes, _NET_TRANSFER_SPEC)
    assert [r.value for r in parsed.rows] == [100.0, None]


def test_parse_workbook_qualifier_preference_falls_back():
    # Two qualifiers, neither matches the preference list → first wins.
    spec = AppendixSpec(
        indicator_id="fiscal/x",
        item_label_match="net transfer",
        prefer_qualifier=("provisional",),  # no match
    )
    wb_bytes = _build_workbook([
        ("APPT_1", [
            [_TITLE],
            [_UNIT],
            ["Item", "2023-24 (Accounts)", "2023-24 (Budget Estimates)"],
            [None, 1, 2],
            ["VI. Net Transfer of Resources", 100.0, 200.0],
        ]),
    ])
    parsed = parse_workbook(wb_bytes, spec)
    assert len(parsed.rows) == 1
    # Iteration order is deterministic — Accounts encountered first.
    assert parsed.rows[0].value == 100.0


def test_parse_workbook_skips_notes_rows():
    # Footnote starting with "Note:" must not be picked as the item row
    # even if the first matching row is far below.
    wb_bytes = _build_workbook([
        ("APPT_1", [
            [_TITLE],
            [_UNIT],
            ["Item", "2020-21", "2021-22"],
            [None, 1, 2],
            ["I. States' Share in Central Taxes", 595.2, 600.0],
            ["Note: net transfer of resources figures revised for FY20.", "x", "y"],
            ["VI. Net Transfer of Resources from the Centre", 1365.4, 1500.0],
        ]),
    ])
    parsed = parse_workbook(wb_bytes, _NET_TRANSFER_SPEC)
    assert len(parsed.rows) == 2
    assert [r.value for r in parsed.rows] == [1365.4, 1500.0]


# ---------------------------------------------------------------------------
# parse_workbook — error paths
# ---------------------------------------------------------------------------


def test_parse_workbook_missing_header_raises():
    wb_bytes = _build_workbook([
        ("APPT_1", [
            [_TITLE],
            [_UNIT],
            ["Description", "2020-21", "2021-22"],  # not "Item"
            ["VI. Net Transfer", 100.0, 200.0],
        ]),
    ])
    with pytest.raises(RBIAppendixShapeError, match="no header row"):
        parse_workbook(wb_bytes, _NET_TRANSFER_SPEC)


def test_parse_workbook_too_few_period_columns_raises():
    wb_bytes = _build_workbook([
        ("APPT_1", [
            [_TITLE],
            [_UNIT],
            ["Item", "2020-21"],  # only 1 period column
            [None, 1],
            ["VI. Net Transfer", 100.0],
        ]),
    ])
    with pytest.raises(RBIAppendixShapeError, match="≥2 fiscal-year columns"):
        parse_workbook(wb_bytes, _NET_TRANSFER_SPEC)


def test_parse_workbook_missing_item_raises():
    wb_bytes = _build_workbook([
        ("APPT_1", [
            [_TITLE],
            [_UNIT],
            ["Item", "2020-21", "2021-22"],
            [None, 1, 2],
            ["I. States' Share in Central Taxes", 100, 110],
        ]),
    ])
    with pytest.raises(RBIAppendixShapeError, match="no row matching item label"):
        parse_workbook(wb_bytes, _NET_TRANSFER_SPEC)


# ---------------------------------------------------------------------------
# SHIPPED_SPECS sanity
# ---------------------------------------------------------------------------


def test_shipped_specs_indicator_ids_unique():
    ids = [s.indicator_id for s in SHIPPED_SPECS]
    assert len(ids) == len(set(ids))


def test_shipped_specs_match_id_pattern():
    import re
    pat = re.compile(r"^[a-z][a-z0-9_]*(/[a-z][a-z0-9_]*)*$")
    for s in SHIPPED_SPECS:
        assert pat.match(s.indicator_id), s.indicator_id


def test_shipped_specs_each_resolves_distinct_item():
    """Every shipped spec must locate a distinct row in the canonical workbook.

    Guards against the 'two specs accidentally match the same item'
    failure mode, which would emit duplicate-looking indicators.
    """
    wb_bytes = _build_workbook([
        ("APPT_1", [
            [_TITLE],
            [_UNIT],
            ["Item", "2007-08", "2008-09"],
            [None, 1, 2],
            ["I. States' Share in Central Taxes", 151, 161],
            ["II. Grants from the Centre (1 to 5)", 108, 129],
            ["III. Gross Loans from the Centre", 7, 7],
            ["IV. Gross Transfer (I+II+III)", 267, 297],
            ["V. Repayment of Loans and Interest Payments", 19, 18],
            ["VI. Net Transfer of Resources from the Centre (IV-V)", 247, 279],
        ]),
    ])
    seen_first_values: set[float] = set()
    for spec in SHIPPED_SPECS:
        parsed = parse_workbook(wb_bytes, spec)
        assert parsed.rows, spec.indicator_id
        first = parsed.rows[0].value
        assert first is not None, spec.indicator_id
        assert first not in seen_first_values, (
            f"{spec.indicator_id}: first-row value {first} collides with another "
            f"spec — needles probably overlap"
        )
        seen_first_values.add(first)
