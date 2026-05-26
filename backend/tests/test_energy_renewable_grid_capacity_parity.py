"""Parity oracle for the state-renewable-grid-capacity-mw canonical lift (PR-Y).

RBI Handbook of Statistics on Indian States 2024-25 edition, Table 143
-> 585 raw meadow obs rows joined into ``energy_installed_capacity.parquet``.
Pattern A-SINGLE (scalar; no facet axis). Publisher does NOT split the
combined renewable capacity into per-source buckets.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PARQUET = REPO_ROOT / "datasets" / "energy" / "energy_installed_capacity.parquet"
MEADOW = (
    REPO_ROOT / "datasets" / "energy" / "_meadow" / "rbi" / "2024-25"
    / "state_renewable_grid_capacity_mw.json"
)

pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason="energy_installed_capacity.parquet not built; run `python -m yen_gov lift-energy`",
)

EXPECTED_SOURCE_ID = "src-1f51c8d742bf"
INDICATOR_ID = "state-renewable-grid-capacity-mw"


def _q(sql: str) -> list[tuple]:
    return duckdb.connect(":memory:").execute(sql).fetchall()


def test_row_count_matches_meadow() -> None:
    """585 obs = 1:1 passthrough (no aggregation; no facet collapse since
    publisher emits a scalar)."""
    meadow_rows = json.loads(MEADOW.read_text(encoding="utf-8"))["rows"]
    assert len(meadow_rows) == 585
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{INDICATOR_ID}'"
    )
    assert rows[0][0] == 585


def test_single_indicator_no_facet_children() -> None:
    """Pattern A-SINGLE: no `state-renewable-grid-capacity-mw-*` children
    should exist. Publisher emits no per-source split (combined wind +
    solar + small-hydro + biomass + waste-to-energy)."""
    indicator_ids = {
        row[0]
        for row in _q(
            f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '{INDICATOR_ID}%'"
        )
    }
    assert indicator_ids == {INDICATOR_ID}


def test_all_rows_carry_expected_source_id() -> None:
    rows = _q(
        f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{INDICATOR_ID}'"
    )
    assert len(rows) == 1
    assert rows[0][0] == EXPECTED_SOURCE_ID


def test_all_rows_have_derivation_raw() -> None:
    rows = _q(
        f"SELECT DISTINCT derivation FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{INDICATOR_ID}'"
    )
    assert len(rows) == 1
    assert rows[0][0] == "raw"


def test_entity_vocabulary_is_state_or_ut_only() -> None:
    rows = _q(
        f"SELECT DISTINCT entity_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{INDICATOR_ID}'"
    )
    entity_ids = {r[0] for r in rows}
    assert "IN" not in entity_ids, "RBI Table 143 should NOT carry a national IN rollup"
    for eid in entity_ids:
        assert eid.startswith(("IN-S", "IN-U")), f"non-state/UT {eid!r}"


def test_time_vocabulary_is_2007_to_2024_end_march() -> None:
    """All period_labels are 'YYYY-04' (end-March snapshot sentinel)
    in range 2007-04..2024-04 (18 years)."""
    rows = _q(
        f"SELECT DISTINCT period_label FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{INDICATOR_ID}' ORDER BY 1"
    )
    labels = [r[0] for r in rows]
    assert labels[0] == "2007-04"
    assert labels[-1] == "2024-04"
    assert len(labels) == 18
    for label in labels:
        assert label.endswith("-04"), f"non-end-March period_label {label!r}"


def test_36_distinct_states_or_uts() -> None:
    rows = _q(
        f"SELECT COUNT(DISTINCT entity_id) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{INDICATOR_ID}'"
    )
    assert rows[0][0] == 36


def test_rajasthan_dominates_in_2024() -> None:
    """Rajasthan (IN-S25 = state code S25 -> ramSeraph IN-S* lookup)
    leads at ~26,693 MW in 2024 per publisher description; sanity-check
    that some state exceeds 20,000 MW (5 states do: RJ, GJ, TN, KA, MH)."""
    rows = _q(
        f"SELECT MAX(value_numeric) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{INDICATOR_ID}' AND period_label = '2024-04'"
    )
    assert rows[0][0] > 20000.0, (
        f"max RE capacity in 2024 = {rows[0][0]}; expected > 20,000 MW "
        f"(top 5 states are RJ/GJ/TN/KA/MH)"
    )


def test_growth_from_2007_to_2024_is_at_least_10x() -> None:
    """National total grew from ~10 GW to ~144 GW = 14x. Sanity: sum
    across states in 2024 must be at least 10x the 2007 sum."""
    rows = _q(
        f"SELECT period_label, SUM(value_numeric) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{INDICATOR_ID}' AND period_label IN ('2007-04', '2024-04') "
        f"GROUP BY period_label ORDER BY period_label"
    )
    totals = dict(rows)
    assert totals["2024-04"] >= 10 * totals["2007-04"], (
        f"RE growth 2007 -> 2024: {totals['2007-04']} -> {totals['2024-04']} "
        f"= {totals['2024-04']/totals['2007-04']:.1f}x; expected >= 10x"
    )


def test_does_not_displace_existing_capacity_indicators() -> None:
    """PR-Y joining energy_installed_capacity must NOT have evicted
    prior PR-S thermal-retired or PR-R rooftop-solar rows."""
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = 'state-rooftop-solar-capacity-mw'"
    )
    assert rows[0][0] >= 300, (
        f"PR-R rooftop-solar rows = {rows[0][0]}; PR-Y must not displace prior indicators"
    )
