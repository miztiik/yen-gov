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
