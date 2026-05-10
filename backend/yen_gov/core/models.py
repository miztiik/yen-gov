"""Pydantic v2 models that mirror the JSON schemas under datasets/schemas/.

Per docs/architecture/backend/core.md, every published artifact corresponds 1:1 to a Pydantic model.
The model is the in-memory typed contract; the schema is the on-disk contract.
Both are kept in lock-step: any schema bump (CLAUDE.md §11) also updates the
model in the same commit.

Models do NOT stamp the artifact-level reserved fields ($schema,
$schema_version, sources). Those are stamped by core.io.write_artifact, which
remains the single chokepoint for emitting files. To bridge the two, every
top-level model exposes:

  - .sources_payload() -> list[core.io.Source]
  - .body_payload()    -> dict (no $schema / $schema_version / sources)

Adapters build a model, then hand both to write_artifact.

Source-of-truth precedence: if a constraint exists in the schema (pattern,
minimum, enum) it is also expressed here. The schema validator (Tier B) is the
final arbiter — but mirroring the constraints catches errors at construction
time rather than at write time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from yen_gov.core.io import Source as _IoSource


# --- shared building blocks -------------------------------------------------

# ECI state code: 'S' (state) or 'U' (UT) + two digits, e.g. S22, U07.
ECIStateCode = Annotated[str, Field(pattern=r"^[SU]\d{2}$")]

# ECI numeric party code (string to preserve leading zeros; integers in URLs).
PartyECICode = Annotated[str, Field(pattern=r"^\d+$")]

Body = Literal["AC", "PC"]
Reservation = Literal["GEN", "SC", "ST"]
Recognition = Literal["national", "state", "registered_unrecognised"]


class _Strict(BaseModel):
    """Base for all our models: forbid unknown fields (mirrors additionalProperties:false)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class SourceRef(_Strict):
    """One provenance entry. Mirrors the {url, fetched_at} object in every schema."""

    url: Annotated[str, Field(pattern=r"^https?://")]
    fetched_at: datetime

    @field_validator("fetched_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware (use UTC)")
        return v.astimezone(timezone.utc)

    def to_io_source(self) -> _IoSource:
        return _IoSource(url=self.url, fetched_at=self.fetched_at)


# --- top-level helper -------------------------------------------------------

class _Artifact(_Strict):
    """Mixin-ish base for top-level artifact models.

    Subclasses declare a class-level `_schema_id` and `_schema_version` matching
    the target schema. They also declare a `sources: list[SourceRef]` field.
    """

    sources: list[SourceRef]

    # Subclasses must override these two.
    _schema_id: str = ""
    _schema_version: str = ""

    def sources_payload(self) -> list[_IoSource]:
        return [s.to_io_source() for s in self.sources]

    def body_payload(self) -> dict[str, Any]:
        # Strip reserved fields ($schema/$schema_version/sources) — io.write_artifact stamps
        # those. exclude_none turns absent Optional fields into omitted keys (rather than
        # explicit nulls), which matches every schema's optional-non-required fields. The
        # only field that is BOTH required AND nullable across schemas is
        # ConstituencyResult.others; that model overrides body_payload to keep it.
        return self.model_dump(mode="json", exclude={"sources"}, exclude_none=True)


# --- election ---------------------------------------------------------------

class Election(_Artifact):
    """Mirrors datasets/schemas/election.schema.json (x-version 3.1)."""

    _schema_id = "https://yen-gov.github.io/schemas/election.schema.json"
    _schema_version = "3.1"

    eci_event_id: str = Field(min_length=1)
    scope: Literal["general", "state", "by_election"]
    body: Body
    year: int = Field(ge=1950)
    month: int | None = Field(default=None, ge=1, le=12)
    states: list[ECIStateCode] = Field(min_length=1)
    poll_dates: list[str] | None = None  # date-formatted strings
    result_date: str | None = None


# --- states collection ------------------------------------------------------

class StateEntry(_Strict):
    eci_code: ECIStateCode
    iso_3166_2: Annotated[str, Field(pattern=r"^[A-Z]{2}-[A-Z0-9]{2,3}$")]
    name: str = Field(min_length=1)
    kind: Literal["state", "union_territory"]
    capital: str | None = None
    verification_status: Literal[
        "live_url_probe_ok", "published_authority_only", "unverified"
    ] | None = None
    notes: str | None = None


class StatesCollection(_Artifact):
    """Mirrors datasets/schemas/state.schema.json (x-version 3.2)."""

    _schema_id = "https://yen-gov.github.io/schemas/state.schema.json"
    _schema_version = "3.2"

    country: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    states: list[StateEntry] = Field(min_length=1)


# --- districts collection ---------------------------------------------------

class DistrictEntry(_Strict):
    id: str = Field(min_length=1)
    id_source: Literal["lgd", "wikipedia"]
    name: str = Field(min_length=1)
    headquarters: str | None = None
    created_on: str | None = None  # date
    split_from: list[str] | None = None
    notes: str | None = None


class DistrictsCollection(_Artifact):
    """Mirrors datasets/schemas/district.schema.json (x-version 3.1)."""

    _schema_id = "https://yen-gov.github.io/schemas/district.schema.json"
    _schema_version = "3.1"

    state: ECIStateCode
    districts: list[DistrictEntry] = Field(min_length=1)


# --- constituencies collection ----------------------------------------------

