"""Pure-parser tests for iced_macro."""
from __future__ import annotations

import pytest

from yen_gov.sources.iced_common import ICEDShapeError
from yen_gov.sources.iced_macro.parsers import (
    parse_balance_trendline,
    parse_gdp_trend,
    parse_gva_trend_national_constant,
    parse_industrial_production,
    parse_population_by_residence,
)


# ---------------------------------------------------------------------------
# parse_gdp_trend
# ---------------------------------------------------------------------------


def test_gdp_trend_keeps_only_priceType_gross_for_national():
    decrypted = {"data": [
        {"trendType": "national", "priceType": "gross",  "priceCategory": "current",  "year": "2020-21", "price": 200000000},
        {"trendType": "national", "priceType": "export", "priceCategory": "current",  "year": "2020-21", "price": 9999},
        {"trendType": "national", "priceType": "import", "priceCategory": "current",  "year": "2020-21", "price": 1234},
        {"trendType": "national", "priceType": "gross",  "priceCategory": "constant", "year": "2020-21", "price": 145000000},
    ]}
    out = parse_gdp_trend(decrypted)
    assert out.skipped_unmapped == 0
    assert out.state == []
    assert {(r["facet"], r["value"]) for r in out.national} == {
        ("current", 200000000), ("constant", 145000000),
    }
    assert all(r["entity_id"] == "IN" and r["time"] == "2020-04" for r in out.national)


def test_gdp_trend_state_rows_have_no_priceType_filter():
    decrypted = {"data": [
        {"trendType": "state", "state": "Tamil Nadu",  "priceCategory": "current",  "year": "2020-21", "price": 1500000},
        {"trendType": "state", "state": "Tamil Nadu",  "priceCategory": "constant", "year": "2020-21", "price": 1100000},
        {"trendType": "state", "state": "Atlantis",    "priceCategory": "current",  "year": "2020-21", "price": 1},
    ]}
    out = parse_gdp_trend(decrypted)
    assert out.skipped_unmapped == 1
    assert {(r["entity_id"], r["facet"], r["value"]) for r in out.state} == {
        ("S22", "current", 1500000),
        ("S22", "constant", 1100000),
    }


def test_gdp_trend_dedups_last_write_wins_per_entity_time_facet():
    decrypted = {"data": [
        {"trendType": "national", "priceType": "gross", "priceCategory": "current", "year": "2020-21", "price": 100},
        {"trendType": "national", "priceType": "gross", "priceCategory": "current", "year": "2020-21", "price": 200},
    ]}
    out = parse_gdp_trend(decrypted)
    assert len(out.national) == 1
    assert out.national[0]["value"] == 200


def test_gdp_trend_skips_unparseable_year():
    decrypted = {"data": [
        {"trendType": "national", "priceType": "gross", "priceCategory": "current", "year": "garbage", "price": 100},
    ]}
    out = parse_gdp_trend(decrypted)
    assert out.national == []


def test_gdp_trend_rejects_wrong_top_level():
    with pytest.raises(ICEDShapeError):
        parse_gdp_trend([])


# ---------------------------------------------------------------------------
# parse_industrial_production
# ---------------------------------------------------------------------------


def test_iip_one_row_per_category_year():
    decrypted = {"data": [
        {"category": "Manufacturing", "year": "2020-21", "index": 110.5},
        {"category": "Mining & Quarrying", "year": "2020-21", "index": 95.0},
        {"category": "", "year": "2020-21", "index": 100},  # empty category dropped
    ]}
    rows = parse_industrial_production(decrypted)
    assert {(r["facet"], r["value"]) for r in rows} == {
        ("Manufacturing", 110.5), ("Mining & Quarrying", 95.0),
    }


def test_iip_dedup_last_write():
    decrypted = {"data": [
        {"category": "Manufacturing", "year": "2020-21", "index": 100},
        {"category": "Manufacturing", "year": "2020-21", "index": 200},
    ]}
    rows = parse_industrial_production(decrypted)
    assert len(rows) == 1
    assert rows[0]["value"] == 200


# ---------------------------------------------------------------------------
# parse_population_by_residence
# ---------------------------------------------------------------------------


