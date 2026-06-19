"""Author-time source + indicator specs for the ingest pipeline (Row 1).

A :class:`SourceSpec` is the PARENT: it carries everything that identifies
the upstream *source* -- the adapter that drives it and the provenance
quartet (producer / title / vintage / url) that derives the citation
``source_id``. Its children are :class:`IndicatorSpec` rows: each carries
everything that identifies one *indicator* the source feeds -- the catalogue
id plus the ``(unit, normalisation, price_basis, sampling_frame)`` tuple that
MUST match the indicator's concept (enforced at registration by
``catalogue_fk``).

Field-split ruling (Gregor = contracts, Row 1 persona debate)
-------------------------------------------------------------
NO field is repeated across the two levels. The split is by *identity axis*:

* SOURCE-level (only on :class:`SourceSpec`): ``adapter_slug`` + the
  provenance quartet ``producer`` / ``title`` / ``vintage`` / ``url``. These
  describe WHO published the data and HOW the pipeline fetches it. The
  derived ``source_id`` is COMPUTED from ``(producer, title, vintage)`` -- it
  is never STORED on either level, so it cannot drift.
* INDICATOR-level (only on :class:`IndicatorSpec`): ``indicator_id`` + the
  measurement tuple ``unit`` / ``normalisation`` / ``price_basis`` /
  ``sampling_frame``. These describe WHAT is measured.

This mirrors the on-disk identity SOT
(``concepts.json -> indicators.json -> source.csv``): a source is a citation,
an indicator is a measurement, and the two meet only by the observation
row's ``source_id`` FK. Repeating, say, ``producer`` on an IndicatorSpec
would invite an adapter to set a different producer per indicator -- a
provenance lie the single-source-of-truth split makes unrepresentable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from yen_gov.canonical.citation import derive_source_id

# The concept normalisation enum, verbatim from concepts.schema.json. Kept
# here (not imported) because the schema is a JSON artifact, not a Python
# module; ``catalogue_fk`` compares a spec's value against the concept row
# at registration, which catches any future drift between the two.
Normalisation = Literal[
    "absolute", "per_capita", "per_area", "share", "ratio", "index"
]


class PriceBasis(BaseModel):
    """Whether a monetary value is in CURRENT (nominal) or CONSTANT (real) prices.

    Mirrors the additive ``price_basis`` object on ``concepts.schema.json``
    (v1.2): ``basis`` is the current/constant discriminator, ``base_year`` is
    the constant-price reference year (null for current prices, which have no
    fixed base). A constant-price UPSERT into a current-price cell is a
    category error the Enrich price-basis gate refuses (Row 6).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    basis: Literal["current", "constant"]
    base_year: int | None = Field(default=None, ge=1850, le=2100)


class IndicatorSpec(BaseModel):
    """CHILD spec: one indicator a source feeds. Indicator-level fields only.

    ``indicator_id`` FKs ``datasets/taxonomy/indicators.json`` at
    registration; the ``(unit, normalisation, price_basis, sampling_frame)``
    tuple MUST match the concept resolved via ``indicator.concept_id`` ->
    ``concepts.json`` (both checks live in ``catalogue_fk``). ``price_basis``
    / ``sampling_frame`` are null for the physical-quantity / count concepts
    that dominate the corpus; non-null only for monetary (``price_basis``) and
    frame-bounded survey/register (``sampling_frame``) concepts.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    indicator_id: str = Field(pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", max_length=60)
    unit: str = Field(min_length=1)
    normalisation: Normalisation
    price_basis: PriceBasis | None = None
    sampling_frame: str | None = Field(default=None, min_length=1)


class SourceSpec(BaseModel):
    """PARENT spec: one upstream source + the indicators it feeds.

    Source-level identity only (adapter + provenance). ``indicators`` is the
    non-empty tuple of child :class:`IndicatorSpec` rows. ``source_id`` is a
    DERIVED property (never a stored field) so it cannot drift from the
    provenance triple.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_slug: str = Field(pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
    producer: str = Field(min_length=1)
    title: str = Field(min_length=1)
    vintage: str = Field(min_length=1)
    url: str | None = Field(default=None)
    indicators: tuple[IndicatorSpec, ...] = Field(min_length=1)

    @property
    def source_id(self) -> str:
        """Derived citation id from ``(producer, title, vintage)``.

        Computed, never stored, so it cannot drift from the provenance triple
        (the single-source-of-truth split, see module docstring).
        """
        return derive_source_id(self.producer, self.title, self.vintage)
