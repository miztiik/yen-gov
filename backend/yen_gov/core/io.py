"""Schema-stamped JSON artifact writer.

The single chokepoint for emitting any file under datasets/. Every artifact
that leaves the pipeline goes through write_artifact, which:

  - stamps $schema (URL) and $schema_version (current x-version of the schema)
  - stamps the sources array (provenance per ADR-0002)
  - validates against the schema before writing (Tier B equivalent, in-process)
  - writes UTF-8 with sorted top-level keys, trailing newline, 2-space indent
  - uses POSIX paths in any string the writer emits (CLAUDE.md §2)

Callers pass payload as a plain dict. Pydantic models live one layer up
(core/models.py) and are responsible for serialising themselves to dicts
before reaching this module — so io.py stays schema-agnostic and is easy
to test without the full model layer in place.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class Source:
    """One provenance entry. Mirrors the {url, fetched_at} object in every schema."""

    url: str
    fetched_at: datetime

    def to_dict(self) -> dict[str, str]:
        ts = self.fetched_at
        if ts.tzinfo is None:
            raise ValueError("Source.fetched_at must be timezone-aware (use UTC)")
        # Normalise to UTC and emit with trailing 'Z' to match RFC 3339.
        utc = ts.astimezone(timezone.utc).replace(tzinfo=None)
        return {"url": self.url, "fetched_at": utc.isoformat(timespec="seconds") + "Z"}


def write_artifact(
    *,
    path: Path,
    schema_id: str,
    schema_version: str,
    payload: dict[str, Any],
    sources: list[Source],
    schema_for_validation: dict[str, Any],
) -> Path:
    """Write a schema-stamped JSON artifact and return the resolved path.

    Args:
        path: target file path (any platform).
        schema_id: $id from the target schema, used as the stamped $schema URL.
        schema_version: must equal the schema's current x-version. Validator
            (Tier B) will reject mismatches; we check here too for early feedback.
        payload: the artifact body. MUST NOT contain $schema, $schema_version,
            or sources — those are stamped here. Raises if it does.
        sources: provenance entries. Empty list signals hand-authored (ADR-0002).
        schema_for_validation: the parsed JSON Schema document. Validation runs
            before we touch disk.

    Raises:
        ValueError: payload contains reserved keys, or post-stamp validation fails.
    """
    reserved = {"$schema", "$schema_version", "sources"}
    overlap = reserved & payload.keys()
    if overlap:
        raise ValueError(f"payload must not include reserved keys: {sorted(overlap)}")

    if schema_for_validation.get("x-version") != schema_version:
        raise ValueError(
            f"schema_version {schema_version!r} does not match schema x-version "
            f"{schema_for_validation.get('x-version')!r}"
        )

    document: dict[str, Any] = {
        "$schema": schema_id,
        "$schema_version": schema_version,
        "sources": [s.to_dict() for s in sources],
        **payload,
    }

    # Validate before writing. Failures here are bugs in the caller's payload.
    Draft202012Validator(schema_for_validation).validate(document)

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return path
