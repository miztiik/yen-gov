# Schemas

**Last Updated**: 2026-05-31

All schemas live in [`datasets/schemas/`](../../datasets/schemas/). Each is a JSON Schema 2020-12 document carrying its own version and changelog (CLAUDE.md §11).

## Current schemas

### Election entities (Phase 0–2)

| File                                  | Title                              | x-version | Describes                                                                |
| ------------------------------------- | ---------------------------------- | :-------: | ------------------------------------------------------------------------ |
| `state.schema.json`                   | States collection                  | 3.3       | Top-level division list for one country. v3.3 (2026-05-11) adds optional `tier` enum (general_category / special_category_neh / special_category_hill / ut_with_legislature / ut_without_legislature / nct_delhi) so cross-state ranked tables can default-filter to comparable entities. |
| `constituency.schema.json`            | Constituencies collection          | 3.0       | AC or PC list for one (state, body) pair.                                |
| `party.schema.json`                   | Parties snapshot (per election)    | 3.0       | Party catalog scoped to one election event.                              |
| `election.schema.json`                | Election event metadata            | 3.0       | Event id, scope, body, year, covered states, dates.                      |
| `result.constituency.schema.json`     | Per-constituency result            | 3.0       | Top-N candidates + NOTA + others bucket + winner + margin for one AC/PC. |
| `result.summary.schema.json`          | Per-event-per-state result summary | 3.0       | State-level rollup of party totals, seats, turnout.                      |
| `processing.schema.json`              | Pipeline processing knobs          | 3.0       | Tunable runtime config (fetch, result aggregation).                      |
| `boundary-layers.schema.json`         | Boundary layers parquet ledger     | 1.0       | One row per boundary shard (`layer_id` PK, `source_id` FK, denominator, simplification metadata). Backs `datasets/boundaries/boundary_layers.parquet` (T.0d, 2026-05-22). Replaces the per-shard `boundary.sources` / `boundary.unkeyed` / `boundary.villages_index` sidecars (retired in same Tier-A commit). |

### Socio-economic / non-election (Phase A, 2026-05-10)

Introduced by [`TODO/SOCIO-ECONOMIC-EXPANSION.md`](../../TODO/SOCIO-ECONOMIC-EXPANSION.md) (decisions D1, D3, D4, RP, Q3 — locked 2026-05-10).

