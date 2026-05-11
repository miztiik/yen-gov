"""RBI State Finances XLSX adapter.

Layout-driven, fail-loud parser + orchestrator that turns RBI's
per-Statement workbooks into indicator-schema artifacts under
``datasets/indicators/in/fiscal/``.

Public surface:

  - :class:`IndicatorSpec` — declares one indicator's location inside
    one workbook.
  - :data:`SHIPPED_SPECS` — the indicators currently published.
  - :func:`parse_workbook` — pure parser; takes XLSX bytes + spec,
    returns parsed rows.
  - :func:`ingest` — orchestrator (network + filesystem boundary).

See ``docs/architecture/backend/sources-rbi.md`` for the design
contract and the per-Statement → indicator mapping.
"""
from .parsers import (
    SHIPPED_SPECS,
    IndicatorSpec,
    ParsedIndicator,
    ParsedRow,
    RBIWorkbookShapeError,
    normalise_state_label,
    parse_workbook,
)

__all__ = [
    "SHIPPED_SPECS",
    "IndicatorSpec",
    "ParsedIndicator",
    "ParsedRow",
    "RBIWorkbookShapeError",
    "normalise_state_label",
    "parse_workbook",
]
