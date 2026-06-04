"""B2a.6 entities/electoral.csv emitter.

Lift ``datasets/taxonomy/lgd_acs.json`` + ``datasets/taxonomy/lgd_pcs.json``
(LGD authoritative Assembly/Parliamentary Constituency registers) to
``datasets/data/entities/electoral.csv`` per the new long-format CSV contract
(parent plan section 3, sub-plan B2a.6).

Columns retained (per ``datasets/data/_schema/columns.json``):

- ``entity_id``   (PK)
- ``name``
- ``entity_kind`` (closed enum: ``ac | pc``)
- ``delim_year``  (integer; v1 emits 2008 only)
- ``state``       (FK -> ``entities/geo.csv.entity_id``; the LGD state slug)
- ``parent``      (AC -> its PC entity_id; PC -> its state slug)
- ``reservation`` (enum ``GEN | SC | ST``; NULL in v1 - LGD register does not
                    carry reservation per the source $comment in lgd_acs.json)

Identity scheme (v1 - LGD-native, mirrors the existing ECI shape adapted to
LGD primary keys since lgd_acs.json explicitly does NOT carry ECI ac_no):

- PC:  ``IN-PC-<delim_year>-<state-slug>-<lgd_pc_id>``
- AC:  ``IN-AC-<delim_year>-<state-slug>-<lgd_ac_id>``

The integer LGD id guarantees uniqueness (within-state slug collisions exist
in lgd_acs.json; sample: 12 duplicate ``(lgd_state_id, slug)`` pairs as of the
2026-06-01 snapshot). The slug rides in a future ``aliases`` column when one
is added; not part of the v1 contract.

LGD/ECI key separation (parent plan F3 / 20.5 / sub-plan invariant 2): this
file MUST NOT carry any LGD district FK. The only AC/PC <-> LGD-district
meeting point is ``entities/electoral_lgd_xwalk.csv`` (B2a.7).

v1 freezes ``delim_year`` at 2008 (no 2026 rows yet); future delimitation
cycles are append-rows-never-overwrite (plan section 3).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv


FILE_CLASS = "datasets/data/entities/electoral.csv"

# LGD register snapshot is post-2008 delimitation (parent plan section 3 +
# source $comment in datasets/taxonomy/lgd_acs.json).
DELIM_YEAR_V1 = 2008


def _read_json_list(path: Path, key: str) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get(key)
    if not isinstance(entries, list):
        raise ValueError(f"{path}: missing or non-list {key!r} key")
    return entries


def _state_slug_index(states: list[dict[str, Any]]) -> dict[int, str]:
    out: dict[int, str] = {}
    for entry in states:
        lgd_id = entry.get("lgd_state_id")
        slug = entry.get("slug")
        if not isinstance(lgd_id, int):
            raise ValueError(f"state entry missing integer 'lgd_state_id': {entry!r}")
        if not slug or not isinstance(slug, str):
            raise ValueError(f"state {lgd_id} missing 'slug'")
        out[lgd_id] = slug
    return out


def _pc_entity_id(state_slug: str, lgd_pc_id: int, delim_year: int) -> str:
    return f"IN-PC-{delim_year}-{state_slug}-{lgd_pc_id}"


def _ac_entity_id(state_slug: str, lgd_ac_id: int, delim_year: int) -> str:
    return f"IN-AC-{delim_year}-{state_slug}-{lgd_ac_id}"


def emit(
    *,
    lgd_states_json: Path,
    lgd_acs_json: Path,
    lgd_pcs_json: Path,
    out_path: Path,
    delim_year: int = DELIM_YEAR_V1,
) -> Path:
    """Emit ``out_path`` from the three LGD registers; return the resolved path.

    Raises:
        FileNotFoundError: any input is missing.
        ValueError: required field missing, identity collision, ``__`` in any
            emitted entity_id (plan section 21.6), or an AC/PC references an
            unknown ``lgd_state_id`` / ``lgd_pc_id``.
    """
    for p in (lgd_states_json, lgd_acs_json, lgd_pcs_json):
        if not p.exists():
            raise FileNotFoundError(p)

    states = _read_json_list(lgd_states_json, "states")
    pcs = _read_json_list(lgd_pcs_json, "pcs")
    acs = _read_json_list(lgd_acs_json, "acs")

    state_slug_by_lgd_id = _state_slug_index(states)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    pc_entity_id_by_lgd_pc_id: dict[int, str] = {}

    for entry in pcs:
        lgd_pc_id = entry.get("lgd_pc_id")
        lgd_state_id = entry.get("lgd_state_id")
        name = entry.get("pc_name")
        if not isinstance(lgd_pc_id, int):
            raise ValueError(f"pc entry missing integer 'lgd_pc_id': {entry!r}")
        if not isinstance(lgd_state_id, int):
            raise ValueError(f"pc {lgd_pc_id} missing integer 'lgd_state_id'")
        if not name or not isinstance(name, str):
            raise ValueError(f"pc {lgd_pc_id} missing 'pc_name'")
        state_slug = state_slug_by_lgd_id.get(lgd_state_id)
        if state_slug is None:
            raise ValueError(
                f"pc {lgd_pc_id} references unknown lgd_state_id={lgd_state_id}"
            )
        entity_id = _pc_entity_id(state_slug, lgd_pc_id, delim_year)
        if "__" in entity_id:
            raise ValueError(
                f"pc entity_id must not contain '__' (plan section 21.6): {entity_id!r}"
            )
        if entity_id in seen:
            raise ValueError(f"duplicate pc entity_id: {entity_id!r}")
        seen.add(entity_id)
        pc_entity_id_by_lgd_pc_id[lgd_pc_id] = entity_id
        rows.append(
            {
                "entity_id": entity_id,
                "name": name,
                "entity_kind": "pc",
                "delim_year": delim_year,
                "state": state_slug,
                "parent": state_slug,
                "reservation": None,
            }
        )

    for entry in acs:
        lgd_ac_id = entry.get("lgd_ac_id")
        lgd_state_id = entry.get("lgd_state_id")
        lgd_pc_id = entry.get("lgd_pc_id")
        name = entry.get("ac_name")
        if not isinstance(lgd_ac_id, int):
            raise ValueError(f"ac entry missing integer 'lgd_ac_id': {entry!r}")
        if not isinstance(lgd_state_id, int):
            raise ValueError(f"ac {lgd_ac_id} missing integer 'lgd_state_id'")
        if not isinstance(lgd_pc_id, int):
            raise ValueError(f"ac {lgd_ac_id} missing integer 'lgd_pc_id'")
        if not name or not isinstance(name, str):
            raise ValueError(f"ac {lgd_ac_id} missing 'ac_name'")
        state_slug = state_slug_by_lgd_id.get(lgd_state_id)
        if state_slug is None:
            raise ValueError(
                f"ac {lgd_ac_id} references unknown lgd_state_id={lgd_state_id}"
            )
        parent_pc_id = pc_entity_id_by_lgd_pc_id.get(lgd_pc_id)
        if parent_pc_id is None:
            raise ValueError(
                f"ac {lgd_ac_id} references unknown lgd_pc_id={lgd_pc_id}"
            )
        entity_id = _ac_entity_id(state_slug, lgd_ac_id, delim_year)
        if "__" in entity_id:
            raise ValueError(
                f"ac entity_id must not contain '__' (plan section 21.6): {entity_id!r}"
            )
        if entity_id in seen:
            raise ValueError(f"duplicate ac entity_id: {entity_id!r}")
        seen.add(entity_id)
        rows.append(
            {
                "entity_id": entity_id,
                "name": name,
                "entity_kind": "ac",
                "delim_year": delim_year,
                "state": state_slug,
                "parent": parent_pc_id,
                "reservation": None,
            }
        )

    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
