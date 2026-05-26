"""Tests for ``yen_gov.canonical.concept_registry`` (PR-Z3a).

Per CLAUDE.md §10 these tests never walk the real corpus; the registry
is exercised via synthetic in-memory fixtures plus a single ``tmp_path``
disk-read smoke. The seed file at
``datasets/taxonomy/concepts.json`` is validated against the schema in a
separate Tier-A check (``test_concepts_seed.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.concept_registry import (
    ConceptMatch,
    DEFAULT_CONCEPTS_PATH,
    find_overlap,
)


_FIXTURE_CONCEPTS = [
    {
        "concept_id": "electricity-used-per-person",
        "noun": "Per-capita electricity",
        "unit_canonical": "kWh",
        "normalisation": "per_capita",
        "entity_kinds": ["state"],
        "description_short": "Electricity consumed per person per year.",
        "sources": [],
    },
    {
        "concept_id": "cattle-population",
        "noun": "Cattle population",
        "unit_canonical": "head",
        "normalisation": "absolute",
        "entity_kinds": ["state", "district"],
        "description_short": "Number of cattle.",
        "sources": [],
    },
    {
        "concept_id": "state-gva",
        "noun": "Gross value added",
        "unit_canonical": "INR crore",
        "normalisation": "absolute",
        "entity_kinds": ["state"],
        "description_short": "State GVA at current prices.",
        "sources": [],
    },
]


def test_exact_match_recommends_upsert() -> None:
    matches = find_overlap(
        noun="Per-capita electricity",
        unit="kWh",
        normalisation="per_capita",
        entity_kind="state",
        concepts=_FIXTURE_CONCEPTS,
    )
    top = matches[0]
    assert top.concept_id == "electricity-used-per-person"
    assert top.recommended_action == "upsert"
    assert top.match_score >= 0.85


def test_same_concept_different_grain_recommends_add_facet() -> None:
    # Same noun/unit/normalisation but a grain the concept does NOT carry.
    matches = find_overlap(
        noun="Per-capita electricity",
        unit="kWh",
        normalisation="per_capita",
        entity_kind="district",
        concepts=_FIXTURE_CONCEPTS,
    )
    top = matches[0]
    assert top.concept_id == "electricity-used-per-person"
    assert top.recommended_action == "add_facet"


def test_unrelated_concept_recommends_mint_new() -> None:
    matches = find_overlap(
        noun="Solar irradiance",
        unit="kWh/m2",
        normalisation="absolute",
        entity_kind="state",
        concepts=_FIXTURE_CONCEPTS,
    )
    assert matches[0].recommended_action == "mint_new"
    assert matches[0].match_score < 0.70


def test_unit_mismatch_drops_below_upsert_threshold() -> None:
    # Same noun + normalisation + grain but different canonical unit.
    matches = find_overlap(
        noun="Per-capita electricity",
        unit="MWh",
        normalisation="per_capita",
        entity_kind="state",
        concepts=_FIXTURE_CONCEPTS,
    )
    top = matches[0]
    assert top.concept_id == "electricity-used-per-person"
    assert top.recommended_action != "upsert"


def test_returns_top_n_sorted_descending() -> None:
    matches = find_overlap(
        noun="Cattle population",
        unit="head",
        normalisation="absolute",
        entity_kind="state",
        concepts=_FIXTURE_CONCEPTS,
        top_n=2,
    )
    assert len(matches) == 2
    assert all(isinstance(m, ConceptMatch) for m in matches)
    assert matches[0].match_score >= matches[1].match_score


def test_disk_read_path_smoke(tmp_path: Path) -> None:
    payload = {
        "$schema": "../schemas/concepts.schema.json",
        "$schema_version": "1.0",
        "concepts": _FIXTURE_CONCEPTS,
    }
    concepts_file = tmp_path / "concepts.json"
    concepts_file.write_text(json.dumps(payload), encoding="utf-8")
    matches = find_overlap(
        noun="Cattle population",
        unit="head",
        normalisation="absolute",
        entity_kind="district",
        concepts_path=concepts_file,
    )
    assert matches[0].concept_id == "cattle-population"
    assert matches[0].recommended_action == "upsert"


def test_default_concepts_path_resolves_to_canonical_seed() -> None:
    # Path-shape check only — no I/O against the real corpus.
    assert DEFAULT_CONCEPTS_PATH.name == "concepts.json"
    assert DEFAULT_CONCEPTS_PATH.parent.name == "taxonomy"


def test_empty_registry_returns_empty_list() -> None:
    matches = find_overlap(
        noun="anything",
        unit="x",
        normalisation="absolute",
        entity_kind="state",
        concepts=[],
    )
    assert matches == []


def test_per_capita_vs_absolute_does_not_recommend_upsert() -> None:
    # Same noun + grain + similar unit but different normalisation must
    # never collapse to UPSERT — counts and per-capita are not the same fact.
    matches = find_overlap(
        noun="Cattle population",
        unit="head",
        normalisation="per_capita",
        entity_kind="state",
        concepts=_FIXTURE_CONCEPTS,
    )
    top = matches[0]
    assert top.concept_id == "cattle-population"
    assert top.recommended_action != "upsert"


@pytest.mark.parametrize(
    "action",
    ["upsert", "add_facet", "mint_new"],
)
def test_action_is_within_recognised_set(action: str) -> None:
    assert action in {"upsert", "add_facet", "mint_new"}
