"""Unit tests for ``yen_gov.canonical.reingest.election_events`` (B2b.4.4).

Stages a miniature fixture parquet + ``lgd_states.json`` under
``tmp_path`` and asserts the emitter's projection semantics including the
ECI ``state_code`` -> LGD ``state_entity_id`` re-key and ISO-date
serialisation. The real-corpus cross-format-parity gate lives in
``test_csv_parquet_parity.py::test_election_events``.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest.election_events import FILE_CLASS, emit


def _stage_parquet(
    path: Path,
    rows: list[
        tuple[str, str, str, str, str, str | None, str, str | None]
    ],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = ", ".join(
        "("
        + ", ".join(
            "NULL"
            if v is None
            else "DATE '" + v + "'"
            if i in (4, 5)
            else "'" + v.replace("'", "''") + "'"
            for i, v in enumerate(r)
        )
        + ")"
        for r in rows
    )
    duckdb.sql(
        "COPY (SELECT state_code, event_id, kind, display, polled_on, "
        "term_end_estimated, data_status, notes FROM (VALUES "
        + values
        + ") AS t(state_code, event_id, kind, display, polled_on, "
        f"term_end_estimated, data_status, notes)) TO '{path.as_posix()}' "
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


def test_emit_re_keys_state_code_and_iso_serialises_dates(tmp_path: Path) -> None:
    parquet_path = tmp_path / "election_events.parquet"
    out_path = tmp_path / "data" / "election_events.csv"
    lgd_states_json = tmp_path / "lgd_states.json"
    _stage_lgd_states(lgd_states_json)
    _stage_parquet(
        parquet_path,
        [
            ("S22", "AcGenMay2026", "assembly", "TN AC", "2026-05-10", "2031-05-09", "complete", None),
            ("U05", "AcGenFeb2025", "assembly", "Delhi AC", "2025-02-05", None, "complete", "note d"),
            ("S01", "AcGenApr2019", "assembly", "AP AC", "2019-04-11", "2024-04-10", "complete", None),
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
        "state_entity_id,event_id,kind,display,polled_on,"
        "term_end_estimated,data_status,notes"
    )
    # PK sort: (state_entity_id, event_id).
    assert lines[1].startswith("andhra-pradesh,AcGenApr2019,assembly,AP AC,2019-04-11,2024-04-10,complete,")
    assert lines[2].startswith("delhi,AcGenFeb2025,assembly,Delhi AC,2025-02-05,,complete,note d")
    assert lines[3].startswith("tamil-nadu,AcGenMay2026,assembly,TN AC,2026-05-10,2031-05-09,complete,")


def test_emit_raises_on_unknown_state_code(tmp_path: Path) -> None:
    parquet_path = tmp_path / "election_events.parquet"
    out_path = tmp_path / "data" / "election_events.csv"
    lgd_states_json = tmp_path / "lgd_states.json"
    _stage_lgd_states(lgd_states_json)
    _stage_parquet(
        parquet_path,
        [("S99", "AcGenJan2030", "assembly", "X", "2030-01-01", None, "complete", None)],
    )
    with pytest.raises(KeyError, match="S99"):
        emit(
            parquet_path=parquet_path,
            out_path=out_path,
            lgd_states_json=lgd_states_json,
        )


def test_emit_round_trips_through_validator(tmp_path: Path) -> None:
    parquet_path = tmp_path / "election_events.parquet"
    out_path = tmp_path / "data" / "election_events.csv"
    lgd_states_json = tmp_path / "lgd_states.json"
    _stage_lgd_states(lgd_states_json)
    _stage_parquet(
        parquet_path,
        [("S01", "AcGenApr2019", "assembly", "AP AC", "2019-04-11", "2024-04-10", "complete", "n")],
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
    target_in_repo = repo_root / "datasets" / "data" / "election_events.csv"
    target_in_repo.parent.mkdir(parents=True, exist_ok=True)
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
