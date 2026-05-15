"""Pure-parser tests for iced_fuel."""
from __future__ import annotations

import pytest

from yen_gov.sources.iced_common import ICEDShapeError
from yen_gov.sources.iced_fuel.parsers import (
    parse_coal_consumption_state,
    parse_oil_consumption_state,
    parse_ppa_share,
)


# ---------------------------------------------------------------------------
# parse_coal_consumption_state
# ---------------------------------------------------------------------------


def test_coal_aggregates_grades_per_state_year():
    decoded = {"data": [
        {"source": "coal", "state": "MAHARASHTRA", "year": "2022-23",
         "type": "RAW COAL", "total": 80.0},
        {"source": "coal", "state": "MAHARASHTRA", "year": "2022-23",
         "type": "WASHED COAL", "total": 10.0},
        {"source": "coal", "state": "MAHARASHTRA", "year": "2022-23",
         "type": "MIDDLINGS", "total": 4.0},
        {"source": "coal", "state": "MAHARASHTRA", "year": "2022-23",
         "type": "LIGNITE", "total": 0.5},
    ]}
    rows, skipped = parse_coal_consumption_state(decoded)
    assert skipped == 0
    assert rows == [{"entity_id": "S13", "time": "2022-04", "value": 94.5}]


def test_coal_drops_total_coal_to_avoid_double_counting():
    decoded = {"data": [
        {"state": "MAHARASHTRA", "year": "2022-23", "type": "RAW COAL", "total": 80.0},
        {"state": "MAHARASHTRA", "year": "2022-23", "type": "TOTAL COAL", "total": 999.0},
    ]}
    rows, _ = parse_coal_consumption_state(decoded)
    assert rows == [{"entity_id": "S13", "time": "2022-04", "value": 80.0}]


def test_coal_case_insensitive_state_lookup():
    decoded = {"data": [
        {"state": "ANDHRA PRADESH", "year": "2022-23", "type": "RAW COAL", "total": 5.0},
        {"state": "andhra pradesh", "year": "2022-23", "type": "WASHED COAL", "total": 2.0},
    ]}
    rows, _ = parse_coal_consumption_state(decoded)
    assert rows == [{"entity_id": "S01", "time": "2022-04", "value": 7.0}]


def test_coal_counts_unmapped_states_unique():
    decoded = {"data": [
        {"state": "ATLANTIS", "year": "2022-23", "type": "RAW COAL", "total": 1.0},
        {"state": "ATLANTIS", "year": "2023-24", "type": "RAW COAL", "total": 2.0},
        {"state": "ELDORADO", "year": "2022-23", "type": "RAW COAL", "total": 3.0},
        {"state": "BIHAR", "year": "2022-23", "type": "RAW COAL", "total": 7.0},
    ]}
    rows, skipped = parse_coal_consumption_state(decoded)
    assert skipped == 2
    assert {r["entity_id"] for r in rows} == {"S04"}


def test_coal_rejects_unexpected_top_level():
    with pytest.raises(ICEDShapeError):
        parse_coal_consumption_state("not a dict")


# ---------------------------------------------------------------------------
# parse_oil_consumption_state
# ---------------------------------------------------------------------------


def test_oil_emits_one_row_per_state_year_product():
    decoded = {"data": [
        {"region": "SR", "state": "ANDHRA PRADESH", "type": "DIESEL/ HSD",
         "year": "2023-24", "quantity": 5800, "source": "oil"},
        {"region": "SR", "state": "ANDHRA PRADESH", "type": "PETROL",
         "year": "2023-24", "quantity": 1900, "source": "oil"},
        {"region": "SR", "state": "ANDHRA PRADESH", "type": "LPG",
         "year": "2023-24", "quantity": 1100, "source": "oil"},
    ]}
    rows, skipped = parse_oil_consumption_state(decoded)
    assert skipped == 0
    by_facet = {r["facet"]: r["value"] for r in rows}
    assert by_facet == {"diesel-hsd": 5800, "petrol": 1900, "lpg": 1100}
    assert all(r["entity_id"] == "S01" and r["time"] == "2023-04" for r in rows)


