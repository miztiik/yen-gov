"""Registration-time catalogue checks for :class:`IndicatorSpec` (Row 1).

Two fail-loud preconditions every ``IndicatorSpec`` must pass before the
orchestrator will register the source that carries it:

(a) **FK existence** -- ``indicator_id`` MUST resolve to a row in
    ``datasets/taxonomy/indicators.json``. A bogus id RAISES
    :class:`CatalogueFkError`. The pipeline never mints identity (CLAUDE.md
    section 0a authority table; the catalogue is the SOT).

(b) **Concept compatibility** -- the spec's
    ``(unit, normalisation, price_basis, sampling_frame)`` tuple MUST match
    the concept resolved via ``indicator.concept_id`` ->
    ``datasets/taxonomy/concepts.json``. A mismatch RAISES
    :class:`ConceptCompatibilityError`. FK existence is necessary but NOT
    sufficient: an indicator can exist yet the spec can declare the wrong
    unit / price basis / sampling frame, which would silently splice
    incompatible methodologies. ``unit != concept.unit_canonical`` is a unit
    lie; a constant-price spec against a current-price concept is a
    price-basis lie; a survey-frame mismatch splices two populations.

Reads are injectable (``indicators`` / ``concepts`` lists, or ``*_path``
overrides) so tests never walk the real corpus (CLAUDE.md section 10); the
defaults point at the on-disk taxonomy SOT.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from yen_gov.canonical.ingest.spec import IndicatorSpec, PriceBasis

# ``ingest/`` is at backend/yen_gov/canonical/ingest/; the taxonomy SOT lives
# at the repo root under datasets/taxonomy/. Resolve once at import time
# (parents[4] = repo root: ingest -> canonical -> yen_gov -> backend -> root).
_TAXONOMY_DIR: Path = (
    Path(__file__).resolve().parents[4] / "datasets" / "taxonomy"
)
DEFAULT_INDICATORS_PATH: Path = _TAXONOMY_DIR / "indicators.json"
DEFAULT_CONCEPTS_PATH: Path = _TAXONOMY_DIR / "concepts.json"


class CatalogueError(Exception):
    """Base for registration-time catalogue violations."""


class CatalogueFkError(CatalogueError):
    """``indicator_id`` (or its ``concept_id``) does not resolve to a catalogue row."""


class ConceptCompatibilityError(CatalogueError):
    """The spec's measurement tuple disagrees with its concept."""


def _load_rows(path: Path, key: str) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload[key]


def _resolve_price_basis(raw: dict | None) -> PriceBasis | None:
    """Parse a concept's on-disk ``price_basis`` dict into a comparable model.

    ``None`` (the field is absent or explicitly null) stays ``None`` so a
    concept with no price basis is equal to a spec declaring no price basis.
    """
    if raw is None:
        return None
    return PriceBasis(basis=raw["basis"], base_year=raw.get("base_year"))


def check_indicator_registration(
    spec: IndicatorSpec,
    *,
    indicators: Iterable[dict] | None = None,
    concepts: Iterable[dict] | None = None,
    indicators_path: Path | None = None,
    concepts_path: Path | None = None,
) -> None:
    """Raise unless ``spec`` passes both catalogue preconditions (a) + (b).

    Returns ``None`` on success (the spec is registrable). Raises
    :class:`CatalogueFkError` for a missing indicator/concept row,
    :class:`ConceptCompatibilityError` for a measurement-tuple mismatch.

    Pass ``indicators`` / ``concepts`` (iterables of catalogue rows) to
    override the on-disk lookup with synthetic fixtures; pass
    ``indicators_path`` / ``concepts_path`` to exercise the disk-read branch
    against a fixture file. Defaults read the real taxonomy SOT.
    """
    ind_rows = (
        list(indicators)
        if indicators is not None
        else _load_rows(indicators_path or DEFAULT_INDICATORS_PATH, "indicators")
    )
    concept_rows = (
        list(concepts)
        if concepts is not None
        else _load_rows(concepts_path or DEFAULT_CONCEPTS_PATH, "concepts")
    )

    indicator = next(
        (r for r in ind_rows if r.get("indicator_id") == spec.indicator_id), None
    )
    if indicator is None:
        raise CatalogueFkError(
            f"indicator_id {spec.indicator_id!r} is not in the indicator "
            "catalogue (datasets/taxonomy/indicators.json); the pipeline "
            "never mints identity"
        )

    concept_id = indicator.get("concept_id")
    if not concept_id:
        raise CatalogueFkError(
            f"indicator {spec.indicator_id!r} has no concept_id; cannot check "
            "concept compatibility"
        )

    concept = next(
        (r for r in concept_rows if r.get("concept_id") == concept_id), None
    )
    if concept is None:
        raise CatalogueFkError(
            f"indicator {spec.indicator_id!r} points at concept_id "
            f"{concept_id!r} which is not in datasets/taxonomy/concepts.json"
        )

    _assert_concept_compatible(spec, concept)


def _assert_concept_compatible(spec: IndicatorSpec, concept: dict) -> None:
    """Raise :class:`ConceptCompatibilityError` on any measurement-tuple mismatch."""
    mismatches: list[str] = []

    if spec.unit != concept["unit_canonical"]:
        mismatches.append(
            f"unit {spec.unit!r} != concept.unit_canonical "
            f"{concept['unit_canonical']!r}"
        )
    if spec.normalisation != concept["normalisation"]:
        mismatches.append(
            f"normalisation {spec.normalisation!r} != concept.normalisation "
            f"{concept['normalisation']!r}"
        )

    concept_price_basis = _resolve_price_basis(concept.get("price_basis"))
    if spec.price_basis != concept_price_basis:
        mismatches.append(
            f"price_basis {spec.price_basis!r} != concept.price_basis "
            f"{concept_price_basis!r}"
        )

    concept_sampling_frame = concept.get("sampling_frame")
    if spec.sampling_frame != concept_sampling_frame:
        mismatches.append(
            f"sampling_frame {spec.sampling_frame!r} != concept.sampling_frame "
            f"{concept_sampling_frame!r}"
        )

    if mismatches:
        raise ConceptCompatibilityError(
            f"IndicatorSpec for {spec.indicator_id!r} is incompatible with "
            f"concept {concept['concept_id']!r}: " + "; ".join(mismatches)
        )