def test_population_residence_keeps_only_rural_urban():
    decrypted = {"data": [
        {"state": "Tamil Nadu", "category": "Rural", "year": 2011, "type": "actual", "population": 37189229},
        {"state": "Tamil Nadu", "category": "Urban", "year": 2011, "type": "actual", "population": 34917440},
        {"state": "Tamil Nadu", "category": "Male",  "year": 2011, "type": "actual", "population": 1},
        {"state": "Tamil Nadu", "category": "Female","year": 2011, "type": "actual", "population": 1},
        {"state": "All India",  "category": "Rural", "year": 2011, "type": "actual", "population": 833463448},
    ]}
    rows, skipped = parse_population_by_residence(decrypted)
    assert skipped == 0
    assert {(r["entity_id"], r["facet"], r["value"]) for r in rows} == {
        ("S22", "Rural", 37189229), ("S22", "Urban", 34917440),
        ("IN",  "Rural", 833463448),
    }
    assert all(r["vintage"] == "actual" for r in rows)


def test_population_residence_skips_unmapped_state():
    decrypted = {"data": [
        {"state": "Atlantis", "category": "Rural", "year": 2011, "type": "actual", "population": 1},
    ]}
    rows, skipped = parse_population_by_residence(decrypted)
    assert rows == []
    assert skipped == 1


# ---------------------------------------------------------------------------
# parse_gva_trend_national_constant
# ---------------------------------------------------------------------------


def test_gva_keeps_only_national_constant():
    decrypted = {"data": [
        {"trendType": "national", "priceType": "constant", "industryItem": "Manufacturing",
         "year": "2020-21", "price": 2500000},
        {"trendType": "national", "priceType": "current",  "industryItem": "Manufacturing",
         "year": "2020-21", "price": 9999},
        {"trendType": "state", "priceType": "constant", "industryItem": "Manufacturing",
         "state": "Tamil Nadu", "year": "2020-21", "price": 1},
        {"trendType": "national", "priceType": "constant", "industryItem": "",
         "year": "2020-21", "price": 100},  # missing industry — drop
    ]}
    rows = parse_gva_trend_national_constant(decrypted)
    assert {(r["facet"], r["value"]) for r in rows} == {("Manufacturing", 2500000)}
    assert all(r["entity_id"] == "IN" for r in rows)


def test_gva_skips_unparseable_year():
    decrypted = {"data": [
        {"trendType": "national", "priceType": "constant", "industryItem": "Manufacturing",
         "year": "garbage", "price": 100},
    ]}
    assert parse_gva_trend_national_constant(decrypted) == []


# ---------------------------------------------------------------------------
# parse_balance_trendline
# ---------------------------------------------------------------------------


def test_bop_normalises_year_strings_and_marks_preliminary():
    decrypted = {"data": [
        {"item": "Trade Balance", "year": "2010-11", "price": -100},
        {"item": "Trade Balance", "year": "2021-22 ", "price": -200},  # trailing space
        {"item": "Trade Balance", "year": "2023-24 (Preliminary)", "price": -300},
    ]}
    rows = parse_balance_trendline(decrypted)
    by_time = {r["time"]: r for r in rows}
    assert set(by_time) == {"2010-04", "2021-04", "2023-04"}
    assert by_time["2010-04"].get("vintage") is None
    assert by_time["2021-04"].get("vintage") is None
    assert by_time["2023-04"]["vintage"] == "preliminary"


def test_bop_drops_partial_year_rows():
    decrypted = {"data": [
        {"item": "Trade Balance", "year": "2024-25  (Apr-Sep) (Preliminary)", "price": 1},
        {"item": "Trade Balance", "year": "2024-25  (Jul-Dec)", "price": 2},
    ]}
    assert parse_balance_trendline(decrypted) == []


def test_bop_preserves_facet_per_item():
    decrypted = {"data": [
        {"item": "Trade Balance",           "year": "2020-21", "price": -100},
        {"item": "Current Account Balance", "year": "2020-21", "price": -50},
        {"item": "",                        "year": "2020-21", "price": 999},  # drop
    ]}
    rows = parse_balance_trendline(decrypted)
    assert {(r["facet"], r["value"]) for r in rows} == {
        ("Trade Balance", -100), ("Current Account Balance", -50),
    }
