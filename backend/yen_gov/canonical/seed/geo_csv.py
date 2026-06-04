"""B2a.5 entities/geo.csv emitter.

Lift ``datasets/taxonomy/lgd_states.json`` + ``datasets/taxonomy/lgd_districts.json``
(LGD authoritative registers) to ``datasets/data/entities/geo.csv`` per the
LGD administrative ladder (parent plan section 3, sub-plan B2a.5).

Columns retained (per ``datasets/data/_schema/columns.json``):

- ``entity_id``   (PK)
- ``name``
- ``parent``      (self-FK; NULL only for the country root)
- ``entity_kind`` (closed enum; v1 emits ``country | state | district``)
- ``aliases``     (pipe-delimited cross-id list for yen-ask grounding;
                    plan section 20.10; nullable)

Identity scheme (v1 - mirrors LGD-canonical doctrine, prior PR series #559+):

- country:  ``IN``
- state:    LGD slug (e.g. ``tamil-nadu``); aliases carry
            ``<iso_alpha>|<eci_st_code>|lgd:<lgd_state_id>``.
- district: ``<state-slug>/<district-slug>`` composite (LGD district slugs
            collide across states for e.g. ``bilaspur``, ``hamirpur``,
            ``pratapgarh``; the composite disambiguates without minting an
            opaque integer id); aliases carry ``lgd:<lgd_district_id>``.

Sub-district + village rows are admissible by columns.json but NOT emitted
in v1 (no current consumer; future ingest extends).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv


FILE_CLASS = "datasets/data/entities/geo.csv"

COUNTRY_ENTITY_ID = "IN"
COUNTRY_NAME = "India"


def _read_json_list(path: Path, key: str) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get(key)
    if not isinstance(entries, list):
        raise ValueError(f"{path}: missing or non-list {key!r} key")
    return entries


def _state_aliases(entry: dict[str, Any]) -> str | None:
    parts: list[str] = []
    iso = entry.get("iso_alpha")
    eci = entry.get("eci_st_code")
    lgd_id = entry.get("lgd_state_id")
    if iso:
        parts.append(str(iso))
    if eci:
        parts.append(str(eci))
    if lgd_id is not None:
        parts.append(f"lgd:{lgd_id}")
    return "|".join(parts) if parts else None


def _district_alias(entry: dict[str, Any]) -> str | None:
    lgd_id = entry.get("lgd_district_id")
    return f"lgd:{lgd_id}" if lgd_id is not None else None


def emit(
    *,
    lgd_states_json: Path,
    lgd_districts_json: Path,
    out_path: Path,
) -> Path:
    """Emit ``out_path`` from the two LGD registers; return the resolved path.

    Raises:
        FileNotFoundError: either input is missing.
        ValueError: required field missing, identity collision, ``__`` in any
            emitted entity_id (plan section 21.6), or district references an
            unknown ``lgd_state_id``.
    """
    if not lgd_states_json.exists():
        raise FileNotFoundError(lgd_states_json)
    if not lgd_districts_json.exists():
        raise FileNotFoundError(lgd_districts_json)

    states = _read_json_list(lgd_states_json, "states")
    districts = _read_json_list(lgd_districts_json, "districts")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    rows.append(
        {
            "entity_id": COUNTRY_ENTITY_ID,
            "name": COUNTRY_NAME,
            "parent": None,
            "entity_kind": "country",
            "aliases": "IN|IND|356",
        }
    )
    seen.add(COUNTRY_ENTITY_ID)

    state_slug_by_lgd_id: dict[int, str] = {}
    for entry in states:
        lgd_id = entry.get("lgd_state_id")
        slug = entry.get("slug")
        name = entry.get("lgd_name_short") or entry.get("lgd_name")
        if not isinstance(lgd_id, int):
            raise ValueError(f"state entry missing integer 'lgd_state_id': {entry!r}")
        if not slug or not isinstance(slug, str):
            raise ValueError(f"state {lgd_id} missing 'slug'")
        if not name or not isinstance(name, str):
            raise ValueError(f"state {lgd_id} missing 'lgd_name'")
        if "__" in slug:
            raise ValueError(
                f"state slug must not contain '__' (plan section 21.6): {slug!r}"
            )
        if slug in seen:
            raise ValueError(f"duplicate state entity_id: {slug!r}")
        seen.add(slug)
        state_slug_by_lgd_id[lgd_id] = slug
        rows.append(
            {
                "entity_id": slug,
                "name": name,
                "parent": COUNTRY_ENTITY_ID,
                "entity_kind": "state",
                "aliases": _state_aliases(entry),
            }
        )

    for entry in districts:
        lgd_state_id = entry.get("lgd_state_id")
        lgd_district_id = entry.get("lgd_district_id")
        slug = entry.get("slug")
        name = entry.get("lgd_name")
        if not isinstance(lgd_state_id, int):
            raise ValueError(
                f"district entry missing integer 'lgd_state_id': {entry!r}"
            )
        if not isinstance(lgd_district_id, int):
            raise ValueError(
                f"district entry missing integer 'lgd_district_id': {entry!r}"
            )
        if not slug or not isinstance(slug, str):
            raise ValueError(f"district {lgd_district_id} missing 'slug'")
        if not name or not isinstance(name, str):
            raise ValueError(f"district {lgd_district_id} missing 'lgd_name'")
        parent_slug = state_slug_by_lgd_id.get(lgd_state_id)
        if parent_slug is None:
            raise ValueError(
                f"district {lgd_district_id} references unknown lgd_state_id={lgd_state_id}"
            )
        entity_id = f"{parent_slug}/{slug}"
        if "__" in entity_id:
            raise ValueError(
                f"district entity_id must not contain '__' (plan section 21.6): {entity_id!r}"
            )
        if entity_id in seen:
            raise ValueError(f"duplicate district entity_id: {entity_id!r}")
        seen.add(entity_id)
        rows.append(
            {
                "entity_id": entity_id,
                "name": name,
                "parent": parent_slug,
                "entity_kind": "district",
                "aliases": _district_alias(entry),
            }
        )

    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
