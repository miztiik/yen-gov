"""B2a.2 topics.csv emitter.

Lift ``datasets/taxonomy/topics.json`` (hand-authored topic catalogue) to
``datasets/data/topics.csv`` (Gapminder parent-pointer shape per parent
plan section 3).

Columns retained (per ``datasets/data/_schema/columns.json``):

- ``topic``  (PK; ``id`` field on the taxonomy entry)
- ``name``   (from taxonomy ``title``)
- ``parent`` (self-FK; NULL for pillars / roots)

The v2 taxonomy is flat (all 18 entries are pillars with no parent), so
every emitted row has ``parent IS NULL``. The schema admits a nested tree
in a future v3 - until then the emitter accepts an optional ``parent``
field on the taxonomy entry and passes it through unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv


FILE_CLASS = "datasets/data/topics.csv"


def _read_topics(topics_json: Path) -> list[dict[str, Any]]:
    payload = json.loads(topics_json.read_text(encoding="utf-8"))
    entries = payload.get("topics")
    if not isinstance(entries, list):
        raise ValueError(
            f"{topics_json}: missing or non-list 'topics' key"
        )
    return entries


def emit(*, topics_json: Path, out_path: Path) -> Path:
    """Emit ``out_path`` from ``topics_json``; return the resolved path.

    Raises:
        FileNotFoundError: ``topics_json`` does not exist.
        ValueError: a topic entry is missing ``id`` or ``title``, or any
            id contains ``__`` (plan section 21.6 / 21.12).
    """
    if not topics_json.exists():
        raise FileNotFoundError(topics_json)

    entries = _read_topics(topics_json)
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for entry in entries:
        topic = entry.get("id")
        name = entry.get("title")
        parent = entry.get("parent")
        if not topic or not isinstance(topic, str):
            raise ValueError(f"topic entry missing 'id': {entry!r}")
        if not name or not isinstance(name, str):
            raise ValueError(f"topic entry missing 'title': {entry!r}")
        if "__" in topic:
            raise ValueError(
                f"topic id must not contain '__' (plan section 21.6): {topic!r}"
            )
        if topic in seen:
            raise ValueError(f"duplicate topic id: {topic!r}")
        seen.add(topic)
        rows.append({"topic": topic, "name": name, "parent": parent or None})

    declared_parents = {row["parent"] for row in rows if row["parent"]}
    missing = declared_parents - seen
    if missing:
        raise ValueError(
            f"topics.json references unknown parent ids: {sorted(missing)}"
        )

    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
