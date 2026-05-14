"""Pure-parser tests for the iced_power adapter.

Per CLAUDE.md §15 (Tier: Unit) — the parsers are pure functions over an
already-decrypted (or already-JSON-parsed) ICED response. We feed them
the exact shape the real API returns (verified against the cached raw
responses on 2026-05-14) and assert the canonical row outputs. No
network, no cipher, no I/O.
"""
from __future__ import annotations

import pytest

from yen_gov.sources.iced_common import ICEDShapeError
from yen_gov.sources.iced_power.parsers import (
    parse_capacity_metatable,
    parse_pipeline,
    parse_power_statistics,
    parse_retired_capacity,
)


# ---------------------------------------------------------------------------
# parse_capacity_metatable
# ---------------------------------------------------------------------------


def test_capacity_metatable_emits_state_year_source_rows_with_facet():
    decrypted = [
        {"state": "Tamil Nadu", "fyear": "2020-21", "source": "wind", "capacity": 9450.5},
        {"state": "Tamil Nadu", "fyear": "2020-21", "source": "coal", "capacity": 4320.0},
        {"state": "Kerala", "fyear": "2020-21", "source": "hydro", "capacity": 2126.6},
        # Unmapped state must drop and bump skipped counter
        {"state": "Atlantis", "fyear": "2020-21", "source": "coal", "capacity": 100},
        # Missing required field → drop silently
        {"state": "Karnataka", "fyear": "2020-21", "source": "wind"},
    ]
    rows, skipped = parse_capacity_metatable(decrypted)

    assert skipped == 1
    triples = {(r["entity_id"], r["time"], r["facet"]) for r in rows}
    assert triples == {
        ("S22", "2020-04", "wind"),
        ("S22", "2020-04", "coal"),
        ("S11", "2020-04", "hydro"),
    }
    # Sorted by (entity_id, time, facet)
    assert [r["entity_id"] for r in rows] == sorted(r["entity_id"] for r in rows)


def test_capacity_metatable_rejects_non_list_top_level():
    with pytest.raises(ICEDShapeError):
        parse_capacity_metatable({"data": []})


def test_capacity_metatable_dedups_last_write_wins():
    decrypted = [
        {"state": "Tamil Nadu", "fyear": "2020-21", "source": "wind", "capacity": 1.0},
        {"state": "Tamil Nadu", "fyear": "2020-21", "source": "wind", "capacity": 2.0},
    ]
    rows, _ = parse_capacity_metatable(decrypted)
    assert len(rows) == 1
    assert rows[0]["value"] == 2.0


# ---------------------------------------------------------------------------
# parse_power_statistics
# ---------------------------------------------------------------------------


def test_power_statistics_yields_generation_and_peak_demand_separately():
    decrypted = {
        "stateWiseData": [
            {
                "state": "Tamil Nadu",
                "fyear": "2025-2026",
                "peakDemand": 18548,
                "energyMet": 88439,
                "data": [
                    {"source": "wind", "capacity": 9450, "generation": 18000.5},
                    {"source": "coal", "capacity": 4320, "generation": 22000.0},
                ],
            },
            {
                "state": "Atlantis",
                "fyear": "2025-2026",
                "peakDemand": 1,
                "data": [],
            },
        ],
        "nationalData": [{"summary": "ignored"}],
    }
    gen, peak, skipped = parse_power_statistics(decrypted)

    assert skipped == 1
    assert {(r["entity_id"], r["time"], r["facet"], r["value"]) for r in gen} == {
        ("S22", "2025-04", "wind", 18000.5),
        ("S22", "2025-04", "coal", 22000.0),
    }
    assert peak == [{"entity_id": "S22", "time": "2025-04", "value": 18548}]


def test_power_statistics_handles_yyyy_yyyy_fyear_format():
    decrypted = {"stateWiseData": [
        {"state": "Tamil Nadu", "fyear": "2025-2026", "peakDemand": 100, "data": []},
    ]}
    _, peak, _ = parse_power_statistics(decrypted)
    assert peak[0]["time"] == "2025-04"


def test_power_statistics_rejects_missing_state_block():
    with pytest.raises(ICEDShapeError):
        parse_power_statistics({"nationalData": []})


# ---------------------------------------------------------------------------
# parse_retired_capacity
# ---------------------------------------------------------------------------


def test_retired_capacity_emits_national_rows_facetted_by_source():
    decrypted = {"data": [
        {"totalCapacity": 399.5, "year": "2005-06", "source": "coal"},
        {"totalCapacity": 460.0, "year": "2010-11", "source": "oil-gas"},
        # Bad year → drop
        {"totalCapacity": 1, "year": "garbage", "source": "coal"},
    ]}
    rows = parse_retired_capacity(decrypted)
    assert {(r["entity_id"], r["time"], r["facet"], r["value"]) for r in rows} == {
        ("IN", "2005-04", "coal", 399.5),
        ("IN", "2010-04", "oil-gas", 460.0),
    }
    assert all(r["entity_id"] == "IN" for r in rows)


def test_retired_capacity_accepts_bare_list_too():
    rows = parse_retired_capacity([
        {"totalCapacity": 100, "year": "2020-21", "source": "coal"},
    ])
    assert rows == [{"entity_id": "IN", "time": "2020-04", "value": 100, "facet": "coal"}]


# ---------------------------------------------------------------------------
# parse_pipeline
# ---------------------------------------------------------------------------


def test_pipeline_zips_category_with_each_seriesData():
    decrypted = {
        "category": ["2024", "2025", "2026"],
        "seriesData": [
            {"name": "Under Construction and likely to be commissioned",
             "data": [6.5, 3.58, 8.52]},
            {"name": "Under Construction but on Hold",
             "data": [0, 0, 0.5]},
        ],
    }
    rows = parse_pipeline(decrypted)
    quads = {(r["entity_id"], r["time"], r["facet"], r["value"]) for r in rows}
    assert quads == {
        ("IN", "2024", "Under Construction and likely to be commissioned", 6.5),
        ("IN", "2025", "Under Construction and likely to be commissioned", 3.58),
        ("IN", "2026", "Under Construction and likely to be commissioned", 8.52),
        ("IN", "2024", "Under Construction but on Hold", 0),
        ("IN", "2025", "Under Construction but on Hold", 0),
        ("IN", "2026", "Under Construction but on Hold", 0.5),
    }


def test_pipeline_rejects_missing_arrays():
    with pytest.raises(ICEDShapeError):
        parse_pipeline({"category": ["2024"]})  # missing seriesData
