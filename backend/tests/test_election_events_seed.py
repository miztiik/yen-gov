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
                    "data_status": "complete",
                },
                {
                    "event_id": "AcGenMay2021",
                    "kind": "assembly",
                    "display": "TN Assembly Election 2021",
                    "polled_on": "2021-04-06",
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
    # 8-column shape post v1.1 (no is_default): state_code, event_id, kind,
    # display, polled_on, term_end_estimated, data_status, notes.
    assert len(rows[0]) == 8


def test_compile_rejects_unknown_default_field(tmp_path):
    """v1.1: the `default` field was removed. A payload that still carries it
    must be rejected by Pydantic `extra="forbid"` rather than silently
    ignored — silent acceptance would let stale fixtures and stale on-disk
    JSON drift past the seed boundary forever.
    """
    payload = {
        "states": {
            "S22": [
                {
                    "event_id": "AcGenMay2026",
                    "kind": "assembly",
                    "display": "x",
                    "polled_on": "2026-05-01",
                    "default": True,  # removed in v1.1 — must raise
                    "data_status": "complete",
                }
            ]
        }
    }
    out = tmp_path / "x.parquet"
    with pytest.raises(Exception):  # pydantic.ValidationError
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
                    "data_status": "complete",
                }
            ]
        }
    }
    out = tmp_path / "out.parquet"
    compile_to_parquet(_write(tmp_path, payload), out)
    rows = _rows(out)
    # term_end_estimated -> column index 5 (8-column post-v1.1 shape)
    assert rows[0][5] is not None


def test_schema_version_constant():
    assert ELECTION_EVENTS_ROW_SCHEMA_VERSION == "1.1"
