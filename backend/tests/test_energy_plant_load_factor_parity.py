"""Parity oracle for the state-plant-load-factor-pct canonical lift (PR-V).

ICED ``/v1/plf-metatable-data`` (state-wise PLF percentage by fuel) ->
1652 raw meadow obs rows joined into ``energy_generation.parquet``.
Pattern A-facet on the EXISTING ``fuel_type`` axis with NO sub-fuel
collapse (PLF is a percentage that cannot be summed across fuels).

8 publisher fuel labels map 1:1 to existing fuel_type axis values via
the dedicated ``_PLF_PUBLISHER_TO_CANONICAL_FUEL`` dict in
``generation.py``:

  bio-power   -> biomass
  coal        -> coal
  hydro       -> hydro
  nuclear     -> nuclear
  oil-gas     -> gas
  small-hydro -> small-hydro  (kebab indicator-id suffix; dim val is snake `small_hydro`)
  solar       -> solar
  wind        -> wind

These tests are skipped at collection time when the parquet is absent
(clean checkout pre-lift). They MUST be re-run after every
``python -m yen_gov lift-energy`` invocation.

Mirror of the structure used by ``test_energy_primary_energy_supply_parity.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PARQUET = REPO_ROOT / "datasets" / "energy" / "energy_generation.parquet"
MEADOW = (
    REPO_ROOT
    / "datasets"
    / "energy"
    / "_meadow"
    / "iced"
    / "2024-25"
    / "state_plant_load_factor_pct.json"
)

pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason=(
        "energy_generation.parquet not built yet; run "
        "`python -m yen_gov lift-energy` first."
    ),
)

EXPECTED_SOURCE_ID = "src-7eb929cbf2d8"
PARENT_ID = "state-plant-load-factor-pct"
EXPECTED_CHILD_IDS = {
    f"{PARENT_ID}-biomass",
    f"{PARENT_ID}-coal",
    f"{PARENT_ID}-gas",
    f"{PARENT_ID}-hydro",
    f"{PARENT_ID}-nuclear",
    f"{PARENT_ID}-small-hydro",
    f"{PARENT_ID}-solar",
    f"{PARENT_ID}-wind",
}


def _q(sql: str) -> list[tuple]:
    return duckdb.connect(":memory:").execute(sql).fetchall()


def test_row_count_matches_meadow():
    """1652 obs rows = passthrough from the publisher (no aggregation, no
    filter at adapter time). If this drifts, either (a) the publisher
    reissued the series, or (b) the adapter dropped rows on an unmapped
    facet (which today would NEVER happen -- all 8 publisher labels are
    in _PLF_PUBLISHER_TO_CANONICAL_FUEL).
    """
    meadow_rows = json.loads(MEADOW.read_text(encoding="utf-8"))["rows"]
    assert len(meadow_rows) == 1652
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert rows[0][0] == 1652


def test_eight_child_indicator_ids():
    """Exactly 8 canonical child indicator_ids on the fuel_type axis.
    Locks the 1:1 publisher-to-canonical mapping. A regression here
    means publisher relabel OR adapter mapping drift (e.g. accidental
    SUB_FUEL_TO_CANONICAL collapse would shrink this to 5).
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
    """Parent ``state-plant-load-factor-pct`` is compute-on-read (catalogue
    + facet-picker only). PLF values across fuels cannot be summed
    meaningfully (% summation is nonsense), so the FacetPicker primitive
    only surfaces the 8 children as individual series; the catalogue
    parent carries 0 obs rows.
    """
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = '{PARENT_ID}'"
    )
    assert rows[0][0] == 0


def test_publisher_bio_power_collapsed_to_biomass():
    """Publisher emits ``bio-power``; canonical axis value is ``biomass``
    per facet_axes_seed.py. A regression here = publisher relabel OR
    adapter mapping drift.

    Crucially, there must be NO ``state-plant-load-factor-pct-bio-power``
    indicator_id in the parquet.
    """
    indicator_ids = {
        row[0]
        for row in _q(
            f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '{PARENT_ID}%'"
        )
    }
    assert f"{PARENT_ID}-biomass" in indicator_ids
    assert f"{PARENT_ID}-bio-power" not in indicator_ids


def test_publisher_oil_gas_collapsed_to_gas():
    """Publisher emits ``oil-gas`` (single bucket combining natural gas +
    diesel + furnace oil per ICED labelling); canonical axis value is
    ``gas`` (the SUB_FUEL_TO_CANONICAL convention).
    """
    indicator_ids = {
        row[0]
        for row in _q(
            f"SELECT DISTINCT indicator_id FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '{PARENT_ID}%'"
        )
    }
    assert f"{PARENT_ID}-gas" in indicator_ids
    assert f"{PARENT_ID}-oil-gas" not in indicator_ids


def test_all_rows_carry_expected_source_id():
    """Every PLF row must carry source_id=src-7eb929cbf2d8 (the ICED
    2024-25 PLF citation). FK closure is enforced separately; this test
    catches drift if a future edit rebrands.
    """
    rows = _q(
        f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert len(rows) == 1
    assert rows[0][0] == EXPECTED_SOURCE_ID


def test_all_rows_have_derivation_raw():
    """Pure passthrough: every (state, FY, fuel) row is one publisher
    observation. No 'sum' / 'imputed' / 'computed' allowed.
    """
    rows = _q(
        f"SELECT DISTINCT derivation FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert len(rows) == 1
    assert rows[0][0] == "raw"


def test_entity_vocabulary_is_state_or_ut_only():
    """All entities are IN-S* (state) or IN-U* (union territory) ISO-style
    codes. Plant Load Factor is a state-grain metric; the publisher does
    NOT emit an 'IN' national rollup row for PLF (you cannot sensibly
    aggregate per-state PLF without capacity weights).
    """
    rows = _q(
        f"SELECT DISTINCT entity_id FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    entity_ids = {r[0] for r in rows}
    assert "IN" not in entity_ids, "PLF should NOT carry a national IN rollup"
    for eid in entity_ids:
        assert eid.startswith(("IN-S", "IN-U")), f"non-state/UT entity_id {eid!r}"


def test_time_vocabulary_is_fiscal_year_2015_to_2025():
    """All period_labels are 'YYYY-04' (fiscal-year-start sentinel) in
    range 2015-04..2025-04 (publisher snapshot covers FY16 to FY26).
    """
    rows = _q(
        f"SELECT DISTINCT period_label FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%' ORDER BY 1"
    )
    labels = [r[0] for r in rows]
    assert labels[0] == "2015-04"
    assert labels[-1] == "2025-04"
    for label in labels:
        assert label.endswith("-04"), f"non-fiscal-year period_label {label!r}"


def test_36_distinct_states_or_uts():
    """All 28 states + 8 UTs (or close to it). Each state need not have
    all 8 fuels (e.g. nuclear PLF only exists in states hosting reactors).
    """
    rows = _q(
        f"SELECT COUNT(DISTINCT entity_id) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id LIKE '{PARENT_ID}%'"
    )
    assert rows[0][0] == 36


def test_does_not_displace_existing_generation_indicators():
    """PLF joining the energy_generation parquet must NOT have evicted
    the prior electricity-generation-gwh rows.
    """
    rows = _q(
        f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
        f"WHERE indicator_id = 'electricity-generation-gwh'"
    )
    # The publisher's generation MU shard was 407 totals; PR-V must
    # leave these untouched.
    assert rows[0][0] >= 400, (
        f"prior electricity-generation-gwh rows count = {rows[0][0]!r}; "
        f"PR-V must not have displaced PR pre-existing generation rows."
    )
