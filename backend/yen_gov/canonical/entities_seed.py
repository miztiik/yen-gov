"""Compile entities.json + per-state districts.json files to entities.parquet.

§8.3 Python-compiles-to-Parquet seam. Produces
``datasets/taxonomy/entities.parquet`` — the canonical entity dimension
read by every downstream join (boundary lookup, breadcrumb resolution,
peer-set filtering).

T.0a-ii role: lift 147 hand-authored district rows (currently in
``datasets/reference/in/states/<S>/districts.json`` for the 6 states
that have them — Assam, Gujarat, Kerala, Tamil Nadu, West Bengal,
Puducherry) into entities.parquet as ``entity_type='district'`` rows
sitting under their parent state. The 40 country/state/UT rows in
``datasets/taxonomy/entities.json`` carry over unchanged. The remaining
~600 LGD-only districts (states that have no hand-authored
districts.json) come in via a follow-up that reads
``datasets/taxonomy/lgd/districts-latest.csv``; calling that out here
so the next agent does not re-derive the gap from on-disk evidence.

The bump to entity.schema.json v1.1 adds the ``legacy_id`` column —
districts in hand-authored JSONs were originally keyed by Wikipedia
slug (``ARI`` for Ariyalur) and citizen-cited that way; the canonical
``entity_id`` moves to LGD-numeric (``IN-S22-D610``) but ``legacy_id``
carries the old slug so old URLs / external citations resolve forward.

Rejected designs (do NOT re-propose):
    1. Mint ``entity_id`` from the Wikipedia slug instead of LGD code
       (``IN-S22-ARI``). Slugs collide across states (CHN = Chennai in
       TN, could be a hypothetical Chandanagar elsewhere); LGD codes
       are the issuing-authority's own identifiers and are stable per
       CLAUDE.md §3 ("never invent IDs when an issuing authority
       publishes one"). Slug stays as ``legacy_id``, not as the PK.
    2. Lift districts as flat (no ``parent_entity_id``). Plan §0e.7
       requires the entities dim to support breadcrumb resolution
       (Tamil Nadu → Mylapore district → Mylapore AC); a missing
       parent_entity_id forces every consumer to derive it by string
       prefix, which couples them to the id grammar.
    3. Pre-resolve ``entity_valid_from`` from district ``created_on``
       AND fall through silently to ``1947`` when missing. For
       districts whose ``created_on`` is omitted we fall through to
       the parent STATE's ``entity_valid_from`` (a real lower bound:
       the district can't predate its state). The validator catches
       any district whose computed ``entity_valid_from`` is younger
       than ``entity_valid_to`` — but the catalogue today has no
       extinct districts, so this is a future-proofing check, not
       active enforcement.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

ENTITIES_ROW_SCHEMA_VERSION = "1.1"

EntityType = Literal[
    "country",
    "state",
    "ut",
    "district",
    "subdistrict",
    "village",
    "ulb",
    "constituency_ac",
    "constituency_pc",
    "union_govt",
    "state_govt",
    "discom",
    "psu",
    "ministry",
]
EntityLevel = Literal[
    "country",
    "state",
    "district",
    "subdistrict",
    "village",
    "ulb",
    "ac",
    "pc",
    "fiscal_actor",
]


# ----------------------------------------------------------------------
# Authoring shapes (input JSONs)
# ----------------------------------------------------------------------


class _BaseEntity(BaseModel):
    """One row of ``entities.json#/entities``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str = Field(min_length=1)
    entity_type: EntityType
    entity_level: EntityLevel
    entity_code: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    display_name_local: str | None = None
    parent_entity_id: str | None = None
    entity_valid_from: int = Field(ge=1800, le=2100)
    entity_valid_to: int | None = Field(default=None, ge=1800, le=2100)
    iso_3166_2: str | None = None
    lgd_code: str | None = None
    legacy_id: str | None = None
    notes: str | None = None


