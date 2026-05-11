"""RBI State Finances XLSX adapter.

Pure-parser package. Exposes:

  - parse_state_finances_workbook(xlsx_bytes) -> ParsedFiscals
  - ingest(...) — orchestrator that fetches, parses, writes 8 indicator
    artifacts under datasets/indicators/in/fiscal/.
  - urls (registry of known-good RBI URLs from recon).

See docs/architecture/backend/sources-rbi.md for the design contract.
"""
from .parsers import (
    INDICATOR_SPECS,
    IndicatorSpec,
    ParsedFiscals,
    ParsedRow,
    parse_state_finances_workbook,
)

__all__ = [
    "INDICATOR_SPECS",
    "IndicatorSpec",
    "ParsedFiscals",
    "ParsedRow",
    "parse_state_finances_workbook",
]
