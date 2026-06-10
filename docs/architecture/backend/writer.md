Last Updated: 2026-05-27

# Canonical writer (`yen_gov.canonical.writer`)

The canonical writer is the sole entry point that persists observation rows into the Hive-partitioned Parquet store under `datasets/<family>/`. It is the write seam referenced by Holy Law #2 ("backend is the only writer to `datasets/`") and the contract surface every lift command (see [lifting.md](lifting.md)) and every adapter eventually funnels through.

## Purpose

- UPSERT observation rows into `datasets/<family>/<family>_<role>.parquet` keyed by the canonical primary key `(entity_id, year, period_label, indicator_id)`.
- Re-write of an existing PK = replace the row (new vintage of the same fact). Mint of a new `indicator_id` is NOT a writer concern -- see [ADR-0044](../../reference/decision-index.md) "grain over entity" and the indicator-catalogue minting rules in [CLAUDE.md section 10](../../../CLAUDE.md).
- Attach `source_id` FK on every row per Holy Law #9 (citation ledger -- see [ADR-0032](../../reference/decision-index.md)).
- Reject rows that violate the meadow grammar (see [ADR-0041](../../reference/decision-index.md)) or that lack a declared `indicator_id` in `datasets/taxonomy/indicators.json`.

## `--dry-run` flag (PR #338)

Per PR-A2 of the grain-rip plan, the writer and every command that drives it accept `--dry-run`:

```
python -m yen_gov lift-energy --dry-run
python -m yen_gov lift-livestock --dry-run
python -m yen_gov emit-taxonomy --dry-run
```

Behaviour:

- Reads all inputs and runs the full transform + validation pipeline.
- Prints the planned change set to stdout: per-table row counts (`upserts`, `inserts`, `noops`, `skips`) and the absolute emit paths that WOULD be written.
- Does NOT touch disk. No Parquet write, no manifest update, no taxonomy regeneration.
- Exits 0 on a clean dry-run; non-zero on a validation failure that would have blocked a real write.

When to use:

- Pre-merge audit of an ingest PR to see what would change on `datasets/` before committing.
- Bisecting a regression: run `--dry-run` on suspect SHAs to confirm the diff cause is upstream of the writer (parser / adapter) versus inside the writer itself.
- Operator sanity check after editing an adapter -- run `--dry-run` against the real meadow snapshot before re-emitting.

## When NOT to use

- CI gates do not run `--dry-run`. Tier A and Tier B (see [validator.md](validator.md)) operate on the on-disk Parquet emitted by a real write. A dry-run cannot stand in for a Tier B pass.
- Frontend never invokes the writer. Frontend reads the emitted Parquet via DuckDB-WASM only (see Holy Law #1).

## See also

- [ADR-0044](../../reference/decision-index.md) -- grain dispatched at read time, not encoded in `indicator_id`.
- [ADR-0041](../../reference/decision-index.md) -- meadow tier path grammar (input side of the writer).
- [ADR-0032](../../reference/decision-index.md) -- `source_id` FK requirement on every observation row.
- [lifting.md](lifting.md) -- per-family lift commands that call the writer.
- [validator.md](validator.md) -- Tier A / Tier B validation that runs after a real write.
- [../data/canonical-store.md](../data/canonical-store.md) -- canonical store schema and Hive partitioning.
