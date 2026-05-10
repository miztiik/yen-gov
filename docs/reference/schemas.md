# Schemas

**Last Updated**: 2026-05-11

All schemas live in [`datasets/schemas/`](../../datasets/schemas/). Each is a JSON Schema 2020-12 document carrying its own version and changelog (CLAUDE.md §11).

## Current schemas

### Election entities (Phase 0–2)

| File                                  | Title                              | x-version | Describes                                                                |
| ------------------------------------- | ---------------------------------- | :-------: | ------------------------------------------------------------------------ |
| `state.schema.json`                   | States collection                  | 3.3       | Top-level division list for one country. v3.3 (2026-05-11) adds optional `tier` enum (general_category / special_category_neh / special_category_hill / ut_with_legislature / ut_without_legislature / nct_delhi) so cross-state ranked tables can default-filter to comparable entities. |
| `district.schema.json`                | Districts collection (per state)   | 3.0       | District list for one state.                                             |
| `constituency.schema.json`            | Constituencies collection          | 3.0       | AC or PC list for one (state, body) pair.                                |
| `party.schema.json`                   | Parties snapshot (per election)    | 3.0       | Party catalog scoped to one election event.                              |
| `election.schema.json`                | Election event metadata            | 3.0       | Event id, scope, body, year, covered states, dates.                      |
| `result.constituency.schema.json`     | Per-constituency result            | 3.0       | Top-N candidates + NOTA + others bucket + winner + margin for one AC/PC. |
| `result.summary.schema.json`          | Per-event-per-state result summary | 3.0       | State-level rollup of party totals, seats, turnout.                      |
| `processing.schema.json`              | Pipeline processing knobs          | 3.0       | Tunable runtime config (fetch, result aggregation).                      |
| `boundary.sources.schema.json`        | Boundary GeoJSON provenance sidecar| 1.0       | `<file>.geojson.sources.json` for electoral/admin boundary GeoJSONs.     |

### Socio-economic / non-election (Phase A, 2026-05-10)

Introduced by [`TODO/SOCIO-ECONOMIC-EXPANSION.md`](../../TODO/SOCIO-ECONOMIC-EXPANSION.md) (decisions D1, D3, D4, RP, Q3 — locked 2026-05-10).

| File                                              | Title                                 | x-version | Describes                                                                                                              |
| ------------------------------------------------- | ------------------------------------- | :-------: | ---------------------------------------------------------------------------------------------------------------------- |
| `feature_collection.metadata.schema.json`         | Feature collection metadata sidecar   | 1.0       | `<file>.metadata.json` for non-electoral GeoJSON FeatureCollections (power plants, hospitals, etc.). Carries `sources`, `license`, `coverage`, `coordinate_system`. |
| `indicator.schema.json`                           | Indicator (long-form fact table)      | 1.1       | One indicator (e.g. installed MW per state per year) as long-form `(entity_id, time, value)` rows with semantic hints (`value_kind`, `direction`, `unit`). v1.1 (2026-05-11) adds optional honesty fields: `attribution_geography`, `comparability`, `funding_split`, `implementing_authority`, `methodology_vintage`, `series_breaks[]`, `icon`. See [ADR-0020](../architecture/decisions/0020-indicator-artifact-as-data-contract.md). |
| `state_government.schema.json`                    | State government history (CM terms)   | 1.0       | Per-state CM term timeline (start/end dates, party_code, alliance, regime). Drives the colour-by-government overlay. |

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
