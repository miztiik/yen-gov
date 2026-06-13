"""Pin the LS PC delimitation-shift methodology_breaks rows from PR-4.

Per TODO/20260613-party-deferred-followups-plan.md section 6 (Max Q1.1d):
two new rows for the pre-1999 LS PC delimitation shifts at 1967 + 1977 plus
the 2008 row that closes the chain. PR-10 will render the markers on
DualAxisBarLine consuming these rows.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "datasets" / "taxonomy" / "methodology_breaks.json"
SCHEMA_PATH = REPO_ROOT / "datasets" / "schemas" / "methodology-break.schema.json"


@pytest.fixture(scope="module")
def payload() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows(payload: dict) -> list[dict]:
    return payload["methodology_breaks"]


def test_pre1999_delim_methodology_breaks_present(rows: list[dict]) -> None:
    """The 2 new PR-4 rows + the 2008 chain-closer must all be present."""
    versions = {r["methodology_version"] for r in rows}
    assert "lspc-delim-1967" in versions, "PR-4 missing lspc-delim-1967 row"
    assert "lspc-delim-1976" in versions, "PR-4 missing lspc-delim-1976 row"
    assert "lspc-delim-2008" in versions, (
        "lspc-delim-2008 row missing (PR-4 backfill alongside the 1967 + 1976 rows)"
    )


def test_pre1999_delim_rows_have_canonical_month_period_seq(rows: list[dict]) -> None:
    """period_seq = month-number per backend/yen_gov/canonical/adapters/eci/identity.py _MONTH_NUM.

    1967 LS poll: Feb -> 2. 1977 LS poll: Mar -> 3. 2009 LS poll: May -> 5
    (matches the on-disk LsGenMay2009 period_label in elections data).
    """
    by_version = {r["methodology_version"]: r for r in rows}
    assert by_version["lspc-delim-1967"]["at_year"] == 1967
    assert by_version["lspc-delim-1967"]["at_period_seq"] == 2
    assert by_version["lspc-delim-1976"]["at_year"] == 1977
    assert by_version["lspc-delim-1976"]["at_period_seq"] == 3
    assert by_version["lspc-delim-2008"]["at_year"] == 2009
    assert by_version["lspc-delim-2008"]["at_period_seq"] == 5


def test_pre1999_delim_rows_form_supersession_chain(rows: list[dict]) -> None:
    """The 3 rows form an explicit chain so the renderer can trace the lineage."""
    by_version = {r["methodology_version"]: r for r in rows}
    assert by_version["lspc-delim-1967"]["supersedes_methodology_version"] is None
    assert (
        by_version["lspc-delim-1976"]["supersedes_methodology_version"]
        == "lspc-delim-1967"
    )
    assert (
        by_version["lspc-delim-2008"]["supersedes_methodology_version"]
        == "lspc-delim-1976"
    )


def test_pre1999_delim_rows_are_frame_change(rows: list[dict]) -> None:
    """All three rows use kind=frame_change per the schema enum (delimitation = sampling-frame move)."""
    by_version = {r["methodology_version"]: r for r in rows}
    for version in ("lspc-delim-1967", "lspc-delim-1976", "lspc-delim-2008"):
        assert by_version[version]["kind"] == "frame_change", (
            f"{version} should be kind=frame_change per schema enum"
        )


def test_methodology_breaks_payload_validates_against_schema(payload: dict) -> None:
    """The full file (including the 3 new PR-4 rows) validates against methodology-break.schema.json."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)
