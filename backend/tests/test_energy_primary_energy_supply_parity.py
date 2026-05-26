"""Parity oracle for the india-primary-energy-supply-mtoe canonical lift (PR-U).

ICED ``/analytics/state-wise-deep-dive`` (primary-energy-supply national
series) -> 140 raw meadow obs rows joined into
``energy_fuel_consumption.parquet``. After filtering 20 publisher ``total``
rows (compute-on-read parent semantics) and mapping publisher
``renewables`` (plural) -> canonical ``renewable`` (singular), the lift
emits 120 obs rows: 20 fiscal years x 6 child fuel indicators.

Pattern A-facet on the EXISTING ``fuel_type`` axis (extended with `oil`
+ `renewable` value_ids in this PR). National-only -- ICED does NOT
publish state-level TPES; every row has entity_id="IN".

These tests are skipped at collection time when the parquet is absent
(clean checkout pre-lift). They MUST be re-run after every
``python -m yen_gov lift-energy`` invocation that touches
``energy_fuel_consumption.parquet``.

Mirror of the structure used by ``test_energy_oil_product_consumption_parity.py``.
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
    / "national_primary_energy_supply_mtoe.json"
)

pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason=(
        "energy_fuel_consumption.parquet not built yet; run "
        "`python -m yen_gov lift-energy` first."
    ),
)

EXPECTED_SOURCE_ID = "src-170d3536d908"
PARENT_ID = "india-primary-energy-supply-mtoe"
EXPECTED_CANONICAL_FUELS = {"coal", "oil", "gas", "hydro", "nuclear", "renewable"}
EXPECTED_CHILD_IDS = {f"{PARENT_ID}-{f}" for f in EXPECTED_CANONICAL_FUELS}


def _q(sql: str) -> list[tuple]:
    return duckdb.connect(":memory:").execute(sql).fetchall()


def test_row_count_120_after_total_filter():
    """Raw meadow = 140 rows (20 FYs x 7 publisher facets); lift filters
    the 20 ``total`` rows as compute-on-read parent semantics, leaving
    120 = 20 FYs x 6 fuel children.

    A regression here means either (a) the lift dropped real rows, (b)
    the ``total`` filter accidentally caught a non-total facet, or (c)
    the publisher reissued the series with a different shape.
    """
    meadow_rows = json.loads(MEADOW.read_text())["rows"]
    assert len(meadow_rows) == 140
    n_total = sum(1 for r in meadow_rows if r["facet"] == "total")
    assert n_total == 20  # one total per FY
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert rows[0][0] == 120


def test_six_child_indicator_ids():
    """Exactly 6 canonical child indicator_ids on the fuel_type axis:
    coal + oil + gas + hydro + nuclear + renewable. Locks down the
    publisher-to-canonical mapping (``renewables`` -> ``renewable``).
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
    """Parent ``india-primary-energy-supply-mtoe`` is compute-on-read: it
    carries zero observation rows; the 6 children own the values. The
    parent row is for catalogue + facet wiring only (frontend sums the
    6 children at query time via allow_compute_on_read_total=True on
    the fuel_type axis).
    """
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{PARENT_ID}'"
    )
    assert rows[0][0] == 0


def test_publisher_renewables_plural_collapsed_to_renewable_singular():
    """Publisher emits ``renewables`` (plural aggregate); canonical
    axis value is ``renewable`` (singular per indicator-naming.md). A
    regression here = publisher relabel OR adapter mapping drift.

    Crucially, there must be NO ``india-primary-energy-supply-mtoe-renewables``
    (plural) indicator_id in the parquet.
    """
    indicator_ids = {
        row[0]
        for row in _q(
            f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '{PARENT_ID}%'"
        )
    }
    assert f"{PARENT_ID}-renewable" in indicator_ids
    assert f"{PARENT_ID}-renewables" not in indicator_ids


def test_all_rows_carry_expected_source_id():
    """Every primary-energy-supply row must carry source_id=src-170d3536d908
    (the ICED 2024-25 primary-energy-supply citation). FK closure is
    enforced separately; this test catches drift if a future edit rebrands.
    """
    rows = _q(
        f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert len(rows) == 1
    assert rows[0][0] == EXPECTED_SOURCE_ID


def test_all_rows_have_derivation_raw():
    """No row should be 'sum' / 'imputed' / 'computed'. Each (FY, fuel)
    row is a single publisher observation (passthrough, no aggregation).
    The compute-on-read parent total is NOT materialised here.
    """
    rows = _q(
        f"SELECT DISTINCT derivation FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert len(rows) == 1
    assert rows[0][0] == "raw"


def test_entity_vocabulary_is_national_only():
    """ICED does NOT publish state-level TPES; every row arrives with
    entity_id="IN" (bare national code, NOT IN-S* / IN-U*). Locks the
    national-only invariant.
    """
    rows = _q(
        f"SELECT DISTINCT entity_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    entity_ids = {r[0] for r in rows}
    assert entity_ids == {"IN"}, (
        f"PR-U is national-only; expected entity vocab {{'IN'}}, "
        f"got {sorted(entity_ids)!r}. State/UT rows here = ICED schema drift."
    )


def test_time_vocabulary_is_fiscal_year_2005_to_2024():
    """All period_labels are 'YYYY-04' (fiscal-year-start sentinel) in
    range 2005-04..2024-04 (20 distinct fiscal years).
    """
    rows = _q(
        f"SELECT DISTINCT period_label FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%' ORDER BY 1"
    )
    labels = [r[0] for r in rows]
    assert len(labels) == 20
    assert labels[0] == "2005-04"
    assert labels[-1] == "2024-04"
    for label in labels:
        assert label.endswith("-04"), f"non-fiscal-year period_label {label!r}"


def test_coal_is_largest_bucket_in_latest_year():
    """Coal has dominated India's TPES since the early 2000s (~55% in
    recent years). Anchor: FY 2024-04 coal > {oil, gas, hydro, nuclear,
    renewable}. A regression where any other fuel exceeds coal = publisher
    unit drift OR adapter mis-mapping (e.g. renewables -> coal).
    """
    rows = _q(
        "SELECT indicator_id, value_numeric "
        f"FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}-%' AND period_label = '2024-04' "
        "ORDER BY value_numeric DESC"
    )
    assert rows[0][0] == f"{PARENT_ID}-coal", (
        f"expected coal as #1 in FY2024-04, got {rows[0][0]!r}"
    )
    # Sanity: coal must dwarf nuclear at least 10x (publisher physics
    # check; if nuclear approaches coal in mtoe terms, mapping is wrong).
    by_id = {r[0]: r[1] for r in rows}
    assert by_id[f"{PARENT_ID}-coal"] > 10 * by_id[f"{PARENT_ID}-nuclear"]


def test_fy2005_anchor_gas_value():
    """First-year anchor: FY 2005-04 gas TPES = 38.35 mtoe per the
    publisher's meadow snapshot (vintage 2024-25). Locks the unit
    (mtoe vs kgoe vs tonnes) and the first-row passthrough fidelity.
    """
    rows = _q(
        "SELECT value_numeric "
        f"FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{PARENT_ID}-gas' AND period_label = '2005-04'"
    )
    assert len(rows) == 1
    assert abs(rows[0][0] - 38.35) < 0.01, (
        f"FY2005-04 gas = {rows[0][0]}; expected 38.35 mtoe. "
        f"Unit drift or first-row passthrough regression."
    )
