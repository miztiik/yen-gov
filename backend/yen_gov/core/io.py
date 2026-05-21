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

# Legacy folded-indicator artifact maintenance lives under
# `backend/yen_gov/legacy/folded_indicator_writer.py` and retires with
# the per-indicator JSON shards in the final Phase 2 P.* PR of
# TODO/20260517 §0e.7. While that legacy contract persists, this
# chokepoint integrates with it for any path matching
# `is_indicator_schema(schema_id)`. Net-new indicator families MUST
# pivot directly onto the canonical Parquet store and never enter
# the folded-block carry-forward branch below.
from yen_gov.legacy.folded_indicator_writer import (
    is_indicator_schema as _is_indicator_schema,
    maintain_folded_blocks as _maintain_folded_blocks,
    strip_operational as _strip_operational,
)


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

    # For indicator artifacts: transparently maintain the four folded
    # blocks introduced in schema v2.0 (`series_spec`, `methodology`,
    # `collection_inventory`, `divergence`). Composers and adapters
    # continue to emit payloads focused on `rows[]` etc.; this layer
    # carries the methodology / series_spec / divergence values
    # forward from the previously-written artifact (or builds stubs
    # when there is no prior file), and ALWAYS re-derives
    # `collection_inventory` from `rows[]` + `series_spec` so the
    # status stays honest after every refresh. Operator-set fields on
    # `collection_inventory` (`frozen`, `refetch_requested`,
    # `unavailable_periods`) are preserved across the re-derivation.
    if _is_indicator_schema(schema_id):
        document = _maintain_folded_blocks(document, path)

    # Validate before writing. Failures here are bugs in the caller's payload.
    Draft202012Validator(schema_for_validation).validate(document)

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=2, ensure_ascii=False, sort_keys=False) + "\n"

    # Write-skip gate: if the on-disk file exists and its parsed dict is
    # structurally equal to ``document`` (after stripping operational-only
    # fields per `_OPERATIONAL_STRIP_PATHS`), this is a re-emit with no real
    # change — return without writing so the file's bytes AND mtime stay
    # untouched and re-running ingest produces a clean git status. This
    # is a value-level compare, NOT a byte compare; JSON key-order or
    # whitespace differences don't matter (Python dict == is structural
    # and order-insensitive). See CLAUDE.md §10 amendment (TODO/20260517 §16).
    if path.exists():
        try:
            prior_doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prior_doc = None
        if isinstance(prior_doc, dict) and _strip_operational(prior_doc) == _strip_operational(document):
            return path

    path.write_text(text, encoding="utf-8")
    return path
