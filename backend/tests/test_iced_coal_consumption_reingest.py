"""Tier-B gate: ICED coal-consumption -> coal-consumption-mt re-ingest.

Graduates the orphan `coal-consumption-mt` series to LIVE re-ingest: the
domestic coal-consumption-by-state feed (per-(state, FY, grade) Mt) is summed
across grades by the parser, then re-keyed from ECI st_code to LGD slug and
reduced to one Mt value per (state, calendar year). No mocks (Holy Law #7);
tmp_path fixtures only. The fixture pins the parser's real contract (grades
summed, TOTAL COAL dropped) and the triple reproduces the on-disk source_id
so a re-emit is idempotent with the committed file.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.sources.iced_fuel.ingest import (
    _COAL_REINGEST_TITLE,
    _COAL_REINGEST_VINTAGE,
    _CSV_FILE_CLASS,
    _CSV_SOURCE_PRODUCER,
    _CSV_VARIABLE_PREFIX_COAL,
    build_coal_consumption_rows,
    ingest_coal_consumption,
)
from yen_gov.sources.iced_fuel.parsers import parse_coal_consumption_state

# Minimal geo.csv FK target: the two state slugs the fixture resolves to
# (S01 -> andhra-pradesh, S13 -> maharashtra) plus the national rollup.
# Rows copied verbatim from datasets/data/entities/geo.csv.
_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01|lgd:28,28,28\n"
    "maharashtra,Maharashtra,IN,state,IN-MH|S13|lgd:27,27,27\n"
)


def _source_id() -> str:
    return derive_source_id(
        _CSV_SOURCE_PRODUCER, _COAL_REINGEST_TITLE, _COAL_REINGEST_VINTAGE
    )


def _stage_fk_targets(repo_root: Path, source_id: str) -> None:
    entities = repo_root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    (entities / "geo.csv").write_text(_GEO_CSV, encoding="utf-8")
    (entities / "source.csv").write_text(
        "source_id,producer,title,vintage,url\n"
        f"{source_id},{_CSV_SOURCE_PRODUCER},{_COAL_REINGEST_TITLE},"
        f"{_COAL_REINGEST_VINTAGE},\n",
        encoding="utf-8",
    )


def _decrypted_response() -> dict:
    # Two states; the parser sums the 4 component grades per (state, year) and
    # drops the precomputed TOTAL COAL row to avoid double-counting:
    #   Maharashtra (S13): 80 + 10 + 4 + 0.5 = 94.5 Mt
    #   Andhra Pradesh (S01): 30 + 10        = 40.0 Mt
    return {
        "data": [
            {"state": "MAHARASHTRA", "year": "2022-23", "type": "RAW COAL", "total": 80.0},
            {"state": "MAHARASHTRA", "year": "2022-23", "type": "WASHED COAL", "total": 10.0},
            {"state": "MAHARASHTRA", "year": "2022-23", "type": "MIDDLINGS", "total": 4.0},
            {"state": "MAHARASHTRA", "year": "2022-23", "type": "LIGNITE", "total": 0.5},
            {"state": "MAHARASHTRA", "year": "2022-23", "type": "TOTAL COAL", "total": 999.0},
            {"state": "ANDHRA PRADESH", "year": "2022-23", "type": "RAW COAL", "total": 30.0},
            {"state": "ANDHRA PRADESH", "year": "2022-23", "type": "WASHED COAL", "total": 10.0},
        ]
    }


def test_source_id_reproduces_on_disk():
    # The triple is pinned so a re-emit is idempotent with the committed file.
    assert _source_id() == "src-c222a8e2cd61"


def test_build_coal_consumption_translates_eci_to_slug_and_year():
    parsed, skipped = parse_coal_consumption_state(_decrypted_response())
    assert skipped == 0
    by_variable = build_coal_consumption_rows(parsed, source_id="src-x")
    rows = by_variable[_CSV_VARIABLE_PREFIX_COAL]
    by_entity = {r["entity_id"]: r for r in rows}
    # ECI st_codes (S01/S13) re-keyed to LGD slugs.
    assert set(by_entity) == {"andhra-pradesh", "maharashtra"}
    # Grades summed; TOTAL COAL dropped.
    assert by_entity["maharashtra"]["value"] == pytest.approx(94.5)
    assert by_entity["andhra-pradesh"]["value"] == pytest.approx(40.0)
    # FY "2022-04" reduced to integer start year.
    assert all(r["time"] == 2022 for r in rows)
    assert all(r["source_id"] == "src-x" for r in rows)


def test_ingest_coal_consumption_end_to_end_validates(tmp_path: Path):
    sid = _source_id()
    _stage_fk_targets(tmp_path, sid)
    raw_path = tmp_path / "coal_consumption_domestic_state.json"
    raw_path.write_text(json.dumps(_decrypted_response()), encoding="utf-8")

    result = ingest_coal_consumption(repo_root=tmp_path, raw_json_path=raw_path)

    assert result.variable_id == _CSV_VARIABLE_PREFIX_COAL
    assert result.row_count == 2
    assert result.skipped_unmapped == 0
    out = tmp_path / "datasets/data/datapoints/geo" / f"{_CSV_VARIABLE_PREFIX_COAL}.csv"
    assert out.read_text(encoding="utf-8").splitlines()[0] == (
        "entity_id,time,value,source_id"
    )
    validate_csv(path=out, file_class=_CSV_FILE_CLASS, repo_root=tmp_path)
