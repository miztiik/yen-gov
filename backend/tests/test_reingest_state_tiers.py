"""Unit tests for ``yen_gov.canonical.reingest.state_tiers`` (B2b.4.3).

Stages a miniature fixture parquet + ``lgd_states.json`` under
``tmp_path`` and asserts the emitter's projection semantics including the
ECI ``state_code`` -> LGD ``state_entity_id`` re-key. The real-corpus
cross-format-parity gate lives in
``test_csv_parquet_parity.py::test_state_tiers``.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest.state_tiers import FILE_CLASS, emit


def _stage_parquet(
    path: Path,
    rows: list[
        tuple[str, str, str, str, str | None, str, str | None]
    ],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = ", ".join(
        "("
        + ", ".join(
            "NULL"
            if v is None
            else "'" + v.replace("'", "''") + "'"
            for v in r
        )
        + ")"
        for r in rows
    )
    duckdb.sql(
        "COPY (SELECT tier_id, tier_label, definition_kind, definition, "
        "authority, state_code, notes FROM (VALUES "
        + values
        + ") AS t(tier_id, tier_label, definition_kind, definition, "
        f"authority, state_code, notes)) TO '{path.as_posix()}' "
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


def test_emit_re_keys_state_code_and_sorts(tmp_path: Path) -> None:
    parquet_path = tmp_path / "state_tiers.parquet"
    out_path = tmp_path / "data" / "state_tiers.csv"
    lgd_states_json = tmp_path / "lgd_states.json"
    _stage_lgd_states(lgd_states_json)
    _stage_parquet(
        parquet_path,
        [
            ("z_tier", "Z label", "constitutional", "def z", "auth z", "S22", None),
            ("a_tier", "A label", "constitutional", "def a", None, "U05", "note a"),
            ("a_tier", "A label", "constitutional", "def a", None, "S01", None),
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
        "tier_id,tier_label,definition_kind,definition,authority,"
        "state_entity_id,notes"
    )
    # PK sort: (tier_id, state_entity_id). a_tier/andhra-pradesh first,
    # a_tier/delhi next, z_tier/tamil-nadu last.
    assert lines[1].startswith("a_tier,A label,constitutional,def a,,andhra-pradesh,")
    assert lines[2].startswith("a_tier,A label,constitutional,def a,,delhi,note a")
    assert lines[3].startswith("z_tier,Z label,constitutional,def z,auth z,tamil-nadu,")


def test_emit_raises_on_unknown_state_code(tmp_path: Path) -> None:
    parquet_path = tmp_path / "state_tiers.parquet"
    out_path = tmp_path / "data" / "state_tiers.csv"
    lgd_states_json = tmp_path / "lgd_states.json"
    _stage_lgd_states(lgd_states_json)
    _stage_parquet(
        parquet_path,
        [("t1", "T1", "constitutional", "def", "auth", "S99", None)],
    )
    with pytest.raises(KeyError, match="S99"):
        emit(
            parquet_path=parquet_path,
            out_path=out_path,
            lgd_states_json=lgd_states_json,
        )


def test_emit_round_trips_through_validator(tmp_path: Path) -> None:
    parquet_path = tmp_path / "state_tiers.parquet"
    out_path = tmp_path / "data" / "state_tiers.csv"
    lgd_states_json = tmp_path / "lgd_states.json"
    _stage_lgd_states(lgd_states_json)
    _stage_parquet(
        parquet_path,
        [("t1", "Tier one", "constitutional", "def one", "auth one", "S01", "n")],
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
    # Stage a minimal geo.csv carrying the FK target so the validator's
    # FK check passes.
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(
        "entity_id,name,parent,entity_kind,aliases\n"
        "andhra-pradesh,Andhra Pradesh,,state,\n",
        encoding="utf-8",
    )
    target_in_repo = repo_root / "datasets" / "data" / "state_tiers.csv"
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
