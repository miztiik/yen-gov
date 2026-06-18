"""Reusable ingest for the ICED ICE-vs-EV (VAHAN) registrations feed.

NITI Aayog's India Climate & Energy Dashboard (ICED) republishes MoRTH VAHAN
new-registration counts split by state x vehicle-category x fuel-category x
fiscal-year as an AES-encrypted JSON feed. This package turns that feed into
ONE canonical long-format CSV indicator - the state EV SHARE of new vehicle
registrations (%) - with a single spec, no per-feed parser code.

Pipeline:

    registry.EvShareSpec  ->  parser.parse_ev_share_feed
                          ->  rbi_handbook.build_state_resolver
                          ->  ingest.ingest  (emit datapoints + upsert
                              variables/concepts/source)

The emitted indicator is a derived SHARE (Hans verdict: a share, not an
absolute EV count, is the cross-state-comparable transition signal). The
feed's ``populationData`` block is dropped entirely (yen-gov already carries
state population; a second population source is forbidden).
"""
from __future__ import annotations

from .ingest import IngestedFeed, IngestResult, ingest
from .parser import (
    EvShareRow,
    EvShareShapeError,
    EvShareSpec,
    parse_ev_share_feed,
)
from .registry import SHIPPED_SPECS, spec_by_indicator_id

__all__ = [
    "EvShareRow",
    "EvShareShapeError",
    "EvShareSpec",
    "IngestResult",
    "IngestedFeed",
    "SHIPPED_SPECS",
    "ingest",
    "parse_ev_share_feed",
    "spec_by_indicator_id",
]
