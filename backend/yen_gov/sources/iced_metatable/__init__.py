"""Adapter for the ICED v1 ``*-metatable-data`` endpoint family.

Three sibling endpoints share the same per-state-per-source-per-FY shape and
ship as plain JSON (no AES envelope — call with ``decrypt=False``):

- ``/v1/gen-metatable-data``           — generation in MU (= GWh) per fuel.
- ``/v1/plf-metatable-data``           — Plant Load Factor (%) per fuel.
- ``/v1/co-emission-metatable-data``   — plant-unit-level CO2 (MtCO2/yr),
  aggregated here to state × year × source.

All three were discovered by the 2026-05-15 ICED full-triage sweep
(see ``.runtime/iced_recon/full_triage_20260515073024.md``).
"""

from .ingest import IngestSummary, ingest_iced_metatable

__all__ = ["IngestSummary", "ingest_iced_metatable"]
