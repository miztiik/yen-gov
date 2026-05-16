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
    path.write_text(text, encoding="utf-8")
    return path


def _is_indicator_schema(schema_id: str) -> bool:
    return schema_id.endswith("/indicator.schema.json")


def _maintain_folded_blocks(document: dict[str, Any], path: Path) -> dict[str, Any]:
    """Carry forward / derive the four v2.0 folded blocks on an indicator.

    Strategy:
      - `methodology`, `series_spec`, `divergence`: if the caller
        provided them in `payload`, keep them verbatim. Else, if a
        prior artifact exists on disk, lift them from there. Else,
        build a stub (mirrors `tools/migrate_indicators_v15_to_v20`
        defaults).
      - `collection_inventory`: ALWAYS re-derived from
        `rows[]` + `series_spec` (preserving operator-set fields
        from the prior on-disk artifact when present).
    """
    # Lazy import to avoid circulars between core.io and inventory.
    from yen_gov.inventory import derive_collection_inventory

    prior: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                prior = loaded
        except (OSError, json.JSONDecodeError):
            prior = {}

    universes = _load_universes(path)

    # methodology / series_spec / divergence: caller wins, then prior, then stub.
    if "methodology" not in document:
        document["methodology"] = prior.get("methodology") or _stub_methodology(document)
    if "series_spec" not in document:
        document["series_spec"] = prior.get("series_spec") or _stub_series_spec(document)
    if "divergence" not in document:
        document["divergence"] = prior.get("divergence", None)

    # collection_inventory: always recompute from the now-final
    # series_spec + rows. Splice in operator-set fields from the prior
    # so a re-run doesn't clobber `frozen: true` / `unavailable_periods`.
    document["collection_inventory"] = derive_collection_inventory(document, universes)
    prior_inv = prior.get("collection_inventory") or {}
    for op_field in ("frozen", "refetch_requested", "unavailable_periods"):
        if op_field in prior_inv:
            document["collection_inventory"][op_field] = prior_inv[op_field]

    return document


def _load_universes(path: Path) -> dict[str, Any]:
    """Load `datasets/reference/in/universes.json` relative to the artifact path.

    Walks up from `path` until it finds a directory containing
    `datasets/reference/in/universes.json`. Returns `{}` when not
    found (legitimate during unit tests with a tmp_path tree).
    """
    cur = path.resolve().parent
    for _ in range(10):
        candidate = cur / "datasets" / "reference" / "in" / "universes.json"
        if candidate.is_file():
            try:
                loaded = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    return loaded
            except (OSError, json.JSONDecodeError):
                return {}
        if cur.parent == cur:
            break
        cur = cur.parent
    return {}


def _stub_methodology(document: dict[str, Any]) -> dict[str, Any]:
    ind = document.get("indicator") or {}
    definition = ind.get("description") or ind.get("title") or "Definition stub — please edit."
    if len(definition) < 10:
        definition = f"{definition} (stub)"
    return {
        "definition": definition,
        "publisher": "Unknown publisher (stub — please edit)",
        "publisher_methodology_url": None,
        "documentation_status": "stub",
        "methodology_breaks": [],
        "known_caveats": [],
        "notes": [],
    }


def _stub_series_spec(document: dict[str, Any]) -> dict[str, Any]:
    rows = document.get("rows") or []
    ind = document.get("indicator") or {}
    time_grain = ind.get("time_grain") or "year"
    grain_to_freq = {
        "fiscal_year": "annual_fy",
        "year": "annual_cy",
        "month": "monthly",
        "quarter": "quarterly_cy",
        "date": "ad_hoc",
        "decade": "decennial",
    }
    frequency = grain_to_freq.get(time_grain, "ad_hoc")
    geographies = sorted({str(r["entity_id"]) for r in rows if "entity_id" in r})
    periods: dict[str, dict[str, str]] = {}
    for r in rows:
        t = r.get("time")
        if t is None:
            continue
        k = str(t)
        if k not in periods:
            periods[k] = {"key": k, "label": k, "frequency": frequency}
    description_src = ind.get("description") or ind.get("title") or "Series description (stub)."
    description = description_src if len(description_src) >= 10 else f"{description_src} (stub)"
    return {
        "description": description,
        "expected_geographies": geographies,
        "expected_periods": [periods[k] for k in sorted(periods)],
        "expected_periods_inference": {
            "basis": "seeded_from_observed_rows",
            "confidence": "none",
            "series": None,
            "note": "Auto-seeded by core.io.write_artifact at refresh time. Replace with publisher-catalogue-derived expectations when an editor reviews this indicator.",
        },
    }
