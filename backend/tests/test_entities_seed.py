"""Tier-A tests for ``yen_gov.canonical.entities_seed``.

Per CLAUDE.md §15, ``tmp_path`` fixtures only.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.entities_seed import (
    ENTITIES_ROW_SCHEMA_VERSION,
    compile_to_parquet,
)


def _write_entities(tmp_path: Path) -> Path:
    payload = {
        "$schema": "./entity.schema.json",
        "$schema_version": "1.1",
        "entities": [
            {
                "entity_id": "IN",
                "entity_type": "country",
                "entity_level": "country",
                "entity_code": "IN",
                "display_name": "India",
                "entity_valid_from": 1947,
            },
            {
                "entity_id": "IN-S22",
                "entity_type": "state",
                "entity_level": "state",
                "entity_code": "S22",
                "display_name": "Tamil Nadu",
                "parent_entity_id": "IN",
                "entity_valid_from": 1969,
                "iso_3166_2": "IN-TN",
            },
        ],
    }
    p = tmp_path / "entities.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _write_districts(state_dir: Path, payload: dict) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    p = state_dir / "districts.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _read(parquet: Path) -> list[tuple]:
    con = duckdb.connect()
    try:
        return con.execute(
            f"SELECT entity_id, entity_type, parent_entity_id, lgd_code, legacy_id, "
            f"display_name, entity_valid_from "
            f"FROM read_parquet('{parquet.as_posix()}') ORDER BY entity_type, entity_id"
        ).fetchall()
    finally:
        con.close()


def test_compile_lifts_districts_with_legacy_id(tmp_path):
    entities_json = _write_entities(tmp_path)
    s22_dir = tmp_path / "reference" / "S22"
    _write_districts(s22_dir, {
        "$schema": "./district.schema.json",
        "$schema_version": "3.4",
        "sources": [],
        "state": "S22",
        "districts": [
            {
                "id": "ARI",
                "id_source": "wikipedia",
                "name": "Ariyalur",
                "lgd_code": "610",
                "created_on": "2007-12-12",
                "headquarters": "Ariyalur",
            },
            {
                "id": "chennai",
                "id_source": "wikipedia",
                "name": "Chennai",
                "lgd_code": "503",
                "headquarters": "Chennai",
            },
        ],
    })
    out = tmp_path / "entities.parquet"
    n = compile_to_parquet(entities_json, [s22_dir / "districts.json"], out)
    assert n == 4  # 2 base + 2 districts
    rows = _read(out)
    by_id = {r[0]: r for r in rows}
    ari = by_id["IN-S22-D610"]
    assert ari[1] == "district"
    assert ari[2] == "IN-S22"  # parent_entity_id
    assert ari[3] == "610"  # lgd_code
    assert ari[4] == "ARI"  # legacy_id (Wikipedia slug)
    assert ari[5] == "Ariyalur"
    assert ari[6] == 2007  # entity_valid_from from created_on
    # Chennai has no created_on -> falls back to parent state's valid_from (1969)
    chennai = by_id["IN-S22-D503"]
    assert chennai[6] == 1969


def test_compile_skips_districts_without_lgd_code(tmp_path):
    """Mahe/Yanam pattern: districts without LGD codes are skipped — the
    canonical entity_id grammar requires an LGD code."""
    entities_json = _write_entities(tmp_path)
    u07_dir = tmp_path / "reference" / "U07"
    _write_districts(u07_dir, {
        "$schema": "./district.schema.json",
        "$schema_version": "3.4",
        "sources": [],
        "state": "S22",  # cheat: use S22 since entities fixture only has S22
        "districts": [
            {"id": "mahe", "id_source": "wikipedia", "name": "Mahe"},
            {"id": "PDY", "id_source": "wikipedia", "name": "Puducherry", "lgd_code": "600"},
        ],
    })
    out = tmp_path / "entities.parquet"
    n = compile_to_parquet(entities_json, [u07_dir / "districts.json"], out)
    # 2 base + 1 district (Mahe skipped)
    assert n == 3


def test_compile_raises_on_unknown_parent_state(tmp_path):
    entities_json = _write_entities(tmp_path)
    s99_dir = tmp_path / "reference" / "S99"
    _write_districts(s99_dir, {
        "$schema": "./district.schema.json",
        "$schema_version": "3.4",
        "sources": [],
        "state": "S99",  # not in entities.json
        "districts": [
            {"id": "x", "id_source": "wikipedia", "name": "X", "lgd_code": "999"},
        ],
    })
    out = tmp_path / "x.parquet"
    with pytest.raises(ValueError, match="unknown parent"):
        compile_to_parquet(entities_json, [s99_dir / "districts.json"], out)


def test_compile_is_deterministic(tmp_path):
    entities_json = _write_entities(tmp_path)
    s22_dir = tmp_path / "reference" / "S22"
    _write_districts(s22_dir, {
        "$schema": "./district.schema.json",
        "$schema_version": "3.4",
        "sources": [],
        "state": "S22",
        "districts": [{
            "id": "ARI", "id_source": "wikipedia",
            "name": "Ariyalur", "lgd_code": "610",
            "created_on": "2007-12-12",
        }],
    })
    a = tmp_path / "a.parquet"
    b = tmp_path / "b.parquet"
    compile_to_parquet(entities_json, [s22_dir / "districts.json"], a)
    compile_to_parquet(entities_json, [s22_dir / "districts.json"], b)
    assert a.read_bytes() == b.read_bytes()


def test_schema_version_constant():
    assert ENTITIES_ROW_SCHEMA_VERSION == "1.1"
