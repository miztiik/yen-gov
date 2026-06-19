"""The ``ingest`` engine -- a sibling to ``canonical/adapters`` (plan section 3).

Row 1 ships the foundational, author-time surface:

* ``messages`` -- the three pydantic stage messages (``ClaimCheck``,
  ``RawRecord``, ``CanonicalBatch``) + ``ReplacementSemantics`` (plan D3).
* ``spec`` -- the parent ``SourceSpec`` + child ``IndicatorSpec`` (no field
  repeated across levels) + ``PriceBasis``.
* ``catalogue_fk`` -- the registration-time FK + concept-compatibility
  checks that keep the pipeline from minting identity.

Later rows add the orchestrator, registry, derived index, fetch, the
enrich/publish honesty gates, and the ``ingest`` CLI.
"""

from __future__ import annotations

from yen_gov.canonical.ingest.catalogue_fk import (
    CatalogueError,
    CatalogueFkError,
    ConceptCompatibilityError,
    check_indicator_registration,
)
from yen_gov.canonical.ingest.messages import (
    CanonicalBatch,
    CanonicalObservationRow,
    CanonicalSourceRow,
    ClaimCheck,
    RawRecord,
    ReplacementSemantics,
)
from yen_gov.canonical.ingest.spec import IndicatorSpec, PriceBasis, SourceSpec

__all__ = [
    "CanonicalBatch",
    "CanonicalObservationRow",
    "CanonicalSourceRow",
    "CatalogueError",
    "CatalogueFkError",
    "ClaimCheck",
    "ConceptCompatibilityError",
    "IndicatorSpec",
    "PriceBasis",
    "RawRecord",
    "ReplacementSemantics",
    "SourceSpec",
    "check_indicator_registration",
]
