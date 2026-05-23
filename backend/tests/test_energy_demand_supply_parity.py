"""Parity oracle for energy_demand_supply.parquet.

No fuel facet on this fact-table (peak demand / supplied / per-capita
consumption are scalar per state-year). The parity check is therefore
straightforward: pick 3 known cells from the 3 source shards and assert
the Parquet has the same value.

Holy Law #7: real Parquet + real shards, no mocks.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PARQUET = REPO_ROOT / "datasets" / "energy" / "energy_demand_supply.parquet"


pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason=(
        "datasets/energy/energy_demand_supply.parquet not on disk; "
        "run `python -m yen_gov lift-energy --root .` first"
    ),
)


def _query_value(entity_id: str, year: int, indicator_id: str) -> float | None:
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            f"SELECT value_numeric FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE entity_id = ? AND year = ? AND indicator_id = ?",
            [entity_id, year, indicator_id],
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return None
    return rows[0][0]


def test_state_peak_demand_matches_shard_s01_2013() -> None:
    """state-peak-electricity-demand-mw, IN-S01 2013-04 = 14072.0 (raw, RBI Hbk T142)."""
    val = _query_value("IN-S01", 2013, "state-peak-electricity-demand-mw")
    assert val == pytest.approx(14072.0, abs=0.01), (
        f"IN-S01 2013 state-peak-electricity-demand-mw expected 14072.0, got {val!r}"
    )


def test_state_peak_supplied_matches_shard_s01_2013() -> None:
    """state-peak-electricity-supplied-mw, IN-S01 2013-04 = 13162.0 (raw, RBI Hbk T142)."""
    val = _query_value("IN-S01", 2013, "state-peak-electricity-supplied-mw")
    assert val == pytest.approx(13162.0, abs=0.01), (
        f"IN-S01 2013 state-peak-electricity-supplied-mw expected 13162.0, got {val!r}"
    )


def test_state_per_capita_consumption_matches_shard_u01_2009() -> None:
    """state-per-capita-electricity-consumption-kwh, IN-U01 2009-04 = 493.979 (raw, ICED Deep Dive)."""
    val = _query_value("IN-U01", 2009, "state-per-capita-electricity-consumption-kwh")
    assert val == pytest.approx(493.979, abs=0.001), (
        f"IN-U01 2009 state-per-capita-electricity-consumption-kwh expected 493.979, got {val!r}"
    )


def test_parquet_has_three_distinct_indicators() -> None:
    """Sanity: the demand-supply table carries the 3 P.1.A indicators
    (peak demand + peak supplied + per-capita consumption); P.1.B will
    extend with requirement / availability."""
    con = duckdb.connect(":memory:")
    try:
        indicators = sorted({
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}')"
            ).fetchall()
        })
    finally:
        con.close()
    expected = {
        "state-peak-electricity-demand-mw",
        "state-peak-electricity-supplied-mw",
        "state-per-capita-electricity-consumption-kwh",
    }
    actual = set(indicators)
    assert actual == expected, (
        f"energy_demand_supply.parquet indicator set drift: expected {expected!r}, got {actual!r}"
    )


# ---------------------------------------------------------------------------
# C4.7: FY25 extension of state-peak-electricity-demand-mw via ICED shard 2.
# Plan: TODO/20260524-p1a-data-reacquisition-plan.md §3 C4.7.
# Coverage was FY13..FY24 (RBI Hbk T142); extended to FY25 with the 34 ICED
# rows (33 states + IN national) from state_electricity_peak_demand_mw.json.
# RBI remains gold for FY13-FY24; ICED is gold ONLY for FY25.
# ---------------------------------------------------------------------------


def test_c47_fy25_peak_demand_tn_value() -> None:
    """state-peak-electricity-demand-mw, IN-S22 (TN) 2025-04 = 20211.0
    (raw, ICED state-wise-deep-dive endpoint, lifted by C4.7)."""
    val = _query_value("IN-S22", 2025, "state-peak-electricity-demand-mw")
    assert val == pytest.approx(20211.0, abs=0.01), (
        f"IN-S22 2025 state-peak-electricity-demand-mw expected 20211.0, got {val!r}"
    )


def test_c47_fy25_peak_demand_national_aggregate() -> None:
    """state-peak-electricity-demand-mw, IN 2025-04 = 245416.0 — the
    national-aggregate row only shard 2 provides; shard 1 (33 state
    rows) was retired specifically because it omits this cell."""
    val = _query_value("IN", 2025, "state-peak-electricity-demand-mw")
    assert val == pytest.approx(245416.0, abs=0.01), (
        f"IN 2025 state-peak-electricity-demand-mw expected 245416.0, got {val!r}"
    )


def test_c47_fy25_peak_demand_source_id_is_iced() -> None:
    """All FY25 rows carry source_id = src-be6a6d5d6493 (ICED Deep Dive
    Energy Database). FY13-FY24 rows must remain RBI = src-99ac1fee8a50.
    Catches a regression where the FY25 lift accidentally writes the
    wrong source FK or backfills onto RBI years."""
    con = duckdb.connect(":memory:")
    try:
        fy25_sources = {
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
                f"WHERE indicator_id = 'state-peak-electricity-demand-mw' AND year = 2025"
            ).fetchall()
        }
        pre_fy25_sources = {
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
                f"WHERE indicator_id = 'state-peak-electricity-demand-mw' AND year BETWEEN 2013 AND 2024"
            ).fetchall()
        }
    finally:
        con.close()
    assert fy25_sources == {"src-be6a6d5d6493"}, (
        f"FY25 source_id set drift: expected {{'src-be6a6d5d6493'}}, got {fy25_sources!r}"
    )
    assert pre_fy25_sources == {"src-99ac1fee8a50"}, (
        f"FY13-FY24 source_id set drift (RBI should be exclusive): "
        f"expected {{'src-99ac1fee8a50'}}, got {pre_fy25_sources!r}"
    )


def test_c47_peak_demand_total_rowcount_after_fy25_extension() -> None:
    """state-peak-electricity-demand-mw rowcount: 396 (RBI FY13-FY24,
    34 entities x 12 years - 12 missing) + 34 (ICED FY25, 33 states +
    IN national) = 430. Pinned so a future regression that double-counts
    overlap years or drops the national row trips immediately."""
    con = duckdb.connect(":memory:")
    try:
        count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = 'state-peak-electricity-demand-mw'"
        ).fetchone()[0]
        fy25_count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = 'state-peak-electricity-demand-mw' AND year = 2025"
        ).fetchone()[0]
        max_period = con.execute(
            f"SELECT MAX(period_label) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = 'state-peak-electricity-demand-mw'"
        ).fetchone()[0]
    finally:
        con.close()
    assert count == 430, f"total rowcount drift: expected 430, got {count}"
    assert fy25_count == 34, f"FY25 rowcount drift: expected 34 (33 states + IN), got {fy25_count}"
    assert max_period == "2025-04", (
        f"max period_label drift: expected '2025-04' (C4.7 should extend coverage by one year), "
        f"got {max_period!r}"
    )
