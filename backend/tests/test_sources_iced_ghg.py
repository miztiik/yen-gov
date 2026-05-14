"""Pure-parser tests for the iced_ghg adapter."""
from __future__ import annotations

import pytest

from yen_gov.sources.iced_common import ICEDShapeError
from yen_gov.sources.iced_ghg.parsers import parse_ghg_subsector


def test_subsector_emits_one_row_per_sector_subsector_year():
    decrypted = {"data": [
        {"sector": "Energy", "subSector": "Transport", "category": "",
         "subCategory": "", "year": 2010, "emission": 100.5},
        {"sector": "Energy", "subSector": "Transport", "category": "",
         "subCategory": "", "year": 2020, "emission": 200.0},
        {"sector": "Agriculture", "subSector": "Rice Cultivation",
         "category": "Total", "subCategory": "", "year": 2020, "emission": 60},
    ]}
    rows = parse_ghg_subsector(decrypted)
    assert len(rows) == 3
    assert {(r["facet"], r["time"], r["value"]) for r in rows} == {
        ("Energy|Transport", "2010", 100.5),
        ("Energy|Transport", "2020", 200.0),
        ("Agriculture|Rice Cultivation", "2020", 60),
    }
    assert all(r["entity_id"] == "IN" for r in rows)


def test_subsector_drops_total_subsector_rows():
    decrypted = {"data": [
        {"sector": "Energy", "subSector": "Total", "category": "",
         "subCategory": "", "year": 2020, "emission": 9999},
        {"sector": "Energy", "subSector": "Transport", "category": "",
         "subCategory": "", "year": 2020, "emission": 200},
    ]}
    rows = parse_ghg_subsector(decrypted)
    assert len(rows) == 1
    assert rows[0]["facet"] == "Energy|Transport"


def test_subsector_drops_deeper_drilldown_rows():
    """A non-empty category that isn't 'Total' is a sub-category; skip."""
    decrypted = {"data": [
        {"sector": "Energy", "subSector": "Fugitive emissions",
         "category": "Oil and natural gas system", "subCategory": "Total",
         "year": 2020, "emission": 50},
        {"sector": "Energy", "subSector": "Fugitive emissions",
         "category": "Total", "subCategory": "", "year": 2020, "emission": 75},
    ]}
    rows = parse_ghg_subsector(decrypted)
    assert len(rows) == 1
    assert rows[0]["value"] == 75


def test_subsector_dedups_last_write_wins():
    decrypted = {"data": [
        {"sector": "Energy", "subSector": "Transport", "category": "",
         "subCategory": "", "year": 2020, "emission": 100},
        {"sector": "Energy", "subSector": "Transport", "category": "",
         "subCategory": "", "year": 2020, "emission": 200},
    ]}
    rows = parse_ghg_subsector(decrypted)
    assert len(rows) == 1
    assert rows[0]["value"] == 200


def test_subsector_skips_non_numeric_emission_and_bad_year():
    decrypted = {"data": [
        {"sector": "Energy", "subSector": "Transport", "category": "",
         "subCategory": "", "year": "garbage", "emission": 100},
        {"sector": "Energy", "subSector": "Transport", "category": "",
         "subCategory": "", "year": 2020, "emission": None},
        {"sector": "Energy", "subSector": "Transport", "category": "",
         "subCategory": "", "year": 2020, "emission": 100},
    ]}
    rows = parse_ghg_subsector(decrypted)
    assert len(rows) == 1


def test_subsector_accepts_string_emission_values():
    """Real upstream sometimes ships '"1005813.0"' as a string."""
    decrypted = {"data": [
        {"sector": "Energy", "subSector": "Energy Industries", "category": "",
         "subCategory": "", "year": 2012, "emission": "1005813.0"},
    ]}
    rows = parse_ghg_subsector(decrypted)
    assert rows[0]["value"] == 1005813.0


def test_subsector_rejects_wrong_top_level():
    with pytest.raises(ICEDShapeError):
        parse_ghg_subsector([])
    with pytest.raises(ICEDShapeError):
        parse_ghg_subsector({"data": "not-a-list"})
