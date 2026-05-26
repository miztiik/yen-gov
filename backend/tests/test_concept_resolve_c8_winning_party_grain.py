"""Tier-A pins for PR-Z3bconcept-resolve cluster 8 (winning-party grain split).

The 2 indicators ``ac-winner-party-id`` + ``winning-party-id`` previously both
FK'd to the single ``winning-party`` concept, tripping
``tier_b_one_indicator_per_concept`` on disjoint entity-kind tuples
(``['ac']`` vs ``['state']``). Per guardrail #13 (Hans identity rule: identity
is what is MEASURED) the AC-grain measure (per-seat plurality winner) and the
state-grain measure (statewide seat-count majority) are distinct measures with
distinct denominators. Each grain gets its own sibling concept_id. The orphan
``winning-party`` parent is deleted.

These pins guard against accidental remap back to the shared concept.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDICATORS = REPO_ROOT / "datasets" / "taxonomy" / "indicators.json"
CONCEPTS = REPO_ROOT / "datasets" / "taxonomy" / "concepts.json"


def _rows() -> list[dict]:
    return json.loads(INDICATORS.read_text(encoding="utf-8"))["indicators"]


def _concepts() -> list[dict]:
    return json.loads(CONCEPTS.read_text(encoding="utf-8"))["concepts"]


def _concept_ids() -> set[str]:
    return {c["concept_id"] for c in _concepts()}


def test_ac_winner_party_uses_ac_concept():
    row = next(r for r in _rows() if r["indicator_id"] == "ac-winner-party-id")
    assert row["concept_id"] == "winning-party-ac"


def test_state_winning_party_uses_state_concept():
    row = next(r for r in _rows() if r["indicator_id"] == "winning-party-id")
    assert row["concept_id"] == "winning-party-state"


def test_winning_party_grain_concepts_exist():
    cids = _concept_ids()
    assert "winning-party-ac" in cids
    assert "winning-party-state" in cids


def test_orphan_winning_party_concept_deleted():
    """Original ``winning-party`` concept had both grains; after the split it is
    orphaned and removed (no remaining FKs)."""
    assert "winning-party" not in _concept_ids()
    leftover = [r["indicator_id"] for r in _rows() if r.get("concept_id") == "winning-party"]
    assert leftover == [], f"winning-party concept should have no FKs after cluster 8; got: {leftover}"


def test_grain_concepts_have_disjoint_entity_kinds():
    ac = next(c for c in _concepts() if c["concept_id"] == "winning-party-ac")
    st = next(c for c in _concepts() if c["concept_id"] == "winning-party-state")
    assert ac["entity_kinds"] == ["ac"]
    assert st["entity_kinds"] == ["state"]
