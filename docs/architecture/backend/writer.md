# Canonical Parquet writer (RETIRED)

**Last Updated**: 2026-06-19
**Status**: RETIRED. `backend/yen_gov/canonical/writer.py` (the Hive-partitioned Parquet writer with the batch-envelope write surface and the `--dry-run` flag) was deleted in the long-format-CSV rip-and-replace (Row 9 of the ingest pipeline rip). Every canonical Parquet table retired (CLAUDE.md X1a-fu2); the `lift-*` commands that drove it are gone too (see [lifting.md](lifting.md)).

The successor write seam is the **canonical long-format CSV writer** at `yen_gov.canonical.csv_writer.write_csv`, documented at [canonical-writer.md](canonical-writer.md). The manifest is now produced by a pure stamp (`yen_gov.canonical.manifest.emit_manifest`), not by a Parquet scan.

## See also

- [canonical-writer.md](canonical-writer.md) - `yen_gov.canonical.csv_writer.write_csv` + `csv_validator` (the live writer + validator).
- [docs/architecture/ingest/pipeline.md](../ingest/pipeline.md) - the ingest pipeline that drives the writer.
- [../data/canonical-store.md](../data/canonical-store.md) - the canonical long-format CSV store layout.
- [validator.md](validator.md) - Tier A / Tier B validation gates.
