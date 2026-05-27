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
    """peak-electricity-demand-mw, IN-S01 2013-04 = 14072.0 (raw, RBI Hbk T142)."""
    val = _query_value("IN-S01", 2013, "peak-electricity-demand-mw")
    assert val == pytest.approx(14072.0, abs=0.01), (
        f"IN-S01 2013 peak-electricity-demand-mw expected 14072.0, got {val!r}"
    )


def test_state_peak_supplied_matches_shard_s01_2013() -> None:
    """peak-electricity-supplied-mw, IN-S01 2013-04 = 13162.0 (raw, RBI Hbk T142)."""
    val = _query_value("IN-S01", 2013, "peak-electricity-supplied-mw")
    assert val == pytest.approx(13162.0, abs=0.01), (
        f"IN-S01 2013 peak-electricity-supplied-mw expected 13162.0, got {val!r}"
    )


def test_state_per_capita_consumption_matches_shard_u01_2009() -> None:
    """state-per-capita-electricity-consumption-kwh, IN-U01 2009-04 = 493.979 (raw, ICED Deep Dive)."""
    val = _query_value("IN-U01", 2009, "state-per-capita-electricity-consumption-kwh")
    assert val == pytest.approx(493.979, abs=0.001), (
        f"IN-U01 2009 state-per-capita-electricity-consumption-kwh expected 493.979, got {val!r}"
    )


def test_parquet_has_six_distinct_indicators_after_p1b() -> None:
    """P.1.A (3) + P.1.B (3) = 6 indicators on this table. P.1.A: peak
    demand (FY13-FY25, RBI+ICED), peak supplied (FY13-FY24, RBI),
    per-capita consumption (FY09-FY24, ICED). P.1.B: requirement,
    availability, per-capita availability (all RBI Handbook, long-arc
    FY05-FY24)."""
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
        # P.1.A
        "peak-electricity-demand-mw",
        "peak-electricity-supplied-mw",
        "state-per-capita-electricity-consumption-kwh",
        # P.1.B
        "state-electricity-requirement-mu",
        "state-electricity-availability-mu",
        "state-per-capita-electricity-availability-kwh",
    }
    # PR-W (Row 6 / P.1.C 7/9) extended this parquet with 12
    # power-purchase-share-pct-{fuel} children (parent carries 0
    # rows so doesn't appear in DISTINCT). Sibling-widening per the
    # NO_CAVEATS_DESCRIPTOR pattern: switch from set-equality to
    # set-superset, allowing future P.1.C / P.1.D additions onto this
    # stem without re-editing the assertion.
    actual = set(indicators)
    assert expected.issubset(actual), (
        f"energy_demand_supply.parquet missing P.1.A/P.1.B indicators: "
        f"{expected - actual!r}"
    )


# ---------------------------------------------------------------------------
# P.1.B pinned-cell parity asserts.
# Plan: TODO/20260522-phase-2-p1-energy-pivot.md §3 P.1.B.
# Cells lifted from RBI Handbook Tables 138 / 139 / 141 shards under
# datasets/indicators/in/energy/state_power_*.json + state_per_capita_*.
# Pinned to catch regressions where the lift accidentally drops rows,
# mis-routes source FKs, or applies an unintended numeric transform.
# ---------------------------------------------------------------------------


def test_p1b_power_requirement_s01_2004() -> None:
    """state-electricity-requirement-mu, IN-S01 2004-04 = 5042.0
    (raw, RBI Hbk Table 141; CEA originating data)."""
    val = _query_value("IN-S01", 2004, "state-electricity-requirement-mu")
    assert val == pytest.approx(5042.0, abs=0.01), (
        f"IN-S01 2004 power requirement expected 5042.0, got {val!r}"
    )


def test_p1b_power_availability_s01_2004() -> None:
    """state-electricity-availability-mu, IN-S01 2004-04 = 5006.0
    (raw, RBI Hbk Table 139; CEA originating data)."""
    val = _query_value("IN-S01", 2004, "state-electricity-availability-mu")
    assert val == pytest.approx(5006.0, abs=0.01), (
        f"IN-S01 2004 power availability expected 5006.0, got {val!r}"
    )


def test_p1b_per_capita_availability_s01_2004() -> None:
    """state-per-capita-electricity-availability-kwh, IN-S01 2004-04 =
    656.9 (raw, RBI Hbk Table 138; CEA originating data)."""
    val = _query_value(
        "IN-S01", 2004, "state-per-capita-electricity-availability-kwh"
    )
    assert val == pytest.approx(656.9, abs=0.01), (
        f"IN-S01 2004 per-capita availability expected 656.9, got {val!r}"
    )


