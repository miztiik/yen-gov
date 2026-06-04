"""Tests for B2a.4 variables.csv emitter (sub-plan)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed.variables_csv import FILE_CLASS, emit


def _stage_indicators(path: Path, indicators: list[dict]) -> None:
    path.write_text(json.dumps({"indicators": indicators}), encoding="utf-8")


def _stage_csv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")


def _indicator(**overrides) -> dict:
    base = {
        "indicator_id": "demo-rate",
        "label_short": "Demo rate",
        "concept_id": "demo-concept",
        "unit": "%",
        "topic_tags": ["elections"],
        "source_id": "in-eci-demo-2024",
        "update_period_days": 365,
    }
    base.update(overrides)
    return base


def test_emit_minimal(tmp_path):
    src = tmp_path / "indicators.json"
    _stage_indicators(
        src,
        [
            _indicator(indicator_id="a-rate", label_short="A rate"),
            _indicator(indicator_id="b-rate", label_short="B rate", source_id=None),
        ],
    )
    out = tmp_path / "datasets" / "data" / "variables.csv"
    emit(indicators_json=src, out_path=out)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == (
        "indicator_id,name,concept_id,unit,derivation,topic,source_id,"
        "update_period_days,time_min,time_max,entity_kinds"
    )
    assert len(lines) == 3
    body = "\n".join(lines[1:])
    assert "a-rate,A rate,demo-concept,%,,elections,in-eci-demo-2024,365,,," in body
    assert "b-rate,B rate,demo-concept,%,,elections,,365,,," in body


def test_emit_picks_first_topic_tag(tmp_path):
    src = tmp_path / "indicators.json"
    _stage_indicators(
        src,
        [_indicator(topic_tags=["energy", "elections"])],
    )
    out = tmp_path / "out.csv"
    emit(indicators_json=src, out_path=out)
    line = out.read_text(encoding="utf-8").splitlines()[1]
    fields = line.split(",")
    assert fields[5] == "energy"


def test_emit_rejects_double_underscore(tmp_path):
    src = tmp_path / "indicators.json"
    _stage_indicators(src, [_indicator(indicator_id="a__b")])
    with pytest.raises(ValueError, match="must not contain '__'"):
        emit(indicators_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_duplicate_id(tmp_path):
    src = tmp_path / "indicators.json"
    _stage_indicators(src, [_indicator(), _indicator()])
    with pytest.raises(ValueError, match="duplicate indicator_id"):
        emit(indicators_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_missing_concept_id(tmp_path):
    src = tmp_path / "indicators.json"
    entry = _indicator()
    entry.pop("concept_id")
    _stage_indicators(src, [entry])
    with pytest.raises(ValueError, match="missing 'concept_id'"):
        emit(indicators_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_missing_unit(tmp_path):
    src = tmp_path / "indicators.json"
    entry = _indicator()
    entry.pop("unit")
    _stage_indicators(src, [entry])
    with pytest.raises(ValueError, match="missing 'unit'"):
        emit(indicators_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_empty_topic_tags(tmp_path):
    src = tmp_path / "indicators.json"
    _stage_indicators(src, [_indicator(topic_tags=[])])
    with pytest.raises(ValueError, match="topic_tags"):
        emit(indicators_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_missing_update_period_days(tmp_path):
    src = tmp_path / "indicators.json"
    entry = _indicator()
    entry.pop("update_period_days")
    _stage_indicators(src, [entry])
    with pytest.raises(ValueError, match="update_period_days"):
        emit(indicators_json=src, out_path=tmp_path / "out.csv")


def test_emitted_csv_passes_validator(tmp_path):
    repo_root = tmp_path
    # Stage FK predecessors: concepts.csv, topics.csv, source.csv
    _stage_csv(
        repo_root / "datasets" / "data" / "concepts.csv",
        "concept_id,noun,unit_canonical,normalisation,entity_kinds,description",
        [
            "demo-concept,Demo,%,share,state,A demo concept",
            "other-concept,Other,votes,absolute,candidate,Another",
        ],
    )
    _stage_csv(
        repo_root / "datasets" / "data" / "topics.csv",
        "topic,name,parent",
        ["elections,Elections,", "energy,Energy,"],
    )
    _stage_csv(
        repo_root / "datasets" / "data" / "entities" / "source.csv",
        "source_id,owner,title,vintage,url",
        ["in-eci-demo-2024,ECI,Demo,2024,"],
    )

    src = tmp_path / "indicators.json"
    _stage_indicators(
        src,
        [
            _indicator(indicator_id="a-rate", label_short="A rate"),
            _indicator(
                indicator_id="b-rate",
                label_short="B rate",
                concept_id="other-concept",
                unit="votes",
                topic_tags=["energy"],
                source_id=None,
            ),
        ],
    )
    out = repo_root / "datasets" / "data" / "variables.csv"
    emit(indicators_json=src, out_path=out)
    validate_csv(path=out, file_class=FILE_CLASS, repo_root=repo_root)
