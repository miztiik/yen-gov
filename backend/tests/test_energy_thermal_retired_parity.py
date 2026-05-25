"""Parity oracle for the india-thermal-capacity-retired-mw canonical lift (PR-S).

ICED ``/v1/retired-capacity-plants`` -> 29 obs rows (national-only, FY05-FY25)
joined into the existing ``energy_installed_capacity`` parquet stem. First
Pattern A-facet indicator in the P.1.C cohort: publisher emits 2 facets
("coal" + "oil-gas") and SUB_FUEL_TO_CANONICAL collapses "oil-gas" -> "gas"
per Hans D33.8 (the 5-bucket fuel_type axis).

These tests are skipped at collection time when the parquet is absent (clean
checkout pre-lift). They MUST be re-run after every ``python -m yen_gov
lift-energy`` invocation that touches ``energy_installed_capacity.parquet``.

Mirror of the structure used by ``test_energy_rooftop_solar_parity.py``.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PARQUET = REPO_ROOT / "datasets" / "energy" / "energy_installed_capacity.parquet"
MEADOW = (
    REPO_ROOT
    / "datasets"
    / "energy"
    / "_meadow"
    / "iced"
    / "2024-25"
    / "india_thermal_capacity_retired_mw.json"
)

pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason=(
        "energy_installed_capacity.parquet not built yet; run "
        "`python -m yen_gov lift-energy` first."
    ),
)

EXPECTED_SOURCE_ID = "src-fd152bd3c6c6"
PARENT_ID = "india-thermal-capacity-retired-mw"
COAL_ID = "india-thermal-capacity-retired-mw-coal"
GAS_ID = "india-thermal-capacity-retired-mw-gas"


def _q(sql: str) -> list[tuple]:
    return duckdb.connect(":memory:").execute(sql).fetchall()


def test_row_count_matches_meadow():
    """29 obs rows = 20 coal years + 9 oil-gas (collapsed to gas) years.

    Locks in the publisher's snapshot at vintage 2024-25. A regression here
    means either (a) the lift dropped rows, (b) the publisher reissued the
    series at a different cadence, or (c) the SUB_FUEL_TO_CANONICAL collapse
    accidentally summed coal + gas into a single bucket.
    """
    meadow_rows = json.loads(MEADOW.read_text())["rows"]
    assert len(meadow_rows) == 29
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert rows[0][0] == 29
    # Counter on raw facet labels: publisher = {coal: 20, oil-gas: 9}.
    raw = Counter(r["facet"] for r in meadow_rows)
    assert raw == {"coal": 20, "oil-gas": 9}


def test_facet_buckets_are_coal_and_gas_only():
    """Publisher emits 2 facets; canonical collapses 'oil-gas' -> 'gas'.

    No 'oil-gas' bucket should appear in the parquet -- the collapse must
    have eliminated it. The raw publisher label leaking through would mean
    SUB_FUEL_TO_CANONICAL did not fire for this shard.
    """
    indicator_ids = {
        row[0]
        for row in _q(
            f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '{PARENT_ID}%'"
        )
    }
    assert indicator_ids == {COAL_ID, GAS_ID}
    # Explicitly forbid the raw publisher label.
    assert f"{PARENT_ID}-oil-gas" not in indicator_ids
    assert f"{PARENT_ID}-oil_gas" not in indicator_ids


def test_coal_2005_04_anchor_value():
    """Coal series first year (FY2005-06): 399.5 MW retired (publisher truth)."""
    rows = _q(
        f"SELECT value_numeric FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{COAL_ID}' AND period_label = '2005-04'"
    )
    assert len(rows) == 1
    assert rows[0][0] == pytest.approx(399.5)


def test_coal_year_count_is_20():
    """Coal retirements are recorded every fiscal year 2005-04..2025-04
    EXCEPT 2024-04 (publisher gap). That's 20 distinct fiscal years.
    """
    rows = _q(
        f"SELECT COUNT(DISTINCT period_label) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{COAL_ID}'"
    )
    assert rows[0][0] == 20


def test_gas_year_count_is_9():
    """Gas (collapsed from 'oil-gas') is sporadic: 9 fiscal years between
    2010-04 and 2024-04. Diesel/oil-fired peaking plant retirements are
    infrequent compared to coal fleet rotation.
    """
    rows = _q(
        f"SELECT COUNT(DISTINCT period_label) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{GAS_ID}'"
    )
    assert rows[0][0] == 9


def test_all_rows_carry_expected_source_id():
    """Every thermal-retired row must carry source_id=src-fd152bd3c6c6
    (the ICED 2024-25 retired-capacity citation). FK closure is enforced
    by test_energy_sources_fk_closure.py; this test catches drift if a
    future edit accidentally rebrands the source.
    """
    rows = _q(
        f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert len(rows) == 1
    assert rows[0][0] == EXPECTED_SOURCE_ID


def test_all_rows_have_derivation_raw():
    """No row should be 'sum' / 'imputed' / 'computed'. The publisher emits
    a single value per (year, fuel), so collapse is a no-op for these rows
    (coal stays coal; oil-gas renames to gas without any addition).
    """
    rows = _q(
        f"SELECT DISTINCT derivation FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert len(rows) == 1
    assert rows[0][0] == "raw"


def test_entity_ids_are_in_only():
    """National-only series. State-level retired-capacity is NOT published
    by ICED. A 'TN' or 'GJ' row appearing here = mis-rolled data.
    """
    rows = _q(
        f"SELECT DISTINCT entity_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert len(rows) == 1
    assert rows[0][0] == "IN"


def test_time_vocabulary_is_fiscal_year_only():
    """All period_labels look like 'YYYY-04' (fiscal-year-start sentinel).
    Mixing 'year' shapes (YYYY) or 'year_month' shapes other than -04 would
    trip the inventory deriver's homogeneous-time-vocabulary contract.
    """
    rows = _q(
        f"SELECT DISTINCT period_label FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    for row in rows:
        label = row[0]
        assert label.endswith("-04"), f"non-fiscal-year period_label {label!r}"
        year = int(label.split("-")[0])
        assert 2005 <= year <= 2025


def test_does_not_displace_other_indicators():
    """Thermal-retired joining the energy_installed_capacity parquet must
    NOT have evicted any pre-existing indicator (block 1-6 rows should
    still be present). Sanity check that the partition write is additive.
    """
    rows = _q(
        f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id NOT LIKE '{PARENT_ID}%' "
        f"ORDER BY indicator_id LIMIT 5"
    )
    indicator_ids = {row[0] for row in rows}
    # At least one block 1-6 indicator should remain (e.g. rooftop solar,
    # state-installed-capacity-allocated-mw, or one of the per-fuel children).
    assert len(indicator_ids) >= 1
