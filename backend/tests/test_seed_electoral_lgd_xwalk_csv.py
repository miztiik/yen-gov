"""Tests for B2a.7 entities/electoral_lgd_xwalk.csv emitter (sub-plan)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed.electoral_lgd_xwalk_csv import FILE_CLASS, emit


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
        "lgd_district_id": 600,
        "lgd_state_id": 32,
        "lgd_name": "Chennai",
        "slug": "chennai",
    }
    base.update(overrides)
    return base


def _ac(**overrides) -> dict:
    base = {
        "lgd_ac_id": 4000,
        "lgd_state_id": 32,
        "lgd_pc_id": 500,
        "ac_name": "Mylapore",
        "slug": "mylapore",
    }
    base.update(overrides)
    return base


def _map_row(**overrides) -> dict:
    base = {
        "lgd_state_id": 32,
        "lgd_ac_id": 4000,
        "lgd_district_ids": [600],
    }
    base.update(overrides)
    return base


def _stage(
    tmp_path: Path,
    *,
    states: list[dict],
    districts: list[dict],
    acs: list[dict],
    map_rows: list[dict],
    fetched_at: str = "2026-06-01T21:38:00Z",
) -> tuple[Path, Path, Path, Path]:
    s = tmp_path / "lgd_states.json"
    d = tmp_path / "lgd_districts.json"
    a = tmp_path / "lgd_acs.json"
    m = tmp_path / "lgd_ac_pc_district_map.json"
    s.write_text(json.dumps({"states": states}), encoding="utf-8")
    d.write_text(json.dumps({"districts": districts}), encoding="utf-8")
    a.write_text(json.dumps({"acs": acs}), encoding="utf-8")
    m.write_text(
        json.dumps(
            {
                "sources": [{"fetched_at": fetched_at, "name": "LGD"}],
                "rows": map_rows,
            }
        ),
        encoding="utf-8",
    )
    return s, a, d, m


def test_emit_minimal_single_district_ac(tmp_path):
    s, a, d, m = _stage(
        tmp_path,
        states=[_state()],
        districts=[_district()],
        acs=[_ac()],
        map_rows=[_map_row()],
    )
    out = tmp_path / "datasets" / "data" / "entities" / "electoral_lgd_xwalk.csv"
    emit(
        lgd_states_json=s,
        lgd_acs_json=a,
        lgd_districts_json=d,
        ac_pc_district_map_json=m,
        out_path=out,
    )
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "electoral_id,lgd_district_id,delim_year,boundary_snapshot,overlap_kind"
    assert len(lines) == 2
    assert lines[1] == (
        "IN-AC-2008-tamil-nadu-4000,tamil-nadu/chennai,2008,lgd:2026-06-01,wholly_inside"
    )


def test_emit_multi_district_ac_marks_partial(tmp_path):
    districts = [_district(), _district(lgd_district_id=601, slug="kanchipuram")]
    map_rows = [_map_row(lgd_district_ids=[600, 601])]
    s, a, d, m = _stage(
        tmp_path,
        states=[_state()],
        districts=districts,
        acs=[_ac()],
        map_rows=map_rows,
    )
    out = tmp_path / "out.csv"
    emit(
        lgd_states_json=s,
        lgd_acs_json=a,
        lgd_districts_json=d,
        ac_pc_district_map_json=m,
        out_path=out,
    )
    body = out.read_text(encoding="utf-8").splitlines()[1:]
    assert len(body) == 2
    assert all(",partial" in line for line in body)


def test_emit_rejects_unknown_ac_in_map(tmp_path):
    s, a, d, m = _stage(
        tmp_path,
        states=[_state()],
        districts=[_district()],
        acs=[_ac()],
        map_rows=[_map_row(lgd_ac_id=9999)],
    )
    with pytest.raises(ValueError, match="ac 9999 not present in lgd_acs.json"):
        emit(
            lgd_states_json=s,
            lgd_acs_json=a,
            lgd_districts_json=d,
            ac_pc_district_map_json=m,
            out_path=tmp_path / "out.csv",
        )


def test_emit_rejects_unknown_district_in_map(tmp_path):
    s, a, d, m = _stage(
        tmp_path,
        states=[_state()],
        districts=[_district()],
        acs=[_ac()],
        map_rows=[_map_row(lgd_district_ids=[9999])],
    )
    with pytest.raises(ValueError, match="references unknown lgd_district_id=9999"):
        emit(
            lgd_states_json=s,
            lgd_acs_json=a,
            lgd_districts_json=d,
            ac_pc_district_map_json=m,
            out_path=tmp_path / "out.csv",
        )


def test_emit_rejects_unknown_state_in_map(tmp_path):
    s, a, d, m = _stage(
        tmp_path,
        states=[_state()],
        districts=[_district()],
        acs=[_ac()],
        map_rows=[_map_row(lgd_state_id=999)],
    )
    with pytest.raises(ValueError, match="references unknown lgd_state_id=999"):
        emit(
            lgd_states_json=s,
            lgd_acs_json=a,
            lgd_districts_json=d,
            ac_pc_district_map_json=m,
            out_path=tmp_path / "out.csv",
        )


def test_emit_rejects_empty_district_list(tmp_path):
    s, a, d, m = _stage(
        tmp_path,
        states=[_state()],
        districts=[_district()],
        acs=[_ac()],
        map_rows=[_map_row(lgd_district_ids=[])],
    )
    with pytest.raises(ValueError, match="'lgd_district_ids' must be non-empty list"):
        emit(
            lgd_states_json=s,
            lgd_acs_json=a,
            lgd_districts_json=d,
            ac_pc_district_map_json=m,
            out_path=tmp_path / "out.csv",
        )


def test_emit_rejects_duplicate_pair(tmp_path):
    s, a, d, m = _stage(
        tmp_path,
        states=[_state()],
        districts=[_district()],
        acs=[_ac()],
        map_rows=[_map_row(), _map_row()],
    )
    with pytest.raises(ValueError, match="duplicate xwalk row"):
        emit(
            lgd_states_json=s,
            lgd_acs_json=a,
            lgd_districts_json=d,
            ac_pc_district_map_json=m,
            out_path=tmp_path / "out.csv",
        )


def test_emit_rejects_double_underscore_in_state_slug(tmp_path):
    s, a, d, m = _stage(
        tmp_path,
        states=[_state(slug="bad__slug")],
        districts=[_district()],
        acs=[_ac()],
        map_rows=[_map_row()],
    )
    with pytest.raises(ValueError, match="must not contain '__'"):
        emit(
            lgd_states_json=s,
            lgd_acs_json=a,
            lgd_districts_json=d,
            ac_pc_district_map_json=m,
            out_path=tmp_path / "out.csv",
        )


def test_boundary_snapshot_derived_from_source_fetched_at(tmp_path):
    s, a, d, m = _stage(
        tmp_path,
        states=[_state()],
        districts=[_district()],
        acs=[_ac()],
        map_rows=[_map_row()],
        fetched_at="2025-12-15T01:02:03Z",
    )
    out = tmp_path / "out.csv"
    emit(
        lgd_states_json=s,
        lgd_acs_json=a,
        lgd_districts_json=d,
        ac_pc_district_map_json=m,
        out_path=out,
    )
    body = out.read_text(encoding="utf-8")
    assert "lgd:2025-12-15" in body


def test_emit_rejects_missing_sources_block(tmp_path):
    s, a, d, m = _stage(
        tmp_path,
        states=[_state()],
        districts=[_district()],
        acs=[_ac()],
        map_rows=[_map_row()],
    )
    # Re-write map file without sources.
    m.write_text(json.dumps({"rows": [_map_row()]}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing 'sources'"):
        emit(
            lgd_states_json=s,
            lgd_acs_json=a,
            lgd_districts_json=d,
            ac_pc_district_map_json=m,
            out_path=tmp_path / "out.csv",
        )


def test_sort_by_pk_columns(tmp_path):
    """Two ACs from same state with multi-district coverage; rows sort by
    (electoral_id, lgd_district_id, delim_year) per columns.json PK."""
    districts = [
        _district(lgd_district_id=600, slug="chennai"),
        _district(lgd_district_id=601, slug="kanchipuram"),
    ]
    acs = [
        _ac(lgd_ac_id=4000, ac_name="A"),
        _ac(lgd_ac_id=4001, ac_name="B"),
    ]
    map_rows = [
        # Author out of order on purpose.
        _map_row(lgd_ac_id=4001, lgd_district_ids=[601, 600]),
        _map_row(lgd_ac_id=4000, lgd_district_ids=[601, 600]),
    ]
    s, a, d, m = _stage(
        tmp_path,
        states=[_state()],
        districts=districts,
        acs=acs,
        map_rows=map_rows,
    )
    out = tmp_path / "out.csv"
    emit(
        lgd_states_json=s,
        lgd_acs_json=a,
        lgd_districts_json=d,
        ac_pc_district_map_json=m,
        out_path=out,
    )
    body = out.read_text(encoding="utf-8").splitlines()[1:]
    electoral_ids = [line.split(",")[0] for line in body]
    district_ids = [line.split(",")[1] for line in body]
    assert electoral_ids == [
        "IN-AC-2008-tamil-nadu-4000",
        "IN-AC-2008-tamil-nadu-4000",
        "IN-AC-2008-tamil-nadu-4001",
        "IN-AC-2008-tamil-nadu-4001",
    ]
    assert district_ids[0] < district_ids[1]
    assert district_ids[2] < district_ids[3]


def test_emitted_csv_passes_validator_with_full_fk_closure(tmp_path):
    """End-to-end: emit geo.csv + electoral.csv (FK predecessors) + the
    xwalk and confirm the cross-file FK validator accepts the triple
    (sub-row gate ``fk-validator``)."""
    from yen_gov.canonical.seed.electoral_csv import emit as electoral_emit
    from yen_gov.canonical.seed.geo_csv import emit as geo_emit

    repo_root = tmp_path / "repo"
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    states = [_state()]
    districts = [_district()]
    acs = [_ac()]
    pcs = [
        {
            "lgd_pc_id": 500,
            "lgd_state_id": 32,
            "pc_name": "Chennai South",
            "slug": "chennai-south",
        }
    ]
    map_rows = [_map_row()]

    s, a, d, m = _stage(
        src_dir,
        states=states,
        districts=districts,
        acs=acs,
        map_rows=map_rows,
    )
    pcs_json = src_dir / "lgd_pcs.json"
    pcs_json.write_text(json.dumps({"pcs": pcs}), encoding="utf-8")

    geo_out = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo_emit(lgd_states_json=s, lgd_districts_json=d, out_path=geo_out)

    electoral_out = repo_root / "datasets" / "data" / "entities" / "electoral.csv"
    electoral_emit(
        lgd_states_json=s,
        lgd_acs_json=a,
        lgd_pcs_json=pcs_json,
        out_path=electoral_out,
    )

    xwalk_out = (
        repo_root / "datasets" / "data" / "entities" / "electoral_lgd_xwalk.csv"
    )
    emit(
        lgd_states_json=s,
        lgd_acs_json=a,
        lgd_districts_json=d,
        ac_pc_district_map_json=m,
        out_path=xwalk_out,
    )
    validate_csv(path=xwalk_out, file_class=FILE_CLASS, repo_root=repo_root)