| File                                              | Title                                 | x-version | Describes                                                                                                              |
| ------------------------------------------------- | ------------------------------------- | :-------: | ---------------------------------------------------------------------------------------------------------------------- |
| `feature_collection.metadata.schema.json`         | Feature collection metadata sidecar   | 1.0       | `<file>.metadata.json` for non-electoral GeoJSON FeatureCollections (power plants, hospitals, etc.). Carries `sources`, `license`, `coverage`, `coordinate_system`. |
| `indicator.schema.json`                           | Indicator (long-form fact table)      | 1.2       | One indicator (e.g. installed MW per state per year) as long-form `(entity_id, time, value)` rows with semantic hints (`value_kind`, `direction`, `unit`). v1.2 (2026-05-14) adds optional renderer hints `chart_type` (choropleth / ranked / stacked-trend) and `default_mode` (absolute / percent) so facetted artifacts can declare their preferred visualisation without per-page string matching — see [archived ADR-0024](../archive/decisions/0024-backend-aggregator-for-facetted-indicators.md) (superseded by PR 7b; rationale folded into [docs/architecture/data/indicator-catalogue.md](../architecture/data/indicator-catalogue.md#adr-0024-rejected-alternatives)) and [`docs/architecture/frontend/charts/stacked-trend.md`](../architecture/frontend/charts/stacked-trend.md). v1.1 (2026-05-11) added the honesty fields: `attribution_geography`, `comparability`, `funding_split`, `implementing_authority`, `methodology_vintage`, `series_breaks[]`, `icon`. See [ADR-0020](../architecture/decisions/0020-indicator-artifact-as-data-contract.md). |
| `office-holdings.schema.json`                     | Government office holdings            | 1.1       | Long-form consolidation of government and constitutional-office tenures. v1.1 adds official `citation_groups`, nullable `regime`, `selection_method`, and `tenure_status` so President / Vice President rows can land with Government of India provenance while CM rows keep legacy `office_citations`. Replaced `state_government.schema.json` in G.1.c (2026-05-22). |

### Schema control plane

| File | Title | x-version | Describes |
| --- | --- | :---: | --- |
| `schema-compatibility.schema.json` | Schema compatibility registry | 1.0 | `datasets/schema-compatibility.json`, the shared reader-side compatibility contract introduced by ADR-0047. Backend Tier B and the frontend JSON corpus contract consume the `json-corpus` surface as of Rows E/F; the canonical DuckDB-WASM reader consumes the `canonical-manifest-reader` surface as of Rows G1/G2. Overrides list explicitly accepted versions for reader surfaces. |
| `schema-evolution.schema.json` | Schema evolution release ledger | 1.0 | `datasets/schema-evolution.json`, the public release metadata ledger introduced by Row H. Entries record schema changes, whether values/provenance/methodology changed, affected artifacts, PR/commit provenance, and retained historical schema paths for declared-version validation. |

After a schema bump, run `python -m yen_gov validate --root .` from the repo root, then update the affected row by hand. Auto-generation is a future convenience, not a blocker.

## Versioning rules

Pulled from CLAUDE.md section 11 and [ADR-0047](../architecture/decisions/0047-schema-version-compatibility-contract.md) - re-stated here for convenience, but `CLAUDE.md` is authoritative if they ever conflict.

- Format is `<major>.<minor>` only. No patch component.
- **Minor bump** for backwards-compatible additions: new optional field, broadened enum, looser bound.
- **Major bump** for any breaking change: removed/renamed field, type change, narrowed bound, semantic shift.
- Every bump adds an `x-changelog` entry in the same commit. The tail entry's `version` MUST equal `x-version` (Tier A enforces this).
- Writers are strict: newly emitted artifacts use the current schema version from the registry.
- Readers and validators are compatible only by explicit contract. Do not infer compatibility from the version number alone.

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

The writer resolves the schema from the local registry and stamps the current `$schema_version`. Writer-side stale schema metadata is an error.

Reader-side policy is compatibility by explicit contract. Backend Tier B and `frontend/src/contracts/datasets-conform.test.ts` consume `datasets/schema-compatibility.json` for the `json-corpus` surface. The canonical DuckDB-WASM runtime derives manifest/table compatibility from the `canonical-manifest-reader` surface. A reader may accept an older declared version only when the compatibility contract says the reader can interpret it without guessing. Unsupported future versions, unsupported major versions, and incompatible shapes fail loud.

When the current schema cannot honestly validate an older declared version, the schema-evolution ledger must name a retained historical schema under `datasets/schemas/archive/<schema-stem>/v<major>.<minor>/<schema-file>`. Retained schemas are repo files with SHA-256 checks in `datasets/schema-evolution.json`; validators must not rely on git history or release assets to discover them.

Do not restamp or rebuild unchanged artifacts just to update `$schema_version` after an additive minor change. If values, logical keys, provenance, and semantics did not change, the old declared version can remain once the reader compatibility contract supports it. See [schema evolution](../architecture/data/schema-evolution.md).

## Running the validator

```sh
PYTHONPATH=backend python -m yen_gov validate --root .
```

Exits 0 on success. On failure, prints `[tier A|B] <relative path>: <message>` per issue and exits 1. Tier B corpus validation is local/on-demand, not a CI gate; run it before commits that touch `datasets/**`, `config/**`, or `datasets/schemas/**`.

## See also

- [`docs/architecture/data-model.md`](../architecture/data-model.md) — what each schema represents.
- [`docs/architecture/data-flow.md`](../architecture/data-flow.md) — where data files end up.
- [`docs/architecture/data/schema-evolution.md`](../architecture/data/schema-evolution.md) - writer-strict / reader-compatible policy.
- [`docs/reference/identifiers.md`](identifiers.md) — code conventions inside payloads.
- [ADR-0047](../architecture/decisions/0047-schema-version-compatibility-contract.md) - schema-version compatibility decision.
- `CLAUDE.md` §11 — authoritative versioning contract.
