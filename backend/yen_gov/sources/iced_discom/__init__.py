"""Adapter for the ICED v0 DISCOM (electricity-distribution) endpoint family.

Two sibling v0 AES-encrypted endpoints expose state-level distribution
operational performance and renewable purchase obligation (RPO) compliance:

- ``/energy/electricity/distribution/operationalPerformanceStates``
  -- per-state, per-FY, per-category operational metrics
  (T&D loss, AT&C loss, billing efficiency, collection efficiency).
- ``/energy/electricity/distribution/rpo``
  -- per-state, per-FY RPO targets and compliance (solar, non-solar, total).

Both were discovered/confirmed by the 2026-05-15 ICED full-triage sweep
(see ``.runtime/iced_recon/full_triage_20260515073024.md``) and reconned
directly via ``tools/iced_discom_recon.py``.
"""

from .ingest import IngestSummary, ingest_iced_discom

__all__ = ["IngestSummary", "ingest_iced_discom"]
