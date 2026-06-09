"""Tests for B2a.5 entities/geo.csv emitter (sub-plan)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed.geo_csv import FILE_CLASS, emit


def _stage(path: Path, key: str, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({key: entries}), encoding="utf-8")


def _state(**overrides) -> dict:
    base = {
        "lgd_state_id": 32,
        "lgd_name": "Tamil Nadu",
        "lgd_name_short": "Tamil Nadu",
        "iso_alpha": "IN-TN",
        "slug": "tamil-nadu",
        "eci_st_code": "S22",
    }
    base.update(overrides)
    return base


def _district(**overrides) -> dict:
    base = {
        "lgd_district_id": 571,
        "lgd_state_id": 32,
        "lgd_name": "Chennai",
        "slug": "chennai",
    }
    base.update(overrides)
    return base


def _stage_pair(tmp_path: Path, states: list[dict], districts: list[dict]) -> tuple[Path, Path]:
    s = tmp_path / "lgd_states.json"
    d = tmp_path / "lgd_districts.json"
    _stage(s, "states", states)
    _stage(d, "districts", districts)
    return s, d


def test_emit_minimal_ladder(tmp_path):
    s, d = _stage_pair(tmp_path, [_state()], [_district()])
    out = tmp_path / "datasets" / "data" / "entities" / "geo.csv"
    emit(lgd_states_json=s, lgd_districts_json=d, out_path=out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code"
    # 1 country + 2 derived national-reference pseudo-entities (G31a)
    # + 1 state + 1 district = 5 rows
    assert len(lines) == 6
    body = "\n".join(lines[1:])
    assert "IN,India,,country,IN|IND|356,," in body
    # G31a derived pseudo-entities live alongside IN with the same
    # entity_kind and parent=IN; see DERIVED_NATIONAL_REFERENCE_ENTITIES
    # in backend/yen_gov/canonical/seed/geo_csv.py.
    assert "IN-median,India (median of states),IN,country,,," in body
    assert "IN-pop-weighted,India (population-weighted average),IN,country,,," in body
    # eci_st_code (S22) is RETAINED on the alias until the 0e decommission sweep;
    # no census snapshot supplied here, so census cells are empty.
    assert "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:32,," in body
    assert "tamil-nadu/chennai,Chennai,tamil-nadu,district,lgd:571,," in body


def test_emit_disambiguates_district_slug_across_states(tmp_path):
    states = [
        _state(lgd_state_id=2, slug="himachal-pradesh", lgd_name="Himachal Pradesh", iso_alpha="IN-HP", eci_st_code="S08"),
        _state(lgd_state_id=22, slug="chhattisgarh", lgd_name="Chhattisgarh", iso_alpha="IN-CG", eci_st_code="S26"),
    ]
    districts = [
        _district(lgd_district_id=10, lgd_state_id=2, slug="bilaspur", lgd_name="Bilaspur"),
        _district(lgd_district_id=20, lgd_state_id=22, slug="bilaspur", lgd_name="Bilaspur"),
    ]
    s, d = _stage_pair(tmp_path, states, districts)
    out = tmp_path / "geo.csv"
    emit(lgd_states_json=s, lgd_districts_json=d, out_path=out)
    body = out.read_text(encoding="utf-8")
    assert "himachal-pradesh/bilaspur" in body
    assert "chhattisgarh/bilaspur" in body


def test_emit_rejects_unknown_state_fk(tmp_path):
    s, d = _stage_pair(
        tmp_path,
        [_state()],
        [_district(lgd_state_id=999)],
    )
    with pytest.raises(ValueError, match="unknown lgd_state_id"):
        emit(lgd_states_json=s, lgd_districts_json=d, out_path=tmp_path / "out.csv")


def test_emit_rejects_double_underscore_state_slug(tmp_path):
    s, d = _stage_pair(
        tmp_path,
        [_state(slug="bad__slug")],
        [],
    )
    with pytest.raises(ValueError, match="must not contain '__'"):
        emit(lgd_states_json=s, lgd_districts_json=d, out_path=tmp_path / "out.csv")


def test_emit_rejects_duplicate_state(tmp_path):
    s, d = _stage_pair(
        tmp_path,
        [_state(), _state(lgd_state_id=33)],
        [],
    )
    with pytest.raises(ValueError, match="duplicate state entity_id"):
        emit(lgd_states_json=s, lgd_districts_json=d, out_path=tmp_path / "out.csv")


def test_emit_rejects_missing_state_slug(tmp_path):
    bad = _state()
    bad.pop("slug")
    s, d = _stage_pair(tmp_path, [bad], [])
    with pytest.raises(ValueError, match="missing 'slug'"):
        emit(lgd_states_json=s, lgd_districts_json=d, out_path=tmp_path / "out.csv")


def test_emitted_csv_passes_validator(tmp_path):
    states = [
        _state(),
        _state(lgd_state_id=2, slug="himachal-pradesh", lgd_name="Himachal Pradesh", iso_alpha="IN-HP", eci_st_code="S08"),
    ]
    districts = [
        _district(),
        _district(lgd_district_id=42, lgd_state_id=2, slug="shimla", lgd_name="Shimla"),
    ]
    s, d = _stage_pair(tmp_path, states, districts)
    repo_root = tmp_path
    out = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    emit(lgd_states_json=s, lgd_districts_json=d, out_path=out)
    validate_csv(path=out, file_class=FILE_CLASS, repo_root=repo_root)


def _stage_snapshot(tmp_path: Path, states: list[list[str]], districts: list[list[str]]) -> tuple[Path, Path]:
    import csv

    sp = tmp_path / "lgd" / "states.csv"
    dp = tmp_path / "lgd" / "districts.csv"
    sp.parent.mkdir(parents=True, exist_ok=True)
    with sp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["lgd_state_code", "state_name", "state_name_local", "census_2001_code", "census_2011_code", "kind"])
        for r in states:
            w.writerow(r)
    with dp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["lgd_state_code", "state_name", "lgd_district_code", "district_name", "census_2001_code", "census_2011_code"])
        for r in districts:
            w.writerow(r)
    return sp, dp


def test_census_columns_joined_from_snapshot(tmp_path):
    """Census LABEL columns are joined from the LGD snapshot by LGD code."""
    s, d = _stage_pair(tmp_path, [_state()], [_district()])
    sp, dp = _stage_snapshot(
        tmp_path,
        [["32", "Tamil Nadu", "TAMIL NADU", "33", "33", "state"]],
        [["32", "Tamil Nadu", "571", "Chennai", "4", "38"]],
    )
    out = tmp_path / "geo.csv"
    emit(
        lgd_states_json=s,
        lgd_districts_json=d,
        out_path=out,
        lgd_snapshot_states_csv=sp,
        lgd_snapshot_districts_csv=dp,
    )
    body = out.read_text(encoding="utf-8")
    assert "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:32,33,33" in body
    assert "tamil-nadu/chennai,Chennai,tamil-nadu,district,lgd:571,4,38" in body


def test_long_name_synonym_in_state_alias(tmp_path):
    """A state whose display name is the short form carries the long name as an alias synonym."""
    s, d = _stage_pair(
        tmp_path,
        [_state(lgd_state_id=1, slug="jammu-and-kashmir", lgd_name="Jammu And Kashmir", lgd_name_short="Jammu & Kashmir", iso_alpha="IN-JK", eci_st_code="U08")],
        [],
    )
    out = tmp_path / "geo.csv"
    emit(lgd_states_json=s, lgd_districts_json=d, out_path=out)
    body = out.read_text(encoding="utf-8")
    # name shows the short form; the long official name rides the alias for search
    assert "jammu-and-kashmir,Jammu & Kashmir,IN,state,IN-JK|U08|lgd:1|Jammu And Kashmir" in body
