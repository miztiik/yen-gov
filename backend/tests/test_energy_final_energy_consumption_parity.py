"""Parity oracle for the india-final-energy-consumption-mtoe canonical lift (PR-X).

ICED ``/analytics/state-wise-deep-dive`` (final-energy-consumption
national series) -> 360 raw meadow obs rows joined into
``energy_demand_supply.parquet``. Pattern A-facet on the NEW
``sector_fuel_pair`` axis with 18 sparse value_ids (publisher emits
18 of the 30 possible sector x fuel pairs; absent cells are NOT
imputed as zero).

Adapter: ``_publisher_sector_fuel_to_canonical`` in ``demand_supply.py``
sanitises publisher "agriculture | oil" -> canonical pair-id
"agriculture-oil"; ``_FINAL_ENERGY_EXPECTED_PAIRS`` frozenset gates
against schema drift.
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
    / "national_final_energy_consumption_by_sector_mtoe.json"
)

pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason="energy_demand_supply.parquet not built; run `python -m yen_gov lift-energy`",
)

EXPECTED_SOURCE_ID = "src-29ecbb6dce9d"
PARENT_ID = "india-final-energy-consumption-mtoe"
EXPECTED_CHILD_IDS = {
    f"{PARENT_ID}-{p}" for p in (
        "agriculture-electricity", "agriculture-gas", "agriculture-oil",
        "cgd-and-others-gas",
        "commercial-electricity", "commercial-oil",
        "industry-coal", "industry-electricity", "industry-gas", "industry-oil",
        "non-energy-gas", "non-energy-oil",
        "other-electricity", "other-oil",
        "residential-electricity", "residential-oil",
        "transport-electricity", "transport-oil",
    )
}


def _q(sql: str) -> list[tuple]:
    return duckdb.connect(":memory:").execute(sql).fetchall()


def test_row_count_matches_meadow() -> None:
    """360 obs = passthrough; no aggregation; no filter."""
    meadow_rows = json.loads(MEADOW.read_text(encoding="utf-8"))["rows"]
    assert len(meadow_rows) == 360
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert rows[0][0] == 360


def test_eighteen_sparse_child_indicator_ids() -> None:
    """Exactly 18 sparse (sector x fuel) pairs -- NOT 30 (6 sectors x
    5 fuels = full Cartesian). The 12 absent pairs (residential coal,
    transport gas, etc.) must NOT be fabricated."""
    indicator_ids = {
        row[0]
        for row in _q(
            f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '{PARENT_ID}%'"
        )
    }
    assert indicator_ids == EXPECTED_CHILD_IDS


def test_parent_has_zero_rows() -> None:
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{PARENT_ID}'"
    )
    assert rows[0][0] == 0


def test_publisher_compound_facet_sanitised() -> None:
    """Publisher emits 'agriculture | oil' (pipe-separated); canonical
    suffix is 'agriculture-oil' (kebab). No raw pipe-separated label
    should leak into indicator_id."""
    indicator_ids = {
        row[0]
        for row in _q(
            f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '{PARENT_ID}%'"
        )
    }
    for ind in indicator_ids:
        assert " | " not in ind, f"raw pipe leaked into {ind!r}"
        assert " " not in ind, f"raw space leaked into {ind!r}"


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


def test_entity_vocabulary_is_national_only() -> None:
    """ICED does NOT publish state-level final-energy consumption; every
    row arrives with entity_id='IN' (bare national code)."""
    rows = _q(
        f"SELECT DISTINCT entity_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    entity_ids = {r[0] for r in rows}
    assert entity_ids == {"IN"}


def test_time_vocabulary_is_fiscal_year_2005_to_2024() -> None:
    """All period_labels are 'YYYY-04' in range 2005-04..2024-04 (20 FYs)."""
    rows = _q(
        f"SELECT DISTINCT period_label FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%' ORDER BY 1"
    )
    labels = [r[0] for r in rows]
    assert labels[0] == "2005-04"
    assert labels[-1] == "2024-04"
    assert len(labels) == 20


def test_industry_oil_is_meaningful_anchor_fy2023() -> None:
    """Sanity: FY2023-04 industry-oil > 10 mtoe (a meaningful chunk;
    industrial fuel-oil + diesel for cement/steel). Observed ~20.9 mtoe
    at the publisher's 2024-25 vintage."""
    rows = _q(
        f"SELECT value_numeric FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{PARENT_ID}-industry-oil' "
        f"  AND period_label = '2023-04'"
    )
    assert len(rows) == 1
    assert rows[0][0] > 10.0, f"industry-oil FY2023-04 = {rows[0][0]}; expected > 10 mtoe"


def test_absent_pairs_are_not_fabricated() -> None:
    """The 12 absent (sector, fuel) pairs from the 6x5 Cartesian must
    NOT appear as indicator_ids. Spot-check the most obvious absences:
    residential-coal, transport-gas, agriculture-coal."""
    indicator_ids = {
        row[0]
        for row in _q(
            f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '{PARENT_ID}%'"
        )
    }
    for absent in (
        f"{PARENT_ID}-residential-coal",
        f"{PARENT_ID}-transport-gas",
        f"{PARENT_ID}-agriculture-coal",
        f"{PARENT_ID}-non-energy-coal",
    ):
        assert absent not in indicator_ids, (
            f"absent pair {absent!r} was fabricated -- adapter must not "
            f"impute pairs the publisher does not emit"
        )
