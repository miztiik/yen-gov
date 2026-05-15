"""Pure-parser tests for iced_metatable."""
from __future__ import annotations

import pytest

from yen_gov.sources.iced_common import ICEDShapeError
from yen_gov.sources.iced_metatable.parsers import (
    parse_co_emission_metatable,
    parse_gen_metatable,
    parse_plf_metatable,
)


# ---------------------------------------------------------------------------
# parse_gen_metatable (bare-list shape)
# ---------------------------------------------------------------------------


def test_gen_metatable_emits_one_row_per_state_year_source():
    decoded = [
        {"state": "Tamil Nadu", "year": "2023-24", "source": "coal", "generation": 12345.6},
        {"state": "Tamil Nadu", "year": "2023-24", "source": "solar", "generation": 7890.1},
        {"state": "Karnataka", "year": "2023-24", "source": "wind", "generation": 4500.0},
    ]
    rows, skipped = parse_gen_metatable(decoded)
    assert skipped == 0
    assert {(r["entity_id"], r["facet"], r["value"]) for r in rows} == {
        ("S22", "coal", 12345.6),
        ("S22", "solar", 7890.1),
        ("S10", "wind", 4500.0),
    }
    assert all(r["time"] == "2023-04" for r in rows)


def test_gen_metatable_drops_others_bucket_and_counts_unmapped():
    decoded = [
        {"state": "Others", "year": "2023-24", "source": "coal", "generation": 999.0},
        {"state": "Atlantis", "year": "2023-24", "source": "coal", "generation": 1.0},
        {"state": "Bihar", "year": "2023-24", "source": "coal", "generation": 7.0},
    ]
    rows, skipped = parse_gen_metatable(decoded)
    assert skipped == 2  # Others and Atlantis both unmapped
    assert {r["entity_id"] for r in rows} == {"S04"}


def test_gen_metatable_dedups_last_write_wins():
    decoded = [
        {"state": "Bihar", "year": "2023-24", "source": "coal", "generation": 100.0},
        {"state": "Bihar", "year": "2023-24", "source": "coal", "generation": 200.0},
    ]
    rows, _ = parse_gen_metatable(decoded)
    assert len(rows) == 1
    assert rows[0]["value"] == 200.0


def test_gen_metatable_skips_null_generation_and_bad_year():
    decoded = [
        {"state": "Bihar", "year": "2023-24", "source": "coal", "generation": None},
        {"state": "Bihar", "year": "garbage", "source": "coal", "generation": 5.0},
        {"state": "Bihar", "year": "2023-24", "source": "", "generation": 5.0},
    ]
    rows, _ = parse_gen_metatable(decoded)
    assert rows == []


def test_gen_metatable_accepts_dict_wrapped_data_key():
    decoded = {"data": [
        {"state": "Goa", "year": "2020-21", "source": "hydro", "generation": 12.5},
    ]}
    rows, _ = parse_gen_metatable(decoded)
    assert rows == [{"entity_id": "S05", "time": "2020-04", "value": 12.5, "facet": "hydro"}]


def test_gen_metatable_rejects_unexpected_top_level():
    with pytest.raises(ICEDShapeError):
        parse_gen_metatable("not a list or dict")


# ---------------------------------------------------------------------------
# parse_plf_metatable
# ---------------------------------------------------------------------------


def test_plf_metatable_uses_plf_field_and_emits_percent():
    decoded = [
        {"state": "Tamil Nadu", "year": "2023-24", "source": "coal", "plf": 62.5},
        {"state": "Tamil Nadu", "year": "2023-24", "source": "wind", "plf": 18.0},
    ]
    rows, _ = parse_plf_metatable(decoded)
    assert {(r["facet"], r["value"]) for r in rows} == {("coal", 62.5), ("wind", 18.0)}


def test_plf_metatable_skips_null_plf():
    decoded = [
        {"state": "Bihar", "year": "2023-24", "source": "coal", "plf": None},
    ]
    rows, _ = parse_plf_metatable(decoded)
    assert rows == []


# ---------------------------------------------------------------------------
# parse_co_emission_metatable (aggregation)
# ---------------------------------------------------------------------------


def test_co_emission_aggregates_units_per_state_year_source():
    decoded = {"data": [
        {"state": "Chhattisgarh", "year": "2024-25", "source": "coal",
         "plantName": "Lara STPS", "unitName": "Unit 2", "value": 6.5},
        {"state": "Chhattisgarh", "year": "2024-25", "source": "coal",
         "plantName": "Lara STPS", "unitName": "Unit 1", "value": 5.5},
        {"state": "Chhattisgarh", "year": "2024-25", "source": "oil-gas",
         "plantName": "X", "unitName": "Y", "value": 0.2},
    ]}
    rows, _ = parse_co_emission_metatable(decoded)
    by_facet = {r["facet"]: r["value"] for r in rows}
    assert by_facet == {"coal": 12.0, "oil-gas": 0.2}
    assert all(r["entity_id"] == "S26" and r["time"] == "2024-04" for r in rows)


def test_co_emission_skips_unmapped_state_and_zero_passthrough():
    decoded = [
        {"state": "Atlantis", "year": "2020-21", "source": "coal", "value": 1.0},
        {"state": "Bihar", "year": "2020-21", "source": "coal", "value": 0.0},
    ]
    rows, skipped = parse_co_emission_metatable(decoded)
    assert skipped == 1
    # zero-value plant year still emits a (Bihar, coal) row of 0.0
    assert rows == [{"entity_id": "S04", "time": "2020-04", "value": 0.0, "facet": "coal"}]


def test_co_emission_handles_bare_list_top_level():
    decoded = [
        {"state": "Goa", "year": "2020-21", "source": "coal", "value": 0.5},
    ]
    rows, _ = parse_co_emission_metatable(decoded)
    assert rows == [{"entity_id": "S05", "time": "2020-04", "value": 0.5, "facet": "coal"}]
