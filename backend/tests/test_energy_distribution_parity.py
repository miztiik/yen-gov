"""Parity oracle for energy_distribution_performance.parquet.

ATC losses + sales-MU, both raw. No fuel facet, no sub-fuel collapse.
P.1.B will extend with ACS-ARR gap, billing/collection efficiency, T&D
losses-pct (3-facet via ``efficiency_dimension`` axis).

Holy Law #7: real Parquet + real shards, no mocks.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PARQUET = REPO_ROOT / "datasets" / "energy" / "energy_distribution_performance.parquet"


pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason=(
        "datasets/energy/energy_distribution_performance.parquet not on disk; "
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


def test_state_atc_losses_matches_shard_in_2015() -> None:
    """state-atc-losses-pct, IN 2015-04 = 23.96 (raw, ICED Deep Dive)."""
    val = _query_value("IN", 2015, "state-atc-losses-pct")
    assert val == pytest.approx(23.96, abs=0.01), (
        f"IN 2015 state-atc-losses-pct expected 23.96, got {val!r}"
    )


def test_state_atc_losses_matches_shard_in_2017() -> None:
    """state-atc-losses-pct, IN 2017-04 = 21.5 (raw)."""
    val = _query_value("IN", 2017, "state-atc-losses-pct")
    assert val == pytest.approx(21.5, abs=0.01), (
        f"IN 2017 state-atc-losses-pct expected 21.5, got {val!r}"
    )


def test_state_electricity_sales_matches_shard_in_2015() -> None:
    """state-electricity-sales-mu, IN 2015-04 = 810968.22 (raw, ICED Deep Dive)."""
    val = _query_value("IN", 2015, "state-electricity-sales-mu")
    assert val == pytest.approx(810968.22, abs=0.01), (
        f"IN 2015 state-electricity-sales-mu expected 810968.22, got {val!r}"
    )


def test_parquet_has_two_distinct_indicators_in_p1a() -> None:
    """Sanity: P.1.A carries ATC + sales only; ACS-ARR / billing-eff /
    collection-eff land in P.1.B."""
    con = duckdb.connect(":memory:")
    try:
        indicators = {
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}')"
            ).fetchall()
        }
    finally:
        con.close()
    expected = {"state-atc-losses-pct", "state-electricity-sales-mu"}
    assert indicators == expected, (
        f"energy_distribution_performance.parquet indicator set drift: "
        f"expected {expected!r}, got {indicators!r} — "
        f"new indicators belong in P.1.B per plan-doc §4"
    )
