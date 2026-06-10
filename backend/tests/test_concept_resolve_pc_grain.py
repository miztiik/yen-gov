"""Tier-A pins for the Parliament PC grain (PR-A2, Model C).

The 13 ``pc-*`` election indicators (TODO/20260531-uk-style-elections-experience-plan.md)
each FK to their OWN per-grain sibling concept with ``entity_kinds == ['pc']`` --
the Model C resolution of the grain-prefix fork (Gregor, 2026-06-01). PC (MP /
Parliament) is a genuinely new grain: a different office on a different boundary
than AC (MLA / assembly). Per ADR-0044 + cluster-8 (guardrail #13) the PC measures
get their own concepts mirroring the ``winning-party-ac`` / ``winning-party-state``
precedent -- they do NOT share concept_ids with the ``ac-*`` siblings (Option B,
rejected).

These pins guard against accidental remap of a ``pc-*`` row onto an ``ac-*``
concept (which would re-merge the deliberate per-grain split and break the
disjoint-entity_kinds invariant).
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INDICATORS = REPO_ROOT / "datasets" / "taxonomy" / "indicators.json"
CONCEPTS = REPO_ROOT / "datasets" / "taxonomy" / "concepts.json"

# (pc indicator_id, expected pc concept_id)
PC_INDICATOR_CONCEPTS: list[tuple[str, str]] = [
    ("pc-total-electors", "electors-pc"),
    ("pc-votes-polled", "votes-polled-pc"),
    ("pc-turnout-pct", "turnout-pc"),
    ("pc-nota-votes", "nota-votes-pc"),
    ("pc-nota-pct", "nota-share-pc"),
    ("pc-winner-candidate-id", "winner-pc"),
    ("pc-winner-party-id", "winning-party-pc"),
    ("pc-margin-votes", "margin-absolute-pc"),
    ("pc-margin-pct", "margin-pc"),
    ("pc-others-votes", "others-votes-pc"),
    ("pc-others-pct", "others-share-pc"),
    ("pc-candidates-total", "candidates-total-pc"),
    ("pc-effective-candidates-laakso", "effective-candidates-pc"),
]


def _rows() -> list[dict]:
    return json.loads(INDICATORS.read_text(encoding="utf-8"))["indicators"]


def _concepts() -> list[dict]:
    return json.loads(CONCEPTS.read_text(encoding="utf-8"))["concepts"]


def _concept_ids() -> set[str]:
    return {c["concept_id"] for c in _concepts()}


def test_all_pc_indicators_present_and_pc_grain():
    rows = {r["indicator_id"]: r for r in _rows()}
    for ind_id, _concept in PC_INDICATOR_CONCEPTS:
        assert ind_id in rows, f"missing pc indicator {ind_id}"
        row = rows[ind_id]
        assert row["entity_kinds"] == ["pc"], f"{ind_id} must be pc-grain"
        assert row["default_entity_kind"] == "pc", f"{ind_id} default grain must be pc"
        assert row["family"] == "elections"


def test_pc_indicators_fk_their_own_pc_concept():
    rows = {r["indicator_id"]: r for r in _rows()}
    for ind_id, concept in PC_INDICATOR_CONCEPTS:
        assert rows[ind_id]["concept_id"] == concept, (
            f"{ind_id} must FK {concept} (Model C per-grain sibling), "
            f"got {rows[ind_id].get('concept_id')}"
        )


def test_pc_concepts_exist_and_are_pc_grain():
    by_id = {c["concept_id"]: c for c in _concepts()}
    for _ind, concept in PC_INDICATOR_CONCEPTS:
        assert concept in by_id, f"missing pc concept {concept}"
        assert by_id[concept]["entity_kinds"] == ["pc"], (
            f"{concept} must be entity_kinds ['pc'] (disjoint from ac sibling)"
        )


def test_pc_concepts_do_not_share_with_ac_siblings():
    """Model C: no pc concept may be extended to also carry the 'ac' grain
    (that would be the rejected Option B). Guards the cluster-8 split."""
    by_id = {c["concept_id"]: c for c in _concepts()}
    for _ind, concept in PC_INDICATOR_CONCEPTS:
        kinds = by_id[concept]["entity_kinds"]
        assert "ac" not in kinds, (
            f"{concept} must NOT carry the 'ac' grain (Option B rejected); got {kinds}"
        )


def test_winning_party_pc_distinct_from_ac_and_state():
    cids = _concept_ids()
    assert "winning-party-pc" in cids
    assert "winning-party-ac" in cids
    assert "winning-party-state" in cids
