"""ICED macro adapter — national/state GDP, IIP.

Emits two indicator artifacts:

  * economy/gdp_inr_crore (entity_kinds=[country, state] — country + per-state GSDP rows in one shard, PR-B6-row9)
  * economy/iip_index

The legacy network-fetch + folded-indicator-JSON orchestrator
(``ingest_iced_macro`` + ``IngestSummary``) was retired in B4-pt2.1 per
parent plan section 21.4. The B1.4.2 canonical CSV emission stays under
``.ingest`` (exercised by ``backend/tests/test_iced_macro_csv_repoint.py``).
"""
from __future__ import annotations

from .ingest import IndicatorEmitResult
from .parsers import (
    GDPParseResult,
    parse_gdp_trend,
    parse_industrial_production,
)

__all__ = (
    "IndicatorEmitResult",
    "GDPParseResult",
    "parse_gdp_trend",
    "parse_industrial_production",
)
