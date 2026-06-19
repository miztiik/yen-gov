"""ICED power-sector adapter — fetch + emit four energy indicator artifacts.

This adapter ships the long-history per-state capacity time series and
the one-year snapshot of actual generation + peak demand that NITI's
ICED publishes. Together with the existing CEA single-month snapshot
they fill yen-gov's biggest gap on the energy side: per-state per-fuel
capacity *over time*.

The legacy network-fetch + folded-indicator-JSON orchestrator
(``ingest_iced_power`` + ``IngestSummary``) was retired in B4-pt2.1 per
parent plan section 21.4. The B1.4.5 canonical CSV emission stays under
``.ingest`` (exercised by ``backend/tests/test_iced_power_csv_repoint.py``).
"""
from __future__ import annotations

from .ingest import IndicatorEmitResult

__all__ = [
    "IndicatorEmitResult",
]
