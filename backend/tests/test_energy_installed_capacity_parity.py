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
# PR 7c-4: installed-capacity shards promoted to the meadow tier per ADR-0041.
MEADOW_ICED = REPO_ROOT / "datasets" / "energy" / "_meadow" / "iced" / "2024-25"
MEADOW_RBI = REPO_ROOT / "datasets" / "energy" / "_meadow" / "rbi" / "2024-25"


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
    """installed-capacity-geographical-mw, IN 2015-04 = 306329.85 (raw)."""
    val = _query_value("IN", 2015, "installed-capacity-geographical-mw")
    assert val == pytest.approx(306329.85, abs=0.01), (
        f"IN 2015 installed-capacity-geographical-mw expected 306329.85, got {val!r}"
    )


def test_state_allocated_publisher_total_matches_shard_in_2015() -> None:
    """installed-capacity-allocated-mw, IN 2015-04 = 305162.5 (raw)."""
    val = _query_value("IN", 2015, "installed-capacity-allocated-mw")
    assert val == pytest.approx(305162.5, abs=0.01), (
        f"IN 2015 installed-capacity-allocated-mw expected 305162.5, got {val!r}"
    )


def test_state_geographical_coal_facet_matches_shard_s01_2015() -> None:
    """installed-capacity-geographical-mw-coal, IN-S01 2015-04 = 9670.0 (raw 1:1).

    Sub-fuel ``coal`` collapses 1:1 to canonical ``coal`` — single shard row
    contributes, derivation="raw"."""
    val = _query_value("IN-S01", 2015, "installed-capacity-geographical-mw-coal")
    assert val == pytest.approx(9670.0, abs=0.01), (
        f"IN-S01 2015 ...-mw-coal expected 9670.0, got {val!r}"
    )


def test_state_geographical_renewable_facet_is_sum_of_collapsed_subfuels() -> None:
    """installed-capacity-geographical-mw-renewable, IN-S01 2015-04 =
    sum of bio-power + small-hydro + solar + wind (+ waste-to-energy if present).

    Verifies the sub-fuel collapse against an independently computed expected
    value from the source shard."""
    shard = json.loads(
        (MEADOW_ICED / "state_installed_capacity_by_source_mw.json").read_text(encoding="utf-8")
    )
    renewable_subs = {"bio-power", "biomass", "small-hydro", "solar", "wind", "waste-to-energy"}
    expected = sum(
        float(r["value"])
        for r in shard["rows"]
        if r["entity_id"] == "S01" and r["time"] == "2015-04" and r["facet"] in renewable_subs
    )
    assert expected > 0, "sanity: shard has at least one renewable sub-fuel row for S01 2015"

    val = _query_value("IN-S01", 2015, "installed-capacity-geographical-mw-renewable")
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


# ---------------------------------------------------------------------------
# C4.6 parity oracle — RBI Handbook Table 140 FY05-FY14 long-arc splice
#
# Lift block 5 adds 374 rows (11 fiscal years FY05-FY14 × 34 states/UTs) to
# the parent indicator ``installed-capacity-allocated-mw``, carrying
# source_id ``src-3d1d55f8a94b`` (rbi_hbk_140_installed_capacity). Block 4
# continues to own FY15-FY25 via ICED Deep Dive (src-bb1d7bec8b34, rotated
# under ADR-0042). The splice boundary at FY15 is documented by the
# methodology break row
# ``rbi-handbook-aggregate-no-fuel-split-pre-fy15``.
#
# Per Fowler pre-impl: cell values pinned against the SHARD source
# (``state_installed_capacity_total_mw.json``), since the canonical Parquet
# is regenerated from the same shard and a value drift would mean the
# adapter or writer corrupted the value in transit.
# ---------------------------------------------------------------------------


def test_c46_longarc_s22_2014() -> None:
    """installed-capacity-allocated-mw, IN-S22 2014-04 = 23258.0 (RBI Handbook Table 140)."""
    val = _query_value("IN-S22", 2014, "installed-capacity-allocated-mw")
    assert val == pytest.approx(23258.0, abs=0.01), (
        f"IN-S22 2014 ...-allocated-mw expected 23258.0 (RBI HBK 140 FY14), got {val!r}"
    )


def test_c46_longarc_s22_2005() -> None:
    """installed-capacity-allocated-mw, IN-S22 2005-04 = SHARD value (RBI Handbook Table 140 FY05).

    Pins the long-arc FAR boundary. Value sourced from the shard directly
    rather than hand-typing it: a drift between shard and Parquet here is
    a writer/adapter bug, not a stale-test bug."""
    shard = json.loads(
        (MEADOW_RBI / "state_installed_capacity_total_mw.json").read_text(encoding="utf-8")
    )
    expected_rows = [r for r in shard["rows"] if r["entity_id"] == "S22" and r["time"] == "2005-04"]
    assert len(expected_rows) == 1, (
        f"shard sanity: expected 1 row for S22 2005-04, got {len(expected_rows)}"
    )
    expected = float(expected_rows[0]["value"])
    val = _query_value("IN-S22", 2005, "installed-capacity-allocated-mw")
    assert val == pytest.approx(expected, abs=0.01), (
        f"IN-S22 2005 ...-allocated-mw expected {expected!r} (RBI HBK 140 FY05), got {val!r}"
    )


