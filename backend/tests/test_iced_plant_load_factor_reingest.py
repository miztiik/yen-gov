"""Tier-B gate: ICED plf-metatable -> plant-load-factor-pct re-ingest.

Graduates the orphan per-fuel `plant-load-factor-pct-<fuel>` family to LIVE
re-ingest: the v1 plant-load-factor-by-state-by-fuel feed (per-(state, FY,
fuel) PLF %) is re-keyed from ECI st_code to LGD slug and split into one
per-fuel CSV. This is a PERCENTAGE / non-fuel-axis family that does NOT fit
the geo_by_fuel file-class, so it keeps its existing per-facet `geo/*.csv`
shape (Path B: current shape, no new file-class). No mocks (Holy Law #7);
tmp_path fixtures only. The fixture pins the parser's real contract (faceted
by fuel source) and the triple reproduces the on-disk source_id so a re-emit
is idempotent with the committed files.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.sources.iced_metatable.ingest import (
    _CSV_FILE_CLASS,
    _CSV_SOURCE_PRODUCER,
    _CSV_VARIABLE_PREFIX_PLF,
    _PLF_REINGEST_TITLE,
    _PLF_REINGEST_VINTAGE,
    build_plant_load_factor_variables,
    ingest_plant_load_factor,
)
from yen_gov.sources.iced_metatable.parsers import parse_plf_metatable

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
        _CSV_SOURCE_PRODUCER, _PLF_REINGEST_TITLE, _PLF_REINGEST_VINTAGE
    )


def _stage_fk_targets(repo_root: Path, source_id: str) -> None:
    entities = repo_root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    (entities / "geo.csv").write_text(_GEO_CSV, encoding="utf-8")
    # The title contains commas, so it is quoted for well-formed CSV.
    (entities / "source.csv").write_text(
        "source_id,producer,title,vintage,url\n"
        f'{source_id},{_CSV_SOURCE_PRODUCER},"{_PLF_REINGEST_TITLE}",'
        f"{_PLF_REINGEST_VINTAGE},\n",
        encoding="utf-8",
    )


def _decrypted_response() -> dict:
    # v1 plf-metatable is plain JSON: {"data": [{state, source, year, plf}]}.
    # Two fuels (coal, solar) x two states (Title Case for ENTITY_MAP).
    return {
        "data": [
            {"state": "Andhra Pradesh", "source": "coal", "year": "2022-23", "plf": 61.25},
            {"state": "Andhra Pradesh", "source": "solar", "year": "2022-23", "plf": 20.0},
            {"state": "Maharashtra", "source": "coal", "year": "2022-23", "plf": 70.0},
            {"state": "Maharashtra", "source": "solar", "year": "2022-23", "plf": 22.5},
        ]
    }


def test_source_id_reproduces_on_disk():
    # The triple is pinned so a re-emit is idempotent with the committed files.
    assert _source_id() == "src-7eb929cbf2d8"


def test_build_plant_load_factor_splits_facets_and_translates():
    parsed, skipped = parse_plf_metatable(_decrypted_response())
    assert skipped == 0
    by_variable = build_plant_load_factor_variables(parsed, source_id="src-x")
    # One variable_id per fuel facet.
    assert set(by_variable) == {
        f"{_CSV_VARIABLE_PREFIX_PLF}-coal",
        f"{_CSV_VARIABLE_PREFIX_PLF}-solar",
    }
    coal = {r["entity_id"]: r for r in by_variable[f"{_CSV_VARIABLE_PREFIX_PLF}-coal"]}
    # ECI st_codes (S01/S13) re-keyed to LGD slugs.
    assert set(coal) == {"andhra-pradesh", "maharashtra"}
    assert coal["andhra-pradesh"]["value"] == pytest.approx(61.25)
    # FY "2022-04" reduced to integer start year.
    assert coal["andhra-pradesh"]["time"] == 2022
    assert all(
        r["source_id"] == "src-x"
        for rows in by_variable.values()
        for r in rows
    )


def test_ingest_plant_load_factor_end_to_end_validates(tmp_path: Path):
    sid = _source_id()
    _stage_fk_targets(tmp_path, sid)
    raw_path = tmp_path / "plf_metatable_data.json"
    raw_path.write_text(json.dumps(_decrypted_response()), encoding="utf-8")

    result = ingest_plant_load_factor(repo_root=tmp_path, raw_json_path=raw_path)

    assert result.skipped_unmapped == 0
    assert result.variable_ids == (
        f"{_CSV_VARIABLE_PREFIX_PLF}-coal",
        f"{_CSV_VARIABLE_PREFIX_PLF}-solar",
    )
    assert len(result.artifact_paths) == 2
    assert result.row_count == 4
    geo_dir = tmp_path / "datasets/data/datapoints/geo"
    for facet in ("coal", "solar"):
        out = geo_dir / f"{_CSV_VARIABLE_PREFIX_PLF}-{facet}.csv"
        assert out.read_text(encoding="utf-8").splitlines()[0] == (
            "entity_id,time,value,source_id"
        )
        validate_csv(path=out, file_class=_CSV_FILE_CLASS, repo_root=tmp_path)
