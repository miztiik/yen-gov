"""ICED coal-FGD - feed spec (catalogue rows + provenance + snapshot year).

A single :class:`CoalFgdSpec` carries everything the downstream surfaces
need: the citizen-facing catalogue rows (``variables.csv`` + ``concepts.csv``),
the citation triple (``source.csv``), and the staging filename. The
classification constants (which ``fgdGroup`` means installed, which
``commissioningGroup`` means operating) live in :mod:`.parser`; the spec only
names identity, provenance, and the assessment snapshot year.
"""
from __future__ import annotations

from dataclasses import dataclass

from yen_gov.canonical.iced_authority_map import ICED_ORG_PRODUCER

__all__ = ["CoalFgdSpec", "SHIPPED_SPEC", "ASSESSMENT_YEAR"]

# The FGD-retrofit status is a CURRENT snapshot (the feed carries no
# assessment-year field per row), so the whole series is stamped with one
# integer ``time`` = the year the snapshot was assessed into the corpus. This
# is deliberately distinct from the source-citation ``vintage`` (the API
# edition tag) below: the vintage cites the publisher edition the snapshot was
# pulled from; the assessment year stamps when we recorded the status.
ASSESSMENT_YEAR = 2026

# D2 (ingest plan Row 10): ICED is not a product-name producer. This endpoint
# is a yen-gov geocode-derived (major-processing) statistic kept under the
# org-led label NITI Aayog ICED (iced_authority_map decision src-85c67674901f).
_ICED_PRODUCER = ICED_ORG_PRODUCER
_ICED_URL = "https://iced.niti.gov.in"


@dataclass(frozen=True)
class CoalFgdSpec:
    """The one ICED coal-FGD feed -> one canonical state-grain indicator."""

    # --- identity / output (variables.csv + concepts.csv) ---
    indicator_id: str
    name: str
    concept_id: str
    concept_noun: str
    concept_description: str
    unit: str
    unit_canonical: str
    normalisation: str          # concepts.csv enum (here: "share")
    topic: str
    entity_kinds: str
    update_period_days: int
    derivation: str

    # --- provenance (source.csv; source_id is DERIVED, never set) ---
    source_producer: str
    source_title: str
    source_vintage: str
    source_url: str

    # --- staging ---
    staging_filename: str


SHIPPED_SPEC = CoalFgdSpec(
    indicator_id="coal-capacity-fgd-share-pct",
    name="Operating coal capacity fitted with FGD (SO2 scrubbers)",
    concept_id="coal-fgd-compliance-share",
    concept_noun="Coal FGD compliance share",
    concept_description=(
        "Share (%) of a state's OPERATING coal-power capacity fitted with FGD "
        "(flue-gas desulphurisation / SO2 scrubbers) - an air-quality "
        "enforcement metric tracking how much of the running coal fleet meets "
        "the SO2-emission norm. Each plant is geocoded to its state by "
        "coordinates (point-in-polygon against the LGD state boundaries); the "
        "numerator counts operating units whose FGD is installed, the "
        "denominator all operating coal units. A geocode-derived (major-"
        "processing) statistic."
    ),
    unit="%",
    unit_canonical="%",
    normalisation="share",
    topic="energy",
    entity_kinds="state",
    update_period_days=365,
    derivation=(
        "Each coal unit geocoded to its state by point-in-polygon over the LGD "
        "state boundaries (datasets/boundaries/in/states/all.geojson; "
        "ray-casting, with a bounded coastal-boundary snap for plants just "
        "outside the simplified coastline). Per state, share = 100 x (sum "
        "capacity of operating coal units with FGD installed) / (sum capacity "
        "of all operating coal units). Operating = commissioningGroup "
        "'operational'; FGD installed = fgdGroup 'FGD installed'."
    ),
    source_producer=_ICED_PRODUCER,
    source_title="Coal Plant AQI Impact List API",
    source_vintage="2024-25",
    source_url=_ICED_URL,
    staging_filename="aq_coal_plant_impact.json",
)