def test_c46_longarc_s10_2010() -> None:
    """installed-capacity-allocated-mw, IN-S10 2010-04 = 11546.0 (RBI Handbook Table 140 FY10).

    Bihar at FY10 — a mid-arc cell on a state that did NOT bifurcate during
    the window. Pins that block 5 emits state-level rows correctly for the
    common case."""
    val = _query_value("IN-S10", 2010, "installed-capacity-allocated-mw")
    assert val == pytest.approx(11546.0, abs=0.01), (
        f"IN-S10 2010 ...-allocated-mw expected 11546.0 (RBI HBK 140 FY10), got {val!r}"
    )


def test_c46_longarc_s29_2014() -> None:
    """installed-capacity-allocated-mw, IN-S29 2014-04 = 9470.0 (RBI Handbook Table 140 FY14).

    Telangana — the entity boundary case. Telangana was formed 2014-06-02,
    so the shard could plausibly carry zero pre-FY15 rows (entity didn't
    exist) OR one row at FY14 (publisher backdates the FY14 = "as-of
    March 2014" snapshot for the new entity). Verified by inspection
    2026-05-24 at lift-prep: shard carries exactly one S29 pre-FY15 row at
    time="2014-04" with value=9470.0; block 5 emits it verbatim."""
    val = _query_value("IN-S29", 2014, "installed-capacity-allocated-mw")
    assert val == pytest.approx(9470.0, abs=0.01), (
        f"IN-S29 2014 ...-allocated-mw expected 9470.0 (RBI HBK 140 FY14, Telangana boundary case), got {val!r}"
    )


def test_c46_longarc_uses_rbi_source_id() -> None:
    """All pre-FY15 ``installed-capacity-allocated-mw`` rows carry the RBI
    Handbook Table 140 source_id (``src-3d1d55f8a94b``); all FY15+ rows carry
    the ICED Deep Dive source_id (``src-bb1d7bec8b34``, rotated under
    ADR-0042). Pins the source_id boundary at year=2015 — a leak in either
    direction means block 4 or block 5 is emitting at the wrong fiscal
    range."""
    con = duckdb.connect(":memory:")
    try:
        rbi_pre = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = 'installed-capacity-allocated-mw' "
            f"AND year < 2015 AND source_id = 'src-3d1d55f8a94b'"
        ).fetchone()[0]
        non_rbi_pre = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = 'installed-capacity-allocated-mw' "
            f"AND year < 2015 AND source_id != 'src-3d1d55f8a94b'"
        ).fetchone()[0]
        iced_post = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = 'installed-capacity-allocated-mw' "
            f"AND year >= 2015 AND source_id = 'src-bb1d7bec8b34'"
        ).fetchone()[0]
        non_iced_post = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = 'installed-capacity-allocated-mw' "
            f"AND year >= 2015 AND source_id != 'src-bb1d7bec8b34'"
        ).fetchone()[0]
    finally:
        con.close()
    assert rbi_pre > 0, "RBI HBK 140 pre-FY15 rows missing from Parquet"
    assert non_rbi_pre == 0, (
        f"source_id leak: {non_rbi_pre} pre-FY15 allocated-mw rows have non-RBI source_id"
    )
    assert iced_post > 0, "ICED FY15+ rows missing from Parquet"
    assert non_iced_post == 0, (
        f"source_id leak: {non_iced_post} FY15+ allocated-mw rows have non-ICED source_id"
    )


def test_c46_longarc_row_count_pre_2015_is_374() -> None:
    """Block 5 emits exactly 374 pre-FY15 rows (11 fiscal years FY05-FY14 ×
    34 states/UTs). Pinned against the shard inspection on 2026-05-24 at
    lift-prep — the plan-doc's original ~305-row estimate was derived
    before the entity-count was firm and has been corrected to 374 in this
    PR. A row-count drift here means either: (a) block 5's
    ``r["time"] >= "2015-04"`` boundary is wrong, OR (b) the upstream shard
    grew/shrank between lift-prep and this run (Telangana boundary case
    audit)."""
    con = duckdb.connect(":memory:")
    try:
        n = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = 'installed-capacity-allocated-mw' "
            f"AND year < 2015"
        ).fetchone()[0]
    finally:
        con.close()
    assert n == 374, (
        f"C4.6 longarc pre-FY15 row count: expected 374 (11 FY × 34 entities), got {n}. "
        f"Either block 5 boundary drifted or upstream shard changed shape."
    )


def test_c46_fy14_fy15_continuity_at_tn() -> None:
    """Tamil Nadu FY14 (RBI Handbook) → FY15 (ICED Deep Dive) splice
    continuity smoke. The splice straddles two publishers + a definitional
    boundary (basis change documented by the
    ``rbi-handbook-aggregate-no-fuel-split-pre-fy15`` methodology break),
    so an exact value-match is NOT expected. But a one-year jump from
    23258 MW (FY14) to anything beyond +/- 10000 MW (FY15) would indicate
    a units or scale corruption rather than a real installed-capacity
    delta. Pins the splice doesn't produce an obviously broken series."""
    fy14 = _query_value("IN-S22", 2014, "installed-capacity-allocated-mw")
    fy15 = _query_value("IN-S22", 2015, "installed-capacity-allocated-mw")
    assert fy14 is not None, "TN FY14 (RBI HBK 140) row missing"
    assert fy15 is not None, "TN FY15 (ICED Deep Dive) row missing"
    delta = abs(fy15 - fy14)
    assert delta < 10000.0, (
        f"TN FY14→FY15 splice produced an implausible jump: "
        f"FY14={fy14!r}, FY15={fy15!r}, delta={delta!r}. "
        f"Unit / scale corruption suspected."
    )

