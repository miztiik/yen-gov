"""Pure-parser tests for the iced_socio adapter.

Per CLAUDE.md §15 (Tier: Unit) — the parsers are pure functions over an
already-decrypted JSON envelope. We feed them the exact dict shape the
real ICED API returns (verified against the cached raw responses on
2026-05-14) and assert the canonical row outputs. No network, no cipher,
no I/O.
"""
from __future__ import annotations

import pytest

from yen_gov.sources.iced_socio.parsers import (
    parse_ghg_economy_wide,
    parse_per_capita_consumption,
    parse_per_capita_income,
)
from yen_gov.sources.iced_common import ICEDShapeError


# ---------------------------------------------------------------------------
# parse_per_capita_income
# ---------------------------------------------------------------------------


def test_per_capita_income_splits_current_and_constant_buckets():
    decrypted = {
        "status": "success",
        "data": [
            {"state": "Tamil Nadu", "year": "2020-21", "priceType": "current", "price": 225106},
            {"state": "Tamil Nadu", "year": "2020-21", "priceType": "constant", "price": 162456},
            {"state": "Kerala",     "year": "2020-21", "priceType": "current", "price": 199000},
            {"state": "Karnataka",  "year": "2019-20", "priceType": "constant", "price": 186000},
            # unmapped ICED label — must skip silently and bump skipped counter
            {"state": "Atlantis",   "year": "2020-21", "priceType": "current", "price": 1},
        ],
    }
    out = parse_per_capita_income(decrypted)

    assert out.skipped_unmapped == 1
    # FY label normalised to YYYY-04 (start month of fiscal year)
    assert {(r["entity_id"], r["time"], r["value"]) for r in out.current} == {
        ("S22", "2020-04", 225106),
        ("S11", "2020-04", 199000),
    }
    assert {(r["entity_id"], r["time"], r["value"]) for r in out.constant} == {
        ("S22", "2020-04", 162456),
        ("S10", "2019-04", 186000),
    }
    # No facet/vintage on these — single-value-per-(state, year).
    for r in (*out.current, *out.constant):
        assert "facet" not in r and "vintage" not in r


def test_per_capita_income_dedups_last_write_wins():
    decrypted = {"data": [
        {"state": "Tamil Nadu", "year": "2020-21", "priceType": "current", "price": 100},
        {"state": "Tamil Nadu", "year": "2020-21", "priceType": "current", "price": 200},
    ]}
    out = parse_per_capita_income(decrypted)
    assert [(r["entity_id"], r["time"], r["value"]) for r in out.current] == [
        ("S22", "2020-04", 200),
    ]


def test_per_capita_income_rejects_non_list_data():
    with pytest.raises(ICEDShapeError):
        parse_per_capita_income({"data": {"oops": "dict"}})


# ---------------------------------------------------------------------------
# parse_per_capita_consumption
# ---------------------------------------------------------------------------


def test_per_capita_consumption_keeps_only_state_segment():
    decrypted = {"data": {
        "state": [
            {"year": "2020-21", "state": "Tamil Nadu", "perCapitaConsumption": 145000},
            {"year": "2019-20", "state": "Kerala",     "perCapitaConsumption": 160000},
        ],
        "indiaWorld": [
            {"year": "1971", "state": "World", "perCapitaConsumption": 999999},
        ],
    }}
    rows, skipped = parse_per_capita_consumption(decrypted)
    assert skipped == 0
    # World row is in indiaWorld, not state — so it must not appear here.
    assert all(r["entity_id"] in {"S22", "S11"} for r in rows)
    assert {(r["entity_id"], r["time"]) for r in rows} == {
        ("S22", "2020-04"), ("S11", "2019-04"),
    }


def test_per_capita_consumption_rejects_missing_state_segment():
    with pytest.raises(ICEDShapeError):
        parse_per_capita_consumption({"data": {"indiaWorld": []}})


# ---------------------------------------------------------------------------
# parse_ghg_economy_wide
# ---------------------------------------------------------------------------


def test_ghg_economy_wide_facets_by_sector_and_pins_to_india():
    decrypted = {"data": [
        {"_id": {"year": 2020, "sector": "Energy"},      "value": 2700000},
        {"_id": {"year": 2020, "sector": "Agriculture"}, "value": 650000},
        {"_id": {"year": 2020, "sector": "Waste"},       "value": 80000},
        # LULUCF can be negative (forest absorption) — must pass through.
        {"_id": {"year": 2020, "sector": "LULUCF"},      "value": -300000},
    ]}
    rows = parse_ghg_economy_wide(decrypted)
    assert all(r["entity_id"] == "IN" for r in rows)
    by_sector = {r["facet"]: r["value"] for r in rows}
    assert by_sector == {
        "Energy": 2700000,
        "Agriculture": 650000,
        "Waste": 80000,
        "LULUCF": -300000,
    }
    # All same year → time uniform.
    assert {r["time"] for r in rows} == {"2020"}


def test_ghg_economy_wide_skips_malformed_id_blocks():
    decrypted = {"data": [
        {"_id": "not a dict", "value": 1},
        {"_id": {"year": 2020, "sector": ""}, "value": 1},   # empty sector
        {"_id": {"year": "junk", "sector": "Energy"}, "value": 1},
        {"_id": {"year": 2020, "sector": "Energy"}, "value": 100},   # the only valid one
    ]}
    rows = parse_ghg_economy_wide(decrypted)
    assert rows == [{"entity_id": "IN", "time": "2020", "value": 100, "facet": "Energy"}]
