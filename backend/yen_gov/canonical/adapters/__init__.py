"""Adapter modules — translate per-source data into canonical CSV rows.

Per docs/architecture/data/canonical-store.md §14 (write path), post the
ingest rip-replace (Row 9 deleted the ``BatchEnvelope`` -> ``write_batch``
Parquet seam):

    source adapter (here)
        | uses existing parsers from yen_gov.canonical.adapters.*
        | produces ObservationRow[] + SourceRow[] (canonical/row_models.py)
        v
    canonical CSV write seam
        | eci.electoral_csv.write_electoral_results / upsert_source_csv
        | (long-format CSV under datasets/data/)

Adapters are the ONLY place that knows source-shape semantics. Per Fowler
(engineering craft) + Gregor (contracts before logic): adapters depend on the
canonical row models + the CSV write seam, which do not know adapters exist.
"""
