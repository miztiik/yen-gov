"""Compile ``datasets/taxonomy/topics.json`` to two Parquet siblings.

§8.3 Python-compiles-to-Parquet seam. Emits:

    1. ``topics.parquet`` — one row per topic (topic_id, title, list,
       summary, icon, featured, peer_set_default). The topic
       dimension.

    2. ``indicator_topic_tags.parquet`` — one row per
       (topic_id, artifact_kind, artifact_id). The M:N join between
       topics and the polymorphic artifact references they expose.
       Per ADR-0022: topic membership lives on the catalogue, not on
       the artifact, so this is THE join table the Topic Front Door
       ``/t/:topic`` reads to enumerate which indicators / elections /
       feature collections belong under each topic.

Input contract: ``datasets/taxonomy/topics.json`` validated against
``datasets/schemas/topic-catalogue.schema.json`` (v1.2).

Topics taxonomy is FLAT — no ``parent_topic_id``. Sub-topics, if ever
needed, use slash-segmented ids (``fiscal/transfers``) per the catalogue
schema's ``id`` pattern; the slash carries no relational semantics for
the seed and no UNNEST-on-read cost. Per Plan §0e.10.2-D LOCKED.

Rejected designs (do NOT re-propose):
    1. Emit a single ``topics.parquet`` with ``artifacts[]`` as a STRUCT
       column. Citizen consumer always wants either "topics list" or
       "artifacts under topic X" — neither benefits from the list
       shape, both pay UNNEST cost.
    2. Add a synthetic ``parent_topic_id`` derived from slash splitting.
       Plan §0e.10.2-D explicitly REJECTED hierarchy; the catalogue is
       a flat list, slash-segmented ids are URL slugs not parentage.
       Re-introducing parentage here would force consumers to choose
       between two truths (the slug vs the column) — that is exactly
       the polymorphism trap §0e.10.2-D refused.
    3. Carry the catalogue's per-artifact polymorphic fields
       (``chart_type``, ``dimension``, ``scope``) on the ``topics``
       dim instead of the ``indicator_topic_tags`` fact. Wrong key:
       these fields describe how the artifact renders WITHIN this
       topic, so they belong on the M:N row, not the topic row. One
       artifact may appear under multiple topics with different
       chart_type hints in the future.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

# Row-schema-version constants. Independent of the input catalogue
# ``topic-catalogue.schema.json`` x-version; bump when the Parquet row
# shape changes.
TOPICS_ROW_SCHEMA_VERSION = "1.0"
INDICATOR_TOPIC_TAGS_ROW_SCHEMA_VERSION = "1.0"


SeventhScheduleList = Literal["state", "union", "concurrent", "na"]
PeerSetDefault = Literal[
    "all",
    "general_category",
    "special_category",
    "neh",
    "himalayan",
    "ut_legislature",
    "ut_no_legislature",
    "nct_delhi",
    "fc_horizontal_devolution_share_quintile",
    "coastal_states",
    "landlocked_states",
    "art_371_states",
]
ArtifactKind = Literal["indicator", "election", "feature_collection"]
ChartType = Literal["choropleth", "ranked", "stacked-trend"]
Scope = Literal["national", "state", "constituency"]


class _Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ArtifactKind
    id: str = Field(min_length=1)
    display: str | None = None
    default: bool = False
    featured: bool = False
    scope: Scope | None = None
    chart_type: ChartType | None = None
    dimension: str | None = None
    peer_set_default: PeerSetDefault | None = None


class _Topic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    list: SeventhScheduleList
    summary: str = Field(min_length=1)
    icon: str | None = None
    featured: bool = False
    peer_set_default: PeerSetDefault | None = None
    notes: str | None = None
    artifacts: list[_Artifact] = Field(min_length=1)


class _TopicCatalogueFile(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    topics: list[_Topic] = Field(min_length=1)


def _topic_rows(
    topics: list[_Topic],
) -> list[tuple[str, str, str, str, str | None, bool, str | None, str | None]]:
    """One row per topic. Sort: catalogue order via numeric index.

    We emit catalogue order verbatim as ``display_order`` (1-based) so the
    Topic Front Door can reproduce the hand-curated rendering order
    without a separate config. The plan's editorial intent (which topic
    leads /t) lives in the JSON's array order; persisting it as an
    explicit column makes it queryable.
    """
    return [
        (
            t.id,
            t.title,
            t.list,
            t.summary,
            t.icon,
            t.featured,
            t.peer_set_default,
            t.notes,
        )
        for t in topics
    ]


def _tag_rows(
    topics: list[_Topic],
) -> list[
    tuple[
        str, str, str, str | None, bool, bool, str | None, str | None, str | None, str | None, int
    ]
]:
    """One row per (topic_id, artifact_kind, artifact_id, in_topic_order).

    The compound natural key is (topic_id, kind, id) — the same
    indicator id can appear in multiple topics (e.g. an electricity
    indicator listed under both ``energy`` and ``infrastructure``)
    without collision. Per-topic order within the artifacts[] array is
    preserved as a 1-based integer so the consumer can render them in
    the catalogue's chosen order without a separate sort hint.
    """
    out: list[
        tuple[
            str,
            str,
            str,
            str | None,
            bool,
            bool,
            str | None,
            str | None,
            str | None,
            str | None,
            int,
        ]
    ] = []
    for topic in topics:
        for idx, art in enumerate(topic.artifacts, start=1):
            out.append(
                (
                    topic.id,
                    art.kind,
                    art.id,
                    art.display,
                    art.default,
                    art.featured,
                    art.scope,
                    art.chart_type,
                    art.dimension,
                    art.peer_set_default,
                    idx,
                )
            )
    out.sort(key=lambda row: (row[0], row[1], row[2]))
    return out


def compile_to_parquet(json_in: Path, topics_out: Path, tags_out: Path) -> tuple[int, int]:
    """Emit ``topics.parquet`` + ``indicator_topic_tags.parquet``.

    Returns ``(n_topics, n_tags)``. Caller ensures both output parents
    exist.
    """
    topics_out = Path(topics_out)
    tags_out = Path(tags_out)
    payload = json.loads(Path(json_in).read_text(encoding="utf-8"))
    for k in ("$schema", "$schema_version", "$comment", "sources"):
        payload.pop(k, None)
    data = _TopicCatalogueFile.model_validate(payload)
    trows = _topic_rows(list(data.topics))
    tagrows = _tag_rows(list(data.topics))

    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE topics (
                topic_id VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                seventh_schedule_list VARCHAR NOT NULL,
                summary VARCHAR NOT NULL,
                icon VARCHAR,
                featured BOOLEAN NOT NULL,
                peer_set_default VARCHAR,
                notes VARCHAR
            )
            """
        )
        con.executemany(
            "INSERT INTO topics VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            trows,
        )
        con.execute(
            f"""
            COPY (
                SELECT * FROM topics
                ORDER BY topic_id
            ) TO '{topics_out.as_posix()}' (FORMAT PARQUET)
            """
        )
        con.execute(
            """
            CREATE TABLE indicator_topic_tags (
                topic_id VARCHAR NOT NULL,
                artifact_kind VARCHAR NOT NULL,
                artifact_id VARCHAR NOT NULL,
                display VARCHAR,
                is_default BOOLEAN NOT NULL,
                featured BOOLEAN NOT NULL,
                scope VARCHAR,
                chart_type VARCHAR,
                dimension VARCHAR,
                peer_set_default_override VARCHAR,
                in_topic_order INTEGER NOT NULL
            )
            """
        )
        if tagrows:
            con.executemany(
                "INSERT INTO indicator_topic_tags VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tagrows,
            )
        con.execute(
            f"""
            COPY (
                SELECT * FROM indicator_topic_tags
                ORDER BY topic_id, artifact_kind, artifact_id
            ) TO '{tags_out.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()
    return len(trows), len(tagrows)