def test_oil_drops_national_aggregate_region():
    decoded = {"data": [
        {"region": "IN", "state": "INDIA", "type": "DIESEL/ HSD",
         "year": "2023-24", "quantity": 80000},
        {"region": "SR", "state": "TAMIL NADU", "type": "DIESEL/ HSD",
         "year": "2023-24", "quantity": 7000},
    ]}
    rows, skipped = parse_oil_consumption_state(decoded)
    assert skipped == 0
    assert rows == [{"entity_id": "S22", "time": "2023-04",
                     "value": 7000, "facet": "diesel-hsd"}]


def test_oil_drops_others_state_bucket():
    decoded = {"data": [
        {"region": "NR", "state": "OTHERS", "type": "PETROL",
         "year": "2023-24", "quantity": 100},
        {"region": "ER", "state": "BIHAR", "type": "PETROL",
         "year": "2023-24", "quantity": 50},
    ]}
    rows, skipped = parse_oil_consumption_state(decoded)
    # OTHERS goes through unmapped path → counted, not silently dropped
    assert skipped == 1
    assert rows == [{"entity_id": "S04", "time": "2023-04",
                     "value": 50, "facet": "petrol"}]


def test_oil_drops_unknown_product_types():
    decoded = {"data": [
        {"region": "SR", "state": "TAMIL NADU", "type": "MADE-UP-FUEL",
         "year": "2023-24", "quantity": 5},
        {"region": "SR", "state": "TAMIL NADU", "type": "PETROL",
         "year": "2023-24", "quantity": 50},
    ]}
    rows, _ = parse_oil_consumption_state(decoded)
    assert rows == [{"entity_id": "S22", "time": "2023-04",
                     "value": 50, "facet": "petrol"}]


def test_oil_dedups_last_write_wins():
    decoded = {"data": [
        {"region": "SR", "state": "TAMIL NADU", "type": "PETROL",
         "year": "2023-24", "quantity": 50},
        {"region": "SR", "state": "TAMIL NADU", "type": "PETROL",
         "year": "2023-24", "quantity": 75},
    ]}
    rows, _ = parse_oil_consumption_state(decoded)
    assert rows == [{"entity_id": "S22", "time": "2023-04",
                     "value": 75, "facet": "petrol"}]


# ---------------------------------------------------------------------------
# parse_ppa_share
# ---------------------------------------------------------------------------


def test_ppa_emits_one_row_per_state_year_source():
    decoded = {"data": [
        {"state": "Tamil Nadu", "year": "2022-23", "source": "coal",
         "purchaseVal": 5.0, "purchasePercentage": 55.0, "totalCost": None},
        {"state": "Tamil Nadu", "year": "2022-23", "source": "solar",
         "purchaseVal": 1.0, "purchasePercentage": 12.0, "totalCost": 1234},
    ]}
    rows, skipped = parse_ppa_share(decoded)
    assert skipped == 0
    by_facet = {r["facet"]: r["value"] for r in rows}
    assert by_facet == {"coal": 55.0, "solar": 12.0}


def test_ppa_drops_empty_state_national_aggregate():
    decoded = {"data": [
        {"state": "", "year": "2022-23", "source": "coal",
         "purchaseVal": 4.0, "purchasePercentage": 47.0},
        {"state": "Bihar", "year": "2022-23", "source": "coal",
         "purchaseVal": 3.0, "purchasePercentage": 80.0},
    ]}
    rows, skipped = parse_ppa_share(decoded)
    assert skipped == 0  # empty-string state isn't unmapped, it's national-aggregate dropped silently
    assert rows == [{"entity_id": "S04", "time": "2022-04",
                     "value": 80.0, "facet": "coal"}]


def test_ppa_skips_null_percentage():
    decoded = {"data": [
        {"state": "Bihar", "year": "2022-23", "source": "coal",
         "purchasePercentage": None},
    ]}
    rows, _ = parse_ppa_share(decoded)
    assert rows == []


def test_ppa_counts_unmapped_states():
    decoded = {"data": [
        {"state": "Atlantis", "year": "2022-23", "source": "coal",
         "purchasePercentage": 50.0},
        {"state": "Bihar", "year": "2022-23", "source": "coal",
         "purchasePercentage": 70.0},
    ]}
    rows, skipped = parse_ppa_share(decoded)
    assert skipped == 1
    assert {r["entity_id"] for r in rows} == {"S04"}


def test_ppa_rejects_unexpected_top_level():
    with pytest.raises(ICEDShapeError):
        parse_ppa_share(42)
