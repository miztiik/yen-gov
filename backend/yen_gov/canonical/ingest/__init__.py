"""The ``ingest`` engine -- a sibling to ``canonical/adapters`` (plan section 3).

Row 1 ships the foundational, author-time surface:

* ``messages`` -- the three pydantic stage messages (``ClaimCheck``,
  ``RawRecord``, ``CanonicalBatch``) + ``ReplacementSemantics`` (plan D3).
* ``spec`` -- the parent ``SourceSpec`` + child ``IndicatorSpec`` (no field
  repeated across levels) + ``PriceBasis``.
* ``catalogue_fk`` -- the registration-time FK + concept-compatibility
  checks that keep the pipeline from minting identity.

Row 4 adds the orchestrator, the adapter registry + derived index, and the
``ingest`` CLI sub-app. Later rows add fetch (Row 5) and the enrich/publish
honesty gates (Row 6).
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
from yen_gov.canonical.ingest.orchestrator import (
    IndicatorStatus,
    IngestError,
    IngestUsageError,
    OrchestrateResult,
    RegistryConsistencyError,
    SourceCoverage,
    build_indicator_index,
    compute_status,
    orchestrate,
)
from yen_gov.canonical.ingest.registry import (
    Adapter,
    AdapterRunResult,
    IngestConfigError,
    OrchestrateConfig,
    RbiHandbookAdapter,
    default_registry,
)
from yen_gov.canonical.ingest.spec import IndicatorSpec, PriceBasis, SourceSpec

__all__ = [
    "Adapter",
    "AdapterRunResult",
    "CanonicalBatch",
    "CanonicalObservationRow",
    "CanonicalSourceRow",
    "CatalogueError",
    "CatalogueFkError",
    "ClaimCheck",
    "ConceptCompatibilityError",
    "IndicatorSpec",
    "IndicatorStatus",
    "IngestConfigError",
    "IngestError",
    "IngestUsageError",
    "OrchestrateConfig",
    "OrchestrateResult",
    "PriceBasis",
    "RawRecord",
    "RbiHandbookAdapter",
    "RegistryConsistencyError",
    "ReplacementSemantics",
    "SourceCoverage",
    "SourceSpec",
    "build_indicator_index",
    "check_indicator_registration",
    "compute_status",
    "default_registry",
    "orchestrate",
]
