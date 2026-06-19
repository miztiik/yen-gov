# Lift commands (RETIRED)

**Last Updated**: 2026-06-19
**Status**: RETIRED. The `python -m yen_gov lift-<family>` CLI family (`lift-energy`, `lift-livestock`, ...) was removed in the long-format-CSV rip-and-replace; the energy + livestock families it drove retired with it (CLAUDE.md X1b-pt2, 2026-06-07), and the Hive-partitioned Parquet store + meadow JSON tier it read are gone.

The successor is the **ingest pipeline**: work is addressed by INDICATOR (`python -m yen_gov ingest run --indicator <id>`), driven through a polymorphic adapter registry rather than a per-family `lift-*` command. A source feeds one or more indicators; the orchestrator resolves the owning adapter underneath.

## See also

- [docs/architecture/ingest/pipeline.md](../ingest/pipeline.md) - the ingest subsystem design.
- [docs/reference/cli-ingest.md](../../reference/cli-ingest.md) - the `ingest run` / `status` / `clean` CLI.
- [docs/how-to/add-a-new-data-source.md](../../how-to/add-a-new-data-source.md) - the cookbook for adding a source.
- [canonical-writer.md](canonical-writer.md) - the canonical long-format CSV writer (the successor write seam).
- [validator.md](validator.md) - the Tier A / Tier B validation gates.
