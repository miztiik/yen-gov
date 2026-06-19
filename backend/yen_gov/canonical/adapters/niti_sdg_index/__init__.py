"""NITI Aayog SDG India Index ingest (greenfield single-series source, Row 11)."""
from __future__ import annotations

from .ingest import (
    SHIPPED_SPEC,
    IngestResult,
    IngestedTable,
    NitiSdgIndexAdapter,
    ingest,
    spec_by_indicator_id,
)
from .parser import SdgIndexSpec, SdgParseError, parse_sdg_index_csv

__all__ = [
    "SHIPPED_SPEC",
    "IngestResult",
    "IngestedTable",
    "NitiSdgIndexAdapter",
    "SdgIndexSpec",
    "SdgParseError",
    "ingest",
    "parse_sdg_index_csv",
    "spec_by_indicator_id",
]
