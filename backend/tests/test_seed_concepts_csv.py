"""Tests for B2a.3 concepts.csv emitter (sub-plan)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed.concepts_csv import FILE_CLASS, emit


def _stage_json(path: Path, concepts: list[dict]) -> None:
    path.write_text(json.dumps({"concepts": concepts}), encoding="utf-8")


def _concept(**overrides) -> dict:
    base = {
        "concept_id": "demo-concept",
        "noun": "Demo concept",
        "unit_canonical": "%",
        "normalisation": "share",
        "entity_kinds": ["state"],
        "description_short": "An example for tests.",
    }
    base.update(overrides)
    return base


def test_emit_minimal(tmp_path):
    src = tmp_path / "concepts.json"
    _stage_json(
        src,
        [
            _concept(concept_id="a-noun", noun="A noun"),
            _concept(concept_id="b-noun", noun="B noun", entity_kinds=["state", "district"]),
        ],
    )
    out = tmp_path / "datasets" / "data" / "concepts.csv"
    emit(concepts_json=src, out_path=out)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "concept_id,noun,unit_canonical,normalisation,entity_kinds,description"
    assert len(lines) == 3
    body = "\n".join(lines[1:])
    assert "a-noun,A noun,%,share,state,An example for tests." in body
    assert "b-noun,B noun,%,share,state district,An example for tests." in body


def test_emit_nullable_description(tmp_path):
    src = tmp_path / "concepts.json"
    _stage_json(src, [_concept(description_short=None)])
    out = tmp_path / "out.csv"
    emit(concepts_json=src, out_path=out)
    line = out.read_text(encoding="utf-8").splitlines()[1]
    assert line.endswith(",")


def test_emit_rejects_double_underscore(tmp_path):
    src = tmp_path / "concepts.json"
    _stage_json(src, [_concept(concept_id="a__b")])
    with pytest.raises(ValueError, match="must not contain '__'"):
        emit(concepts_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_duplicate_id(tmp_path):
    src = tmp_path / "concepts.json"
    _stage_json(src, [_concept(), _concept()])
    with pytest.raises(ValueError, match="duplicate concept_id"):
        emit(concepts_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_missing_noun(tmp_path):
    src = tmp_path / "concepts.json"
    entry = _concept()
    entry.pop("noun")
    _stage_json(src, [entry])
    with pytest.raises(ValueError, match="missing 'noun'"):
        emit(concepts_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_empty_entity_kinds(tmp_path):
    src = tmp_path / "concepts.json"
    _stage_json(src, [_concept(entity_kinds=[])])
    with pytest.raises(ValueError, match="entity_kinds"):
        emit(concepts_json=src, out_path=tmp_path / "out.csv")


def test_emitted_csv_passes_validator(tmp_path):
    src = tmp_path / "concepts.json"
    _stage_json(
        src,
        [
            _concept(concept_id="abs-one", normalisation="absolute"),
            _concept(concept_id="per-area-one", normalisation="per_area"),
            _concept(concept_id="ratio-one", normalisation="ratio"),
            _concept(concept_id="index-one", normalisation="index"),
        ],
    )
    repo_root = tmp_path
    out = repo_root / "datasets" / "data" / "concepts.csv"
    emit(concepts_json=src, out_path=out)
    validate_csv(path=out, file_class=FILE_CLASS, repo_root=repo_root)
