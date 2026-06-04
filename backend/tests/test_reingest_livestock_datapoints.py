"""Unit tests for ``yen_gov.canonical.reingest.livestock_datapoints`` (B2b.2).

These tests stage miniature fixture parquets + geo.csv + lgd_states.json
under ``tmp_path`` and assert the emitter's projection semantics, including
the ECI -> LGD state slug AND the LGD-district -> ``state/district`` slug
re-keys. The real-corpus cross-format-parity gate lives in
``test_csv_parquet_parity.py::test_livestock``.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.reingest.livestock_datapoints import (
    FILE_CLASS,
    emit,
    load_eci_to_slug,
    load_lgd_district_to_geo_entity,
)


def _stage_lgd_states(path: Path) -> None:
    payload = {
        "states": [
            {"lgd_state_id": 32, "slug": "tamil-nadu", "eci_st_code": "S22"},
            {"lgd_state_id": 8, "slug": "himachal-pradesh", "eci_st_code": "S08"},
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stage_geo_entities(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "entity_id,name,parent,entity_kind,aliases\n"
        "IN,India,,country,IN|IND|356\n"
        "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:32\n"
        "tamil-nadu/coimbatore,Coimbatore,tamil-nadu,district,lgd:579\n"
        "himachal-pradesh,Himachal Pradesh,IN,state,IN-HP|S08|lgd:8\n"
        "himachal-pradesh/shimla,Shimla,himachal-pradesh,district,lgd:23\n",
        encoding="utf-8",
    )


def _stage_parquet(
    path: Path,
    rows: list[tuple[str, str, int, str, int, str, float | None, str | None, str, str]],
) -> None:
    # rows: observation_id, entity_id, year, period_label, period_seq,
    #       indicator_id, value_numeric, value_text, source_id, derivation
    path.parent.mkdir(parents=True, exist_ok=True)
    values = ", ".join(
        "("
        + ", ".join(
            "NULL" if v is None else (f"'{v}'" if isinstance(v, str) else repr(v))
            for v in r
        )
        + ")"
        for r in rows
    )
    rel = duckdb.sql(
        "SELECT observation_id, entity_id, \"year\", period_label, period_seq, "
        "indicator_id, value_numeric::DOUBLE AS value_numeric, value_text, "
        "source_id, derivation FROM (VALUES "
        + values
        + ") AS t(observation_id, entity_id, \"year\", period_label, period_seq, "
        "indicator_id, value_numeric, value_text, source_id, derivation)"
    )
    duckdb.sql(f"COPY ({rel.sql_query()}) TO '{path.as_posix()}' (FORMAT PARQUET)")


@pytest.fixture
def staged(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    parquet_dir = tmp_path / "livestock"
    parquet_dir.mkdir()
    lgd_states = tmp_path / "lgd_states.json"
    geo_csv = tmp_path / "data" / "entities" / "geo.csv"
    out_dir = tmp_path / "data" / "datapoints" / "geo"
    _stage_lgd_states(lgd_states)
    _stage_geo_entities(geo_csv)
    _stage_parquet(
        parquet_dir / "livestock_fixture.parquet",
        [
            ("obs1", "IN", 2020, "2020-21", 1, "ls-ind", 100.5, None, "src-aaa", "sum"),
            ("obs2", "IN-S22", 2020, "2020-21", 1, "ls-ind", 33.0, None, "src-aaa", "sum"),
            ("obs3", "IN-S08", 2021, "2021-22", 1, "ls-ind", 44.0, None, "src-aaa", "sum"),
            ("obs4", "IN-S22-D579", 2021, "2021-22", 1, "ls-ind", 7.7, None, "src-bbb", "sum"),
            ("obs5", "IN-S08-D23", 2021, "2021-22", 1, "other-ind", 11.0, None, "src-bbb", "sum"),
        ],
    )
    return parquet_dir, lgd_states, geo_csv, out_dir


def test_load_eci_to_slug_skips_rows_without_eci_code(tmp_path: Path) -> None:
    register = tmp_path / "lgd_states.json"
    register.write_text(
        json.dumps(
            {
                "states": [
                    {"lgd_state_id": 1, "slug": "a", "eci_st_code": "S01"},
                    {"lgd_state_id": 2, "slug": "no-eci"},
                    {"lgd_state_id": 3, "eci_st_code": "S03"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert load_eci_to_slug(register) == {"S01": "a"}


def test_load_lgd_district_to_geo_entity_only_districts(tmp_path: Path) -> None:
    geo_csv = tmp_path / "geo.csv"
    _stage_geo_entities(geo_csv)
    mapping = load_lgd_district_to_geo_entity(geo_csv)
    assert mapping == {
        "579": "tamil-nadu/coimbatore",
        "23": "himachal-pradesh/shimla",
    }


def test_emit_projects_and_remaps_entities(staged) -> None:
    parquet_dir, lgd_states, geo_csv, out_dir = staged
    emitted = emit(
        parquet_dir=parquet_dir,
        lgd_states_json=lgd_states,
        geo_entities_csv=geo_csv,
        out_dir=out_dir,
    )
    names = sorted(p.name for p in emitted)
    assert names == ["ls-ind.csv", "other-ind.csv"]

    ls = (out_dir / "ls-ind.csv").read_text(encoding="utf-8").splitlines()
    assert ls[0] == "entity_id,time,value,source_id"
    # Sort is by PK (entity_id, time); slugs sort before "IN" lexically.
    assert ls[1:] == [
        "IN,2020,100.5,src-aaa",
        "himachal-pradesh,2021,44,src-aaa",
        "tamil-nadu,2020,33,src-aaa",
        "tamil-nadu/coimbatore,2021,7.7,src-bbb",
    ]
    other = (out_dir / "other-ind.csv").read_text(encoding="utf-8").splitlines()
    assert other[1:] == ["himachal-pradesh/shimla,2021,11,src-bbb"]


def test_emit_rejects_unknown_eci_code(staged, tmp_path: Path) -> None:
    parquet_dir, _lgd, geo_csv, out_dir = staged
    register = tmp_path / "lgd_states_partial.json"
    register.write_text(
        json.dumps(
            {"states": [{"lgd_state_id": 8, "slug": "himachal-pradesh", "eci_st_code": "S08"}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(KeyError, match="S22"):
        emit(
            parquet_dir=parquet_dir,
            lgd_states_json=register,
            geo_entities_csv=geo_csv,
            out_dir=out_dir,
        )


def test_emit_rejects_unknown_district_id(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "livestock"
    parquet_dir.mkdir()
    lgd_states = tmp_path / "lgd_states.json"
    geo_csv = tmp_path / "data" / "entities" / "geo.csv"
    _stage_lgd_states(lgd_states)
    _stage_geo_entities(geo_csv)
    _stage_parquet(
        parquet_dir / "bad.parquet",
        [("o1", "IN-S22-D99999", 2020, "2020-21", 1, "x", 1.0, None, "src-x", "sum")],
    )
    with pytest.raises(KeyError, match="99999"):
        emit(
            parquet_dir=parquet_dir,
            lgd_states_json=lgd_states,
            geo_entities_csv=geo_csv,
            out_dir=tmp_path / "out",
        )


def test_emit_rejects_unknown_entity_shape(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "livestock"
    parquet_dir.mkdir()
    lgd_states = tmp_path / "lgd_states.json"
    geo_csv = tmp_path / "data" / "entities" / "geo.csv"
    _stage_lgd_states(lgd_states)
    _stage_geo_entities(geo_csv)
    _stage_parquet(
        parquet_dir / "bad.parquet",
        [("o1", "ZZ-S01", 2020, "2020-21", 1, "x", 1.0, None, "src-x", "sum")],
    )
    with pytest.raises(ValueError, match="unrecognised entity_id"):
        emit(
            parquet_dir=parquet_dir,
            lgd_states_json=lgd_states,
            geo_entities_csv=geo_csv,
            out_dir=tmp_path / "out",
        )


def test_file_class_constant_matches_columns_contract() -> None:
    assert FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
