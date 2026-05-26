# tools/migrate/

One-shot DuckDB CTAS migration scripts for the grain-rip
(`TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md` §3 PR-B
series). Each script renames or collapses `indicator_id` values across the
canonical Parquet shards for a single family. Idempotent: re-running on
post-migration shards is a no-op.

| Script | PR | Scope |
| --- | --- | --- |
| `path_b_elections.py` | B2 | Strip `state-` prefix on 8 elections rollups |
