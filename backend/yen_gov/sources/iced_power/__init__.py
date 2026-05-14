"""ICED power-sector adapter — fetch + emit five energy indicator artifacts.

This adapter ships the long-history per-state capacity time series and
the one-year snapshot of actual generation + peak demand that NITI's
ICED publishes. Together with the existing CEA single-month snapshot
they fill yen-gov's biggest gap on the energy side: per-state per-fuel
capacity *over time*.

Indicators emitted (all five all-states where the upstream supports it):

* ``energy/state_installed_capacity_by_source_mw``
  — per-state per-source capacity, FY2015-16 → FY2025-26, faceted by source.
* ``energy/state_electricity_generation_by_source_gwh``
  — per-state per-source actual generation (snapshot, FY2025-26).
* ``energy/state_peak_electricity_demand_mw``
  — per-state peak electricity demand (snapshot, FY2025-26).
* ``energy/india_thermal_capacity_retired_mw``
  — national thermal capacity retired by year × fuel source, FY2005-06 →.
* ``energy/india_capacity_pipeline_gw``
  — national under-construction capacity pipeline, 2011 → 2031, by status.

The orchestrator at :mod:`.ingest` does the network and persistence.
Pure parsers in :mod:`.parsers` consume already-decrypted (or already-
JSON-parsed) ICED responses and return canonical row dicts.
"""
from __future__ import annotations

from .ingest import (
    IndicatorEmitResult,
    IngestSummary,
    ingest_iced_power,
)

__all__ = [
    "IndicatorEmitResult",
    "IngestSummary",
    "ingest_iced_power",
]
