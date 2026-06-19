"""Legacy row data-shape DTOs for the ECI electoral path + the citation seeds.

Relocated VERBATIM from the retired ``canonical/envelope.py`` (ingest
rip-replace Row 9). ``envelope.py`` and ``writer.py`` were the
Parquet-era ``adapter -> write_batch`` contract; both are deleted. What
survives here are the *row builder* DTOs that two still-live, not-yet-
modernised paths construct:

* the three ECI electoral adapters (``eci_ls``, ``eci_ae_panel``,
  ``pipeline.canonical_eci_backfill``) + their three sub-helpers
  (``eci.observations``, ``eci.pc_observations``, ``eci.rollups``) build
  :class:`ObservationRow` + the six dim rows, then hand the observation +
  source rows to ``eci.electoral_csv.write_electoral_results`` /
  ``upsert_source_csv``;
* three citation seeds (``boundary_layers_seed``, ``livestock_sources_seed``,
  ``datagovin_ogd.ingest_pincode``) build :class:`SourceRow`.

Ruling (Gregor contracts + Fowler craft, Row 9 debate): these are NOT the
new pipeline contract. ``canonical/ingest/messages.py`` owns the
long-format-CSV stage messages, and its ``CanonicalObservationRow``
(geo 4-tuple ``entity_id/time/value/source_id``) +
``CanonicalSourceRow`` (5-field ``source.csv`` ledger row) deliberately
bind to the NEW on-disk shapes. The ECI electoral path still uses the
LEGACY 9-field observation row
(``entity_id/year/period_label/period_seq/indicator_id/value_numeric/
value_text/source_id/derivation``) and the 11-field citation-builder
``SourceRow``; those shapes do not fit the ``messages.py`` types, so they
are quarantined HERE rather than polluting the new contract or being
force-fit. ``citation.py`` was rejected as a home because it is
stdlib-only by explicit contract (no pydantic).

Dropped on relocation (died with the writer path, zero surviving
consumers): the ``BatchEnvelope`` container, envelope's own
``ReplacementSemantics`` (``messages.py`` carries the surviving one), the
writer-only ``ObservationRow.with_id()`` / ``compute_observation_id`` helpers,
and the no-op ``_exactly_one_value`` field-validator (it never enforced
anything; the cross-field check lived in the now-deleted writer).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceRow(BaseModel):
    """A citation-ledger builder row (11-field legacy shape).

    Identity is the ``(producer, title, vintage)`` triple; ``source_id`` is
    its deterministic 12-char hash -- build via
    ``canonical.citation.derive_source_id``, never hand-author.

    Only the five on-disk fields ``(source_id, producer, title, vintage,
    url_main)`` reach ``datasets/data/entities/source.csv`` (the 6
    ``license`` .. ``notes`` extension fields are retained for the seeds'
    builders + their tests but are not written -- CLAUDE.md section 12). The
    on-disk write row is the 5-field ``messages.CanonicalSourceRow``; this
    11-field DTO is the builder-side superset.

    ``frozen=True`` because rows are dedup'd by ``source_id``; mutate via
    ``model_copy(update=...)``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=r"^src-[a-z0-9]{12}$")
    producer: str = Field(min_length=1)
    title: str = Field(min_length=1)
    vintage: str = Field(
        min_length=1,
        description=(
            "Strongest period anchor available per ADR-0042: publisher edition "
            "when the upstream publishes one, operator snapshot window when not."
        ),
    )
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
    """A row destined for the per-state electoral CSV via
    ``eci.electoral_csv.write_electoral_results``.

    The 9-field electoral observation shape (``observation_id`` is the
    optional derived hash of the logical key, dropped at CSV-write time).
    Mirrors the columns of ``datasets/data/datapoints/electoral/*.csv``.
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


class PersonDimRow(BaseModel):
    """A candidacy-person dim row (ADR-0035 Layer 1: one person per candidacy).

    Built by the electoral adapters; not written to disk (the dim parquets
    retired in X1b). PK = person_id.
    """

    model_config = ConfigDict(extra="forbid")

    person_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    display_name: str | None = None
    source_id: str = Field(min_length=1)
    sex: str | None = Field(default=None)
    age: int | None = Field(default=None, ge=18, le=120)
    education: str | None = Field(default=None)
    profession: str | None = Field(default=None)


class CandidacyRow(BaseModel):
    """A per-contest candidacy dim row. PK = candidacy_key. Built by the
    electoral adapters; not written to disk (the dim parquets retired)."""

    model_config = ConfigDict(extra="forbid")

    candidacy_key: str = Field(
        pattern=r"^IN-(?:[SU]\d{2}-AC-\d{4}|PC-\d{4}-[SU]\d{2})-\d+-"
        r"(?:AcGen|LsGen|AcBye|LsBye)"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{4}-C\d{2,3}$"
    )
    person_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    ac_id: str | None = Field(default=None, pattern=r"^IN-[SU]\d{2}-AC-\d{4}-\d+$")
    pc_id: str | None = Field(default=None, pattern=r"^IN-PC-\d{4}-[SU]\d{2}-\d+$")
    election_id: str = Field(min_length=1)
    ballot_serial: int = Field(ge=1, le=999)
    party_id: str = Field(pattern=r"^parties\.IN\.[A-Z][A-Z0-9_]*$")
    rank: int = Field(ge=1)
    votes_polled: float | None = None
    vote_share_pct: float | None = None
    won: bool
    source_id: str = Field(min_length=1)
    party_short_raw: str | None = None
    constituency_type: str | None = Field(default=None)
    party_type: str | None = Field(default=None)

    @model_validator(mode="after")
    def _exactly_one_constituency_fk(self) -> "CandidacyRow":
        """Exactly one of ac_id / pc_id is set; grain is dispatched at read time."""
        if (self.ac_id is None) == (self.pc_id is None):
            raise ValueError(
                "CandidacyRow requires exactly one of ac_id / pc_id to be set "
                f"(ac_id={self.ac_id!r}, pc_id={self.pc_id!r})"
            )
        return self


class AcDimRow(BaseModel):
    """An Assembly-constituency dim row. PK = ac_id. Built by the electoral
    adapters; not written to disk (the dim parquets retired)."""

    model_config = ConfigDict(extra="forbid")

    ac_id: str = Field(pattern=r"^IN-[SU]\d{2}-AC-\d{4}-\d+$")
    state_code: str = Field(pattern=r"^[SU]\d{2}$")
    delim_year: int = Field(ge=1850, le=2100)
    eci_no: int = Field(ge=1)
    name: str | None = None
    source_id: str = Field(min_length=1)
    lgd_ac_id: int | None = None


class PcDimRow(BaseModel):
    """A Parliament-constituency (Lok Sabha) dim row. PK = pc_id (carries the
    state_code for global uniqueness). Built by the electoral adapters; not
    written to disk (the dim parquets retired)."""

    model_config = ConfigDict(extra="forbid")

    pc_id: str = Field(pattern=r"^IN-PC-\d{4}-[SU]\d{2}-\d+$")
    state_code: str = Field(pattern=r"^[SU]\d{2}$")
    delim_year: int = Field(ge=1850, le=2100)
    pc_no: int = Field(ge=1)
    name: str | None = None
    source_id: str = Field(min_length=1)


class PartyDimRow(BaseModel):
    """A party dim row. PK = party_id. Built by the electoral adapters; not
    written to disk (the dim parquets retired). The brand_colour /
    wikipedia_url / election_symbol mirror columns are flattened from
    taxonomy/parties.json for the frontend resolver + symbol chip."""

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
    # --- additive mirror columns (all nullable) ---
    brand_colour_hex: str | None = Field(
        default=None,
        pattern=r"^#[0-9a-fA-F]{6}$",
    )
    brand_colour_confidence: str | None = Field(
        default=None,
        pattern=r"^(high|medium|low)$",
    )
    wikipedia_url: str | None = None
    election_symbol_asset_path: str | None = Field(
        default=None,
        pattern=r"^party-symbols/[a-z0-9_-]+\.(svg|png|jpg|jpeg|webp)$",
    )
    election_symbol_render_mode: str | None = Field(
        default=None,
        pattern=r"^(source_coloured|recolourable|silhouette)$",
    )


class PartyAllianceDimRow(BaseModel):
    """A per-event party-alliance dim row. Composite PK = (party_id,
    period_label). Built by the electoral adapters; not written to disk (the
    dim parquets retired; the data SoT is
    ``datasets/data/entities/party_alliances.csv``)."""

    model_config = ConfigDict(extra="forbid")

    party_id: str = Field(pattern=r"^parties\.IN\.[A-Z][A-Z0-9_]*$")
    short_name: str = Field(min_length=1)
    period_label: str = Field(min_length=1)
    alliance: str | None = None
    source_id: str = Field(min_length=1)
