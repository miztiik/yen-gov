"""Tier-A: ``datasets/taxonomy/concepts.json`` validates against
``datasets/schemas/concepts.schema.json`` (PR-Z3a).

This is the seed contract test — it walks the on-disk taxonomy file
(allowed because the file is committed-and-versioned per ADR-0044, not
runtime corpus) and asserts every row matches the schema. The
``find_overlap`` behavioural surface is tested in
``test_concept_registry.py`` against synthetic fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPO_ROOT / "datasets" / "schemas" / "concepts.schema.json"
SEED = REPO_ROOT / "datasets" / "taxonomy" / "concepts.json"


def test_concepts_schema_file_exists() -> None:
    assert SCHEMA.is_file(), f"missing schema: {SCHEMA}"


def test_concepts_seed_file_exists() -> None:
    assert SEED.is_file(), f"missing seed: {SEED}"


def test_concepts_seed_validates_against_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = json.loads(SEED.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(data))
    assert not errors, "\n".join(
        f"{list(e.path)}: {e.message}" for e in errors[:10]
    )


def test_concept_ids_are_unique() -> None:
    data = json.loads(SEED.read_text(encoding="utf-8"))
    ids = [c["concept_id"] for c in data["concepts"]]
    assert len(ids) == len(set(ids)), "duplicate concept_id detected"


def test_concepts_schema_version_pinned() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = json.loads(SEED.read_text(encoding="utf-8"))
    assert schema["x-version"] == "1.0"
    assert data["$schema_version"] == "1.0"
    # x-changelog tail invariant per CLAUDE.md §11.
    assert schema["x-changelog"][-1]["version"] == schema["x-version"]
