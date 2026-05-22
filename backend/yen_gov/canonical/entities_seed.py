"""Compile entities.json to entities.parquet.

§8.3 Python-compiles-to-Parquet seam. Produces
``datasets/taxonomy/entities.parquet`` — the canonical entity dimension
read by every downstream join (boundary lookup, breadcrumb resolution,
peer-set filtering).

T.0c-iii Phase B (2026-05-22): the per-state ``districts.json`` loader
is GONE. ``datasets/taxonomy/entities.json`` is now the sole input —
it carries all 185 rows (1 country + 29 states + 10 UTs + 145
districts) that Phase A folded in. The 6
``datasets/reference/in/states/<S>/districts.json`` files still sit on
disk (deletion is Phase C scope) but no code path reads them. The
remaining ~600 LGD-only districts (states with no hand-authored
districts.json) come in via a follow-up that reads
``datasets/taxonomy/lgd/districts-latest.csv``; calling that out here
so the next agent does not re-derive the gap from on-disk evidence.

The entity.schema.json v1.1 ``legacy_id`` column — districts in the
old per-state JSONs were keyed by Wikipedia slug (``ARI`` for
Ariyalur) and citizen-cited that way; the canonical ``entity_id`` is
LGD-numeric (``IN-S22-D610``) but ``legacy_id`` carries the old slug
so old URLs / external citations resolve forward.

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
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

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


# ----------------------------------------------------------------------
# Loaders
# ----------------------------------------------------------------------


def _load_base_entities(path: Path) -> list[_BaseEntity]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for k in ("$schema", "$schema_version", "$comment", "sources"):
        payload.pop(k, None)
    return [_BaseEntity.model_validate(row) for row in payload["entities"]]


# ----------------------------------------------------------------------
# Compile
# ----------------------------------------------------------------------


def compile_to_parquet(
    entities_json: Path,
    parquet_out: Path,
) -> int:
    """Read ``entities.json``, project, emit ``parquet_out``.

    Returns total row count. Deterministic sort
    ``(entity_type, entity_id)`` so re-runs produce byte-identical
    output.

    Phase B (T.0c-iii, 2026-05-22): the per-state ``districts.json``
    loader and its dedup loop are gone. ``entities.json`` is the sole
    input — all 185 rows (1 country + 29 states + 10 UTs + 145
    districts) live there after Phase A folded the per-state JSONs in.
    The 6 ``datasets/reference/in/states/<S>/districts.json`` files
    still sit on disk (deletion is Phase C scope) but no code path
    reads them. Refs: TODO/20260517-canonical-long-format-pivot.md
    §0e.10.4 row 318; TODO/20260521-phase-2-preflight-audit-gregor.md
    #5.
    """
    parquet_out = Path(parquet_out)
    rows = _load_base_entities(Path(entities_json))

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
