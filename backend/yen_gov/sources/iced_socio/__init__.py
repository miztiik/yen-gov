"""ICED socio-economic adapter: per-capita income (constant), HDI, per-capita
consumption, population-by-sex, national GHG emissions by sector.

Five indicators across four topics. See ``ingest.py`` for the full list
and the per-indicator metadata; see ``parsers.py`` for the pure
extraction functions.
"""
from .ingest import (
    ingest_iced_socio,
    IngestSummary,
    IndicatorEmitResult,
)

__all__ = ("ingest_iced_socio", "IngestSummary", "IndicatorEmitResult")
