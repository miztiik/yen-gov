"""Contract tests for Row A3: lgd_ac_id lifted onto dim_acs.parquet.

ADR-0049: ``lgd_ac_id`` is the canonical internal join key; the crosswalk
covers only the 2008 delimitation cycle, so 1976 rows and ACs without an LGD
binding stay NULL.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from yen_gov.pipeline.dim_acs_lgd_lift import (
    CROSSWALK_DELIM_YEAR,
    load_lgd_lookup,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS = REPO_ROOT / "datasets"
DIM_ACS = DATASETS / "elections" / "dim_acs.parquet"
CROSSWALK = DATASETS / "taxonomy" / "ac_crosswalk.parquet"


def test_load_lgd_lookup_excludes_nulls() -> None:
    lookup = load_lgd_lookup(DATASETS)
    assert lookup, "expected a non-empty covered lookup"
    # Every value is a positive int LGD code; keys are (state_code, eci_no).
    for (state_code, eci_no), lgd in lookup.items():
        assert isinstance(state_code, str) and state_code
        assert isinstance(eci_no, int) and eci_no >= 1
        assert isinstance(lgd, int) and lgd >= 1


def test_load_lgd_lookup_missing_crosswalk_returns_empty(tmp_path: Path) -> None:
    assert load_lgd_lookup(tmp_path) == {}


@pytest.mark.skipif(not DIM_ACS.is_file(), reason="dim_acs.parquet not materialised")
def test_shipped_dim_acs_has_lgd_column() -> None:
    con = duckdb.connect(":memory:")
    try:
        cols = [
            c[0]
            for c in con.execute(
                "SELECT * FROM read_parquet(?) LIMIT 0", [DIM_ACS.as_posix()]
            ).description
        ]
    finally:
        con.close()
    assert "lgd_ac_id" in cols


@pytest.mark.skipif(
    not (DIM_ACS.is_file() and CROSSWALK.is_file()),
    reason="dim_acs/crosswalk not materialised",
)
def test_shipped_dim_acs_matches_crosswalk() -> None:
    """Every 2008 row's lgd_ac_id equals the crosswalk; non-2008 rows are NULL."""
    lookup = load_lgd_lookup(DATASETS)
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            "SELECT state_code, eci_no, delim_year, lgd_ac_id "
            "FROM read_parquet(?)",
            [DIM_ACS.as_posix()],
        ).fetchall()
    finally:
        con.close()

    covered = 0
    for state_code, eci_no, delim_year, lgd_ac_id in rows:
        if delim_year != CROSSWALK_DELIM_YEAR:
            assert lgd_ac_id is None, (
                f"non-{CROSSWALK_DELIM_YEAR} row {state_code}/{eci_no} "
                f"@{delim_year} must have NULL lgd_ac_id, got {lgd_ac_id}"
            )
            continue
        expected = lookup.get((str(state_code), int(eci_no)))
        assert lgd_ac_id == expected, (
            f"{state_code}/{eci_no}@{delim_year}: "
            f"dim lgd_ac_id={lgd_ac_id} != crosswalk {expected}"
        )
        if expected is not None:
            covered += 1

    assert covered == len(lookup), (
        f"covered dim rows {covered} != crosswalk covered keys {len(lookup)}"
    )
