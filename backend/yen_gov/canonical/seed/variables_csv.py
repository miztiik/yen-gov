"""B2a.4 variables.csv emitter.

Lift ``datasets/taxonomy/indicators.json`` (hand-authored indicator
catalogue) to ``datasets/data/variables.csv`` (indicator catalogue per
parent plan section 3 / sub-plan B2a.4).

Columns emitted (per ``datasets/data/_schema/columns.json``):

- ``indicator_id``         (PK)
- ``name``                 (lifted from taxonomy ``label_short``)
- ``concept_id``           (FK -> concepts.csv; non-null per F6 / ADR-0044)
- ``unit``
- ``derivation``           (nullable; not present in taxonomy v1; emitted NULL)
- ``topic``                (FK -> topics.csv; first entry of ``topic_tags``)
- ``source_id``            (FK -> entities/source.csv; nullable)
- ``update_period_days``   (non-null integer; publisher refresh cadence)
- ``time_min``             (nullable; B2b backfills from datapoints)
- ``time_max``             (nullable; B2b backfills from datapoints)
- ``entity_kinds``         (nullable; B2b backfills as the observed-set;
                            in B2a it is left NULL even though the taxonomy
                            declares a list - see sub-plan B2a.4 note)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv


FILE_CLASS = "datasets/data/variables.csv"


def _read_indicators(indicators_json: Path) -> list[dict[str, Any]]:
    payload = json.loads(indicators_json.read_text(encoding="utf-8"))
    entries = payload.get("indicators")
    if not isinstance(entries, list):
        raise ValueError(
            f"{indicators_json}: missing or non-list 'indicators' key"
        )
    return entries


def emit(*, indicators_json: Path, out_path: Path) -> Path:
    """Emit ``out_path`` from ``indicators_json``; return the resolved path.

    Raises:
        FileNotFoundError: ``indicators_json`` does not exist.
        ValueError: an indicator entry is missing a required field, declares
            an id containing ``__`` (plan section 21.6 / 21.12), or
            duplicates an existing ``indicator_id``.
    """
    if not indicators_json.exists():
        raise FileNotFoundError(indicators_json)

    entries = _read_indicators(indicators_json)
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for entry in entries:
        indicator_id = entry.get("indicator_id")
        name = entry.get("label_short")
        concept_id = entry.get("concept_id")
        unit = entry.get("unit")
        topic_tags = entry.get("topic_tags")
        source_id = entry.get("source_id")
        update_period_days = entry.get("update_period_days")
        if not indicator_id or not isinstance(indicator_id, str):
            raise ValueError(f"indicator entry missing 'indicator_id': {entry!r}")
        if "__" in indicator_id:
            raise ValueError(
                f"indicator_id must not contain '__' (plan section 21.6): "
                f"{indicator_id!r}"
            )
        if indicator_id in seen:
            raise ValueError(f"duplicate indicator_id: {indicator_id!r}")
        if not name or not isinstance(name, str):
            raise ValueError(
                f"indicator {indicator_id!r} missing 'label_short'"
            )
        if not concept_id or not isinstance(concept_id, str):
            raise ValueError(
                f"indicator {indicator_id!r} missing 'concept_id' (F6)"
            )
        if not unit or not isinstance(unit, str):
            raise ValueError(f"indicator {indicator_id!r} missing 'unit'")
        if not isinstance(topic_tags, list) or not topic_tags:
            raise ValueError(
                f"indicator {indicator_id!r} missing non-empty 'topic_tags'"
            )
        topic = topic_tags[0]
        if not isinstance(topic, str) or not topic:
            raise ValueError(
                f"indicator {indicator_id!r} 'topic_tags[0]' must be a non-empty string"
            )
        if not isinstance(update_period_days, int) or isinstance(
            update_period_days, bool
        ):
            raise ValueError(
                f"indicator {indicator_id!r} missing integer 'update_period_days'"
            )
        if source_id is not None and (
            not isinstance(source_id, str) or not source_id
        ):
            raise ValueError(
                f"indicator {indicator_id!r} 'source_id' must be a non-empty string when set"
            )
        seen.add(indicator_id)
        rows.append(
            {
                "indicator_id": indicator_id,
                "name": name,
                "concept_id": concept_id,
                "unit": unit,
                "derivation": None,
                "topic": topic,
                "source_id": source_id,
                "update_period_days": update_period_days,
                "time_min": None,
                "time_max": None,
                "entity_kinds": None,
            }
        )

    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
