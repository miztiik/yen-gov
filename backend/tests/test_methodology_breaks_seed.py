"""Tier-A tests for ``yen_gov.canonical.methodology_breaks_seed``.

Per CLAUDE.md §15: operates on ``tmp_path``, never walks real corpus.
Asserts the seed's row projection + Pydantic-enforced contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.methodology_breaks_seed import (
    METHODOLOGY_BREAK_KINDS,
    compile_to_parquet,
)


def _write_fixture(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "methodology_breaks.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _read(parquet: Path) -> list[tuple]:
    con = duckdb.connect()
    try:
        return con.execute(
            f"SELECT * FROM read_parquet('{parquet.as_posix()}') ORDER BY methodology_version"
        ).fetchall()
    finally:
        con.close()


def test_compile_writes_one_row_per_break(tmp_path):
    payload = {
        "methodology_breaks": [
            {
                "methodology_version": "test-rebase-2020-01",
                "at_year": 2020,
                "at_period_seq": 1,
                "kind": "rebase",
                "note": "Series rebased from 2011-12 to 2020-21 base; pre-break and post-break levels are not comparable.",
                "publisher_url": "https://example.org/notes",
            },
            {
                "methodology_version": "test-frame-2022-03",
                "at_year": 2022,
                "at_period_seq": 3,
                "kind": "frame_change",
                "note": "Sampling frame updated to LGD-2022; small-town coverage expanded.",
            },
        ]
    }
    out = tmp_path / "breaks.parquet"
    n = compile_to_parquet(_write_fixture(tmp_path, payload), out)
    assert n == 2
    rows = _read(out)
    assert len(rows) == 2
    # Sort order is by methodology_version (PK)
    assert rows[0][0] == "test-frame-2022-03"
    assert rows[1][0] == "test-rebase-2020-01"
    # publisher_url column is present and null for the second row
    assert rows[0][5] is None
    assert rows[1][5] == "https://example.org/notes"


def test_compile_is_deterministic(tmp_path):
    payload = {
        "methodology_breaks": [
            {
                "methodology_version": "v1",
                "at_year": 2021,
                "at_period_seq": 5,
                "kind": "definition_change",
                "note": "Definition tightened; off-grid solar moved out of grid-connected aggregate.",
            }
        ]
    }
    p_in = _write_fixture(tmp_path, payload)
    out1 = tmp_path / "1.parquet"
    out2 = tmp_path / "2.parquet"
    compile_to_parquet(p_in, out1)
    compile_to_parquet(p_in, out2)
    assert out1.read_bytes() == out2.read_bytes()


def test_compile_rejects_short_note(tmp_path):
    """note min_length=20 mirrors the JSON Schema contract."""
    payload = {
        "methodology_breaks": [
            {
                "methodology_version": "v1",
                "at_year": 2021,
                "at_period_seq": 1,
                "kind": "rebase",
                "note": "too short",
            }
        ]
    }
    with pytest.raises(Exception):
        compile_to_parquet(_write_fixture(tmp_path, payload), tmp_path / "x.parquet")


def test_compile_rejects_unknown_kind(tmp_path):
    payload = {
        "methodology_breaks": [
            {
                "methodology_version": "v1",
                "at_year": 2021,
                "at_period_seq": 1,
                "kind": "not_a_real_kind",
                "note": "this note is at least twenty characters long.",
            }
        ]
    }
    with pytest.raises(Exception):
        compile_to_parquet(_write_fixture(tmp_path, payload), tmp_path / "x.parquet")


def test_compile_rejects_at_year_out_of_range(tmp_path):
    payload = {
        "methodology_breaks": [
            {
                "methodology_version": "v1",
                "at_year": 1849,
                "at_period_seq": 1,
                "kind": "rebase",
                "note": "this note is at least twenty characters long.",
            }
        ]
    }
    with pytest.raises(Exception):
        compile_to_parquet(_write_fixture(tmp_path, payload), tmp_path / "x.parquet")


def test_kinds_constant_matches_schema_enum():
    """The constant pins the same enum the JSON Schema validates."""
    assert METHODOLOGY_BREAK_KINDS == (
        "rebase",
        "definition_change",
        "frame_change",
        "coverage_change",
        "reclassification",
    )


def test_compile_empty_payload(tmp_path):
    """Empty methodology_breaks[] writes a 0-row parquet (still valid)."""
    payload: dict = {"methodology_breaks": []}
    out = tmp_path / "empty.parquet"
    n = compile_to_parquet(_write_fixture(tmp_path, payload), out)
    assert n == 0
    rows = _read(out)
    assert rows == []