def test_p1b_source_id_routing() -> None:
    """Each P.1.B RBI Handbook indicator MUST carry the source_id for
    its Table number. T141 / T139 / T138 are three DIFFERENT source
    rows (one per Handbook table) per the v2.0 citation ledger; the
    triples differ on the title field. Catches a regression where the
    lift accidentally cross-wires source FKs between blocks."""
    cases = {
        "state-electricity-requirement-mu":              "src-f7ce9960caba",  # T141
        "state-electricity-availability-mu":             "src-97a3c47d092f",  # T139
        "state-per-capita-electricity-availability-kwh": "src-9a38005d8713",  # T138
    }
    con = duckdb.connect(":memory:")
    try:
        for indicator_id, expected_src in cases.items():
            srcs = {
                row[0]
                for row in con.execute(
                    f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
                    f"WHERE indicator_id = ?",
                    [indicator_id],
                ).fetchall()
            }
            assert srcs == {expected_src}, (
                f"source_id drift on {indicator_id}: expected exclusive "
                f"{{{expected_src!r}}}, got {srcs!r}"
            )
    finally:
        con.close()


# ---------------------------------------------------------------------------
# C4.7: FY25 extension of peak-electricity-demand-mw via ICED shard 2.
# Plan: TODO/20260524-p1a-data-reacquisition-plan.md §3 C4.7.
# Coverage was FY13..FY24 (RBI Hbk T142); extended to FY25 with the 34 ICED
# rows (33 states + IN national) from state_electricity_peak_demand_mw.json.
# RBI remains gold for FY13-FY24; ICED is gold ONLY for FY25.
# ---------------------------------------------------------------------------


def test_c47_fy25_peak_demand_tn_value() -> None:
    """peak-electricity-demand-mw, IN-S22 (TN) 2025-04 = 20211.0
    (raw, ICED state-wise-deep-dive endpoint, lifted by C4.7)."""
    val = _query_value("IN-S22", 2025, "peak-electricity-demand-mw")
    assert val == pytest.approx(20211.0, abs=0.01), (
        f"IN-S22 2025 peak-electricity-demand-mw expected 20211.0, got {val!r}"
    )


def test_c47_fy25_peak_demand_national_aggregate() -> None:
    """peak-electricity-demand-mw, IN 2025-04 = 245416.0 — the
    national-aggregate row only shard 2 provides; shard 1 (33 state
    rows) was retired specifically because it omits this cell."""
    val = _query_value("IN", 2025, "peak-electricity-demand-mw")
    assert val == pytest.approx(245416.0, abs=0.01), (
        f"IN 2025 peak-electricity-demand-mw expected 245416.0, got {val!r}"
    )


def test_c47_fy25_peak_demand_source_id_is_iced() -> None:
    """All FY25 rows carry source_id = src-bb1d7bec8b34 (ICED Deep Dive
    Energy Database; rotated under ADR-0042 when ICED vintage flipped
    from "" → "2024-25"). FY13-FY24 rows must remain RBI = src-99ac1fee8a50.
    Catches a regression where the FY25 lift accidentally writes the
    wrong source FK or backfills onto RBI years."""
    con = duckdb.connect(":memory:")
    try:
        fy25_sources = {
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
                f"WHERE indicator_id = 'peak-electricity-demand-mw' AND year = 2025"
            ).fetchall()
        }
        pre_fy25_sources = {
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
                f"WHERE indicator_id = 'peak-electricity-demand-mw' AND year BETWEEN 2013 AND 2024"
            ).fetchall()
        }
    finally:
        con.close()
    assert fy25_sources == {"src-bb1d7bec8b34"}, (
        f"FY25 source_id set drift: expected {{'src-bb1d7bec8b34'}}, got {fy25_sources!r}"
    )
    assert pre_fy25_sources == {"src-99ac1fee8a50"}, (
        f"FY13-FY24 source_id set drift (RBI should be exclusive): "
        f"expected {{'src-99ac1fee8a50'}}, got {pre_fy25_sources!r}"
    )


def test_c47_peak_demand_total_rowcount_after_fy25_extension() -> None:
    """peak-electricity-demand-mw rowcount: 396 (RBI FY13-FY24,
    34 entities x 12 years - 12 missing) + 34 (ICED FY25, 33 states +
    IN national) = 430. Pinned so a future regression that double-counts
    overlap years or drops the national row trips immediately."""
    con = duckdb.connect(":memory:")
    try:
        count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = 'peak-electricity-demand-mw'"
        ).fetchone()[0]
        fy25_count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = 'peak-electricity-demand-mw' AND year = 2025"
        ).fetchone()[0]
        max_period = con.execute(
            f"SELECT MAX(period_label) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = 'peak-electricity-demand-mw'"
        ).fetchone()[0]
    finally:
        con.close()
    assert count == 430, f"total rowcount drift: expected 430, got {count}"
    assert fy25_count == 34, f"FY25 rowcount drift: expected 34 (33 states + IN), got {fy25_count}"
    assert max_period == "2025-04", (
        f"max period_label drift: expected '2025-04' (C4.7 should extend coverage by one year), "
        f"got {max_period!r}"
    )
