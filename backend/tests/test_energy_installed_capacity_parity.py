"""Parity oracle + D33.8 negative assert for energy_installed_capacity.parquet.

Asserts the canonical Parquet contains specific (entity, year, indicator)
cells with values that match the source JSON shard byte-for-byte. Cells are
hand-picked RAW (1:1 mapped) rows — no sub-fuel collapse aggregation involved
— so a mismatch unambiguously means the adapter or writer corrupted the value
in transit.

D33.8 negative assert (per plan-doc §3.1 follow-up 6): the Parquet MUST NOT
contain any ``*-total-mw`` or ``*-thermal-mw`` indicator_id. Those are
compute-on-read parents per Hans's atomic-fuel ruling; emitting them at write
time would hide methodology breaks (B3 MNRE off-grid Aug-2021, B7 CEA coal
aggregate proxy FY22+) inside a single aggregate.

Holy Law #7: uses real on-disk Parquet + real shard sources, no mocks.
Skipped cleanly when the canonical Parquet is absent (e.g., on a fresh
checkout before ``python -m yen_gov lift-energy --root .``).
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PARQUET = REPO_ROOT / "datasets" / "energy" / "energy_installed_capacity.parquet"
SHARD_DIR = REPO_ROOT / "datasets" / "indicators" / "in" / "energy"


pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason=(
        "datasets/energy/energy_installed_capacity.parquet not on disk; "
        "run `python -m yen_gov lift-energy --root .` first"
    ),
)


def _query_value(entity_id: str, year: int, indicator_id: str) -> float | None:
    """Look up a single observation value in the Parquet."""
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


# ---------------------------------------------------------------------------
# Parity oracle (≥3 cells)
# ---------------------------------------------------------------------------


def test_state_geographical_publisher_total_matches_shard_in_2015() -> None:
    """state-installed-capacity-geographical-mw, IN 2015-04 = 306329.85 (raw)."""
    val = _query_value("IN", 2015, "state-installed-capacity-geographical-mw")
    assert val == pytest.approx(306329.85, abs=0.01), (
        f"IN 2015 state-installed-capacity-geographical-mw expected 306329.85, got {val!r}"
    )


def test_state_allocated_publisher_total_matches_shard_in_2015() -> None:
    """state-installed-capacity-allocated-mw, IN 2015-04 = 305162.5 (raw)."""
    val = _query_value("IN", 2015, "state-installed-capacity-allocated-mw")
    assert val == pytest.approx(305162.5, abs=0.01), (
        f"IN 2015 state-installed-capacity-allocated-mw expected 305162.5, got {val!r}"
    )


def test_state_geographical_coal_facet_matches_shard_s01_2015() -> None:
    """state-installed-capacity-geographical-mw-coal, IN-S01 2015-04 = 9670.0 (raw 1:1).

    Sub-fuel ``coal`` collapses 1:1 to canonical ``coal`` — single shard row
    contributes, derivation="raw"."""
    val = _query_value("IN-S01", 2015, "state-installed-capacity-geographical-mw-coal")
    assert val == pytest.approx(9670.0, abs=0.01), (
        f"IN-S01 2015 ...-mw-coal expected 9670.0, got {val!r}"
    )


def test_state_geographical_renewable_facet_is_sum_of_collapsed_subfuels() -> None:
    """state-installed-capacity-geographical-mw-renewable, IN-S01 2015-04 =
    sum of bio-power + small-hydro + solar + wind (+ waste-to-energy if present).

    Verifies the sub-fuel collapse against an independently computed expected
    value from the source shard."""
    shard = json.loads(
        (SHARD_DIR / "state_installed_capacity_by_source_mw.json").read_text(encoding="utf-8")
    )
    renewable_subs = {"bio-power", "biomass", "small-hydro", "solar", "wind", "waste-to-energy"}
    expected = sum(
        float(r["value"])
        for r in shard["rows"]
        if r["entity_id"] == "S01" and r["time"] == "2015-04" and r["facet"] in renewable_subs
    )
    assert expected > 0, "sanity: shard has at least one renewable sub-fuel row for S01 2015"

    val = _query_value("IN-S01", 2015, "state-installed-capacity-geographical-mw-renewable")
    assert val == pytest.approx(expected, abs=0.01), (
        f"IN-S01 2015 ...-mw-renewable expected {expected!r} (sum-of-{len(renewable_subs)}), got {val!r}"
    )


# ---------------------------------------------------------------------------
# C4.5 parity oracle — state-installed-capacity-snapshot-mw-{fuel}
#
# 3 cells per fuel = 15 raw 1:1 assertions. The CEA Monthly IC sheet is a
# per-state per-fuel snapshot (single period, time="2026-03"), so each
# canonical row is a verbatim copy of one shard row with no aggregation —
# a mismatch unambiguously means the adapter or writer corrupted the value.
# ---------------------------------------------------------------------------


def test_c45_snapshot_coal_in_s24_2026() -> None:
    """state-installed-capacity-snapshot-mw-coal, IN-S24 2026-03 = 25550.906."""
    val = _query_value("IN-S24", 2026, "state-installed-capacity-snapshot-mw-coal")
    assert val == pytest.approx(25550.906, abs=0.01), (
        f"IN-S24 2026 ...-snapshot-mw-coal expected 25550.906, got {val!r}"
    )


def test_c45_snapshot_coal_in_s13_2026() -> None:
    """state-installed-capacity-snapshot-mw-coal, IN-S13 2026-03 = 24714.238."""
    val = _query_value("IN-S13", 2026, "state-installed-capacity-snapshot-mw-coal")
    assert val == pytest.approx(24714.238, abs=0.01), (
        f"IN-S13 2026 ...-snapshot-mw-coal expected 24714.238, got {val!r}"
    )


def test_c45_snapshot_coal_in_s06_2026() -> None:
    """state-installed-capacity-snapshot-mw-coal, IN-S06 2026-03 = 16735.582."""
    val = _query_value("IN-S06", 2026, "state-installed-capacity-snapshot-mw-coal")
    assert val == pytest.approx(16735.582, abs=0.01), (
        f"IN-S06 2026 ...-snapshot-mw-coal expected 16735.582, got {val!r}"
    )


def test_c45_snapshot_gas_in_s06_2026() -> None:
    """state-installed-capacity-snapshot-mw-gas, IN-S06 2026-03 = 5615.72."""
    val = _query_value("IN-S06", 2026, "state-installed-capacity-snapshot-mw-gas")
    assert val == pytest.approx(5615.72, abs=0.01), (
        f"IN-S06 2026 ...-snapshot-mw-gas expected 5615.72, got {val!r}"
    )


def test_c45_snapshot_gas_in_s13_2026() -> None:
    """state-installed-capacity-snapshot-mw-gas, IN-S13 2026-03 = 3124.73."""
    val = _query_value("IN-S13", 2026, "state-installed-capacity-snapshot-mw-gas")
    assert val == pytest.approx(3124.73, abs=0.01), (
        f"IN-S13 2026 ...-snapshot-mw-gas expected 3124.73, got {val!r}"
    )


def test_c45_snapshot_gas_in_u05_2026() -> None:
    """state-installed-capacity-snapshot-mw-gas, IN-U05 2026-03 = 2007.414434."""
    val = _query_value("IN-U05", 2026, "state-installed-capacity-snapshot-mw-gas")
    assert val == pytest.approx(2007.414434, abs=0.000001), (
        f"IN-U05 2026 ...-snapshot-mw-gas expected 2007.414434, got {val!r}"
    )


def test_c45_snapshot_hydro_in_s19_2026() -> None:
    """state-installed-capacity-snapshot-mw-hydro, IN-S19 2026-03 = 3827.435354."""
    val = _query_value("IN-S19", 2026, "state-installed-capacity-snapshot-mw-hydro")
    assert val == pytest.approx(3827.435354, abs=0.000001), (
        f"IN-S19 2026 ...-snapshot-mw-hydro expected 3827.435354, got {val!r}"
    )


def test_c45_snapshot_hydro_in_s08_2026() -> None:
    """state-installed-capacity-snapshot-mw-hydro, IN-S08 2026-03 = 3706.8698620."""
    val = _query_value("IN-S08", 2026, "state-installed-capacity-snapshot-mw-hydro")
    assert val == pytest.approx(3706.8698620, abs=0.000001), (
        f"IN-S08 2026 ...-snapshot-mw-hydro expected 3706.8698620, got {val!r}"
    )


def test_c45_snapshot_hydro_in_s24_2026() -> None:
    """state-installed-capacity-snapshot-mw-hydro, IN-S24 2026-03 = 3652.222272."""
    val = _query_value("IN-S24", 2026, "state-installed-capacity-snapshot-mw-hydro")
    assert val == pytest.approx(3652.222272, abs=0.000001), (
        f"IN-S24 2026 ...-snapshot-mw-hydro expected 3652.222272, got {val!r}"
    )


def test_c45_snapshot_nuclear_in_s22_2026() -> None:
    """state-installed-capacity-snapshot-mw-nuclear, IN-S22 2026-03 = 1448.0."""
    val = _query_value("IN-S22", 2026, "state-installed-capacity-snapshot-mw-nuclear")
    assert val == pytest.approx(1448.0, abs=0.01), (
        f"IN-S22 2026 ...-snapshot-mw-nuclear expected 1448.0, got {val!r}"
    )


def test_c45_snapshot_nuclear_in_s13_2026() -> None:
    """state-installed-capacity-snapshot-mw-nuclear, IN-S13 2026-03 = 1068.66."""
    val = _query_value("IN-S13", 2026, "state-installed-capacity-snapshot-mw-nuclear")
    assert val == pytest.approx(1068.66, abs=0.01), (
        f"IN-S13 2026 ...-snapshot-mw-nuclear expected 1068.66, got {val!r}"
    )


def test_c45_snapshot_nuclear_in_s06_2026() -> None:
    """state-installed-capacity-snapshot-mw-nuclear, IN-S06 2026-03 = 1034.89."""
    val = _query_value("IN-S06", 2026, "state-installed-capacity-snapshot-mw-nuclear")
    assert val == pytest.approx(1034.89, abs=0.01), (
        f"IN-S06 2026 ...-snapshot-mw-nuclear expected 1034.89, got {val!r}"
    )


def test_c45_snapshot_renewable_in_s20_2026() -> None:
    """state-installed-capacity-snapshot-mw-renewable, IN-S20 2026-03 = 46608.04."""
    val = _query_value("IN-S20", 2026, "state-installed-capacity-snapshot-mw-renewable")
    assert val == pytest.approx(46608.04, abs=0.01), (
        f"IN-S20 2026 ...-snapshot-mw-renewable expected 46608.04, got {val!r}"
    )


def test_c45_snapshot_renewable_in_s06_2026() -> None:
    """state-installed-capacity-snapshot-mw-renewable, IN-S06 2026-03 = 45188.33."""
    val = _query_value("IN-S06", 2026, "state-installed-capacity-snapshot-mw-renewable")
    assert val == pytest.approx(45188.33, abs=0.01), (
        f"IN-S06 2026 ...-snapshot-mw-renewable expected 45188.33, got {val!r}"
    )


def test_c45_snapshot_renewable_in_s13_2026() -> None:
    """state-installed-capacity-snapshot-mw-renewable, IN-S13 2026-03 = 28933.63."""
    val = _query_value("IN-S13", 2026, "state-installed-capacity-snapshot-mw-renewable")
    assert val == pytest.approx(28933.63, abs=0.01), (
        f"IN-S13 2026 ...-snapshot-mw-renewable expected 28933.63, got {val!r}"
    )


def test_c45_snapshot_row_count_per_fuel_is_35() -> None:
    """Every CEA fuel emits exactly 35 per-state snapshot rows (one per
    state/UT) in year=2026. Guards against the upstream-truncation case the
    adapter's ``assert len(shard_rows) >= 30`` was placed to catch — and
    pins the row-count delta (175 new rows = 5 fuels x 35 states) for
    sprint accounting."""
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            f"SELECT indicator_id, COUNT(*) AS n FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE 'state-installed-capacity-snapshot-mw-%' "
            f"AND year = 2026 GROUP BY indicator_id ORDER BY indicator_id"
        ).fetchall()
    finally:
        con.close()
    counts = {row[0]: row[1] for row in rows}
    expected = {
        f"state-installed-capacity-snapshot-mw-{fuel}": 35
        for fuel in ("coal", "gas", "hydro", "nuclear", "renewable")
    }
    assert counts == expected, (
        f"snapshot-mw per-fuel row counts off: expected {expected!r}, got {counts!r}"
    )


# ---------------------------------------------------------------------------
# D33.8 negative assert (per plan-doc §3.1 follow-up 6)
# ---------------------------------------------------------------------------


def test_d33_8_no_total_mw_rows_emitted() -> None:
    """D33.8: ``*-total-mw`` rows are compute-on-read parents; emitting them
    at write time would hide methodology breaks B3 + B7 inside an aggregate.
    Writer + adapter MUST refuse to emit any."""
    con = duckdb.connect(":memory:")
    try:
        n = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '%-total-mw'"
        ).fetchone()[0]
    finally:
        con.close()
    assert n == 0, (
        f"D33.8 violation: energy_installed_capacity.parquet contains {n} "
        f"`*-total-mw` rows. These must compute on read from per-fuel children, "
        f"never emit at write time. See ADR-0030 D33.8."
    )


def test_d33_8_no_thermal_mw_rows_emitted() -> None:
    """D33.8: ``*-thermal-mw`` rows are compute-on-read parents that sum
    coal + gas + diesel. Emitting at write time hides the fuel mix and breaks
    the citizen-facing per-fuel breakdown."""
    con = duckdb.connect(":memory:")
    try:
        n = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '%-thermal-mw'"
        ).fetchone()[0]
    finally:
        con.close()
    assert n == 0, (
        f"D33.8 violation: energy_installed_capacity.parquet contains {n} "
        f"`*-thermal-mw` rows. These must compute on read from per-fuel children."
    )


def test_parquet_has_canonical_observation_columns() -> None:
    """Schema-conformance smoke: the energy fact-table follows the same
    column shape as elections/election_results.parquet."""
    con = duckdb.connect(":memory:")
    try:
        cols = {
            row[0]: row[1]
            for row in con.execute(
                f"DESCRIBE SELECT * FROM read_parquet('{PARQUET.as_posix()}')"
            ).fetchall()
        }
    finally:
        con.close()
    assert list(cols.keys()) == [
        "observation_id", "entity_id", "year", "period_label", "period_seq",
        "indicator_id", "value_numeric", "value_text", "source_id", "derivation",
    ], f"unexpected columns in energy_installed_capacity.parquet: {list(cols.keys())!r}"
