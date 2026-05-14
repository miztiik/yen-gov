"""ICED GHG sub-sector adapter (NITI Aayog, India BUR/UNFCCC).

Emits one indicator artifact:

  * environment/india_ghg_emissions_by_subsector_ggco2e
"""
from __future__ import annotations

from .ingest import IndicatorEmitResult, IngestSummary, ingest_iced_ghg
from .parsers import parse_ghg_subsector

__all__ = (
    "IndicatorEmitResult",
    "IngestSummary",
    "ingest_iced_ghg",
    "parse_ghg_subsector",
)
