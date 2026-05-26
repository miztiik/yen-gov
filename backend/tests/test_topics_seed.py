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


def test_compile_accepts_topic_without_artifacts(tmp_path):
    """artifacts is permitted to be empty (topic-catalogue.schema.json v1.3
    lowered minItems from 1→0). Structural placeholder topics whose first
    P.* ingestion has not yet landed open with an empty artifacts[] array
    and gain entries when the P.* PR wires them up. Per TODO/20260517 §0e.4."""
    payload = {
        "topics": [
            {
                "id": "empty",
                "title": "Empty",
                "list": "state",
                "summary": "Placeholder topic — no artifacts wired yet.",
                "artifacts": [],
            }
        ]
    }
    topics_out = tmp_path / "t.parquet"
    tags_out = tmp_path / "tags.parquet"
    n_topics, n_tags = compile_to_parquet(
        _write_catalogue(tmp_path, payload), topics_out, tags_out
    )
    assert n_topics == 1
    assert n_tags == 0
    trows = _rows(topics_out)
    assert trows[0][0] == "empty"
    # Tags parquet exists but is empty.
    tagrows = _rows(tags_out)
    assert tagrows == []


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
    # 2.0 because chart_type + dimension columns are REMOVED from the
    # indicator_topic_tags Parquet row shape per PR-A3c (ADR-0045 split).
    # Render hints now live in datasets/grapher/topic_render.json
    # (frontend-owned). Bumped in lockstep with topic-catalogue.schema.json
    # v2.0 so consumers can probe the row-schema-version and switch reads
    # to the grapher catalogue overlay before reading.
    assert INDICATOR_TOPIC_TAGS_ROW_SCHEMA_VERSION == "2.0"
