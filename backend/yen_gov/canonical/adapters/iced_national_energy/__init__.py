"""ICED national energy-balance ingest (primary supply + final consumption).

NITI Aayog's India Climate & Energy Dashboard (ICED) publishes India's national
energy balance as two AES-encrypted JSON feeds: Source-wise Energy Supply (Total
Primary Energy Supply by source) and Sector-wise Energy Consumption (final
consumption by sector x fuel). This package turns each into the canonical
long-format faceted CSV store:

    registry.{PRIMARY,FINAL}_ENERGY_SPEC  ->  parser.parse_*
                                          ->  ingest.ingest_{primary,final}
                                              (emit faceted datapoints +
                                              upsert variables/concepts/source)

Both are NATIONAL series (entity_id ``IN``), fiscal-year, in mtoe. Primary
supply faceted by primary_source (geo_by_primary_source); final consumption
faceted by sector AND fuel (geo_by_sector_fuel - the first two-axis class).
"""
from __future__ import annotations

from .ingest import IngestResult, ingest_final, ingest_primary
from .parser import (
    FinalConsumptionRow,
    FinalEnergySpec,
    NationalEnergyShapeError,
    PrimaryEnergySpec,
    PrimarySupplyRow,
    parse_sector_wise_consumption,
    parse_source_wise_supply,
)
from .registry import FINAL_ENERGY_SPEC, PRIMARY_ENERGY_SPEC

__all__ = [
    "FINAL_ENERGY_SPEC",
    "FinalConsumptionRow",
    "FinalEnergySpec",
    "IngestResult",
    "NationalEnergyShapeError",
    "PRIMARY_ENERGY_SPEC",
    "PrimaryEnergySpec",
    "PrimarySupplyRow",
    "ingest_final",
    "ingest_primary",
    "parse_sector_wise_consumption",
    "parse_source_wise_supply",
]
