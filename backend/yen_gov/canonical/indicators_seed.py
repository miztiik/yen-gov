"""Compile ``datasets/taxonomy/indicators.json`` to a Parquet sibling
(``taxonomy/indicators.parquet``) for DuckDB-WASM consumption.

The hand-authored catalogue lives in JSON (operator-friendly authoring,
git-diff-friendly review). The parquet is the canonical wire format read
by the static frontend via DuckDB-WASM per ADR-0030. Mirrors
``indicator-catalogue.schema.json`` v1.0 column-for-column with two
deliberate denormalisations:

1. ``dimension_values`` (dict[str,str]) and ``funding_split`` (struct)
   are serialised to JSON-string columns so the parquet schema stays
   flat. Frontend uses ``json_extract`` when it needs to decompose them.
2. ``coverage_*`` columns are present in the schema but typically null
   at compile time -- the canonical writer denormalises them by querying
   the family observation parquets after they emit. The catalogue
   parquet is rebuilt on the next emit-taxonomy cycle.

Idempotent: re-running with byte-identical input yields byte-identical
output (no timestamps, no random IDs, deterministic row order).

D29 contract is enforced here at compile time (failing closed):
- parent row (parent_indicator_id IS NULL) MUST NOT carry dimension_values
- child row (parent_indicator_id non-null) MUST carry dimension_values
  AND a per-child source_id

P.1.A C3 seed (2026-05-22).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "IndicatorRow",
    "compile_to_parquet",
]


class _FundingSplit(BaseModel):
    """Nested struct on the catalogue row -- serialised to JSON string."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    centre_pct: float = Field(ge=0, le=100)
    state_pct: float = Field(ge=0, le=100)
    other_pct: float | None = Field(default=None, ge=0, le=100)
    source: str = Field(min_length=1)


