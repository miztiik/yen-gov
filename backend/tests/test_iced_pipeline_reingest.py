"""Tier-B gate: ICED plant-pipeline -> under-construction-capacity-gw re-ingest.

Graduates the orphan `under-construction-capacity-gw` series to LIVE
re-ingest: the plantPipelineInfo feed (per-(year, status) GW additions) sums
to one national GW total per calendar year. No mocks (Holy Law #7); tmp_path
fixtures only. The fixture reproduces the on-disk values (2011=0.485,
2012=4.69) so the contract is pinned to real shape.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.adapters.iced_power.ingest import (
    _CSV_FILE_CLASS,
    _CSV_SOURCE_PRODUCER,
    _PIPELINE_TITLE,
    _PIPELINE_VARIABLE_ID,
    _PIPELINE_VINTAGE,
    build_pipeline_rows,
    ingest_pipeline,
)

_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
)


def _source_id() -> str:
    return derive_source_id(_CSV_SOURCE_PRODUCER, _PIPELINE_TITLE, _PIPELINE_VINTAGE)


def _stage_fk_targets(repo_root: Path, source_id: str) -> None:
    entities = repo_root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    (entities / "geo.csv").write_text(_GEO_CSV, encoding="utf-8")
    (entities / "source.csv").write_text(
        "source_id,producer,title,vintage,url\n"
        f"{source_id},{_CSV_SOURCE_PRODUCER},{_PIPELINE_TITLE},{_PIPELINE_VINTAGE},\n",
        encoding="utf-8",
    )


def _pipeline_response() -> dict:
    # Two statuses per year -> the canonical series sums them.
    return {
        "category": ["2011", "2012"],
        "seriesData": [
            {"name": "Under Construction and likely to be commissioned", "data": [0.3, 2.0]},
            {"name": "Under Construction but on Hold", "data": [0.185, 2.69]},
        ],
    }


def test_source_id_reproduces_on_disk():
    # The triple is pinned so a re-emit is idempotent with the committed file.
    assert _source_id() == "src-e0b2a084d204"


def test_build_pipeline_rows_sums_statuses_per_year():
    from yen_gov.canonical.adapters.iced_power.parsers import parse_plant_pipeline_info

    parsed = parse_plant_pipeline_info(_pipeline_response())
    by_variable = build_pipeline_rows(parsed, source_id="src-x")
    rows = by_variable[_PIPELINE_VARIABLE_ID]
    by_year = {r["time"]: r["value"] for r in rows}
    assert by_year[2011] == pytest.approx(0.485)
    assert by_year[2012] == pytest.approx(4.69)
    assert all(r["entity_id"] == "IN" for r in rows)


def test_ingest_pipeline_end_to_end_validates(tmp_path: Path):
    sid = _source_id()
    _stage_fk_targets(tmp_path, sid)
    raw_path = tmp_path / "plant_pipeline_info.json"
    raw_path.write_text(json.dumps(_pipeline_response()), encoding="utf-8")

    result = ingest_pipeline(repo_root=tmp_path, raw_json_path=raw_path)

    assert result.variable_id == _PIPELINE_VARIABLE_ID
    assert result.row_count == 2
    out = tmp_path / "datasets/data/datapoints/geo" / f"{_PIPELINE_VARIABLE_ID}.csv"
    assert out.read_text(encoding="utf-8").splitlines()[0] == (
        "entity_id,time,value,source_id"
    )
    validate_csv(path=out, file_class=_CSV_FILE_CLASS, repo_root=tmp_path)