class _District(BaseModel):
    """One row of ``districts.json#/districts``. Permits extras for
    forward-compat (e.g. ``census_2011_code`` added later).

    Per ``district.schema.json`` v3.4, only ``id`` / ``id_source`` /
    ``name`` are required; ``lgd_code`` is optional because some small
    UT districts (Mahe, Yanam in Puducherry) have no published LGD
    code. Such districts are skipped by ``_district_to_entity`` because
    the canonical entity_id grammar (``IN-<state>-D<lgd_code>``)
    requires an LGD code; they are surfaced through the count of
    'skipped' rows the CLI logs.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    id: str = Field(min_length=1)
    id_source: str | None = None
    name: str = Field(min_length=1)
    name_alt: str | list[str] | None = None
    name_ta: str | None = None  # Tamil-script alias (S22 only today)
    name_source: str | None = None
    headquarters: str | None = None
    created_on: str | None = None  # ISO date or None
    created_after_2011: bool | None = None
    split_from: list[str] | None = None
    notes: str | None = None
    lgd_code: str | None = None
    census_2011_code: int | None = None
    lgd_code_history: list[str] | dict | None = None


class _DistrictsFile(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    state: str = Field(pattern=r"^[SU]\d{2}$")
    districts: list[_District]


# ----------------------------------------------------------------------
# Loaders
# ----------------------------------------------------------------------


def _load_base_entities(path: Path) -> list[_BaseEntity]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for k in ("$schema", "$schema_version", "$comment", "sources"):
        payload.pop(k, None)
    return [_BaseEntity.model_validate(row) for row in payload["entities"]]


def _load_districts_files(district_files: Iterable[Path]) -> list[tuple[str, _District]]:
    """Read every districts.json and return flat ``(state_code, district)`` pairs.

    Skips files that don't exist (callers globbing
    ``states/*/districts.json`` get back only the states that authored one).
    """
    out: list[tuple[str, _District]] = []
    for p in district_files:
        if not p.is_file():
            continue
        raw = json.loads(p.read_text(encoding="utf-8"))
        for k in ("$schema", "$schema_version", "$comment", "sources"):
            raw.pop(k, None)
        df = _DistrictsFile.model_validate(raw)
        for d in df.districts:
            out.append((df.state, d))
    return out


# ----------------------------------------------------------------------
# Transform
# ----------------------------------------------------------------------


_CREATED_ON_YEAR = re.compile(r"^(\d{4})")


def _district_valid_from(district: _District, parent_valid_from: int) -> int:
    """Year the district came into existence.

    Order of evidence: explicit ``created_on`` ISO date > parent state's
    valid_from (the district can't predate its state). Never falls back
    to a hardcoded constant — the parent state is always known here.
    """
    if district.created_on:
        m = _CREATED_ON_YEAR.match(district.created_on)
        if m:
            return int(m.group(1))
    return parent_valid_from


def _district_notes(district: _District) -> str | None:
    """Compose a citizen-readable notes string from the district's
    structured side fields.

    The JSON has ``headquarters`` + ``split_from`` + ``notes`` as
    separate keys; the entity row collapses them into one prose field
    that the breadcrumb / tooltip / 'about this district' surfaces
    consume. The ordering is intentional — headquarters first
    (citizen most likely wants to know "where is this district based"),
    then provenance ("carved from X"), then editorial.
    """
    parts: list[str] = []
    if district.headquarters:
        parts.append(f"Headquarters: {district.headquarters}.")
    if district.split_from:
        joined = ", ".join(district.split_from)
        parts.append(f"Carved from: {joined}.")
    if district.notes:
        parts.append(district.notes)
    return " ".join(parts) if parts else None


def _district_to_entity(
    state_code: str,
    district: _District,
    parent_valid_from: int,
) -> _BaseEntity:
    """Project one district JSON row to one entities.parquet row."""
    return _BaseEntity(
        entity_id=f"IN-{state_code}-D{district.lgd_code}",
        entity_type="district",
        entity_level="district",
        entity_code=district.lgd_code,
        display_name=district.name,
        display_name_local=district.name_ta,
        parent_entity_id=f"IN-{state_code}",
        entity_valid_from=_district_valid_from(district, parent_valid_from),
        entity_valid_to=None,
        iso_3166_2=None,
        lgd_code=district.lgd_code,
        legacy_id=district.id,
        notes=_district_notes(district),
    )


# ----------------------------------------------------------------------
# Compile
# ----------------------------------------------------------------------


def compile_to_parquet(
    entities_json: Path,
    district_files: Iterable[Path],
    parquet_out: Path,
) -> int:
    """Read all inputs, project, emit ``parquet_out``.

    Returns total row count. Districts without an ``lgd_code`` (e.g.
    Mahe / Yanam in Puducherry today) are skipped because the canonical
    ``entity_id`` grammar requires an LGD code; rows can be added in a
    follow-up once their codes are looked up. Deterministic sort
    ``(entity_type, entity_id)`` so re-runs produce byte-identical
    output.
    """
    parquet_out = Path(parquet_out)
    base = _load_base_entities(Path(entities_json))
    by_id: dict[str, int] = {e.entity_id: e.entity_valid_from for e in base}

    rows: list[_BaseEntity] = list(base)
    for state_code, district in _load_districts_files(district_files):
        if not district.lgd_code:
            # Forward-compat: skip districts whose lgd_code we don't
            # have. The canonical entity_id needs the LGD code; without
            # it there's no stable identifier to mint. Surfaced via the
            # return-count diff (caller logs skipped count if it cares).
            continue
        parent_id = f"IN-{state_code}"
        parent_from = by_id.get(parent_id)
        if parent_from is None:
            raise ValueError(
                f"districts.json for {state_code} references unknown parent "
                f"entity {parent_id!r}; add the state to entities.json first"
            )
        rows.append(_district_to_entity(state_code, district, parent_from))

    # Cross-row uniqueness: entity_id is PK
    seen: set[str] = set()
    for r in rows:
        if r.entity_id in seen:
            raise ValueError(f"duplicate entity_id {r.entity_id!r}")
        seen.add(r.entity_id)

    rows.sort(key=lambda r: (r.entity_type, r.entity_id))

    tuples = [
        (
            r.entity_id,
            r.entity_type,
            r.entity_level,
            r.entity_code,
            r.display_name,
            r.display_name_local,
            r.parent_entity_id,
            r.entity_valid_from,
            r.entity_valid_to,
            r.iso_3166_2,
            r.lgd_code,
            r.legacy_id,
            r.notes,
        )
        for r in rows
    ]

    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE entities (
                entity_id VARCHAR NOT NULL,
                entity_type VARCHAR NOT NULL,
                entity_level VARCHAR NOT NULL,
                entity_code VARCHAR NOT NULL,
                display_name VARCHAR NOT NULL,
                display_name_local VARCHAR,
                parent_entity_id VARCHAR,
                entity_valid_from INTEGER NOT NULL,
                entity_valid_to INTEGER,
                iso_3166_2 VARCHAR,
                lgd_code VARCHAR,
                legacy_id VARCHAR,
                notes VARCHAR
            )
            """
        )
        con.executemany(
            "INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuples,
        )
        con.execute(
            f"""
            COPY (
                SELECT * FROM entities
                ORDER BY entity_type, entity_id
            ) TO '{parquet_out.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()
    return len(rows)
