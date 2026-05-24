"""Tests for the data.gov.in Pincode Directory pure parser (Phase A.1.a).

Covers:
  - happy path: 5-row fixture → 5 PincodeRows.
  - header tolerance: case + whitespace variants ("Circle Name" vs "circlename").
  - encoding tolerance: UTF-8 BOM is stripped.
  - pincode validation: 6-digit OK; 5-digit / 7-digit / alpha-bearing skipped
    and counted in ``invalid_pincode_count``.
  - Excel-mediated "560001.0" coerced back to "560001".
  - shape errors: missing required column, header-less CSV, all-invalid CSV.

Mirrors the inline-CSV pattern of ``test_sources_datagovin_ogd.py`` (no
fixture files, no I/O).
"""
from __future__ import annotations

import pytest

from yen_gov.sources.datagovin_ogd.pincode_directory import (
    ParsedPincodeDirectory,
    PincodeDirectoryShapeError,
    parse_pincode_directory,
)


def _csv(*lines: str) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_happy_path_five_rows_parse_in_order() -> None:
    raw = _csv(
        "circlename,regionname,divisionname,officename,pincode",
        "Tamilnadu Circle,Chennai Region,Chennai South Division,T Nagar SO,600017",
        "Karnataka Circle,Bengaluru Region,Bengaluru East Division,Indiranagar SO,560038",
        "Maharashtra Circle,Mumbai Region,Mumbai South Division,Fort SO,400001",
        "Delhi Circle,Delhi Region,New Delhi Central Division,Connaught Place HO,110001",
        "West Bengal Circle,Kolkata Region,Kolkata South Division,Park Street SO,700016",
    )
    parsed: ParsedPincodeDirectory = parse_pincode_directory(raw)
    assert parsed.record_count == 5
    assert parsed.invalid_pincode_count == 0
    assert len(parsed.rows) == 5

    first = parsed.rows[0]
    assert first.circlename == "Tamilnadu Circle"
    assert first.regionname == "Chennai Region"
    assert first.divisionname == "Chennai South Division"
    assert first.officename == "T Nagar SO"
    assert first.pincode == "600017"

    pins = [r.pincode for r in parsed.rows]
    assert pins == ["600017", "560038", "400001", "110001", "700016"]


def test_header_matching_is_case_and_whitespace_tolerant() -> None:
    # Upstream sometimes ships "Circle Name" / "Region Name" etc.; we
    # collapse whitespace + lowercase before matching.
    raw = _csv(
        "Circle Name, Region Name ,Division Name,Office Name,PIN Code",
        "Kerala Circle,Kochi Region,Ernakulam Division,Fort Kochi SO,682001",
    )
    parsed = parse_pincode_directory(raw)
    assert len(parsed.rows) == 1
    row = parsed.rows[0]
    assert row.circlename == "Kerala Circle"
    assert row.regionname == "Kochi Region"
    assert row.divisionname == "Ernakulam Division"
    assert row.officename == "Fort Kochi SO"
    assert row.pincode == "682001"


def test_utf8_bom_is_stripped() -> None:
    raw = b"\xef\xbb\xbf" + _csv(
        "circlename,regionname,divisionname,officename,pincode",
        "Assam Circle,Guwahati Region,Guwahati North Division,Pan Bazar SO,781001",
    )
    parsed = parse_pincode_directory(raw)
    assert len(parsed.rows) == 1
    assert parsed.rows[0].pincode == "781001"


def test_excel_exported_pincode_with_trailing_dot_zero_is_coerced() -> None:
    # Some Excel-mediated exports save numeric columns as floats, so
    # "560001" becomes "560001.0" by the time it hits CSV.
    raw = _csv(
        "circlename,regionname,divisionname,officename,pincode",
        "Karnataka Circle,Bengaluru Region,Bengaluru South Division,Jayanagar SO,560011.0",
    )
    parsed = parse_pincode_directory(raw)
    assert len(parsed.rows) == 1
    assert parsed.rows[0].pincode == "560011"


# ---------------------------------------------------------------------------
# Pincode validation
# ---------------------------------------------------------------------------


def test_invalid_pincodes_are_skipped_and_counted_not_raised() -> None:
    # One valid + three invalid (too short, too long, alpha-bearing).
    # parse_pincode_directory should keep the valid one and report the
    # other three in invalid_pincode_count.
    raw = _csv(
        "circlename,regionname,divisionname,officename,pincode",
        "Tamilnadu Circle,Chennai Region,Chennai South Division,T Nagar SO,600017",
        "X,Y,Z,Short SO,12345",
        "X,Y,Z,Long SO,1234567",
        "X,Y,Z,Alpha SO,60001A",
    )
    parsed = parse_pincode_directory(raw)
    assert parsed.record_count == 4
    assert parsed.invalid_pincode_count == 3
    assert len(parsed.rows) == 1
    assert parsed.rows[0].pincode == "600017"


def test_all_invalid_pincodes_raise_shape_error() -> None:
    raw = _csv(
        "circlename,regionname,divisionname,officename,pincode",
        "X,Y,Z,Bad1 SO,12345",
        "X,Y,Z,Bad2 SO,XYZ123",
    )
    with pytest.raises(PincodeDirectoryShapeError, match="none survived"):
        parse_pincode_directory(raw)


# ---------------------------------------------------------------------------
# Shape errors
# ---------------------------------------------------------------------------


def test_missing_required_column_raises_shape_error() -> None:
    # Missing 'pincode' column — the whole point of the file.
    raw = _csv(
        "circlename,regionname,divisionname,officename",
        "Tamilnadu Circle,Chennai Region,Chennai South Division,T Nagar SO",
    )
    with pytest.raises(PincodeDirectoryShapeError, match="pincode"):
        parse_pincode_directory(raw)


def test_empty_csv_raises_shape_error() -> None:
    with pytest.raises(PincodeDirectoryShapeError, match="no header"):
        parse_pincode_directory(b"")
