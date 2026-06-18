"""Reusable ingest for ICED renewable-energy potential feeds.

NITI Aayog's India Climate & Energy Dashboard (ICED) publishes modelled
state-wise renewable potential (solar, wind, bio-energy) as AES-encrypted
JSON feeds. This package turns each feed into the canonical long-format CSV
store with a single per-feed spec - no per-feed parser code.

Pipeline:

    registry.RenewablePotentialSpec  ->  parser.parse_potential_feed
                                     ->  rbi_handbook.build_state_resolver
                                     ->  ingest.ingest  (emit datapoints +
                                         upsert variables/concepts/source)

These are MODELLED maximum-buildable-potential series (geography-driven, a
single assessment-year snapshot), NOT installed capacity and NOT a
performance ranking - see each spec's ``concept_description``.
"""
from __future__ import annotations

from .ingest import IngestedFeed, IngestResult, ingest
from .parser import (
    PotentialRow,
    RenewablePotentialShapeError,
    RenewablePotentialSpec,
    parse_potential_feed,
)
from .registry import SHIPPED_SPECS, spec_by_indicator_id

__all__ = [
    "IngestResult",
    "IngestedFeed",
    "PotentialRow",
    "RenewablePotentialShapeError",
    "RenewablePotentialSpec",
    "SHIPPED_SPECS",
    "ingest",
    "parse_potential_feed",
    "spec_by_indicator_id",
]
