"""Parity oracle for energy_fuel_consumption.parquet.

P.1.C PR-Q -- coal consumption (Mt, state x fiscal-year), raw lift from
ICED ``/energy/fuel-sources/coal/consumption-domestic-state``.

This is the FIRST canonical fact-table on the ``energy_fuel_consumption``
stem; subsequent P.1.C PRs (oil-product / primary / final energy supply)
will add more indicators to this same parquet.

Holy Law #7: real Parquet + real shards, no mocks.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PARQUET = REPO_ROOT / "datasets" / "energy" / "energy_fuel_consumption.parquet"
MEADOW = (
    REPO_ROOT
    / "datasets"
    / "energy"
    / "_meadow"
    / "iced"
    / "2024-25"
    / "state_coal_consumption_mt.json"
)

# Citation ledger row for the ICED coal-consumption endpoint
# (derive_source_id("NITI Aayog India Climate & Energy Dashboard",
#  "Coal Consumption (Domestic) State-wise API ...", "2024-25"))
EXPECTED_SOURCE_ID = "src-c222a8e2cd61"


pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason=(
        "datasets/energy/energy_fuel_consumption.parquet not on disk; "
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


def test_state_coal_consumption_first_row_s01_2006() -> None:
    """First row of the meadow shard: S01 FY 2006-04 = 29.49 Mt (raw, ICED)."""
    val = _query_value("IN-S01", 2006, "state-coal-consumption-mt")
    assert val == pytest.approx(29.49, abs=0.01), (
        f"IN-S01 2006 state-coal-consumption-mt expected 29.49, got {val!r}"
    )


def test_state_coal_consumption_top_consumer_s26_2024() -> None:
    """S26 FY 2024-04 = 128.16 Mt (top coal-consuming state-year in the shard)."""
    val = _query_value("IN-S26", 2024, "state-coal-consumption-mt")
    assert val == pytest.approx(128.16, abs=0.01), (
        f"IN-S26 2024 state-coal-consumption-mt expected 128.16, got {val!r}"
    )


def test_state_coal_consumption_s27_2020() -> None:
    """S27 FY 2020-04 = 47.3 Mt (mid-tier consumer)."""
    val = _query_value("IN-S27", 2020, "state-coal-consumption-mt")
    assert val == pytest.approx(47.3, abs=0.01), (
        f"IN-S27 2020 state-coal-consumption-mt expected 47.3, got {val!r}"
    )


def test_parquet_has_single_indicator() -> None:
    """Only one indicator in this parquet (PR-Q first-cut); subsequent
    P.1.C PRs extend the indicator set on the same parquet."""
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
    assert indicators == {"state-coal-consumption-mt"}, (
        f"energy_fuel_consumption.parquet indicator set drift: {indicators!r}"
    )


def test_row_count_matches_meadow_shard() -> None:
    """Lift is 1:1 with meadow rows (no aggregation, no facet drop) for
    state-coal-consumption-mt: 450 rows expected."""
    con = duckdb.connect(":memory:")
    try:
        n = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = ?",
            ["state-coal-consumption-mt"],
        ).fetchone()[0]
    finally:
        con.close()
    meadow_rows = json.loads(MEADOW.read_text(encoding="utf-8"))["rows"]
    assert n == len(meadow_rows) == 450, (
        f"row count drift: parquet={n}, meadow={len(meadow_rows)}, expected 450"
    )


def test_all_rows_carry_coal_consumption_source_id() -> None:
    """source_id FK closure: every coal-consumption row carries the
    ICED citation ledger row's source_id (src-c222a8e2cd61)."""
    con = duckdb.connect(":memory:")
    try:
        source_ids = {
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
                f"WHERE indicator_id = ?",
                ["state-coal-consumption-mt"],
            ).fetchall()
        }
    finally:
        con.close()
    assert source_ids == {EXPECTED_SOURCE_ID}, (
        f"source_id drift: {source_ids!r}, expected {{{EXPECTED_SOURCE_ID!r}}}"
    )


def test_all_rows_have_derivation_raw() -> None:
    """The lift is documented as derivation='raw' (the 4-grade sum was
    done at MEADOW generation time, not adapter time)."""
    con = duckdb.connect(":memory:")
    try:
        derivations = {
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT derivation FROM read_parquet('{PARQUET.as_posix()}') "
                f"WHERE indicator_id = ?",
                ["state-coal-consumption-mt"],
            ).fetchall()
        }
    finally:
        con.close()
    assert derivations == {"raw"}, (
        f"derivation drift: {derivations!r}, expected {{'raw'}}"
    )


def test_time_vocabulary_is_fiscal_year_only() -> None:
    """ADR-0041 nn4 + inventory deriver homogeneity rule: every row
    on a single indicator must share one time-shape. Here period_label
    must always match YYYY-04 (fiscal-year shape)."""
    con = duckdb.connect(":memory:")
    try:
        labels = [
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT period_label FROM read_parquet('{PARQUET.as_posix()}') "
                f"WHERE indicator_id = ?",
                ["state-coal-consumption-mt"],
            ).fetchall()
        ]
    finally:
        con.close()
    for lbl in labels:
        assert lbl.endswith("-04") and len(lbl) == 7, (
            f"period_label {lbl!r} violates fiscal-year shape YYYY-04"
        )
    # Coverage spans the ICED vintage (FY 2006-04 ... FY 2024-04).
    assert "2006-04" in labels
    assert "2024-04" in labels


def test_entity_ids_are_in_prefix_normalised() -> None:
    """to_entity_id() must prepend ``IN-`` to every state code; the
    raw S01..U09 meadow forms are NOT allowed in the canonical parquet."""
    con = duckdb.connect(":memory:")
    try:
        entity_ids = [
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT entity_id FROM read_parquet('{PARQUET.as_posix()}') "
                f"WHERE indicator_id = ?",
                ["state-coal-consumption-mt"],
            ).fetchall()
        ]
    finally:
        con.close()
    for eid in entity_ids:
        assert eid.startswith("IN-") or eid == "IN", (
            f"entity_id {eid!r} missing IN- prefix"
        )
    # 26 sub-national entities in the shard (S01..S29 minus a few + 3 UTs).
    assert len(entity_ids) == 26, (
        f"entity_id count drift: {len(entity_ids)}, expected 26"
    )
