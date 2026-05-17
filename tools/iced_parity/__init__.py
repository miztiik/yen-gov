"""ICED value-parity oracle.

Operator-driven CLI + module (NOT in pytest, NOT in backend/, NOT in
admin/) per Phase 2 of TODO/20260517-iced-bulk-ingest-and-parity-oracle.md.

Step 6 lands the pure-function substrate:
  - models.py     dataclass for one ledger record (ParityObservation)
  - classify.py   pure status classifier (six-value enum)
  - sample.py     pure cell-sampling strategies over an indicator artifact
  - ledger.py     append-only JSONL read/append and aggregate roll-up
  - banner.py     pure summariser that builds the `upstream_parity`
                  object spliced into the indicator artifact's
                  `divergence` slot (wired in step 7)
  - probe.py      protocol-only fetcher boundary; live HTTP wiring is
                  step 7 (kept out of step 6 so unit tests stay pure)

All public symbols are re-exported here for the convenience of callers.
"""

from .banner import summarise
from .classify import (
    DEFAULT_ABS_TOLERANCE,
    DEFAULT_REL_TOLERANCE,
    classify,
)
from .ledger import append, last_upstream_value, ledger_path, read_lines
from .models import STATUS_VALUES, ParityObservation, Status
from .probe import UpstreamFetcher
from .sample import Cell, all_cells, stratified_sample

__all__ = [
    "Cell",
    "DEFAULT_ABS_TOLERANCE",
    "DEFAULT_REL_TOLERANCE",
    "ParityObservation",
    "STATUS_VALUES",
    "Status",
    "UpstreamFetcher",
    "all_cells",
    "append",
    "classify",
    "last_upstream_value",
    "ledger_path",
    "read_lines",
    "stratified_sample",
    "summarise",
]
