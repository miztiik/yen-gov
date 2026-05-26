"""Tier-A pins for PR-Z3bconcept-resolve cluster 7 (vote-share grain split).

The 2 indicators ``candidate-vote-share-pct`` + ``party-vote-share-pct``
previously both FK'd to the single ``vote-share`` concept, tripping
``tier_b_one_indicator_per_concept`` on disjoint entity-kind tuples
(``['candidate']`` vs ``['party']``). Per guardrail #13 (Hans identity rule:
identity is what is MEASURED, and the denominator differs by grain — AC turnout
for candidate-grain vs state turnout for party-grain), each grain gets its own
sibling concept_id. The orphan ``vote-share`` parent is deleted.

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


def test_candidate_vote_share_uses_candidate_concept():
    row = next(r for r in _rows() if r["indicator_id"] == "candidate-vote-share-pct")
    assert row["concept_id"] == "vote-share-candidate"


def test_party_vote_share_uses_party_concept():
    row = next(r for r in _rows() if r["indicator_id"] == "party-vote-share-pct")
    assert row["concept_id"] == "vote-share-party"


def test_vote_share_grain_concepts_exist():
    cids = _concept_ids()
    assert "vote-share-candidate" in cids
    assert "vote-share-party" in cids


def test_orphan_vote_share_concept_deleted():
    """Original ``vote-share`` concept had both grains; after the split it is
    orphaned and removed (no remaining FKs)."""
    assert "vote-share" not in _concept_ids()
    leftover = [r["indicator_id"] for r in _rows() if r.get("concept_id") == "vote-share"]
    assert leftover == [], f"vote-share concept should have no FKs after cluster 7; got: {leftover}"


def test_grain_concepts_have_disjoint_entity_kinds():
    cand = next(c for c in _concepts() if c["concept_id"] == "vote-share-candidate")
    party = next(c for c in _concepts() if c["concept_id"] == "vote-share-party")
    assert cand["entity_kinds"] == ["candidate"]
    assert party["entity_kinds"] == ["party"]
