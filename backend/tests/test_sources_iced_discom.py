"""Pure-parser tests for iced_discom."""
from __future__ import annotations

import pytest

from yen_gov.sources.iced_common import ICEDShapeError
from yen_gov.sources.iced_discom.parsers import (
    OPPERF_CATEGORIES,
    parse_opperf_states,
    parse_rpo,
)


# ---------------------------------------------------------------------------
# parse_opperf_states
# ---------------------------------------------------------------------------


def test_opperf_splits_categories_and_emits_one_row_per_state_year():
    decoded = {"data": [
        {"category": "transmission-and-distribution-loss", "state": "Tamil Nadu",
         "fyear": "2023-24", "value": 13.4, "unit": "%"},
        {"category": "billing-efficiency", "state": "Tamil Nadu",
         "fyear": "2023-24", "value": 92.1, "unit": "%"},
        {"category": "collection-efficiency", "state": "Tamil Nadu",
         "fyear": "2023-24", "value": 99.0, "unit": "%"},
        {"category": "aggregate-technical-and-commercial-loss",
         "state": "Tamil Nadu", "fyear": "2023-24", "value": 14.0, "unit": "%"},
    ]}
    by_cat, skipped = parse_opperf_states(decoded)
    assert skipped == 0
    assert set(by_cat.keys()) == set(OPPERF_CATEGORIES)
    assert by_cat["transmission-and-distribution-loss"] == [
        {"entity_id": "S22", "time": "2023-04", "value": 13.4}
    ]
    assert by_cat["billing-efficiency"][0]["value"] == 92.1
    assert by_cat["collection-efficiency"][0]["value"] == 99.0
    assert by_cat["aggregate-technical-and-commercial-loss"][0]["value"] == 14.0


def test_opperf_drops_unknown_category():
    decoded = {"data": [
        {"category": "made-up-category", "state": "Tamil Nadu",
         "fyear": "2023-24", "value": 1.0},
        {"category": "billing-efficiency", "state": "Tamil Nadu",
         "fyear": "2023-24", "value": 90.0},
    ]}
    by_cat, _ = parse_opperf_states(decoded)
    assert by_cat["billing-efficiency"][0]["value"] == 90.0
    # other categories empty
    assert by_cat["transmission-and-distribution-loss"] == []


def test_opperf_counts_unmapped_states():
    decoded = {"data": [
        {"category": "billing-efficiency", "state": "Atlantis",
         "fyear": "2023-24", "value": 1.0},
        {"category": "billing-efficiency", "state": "Bihar",
         "fyear": "2023-24", "value": 90.0},
    ]}
    by_cat, skipped = parse_opperf_states(decoded)
    assert skipped == 1
    assert by_cat["billing-efficiency"] == [
        {"entity_id": "S04", "time": "2023-04", "value": 90.0}
    ]


def test_opperf_dedups_last_write_wins():
    decoded = {"data": [
        {"category": "billing-efficiency", "state": "Bihar",
         "fyear": "2023-24", "value": 80.0},
        {"category": "billing-efficiency", "state": "Bihar",
         "fyear": "2023-24", "value": 95.0},
    ]}
    by_cat, _ = parse_opperf_states(decoded)
    assert by_cat["billing-efficiency"] == [
        {"entity_id": "S04", "time": "2023-04", "value": 95.0}
    ]


def test_opperf_skips_null_value_and_bad_year():
    decoded = {"data": [
        {"category": "billing-efficiency", "state": "Bihar",
         "fyear": "2023-24", "value": None},
        {"category": "billing-efficiency", "state": "Bihar",
         "fyear": "garbage", "value": 1.0},
    ]}
    by_cat, _ = parse_opperf_states(decoded)
    assert by_cat["billing-efficiency"] == []


def test_opperf_rejects_unexpected_top_level():
    with pytest.raises(ICEDShapeError):
        parse_opperf_states("not a dict")


# ---------------------------------------------------------------------------
# parse_rpo
# ---------------------------------------------------------------------------


def test_rpo_emits_three_facets_per_state_year():
    decoded = [
        {"state": "Tamil Nadu", "fyear": "2020-21",
         "solarCompliance": 80.0, "nonSolarCompliance": 110.0,
         "totalCompliance": 95.0, "rpoCompliance": 999.0,
         "solarTarget": 5.0, "nonSolarTarget": 10.0, "totalTarget": 15.0},
    ]
    rows, skipped = parse_rpo(decoded)
    assert skipped == 0
    by_facet = {r["facet"]: r["value"] for r in rows}
    assert by_facet == {"solar": 80.0, "non-solar": 110.0, "total": 95.0}
    assert all(r["entity_id"] == "S22" and r["time"] == "2020-04" for r in rows)


def test_rpo_skips_null_compliance_per_facet():
    decoded = [
        {"state": "Bihar", "fyear": "2020-21",
         "solarCompliance": None, "nonSolarCompliance": 50.0,
         "totalCompliance": None},
    ]
    rows, _ = parse_rpo(decoded)
    assert rows == [{"entity_id": "S04", "time": "2020-04",
                     "value": 50.0, "facet": "non-solar"}]


def test_rpo_dedups_last_write_wins():
    decoded = [
        {"state": "Bihar", "fyear": "2020-21",
         "solarCompliance": 10.0, "nonSolarCompliance": 20.0, "totalCompliance": 15.0},
        {"state": "Bihar", "fyear": "2020-21",
         "solarCompliance": 90.0, "nonSolarCompliance": 80.0, "totalCompliance": 85.0},
    ]
    rows, _ = parse_rpo(decoded)
    by_facet = {r["facet"]: r["value"] for r in rows}
    assert by_facet == {"solar": 90.0, "non-solar": 80.0, "total": 85.0}


def test_rpo_counts_unmapped_states():
    decoded = [
        {"state": "Atlantis", "fyear": "2020-21",
         "solarCompliance": 1.0, "nonSolarCompliance": 1.0, "totalCompliance": 1.0},
        {"state": "Bihar", "fyear": "2020-21",
         "solarCompliance": 50.0, "nonSolarCompliance": 50.0, "totalCompliance": 50.0},
    ]
    rows, skipped = parse_rpo(decoded)
    assert skipped == 1
    assert {r["entity_id"] for r in rows} == {"S04"}


def test_rpo_accepts_dict_wrapped_data_key():
    decoded = {"data": [
        {"state": "Goa", "fyear": "2019-20",
         "solarCompliance": 25.0, "nonSolarCompliance": 30.0, "totalCompliance": 28.0},
    ]}
    rows, _ = parse_rpo(decoded)
    assert {r["entity_id"] for r in rows} == {"S05"}
    assert all(r["time"] == "2019-04" for r in rows)


def test_rpo_rejects_unexpected_top_level():
    with pytest.raises(ICEDShapeError):
        parse_rpo(42)
