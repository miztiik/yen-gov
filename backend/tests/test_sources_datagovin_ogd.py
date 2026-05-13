"""Tests for the data.gov.in OGD CSV adapter.

Pure parser tests (no I/O). Covers:
  - happy path: small fixture CSV → expected canonical rows.
  - shape errors: missing required column, missing value column, empty CSV.
  - encoding tolerance: UTF-8 BOM is stripped.
  - period encoding: ``fy_span`` maps "2016-17" → "2016-04".
  - value summing: multiple value columns are summed (Col.4 + Col.5).
  - unmatched state labels are reported, not silently dropped.
"""
from __future__ import annotations

import pytest

from yen_gov.sources.datagovin_ogd.parsers import (
    DataGovInCsvShapeError,
    IndicatorSpec,
    parse_csv,
)


SPEC = IndicatorSpec(
    indicator_id="fiscal/centre_transfers_gross",
    state_column="States",
    time_column="Financial Year",
    value_columns=(
        "Revenue Receipts - Share In Central Taxes - Col. (4)",
        "Revenue Receipts - Grants-In-Aid - Col. (5)",
    ),
    period_kind="fy_span",
)


def _csv(*lines: str) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_happy_path_sums_value_columns_and_normalises_period() -> None:
    raw = _csv(
        "Financial Year,States,Revenue Receipts - Share in Central Taxes - Col. (4),Revenue Receipts - Grants-in-Aid - Col. (5)",
        "2016-17,Andhra Pradesh,26263.88,23346.38",
        "2017-18,Tamil Nadu,30000.00,10000.00",
    )
    parsed = parse_csv(raw, SPEC)
    assert parsed.record_count == 2
    assert parsed.unmatched_states == ()
    rows = {(r.entity_id, r.time): r.value for r in parsed.rows}
    # Andhra Pradesh = S01, FY span → 2016-04
    assert rows[("S01", "2016-04")] == pytest.approx(26263.88 + 23346.38)
    # Tamil Nadu = S22, FY 2017-18 → 2017-04
    assert rows[("S22", "2017-04")] == pytest.approx(40000.00)


def test_header_matching_is_case_and_whitespace_tolerant() -> None:
    # Note differing case for "in"/"In" and extra spaces.
    raw = _csv(
        "Financial Year,States,Revenue Receipts - Share  in  Central Taxes - Col. (4),Revenue Receipts - Grants-in-Aid - Col. (5)",
        "2018-19,Karnataka,100,50",
    )
    parsed = parse_csv(raw, SPEC)
    assert len(parsed.rows) == 1
    assert parsed.rows[0].entity_id == "S10"  # Karnataka
    assert parsed.rows[0].value == pytest.approx(150.0)


def test_utf8_bom_is_stripped() -> None:
    raw = b"\xef\xbb\xbf" + _csv(
        "Financial Year,States,Revenue Receipts - Share in Central Taxes - Col. (4),Revenue Receipts - Grants-in-Aid - Col. (5)",
        "2019-20,Kerala,200,100",
    )
    parsed = parse_csv(raw, SPEC)
    assert len(parsed.rows) == 1
    assert parsed.rows[0].entity_id == "S11"  # Kerala


def test_comma_grouped_numbers_are_parsed() -> None:
    raw = _csv(
        "Financial Year,States,Revenue Receipts - Share in Central Taxes - Col. (4),Revenue Receipts - Grants-in-Aid - Col. (5)",
        '2020-21,Maharashtra,"1,23,456.78","98,765.43"',
    )
    parsed = parse_csv(raw, SPEC)
    assert len(parsed.rows) == 1
    assert parsed.rows[0].value == pytest.approx(123456.78 + 98765.43)


def test_unmatched_state_labels_are_reported_not_silently_dropped() -> None:
    raw = _csv(
        "Financial Year,States,Revenue Receipts - Share in Central Taxes - Col. (4),Revenue Receipts - Grants-in-Aid - Col. (5)",
        "2016-17,Andhra Pradesh,1,1",
        "2016-17,Atlantis,99,99",
    )
    parsed = parse_csv(raw, SPEC)
    assert len(parsed.rows) == 1
    assert parsed.unmatched_states == ("Atlantis",)


def test_missing_value_column_raises_shape_error() -> None:
    raw = _csv(
        "Financial Year,States,Revenue Receipts - Share in Central Taxes - Col. (4)",
        "2016-17,Andhra Pradesh,100",
    )
    with pytest.raises(DataGovInCsvShapeError, match="Grants-In-Aid"):
        parse_csv(raw, SPEC)


def test_missing_state_column_raises_shape_error() -> None:
    raw = _csv(
        "Financial Year,Revenue Receipts - Share in Central Taxes - Col. (4),Revenue Receipts - Grants-in-Aid - Col. (5)",
        "2016-17,100,50",
    )
    with pytest.raises(DataGovInCsvShapeError, match="state_col"):
        parse_csv(raw, SPEC)


def test_empty_csv_after_filtering_raises_shape_error() -> None:
    raw = _csv(
        "Financial Year,States,Revenue Receipts - Share in Central Taxes - Col. (4),Revenue Receipts - Grants-in-Aid - Col. (5)",
        "2016-17,Atlantis,1,1",
    )
    with pytest.raises(DataGovInCsvShapeError, match="none survived"):
        parse_csv(raw, SPEC)


def test_no_header_raises_shape_error() -> None:
    with pytest.raises(DataGovInCsvShapeError, match="no header"):
        parse_csv(b"", SPEC)
