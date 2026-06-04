"""Unit tests for ``yen_gov.canonical.reingest.ac_crosswalk`` (B2b.4.6).

Stages a miniature fixture parquet + ``lgd_states.json`` under
``tmp_path`` and asserts the emitter's projection semantics including the
ECI ``state_code`` -> LGD ``state_entity_id`` re-key, nullable
``lgd_ac_id``, and PK sort. The real-corpus cross-format-parity gate
lives in ``test_csv_parquet_parity.py::test_ac_crosswalk``.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest.ac_crosswalk import FILE_CLASS, emit


def _stage_parquet(
    path: Path,
    rows: list[
        tuple[str, int, int | None, str, str, int, str, str]
    ],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = ", ".join(
        "("
        + ", ".join(
            "NULL"
            if v is None
            else str(v)
            if isinstance(v, int)
            else "'" + v.replace("'", "''") + "'"
            for v in r
        )
        + ")"
        for r in rows
    )
    duckdb.sql(
        "COPY (SELECT state_code, eci_no, lgd_ac_id, ac_id, ac_name, "
        "delim_year, match_method, source_id FROM (VALUES "
        + values
        + ") AS t(state_code, eci_no, lgd_ac_id, ac_id, ac_name, "
        f"delim_year, match_method, source_id)) TO '{path.as_posix()}' "
        "(FORMAT PARQUET)"
    )


def _stage_lgd_states(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "states": [
            {"eci_st_code": "S01", "slug": "andhra-pradesh"},
            {"eci_st_code": "S22", "slug": "tamil-nadu"},
            {"eci_st_code": "U05", "slug": "delhi"},
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_emit_re_keys_state_code_and_handles_null_lgd_ac_id(
    tmp_path: Path,
) -> None:
    parquet_path = tmp_path / "ac_crosswalk.parquet"
    out_path = tmp_path / "data" / "entities" / "ac_crosswalk.csv"
    lgd_states_json = tmp_path / "lgd_states.json"
    _stage_lgd_states(lgd_states_json)
    _stage_parquet(
        parquet_path,
        [
            ("S22", 5, 12345, "IN-S22-AC-2008-5", "TN5", 2008, "lgd_direct", "src-1"),
            ("U05", 1, None, "IN-U05-AC-2008-1", "DL1", 2008, "name_match", "src-1"),
            ("S01", 1, 28120, "IN-S01-AC-2008-1", "AP1", 2008, "lgd_direct", "src-1"),
            ("S01", 1, 28120, "IN-S01-AC-2002-1", "AP1-2002", 2002, "lgd_direct", "src-1"),
        ],
    )

    emitted = emit(
        parquet_path=parquet_path,
        out_path=out_path,
        lgd_states_json=lgd_states_json,
    )
    assert emitted == out_path
    text = out_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert "\r" not in text
    lines = text.splitlines()
    assert lines[0] == (
        "state_entity_id,delim_year,eci_no,lgd_ac_id,ac_id,ac_name,"
        "match_method,source_id"
    )
    # PK sort: (state_entity_id, delim_year, eci_no).
    assert lines[1].startswith(
        "andhra-pradesh,2002,1,28120,IN-S01-AC-2002-1,AP1-2002,lgd_direct,src-1"
    )
    assert lines[2].startswith(
        "andhra-pradesh,2008,1,28120,IN-S01-AC-2008-1,AP1,lgd_direct,src-1"
    )
    # delhi row has null lgd_ac_id -> empty field.
    assert lines[3].startswith(
        "delhi,2008,1,,IN-U05-AC-2008-1,DL1,name_match,src-1"
    )
    assert lines[4].startswith(
        "tamil-nadu,2008,5,12345,IN-S22-AC-2008-5,TN5,lgd_direct,src-1"
    )


def test_emit_raises_on_unknown_state_code(tmp_path: Path) -> None:
    parquet_path = tmp_path / "ac_crosswalk.parquet"
    out_path = tmp_path / "data" / "entities" / "ac_crosswalk.csv"
    lgd_states_json = tmp_path / "lgd_states.json"
    _stage_lgd_states(lgd_states_json)
    _stage_parquet(
        parquet_path,
        [("S99", 1, 1, "IN-S99-AC-2008-1", "X", 2008, "lgd_direct", "src-1")],
    )
    with pytest.raises(KeyError, match="S99"):
        emit(
            parquet_path=parquet_path,
            out_path=out_path,
            lgd_states_json=lgd_states_json,
        )


def test_emit_round_trips_through_validator(tmp_path: Path) -> None:
    parquet_path = tmp_path / "ac_crosswalk.parquet"
    out_path = tmp_path / "data" / "entities" / "ac_crosswalk.csv"
    lgd_states_json = tmp_path / "lgd_states.json"
    _stage_lgd_states(lgd_states_json)
    _stage_parquet(
        parquet_path,
        [("S01", 1, 28120, "IN-S01-AC-2008-1", "AP1", 2008, "lgd_direct", "src-1")],
    )
    emit(
        parquet_path=parquet_path,
        out_path=out_path,
        lgd_states_json=lgd_states_json,
    )
    repo_root = tmp_path / "repo"
    schema_target = repo_root / "datasets" / "data" / "_schema"
    schema_target.mkdir(parents=True)
    src_schema = (
        Path(__file__).resolve().parents[2]
        / "datasets"
        / "data"
        / "_schema"
    )
    for name in ("columns.json", "columns.schema.json"):
        (schema_target / name).write_text(
            (src_schema / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(
        "entity_id,name,parent,entity_kind,aliases\n"
        "andhra-pradesh,Andhra Pradesh,,state,\n",
        encoding="utf-8",
    )
    source = repo_root / "datasets" / "data" / "entities" / "source.csv"
    source.write_text(
        "source_id,producer,title,vintage,url\n"
        "src-1,Producer,Title,2008,https://example.org\n",
        encoding="utf-8",
    )
    target_in_repo = (
        repo_root / "datasets" / "data" / "entities" / "ac_crosswalk.csv"
    )
    target_in_repo.write_text(
        out_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    validate_csv(
        path=target_in_repo, file_class=FILE_CLASS, repo_root=repo_root
    )


def test_emit_raises_when_parquet_missing(tmp_path: Path) -> None:
    lgd_states_json = tmp_path / "lgd_states.json"
    _stage_lgd_states(lgd_states_json)
    with pytest.raises(FileNotFoundError):
        emit(
            parquet_path=tmp_path / "absent.parquet",
            out_path=tmp_path / "out.csv",
            lgd_states_json=lgd_states_json,
        )
