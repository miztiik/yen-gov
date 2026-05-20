"""Tier-A tests for ``yen_gov.canonical.election_events_seed``.

Per CLAUDE.md §15, ``tmp_path`` fixtures only.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.election_events_seed import (
    ELECTION_EVENTS_ROW_SCHEMA_VERSION,
    compile_to_parquet,
)


def _write(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "election_events.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _rows(parquet: Path) -> list[tuple]:
    con = duckdb.connect()
    try:
        return con.execute(
            f"SELECT * FROM read_parquet('{parquet.as_posix()}') ORDER BY state_code, event_id"
        ).fetchall()
    finally:
        con.close()


def test_compile_emits_one_row_per_event(tmp_path):
    payload = {
        "states": {
            "S22": [
                {
                    "event_id": "AcGenMay2026",
                    "kind": "assembly",
                    "display": "TN Assembly Election 2026",
                    "polled_on": "2026-05-01",
                    "default": True,
                    "data_status": "complete",
                },
                {
                    "event_id": "AcGenMay2021",
                    "kind": "assembly",
                    "display": "TN Assembly Election 2021",
                    "polled_on": "2021-04-06",
                    "default": False,
                    "data_status": "complete",
                },
            ]
        }
    }
    out = tmp_path / "election_events.parquet"
    n = compile_to_parquet(_write(tmp_path, payload), out)
    assert n == 2
    rows = _rows(out)
    assert [r[1] for r in rows] == ["AcGenMay2021", "AcGenMay2026"]
    # is_default flag preserved
    by_id = {r[1]: r[6] for r in rows}  # event_id -> is_default
    assert by_id["AcGenMay2026"] is True
    assert by_id["AcGenMay2021"] is False


def test_compile_rejects_two_defaults_per_state(tmp_path):
    """Plan §0e.10.2-E LOCKED: at most one default event per state."""
    payload = {
        "states": {
            "S22": [
                {
                    "event_id": "AcGenMay2026",
                    "kind": "assembly",
                    "display": "x",
                    "polled_on": "2026-05-01",
                    "default": True,
                    "data_status": "complete",
                },
                {
                    "event_id": "AcGenMay2021",
                    "kind": "assembly",
                    "display": "x",
                    "polled_on": "2021-04-06",
                    "default": True,  # second default — must fail
                    "data_status": "complete",
                },
            ]
        }
    }
    out = tmp_path / "x.parquet"
    with pytest.raises(ValueError, match="default"):
        compile_to_parquet(_write(tmp_path, payload), out)


def test_compile_passes_nullable_term_end(tmp_path):
    payload = {
        "states": {
            "S22": [
                {
                    "event_id": "AcGenMay2026",
                    "kind": "assembly",
                    "display": "x",
                    "polled_on": "2026-05-01",
                    "term_end_estimated": "2031-05-01",
                    "default": True,
                    "data_status": "complete",
                }
            ]
        }
    }
    out = tmp_path / "out.parquet"
    compile_to_parquet(_write(tmp_path, payload), out)
    rows = _rows(out)
    # term_end_estimated -> column index 5
    assert rows[0][5] is not None


def test_schema_version_constant():
    assert ELECTION_EVENTS_ROW_SCHEMA_VERSION == "1.0"