class IndicatorRow(BaseModel):
    """One row of taxonomy/indicators.parquet.

    PK = ``indicator_id``. Mirrors ``indicator-catalogue.schema.json``
    item shape v1.0. ``dimension_values`` and ``funding_split`` are kept
    as native types here for Pydantic validation; the parquet
    serialiser converts them to JSON strings.
    """

    model_config = ConfigDict(extra="forbid")

    indicator_id: str = Field(pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", max_length=60)
    label_short: str = Field(min_length=1, max_length=60)
    label_long: str = Field(min_length=1)
    description_short: str = Field(min_length=10)
    description_long: str | None = None
    unit: str = Field(min_length=1)
    cadence: Literal[
        "annual_fy",
        "annual_cy",
        "quarterly_fy",
        "quarterly_cy",
        "monthly_fy",
        "monthly_cy",
        "weekly",
        "daily",
        "decennial",
        "ad_hoc",
    ]
    default_period_seq_for_cadence: int | None = None
    family: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    pillar: Literal["people", "money", "infrastructure", "politics"]
    topic_tags: list[str] = Field(default_factory=list)
    value_kind: Literal[
        "absolute", "rate", "ratio", "count", "index", "percentage", "currency"
    ]
    direction: Literal["higher_is_better", "lower_is_better", "neutral"]
    denominator: str | None = None
    attribution_geography: Literal[
        "where_produced",
        "where_allocated",
        "where_consumed",
        "where_billed",
        "where_resident",
        "where_administered",
    ]
    comparability: Literal[
        "comparable_across_states_and_time",
        "comparable_across_states_snapshot_only",
        "comparable_within_state_over_time",
        "directional_only",
    ]
    implementing_authority: (
        Literal[
            "state", "centre", "joint", "local_body", "parastatal", "private", "unspecified"
        ]
        | None
    ) = None
    funding_split: _FundingSplit | None = None
    methodology_vintage: str | None = None
    revision_tier: Literal["first_release", "revised", "final", "mixed"] | None = None
    excluded_notes: list[str] = Field(default_factory=list)
    parent_indicator_id: str | None = Field(
        default=None, pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", max_length=60
    )
    dimension_values: dict[str, str] | None = None
    methodology_version: str | None = None
    methodology_break_ids: list[str] = Field(default_factory=list)
    source_id: str | None = None
    coverage_states_count: int | None = None
    coverage_year_min: int | None = None
    coverage_year_max: int | None = None
    coverage_density: float | None = Field(default=None, ge=0, le=1)
    renderer_rules: list[str] = Field(default_factory=list)


# 31 columns, flat. Lists kept as VARCHAR[]; dicts/structs serialised to
# JSON-string for DuckDB-WASM friendliness.
_DDL = """
CREATE TABLE indicators (
    indicator_id VARCHAR PRIMARY KEY,
    label_short VARCHAR NOT NULL,
    label_long VARCHAR NOT NULL,
    description_short VARCHAR NOT NULL,
    description_long VARCHAR,
    unit VARCHAR NOT NULL,
    cadence VARCHAR NOT NULL,
    default_period_seq_for_cadence INTEGER,
    family VARCHAR NOT NULL,
    pillar VARCHAR NOT NULL,
    topic_tags VARCHAR[],
    value_kind VARCHAR NOT NULL,
    direction VARCHAR NOT NULL,
    denominator VARCHAR,
    attribution_geography VARCHAR NOT NULL,
    comparability VARCHAR NOT NULL,
    implementing_authority VARCHAR,
    funding_split_json VARCHAR,
    methodology_vintage VARCHAR,
    revision_tier VARCHAR,
    excluded_notes VARCHAR[],
    parent_indicator_id VARCHAR,
    dimension_values_json VARCHAR,
    methodology_version VARCHAR,
    methodology_break_ids VARCHAR[],
    source_id VARCHAR,
    coverage_states_count INTEGER,
    coverage_year_min INTEGER,
    coverage_year_max INTEGER,
    coverage_density DOUBLE,
    renderer_rules VARCHAR[]
)
"""


def _row_to_tuple(row: IndicatorRow) -> tuple:
    return (
        row.indicator_id,
        row.label_short,
        row.label_long,
        row.description_short,
        row.description_long,
        row.unit,
        row.cadence,
        row.default_period_seq_for_cadence,
        row.family,
        row.pillar,
        list(row.topic_tags),
        row.value_kind,
        row.direction,
        row.denominator,
        row.attribution_geography,
        row.comparability,
        row.implementing_authority,
        (
            json.dumps(
                row.funding_split.model_dump(exclude_none=True),
                sort_keys=True,
                separators=(",", ":"),
            )
            if row.funding_split is not None
            else None
        ),
        row.methodology_vintage,
        row.revision_tier,
        list(row.excluded_notes),
        row.parent_indicator_id,
        (
            json.dumps(row.dimension_values, sort_keys=True, separators=(",", ":"))
            if row.dimension_values is not None
            else None
        ),
        row.methodology_version,
        list(row.methodology_break_ids),
        row.source_id,
        row.coverage_states_count,
        row.coverage_year_min,
        row.coverage_year_max,
        row.coverage_density,
        list(row.renderer_rules),
    )


def compile_to_parquet(json_in: Path, parquet_out: Path) -> int:
    """Read ``json_in``, validate, write ``parquet_out``.

    Returns the number of rows written. Caller is responsible for
    ensuring ``parquet_out.parent`` exists.

    Re-running with byte-identical input yields byte-identical output.
    """
    parquet_out = Path(parquet_out)
    payload = json.loads(Path(json_in).read_text(encoding="utf-8"))
    raw_rows = payload.get("indicators", [])
    rows = [IndicatorRow.model_validate(r) for r in raw_rows]

    # D29 contract enforcement (fail closed at compile time).
    for r in rows:
        if r.parent_indicator_id is None:
            if r.dimension_values is not None:
                raise ValueError(
                    f"indicator {r.indicator_id!r}: parent row must not carry "
                    "dimension_values (per indicator-catalogue.schema.json D29)."
                )
        else:
            if not r.dimension_values:
                raise ValueError(
                    f"indicator {r.indicator_id!r}: child row (parent_indicator_id "
                    "non-null) must carry dimension_values (per D29)."
                )
            if r.source_id is None:
                raise ValueError(
                    f"indicator {r.indicator_id!r}: child row must carry source_id "
                    "(per D29 -- siblings can have different upstreams)."
                )

    # Deterministic order: by indicator_id (PK).
    rows.sort(key=lambda r: r.indicator_id)

    con = duckdb.connect(":memory:")
    try:
        con.execute(_DDL)
        if rows:
            con.executemany(
                "INSERT INTO indicators VALUES ("
                + ", ".join(["?"] * 31)
                + ")",
                [_row_to_tuple(r) for r in rows],
            )
        con.execute(
            f"""
            COPY (
                SELECT * FROM indicators ORDER BY indicator_id
            ) TO '{parquet_out.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()

    return len(rows)
