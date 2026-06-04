"""Unit tests for ``yen_gov.canonical.reingest.energy_datapoints`` (B2b.1).

These tests stage miniature fixture parquets under ``tmp_path`` and assert
the emitter's projection semantics, including the ECI -> LGD entity re-key.
The real-corpus cross-format-parity gate lives in
``test_csv_parquet_parity.py::test_energy``.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.reingest.energy_datapoints import (
    FILE_CLASS,
    emit,
    load_eci_to_slug,
)


def _stage_lgd_states(path: Path) -> None:
    payload = {
        "states": [
            {"lgd_state_id": 32, "slug": "tamil-nadu", "eci_st_code": "S22"},
            {"lgd_state_id": 8, "slug": "himachal-pradesh", "eci_st_code": "S08"},
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


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
def staged(tmp_path: Path) -> tuple[Path, Path, Path]:
    parquet_dir = tmp_path / "energy"
    parquet_dir.mkdir()
    lgd_states = tmp_path / "lgd_states.json"
    out_dir = tmp_path / "data" / "datapoints" / "geo"
    _stage_lgd_states(lgd_states)
    _stage_parquet(
        parquet_dir / "energy_fixture.parquet",
        [
            ("obs1", "IN", 2020, "2020", 1, "demo-ind", 100.5, None, "src-aaa", "raw"),
            ("obs2", "IN-S22", 2020, "2020", 1, "demo-ind", 33.0, None, "src-aaa", "raw"),
            ("obs3", "IN-S08", 2021, "2021", 1, "demo-ind", 44.0, None, "src-aaa", "raw"),
            ("obs4", "IN-S22", 2021, "2021", 1, "other-ind", 7.7, None, "src-bbb", "raw"),
        ],
    )
    return parquet_dir, lgd_states, out_dir


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


def test_emit_projects_and_remaps_entities(staged) -> None:
    parquet_dir, lgd_states, out_dir = staged
    emitted = emit(parquet_dir=parquet_dir, lgd_states_json=lgd_states, out_dir=out_dir)
    names = sorted(p.name for p in emitted)
    assert names == ["demo-ind.csv", "other-ind.csv"]

    demo = (out_dir / "demo-ind.csv").read_text(encoding="utf-8").splitlines()
    assert demo[0] == "entity_id,time,value,source_id"
    # Sort is by PK (entity_id, time); slugs sort before "IN" lexically.
    assert demo[1:] == [
        "IN,2020,100.5,src-aaa",
        "himachal-pradesh,2021,44,src-aaa",
        "tamil-nadu,2020,33,src-aaa",
    ]
    other = (out_dir / "other-ind.csv").read_text(encoding="utf-8").splitlines()
    assert other[1:] == ["tamil-nadu,2021,7.7,src-bbb"]


def test_emit_rejects_unknown_eci_code(staged, tmp_path: Path) -> None:
    parquet_dir, _lgd, out_dir = staged
    # A register that drops S22 deliberately.
    register = tmp_path / "lgd_states_partial.json"
    register.write_text(
        json.dumps({"states": [{"lgd_state_id": 8, "slug": "himachal-pradesh", "eci_st_code": "S08"}]}),
        encoding="utf-8",
    )
    with pytest.raises(KeyError, match="S22"):
        emit(parquet_dir=parquet_dir, lgd_states_json=register, out_dir=out_dir)


def test_emit_rejects_unknown_entity_shape(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "energy"
    parquet_dir.mkdir()
    lgd_states = tmp_path / "lgd_states.json"
    _stage_lgd_states(lgd_states)
    _stage_parquet(
        parquet_dir / "bad.parquet",
        [("o1", "ZZ-S01", 2020, "2020", 1, "x", 1.0, None, "src-x", "raw")],
    )
    with pytest.raises(ValueError, match="unrecognised entity_id"):
        emit(parquet_dir=parquet_dir, lgd_states_json=lgd_states, out_dir=tmp_path / "out")


def test_file_class_constant_matches_columns_contract() -> None:
    # Cheap guard against the glob drifting.
    assert FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
