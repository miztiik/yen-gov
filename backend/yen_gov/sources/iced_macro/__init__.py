"""ICED macro adapter — national/state GDP, IIP, census population.

Emits four indicator artifacts:

  * economy/india_gdp_inr_crore
  * economy/state_gdp_inr_crore
  * economy/india_iip_index_2011_12
  * demography/state_population_by_residence_count
"""
from __future__ import annotations

from .ingest import IndicatorEmitResult, IngestSummary, ingest_iced_macro
from .parsers import (
    GDPParseResult,
    parse_gdp_trend,
    parse_industrial_production,
    parse_population_by_residence,
)

__all__ = (
    "IndicatorEmitResult",
    "IngestSummary",
    "ingest_iced_macro",
    "GDPParseResult",
    "parse_gdp_trend",
    "parse_industrial_production",
    "parse_population_by_residence",
)
