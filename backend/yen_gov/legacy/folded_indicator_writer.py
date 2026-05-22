"""Legacy folded-indicator artifact maintenance.

This module implements behaviour that is bound to the legacy
per-indicator JSON shard contract under
`datasets/indicators/in/<topic>/<id>.json` (schema v3.0 → v4.0).
Under the canonical pivot (ADR-0030 + ADR-0032 +
TODO/20260517-canonical-long-format-pivot.md §0e.7), every indicator
family migrates to long-format observation rows in Hive-partitioned
Parquet under `datasets/indicators/<family>/...` plus
`datasets/taxonomy/indicators.parquet`. When the last per-indicator
JSON shard is deleted (final P.* PR in §0e.7), the call-site in
`backend/yen_gov/core/io.py.write_artifact` deletes with it and this
module is removed.

Until then, this module is the single home for:

  * `OPERATIONAL_STRIP_PATHS`: structural-equality strip-list for the
    write-skip gate. Each entry is a place where the legacy contract
    is silently leaky (operator-clock telemetry baked into citizen
    artifacts) and we are accepting that until the family migrates.
  * `strip_operational` / `strip_path`: helpers for the strip-list.
  * `is_indicator_schema`: predicate naming the legacy schema family.
  * `maintain_folded_blocks`: caller-wins / prior-wins / stub
    derivation of `methodology`, `series_spec`, `divergence`.
  * `_stub_methodology` / `_stub_series_spec`: stub builders for
    indicators with no prior artifact on disk.

Net-new indicator data MUST NOT pass through this module — new
indicator families pivot directly onto the canonical Parquet store
(see `backend/yen_gov/canonical/writer.py`).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


# Operational / non-deterministic fields stripped before the dict-equal
# write-skip compare in `core/io.py.write_artifact`. These vary
# run-to-run for reasons unrelated to the artifact's data content
# (operator-clock telemetry, not citizen content) so byte-identical
# re-runs MUST still hit the skip path. Each entry is a JSON path read
# by `strip_path`. Keep this list short and append only with a
# rationale comment — every entry is a place where the legacy contract
# is silently leaky. See CLAUDE.md §10 amendment (commit 19 of
# TODO/20260517 §16). This list retires with the module.
OPERATIONAL_STRIP_PATHS: tuple[tuple[str, ...], ...] = (
    # `sources[].fetched_at` — operator-clock at fetch time. Until each
    # adapter migrates to publisher-`Last-Modified` / release-vintage
    # derivation (§16 commit 13), wall-clock leaks into this field.
    ("sources", "*", "fetched_at"),
    # `collection_inventory.last_collected_at` — derived `max(sources[].fetched_at)`.
    # Removed entirely when the block is lifted out of the artifact in
    # §16 commits 4-7; harmless strip until then.
    ("collection_inventory", "last_collected_at"),
)


def strip_operational(doc: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of ``doc`` with operational-only fields removed.

    Used by `core/io.py.write_artifact` to compare a candidate artifact
    against the on-disk file's parsed dict, ignoring fields whose value
    alone changes on every run for reasons unrelated to data content.
    """
    out = copy.deepcopy(doc)
    for path in OPERATIONAL_STRIP_PATHS:
        strip_path(out, path)
    return out


def strip_path(doc: Any, path: tuple[str, ...]) -> None:
    if not path:
        return
    head, *rest = path
    if head == "*":
        if isinstance(doc, list):
            for item in doc:
                strip_path(item, tuple(rest))
        return
    if not isinstance(doc, dict):
        return
    if not rest:
        doc.pop(head, None)
        return
    if head in doc:
        strip_path(doc[head], tuple(rest))


def is_indicator_schema(schema_id: str) -> bool:
    return schema_id.endswith("/indicator.schema.json")


def maintain_folded_blocks(document: dict[str, Any], path: Path) -> dict[str, Any]:
    """Carry forward / derive the three v4.0 folded blocks on an indicator.

    Strategy (v4.0 — `collection_inventory` lifted OUT of the artifact;
    see ADR-0026 and TODO/20260517 §16):
      - `methodology`, `series_spec`, `divergence`: if the caller
        provided them in `payload`, keep them verbatim. Else, if a
        prior artifact exists on disk, lift them from there. Else,
        build a stub. `series_spec` in v4.0 is `{description}` only;
        observed/expected periods + geographies now live in the
        external completeness index `datasets/reference/in/indicators-completeness.json`.
    """
    prior: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                prior = loaded
        except (OSError, json.JSONDecodeError):
            prior = {}

    # methodology / series_spec / divergence: caller wins, then prior, then stub.
    if "methodology" not in document:
        document["methodology"] = prior.get("methodology") or _stub_methodology(document)
    if "series_spec" not in document:
        document["series_spec"] = prior.get("series_spec") or _stub_series_spec(document)
    if "divergence" not in document:
        document["divergence"] = prior.get("divergence", None)

    return document


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
    """v4.0 stub: description only. Observed/expected periods + geographies
    moved to the external completeness index."""
    ind = document.get("indicator") or {}
    description_src = ind.get("description") or ind.get("title") or "Series description (stub)."
    description = description_src if len(description_src) >= 10 else f"{description_src} (stub)"
    return {"description": description}
