"""Tier-A tests for ``yen_gov.canonical.entities_seed``.

Per CLAUDE.md §15, ``tmp_path`` fixtures only.

T.0c-iii Phase B (2026-05-22): the per-state ``districts.json`` loader
is gone; ``entities.json`` is the sole input. Tests cover the
post-Phase-B contract — that ``compile_to_parquet`` projects every
entities.json row (including the ``entity_type='district'`` rows that
Phase A folded in) through to ``entities.parquet`` with deterministic
ordering and PK uniqueness enforcement.
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


def _write_entities(tmp_path: Path, entities: list[dict]) -> Path:
    payload = {
        "$schema": "./entity.schema.json",
        "$schema_version": "1.1",
        "entities": entities,
    }
    p = tmp_path / "entities.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _base_country_and_state() -> list[dict]:
    return [
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
    ]


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


def test_compile_emits_one_row_per_entities_json_row(tmp_path):
    """Pure pass-through: N entities.json rows → N parquet rows."""
    entities_json = _write_entities(tmp_path, _base_country_and_state())
    out = tmp_path / "entities.parquet"
    n = compile_to_parquet(entities_json, out)
    assert n == 2
    rows = _read(out)
    by_id = {r[0]: r for r in rows}
    assert set(by_id) == {"IN", "IN-S22"}
    assert by_id["IN"][1] == "country"
    assert by_id["IN-S22"][1] == "state"
    assert by_id["IN-S22"][2] == "IN"


def test_compile_handles_district_rows_in_entities_json(tmp_path):
    """Phase A folded the 145 district rows INTO entities.json; Phase B
    relies on them flowing through ``compile_to_parquet`` with their
    ``lgd_code`` / ``legacy_id`` / ``parent_entity_id`` intact."""
    entities = _base_country_and_state() + [
        {
            "entity_id": "IN-S22-D610",
            "entity_type": "district",
            "entity_level": "district",
            "entity_code": "610",
            "display_name": "Ariyalur",
            "parent_entity_id": "IN-S22",
            "entity_valid_from": 2007,
            "lgd_code": "610",
            "legacy_id": "ARI",
            "notes": "Headquarters: Ariyalur.",
        },
        {
            "entity_id": "IN-S22-D503",
            "entity_type": "district",
            "entity_level": "district",
            "entity_code": "503",
            "display_name": "Chennai",
            "parent_entity_id": "IN-S22",
            "entity_valid_from": 1969,
            "lgd_code": "503",
            "legacy_id": "chennai",
        },
    ]
    entities_json = _write_entities(tmp_path, entities)
    out = tmp_path / "entities.parquet"
    n = compile_to_parquet(entities_json, out)
    assert n == 4
    rows = _read(out)
    by_id = {r[0]: r for r in rows}
    ari = by_id["IN-S22-D610"]
    assert ari[1] == "district"
    assert ari[2] == "IN-S22"  # parent_entity_id
    assert ari[3] == "610"  # lgd_code
    assert ari[4] == "ARI"  # legacy_id (Wikipedia slug)
    assert ari[5] == "Ariyalur"
    assert ari[6] == 2007  # entity_valid_from from entities.json row
    chennai = by_id["IN-S22-D503"]
    assert chennai[4] == "chennai"
    assert chennai[6] == 1969


def test_compile_raises_on_duplicate_entity_id(tmp_path):
    """Cross-row uniqueness: ``entity_id`` is the PK on entities.parquet."""
    entities = _base_country_and_state() + [
        {
            "entity_id": "IN-S22",  # dup of the state row above
            "entity_type": "state",
            "entity_level": "state",
            "entity_code": "S22",
            "display_name": "Tamil Nadu (dup)",
            "parent_entity_id": "IN",
            "entity_valid_from": 1969,
        },
    ]
    entities_json = _write_entities(tmp_path, entities)
    out = tmp_path / "x.parquet"
    with pytest.raises(ValueError, match="duplicate entity_id"):
        compile_to_parquet(entities_json, out)


def test_compile_sort_order_is_entity_type_then_entity_id(tmp_path):
    """Deterministic sort key — every consumer that read_parquet's the
    file relies on this row order for byte-stable downstream emits."""
    entities = [
        # Deliberately reverse-alphabetical input to prove the sort happens.
        {
            "entity_id": "IN-S22-D610",
            "entity_type": "district",
            "entity_level": "district",
            "entity_code": "610",
            "display_name": "Ariyalur",
            "parent_entity_id": "IN-S22",
            "entity_valid_from": 2007,
            "lgd_code": "610",
        },
        {
            "entity_id": "IN-S22",
            "entity_type": "state",
            "entity_level": "state",
            "entity_code": "S22",
            "display_name": "Tamil Nadu",
            "parent_entity_id": "IN",
            "entity_valid_from": 1969,
        },
        {
            "entity_id": "IN",
            "entity_type": "country",
            "entity_level": "country",
            "entity_code": "IN",
            "display_name": "India",
            "entity_valid_from": 1947,
        },
    ]
    entities_json = _write_entities(tmp_path, entities)
    out = tmp_path / "entities.parquet"
    compile_to_parquet(entities_json, out)
    con = duckdb.connect()
    try:
        ordered = con.execute(
            f"SELECT entity_id, entity_type FROM read_parquet('{out.as_posix()}')"
        ).fetchall()
    finally:
        con.close()
    assert ordered == [
        ("IN", "country"),
        ("IN-S22-D610", "district"),
        ("IN-S22", "state"),
    ]


def test_compile_is_deterministic(tmp_path):
    entities = _base_country_and_state() + [
        {
            "entity_id": "IN-S22-D610",
            "entity_type": "district",
            "entity_level": "district",
            "entity_code": "610",
            "display_name": "Ariyalur",
            "parent_entity_id": "IN-S22",
            "entity_valid_from": 2007,
            "lgd_code": "610",
            "legacy_id": "ARI",
        },
    ]
    entities_json = _write_entities(tmp_path, entities)
    a = tmp_path / "a.parquet"
    b = tmp_path / "b.parquet"
    compile_to_parquet(entities_json, a)
    compile_to_parquet(entities_json, b)
    assert a.read_bytes() == b.read_bytes()


def test_schema_version_constant():
    assert ENTITIES_ROW_SCHEMA_VERSION == "1.1"
