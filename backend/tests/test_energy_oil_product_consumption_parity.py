"""Parity oracle for the state-oil-product-consumption-kt canonical lift (PR-T).

ICED ``/energy/fuel-sources/oil/consumptionStateProductTrend`` -> 2901 obs rows
(36 states x ~15 fiscal years x ~7 products) joined into
``energy_fuel_consumption.parquet``. Pattern A-facet on the NEW ``oil_product``
axis: 1:1 publisher-to-canonical mapping (no SUB_FUEL_TO_CANONICAL collapse),
7 children.

These tests are skipped at collection time when the parquet is absent (clean
checkout pre-lift). They MUST be re-run after every ``python -m yen_gov
lift-energy`` invocation that touches ``energy_fuel_consumption.parquet``.

Mirror of the structure used by ``test_energy_thermal_retired_parity.py``.
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
    / "state_oil_product_consumption_kt.json"
)

pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason=(
        "energy_fuel_consumption.parquet not built yet; run "
        "`python -m yen_gov lift-energy` first."
    ),
)

EXPECTED_SOURCE_ID = "src-cba8334fedc5"
PARENT_ID = "state-oil-product-consumption-kt"
EXPECTED_FACETS = {
    "diesel-hsd",
    "petrol",
    "lpg",
    "kerosene",
    "naphtha",
    "petroleum-coke",
    "others",
}
EXPECTED_CHILD_IDS = {f"{PARENT_ID}-{f}" for f in EXPECTED_FACETS}


def _q(sql: str) -> list[tuple]:
    return duckdb.connect(":memory:").execute(sql).fetchall()


def test_row_count_matches_meadow():
    """2901 obs rows = sum across 36 states x ~15 FYs x ~7 products.

    Locks in the publisher's snapshot at vintage 2024-25. A regression here
    means either (a) the lift dropped rows, (b) the publisher reissued the
    series, or (c) the 'OTHERS state bucket' / 'IN aggregate' drop logic
    accidentally skipped real rows.
    """
    meadow_rows = json.loads(MEADOW.read_text())["rows"]
    assert len(meadow_rows) == 2901
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert rows[0][0] == 2901


def test_seven_child_indicator_ids():
    """Exactly 7 canonical child indicator_ids (one per oil product).

    The publisher's product vocabulary is 1:1 with the canonical
    ``oil_product`` axis -- no collapse step (unlike fuel_type's
    SUB_FUEL_TO_CANONICAL for coal/oil-gas). A regression here means a
    publisher product was added/renamed/dropped.
    """
    indicator_ids = {
        row[0]
        for row in _q(
            f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '{PARENT_ID}%'"
        )
    }
    assert indicator_ids == EXPECTED_CHILD_IDS


def test_parent_has_zero_rows():
    """Parent ``state-oil-product-consumption-kt`` is compute-on-read: it
    carries zero observation rows; the 7 children own the values. The
    parent row is for catalogue + facet wiring only.
    """
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{PARENT_ID}'"
    )
    assert rows[0][0] == 0


def test_diesel_dominates_petrol_nationally():
    """Diesel-HSD is the largest single product by consumption (transport
    + agriculture). Petrol is #2. A regression where petrol > diesel for
    any large state in any recent year = publisher unit/label drift.

    Test a specific high-volume anchor: Tamil Nadu (IN-S22), FY 2023-04.
    """
    rows = _q(
        "SELECT indicator_id, value_numeric "
        f"FROM read_parquet('{PARQUET.as_posix()}') "
        "WHERE entity_id = 'IN-S22' AND period_label = '2023-04' "
        f"  AND indicator_id IN ('{PARENT_ID}-diesel-hsd', '{PARENT_ID}-petrol') "
        "ORDER BY indicator_id"
    )
    by_id = {r[0]: r[1] for r in rows}
    assert by_id[f"{PARENT_ID}-diesel-hsd"] > by_id[f"{PARENT_ID}-petrol"]


def test_all_rows_carry_expected_source_id():
    """Every oil-product row must carry source_id=src-cba8334fedc5
    (the ICED 2024-25 oil-consumption citation). FK closure is enforced
    separately; this test catches drift if a future edit rebrands.
    """
    rows = _q(
        f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert len(rows) == 1
    assert rows[0][0] == EXPECTED_SOURCE_ID


def test_all_rows_have_derivation_raw():
    """No row should be 'sum' / 'imputed' / 'computed'. Each (state, FY,
    product) row is a single publisher observation (passthrough, no
    aggregation). Future "rollup-into-parent" logic would create rows
    with derivation='sum'; this test guards against that.
    """
    rows = _q(
        f"SELECT DISTINCT derivation FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert len(rows) == 1
    assert rows[0][0] == "raw"


def test_entity_vocabulary_is_state_or_ut_only():
    """All entities are IN-S* (state) or IN-U* (union territory) ISO-style
    codes. National 'IN' rollups should have been dropped at adapter time
    (the publisher emits an 'IN' aggregate row that we filter out).
    """
    rows = _q(
        f"SELECT DISTINCT entity_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    entity_ids = {r[0] for r in rows}
    # Pure 'IN' national aggregate row would be a bare 'IN' code (not 'IN-S*' or 'IN-U*').
    assert "IN" not in entity_ids, "national aggregate row should have been dropped"
    for eid in entity_ids:
        assert eid.startswith(("IN-S", "IN-U")), f"non-state/UT entity_id {eid!r}"


def test_time_vocabulary_is_fiscal_year_only():
    """All period_labels are 'YYYY-04' (fiscal-year-start sentinel) in
    range 2010-04..2024-04. Inventory deriver requires homogeneous time
    vocab per indicator.
    """
    rows = _q(
        f"SELECT DISTINCT period_label FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    for row in rows:
        label = row[0]
        assert label.endswith("-04"), f"non-fiscal-year period_label {label!r}"
        year = int(label.split("-")[0])
        assert 2010 <= year <= 2024


def test_36_distinct_states():
    """India + UTs == 28 states + 8 UTs = 36. Less = publisher gap or
    adapter mis-filter (e.g. dropped 'OTHERS' too aggressively).
    """
    rows = _q(
        f"SELECT COUNT(DISTINCT entity_id) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert rows[0][0] == 36


def test_does_not_displace_other_indicators():
    """Oil-product joining the energy_fuel_consumption parquet must NOT
    have evicted the prior block 1 coal-consumption rows (PR-Q).
    """
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = 'state-coal-consumption-mt'"
    )
    # PR-Q lifted 450 coal-consumption rows; they must persist post-PR-T.
    assert rows[0][0] >= 400
