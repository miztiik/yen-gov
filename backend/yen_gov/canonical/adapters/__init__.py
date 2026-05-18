"""Adapter modules — translate per-source data into BatchEnvelope.

Per docs/architecture/data/canonical-store.md §14 (write path):

    source adapter (here)
        | uses existing parsers from yen_gov.sources.*
        | produces ObservationRow[] + SourceRow[]
        v
    BatchEnvelope (yen_gov.canonical.envelope)
        v
    write_batch (yen_gov.canonical.writer)

Adapters are the ONLY place that knows source-shape semantics. The writer is
fully agnostic — it sees rows, not pages. Per Fowler (engineering craft) +
Gregor (contracts before logic): adapters depend on the canonical envelope,
the canonical envelope does not know adapters exist.
"""
