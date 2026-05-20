"""Typed batch envelope — adapter -> writer contract (D20).

An adapter (httpx + lxml + pandas) builds ONE envelope per fetch, then hands
it to ``write_batch(envelope, datasets_root)``. The envelope is the only
shape the writer accepts; adapters cannot bypass it.

Per docs/architecture/data/canonical-store.md §14 (write path):

    adapter
        |
        | typed batch envelope (D20):
        |   { target_family, schema_version, source_rows[],
        |     observation_rows[], replacement_semantics }
        v
    canonical writer

D17 / R16: source_id is row-attribute (NOT logical key). Two envelopes that
emit the same logical key with different source_ids UPSERT into one row.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReplacementSemantics(str, Enum):
    """How the writer reconciles envelope rows with what's already in the store."""

    upsert = "upsert"
    """D7 default. Match on logical key (entity_id, year, period_label,
    indicator_id); update value_* + source_id in place; insert if absent.
    A re-fetch with byte-identical upstream is a no-op."""

    replace_partition = "replace_partition"
    """Rare. Delete every row whose (family, indicator_id) matches this
    envelope, then insert envelope rows. Reserved for upstream corrections
    that REMOVE observations (the writer cannot infer deletions from an
    UPSERT). Adapters MUST document why they chose this on use."""


class SourceRow(BaseModel):
    """A row destined for taxonomy/sources.parquet (citation ledger).

    v2.0 (ADR-0032): one row per CITATION, not per fetch event. Natural
    identity = ``(producer, title, vintage)``; ``source_id`` is the
    deterministic 12-char hash of that triple — use
    ``backend.yen_gov.canonical.citation.derive_source_id`` to build it,
    never hand-author.

    Mirrors ``datasets/schemas/source.schema.json`` item shape exactly.
    Fetch telemetry (url-it-was-polled-from, content_hash, first/last_seen)
    is OUT of the contract — adapters that need cache-invalidation state
    write it to a sidecar under ``.runtime/<adapter>/<source_id>.json``.

    ``frozen=True`` because rows are dedup'd by source_id in the writer's
    envelope-apply step; mutating a row after construction would defeat
    that dedup. Adapters that need to vary a field should build a new
    SourceRow via ``model_copy(update=...)``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=r"^src-[a-z0-9]{12}$")
    producer: str = Field(min_length=1)
    title: str = Field(min_length=1)
    vintage: str  # required string; permitted empty when source publishes no vintage
    license: Literal[
        "OGL-IN-1.0", "CC-BY-4.0", "CC0-1.0", "public-domain", "unknown-public", "internal"
    ]
    confidence_tier: Literal["gold", "silver", "bronze"]
    is_issuing_authority: bool
    verification_method: Literal["live-fetch", "archived-snapshot", "transcribed", "editorial"]
    url_main: str | None = None
    citation_full: str | None = None
    notes: str | None = None


class ObservationRow(BaseModel):
    """A row destined for ``datasets/<family>/observations.parquet``.

    Mirrors datasets/schemas/observation.schema.json. ``observation_id`` is
    derived; the adapter may omit it and ``compute_observation_id`` fills it.
    """

    model_config = ConfigDict(extra="forbid")

    observation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    entity_id: str = Field(min_length=1)
    year: int = Field(ge=1850, le=2100)
    period_label: str = Field(min_length=1)
    period_seq: int = Field(ge=1)
    indicator_id: str = Field(pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", max_length=60)
    value_numeric: float | None = None
    value_text: str | None = None
    source_id: str = Field(min_length=1)
    derivation: str | None = Field(
        default=None,
        pattern=r"^(raw|sum|argmax|join|ratio_pct|diff|count|count_where|laakso_taagepera|constant)$",
    )

    @field_validator("value_text")
    @classmethod
    def _exactly_one_value(cls, v: str | None, info) -> str | None:
        # Writer-enforced (per observation.schema.json description). Pydantic
        # only sees one field at a time; cross-field enforcement happens in
        # writer.write_batch before emit.
        return v

    def with_id(self) -> "ObservationRow":
        if self.observation_id is not None:
            return self
        return self.model_copy(update={"observation_id": compute_observation_id(self)})


def compute_observation_id(row: ObservationRow) -> str:
    """sha256(entity_id || year || period_label || indicator_id), hex.

    Per observation.schema.json + D7 logical key. source_id is NOT part of
    the identity hash (R16).
    """
    key = f"{row.entity_id}|{row.year}|{row.period_label}|{row.indicator_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class CandidateDimRow(BaseModel):
    """A row destined for ``datasets/elections/dim_candidates.parquet``.

    Mirrors datasets/schemas/dim-candidates.schema.json. PK = candidate_id
    (matches observations.entity_id for candidate-* rows).
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(
        pattern=r"^IN-[SU]\d{2}-AC-\d{4}-\d+-(?:AcGen|LsGen|AcBye|LsBye)"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{4}-C\d{2}$"
    )
    ac_id: str = Field(pattern=r"^IN-[SU]\d{2}-AC-\d{4}-\d+$")
    period_label: str = Field(min_length=1)
    ballot_serial: int = Field(ge=1, le=99)
    name: str | None = None
    party_id: str = Field(pattern=r"^parties\.IN\.[A-Z][A-Z0-9_]*$")
    rank: int = Field(ge=1)
    source_id: str = Field(min_length=1)
    # v1.1 (additive): verbatim ECI party_short from the upstream candidate row.
    # Citizen UI falls back to this when party_id == 'parties.IN.UNK' so the
    # chip never shows the literal sentinel. Nullable for NOTA / missing.
    party_short_raw: str | None = None
    # v1.2 (additive, PR-S.1): biographic fields lifted from the per-candidate
    # JSON sidecars formerly under datasets/people/<event>/<ac>/<slug>.json
    # into inline columns on dim_candidates. Enums mirror dim-candidates schema
    # v1.2 (copied verbatim from people.entity.schema.json v1.0). Nullable on
    # every field — biographic data is only populated for the subset of events
    # where an ECI Statistical Report adapter has run (currently TN AcGenApr2021).
    sex: str | None = Field(default=None)
    age: int | None = Field(default=None, ge=18, le=120)
    education: str | None = Field(default=None)
    profession: str | None = Field(default=None)
    constituency_type: str | None = Field(default=None)
    party_type: str | None = Field(default=None)


