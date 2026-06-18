"""Reusable ingest for the ICED captive-power (industry-wise) feed.

NITI Aayog's India Climate & Energy Dashboard (ICED) republishes the Central
Electricity Authority's captive-power returns as a single AES-encrypted JSON
feed. This package turns it into two canonical long-format CSV indicators -
state totals of captive (behind-the-meter, industry self-generation) capacity
(MW) and generation (GWh) - by summing over the feed's 22 industry categories.

Pipeline:

    registry.CaptivePowerSpec  ->  parser.parse_captive_feed
                               ->  rbi_handbook.build_state_resolver
                               ->  ingest.ingest  (emit datapoints +
                                   upsert variables/concepts/source)

Captive power is self-generation, NOT grid supply, and is self-reported to the
CEA and widely under-reported - see each spec's ``concept_description`` and the
frontend caveats. A high captive total is ambiguous (industrial strength, or a
symptom of an unreliable / costly public grid), so the indicators are
``direction: neutral``.
"""
from __future__ import annotations

from .ingest import IngestResult, IngestedIndicator, ingest
from .parser import (
    CaptiveDropReport,
    CaptivePowerShapeError,
    CaptivePowerSpec,
    CaptiveRow,
    parse_captive_feed,
)
from .registry import SHIPPED_SPECS, spec_by_indicator_id

__all__ = [
    "CaptiveDropReport",
    "CaptivePowerShapeError",
    "CaptivePowerSpec",
    "CaptiveRow",
    "IngestResult",
    "IngestedIndicator",
    "SHIPPED_SPECS",
    "ingest",
    "parse_captive_feed",
    "spec_by_indicator_id",
]
