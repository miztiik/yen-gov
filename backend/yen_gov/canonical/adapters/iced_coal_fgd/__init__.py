"""Net-new ingest for the ICED coal-plant FGD air-quality feed.

NITI Aayog's India Climate & Energy Dashboard (ICED) publishes a coal-plant
air-quality-impact inventory (one row per generating unit, with coordinates
and FGD-retrofit status) as an AES-encrypted JSON feed. This package turns it
into a single state-grain canonical indicator -
``coal-capacity-fgd-share-pct``: the share of each state's OPERATING coal
capacity fitted with FGD (flue-gas desulphurisation / SO2 scrubbers).

Pipeline:

    parser.parse_coal_units    ->  geocode.StateGeocoder (point-in-polygon
                                    coordinate -> LGD state)
                               ->  ingest.ingest (per-state share, emit
                                    datapoints + upsert variables/concepts/
                                    source)

This is a geocode-derived (major-processing) statistic, and a SNAPSHOT (FGD
status is current, not a time series) stamped at one assessment year - see
``registry.SHIPPED_SPEC`` and ``ingest.GeocodeReport``.
"""
from __future__ import annotations

from .geocode import GeoMatch, GeocoderError, StateGeocoder
from .ingest import (
    CoalFgdGeocodeError,
    CoalFgdIngestResult,
    GeocodeReport,
    ingest,
)
from .parser import (
    CoalFgdShapeError,
    CoalUnit,
    ParseReport,
    parse_coal_units,
)
from .registry import ASSESSMENT_YEAR, SHIPPED_SPEC, CoalFgdSpec

__all__ = [
    "ASSESSMENT_YEAR",
    "CoalFgdGeocodeError",
    "CoalFgdIngestResult",
    "CoalFgdShapeError",
    "CoalFgdSpec",
    "CoalUnit",
    "GeoMatch",
    "GeocodeReport",
    "GeocoderError",
    "ParseReport",
    "SHIPPED_SPEC",
    "StateGeocoder",
    "ingest",
    "parse_coal_units",
]
