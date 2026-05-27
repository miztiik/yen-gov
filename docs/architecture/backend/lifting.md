Last Updated: 2026-05-27

# Lift commands (`yen_gov lift-*`)

Lift commands are the per-family adapters that read meadow JSON snapshots (see [ADR-0041](../decisions/0041-meadow-tier.md)) and emit canonical Parquet rows via the [canonical writer](writer.md). One lift command per indicator family; each owns the family's parse + normalise + UPSERT flow.

## Available commands

```
python -m yen_gov lift-energy
python -m yen_gov lift-livestock
python -m yen_gov lift-fiscal
python -m yen_gov lift-elections
... etc.
```

Each command:

1. Walks `datasets/<family>/_meadow/<source>/<vintage>/` for that family's meadow JSON snapshots.
2. Resolves entity IDs via `datasets/taxonomy/entities.parquet` and indicator IDs via `datasets/taxonomy/indicators.json`.
3. Attaches a `source_id` per Holy Law #9 (see [ADR-0032](../decisions/0032-sources-citation-ledger.md)).
4. UPSERTs through the canonical writer keyed by `(entity_id, year, period_label, indicator_id)`.

## `--table <stem>` flag (PR #368)

Per PR-A4 of the grain-rip plan, lift commands accept `--table <stem>` to restrict the run to a single table stem within the family:

```
python -m yen_gov lift-energy --table installed_capacity_mw
python -m yen_gov lift-livestock --table owner_registration_count
```

Behaviour:

- Only meadow shards whose canonical target table is `<family>_<stem>.parquet` are read, parsed, and emitted.
- All other tables in the family are left untouched on disk.
- Combines cleanly with `--dry-run` (see [writer.md](writer.md)) for tight iteration on one adapter at a time.

When to use:

- Iterating on a single adapter without paying the wall-clock cost of the whole family.
- Bisecting a regression localised to one table stem.
- Re-emitting one table after a schema fix without churning the rest of the family in the diff.

## When NOT to use

- Full-family emit before a PR merge: omit `--table` so every shard is re-run and the family is internally consistent.
- Cross-family invariants (e.g. shared entity dimension regeneration) -- run `emit-taxonomy` separately; `--table` does not gate that.

## See also

- [ADR-0041](../decisions/0041-meadow-tier.md) -- meadow tier path grammar that lift commands read from.
- [ADR-0044](../decisions/0044-grain-over-entity.md) -- grain dispatched at read time; lift commands do not encode grain in the `indicator_id`.
- [writer.md](writer.md) -- canonical writer that lift commands call, including the `--dry-run` flag.
- [validator.md](validator.md) -- Tier A / Tier B gates that run after a lift writes to disk.
