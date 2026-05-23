"""Parity oracle + D33.8 negative assert for energy_generation.parquet.

Same shape as test_energy_installed_capacity_parity.py: hand-picked RAW
cells vs source JSON, plus D33.8 negative assert (no ``*-total-gwh`` /
``*-total-mu`` rows — generation totals compute on read).

The unit-name relation MU ↔ GWh (1 MU = 1 GWh) is enforced upstream by
the catalogue's canonical unit ``GWh``; legacy shard publishes ``MU``,
adapter copies the numeric verbatim and re-labels.

Holy Law #7: real on-disk Parquet + real shards, no mocks.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PARQUET = REPO_ROOT / "datasets" / "energy" / "energy_generation.parquet"
SHARD_DIR = REPO_ROOT / "datasets" / "indicators" / "in" / "energy"


pytestmark = pytest.mark.skipif(
    not PARQUET.is_file(),
    reason=(
        "datasets/energy/energy_generation.parquet not on disk; "
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


def test_state_generation_publisher_total_matches_shard_in_2015() -> None:
    """state-electricity-generation-gwh, IN 2015-04 = 1167584.06 MU = 1167584.06 GWh."""
    val = _query_value("IN", 2015, "state-electricity-generation-gwh")
    assert val == pytest.approx(1167584.06, abs=0.01), (
        f"IN 2015 state-electricity-generation-gwh expected 1167584.06, got {val!r}"
    )


def test_state_generation_coal_facet_matches_shard_s01_2015() -> None:
    """state-electricity-generation-gwh-coal, IN-S01 2015-04 = 52023.75 (raw 1:1)."""
    val = _query_value("IN-S01", 2015, "state-electricity-generation-gwh-coal")
    assert val == pytest.approx(52023.75, abs=0.01), (
        f"IN-S01 2015 ...-gwh-coal expected 52023.75, got {val!r}"
    )


def test_state_generation_renewable_facet_is_sum_of_collapsed_subfuels() -> None:
    """state-electricity-generation-gwh-renewable for IN-S01 2015-04 must equal
    sum of renewable sub-fuels (bio-power + small-hydro + solar + wind ...)."""
    shard = json.loads(
        (SHARD_DIR / "state_electricity_generation_by_source_gwh.json").read_text(encoding="utf-8")
    )
    renewable_subs = {"bio-power", "biomass", "small-hydro", "solar", "wind", "waste-to-energy"}
    expected = sum(
        float(r["value"])
        for r in shard["rows"]
        if r["entity_id"] == "S01" and r["time"] == "2015-04" and r["facet"] in renewable_subs
    )
    assert expected > 0, "sanity: shard has at least one renewable sub-fuel row for S01 2015"

    val = _query_value("IN-S01", 2015, "state-electricity-generation-gwh-renewable")
    assert val == pytest.approx(expected, abs=0.01), (
        f"IN-S01 2015 ...-gwh-renewable expected {expected!r}, got {val!r}"
    )


def test_d33_8_no_total_gwh_rows_emitted() -> None:
    """D33.8: ``*-total-gwh`` rows are compute-on-read parents."""
    con = duckdb.connect(":memory:")
    try:
        n = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '%-total-gwh'"
        ).fetchone()[0]
    finally:
        con.close()
    assert n == 0, (
        f"D33.8 violation: energy_generation.parquet contains {n} `*-total-gwh` rows."
    )


def test_d33_8_no_thermal_gwh_rows_emitted() -> None:
    """D33.8: ``*-thermal-gwh`` rows are compute-on-read parents."""
    con = duckdb.connect(":memory:")
    try:
        n = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{PARQUET.as_posix()}') "
            f"WHERE indicator_id LIKE '%-thermal-gwh'"
        ).fetchone()[0]
    finally:
        con.close()
    assert n == 0, (
        f"D33.8 violation: energy_generation.parquet contains {n} `*-thermal-gwh` rows."
    )
