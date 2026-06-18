"""Reusable ingest for the ICED transmission-substation list feed.

NITI Aayog's India Climate & Energy Dashboard (ICED) publishes the national
transmission-substation asset inventory as an AES-encrypted JSON feed (one
element per commissioned substation). This package turns it into the canonical
long-format CSV store as ONE faceted indicator.

Pipeline:

    registry.SHIPPED_SPEC  ->  parser.parse_substation_feed
                           ->  ingest.ingest  (emit geo_by_voltage datapoints +
                               upsert variables/concepts/source)

The feed carries NO state field, so this is a NATIONAL series
(``entity_id = "IN"``); the analytical detail lives on the ``voltage_class``
facet axis - the summed substation capacity (MVA) commissioned per fiscal year
by voltage tier (hvdc / 765kv / 400kv / 220kv / other). A grid build-out
indicator, NOT installed generation capacity and NOT a per-state ranking - see
the spec's ``concept_description``.
"""
from __future__ import annotations

from .ingest import IngestResult, ingest
from .parser import (
    ParseStats,
    SubstationFacetRow,
    TransmissionSubstationShapeError,
    TransmissionSubstationSpec,
    VOLTAGE_CLASSES,
    classify_voltage_class,
    parse_substation_feed,
)
from .registry import SHIPPED_SPEC

__all__ = [
    "IngestResult",
    "ParseStats",
    "SHIPPED_SPEC",
    "SubstationFacetRow",
    "TransmissionSubstationShapeError",
    "TransmissionSubstationSpec",
    "VOLTAGE_CLASSES",
    "classify_voltage_class",
    "ingest",
    "parse_substation_feed",
]
