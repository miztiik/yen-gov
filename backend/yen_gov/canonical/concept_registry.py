"""Concept registry overlap helper.

Hand-authored taxonomy at ``datasets/taxonomy/concepts.json`` declares the
citizen-readable nouns (``concept_id``) that indicators FK to. This module
provides the read-side helper used by the future ``check-overlap`` CLI
and the future Tier-B proliferation checks (PR-Z3b): given a candidate
``(noun, unit, normalisation, entity_kind)`` tuple a new ingest proposes,
score it against the existing concepts and return ranked matches plus a
recommended action.

OWID precedent: every Grapher variable resolves to a single concept; new
publishers of an existing fact are facets, not new variables. See
``TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md`` §0quint
+ §2 PR-Z3 (guardrails #13-#18).

Ships in PR-Z3a. The CLI command and Tier-B checks that consume this
helper ship in PR-Z3b.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Literal

RecommendedAction = Literal["upsert", "add_facet", "mint_new"]

DEFAULT_CONCEPTS_PATH = (
    Path(__file__).resolve().parents[3]
    / "datasets"
    / "taxonomy"
    / "concepts.json"
)


@dataclass(frozen=True)
class ConceptMatch:
    """One overlap candidate returned by :func:`find_overlap`.

    ``match_score`` is in ``[0.0, 1.0]``. ``recommended_action`` is the
    handover-doc instruction the candidate ingest must follow:

    * ``upsert``  -- score >= 0.85: the existing concept IS the same fact
      at the same grain; the new ingest UPSERTs into the existing
      indicator (new vintage, new publisher, etc.).
    * ``add_facet`` -- 0.70 <= score < 0.85: the existing concept is the
      same fact at a different grain or facet; add a facet axis on the
      existing indicator instead of minting a new id.
    * ``mint_new`` -- score < 0.70: distinct concept; minting a new id is
      acceptable provided no other match crosses the threshold.
    """

    concept_id: str
    match_score: float
    existing_entity_kinds: tuple[str, ...]
    recommended_action: RecommendedAction


def _normalise_text(s: str) -> str:
    return " ".join(s.lower().split())


def _score(
    candidate_noun: str,
    candidate_unit: str,
    candidate_norm: str,
    candidate_kind: str,
    row: dict,
) -> tuple[float, RecommendedAction]:
    noun_score = SequenceMatcher(
        None, _normalise_text(candidate_noun), _normalise_text(row["noun"])
    ).ratio()
    unit_match = (
        _normalise_text(candidate_unit) == _normalise_text(row["unit_canonical"])
    )
    norm_match = candidate_norm == row["normalisation"]
    kind_match = candidate_kind in row["entity_kinds"]

    # Weighted blend: noun similarity 0.55, unit equality 0.25, normalisation
    # equality 0.20. Grain alignment is the action discriminator, not a score
    # input — the same concept can live at multiple grains.
    score = noun_score * 0.55 + (0.25 if unit_match else 0.0) + (
        0.20 if norm_match else 0.0
    )
    score = round(score, 4)

    if score >= 0.85 and unit_match and norm_match and kind_match:
        action: RecommendedAction = "upsert"
    elif score >= 0.70 and unit_match and norm_match:
        action = "add_facet"
    else:
        action = "mint_new"
    return score, action


def find_overlap(
    noun: str,
    unit: str,
    normalisation: str,
    entity_kind: str,
    *,
    concepts: Iterable[dict] | None = None,
    concepts_path: Path | None = None,
    top_n: int = 5,
) -> list[ConceptMatch]:
    """Score ``(noun, unit, normalisation, entity_kind)`` against the
    concept registry; return the top ``top_n`` matches sorted by score
    descending (ties broken by ``concept_id``).

    Pass ``concepts`` (an iterable of concept rows) to override the
    on-disk lookup — used by tests with synthetic fixtures so they never
    walk the real corpus per CLAUDE.md §10. ``concepts_path`` overrides
    the default ``datasets/taxonomy/concepts.json`` location for tests
    that want to exercise the disk-read path.
    """

    if concepts is None:
        path = concepts_path or DEFAULT_CONCEPTS_PATH
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload["concepts"]
    else:
        rows = list(concepts)

    scored: list[ConceptMatch] = []
    for row in rows:
        score, action = _score(noun, unit, normalisation, entity_kind, row)
        scored.append(
            ConceptMatch(
                concept_id=row["concept_id"],
                match_score=score,
                existing_entity_kinds=tuple(row["entity_kinds"]),
                recommended_action=action,
            )
        )

    scored.sort(key=lambda m: (-m.match_score, m.concept_id))
    return scored[:top_n]


__all__ = [
    "ConceptMatch",
    "RecommendedAction",
    "find_overlap",
    "DEFAULT_CONCEPTS_PATH",
]
