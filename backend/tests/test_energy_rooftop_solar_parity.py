"""Parity oracle for rooftop solar capacity rows in energy_installed_capacity.parquet.

P.1.C PR-R -- rooftop solar capacity (MW, state x fiscal-year), raw lift
from ICED ``/energy/renewable/solar/rooftop/state``.

Rooftop solar joins the existing ``energy_installed_capacity`` parquet
stem (not a new stem) because it is a sub-fuel measurement of installed
MW. The parquet already holds 5 CEA per-fuel snapshot indicators, plus
the ICED geographical / allocated families; rooftop adds one more
indicator_id (``state-rooftop-solar-capacity-mw``) with 321 rows.

Holy Law #7: real Parquet + real shards, no mocks.
"""

from __future__ import annotations

import json
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
    / "state_rooftop_solar_capacity_mw.json"
)

# Citation ledger row for the ICED rooftop-solar endpoint
# (derive_source_id("NITI Aayog India Climate & Energy Dashboard",
#  "Rooftop Solar Capacity (MW) State-wise API ...", "2024-25"))
EXPECTED_SOURCE_ID = "src-018bb42f9519"
INDICATOR_ID = "state-rooftop-solar-capacity-mw"


pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason=(
        "datasets/energy/energy_installed_capacity.parquet not on disk; "
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


def test_rooftop_solar_national_aggregate_2017() -> None:
    """First-year IN national rollup: FY 2017-04 = 1063.63 MW (raw, ICED)."""
    val = _query_value("IN", 2017, INDICATOR_ID)
    assert val == pytest.approx(1063.63, abs=0.01), (
        f"IN 2017 {INDICATOR_ID} expected 1063.63, got {val!r}"
    )


def test_rooftop_solar_national_aggregate_2025() -> None:
    """Latest IN national rollup: FY 2025-04 = 25727.65 MW (~25.7 GW)."""
    val = _query_value("IN", 2025, INDICATOR_ID)
    assert val == pytest.approx(25727.65, abs=0.01), (
        f"IN 2025 {INDICATOR_ID} expected 25727.65, got {val!r}"
    )


def test_rooftop_solar_top_state_s06_2025() -> None:
    """S06 (Gujarat) FY 2025-04 = 6881.8 MW -- the top-rooftop state-year
    in the shard, reflecting the SURYA Gujarat residential push + a
    decade of state co-funding."""
    val = _query_value("IN-S06", 2025, INDICATOR_ID)
    assert val == pytest.approx(6881.8, abs=0.01), (
        f"IN-S06 2025 {INDICATOR_ID} expected 6881.8, got {val!r}"
    )


def test_rooftop_solar_row_count_matches_meadow() -> None:
    """Lift is 1:1 with meadow rows (no aggregation, no facet drop)
    for ``state-rooftop-solar-capacity-mw``: 321 rows expected."""
    con = duckdb.connect(":memory:")
    try:
        n = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id = ?",
            [INDICATOR_ID],
        ).fetchone()[0]
    finally:
        con.close()
    meadow_rows = json.loads(MEADOW.read_text(encoding="utf-8"))["rows"]
    assert n == len(meadow_rows) == 321, (
        f"row count drift: parquet={n}, meadow={len(meadow_rows)}, expected 321"
    )


def test_all_rooftop_rows_carry_source_id() -> None:
    """source_id FK closure: every rooftop-solar row carries the ICED
    citation ledger row's source_id (src-018bb42f9519)."""
    con = duckdb.connect(":memory:")
    try:
        source_ids = {
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT source_id FROM read_parquet('{PARQUET.as_posix()}') "
                f"WHERE indicator_id = ?",
                [INDICATOR_ID],
            ).fetchall()
        }
    finally:
        con.close()
    assert source_ids == {EXPECTED_SOURCE_ID}, (
        f"source_id drift: {source_ids!r}, expected {{{EXPECTED_SOURCE_ID!r}}}"
    )


def test_all_rooftop_rows_have_derivation_raw() -> None:
    """Lift is a 1:1 raw read; no derivation/imputation by the adapter."""
    con = duckdb.connect(":memory:")
    try:
        derivations = {
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT derivation FROM read_parquet('{PARQUET.as_posix()}') "
                f"WHERE indicator_id = ?",
                [INDICATOR_ID],
            ).fetchall()
        }
    finally:
        con.close()
    assert derivations == {"raw"}, (
        f"derivation drift: {derivations!r}, expected {{'raw'}}"
    )


def test_rooftop_time_vocabulary_is_fiscal_year_only() -> None:
    """ADR-0041 nn4 + inventory deriver homogeneity rule: every row
    on one indicator must share one time-shape. period_label must
    match YYYY-04 (fiscal-year shape)."""
    con = duckdb.connect(":memory:")
    try:
        labels = [
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT period_label FROM read_parquet('{PARQUET.as_posix()}') "
                f"WHERE indicator_id = ?",
                [INDICATOR_ID],
            ).fetchall()
        ]
    finally:
        con.close()
    for lbl in labels:
        assert lbl.endswith("-04") and len(lbl) == 7, (
            f"period_label {lbl!r} violates fiscal-year shape YYYY-04"
        )
    # Coverage spans the ICED vintage (FY 2017-04 ... FY 2025-04).
    assert "2017-04" in labels
    assert "2025-04" in labels


def test_rooftop_entity_ids_are_in_prefix_normalised() -> None:
    """to_entity_id() must prepend ``IN-`` to every state code; the
    raw S01..U09 meadow forms are NOT allowed in the canonical parquet.
    The IN national-aggregate entity_id is exempt (already canonical)."""
    con = duckdb.connect(":memory:")
    try:
        entity_ids = [
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT entity_id FROM read_parquet('{PARQUET.as_posix()}') "
                f"WHERE indicator_id = ?",
                [INDICATOR_ID],
            ).fetchall()
        ]
    finally:
        con.close()
    for eid in entity_ids:
        if eid == "IN":
            continue
        assert eid.startswith("IN-"), (
            f"entity_id {eid!r} missing IN- prefix; "
            f"to_entity_id() did not normalise correctly"
        )


def test_rooftop_does_not_displace_other_indicators() -> None:
    """The PR-R addition extends the parquet by 321 rows; the existing
    5 indicators (CEA snapshot per fuel x 5) plus the 3 ICED families
    (geographical, geographical-by-fuel, allocated) must all still be
    present. Lock the indicator-set superset to catch accidental
    displacement on regen."""
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
    # Spot-check: rooftop is present + at least one CEA snapshot fuel +
    # the geographical parent + the allocated parent.
    assert INDICATOR_ID in indicators
    assert "state-installed-capacity-snapshot-mw-coal" in indicators
    assert "state-installed-capacity-geographical-mw" in indicators
    assert "state-installed-capacity-allocated-mw" in indicators
