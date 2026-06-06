"""Adapter for the ICED v1 ``*-metatable-data`` endpoint family.

Three sibling endpoints share the same per-state-per-source-per-FY shape and
ship as plain JSON (no AES envelope — call with ``decrypt=False``):

- ``/v1/gen-metatable-data``           — generation in MU (= GWh) per fuel.
- ``/v1/plf-metatable-data``           — Plant Load Factor (%) per fuel.
- ``/v1/co-emission-metatable-data``   — plant-unit-level CO2 (MtCO2/yr),
  aggregated here to state × year × source.

The legacy network-fetch + folded-indicator-JSON orchestrator
(``ingest_iced_metatable`` + ``IngestSummary``) was retired in B4-pt2.1
per parent plan section 21.4. The B1.4.4 canonical CSV emission stays
under ``.ingest`` (exercised by ``backend/tests/test_iced_metatable_csv_repoint.py``).
"""

from .ingest import IndicatorEmitResult

__all__ = ["IndicatorEmitResult"]
