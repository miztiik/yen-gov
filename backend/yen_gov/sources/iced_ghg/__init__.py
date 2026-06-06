"""ICED GHG sub-sector adapter (NITI Aayog, India BUR/UNFCCC).

The legacy network-fetch + folded-indicator-JSON orchestrator
(``ingest_iced_ghg`` + ``IngestSummary``) was retired in B4-pt2.1 per
parent plan section 21.4. The B1.4.1 canonical CSV emission stays under
``.ingest`` (exercised by ``backend/tests/test_iced_ghg_csv_repoint.py``).
"""
from __future__ import annotations

from .ingest import IndicatorEmitResult
from .parsers import parse_ghg_subsector

__all__ = (
    "IndicatorEmitResult",
    "parse_ghg_subsector",
)
