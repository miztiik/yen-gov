"""Schema registry — single source of truth for schema metadata.

Why this module exists
----------------------
Before this module, every _Artifact subclass and every composer hand-typed
its schema's `_schema_version` / `_schema_id` as a Python literal:

    class DistrictsCollection(_Artifact):
        _schema_id = "https://yen-gov.github.io/schemas/district.schema.json"
        _schema_version = "3.2"

That is a shadow copy of metadata that already exists in
`datasets/schemas/<name>.schema.json` (`x-version`, `$id`). When a schema
was bumped (district 3.1 -> 3.2 on 2026-05-13, indicator 1.2 -> 1.3 on
2026-05-14), one or more shadow copies got missed and the strict equality
check in `core/io.py` rejected the next round-trip emit. The bug sat
dormant until a test ran.

Structural fix (CLAUDE.md sec.5): there is no second source of truth. The
schema file IS the contract; this module reads `x-version` / `$id` once at
import time and caches. Models and composers call into this module instead
of typing the version themselves. Drift becomes impossible by construction.

Usage
-----
    from yen_gov.core.schema_registry import schema_id, schema_version

    class DistrictsCollection(_Artifact):
        _schema_id = schema_id("district.schema.json")
        _schema_version = schema_version("district.schema.json")

Test isolation
--------------
The registry caches per-process and resolves filenames against
`_SCHEMA_DIR`. A test that wants to point at a different schemas dir can
monkeypatch `_SCHEMA_DIR` and call `schema_doc.cache_clear()` (and the
sibling helpers' `.cache_clear()`). No Port abstraction is built for this
because no production code path needs swappability — YAGNI applies until
proven otherwise.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

# `core/` lives at backend/yen_gov/core/. Schemas live at the repo root in
# datasets/schemas/. Resolve once at import time.
_SCHEMA_DIR: Path = (
    Path(__file__).resolve().parents[3] / "datasets" / "schemas"
)


class SchemaRegistryError(Exception):
    """Raised when a schema file is missing, unreadable, or malformed.

    Always names the offending filename so the traceback is debuggable
    even when the failure happens deep in an import chain.
    """


@lru_cache(maxsize=None)
def schema_doc(filename: str) -> dict[str, Any]:
    """Return the parsed JSON Schema dict for ``filename``.

    ``filename`` is the basename under ``datasets/schemas/`` (e.g.
    ``"district.schema.json"``), not a path.
    """
    path = _SCHEMA_DIR / filename
    if not path.is_file():
        raise SchemaRegistryError(
            f"schema file not found: {filename} (expected at {path})"
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaRegistryError(
            f"schema file is not valid JSON: {filename} ({exc})"
        ) from exc


def schema_version(filename: str) -> str:
    """Return the ``x-version`` string of the named schema."""
    doc = schema_doc(filename)
    try:
        return doc["x-version"]
    except KeyError as exc:
        raise SchemaRegistryError(
            f"schema {filename!r} is missing required key 'x-version'"
        ) from exc


def schema_id(filename: str) -> str:
    """Return the ``$id`` string of the named schema."""
    doc = schema_doc(filename)
    try:
        return doc["$id"]
    except KeyError as exc:
        raise SchemaRegistryError(
            f"schema {filename!r} is missing required key '$id'"
        ) from exc
