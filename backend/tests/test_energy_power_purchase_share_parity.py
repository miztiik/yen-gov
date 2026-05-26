"""Parity oracle for the state-power-purchase-share-pct canonical lift (PR-W).

ICED ``/statelevel-power-purchase-quantum-and-cost`` (state-wise
procurement-mix share by source) -> 2658 raw meadow obs rows joined
into ``energy_demand_supply.parquet``. Pattern A-facet on the EXISTING
``fuel_type`` axis with NO sub-fuel collapse (procurement share is a
percentage; cannot be summed across sources without double-counting).

12 publisher source labels map 1:1 to canonical fuel_type axis values
via ``_POWER_PURCHASE_PUBLISHER_TO_CANONICAL`` in ``demand_supply.py``:
  bio-power          -> biomass
  coal               -> coal
  diesel             -> diesel
  hybrid-bundled     -> hybrid-bundled   (NEW axis val_id `hybrid_bundled`)
  hydro              -> hydro
  nuclear            -> nuclear
  oil-gas            -> gas
  other-res          -> renewable-other
  small-hydro        -> small-hydro
  solar              -> solar
  trading-and-others -> trading-other    (NEW axis val_id `trading_other`)
  wind               -> wind

These tests are skipped at collection time when the parquet is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PARQUET = REPO_ROOT / "datasets" / "energy" / "energy_demand_supply.parquet"
MEADOW = (
    REPO_ROOT / "datasets" / "energy" / "_meadow" / "iced" / "2024-25"
    / "state_power_purchase_share_pct.json"
)

pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason="energy_demand_supply.parquet not built; run `python -m yen_gov lift-energy`",
)

EXPECTED_SOURCE_ID = "src-1401f8087b0d"
PARENT_ID = "state-power-purchase-share-pct"
EXPECTED_CHILD_IDS = {
    f"{PARENT_ID}-biomass",
    f"{PARENT_ID}-coal",
    f"{PARENT_ID}-diesel",
    f"{PARENT_ID}-gas",
    f"{PARENT_ID}-hybrid-bundled",
    f"{PARENT_ID}-hydro",
    f"{PARENT_ID}-nuclear",
    f"{PARENT_ID}-renewable-other",
    f"{PARENT_ID}-small-hydro",
    f"{PARENT_ID}-solar",
    f"{PARENT_ID}-trading-other",
    f"{PARENT_ID}-wind",
}


def _q(sql: str) -> list[tuple]:
    return duckdb.connect(":memory:").execute(sql).fetchall()


def test_row_count_matches_meadow() -> None:
    """2658 obs = passthrough; no aggregation, no filter."""
    meadow_rows = json.loads(MEADOW.read_text(encoding="utf-8"))["rows"]
    assert len(meadow_rows) == 2658
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert rows[0][0] == 2658


def test_twelve_child_indicator_ids() -> None:
    """Exactly 12 canonical child indicator_ids, locking the 1:1 mapping."""
    indicator_ids = {
        row[0]
        for row in _q(
            f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '{PARENT_ID}%'"
        )
    }
    assert indicator_ids == EXPECTED_CHILD_IDS


def test_parent_has_zero_rows() -> None:
    """Compute-on-read parent: catalogue + facet-picker only; no obs rows."""
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{PARENT_ID}'"
    )
    assert rows[0][0] == 0


def test_publisher_collapses_documented() -> None:
    """Verify the 4 non-trivial publisher-to-canonical collapses:
    bio-power -> biomass, oil-gas -> gas, other-res -> renewable-other,
    trading-and-others -> trading-other, hybrid-bundled -> hybrid-bundled.
    None of the raw publisher labels should appear as indicator_id suffixes.
    """
    indicator_ids = {
        row[0]
        for row in _q(
            f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '{PARENT_ID}%'"
        )
    }
    # Canonical IDs MUST be present.
    for fuel in ("biomass", "gas", "renewable-other", "trading-other", "hybrid-bundled"):
        assert f"{PARENT_ID}-{fuel}" in indicator_ids, f"missing {fuel}"
    # Raw publisher labels MUST NOT appear as indicator_id suffixes.
    for raw in ("bio-power", "oil-gas", "other-res", "trading-and-others"):
        assert f"{PARENT_ID}-{raw}" not in indicator_ids, (
            f"raw publisher label `{raw}` leaked into indicator_id"
        )


def test_all_rows_carry_expected_source_id() -> None:
    rows = _q(
        f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert len(rows) == 1
    assert rows[0][0] == EXPECTED_SOURCE_ID


def test_all_rows_have_derivation_raw() -> None:
    rows = _q(
        f"SELECT DISTINCT derivation FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert len(rows) == 1
    assert rows[0][0] == "raw"


def test_entity_vocabulary_is_state_or_ut_only() -> None:
    """All entities are IN-S* (state) or IN-U* (UT). No national IN rollup
    -- procurement is per-DISCOM (state-grain only)."""
    rows = _q(
        f"SELECT DISTINCT entity_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    entity_ids = {r[0] for r in rows}
    assert "IN" not in entity_ids
    for eid in entity_ids:
        assert eid.startswith(("IN-S", "IN-U")), f"non-state/UT {eid!r}"


def test_time_vocabulary_is_fiscal_year_2015_to_2024() -> None:
    """All period_labels are 'YYYY-04' in range 2015-04..2024-04 (10 FYs)."""
    rows = _q(
        f"SELECT DISTINCT period_label FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%' ORDER BY 1"
    )
    labels = [r[0] for r in rows]
    assert labels[0] == "2015-04"
    assert labels[-1] == "2024-04"
    assert len(labels) == 10


def test_36_distinct_states_or_uts() -> None:
    rows = _q(
        f"SELECT COUNT(DISTINCT entity_id) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert rows[0][0] == 36


def test_does_not_displace_existing_demand_supply_indicators() -> None:
    """PR-W joining energy_demand_supply must NOT have evicted prior
    peak-demand or per-capita-availability indicators."""
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = 'state-peak-electricity-demand-mw'"
    )
    assert rows[0][0] >= 300
