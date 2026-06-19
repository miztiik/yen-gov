"""Typed stage messages for the ingest pipeline (Row 1, plan D3).

Three pure-filter stages -- Fetch -> Enrich -> Publish -- hand each other
ONE pydantic message per hop. Every message is validated at construction
(the producing filter) and trusted between hops:

    FETCH   produces ClaimCheck      (a handle to the cached raw payload)
    ENRICH  produces CanonicalBatch   (parsed + canonicalised rows to write)

``RawRecord`` is the intermediate ENRICH works on internally: one parsed
upstream cell BEFORE entity/unit/period resolution.

Per the engineering contract (plan D3) pydantic is mandatory for every
in-process boundary type. These mirror the style of
``yen_gov.canonical.envelope`` (``ConfigDict(extra="forbid")`` + ``Field``
constraints) but DELIBERATELY do not reuse it:

* ``CanonicalSourceRow`` is the FIVE-field ``source.csv`` shape
  ``(source_id, producer, title, vintage, url)`` -- NOT the retired
  11-field ``envelope.SourceRow`` (license / confidence_tier / ... were
  dropped from the on-disk citation ledger; CLAUDE.md section 12).
* ``CanonicalObservationRow`` mirrors the NON-FACET
  ``datasets/data/datapoints/geo/*.csv`` column set
  ``(entity_id, time, value, source_id)`` EXACTLY. The indicator is the
  FILENAME (one file per variable_id), so ``indicator_id`` is a
  BATCH-level field, never a row column. ``test_ingest_spec`` pins the row
  field names to ``columns.json`` so the two can never drift.

Ruling (Gregor + Hans + Max, Row 1 debate): the canonical observation shape
binds to ``columns.json`` (the data-shape SOT, CLAUDE.md Holy Law #3), not
to the legacy ``envelope.ObservationRow`` 6-tuple
``(entity_id, year, period_label, indicator_id, value_numeric, source_id)``
that the long-format CSV rip retired. ``period_label`` and the per-row
``indicator_id`` are gone; ``year`` is the integer column ``time``.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ReplacementSemantics(str, Enum):
    """How PUBLISH reconciles a batch's rows with what is already on disk."""

    upsert = "upsert"
    """Default. Match on the geo PK ``(entity_id, time)``; update value +
    source_id in place; insert if absent. A re-fetch with byte-identical
    upstream is a no-op."""

    replace_partition = "replace_partition"
    """Delete every row of this indicator's file, then insert the batch.
    Reserved for upstream corrections that REMOVE observations (an UPSERT
    cannot infer deletions). Callers MUST document why they chose this."""


class ClaimCheck(BaseModel):
    """FETCH output: an opaque handle to one fetched-and-cached raw payload.

    A claim check is a *reference*, never the bytes. The orchestrator dedups
    cache units by ``cache_key`` equality and re-opens a year only when
    ``content_hash`` changes (the year-checkpoint diff, Row 2). The raw bytes
    live under the gitignored meadow tier; ``payload_ref`` is the
    repo-relative POSIX handle to them (relativised by the path util, Row 3).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_slug: str = Field(min_length=1)
    cache_key: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload_ref: str = Field(min_length=1)


class RawRecord(BaseModel):
    """ENRICH intermediate: one parsed upstream cell BEFORE canonicalisation.

    Carries the publisher's verbatim entity + period labels (pre-LGD /
    pre-period-normalisation) plus the value. ENRICH resolves these into a
    :class:`CanonicalObservationRow`. ``indicator_id`` is the slice ENRICH is
    parsing (one indicator per pass).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    indicator_id: str = Field(pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", max_length=60)
    source_id: str = Field(pattern=r"^src-[a-z0-9]{12}$")
    raw_entity: str = Field(min_length=1)
    raw_period: str = Field(min_length=1)
    value_numeric: float | None = None
    value_text: str | None = None


class CanonicalSourceRow(BaseModel):
    """One row destined for ``datasets/data/entities/source.csv``.

    The FIVE-field citation-ledger shape (CLAUDE.md section 12): identity is
    the ``(producer, title, vintage)`` triple, ``source_id`` is its derived
    12-char hash (build via ``canonical.citation.derive_source_id``), ``url``
    is the optional citizen-openable landing page. producer / title / vintage
    are required non-empty -- they are the triple that derives ``source_id``
    (Holy Law #9). ``url`` is the only nullable field, matching the on-disk
    ``source.csv`` column contract.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=r"^src-[a-z0-9]{12}$")
    producer: str = Field(min_length=1)
    title: str = Field(min_length=1)
    vintage: str = Field(min_length=1)
    url: str | None = Field(default=None)


class CanonicalObservationRow(BaseModel):
    """One row destined for ``datasets/data/datapoints/geo/<indicator_id>.csv``.

    Mirrors the NON-FACET ``geo/*.csv`` column set from
    ``datasets/data/_schema/columns.json`` EXACTLY:
    ``(entity_id, time, value, source_id)``. ``indicator_id`` is the FILE
    (batch-level on :class:`CanonicalBatch`), never a row column.
    ``test_observation_row_keys_match_geo_columns`` pins these field names to
    columns.json so a future column change fails loud here.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_id: str = Field(min_length=1)
    time: int = Field(ge=1850, le=2100)
    value: float | None = None
    source_id: str = Field(pattern=r"^src-[a-z0-9]{12}$")


class CanonicalBatch(BaseModel):
    """ENRICH output / PUBLISH input: one indicator's canonical rows.

    One batch == one ``geo/<indicator_id>.csv`` file. ``observation_rows``
    carry the 4-column geo shape; ``source_rows`` carry the 5-field citation
    rows UPSERTed into ``source.csv``. ``replacement_semantics`` defaults to
    upsert. ``indicator_id`` lives HERE (the file identity), not on each row.
    """

    model_config = ConfigDict(extra="forbid")

    indicator_id: str = Field(pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", max_length=60)
    replacement_semantics: ReplacementSemantics = ReplacementSemantics.upsert
    source_rows: list[CanonicalSourceRow] = Field(default_factory=list)
    observation_rows: list[CanonicalObservationRow]
