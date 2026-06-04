"""Tests for B2a.2 topics.csv emitter (sub-plan)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed.topics_csv import FILE_CLASS, emit


def _stage_json(path: Path, topics: list[dict]) -> None:
    path.write_text(json.dumps({"topics": topics}), encoding="utf-8")


def test_emit_flat_pillars(tmp_path):
    src = tmp_path / "topics.json"
    _stage_json(
        src,
        [
            {"id": "fiscal", "title": "Money & debt"},
            {"id": "energy", "title": "Power & energy"},
        ],
    )
    out = tmp_path / "datasets" / "data" / "topics.csv"
    emit(topics_json=src, out_path=out)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "topic,name,parent"
    assert len(lines) == 3
    body = "\n".join(lines[1:])
    assert "energy,Power & energy," in body
    assert "fiscal,Money & debt," in body


def test_emit_with_nested_parent(tmp_path):
    src = tmp_path / "topics.json"
    _stage_json(
        src,
        [
            {"id": "fiscal", "title": "Money & debt"},
            {"id": "fiscal-debt", "title": "Debt", "parent": "fiscal"},
        ],
    )
    out = tmp_path / "topics.csv"
    emit(topics_json=src, out_path=out)
    body = out.read_text(encoding="utf-8")
    assert "fiscal-debt,Debt,fiscal" in body


def test_emit_rejects_double_underscore(tmp_path):
    src = tmp_path / "topics.json"
    _stage_json(src, [{"id": "a__b", "title": "X"}])
    with pytest.raises(ValueError, match="must not contain '__'"):
        emit(topics_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_duplicate_id(tmp_path):
    src = tmp_path / "topics.json"
    _stage_json(
        src,
        [
            {"id": "fiscal", "title": "A"},
            {"id": "fiscal", "title": "B"},
        ],
    )
    with pytest.raises(ValueError, match="duplicate topic id"):
        emit(topics_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_unknown_parent(tmp_path):
    src = tmp_path / "topics.json"
    _stage_json(
        src,
        [{"id": "child", "title": "Child", "parent": "ghost"}],
    )
    with pytest.raises(ValueError, match="unknown parent"):
        emit(topics_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_missing_title(tmp_path):
    src = tmp_path / "topics.json"
    _stage_json(src, [{"id": "fiscal"}])
    with pytest.raises(ValueError, match="missing 'title'"):
        emit(topics_json=src, out_path=tmp_path / "out.csv")


def test_emitted_csv_passes_validator(tmp_path):
    src = tmp_path / "topics.json"
    _stage_json(
        src,
        [
            {"id": "fiscal", "title": "Money & debt"},
            {"id": "fiscal-debt", "title": "Debt", "parent": "fiscal"},
        ],
    )
    repo_root = tmp_path
    out = repo_root / "datasets" / "data" / "topics.csv"
    emit(topics_json=src, out_path=out)
    validate_csv(path=out, file_class=FILE_CLASS, repo_root=repo_root)
