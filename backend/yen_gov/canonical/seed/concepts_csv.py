"""B2a.3 concepts.csv emitter.

Lift ``datasets/taxonomy/concepts.json`` (hand-authored concept registry)
to ``datasets/data/concepts.csv`` (F6 one-row-per-concept identity per
parent plan section 3 / sub-plan B2a.3).

Columns retained (per ``datasets/data/_schema/columns.json``):

- ``concept_id``     (PK)
- ``noun``
- ``unit_canonical``
- ``normalisation``  (closed enum; matches ``concepts.schema.json``)
- ``entity_kinds``   (space-joined list of admissible grains)
- ``description``    (lifted from taxonomy ``description_short``; nullable)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv


FILE_CLASS = "datasets/data/concepts.csv"


def _read_concepts(concepts_json: Path) -> list[dict[str, Any]]:
    payload = json.loads(concepts_json.read_text(encoding="utf-8"))
    entries = payload.get("concepts")
    if not isinstance(entries, list):
        raise ValueError(
            f"{concepts_json}: missing or non-list 'concepts' key"
        )
    return entries


def emit(*, concepts_json: Path, out_path: Path) -> Path:
    """Emit ``out_path`` from ``concepts_json``; return the resolved path.

    Raises:
        FileNotFoundError: ``concepts_json`` does not exist.
        ValueError: a concept entry is missing a required field, declares
            an id containing ``__`` (plan section 21.6 / 21.12), or
            duplicates an existing ``concept_id``.
    """
    if not concepts_json.exists():
        raise FileNotFoundError(concepts_json)

    entries = _read_concepts(concepts_json)
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for entry in entries:
        concept_id = entry.get("concept_id")
        noun = entry.get("noun")
        unit_canonical = entry.get("unit_canonical")
        normalisation = entry.get("normalisation")
        entity_kinds = entry.get("entity_kinds")
        description = entry.get("description_short")
        if not concept_id or not isinstance(concept_id, str):
            raise ValueError(f"concept entry missing 'concept_id': {entry!r}")
        if "__" in concept_id:
            raise ValueError(
                f"concept_id must not contain '__' (plan section 21.6): {concept_id!r}"
            )
        if concept_id in seen:
            raise ValueError(f"duplicate concept_id: {concept_id!r}")
        if not noun or not isinstance(noun, str):
            raise ValueError(f"concept {concept_id!r} missing 'noun'")
        if not unit_canonical or not isinstance(unit_canonical, str):
            raise ValueError(f"concept {concept_id!r} missing 'unit_canonical'")
        if not normalisation or not isinstance(normalisation, str):
            raise ValueError(f"concept {concept_id!r} missing 'normalisation'")
        if not isinstance(entity_kinds, list) or not entity_kinds:
            raise ValueError(
                f"concept {concept_id!r} missing non-empty 'entity_kinds' list"
            )
        if not all(isinstance(k, str) and k for k in entity_kinds):
            raise ValueError(
                f"concept {concept_id!r} 'entity_kinds' must be non-empty strings"
            )
        seen.add(concept_id)
        rows.append(
            {
                "concept_id": concept_id,
                "noun": noun,
                "unit_canonical": unit_canonical,
                "normalisation": normalisation,
                "entity_kinds": " ".join(entity_kinds),
                "description": description or None,
            }
        )

    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
