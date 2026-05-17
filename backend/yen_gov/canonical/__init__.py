"""Canonical long-format store — write seam.

Per ADR-0030 + docs/architecture/data/canonical-store.md.

Public surface:

    from yen_gov.canonical import BatchEnvelope, write_batch

The writer is the SOLE producer of datasets/<family>/*.parquet,
datasets/taxonomy/*.parquet, and datasets/manifest.json.

D34: module layout pinned — writer.py, reader.py (frontend mirror), migration/,
registry.py. No consolidator.py.
"""

from __future__ import annotations

from yen_gov.canonical.envelope import (
    BatchEnvelope,
    ObservationRow,
    ReplacementSemantics,
    SourceRow,
)
from yen_gov.canonical.writer import WriteResult, write_batch

__all__ = [
    "BatchEnvelope",
    "ObservationRow",
    "ReplacementSemantics",
    "SourceRow",
    "WriteResult",
    "write_batch",
]