class ConstituencyEntry(_Strict):
    eci_no: int = Field(ge=1)
    name: str = Field(min_length=1)
    district_id: str | None = None
    pc_id: Annotated[str, Field(pattern=r"^[SU]\d{2}-PC-\d+$")] | None = None
    electors: int | None = Field(default=None, ge=0)
    established_year: int | None = Field(default=None, ge=1947, le=2100)
    reservation: Reservation
    notes: str | None = None


ConstituencyStatus = Literal["provisional", "complete"]


class ConstituenciesCollection(_Artifact):
    """Mirrors datasets/schemas/constituency.schema.json (x-version 4.1)."""

    _schema_id = "https://yen-gov.github.io/schemas/constituency.schema.json"
    _schema_version = "4.1"

    state: ECIStateCode
    body: Body
    status: ConstituencyStatus
    constituencies: list[ConstituencyEntry] = Field(min_length=1)


# --- parties snapshot -------------------------------------------------------

class PartyEntry(_Strict):
    eci_code: PartyECICode
    short_name: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    symbol: str | None = None
    recognition: Recognition | None = None
    alliance: str | None = None


class PartiesSnapshot(_Artifact):
    """Mirrors datasets/schemas/party.schema.json (x-version 3.1)."""

    _schema_id = "https://yen-gov.github.io/schemas/party.schema.json"
    _schema_version = "3.1"

    election: str = Field(min_length=1)
    parties: list[PartyEntry] = Field(min_length=1)


# --- per-constituency result ------------------------------------------------

class ResultTotals(_Strict):
    electors: int | None = Field(default=None, ge=0)
    votes_polled: int = Field(ge=0)
    turnout_pct: float | None = Field(default=None, ge=0, le=100)


class CandidateResult(_Strict):
    rank: int = Field(ge=1)
    name: str = Field(min_length=1)
    party_eci_code: PartyECICode | None = None
    party_short: str = Field(min_length=1)
    votes: int = Field(ge=0)
    vote_share_pct: float = Field(ge=0, le=100)
    is_winner: bool | None = None


class NotaResult(_Strict):
    votes: int = Field(ge=0)
    vote_share_pct: float = Field(ge=0, le=100)


class OthersBucket(_Strict):
    candidate_count: int = Field(ge=1)
    votes: int = Field(ge=0)
    vote_share_pct: float = Field(ge=0, le=100)


class WinnerInfo(_Strict):
    name: str = Field(min_length=1)
    party_eci_code: PartyECICode | None = None
    party_short: str = Field(min_length=1)
    votes: int = Field(ge=0)
    margin_votes: int = Field(ge=0)
    margin_pct: float = Field(ge=0, le=100)


class ConstituencyResult(_Artifact):
    """Mirrors datasets/schemas/result.constituency.schema.json (x-version 3.1)."""

    _schema_id = "https://yen-gov.github.io/schemas/result.constituency.schema.json"
    _schema_version = "3.1"

    election: str = Field(min_length=1)
    state: ECIStateCode
    body: Body
    eci_no: int = Field(ge=1)
    constituency_name: str | None = Field(default=None, min_length=1)
    totals: ResultTotals
    candidates: list[CandidateResult] = Field(min_length=1)
    nota: NotaResult
    others: OthersBucket | None = None
    top_n_cutoff: int = Field(ge=1)
    winner: WinnerInfo

    def body_payload(self) -> dict[str, Any]:
        # `others` is required AND nullable in the schema — keep the explicit null
        # when no candidates were collapsed.
        d = super().body_payload()
        d.setdefault("others", None)
        return d


# --- per-state result summary -----------------------------------------------

class PartyTotals(_Strict):
    party_eci_code: PartyECICode | None = None
    party_short: str = Field(min_length=1)
    party_full: str | None = None
    seats_contested: int | None = Field(default=None, ge=0)
    seats_won: int = Field(ge=0)
    votes: int = Field(ge=0)
    vote_share_pct: float = Field(ge=0, le=100)


class AllianceDistribution(_Strict):
    alliance: str = Field(min_length=1)
    seats_won: int = Field(ge=0)
    vote_share_pct: float | None = Field(default=None, ge=0, le=100)


class SummaryTotals(_Strict):
    electors: int | None = Field(default=None, ge=0)
    votes_polled: int | None = Field(default=None, ge=0)
    turnout_pct: float | None = Field(default=None, ge=0, le=100)


class ResultSummary(_Artifact):
    """Mirrors datasets/schemas/result.summary.schema.json (x-version 3.1)."""

    _schema_id = "https://yen-gov.github.io/schemas/result.summary.schema.json"
    _schema_version = "3.1"

    election: str = Field(min_length=1)
    state: ECIStateCode
    body: Body
    total_seats: int = Field(ge=1)
    totals: SummaryTotals | None = None
    party_totals: list[PartyTotals] = Field(min_length=1)
    alliance_distribution: list[AllianceDistribution] | None = None


# --- processing config ------------------------------------------------------

class FetchKnobs(_Strict):
    concurrency: int = Field(ge=1, le=32)
    retry_attempts: int = Field(ge=0, le=10)
    retry_backoff_seconds: float | None = Field(default=None, ge=0)
    timeout_seconds: float = Field(gt=0)
    user_agent: str = Field(min_length=1)


class ResultsKnobs(_Strict):
    top_n_candidates: int = Field(ge=1)
    collapse_others: bool


class ProcessingConfig(_Artifact):
    """Mirrors datasets/schemas/processing.schema.json (x-version 3.1)."""

    _schema_id = "https://yen-gov.github.io/schemas/processing.schema.json"
    _schema_version = "3.1"

    fetch: FetchKnobs
    results: ResultsKnobs
