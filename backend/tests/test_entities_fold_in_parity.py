"""Parity test for the T.0c-iii Phase A fold-in: ``entities.json``
already-folded rows MUST win over ``districts.json`` rows with the
same ``entity_id``.

Per CLAUDE.md §15, ``tmp_path`` fixtures only. Real DuckDB COPY via
``compile_to_parquet`` (Holy Law #7, no mocks).

Why this test exists
--------------------
After T.0c-iii Phase A lands, ``datasets/taxonomy/entities.json``
carries the 145 district rows that the seed previously projected from
``datasets/reference/in/states/<S>/districts.json``. Both inputs now
contain the same ``entity_id`` set during the deprecation window
(Phase B = frontend consumer audit; Phase C = file deletion). The
seed's dedup contract is: entities.json wins. This test pins that
contract so a future change cannot silently regress to "raise on
duplicate" (the pre-Phase-A behaviour) or, worse, to
"districts.json wins" (which would let an unmaintained sidecar
override the hand-authored canonical row).
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from yen_gov.canonical.entities_seed import compile_to_parquet


def _write_entities_with_districts(tmp_path: Path) -> Path:
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
                "entity_valid_from": 1947,
                "iso_3166_2": "IN-TN",
            },
            # District already folded into entities.json with curated
            # notes. The districts.json sidecar carries a DIFFERENT
            # notes string for the same entity_id; the seed must
            # preserve the entities.json row.
            {
                "entity_id": "IN-S22-D610",
                "entity_type": "district",
                "entity_level": "district",
                "entity_code": "610",
                "display_name": "Ariyalur",
                "display_name_local": None,
                "parent_entity_id": "IN-S22",
                "entity_valid_from": 2007,
                "entity_valid_to": None,
                "iso_3166_2": None,
                "lgd_code": "610",
                "legacy_id": "ARI",
                "notes": "ENTITIES_JSON_NOTES",
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


def test_entities_json_wins_over_districts_json_on_dup_entity_id(tmp_path):
    """Dup ``entity_id`` between entities.json and districts.json:
    entities.json row survives unchanged; districts.json row is dropped."""
    entities_json = _write_entities_with_districts(tmp_path)
    s22_dir = tmp_path / "reference" / "S22"
    _write_districts(
        s22_dir,
        {
            "$schema": "./district.schema.json",
            "$schema_version": "3.4",
            "sources": [],
            "state": "S22",
            "districts": [
                # Same lgd_code as the entities.json row above; would
                # project to the same entity_id. Different notes
                # composition (headquarters / split_from) — if the
                # dedup is broken and districts.json wins, the
                # ``notes`` field below will overwrite the curated
                # ``ENTITIES_JSON_NOTES`` from entities.json.
                {
                    "id": "ARI",
                    "id_source": "wikipedia",
                    "name": "Ariyalur (sidecar override)",
                    "lgd_code": "610",
                    "created_on": "2099-01-01",
                    "headquarters": "DISTRICTS_JSON_OVERRIDE",
                    "split_from": ["PER"],
                },
            ],
        },
    )
    out = tmp_path / "entities.parquet"
    n = compile_to_parquet(entities_json, [s22_dir / "districts.json"], out)

    # Row count: 1 country + 1 state + 1 district. NOT 4 (no dup row).
    assert n == 3

    rows = duckdb.connect().execute(
        f"SELECT entity_id, display_name, entity_valid_from, notes "
        f"FROM read_parquet('{out.as_posix()}') "
        f"WHERE entity_id = 'IN-S22-D610'"
    ).fetchall()
    assert len(rows) == 1
    entity_id, display_name, valid_from, notes = rows[0]

    # entities.json wins: display_name, entity_valid_from, notes all
    # come from the entities.json row, not the districts.json projection.
    assert display_name == "Ariyalur"  # not "Ariyalur (sidecar override)"
    assert valid_from == 2007  # not 2099 from districts.json `created_on`
    assert notes == "ENTITIES_JSON_NOTES"  # not "Headquarters: DISTRICTS_JSON_OVERRIDE..."


def test_districts_json_only_rows_still_lift(tmp_path):
    """Sanity: districts NOT present in entities.json continue to lift
    from districts.json (the seed's pre-Phase-A path). Pins that
    entities.json-wins dedup didn't accidentally suppress every
    districts.json row."""
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
                "entity_valid_from": 1947,
                "iso_3166_2": "IN-TN",
            },
        ],
    }
    entities_json = tmp_path / "entities.json"
    entities_json.write_text(json.dumps(payload), encoding="utf-8")

    s22_dir = tmp_path / "reference" / "S22"
    _write_districts(
        s22_dir,
        {
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
                    "created_on": "2007-11-23",
                    "headquarters": "Ariyalur",
                },
            ],
        },
    )
    out = tmp_path / "entities.parquet"
    n = compile_to_parquet(entities_json, [s22_dir / "districts.json"], out)

    # 1 country + 1 state + 1 district lifted from districts.json
    assert n == 3
    rows = duckdb.connect().execute(
        f"SELECT entity_id, legacy_id "
        f"FROM read_parquet('{out.as_posix()}') "
        f"WHERE entity_id = 'IN-S22-D610'"
    ).fetchall()
    assert rows == [("IN-S22-D610", "ARI")]
