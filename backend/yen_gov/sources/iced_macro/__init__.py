"""ICED macro adapter — national/state GDP, IIP.

Emits two indicator artifacts:

  * economy/gdp_inr_crore (entity_kinds=[country, state] — country + per-state GSDP rows in one shard, PR-B6-row9)
  * economy/iip_index

(`demography/state_population_by_residence_count` was retired in PR-D4 —
Census 2011 was the last completed enumeration and the 2021 round was
postponed; six decennial points was a position not a trajectory, and no
canonical successor is planned.)
"""
from __future__ import annotations

from .ingest import IndicatorEmitResult, IngestSummary, ingest_iced_macro
from .parsers import (
    GDPParseResult,
    parse_gdp_trend,
    parse_industrial_production,
)

__all__ = (
    "IndicatorEmitResult",
    "IngestSummary",
    "ingest_iced_macro",
    "GDPParseResult",
    "parse_gdp_trend",
    "parse_industrial_production",
)
