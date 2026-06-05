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
            ``<iso_alpha>|<eci_st_code>|lgd:<lgd_state_id>|<long-name>`` (the ECI
            state code is RETAINED until the dedicated 0e decommission sweep
            repoints its consumers - see ``_state_aliases``).
- district: ``<state-slug>/<district-slug>`` composite (LGD district slugs
            collide across states for e.g. ``bilaspur``, ``hamirpur``,
            ``pratapgarh``; the composite disambiguates without minting an
            opaque integer id); aliases carry ``lgd:<lgd_district_id>``.

Census (B2b.5.0c): ``census_2001_code`` + ``census_2011_code`` are two dated
LABEL columns joined from the LGD parsed snapshot (B2b.5.0a) by LGD code; empty
when the entity did not exist at that census. NEVER join keys.

Sub-district + village rows are admissible by columns.json but NOT emitted
in v1 (no current consumer; future ingest extends).
"""

from __future__ import annotations

import csv
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


def _census_index(snapshot_csv: Path, code_col: str) -> dict[str, tuple[str, str]]:
    """Map an LGD code (string) -> (census_2001_code, census_2011_code).

    Reads the committed LGD parsed snapshot (B2b.5.0a). The census columns are
    already 0-sentinel-normalised to empty (parser ``_census``), so an entity
    that did not exist at a census carries an empty label here.
    """
    out: dict[str, tuple[str, str]] = {}
    with snapshot_csv.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            out[r[code_col]] = (
                (r.get("census_2001_code") or "").strip(),
                (r.get("census_2011_code") or "").strip(),
            )
    return out


def _state_aliases(entry: dict[str, Any]) -> str | None:
    """State aliases = ISO 3166-2 + ECI state code + lgd:<id> + long-name synonym.

    NOTE (B2b.5.0c): the ECI state code (``eci_st_code``) is RETAINED here for
    now. Its repo-wide decommission (round-8) happens in the dedicated 0e sweep
    stage, where every consumer is repointed atomically - in particular
    ``governments_term_shape.load_eci_state_to_geo_entity`` resolves office
    jurisdiction (``IN-S04`` -> ``bihar``) through this very alias, so stripping
    it here would break the office-holdings parity before its owning surface is
    repointed. 0c only ADDS the census LABEL columns; the alias set is unchanged.
    """
    parts: list[str] = []
    iso = entry.get("iso_alpha")
    eci = entry.get("eci_st_code")
    lgd_id = entry.get("lgd_state_id")
    short = entry.get("lgd_name_short")
    long = entry.get("lgd_name")
    if iso:
        parts.append(str(iso))
    if eci:
        parts.append(str(eci))
    if lgd_id is not None:
        parts.append(f"lgd:{lgd_id}")
    if short and long and short != long:
        parts.append(str(long))
    return "|".join(parts) if parts else None


def _district_alias(entry: dict[str, Any]) -> str | None:
    lgd_id = entry.get("lgd_district_id")
    return f"lgd:{lgd_id}" if lgd_id is not None else None


def emit(
    *,
    lgd_states_json: Path,
    lgd_districts_json: Path,
    out_path: Path,
    lgd_snapshot_states_csv: Path | None = None,
    lgd_snapshot_districts_csv: Path | None = None,
) -> Path:
    """Emit ``out_path`` from the two LGD registers; return the resolved path.

    The slug + structure (entity_id scheme ``<state-slug>`` / ``<state-slug>/
    <district-slug>``) come from the LGD registers (yen-gov-authored display
    fields, preserved so boundary geometry + datapoint consumers keep resolving).
    When the LGD parsed-snapshot CSVs (B2b.5.0a) are supplied, the two dated
    census LABEL columns are joined on by LGD code; ``eci_st_code`` is never
    carried (round-8 decommission).

    Raises:
        FileNotFoundError: a required input is missing.
        ValueError: required field missing, identity collision, ``__`` in any
            emitted entity_id (plan section 21.6), or district references an
            unknown ``lgd_state_id``.
    """
    if not lgd_states_json.exists():
        raise FileNotFoundError(lgd_states_json)
    if not lgd_districts_json.exists():
        raise FileNotFoundError(lgd_districts_json)

    state_census: dict[str, tuple[str, str]] = {}
    district_census: dict[str, tuple[str, str]] = {}
    if lgd_snapshot_states_csv is not None:
        if not lgd_snapshot_states_csv.exists():
            raise FileNotFoundError(lgd_snapshot_states_csv)
        state_census = _census_index(lgd_snapshot_states_csv, "lgd_state_code")
    if lgd_snapshot_districts_csv is not None:
        if not lgd_snapshot_districts_csv.exists():
            raise FileNotFoundError(lgd_snapshot_districts_csv)
        district_census = _census_index(lgd_snapshot_districts_csv, "lgd_district_code")

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
            "census_2001_code": None,
            "census_2011_code": None,
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
        c2001, c2011 = state_census.get(str(lgd_id), ("", ""))
        rows.append(
            {
                "entity_id": slug,
                "name": name,
                "parent": COUNTRY_ENTITY_ID,
                "entity_kind": "state",
                "aliases": _state_aliases(entry),
                "census_2001_code": c2001 or None,
                "census_2011_code": c2011 or None,
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
        c2001, c2011 = district_census.get(str(lgd_district_id), ("", ""))
        rows.append(
            {
                "entity_id": entity_id,
                "name": name,
                "parent": parent_slug,
                "entity_kind": "district",
                "aliases": _district_alias(entry),
                "census_2001_code": c2001 or None,
                "census_2011_code": c2011 or None,
            }
        )

    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
