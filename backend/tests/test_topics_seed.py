"""Tier-A tests for ``yen_gov.canonical.topics_seed``.

Per CLAUDE.md §15, ``tmp_path`` fixtures only — no real corpus walks.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.topics_seed import (
    INDICATOR_TOPIC_TAGS_ROW_SCHEMA_VERSION,
    TOPICS_ROW_SCHEMA_VERSION,
    compile_to_parquet,
)


def _write_catalogue(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "topics.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _rows(parquet: Path) -> list[tuple]:
    con = duckdb.connect()
    try:
        return con.execute(
            f"SELECT * FROM read_parquet('{parquet.as_posix()}') ORDER BY 1, 2, 3"
        ).fetchall()
    finally:
        con.close()


def _minimal_topic(**overrides) -> dict:
    base = {
        "id": "fiscal",
        "title": "Fiscal capacity",
        "list": "state",
        "summary": "How much money the state has.",
        "icon": "rupee",
        "featured": True,
        "artifacts": [
            {"kind": "indicator", "id": "deficit", "default": True, "featured": True},
            {"kind": "indicator", "id": "debt", "default": False, "featured": False},
        ],
    }
    base.update(overrides)
    return base


def test_compile_emits_topics_and_tags(tmp_path):
    payload = {"topics": [_minimal_topic()]}
    topics_out = tmp_path / "topics.parquet"
    tags_out = tmp_path / "tags.parquet"
    n_topics, n_tags = compile_to_parquet(
        _write_catalogue(tmp_path, payload), topics_out, tags_out
    )
    assert n_topics == 1
    assert n_tags == 2
    trows = _rows(topics_out)
    assert trows[0][0] == "fiscal"
    assert trows[0][1] == "Fiscal capacity"
    assert trows[0][2] == "state"  # seventh_schedule_list
    assert trows[0][5] is True  # featured
    tagrows = _rows(tags_out)
    # Sorted (topic_id, kind, id) -> debt then deficit
    assert [r[2] for r in tagrows] == ["debt", "deficit"]
    # in_topic_order preserves catalogue order from the artifacts[] array
    by_id = {r[2]: r[-1] for r in tagrows}
    assert by_id["deficit"] == 1
    assert by_id["debt"] == 2


def test_compile_rejects_topic_without_artifacts(tmp_path):
    """artifacts is required and non-empty (min_length=1) — Jony rule:
    a topic with no artifacts is not a topic."""
    payload = {
        "topics": [
            {
                "id": "empty",
                "title": "Empty",
                "list": "state",
                "summary": "x",
                "artifacts": [],
            }
        ]
    }
    with pytest.raises(Exception):
        compile_to_parquet(
            _write_catalogue(tmp_path, payload),
            tmp_path / "t.parquet",
            tmp_path / "tags.parquet",
        )


def test_compile_is_deterministic(tmp_path):
    payload = {
        "topics": [
            _minimal_topic(),
            _minimal_topic(id="energy", title="Energy", artifacts=[
                {"kind": "indicator", "id": "renewables-share"}
            ]),
        ]
    }
    p_in = _write_catalogue(tmp_path, payload)
    a1 = tmp_path / "t1.parquet"
    a2 = tmp_path / "t2.parquet"
    b1 = tmp_path / "tag1.parquet"
    b2 = tmp_path / "tag2.parquet"
    compile_to_parquet(p_in, a1, b1)
    compile_to_parquet(p_in, a2, b2)
    assert a1.read_bytes() == a2.read_bytes()
    assert b1.read_bytes() == b2.read_bytes()


def test_schema_version_constants():
    assert TOPICS_ROW_SCHEMA_VERSION == "1.0"
    assert INDICATOR_TOPIC_TAGS_ROW_SCHEMA_VERSION == "1.0"
