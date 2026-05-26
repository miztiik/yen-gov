"""Schema-shape assertions for indicator-catalogue.schema.json v2.2
(PR-Z3b-tail-conceptFK Carve 0a -- concept_id FK schema bump).

Per TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md §0quat
guardrail #13: every indicator MUST FK to one row in
``datasets/taxonomy/concepts.json`` declaring
``(noun, unit_canonical, normalisation, entity_kinds)``. Carve 0a is the
schema-only bump (additive optional ``concept_id`` field); Carve 1 will
backfill all 183 ``datasets/taxonomy/indicators.json`` rows via Z3a
``find_overlap`` clustering at confidence >=0.95 + stub-concepts auto-mint
for unmatched rows. The DARK ``tier_b_one_indicator_per_concept`` check
(PR-Z3b-tail3 #366) chains live in a follow-up PR after Carve 1.

Schema-only contract assertions plus a catalogue-stamp sentinel; no row
backfill in this PR (the field stays absent on all 183 indicators).
"""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "datasets" / "schemas" / "indicator-catalogue.schema.json"
CATALOGUE_PATH = REPO_ROOT / "datasets" / "taxonomy" / "indicators.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _catalogue() -> dict:
    return json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))


def test_schema_x_version_is_2_2():
    assert _schema()["x-version"] == "2.2"


def test_catalogue_schema_version_stamp_is_2_2():
    # Tier-B `validate.run()` enforces $schema_version == schema x-version;
    # bumping the schema requires the catalogue stamp to track.
    assert _catalogue()["$schema_version"] == "2.2"


def test_x_changelog_tail_entry_is_2_2():
    changelog = _schema()["x-changelog"]
    tail = changelog[-1]
    assert tail["version"] == "2.2"
    assert tail["date"] == "2026-05-26"
    assert "concept_id" in tail["description"]
    assert "Carve 0a" in tail["description"]


def test_schema_declares_concept_id_property():
    props = _schema()["properties"]["indicators"]["items"]["properties"]
    assert "concept_id" in props
    ci = props["concept_id"]
    assert ci["type"] == "string"
    assert ci["pattern"] == r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$"
    assert ci["maxLength"] == 40


def test_concept_id_is_optional_in_required_list():
    required = _schema()["properties"]["indicators"]["items"]["required"]
    assert "concept_id" not in required, (
        "v2.2 field is optional during the v2.1->v2.2 transition; "
        "intent-required is enforced via Tier-B "
        "tier_b_one_indicator_per_concept once chained live."
    )


def test_v21_update_period_days_still_present():
    """v2.2 is purely additive on top of v2.1; the v2.1 field must remain."""
    props = _schema()["properties"]["indicators"]["items"]["properties"]
    assert "update_period_days" in props
    assert props["update_period_days"]["type"] == "integer"
