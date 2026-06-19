"""Adapter for the ICED v0 DISCOM (electricity-distribution) endpoint family.

Two sibling v0 AES-encrypted endpoints expose state-level distribution
operational performance and renewable purchase obligation (RPO) compliance:

- ``/energy/electricity/distribution/operationalPerformanceStates``
  -- per-state, per-FY, per-category operational metrics
  (T&D loss, AT&C loss, billing efficiency, collection efficiency).
- ``/energy/electricity/distribution/rpo``
  -- per-state, per-FY RPO targets and compliance (solar, non-solar, total).

The legacy network-fetch + folded-indicator-JSON orchestrator
(``ingest_iced_discom`` + ``IngestSummary``) was retired in B4-pt2.1
per parent plan section 21.4. The B1.4.7 canonical CSV emission stays
under ``.ingest`` (exercised by ``backend/tests/test_iced_discom_csv_repoint.py``).
"""

from .ingest import IndicatorEmitResult

__all__ = ["IndicatorEmitResult"]
