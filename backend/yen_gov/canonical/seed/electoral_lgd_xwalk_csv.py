"""B2a.7 entities/electoral_lgd_xwalk.csv emitter.

Lift ``datasets/taxonomy/lgd_ac_pc_district_map.json`` (LGD Constituency
Coverage Report - per-AC district coverage edges) to
``datasets/data/entities/electoral_lgd_xwalk.csv`` per the long-format CSV
contract (parent plan section 20.5 / sub-plan B2a.7).

Columns retained (per ``datasets/data/_schema/columns.json``):

- ``electoral_id``      (PK; FK -> ``entities/electoral.csv.entity_id``)
- ``lgd_district_id``   (PK; FK -> ``entities/geo.csv.entity_id`` - district grain
                          uses the composite ``<state-slug>/<district-slug>`` id
                          minted by ``seed/geo_csv.py``)
- ``delim_year``        (PK; integer; v1 emits 2008 only)
- ``boundary_snapshot`` (LGD vintage the overlap was computed against -
                          the decay receipt, plan section 20.5)
- ``overlap_kind``      (enum ``wholly_inside | majority | partial``; the
                          source asserts coverage edges only, so a single-
                          district AC -> ``wholly_inside``; a multi-district
                          AC -> ``partial`` for every row. ``majority``
                          requires area-weighted overlap which the source
                          does not carry; reserved for a future ingest.)

LGD/ECI key separation (parent plan F3 / 20.5 / sub-plan invariant 2):
this is the ONLY meeting point between admin (LGD) and electoral (ECI+delim)
key spaces. ``electoral.csv`` MUST NOT carry a district FK; the join lives
HERE and surfaces ``overlap_kind`` so cross-space overlays never silently
project mismatched polygons.

PC rows: the source covers ACs only (per its $comment). PC coverage will
arrive in a future ingest computed by area-weighted overlay over ECI PC
polygons; not in v1.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv


FILE_CLASS = "datasets/data/entities/electoral_lgd_xwalk.csv"

# LGD register snapshot is post-2008 delimitation (parent plan section 3).
DELIM_YEAR_V1 = 2008


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _district_id_index(
    districts: list[dict[str, Any]],
    state_slug_by_lgd_id: dict[int, str],
) -> dict[int, str]:
    out: dict[int, str] = {}
    for entry in districts:
        lgd_district_id = entry.get("lgd_district_id")
        lgd_state_id = entry.get("lgd_state_id")
        slug = entry.get("slug")
        if not isinstance(lgd_district_id, int):
            raise ValueError(
                f"district entry missing integer 'lgd_district_id': {entry!r}"
            )
        if not isinstance(lgd_state_id, int):
            raise ValueError(
                f"district {lgd_district_id} missing integer 'lgd_state_id'"
            )
        if not slug or not isinstance(slug, str):
            raise ValueError(f"district {lgd_district_id} missing 'slug'")
        parent_slug = state_slug_by_lgd_id.get(lgd_state_id)
        if parent_slug is None:
            raise ValueError(
                f"district {lgd_district_id} references unknown lgd_state_id="
                f"{lgd_state_id}"
            )
        out[lgd_district_id] = f"{parent_slug}/{slug}"
    return out


def _ac_id_index(acs: list[dict[str, Any]]) -> dict[tuple[int, int], int]:
    """Map ``(lgd_state_id, lgd_ac_id) -> lgd_ac_id`` membership only."""
    out: dict[tuple[int, int], int] = {}
    for entry in acs:
        lgd_ac_id = entry.get("lgd_ac_id")
        lgd_state_id = entry.get("lgd_state_id")
        if not isinstance(lgd_ac_id, int):
            raise ValueError(f"ac entry missing integer 'lgd_ac_id': {entry!r}")
        if not isinstance(lgd_state_id, int):
            raise ValueError(f"ac {lgd_ac_id} missing integer 'lgd_state_id'")
        out[(lgd_state_id, lgd_ac_id)] = lgd_ac_id
    return out


def _ac_entity_id(state_slug: str, lgd_ac_id: int, delim_year: int) -> str:
    return f"IN-AC-{delim_year}-{state_slug}-{lgd_ac_id}"


def _boundary_snapshot_from_source(payload: dict[str, Any]) -> str:
    """Derive the snapshot label from the first source's ``fetched_at`` date.

    Returns ``lgd:YYYY-MM-DD`` - the LGD portal date the coverage report was
    pulled on. Per CLAUDE.md anti-pattern: no ``datetime.now()`` in content
    columns; the value comes from the SOURCE artifact's vintage, not wall-clock.
    """
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("ac_pc_district_map: missing 'sources' for boundary_snapshot")
    fetched_at = sources[0].get("fetched_at")
    if not fetched_at or not isinstance(fetched_at, str):
        raise ValueError(
            "ac_pc_district_map: sources[0] missing 'fetched_at' for boundary_snapshot"
        )
    date_part = fetched_at[:10]
    if len(date_part) != 10 or date_part[4] != "-" or date_part[7] != "-":
        raise ValueError(
            f"ac_pc_district_map: unparsable 'fetched_at': {fetched_at!r}"
        )
    return f"lgd:{date_part}"


def emit(
    *,
    lgd_states_json: Path,
    lgd_acs_json: Path,
    lgd_districts_json: Path,
    ac_pc_district_map_json: Path,
    out_path: Path,
    delim_year: int = DELIM_YEAR_V1,
) -> Path:
    """Emit ``out_path`` from the four LGD registers; return the resolved path.

    Raises:
        FileNotFoundError: any input is missing.
        ValueError: required field missing, ``__`` in any emitted FK, or a
            map row references an unknown AC / district / state.
    """
    for p in (
        lgd_states_json,
        lgd_acs_json,
        lgd_districts_json,
        ac_pc_district_map_json,
    ):
        if not p.exists():
            raise FileNotFoundError(p)

    states_payload = _read_json(lgd_states_json)
    acs_payload = _read_json(lgd_acs_json)
    districts_payload = _read_json(lgd_districts_json)
    map_payload = _read_json(ac_pc_district_map_json)

    states = states_payload.get("states")
    acs = acs_payload.get("acs")
    districts = districts_payload.get("districts")
    map_rows = map_payload.get("rows")
    for name, value in (
        ("states", states),
        ("acs", acs),
        ("districts", districts),
        ("rows", map_rows),
    ):
        if not isinstance(value, list):
            raise ValueError(f"input missing or non-list {name!r} key")

    state_slug_by_lgd_id = _state_slug_index(states)
    district_id_by_lgd_id = _district_id_index(districts, state_slug_by_lgd_id)
    ac_membership = _ac_id_index(acs)

    boundary_snapshot = _boundary_snapshot_from_source(map_payload)

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()

    for entry in map_rows:
        lgd_state_id = entry.get("lgd_state_id")
        lgd_ac_id = entry.get("lgd_ac_id")
        lgd_district_ids = entry.get("lgd_district_ids")
        if not isinstance(lgd_state_id, int):
            raise ValueError(
                f"xwalk entry missing integer 'lgd_state_id': {entry!r}"
            )
        if not isinstance(lgd_ac_id, int):
            raise ValueError(f"xwalk entry missing integer 'lgd_ac_id': {entry!r}")
        if not isinstance(lgd_district_ids, list) or not lgd_district_ids:
            raise ValueError(
                f"xwalk ac {lgd_ac_id}: 'lgd_district_ids' must be non-empty list"
            )
        state_slug = state_slug_by_lgd_id.get(lgd_state_id)
        if state_slug is None:
            raise ValueError(
                f"xwalk ac {lgd_ac_id} references unknown lgd_state_id="
                f"{lgd_state_id}"
            )
        if (lgd_state_id, lgd_ac_id) not in ac_membership:
            raise ValueError(
                f"xwalk ac {lgd_ac_id} not present in lgd_acs.json for "
                f"state {lgd_state_id}"
            )
        electoral_id = _ac_entity_id(state_slug, lgd_ac_id, delim_year)
        if "__" in electoral_id:
            raise ValueError(
                f"electoral_id must not contain '__' (plan section 21.6): "
                f"{electoral_id!r}"
            )
        kind = "wholly_inside" if len(lgd_district_ids) == 1 else "partial"
        for district_lgd_id in lgd_district_ids:
            if not isinstance(district_lgd_id, int):
                raise ValueError(
                    f"xwalk ac {lgd_ac_id}: district id must be integer, got "
                    f"{district_lgd_id!r}"
                )
            district_entity_id = district_id_by_lgd_id.get(district_lgd_id)
            if district_entity_id is None:
                raise ValueError(
                    f"xwalk ac {lgd_ac_id} references unknown "
                    f"lgd_district_id={district_lgd_id}"
                )
            if "__" in district_entity_id:
                raise ValueError(
                    f"lgd_district_id must not contain '__' "
                    f"(plan section 21.6): {district_entity_id!r}"
                )
            key = (electoral_id, district_entity_id, delim_year)
            if key in seen:
                raise ValueError(
                    f"duplicate xwalk row: electoral_id={electoral_id!r} "
                    f"lgd_district_id={district_entity_id!r} "
                    f"delim_year={delim_year}"
                )
            seen.add(key)
            rows.append(
                {
                    "electoral_id": electoral_id,
                    "lgd_district_id": district_entity_id,
                    "delim_year": delim_year,
                    "boundary_snapshot": boundary_snapshot,
                    "overlap_kind": kind,
                }
            )

    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
