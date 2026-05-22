"""Wikipedia reference scrape: constituencies for one state.

Companion to `pipeline/run.py`. Where `run` orchestrates ECI result fetching,
this module orchestrates the one-shot Wikipedia constituency scrape that
populates `datasets/reference/in/states/<S>/constituencies.json`.

Districts are no longer scraped from Wikipedia. The 145 current districts
live as hand-curated `entity_type='district'` rows on
`datasets/taxonomy/entities.json`, sourced from the Local Government
Directory (Ministry of Panchayati Raj) per CLAUDE.md §3. The district-name
→ `district_id` lookup that the constituencies parser needs is built from
entities.json by `_district_lookup_from_entities()` below — mapping each
entity's `display_name` to its `legacy_id` (the 3-letter wikipedia-derived
id that the existing `constituencies.json` files cross-reference). See
ADR-0033 and TODO/20260522-districts-wikipedia-adapter-retirement-handover.md.

Kept separate from `pipeline/run.py` because:
  - The Wikipedia adapter is a one-shot per state per delimitation cycle, not
    a per-event run. Different cadence, different output tree.
  - It needs a different UA string (descriptive, per Wikipedia bot etiquette
    — see docs/architecture/backend/sources-wikipedia.md) than the ECI fetcher.
  - It writes under `datasets/reference/`, not `datasets/elections/`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from yen_gov.core.http import Fetcher
from yen_gov.core.io import write_artifact
from yen_gov.core.models import (
    ConstituenciesCollection,
    ConstituencyEntry,
    SourceRef,
)
from yen_gov.sources.wikipedia.constituencies import (
    build_district_lookup, parse_ac_constituencies,
)
from yen_gov.sources.wikipedia.urls import ac_constituencies_url


@dataclass(frozen=True)
class ReferencePaths:
    constituencies: Path


@dataclass(frozen=True)
class ReferenceResult:
    constituencies: ConstituenciesCollection
    paths: ReferencePaths


def scrape_state_reference(
    *,
    state_code: str,
    output_dir: Path,
    schema_dir: Path,
    fetcher: Fetcher,
    entities_path: Path,
) -> ReferenceResult:
    """Fetch + parse + emit constituencies.json for one state.

    The district-name lookup that resolves the AC table's District column
    to `district_id` is read from `entities_path` (entities.json) rather
    than from a freshly-scraped districts.json. Unresolved district names
    silently land as `district_id=None` on the constituency entry, matching
    the pre-retirement behaviour for unresolved heuristic matches
    (docs/architecture/backend/sources-wikipedia.md).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    district_id_by_name = _district_lookup_from_entities(
        entities_path, state_eci_code=state_code,
    )

    c_url = ac_constituencies_url(state_code)
    c_fr = fetcher.fetch(c_url)
    c_src = SourceRef(url=c_fr.url, fetched_at=c_fr.fetched_at)
    constituencies = parse_ac_constituencies(
        c_fr.content, state_code=state_code, sources=[c_src],
        district_id_by_name=district_id_by_name,
    )
    constituencies_path = output_dir / "constituencies.json"
    write_artifact(
        path=constituencies_path,
        schema_id=constituencies._schema_id,
        schema_version=constituencies._schema_version,
        payload=constituencies.body_payload(),
        sources=constituencies.sources_payload(),
        schema_for_validation=_load_schema(schema_dir, "constituency.schema.json"),
    )

    return ReferenceResult(
        constituencies=constituencies,
        paths=ReferencePaths(constituencies=constituencies_path),
    )


def _district_lookup_from_entities(
    entities_path: Path, *, state_eci_code: str,
) -> dict[str, str]:
    """Build `{district_display_name -> legacy_id}` lookup from entities.json.

    Filters to current districts (`entity_type='district'`,
    `parent_entity_id=f'IN-{state}'`, `entity_valid_to IS NULL`) in the given
    state. Returns `{}` when entities.json is missing or has no districts
    seeded for this state (e.g. the Mahe and Yanam Puducherry regions which
    LGD does not enumerate as standalone districts — the constituencies parser
    tolerates `{}` and silently leaves `district_id=None` for unresolved
    names, matching pre-retirement behaviour for heuristic misses).
    """
    if not entities_path.exists():
        return {}
    doc = json.loads(entities_path.read_text(encoding="utf-8"))
    parent_id = f"IN-{state_eci_code}"
    pairs = [
        (e["display_name"], e["legacy_id"])
        for e in doc.get("entities", [])
        if e.get("entity_type") == "district"
        and e.get("parent_entity_id") == parent_id
        and e.get("legacy_id")
        and e.get("entity_valid_to") is None
    ]
    return build_district_lookup(pairs)


def _load_schema(schema_dir: Path, name: str) -> dict:
    return json.loads((schema_dir / name).read_text(encoding="utf-8"))
