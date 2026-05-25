"""Parity oracle for energy_distribution_performance.parquet.

P.1.A — ATC losses + sales-MU, both raw.
P.1.B — efficiency triple (billing / collection / T&D-loss), ACS-ARR gap,
RPO compliance 3-facet (solar / non-solar / total).

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


def test_parquet_has_eight_distinct_indicators_after_p1b() -> None:
    """P.1.A (2) + P.1.B (6: 3 efficiency children + ACS-ARR + 3 RPO
    children) = 8 observation-emitting indicators on this table. The 2
    parents (state-distribution-efficiency-pct + state-rpo-compliance-pct)
    are compute-on-read and emit NO rows here."""
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
    expected = {
        # P.1.A
        "state-atc-losses-pct",
        "state-electricity-sales-mu",
        # P.1.B — efficiency triple (children of state-distribution-efficiency-pct)
        "state-distribution-efficiency-pct-billing",
        "state-distribution-efficiency-pct-collection",
        "state-distribution-efficiency-pct-td-loss",
        # P.1.B — ACS-ARR standalone
        "state-acs-arr-gap-inr-per-kwh",
        # P.1.B — RPO triple (children of state-rpo-compliance-pct)
        "state-rpo-compliance-pct-solar",
        "state-rpo-compliance-pct-non-solar",
        "state-rpo-compliance-pct-total",
    }
    assert indicators == expected, (
        f"energy_distribution_performance.parquet indicator set drift: "
        f"expected {expected!r}, got {indicators!r}"
    )


# ---------------------------------------------------------------------------
# P.1.B pinned-cell parity asserts.
# Plan: TODO/20260522-phase-2-p1-energy-pivot.md §3 P.1.B.
# Cells lifted from shards under datasets/indicators/in/energy/ (see
# the corresponding state_*_*.json files). Pinned to catch regressions
# where the lift accidentally drops rows, mis-routes facets, or applies
# an unintended numeric transform.
# ---------------------------------------------------------------------------


def test_p1b_distribution_billing_efficiency_s01_2009() -> None:
    """state-distribution-efficiency-pct-billing, IN-S01 2009-04 =
    85.6402621476843 (raw, ICED distribution-perf endpoint)."""
    val = _query_value(
        "IN-S01", 2009, "state-distribution-efficiency-pct-billing"
    )
    assert val == pytest.approx(85.6402621476843, abs=1e-9), (
        f"IN-S01 2009 billing-efficiency expected 85.6402..., got {val!r}"
    )


def test_p1b_distribution_collection_efficiency_s01_2009() -> None:
    """state-distribution-efficiency-pct-collection, IN-S01 2009-04 =
    97.58 (raw, ICED distribution-perf endpoint)."""
    val = _query_value(
        "IN-S01", 2009, "state-distribution-efficiency-pct-collection"
    )
    assert val == pytest.approx(97.58, abs=1e-4), (
        f"IN-S01 2009 collection-efficiency expected 97.58, got {val!r}"
    )


def test_p1b_distribution_td_loss_s01_2009() -> None:
    """state-distribution-efficiency-pct-td-loss, IN-S01 2009-04 =
    18.37 (raw, ICED distribution-perf endpoint)."""
    val = _query_value(
        "IN-S01", 2009, "state-distribution-efficiency-pct-td-loss"
    )
    assert val == pytest.approx(18.37, abs=1e-4), (
        f"IN-S01 2009 td-loss expected 18.37, got {val!r}"
    )


def test_p1b_acs_arr_gap_in_2016() -> None:
    """state-acs-arr-gap-inr-per-kwh, IN 2016-04 = 0.69 (raw, ICED Deep
    Dive endpoint)."""
    val = _query_value("IN", 2016, "state-acs-arr-gap-inr-per-kwh")
    assert val == pytest.approx(0.69, abs=1e-4), (
        f"IN 2016 ACS-ARR gap expected 0.69, got {val!r}"
    )


def test_p1b_rpo_solar_s01_2018() -> None:
    """state-rpo-compliance-pct-solar, IN-S01 2018-04 = 7.5254...
    (raw, ICED distribution-RPO endpoint, facet=solar)."""
    val = _query_value("IN-S01", 2018, "state-rpo-compliance-pct-solar")
    assert val == pytest.approx(7.525411382975202, abs=1e-9), (
        f"IN-S01 2018 RPO solar expected 7.5254..., got {val!r}"
    )


def test_p1b_rpo_non_solar_s01_2018() -> None:
    """state-rpo-compliance-pct-non-solar, IN-S01 2018-04 = 15.8669...
    (raw, ICED distribution-RPO endpoint, facet=non-solar). Verifies
    the legacy hyphenated facet 'non-solar' correctly routes to the
    canonical -non-solar child indicator_id."""
    val = _query_value("IN-S01", 2018, "state-rpo-compliance-pct-non-solar")
    assert val == pytest.approx(15.866966857596928, abs=1e-9), (
        f"IN-S01 2018 RPO non-solar expected 15.8669..., got {val!r}"
    )


def test_p1b_rpo_total_s01_2018() -> None:
    """state-rpo-compliance-pct-total, IN-S01 2018-04 = 23.3923...
    (raw, ICED distribution-RPO endpoint, facet=total). This is the
    regulator's combined-target compliance ratio, NOT the sum of solar
    + non-solar."""
    val = _query_value("IN-S01", 2018, "state-rpo-compliance-pct-total")
    assert val == pytest.approx(23.392378240572132, abs=1e-9), (
        f"IN-S01 2018 RPO total expected 23.3923..., got {val!r}"
    )


def test_p1b_source_id_routing() -> None:
    """Each P.1.B indicator MUST carry the source_id for its upstream
    endpoint. ICED distribution-perf for the efficiency triple, ICED
    Deep Dive for ACS-ARR, ICED distribution-RPO for the RPO triple.
    Catches a regression where the lift accidentally cross-wires
    source FKs between blocks."""
    cases = {
        # 3 ICED ids rotated under ADR-0042 (vintage "" → "2024-25"):
        # iced_distribution_perf, iced_deep_dive, iced_distribution_rpo.
        "state-distribution-efficiency-pct-billing":    "src-650b1c25d1f7",
        "state-distribution-efficiency-pct-collection": "src-650b1c25d1f7",
        "state-distribution-efficiency-pct-td-loss":    "src-650b1c25d1f7",
        "state-acs-arr-gap-inr-per-kwh":                "src-bb1d7bec8b34",
        "state-rpo-compliance-pct-solar":               "src-0ea63ed47704",
        "state-rpo-compliance-pct-non-solar":           "src-0ea63ed47704",
        "state-rpo-compliance-pct-total":               "src-0ea63ed47704",
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
