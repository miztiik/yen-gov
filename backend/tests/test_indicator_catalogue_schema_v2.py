"""Schema-shape assertions for indicator-catalogue.schema.json v2.0 (PR-B1).

Locks the shape of the v2.0 BREAKING change so future incidental edits to
the schema cannot regress it without an explicit test update + changelog
bump.
"""

from __future__ import annotations

import json
from pathlib import Path


SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "datasets"
    / "schemas"
    / "indicator-catalogue.schema.json"
)


def _load() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_x_version_is_current():
    # Tracks the latest x-version; bumped to "2.2" in
    # PR-Z3b-tail-conceptFK Carve 0a (additive concept_id).
    s = _load()
    assert s["x-version"] == "2.2"


def test_changelog_has_2_1_entry():
    s = _load()
    versions = [e["version"] for e in s["x-changelog"]]
    assert "2.1" in versions


def test_changelog_has_2_0_entry():
    s = _load()
    versions = [e["version"] for e in s["x-changelog"]]
    assert "2.0" in versions


def test_entity_kinds_and_default_entity_kind_required():
    s = _load()
    required = s["properties"]["indicators"]["items"]["required"]
    assert "entity_kinds" in required
    assert "default_entity_kind" in required


def test_id_aliases_and_deprecated_in_removed():
    s = _load()
    props = s["properties"]["indicators"]["items"]["properties"]
    assert "id_aliases" not in props
    assert "deprecated_in" not in props


def test_entity_kind_enum_is_closed_six():
    s = _load()
    props = s["properties"]["indicators"]["items"]["properties"]
    assert props["entity_kinds"]["items"]["enum"] == [
        "country",
        "state",
        "district",
        "ac",
        "party",
        "candidate",
    ]
    assert props["default_entity_kind"]["enum"] == [
        "country",
        "state",
        "district",
        "ac",
        "party",
        "candidate",
    ]


def test_entity_kinds_min_items_one_and_unique():
    s = _load()
    p = s["properties"]["indicators"]["items"]["properties"]["entity_kinds"]
    assert p["minItems"] == 1
    assert p["uniqueItems"] is True
