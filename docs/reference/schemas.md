# Schemas

**Last Updated**: 2026-05-08

All schemas live in [`datasets/schemas/`](../../datasets/schemas/). Each is a JSON Schema 2020-12 document carrying its own version and changelog (CLAUDE.md §11).

## Current schemas

| File                                  | Title                              | x-version | Describes                                                                |
| ------------------------------------- | ---------------------------------- | :-------: | ------------------------------------------------------------------------ |
| `state.schema.json`                   | States collection                  | 3.0       | Top-level division list for one country.                                 |
| `district.schema.json`                | Districts collection (per state)   | 3.0       | District list for one state.                                             |
| `constituency.schema.json`            | Constituencies collection          | 3.0       | AC or PC list for one (state, body) pair.                                |
| `party.schema.json`                   | Parties snapshot (per election)    | 3.0       | Party catalog scoped to one election event.                              |
| `election.schema.json`                | Election event metadata            | 3.0       | Event id, scope, body, year, covered states, dates.                      |
| `result.constituency.schema.json`     | Per-constituency result            | 3.0       | Top-N candidates + NOTA + others bucket + winner + margin for one AC/PC. |
| `result.summary.schema.json`          | Per-event-per-state result summary | 3.0       | State-level rollup of party totals, seats, turnout.                      |
| `processing.schema.json`              | Pipeline processing knobs          | 3.0       | Tunable runtime config (fetch, result aggregation).                      |

To regenerate this table after a schema bump, run `python -m yen_gov validate` and update the row by hand. (Auto-generation is a Phase 4 nice-to-have, not a blocker.)

## Versioning rules

Pulled from CLAUDE.md §11 — re-stated here for convenience, but `CLAUDE.md` is authoritative if they ever conflict.

- Format is `<major>.<minor>` only. No patch component.
- **Minor bump** for backwards-compatible additions: new optional field, broadened enum, looser bound.
- **Major bump** for any breaking change: removed/renamed field, type change, narrowed bound, semantic shift.
- Every bump adds an `x-changelog` entry in the same commit. The tail entry's `version` MUST equal `x-version` (Tier A enforces this).

## How a data file declares its schema

Every JSON file under `datasets/` (except the schemas themselves) and `config/` must include:

```json
{
  "$schema": "https://yen-gov.github.io/schemas/<name>.schema.json",
  "$schema_version": "3.0",
  "sources": [
    { "url": "https://results.eci.gov.in/...", "fetched_at": "2026-05-08T14:30:00Z" }
  ],
  ...
}
```

The validator resolves `$schema` to a local file by basename match (or by `$id` exact match), then enforces `$schema_version == schema.x-version`. Mismatch fails Tier B.

If a future migration requires consumers to read both old and new versions, we'll add a per-schema migration map to the validator. Until then, the rule is strict: data files are emitted at the current version, full stop.

## Running the validator

```sh
PYTHONPATH=backend python -m yen_gov validate
```

Exits 0 on success. On failure, prints `[tier A|B] <relative path>: <message>` per issue and exits 1. CI runs this on every PR (Phase 4).

## See also

- [`docs/architecture/data-model.md`](../architecture/data-model.md) — what each schema represents.
- [`docs/architecture/data-flow.md`](../architecture/data-flow.md) — where data files end up.
- [`docs/reference/identifiers.md`](identifiers.md) — code conventions inside payloads.
- `CLAUDE.md` §11 — authoritative versioning contract.
