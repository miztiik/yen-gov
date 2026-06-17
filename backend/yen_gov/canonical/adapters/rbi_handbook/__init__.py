"""Reusable ingest for RBI Handbook of Statistics on Indian States tables.

The Reserve Bank of India republishes a large set of ``state x period``
tables (Social and Demographic Indicators, State Domestic Product,
Fiscal, Banking, Agriculture, Prices, ...) as one XLSX per table. This
package turns any such table into the canonical long-format CSV store
with a single per-table spec - no per-table parser code.

Pipeline:

    registry.HbsTableSpec  ->  parser.parse_hbs_workbook
                           ->  resolver.build_state_resolver
                           ->  ingest.ingest  (emit datapoints + catalogue)

Provenance follows Holy Law #9 + the Hans + Max verdict: RBI is the
machine-readable access surface, the issuing authority (SRS / ORGI /
Census) is the ``producer``.
"""
from __future__ import annotations

from .ingest import IngestedTable, IngestResult, ingest
from .parser import (
    TIME_CALENDAR_YEAR,
    TIME_INTERVAL_WINDOW_END,
    HbsTableSpec,
    LongRow,
    RbiHbsShapeError,
    parse_hbs_workbook,
)
from .registry import SHIPPED_SPECS, spec_by_indicator_id
from .resolver import (
    COUNTRY_ENTITY_ID,
    StateResolver,
    build_state_resolver,
    normalise_label,
)

__all__ = [
    "COUNTRY_ENTITY_ID",
    "HbsTableSpec",
    "IngestResult",
    "IngestedTable",
    "LongRow",
    "RbiHbsShapeError",
    "SHIPPED_SPECS",
    "StateResolver",
    "TIME_CALENDAR_YEAR",
    "TIME_INTERVAL_WINDOW_END",
    "build_state_resolver",
    "ingest",
    "normalise_label",
    "parse_hbs_workbook",
    "spec_by_indicator_id",
]
