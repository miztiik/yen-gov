"""Canonical long-format store.

Per ADR-0030 + docs/architecture/data/canonical-store.md.

The Parquet-era ``BatchEnvelope`` -> ``write_batch`` write seam (``envelope.py``
+ ``writer.py``) was deleted in the ingest rip-replace (Row 9). The canonical
store is now long-format CSV under ``datasets/data/``. The current homes:

* ``canonical/ingest/messages.py`` -- the long-format-CSV pipeline stage
  messages (Fetch -> Enrich -> Publish).
* ``canonical/csv_writer.py`` + ``canonical/csv_columns.py`` -- the typed CSV
  write boundary + per-file column contract.
* ``canonical/adapters/eci/electoral_csv.py`` -- the per-state electoral CSV
  write seam; ``canonical/row_models.py`` -- the legacy row DTOs the ECI
  electoral adapters + citation seeds still build.

The package no longer re-exports row types or a writer; import them from the
submodule that owns them.
"""
