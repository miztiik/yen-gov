"""Tests for ``yen_gov.canonical.state_lgd_resolver``.

Pure-logic tests — no parquet, no fetch, no fixtures beyond inline
dicts. Verifies the projection from ``entities`` list to
``{state_lgd_int: ECI_code}`` map under all the edge cases the lift
orchestrator actually exercises.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.state_lgd_resolver import (
    STATE_LIKE_ENTITY_TYPES,
    build_state_lgd_to_eci_map,
    load_state_lgd_to_eci_map,
)


def _state_row(
    *,
    entity_id: str,
    entity_code: str,
    lgd_code: str | None,
    entity_type: str = "state",
    entity_valid_to: int | None = None,
) -> dict[str, object]:
    """Minimal entities.json-shaped row factory."""
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "entity_level": "state" if entity_type == "state" else "ut",
        "entity_code": entity_code,
        "display_name": entity_id,
        "parent_entity_id": "IN",
        "entity_valid_from": 1947,
        "entity_valid_to": entity_valid_to,
        "iso_3166_2": None,
        "lgd_code": lgd_code,
        "notes": None,
    }


def test_state_like_entity_types_is_exactly_state_and_ut() -> None:
    assert STATE_LIKE_ENTITY_TYPES == frozenset({"state", "ut"})


def test_projects_state_rows_to_lgd_to_eci_dict() -> None:
    entities = [
        _state_row(entity_id="IN-S22", entity_code="S22", lgd_code="33"),
        _state_row(entity_id="IN-S08", entity_code="S08", lgd_code="02"),
        _state_row(entity_id="IN-U05", entity_code="U05", lgd_code="07", entity_type="ut"),
    ]
    assert build_state_lgd_to_eci_map(entities) == {33: "S22", 2: "S08", 7: "U05"}


def test_ignores_non_state_non_ut_rows() -> None:
    entities = [
        _state_row(entity_id="IN-S22", entity_code="S22", lgd_code="33"),
        {
            "entity_id": "IN-S22-D603",
            "entity_type": "district",
            "entity_level": "district",
            "entity_code": "603",
            "display_name": "Chennai",
            "parent_entity_id": "IN-S22",
            "entity_valid_from": 1947,
            "entity_valid_to": None,
            "iso_3166_2": None,
            "lgd_code": "603",
            "notes": None,
        },
        {
            "entity_id": "IN-S22-CM",
            "entity_type": "office_bearer",
            "entity_level": "fiscal_actor",
            "entity_code": "CM",
            "display_name": "Chief Minister of Tamil Nadu",
            "parent_entity_id": "IN-S22",
            "entity_valid_from": 1947,
            "entity_valid_to": None,
            "iso_3166_2": None,
            "lgd_code": None,
            "notes": None,
        },
    ]
    assert build_state_lgd_to_eci_map(entities) == {33: "S22"}


def test_ignores_historic_states_with_entity_valid_to() -> None:
    """Composite J&K (IN-S09) shares lgd_code='01' with the post-2019
    J&K UT (IN-U08); the lift must route 2024 features to U08, not S09.
    """
    entities = [
        _state_row(
            entity_id="IN-S09",
            entity_code="S09",
            lgd_code="01",
            entity_valid_to=2019,  # historic — exclude
        ),
        _state_row(
            entity_id="IN-U08",
            entity_code="U08",
            lgd_code="01",
            entity_type="ut",
        ),
    ]
    assert build_state_lgd_to_eci_map(entities) == {1: "U08"}


def test_ignores_rows_missing_lgd_code() -> None:
    entities = [
        _state_row(entity_id="IN-S22", entity_code="S22", lgd_code="33"),
        _state_row(entity_id="IN-S99", entity_code="S99", lgd_code=None),
    ]
    assert build_state_lgd_to_eci_map(entities) == {33: "S22"}


def test_raises_on_duplicate_lgd_with_different_eci() -> None:
    entities = [
        _state_row(entity_id="IN-S22", entity_code="S22", lgd_code="33"),
        _state_row(entity_id="IN-S99", entity_code="S99", lgd_code="33"),
    ]
    with pytest.raises(ValueError, match="duplicate state_lgd 33"):
        build_state_lgd_to_eci_map(entities)


def test_no_raise_on_duplicate_lgd_same_eci_idempotent() -> None:
    """Defensive: if the input list contains the same row twice (caller
    bug), the mapping is idempotent and does NOT raise — the contract
    is 'one LGD per ECI', not 'one row per LGD'.
    """
    entities = [
        _state_row(entity_id="IN-S22", entity_code="S22", lgd_code="33"),
        _state_row(entity_id="IN-S22", entity_code="S22", lgd_code="33"),
    ]
    assert build_state_lgd_to_eci_map(entities) == {33: "S22"}


def test_coerces_string_lgd_to_int() -> None:
    """LGD codes in entities.json are zero-padded strings ('02', '06');
    the returned map keys are bare ints so the lift can do a fast
    ``int(feature.state_lgd)`` lookup.
    """
    entities = [
        _state_row(entity_id="IN-S07", entity_code="S07", lgd_code="06"),
        _state_row(entity_id="IN-S08", entity_code="S08", lgd_code="02"),
    ]
    assert build_state_lgd_to_eci_map(entities) == {6: "S07", 2: "S08"}


def test_load_state_lgd_to_eci_map_from_disk(tmp_path: Path) -> None:
    """``load_state_lgd_to_eci_map`` reads entities.json then projects."""
    doc = {
        "$schema": "../schemas/entity.schema.json",
        "$schema_version": "1.2",
        "entities": [
            _state_row(entity_id="IN-S22", entity_code="S22", lgd_code="33"),
            _state_row(entity_id="IN-U05", entity_code="U05", lgd_code="07", entity_type="ut"),
        ],
    }
    path = tmp_path / "entities.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert load_state_lgd_to_eci_map(path) == {33: "S22", 7: "U05"}


def test_real_entities_json_yields_36_state_mappings() -> None:
    """Real-corpus smoke: the committed entities.json must produce
    exactly 36 state/UT mappings (28 states + 8 UTs, per the post-2019
    composition).
    """
    repo_root = Path(__file__).resolve().parents[2]
    entities_path = repo_root / "datasets" / "taxonomy" / "entities.json"
    mapping = load_state_lgd_to_eci_map(entities_path)
    assert len(mapping) == 36, (
        f"expected 36 state/UT LGD mappings; got {len(mapping)}. "
        "If a state was recently added/removed update this assertion."
    )
    # Spot-check a few well-known mappings
    assert mapping[33] == "S22"  # Tamil Nadu
    assert mapping[2] == "S08"   # Himachal Pradesh
    assert mapping[7] == "U05"   # Delhi
