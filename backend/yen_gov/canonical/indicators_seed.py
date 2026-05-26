"""Compile ``datasets/taxonomy/indicators.json`` to a Parquet sibling
(``taxonomy/indicators.parquet``) for DuckDB-WASM consumption.

The hand-authored catalogue lives in JSON (operator-friendly authoring,
git-diff-friendly review). The parquet is the canonical wire format read
by the static frontend via DuckDB-WASM per ADR-0030. Mirrors
``indicator-catalogue.schema.json`` v1.1 column-for-column with two
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

v2.0 (PR-B1 2026-05-26) grain-over-entity rip-and-replace per
ADR-0044 (TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md
Phase B). Drops ``id_aliases`` + ``deprecated_in`` (per-PR rename scripts
under ``tools/migrate/`` replace the one-release alias window) and adds
required ``entity_kinds`` (list[str]) + ``default_entity_kind`` (str).
Enum is ``{country,state,district,ac,party,candidate}``. Grain dispatches
at read time from each observation row's ``entity_kind`` column; the
indicator_id never encodes the grain.

P.1.A C3 seed (2026-05-22). v1.1 widening 2026-05-22 (T.3). v2.0 PR-B1
2026-05-26 (grain-over-entity rip).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "IndicatorRow",
    "ENTITY_KIND_VALUES",
    "compile_to_parquet",
]


# v2.0 (PR-B1 2026-05-26). The closed enum of entity_kinds supported on
# the canonical catalogue per ADR-0044. Widened beyond the geographic
# four {country,state,district,ac} to include {party,candidate} because
# election-class indicators (party-vote-share-pct, candidate-rank) carry
# party/candidate as the entity. Mirrors
# ``indicator-catalogue.schema.json`` v2.0 enum exactly.
ENTITY_KIND_VALUES = (
    "country",
    "state",
    "district",
    "ac",
    "party",
    "candidate",
)


class _FundingSplit(BaseModel):
    """Nested struct on the catalogue row -- serialised to JSON string."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    centre_pct: float = Field(ge=0, le=100)
    state_pct: float = Field(ge=0, le=100)
    other_pct: float | None = Field(default=None, ge=0, le=100)
    source: str = Field(min_length=1)


class _IndicatorMeta(BaseModel):
    """v2.3 (PR-Zjust 2026-05-26 guardrail #15) per-row free-form metadata.

    Today only carries ``justification`` (required on cross-grain concept
    twins by Tier-B ``tier_b_indicator_has_justification``). Additive
    sub-properties land here in future PRs.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    justification: str | None = Field(default=None, min_length=20)


class IndicatorRow(BaseModel):
    """One row of taxonomy/indicators.parquet.

    PK = ``indicator_id``. Mirrors ``indicator-catalogue.schema.json``
    item shape v1.1. ``dimension_values`` and ``funding_split`` are kept
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
    # v2.0 (PR-B1 2026-05-26 grain-over-entity rip per ADR-0044). The
    # entity kinds this indicator can be observed at. Grain is dispatched
    # at READ time from each observation row's ``entity_kind`` column;
    # never encoded in ``indicator_id``. After Phase-B collapse pairs the
    # same indicator_id can carry e.g. [country, state, district].
    entity_kinds: list[
        Literal["country", "state", "district", "ac", "party", "candidate"]
    ] = Field(min_length=1)
    default_entity_kind: Literal[
        "country", "state", "district", "ac", "party", "candidate"
    ]
    # v2.1 (PR-Z3b-tail-actionC 2026-05-26 guardrail #18). Publisher
    # refresh cadence in days (NDLM monthly = 30, RBI Handbook annual =
    # 365, Census decennial = 3650). Optional in schema during the
    # v2.0->v2.1 transition; intent is required. Enforced by the DARK
    # ``tier_b_indicator_freshness_declared`` check once chained live.
    update_period_days: int | None = Field(default=None, ge=1)
    # v2.2 (PR-Z3b-tail-conceptFK Carve 1 2026-05-26 guardrail #13). FK
    # to ``datasets/taxonomy/concepts.json``. Optional during the
    # v2.1->v2.2 transition; backfilled on all 183 rows by Carve 1 via
    # the concept_registry find_overlap helper. Enforced by the DARK
    # ``tier_b_one_indicator_per_concept`` check once chained live.
    concept_id: str | None = Field(
        default=None, pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", max_length=40
    )
    # v2.3 (PR-Zjust 2026-05-26 guardrail #15). Free-form structured
    # metadata; today only carries ``justification`` (required on
    # cross-grain concept twins by Tier-B
    # ``tier_b_indicator_has_justification``, chained live in this PR).
    # Pydantic-validated but NOT serialised to the parquet tuple --
    # consumers read meta.justification from the JSON catalogue.
    meta: _IndicatorMeta | None = None


# 35 columns, flat. Lists kept as VARCHAR[]; dicts/structs serialised to
# JSON-string for DuckDB-WASM friendliness. v2.0 (PR-B1 2026-05-26):
# id_aliases + deprecated_in removed; entity_kinds + default_entity_kind
# added (ADR-0044 grain-over-entity). v2.1 (PR-Z3b-tail-actionC
# 2026-05-26): update_period_days added (guardrail #18). v2.2
# (PR-Z3b-tail-conceptFK Carve 1 2026-05-26): concept_id FK added
# (guardrail #13).
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
    renderer_rules VARCHAR[],
    entity_kinds VARCHAR[] NOT NULL,
    default_entity_kind VARCHAR NOT NULL,
    update_period_days INTEGER,
    concept_id VARCHAR
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
        list(row.entity_kinds),
        row.default_entity_kind,
        row.update_period_days,
        row.concept_id,
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

        # v2.0 (PR-B1) -- default_entity_kind MUST be a member of
        # entity_kinds. Mirrors the soft contract spelled out in
        # indicator-catalogue.schema.json v2.0.
        if r.default_entity_kind not in r.entity_kinds:
            raise ValueError(
                f"indicator {r.indicator_id!r}: default_entity_kind "
                f"{r.default_entity_kind!r} not in entity_kinds "
                f"{list(r.entity_kinds)!r} (per indicator-catalogue.schema.json v2.0)."
            )

    # Deterministic order: by indicator_id (PK).
    rows.sort(key=lambda r: r.indicator_id)

    con = duckdb.connect(":memory:")
    try:
        con.execute(_DDL)
        if rows:
            con.executemany(
                "INSERT INTO indicators VALUES ("
                + ", ".join(["?"] * 35)
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
