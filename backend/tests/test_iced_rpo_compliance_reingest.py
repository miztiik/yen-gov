"""Tier-B gate: ICED distribution-rpo -> rpo-compliance-pct re-ingest.

Graduates the orphan per-segment `rpo-compliance-pct-<segment>` family to LIVE
re-ingest: the distribution RPO feed (per-(state, FY) Renewable Purchase
Obligation compliance %, along solar / non-solar / total segments) is re-keyed
from ECI st_code to LGD slug and split into one per-segment CSV. This is a
PERCENTAGE / non-fuel-axis family that does NOT fit the geo_by_fuel
file-class, so it keeps its existing per-facet `geo/*.csv` shape (Path B:
current shape, no new file-class). No mocks (Holy Law #7); tmp_path fixtures
only. The fixture pins the parser's real contract (faceted into solar /
non-solar / total) and the triple reproduces the on-disk source_id so a
re-emit is idempotent with the committed files.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.adapters.iced_discom.ingest import (
    _CSV_FILE_CLASS,
    _CSV_SOURCE_PRODUCER,
    _CSV_VARIABLE_PREFIX_RPO,
    _RPO_REINGEST_TITLE,
    _RPO_REINGEST_VINTAGE,
    build_rpo_compliance_variables,
    ingest_rpo_compliance,
)
from yen_gov.canonical.adapters.iced_discom.parsers import parse_rpo

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
        _CSV_SOURCE_PRODUCER, _RPO_REINGEST_TITLE, _RPO_REINGEST_VINTAGE
    )


def _stage_fk_targets(repo_root: Path, source_id: str) -> None:
    entities = repo_root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    (entities / "geo.csv").write_text(_GEO_CSV, encoding="utf-8")
    # The title contains commas, so it is quoted for well-formed CSV.
    (entities / "source.csv").write_text(
        "source_id,producer,title,vintage,url\n"
        f'{source_id},{_CSV_SOURCE_PRODUCER},"{_RPO_REINGEST_TITLE}",'
        f"{_RPO_REINGEST_VINTAGE},\n",
        encoding="utf-8",
    )


def _decrypted_response() -> dict:
    # /energy/electricity/distribution/rpo is AES on the wire; the staged blob
    # here is already plain JSON: {"data": [{state, fyear, solarCompliance,
    # nonSolarCompliance, totalCompliance}]}. The parser fans each state-year
    # row out into 3 facet rows (solar, non-solar, total). Two states (Title
    # Case for ENTITY_MAP).
    return {
        "data": [
            {
                "state": "Andhra Pradesh",
                "fyear": "2022-23",
                "solarCompliance": 7.5,
                "nonSolarCompliance": 12.0,
                "totalCompliance": 10.0,
            },
            {
                "state": "Maharashtra",
                "fyear": "2022-23",
                "solarCompliance": 50.0,
                "nonSolarCompliance": 60.0,
                "totalCompliance": 55.5,
            },
        ]
    }


def test_source_id_reproduces_on_disk():
    # The triple is pinned so a re-emit is idempotent with the committed files.
    assert _source_id() == "src-0ea63ed47704"


def test_build_rpo_compliance_splits_facets_and_translates():
    parsed, skipped = parse_rpo(_decrypted_response())
    assert skipped == 0
    by_variable = build_rpo_compliance_variables(parsed, source_id="src-x")
    # One variable_id per RPO segment facet.
    assert set(by_variable) == {
        f"{_CSV_VARIABLE_PREFIX_RPO}-solar",
        f"{_CSV_VARIABLE_PREFIX_RPO}-non-solar",
        f"{_CSV_VARIABLE_PREFIX_RPO}-total",
    }
    solar = {r["entity_id"]: r for r in by_variable[f"{_CSV_VARIABLE_PREFIX_RPO}-solar"]}
    # ECI st_codes (S01/S13) re-keyed to LGD slugs.
    assert set(solar) == {"andhra-pradesh", "maharashtra"}
    assert solar["andhra-pradesh"]["value"] == pytest.approx(7.5)
    # FY "2022-04" reduced to integer start year.
    assert solar["andhra-pradesh"]["time"] == 2022
    assert all(
        r["source_id"] == "src-x"
        for rows in by_variable.values()
        for r in rows
    )


def test_ingest_rpo_compliance_end_to_end_validates(tmp_path: Path):
    sid = _source_id()
    _stage_fk_targets(tmp_path, sid)
    raw_path = tmp_path / "distribution_rpo.json"
    raw_path.write_text(json.dumps(_decrypted_response()), encoding="utf-8")

    result = ingest_rpo_compliance(repo_root=tmp_path, raw_json_path=raw_path)

    assert result.skipped_unmapped == 0
    assert result.variable_ids == (
        f"{_CSV_VARIABLE_PREFIX_RPO}-non-solar",
        f"{_CSV_VARIABLE_PREFIX_RPO}-solar",
        f"{_CSV_VARIABLE_PREFIX_RPO}-total",
    )
    assert len(result.artifact_paths) == 3
    assert result.row_count == 6
    geo_dir = tmp_path / "datasets/data/datapoints/geo"
    for facet in ("solar", "non-solar", "total"):
        out = geo_dir / f"{_CSV_VARIABLE_PREFIX_RPO}-{facet}.csv"
        assert out.read_text(encoding="utf-8").splitlines()[0] == (
            "entity_id,time,value,source_id"
        )
        validate_csv(path=out, file_class=_CSV_FILE_CLASS, repo_root=tmp_path)
