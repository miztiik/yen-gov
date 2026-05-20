"""Compile ``datasets/taxonomy/state_tiers.json`` to a denormalised Parquet.

§8.3 Python-compiles-to-Parquet seam — mirrors
``facet_axes_seed.compile_to_parquet`` (TODO row 1.8d-ii) but operates on
an on-disk hand-authored JSON instead of a Python literal.

Input contract: ``datasets/taxonomy/state_tiers.json`` validated against
``datasets/schemas/state-tiers.schema.json`` (v1.0).

Output contract: ``datasets/taxonomy/state_tiers.parquet`` — one row per
``(tier_id, member_state_code)`` so DuckDB joins ``WHERE
state_tiers.tier_id = 'special_category'`` return one state code per row
without unnesting a list column.

Why denormalised, not nested:
    The OWID precedent for peer-set tables is the long format
    ``regions.csv`` — one row per ``(region_code, member_iso)``. Parquet
    list columns are not free in DuckDB-WASM scan plans (1.x release
    notes still flag UNNEST as a join hazard). Citizen-facing queries
    are always ``WHERE tier_id = ?`` then collect members — the long
    shape is the obvious join target.

Sort order is deterministic ``(tier_id, member_state_code)`` so a re-run
with byte-identical input produces byte-identical Parquet output
(CLAUDE.md anti-pattern #1 carve-out). Rejected: stamping
``compiled_at`` into the artifact — same fetched_at-smear class as
/memories/lessons.md 2026-05-16.

Rejected designs (do NOT re-propose):
    1. Emit tiers as a STRUCT column with members[] inside. UNNEST cost
       on the consumer side; loses the obvious join shape.
    2. Re-author the data as a Python literal here. Duplicates the JSON
       that already has its own schema + Tier-A validator gate; two
       sources of truth diverge. Pattern stays "JSON is canonical, Python
       compiles".
    3. Skip ``definition_kind`` / ``authority`` / ``definition`` columns
       to keep the table narrow. Lost the Hans-vetted citation chain
       (why is this tier a tier, on whose authority); the citizen-page
       'About this peer set' tooltip needs these verbatim. Carry them
       as wide columns; they repeat per member-row but the table is 30
       members × 11 tiers so the cost is rounding noise.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

# Row-schema-version constant. Distinct from the input
# ``state-tiers.schema.json`` x-version — that one governs the JSON
# authoring contract; this one governs the projected Parquet row shape.
# Bump together when the row shape changes; leave the JSON version alone
# when only the projection logic changes.
STATE_TIERS_ROW_SCHEMA_VERSION = "1.0"


DefinitionKind = Literal[
    "constitutional",
    "statutory",
    "fc_derived",
    "geographic",
    "editorial",
    "residual",
    "research",
]


class _Tier(BaseModel):
    """One row in ``state_tiers.json#/tiers``. Mirrors the schema 1:1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    definition_kind: DefinitionKind
    definition: str = Field(min_length=1)
    authority: str | None = None
    members: list[str] = Field(default_factory=list)
    notes: str | None = None


class _StateTiersFile(BaseModel):
    """Top-level shape of ``state_tiers.json`` we need for compilation.

    Permits extra top-level fields (``$schema``, ``$schema_version``,
    ``$comment``, ``sources``) — the seed only consumes ``tiers``.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    tiers: list[_Tier]


def _denormalised_rows(
    tiers: list[_Tier],
) -> list[tuple[str, str, str, str, str | None, str, str | None]]:
    """Flatten ``tiers[].members[]`` to one row per (tier, member).

    Tiers with empty ``members`` (e.g. ``fc_horizontal_devolution_share_quintile``
    pending FC-XV recon) emit ZERO rows here. The consumer side handles
    "no members yet" by degrading the peer-set filter to "all" per the
    note in the source JSON. That keeps the citizen UI honest about
    pending data instead of silently shipping an empty tier.

    Returns rows in (tier_id, member_state_code) sort order so the COPY
    is byte-deterministic.
    """
    out: list[tuple[str, str, str, str, str | None, str, str | None]] = []
    for tier in tiers:
        for member in tier.members:
            out.append(
                (
                    tier.id,
                    tier.label,
                    tier.definition_kind,
                    tier.definition,
                    tier.authority,
                    member,
                    tier.notes,
                )
            )
    out.sort(key=lambda row: (row[0], row[5]))
    return out


def compile_to_parquet(json_in: Path, parquet_out: Path) -> int:
    """Read ``json_in``, validate via Pydantic, write ``parquet_out``.

    Returns the number of denormalised rows written. Caller is
    responsible for ensuring ``parquet_out.parent`` exists.

    Re-running with byte-identical input yields byte-identical output —
    no ``datetime.now()`` stamping, no random IDs.
    """
    parquet_out = Path(parquet_out)
    payload = json.loads(Path(json_in).read_text(encoding="utf-8"))
    payload.pop("$schema", None)
    payload.pop("$schema_version", None)
    payload.pop("$comment", None)
    payload.pop("sources", None)
    data = _StateTiersFile.model_validate(payload)
    rows = _denormalised_rows(list(data.tiers))

    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE state_tiers (
                tier_id VARCHAR NOT NULL,
                tier_label VARCHAR NOT NULL,
                definition_kind VARCHAR NOT NULL,
                definition VARCHAR NOT NULL,
                authority VARCHAR,
                state_code VARCHAR NOT NULL,
                notes VARCHAR
            )
            """
        )
        if rows:
            con.executemany(
                "INSERT INTO state_tiers VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        con.execute(
            f"""
            COPY (
                SELECT * FROM state_tiers
                ORDER BY tier_id, state_code
            ) TO '{parquet_out.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()
    return len(rows)
