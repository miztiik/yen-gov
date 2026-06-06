"""ICED socio-economic adapter: per-capita income (constant), HDI, per-capita
consumption, population-by-sex, national GHG emissions by sector.

The legacy network-fetch + folded-indicator-JSON orchestrator
(``ingest_iced_socio`` + ``IngestSummary``) was retired in B4-pt2.1 per
parent plan section 21.4. The B1.4.6 canonical CSV emission stays under
``.ingest`` (exercised by ``backend/tests/test_iced_socio_csv_repoint.py``).
"""
from .ingest import IndicatorEmitResult

__all__ = ("IndicatorEmitResult",)