class AcDimRow(BaseModel):
    """A row destined for ``datasets/elections/dim_acs.parquet``.

    Mirrors datasets/schemas/dim-acs.schema.json. PK = ac_id.
    """

    model_config = ConfigDict(extra="forbid")

    ac_id: str = Field(pattern=r"^IN-[SU]\d{2}-AC-\d{4}-\d+$")
    state_code: str = Field(pattern=r"^[SU]\d{2}$")
    delim_year: int = Field(ge=1850, le=2100)
    eci_no: int = Field(ge=1)
    name: str | None = None
    source_id: str = Field(min_length=1)


class PartyDimRow(BaseModel):
    """A row destined for ``datasets/elections/dim_parties.parquet``.

    Mirrors datasets/schemas/dim-parties.schema.json. PK = party_id.
    Sourced from the in-memory PartyLookup registry (taxonomy/parties.json),
    NOT re-fetched.
    """

    model_config = ConfigDict(extra="forbid")

    party_id: str = Field(pattern=r"^parties\.IN\.[A-Z][A-Z0-9_]*$")
    eci_code: str | None = None
    short_name: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    recognition: str | None = Field(
        default=None,
        pattern=r"^(national|state|registered_unrecognised|unknown)$",
    )
    source_id: str = Field(min_length=1)


class PartyAllianceDimRow(BaseModel):
    """A row destined for ``datasets/elections/dim_party_alliances.parquet``.

    Mirrors datasets/schemas/dim-party-alliances.schema.json. Composite PK =
    (party_id, period_label). Alliance is per-event (DMK was 'UPA' in 2019,
    'SPA' in 2026), so it sits on its own dim table rather than as a column
    on dim_parties (party identity). Sourced from the alliance_history[]
    field of taxonomy/parties.json entries.
    """

    model_config = ConfigDict(extra="forbid")

    party_id: str = Field(pattern=r"^parties\.IN\.[A-Z][A-Z0-9_]*$")
    short_name: str = Field(min_length=1)
    period_label: str = Field(min_length=1)
    alliance: str | None = None
    source_id: str = Field(min_length=1)


class BatchEnvelope(BaseModel):
    """The one shape adapters hand to the writer.

    ``schema_version`` is the writer-contract version (not a row-schema
    version). Bump when this envelope's own shape changes.

    Dimension lists are optional. Each is UPSERTed on its own PK and emits a
    sibling Parquet under datasets/<target_family>/dim_*.parquet. Empty lists
    are a no-op (existing dim Parquet untouched).
    """

    model_config = ConfigDict(extra="forbid")

    target_family: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    schema_version: str = Field(pattern=r"^\d+\.\d+$", default="1.0")
    replacement_semantics: ReplacementSemantics = ReplacementSemantics.upsert
    source_rows: list[SourceRow] = Field(default_factory=list)
    observation_rows: list[ObservationRow]
    candidate_dim_rows: list[CandidateDimRow] = Field(default_factory=list)
    ac_dim_rows: list[AcDimRow] = Field(default_factory=list)
    party_dim_rows: list[PartyDimRow] = Field(default_factory=list)
    party_alliance_dim_rows: list[PartyAllianceDimRow] = Field(default_factory=list)
