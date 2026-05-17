# AGENTS.md - backend/yen_gov

**Last Updated**: 2026-05-17

Canonical backend rationale lives in `docs/architecture/backend/`; this file is only a fast module map for agents.

## Canonical Docs

- [Backend overview](../../docs/architecture/backend/overview.md)
- [Backend core](../../docs/architecture/backend/core.md)
- [Pipeline](../../docs/architecture/backend/pipeline.md)
- [Dataset coverage](../../docs/architecture/backend/coverage.md)
- [ECI source adapter](../../docs/architecture/backend/sources-eci.md)
- [Data provenance](../../docs/concepts/data-provenance.md)
- [Dataset shapes](../../docs/concepts/dataset-shapes.md)
- [Canonical store (Parquet + DuckDB-WASM)](../../docs/architecture/data/canonical-store.md) — current model
- [Folded indicator](../../docs/concepts/folded-indicator.md) — **obsolete under ADR-0030**, kept for `_old/` reader context only
- [Collection inventory](../../docs/concepts/collection-inventory.md) — **obsolete under ADR-0030**
- [Data quality stance](../../docs/concepts/data-quality.md)

## Invariants

- Local pipeline only; no production backend assumption.
- Producers write schema-validated artifacts to `datasets/`; consumers treat those artifacts as contracts.
- Cross-runtime sharing is data only: JSON, SQLite, CSV, schemas. No frontend imports.
- Core/domain code must not import adapters or infrastructure.
- Persisted paths are POSIX-relative, never absolute or Windows-style.
- Every emitted data file carries `sources[]` and schema metadata.
- **Canonical pivot (ADR-0030).** New writes target Hive-partitioned Parquet under `datasets/<family>/` written by UPSERT-into-DuckDB. Canonical row = `(observation_id, entity_id, year:int, period_label:text, indicator_id, value, source_id)`. Time axis is **OWID `year:int`** (end-year for FY); `period_label` is the verbatim publisher string. Sources are a **table** (`datasets/taxonomy/sources.parquet`) keyed by `(url, content_hash)`; observation rows carry `source_id` FK. `first_fetched_at` (immutable) + `last_seen_at` (mutable) replace `fetched_at`. See [canonical store](../../docs/architecture/data/canonical-store.md).
- **Legacy folded JSON** (`datasets/indicators/in/<topic>/<id>.json` and its sidecar inventory/operator-state files) is **read-only** under `datasets/_old/` during the pivot; deleted at end of Phase 1. No new writers in that shape. The pre-pivot rule "adapter owns opaque `{key, label, frequency}` tokens; no normaliser" is **withdrawn** for canonical artifacts — under OWID adoption, adapters write `year:int` + verbatim `period_label`, and indicators carry `cadence` on the indicator row.
- Per Holy Law #9 + CLAUDE.md §12: every emitted Parquet observation carries a `source_id` FK (legacy JSON files in `_old/` still use their existing `sources[]` array until deletion).

## Validation

- Backend behaviour changes need `pytest -q` in `backend/`.
- Dataset/schema changes need the producer validator tests and consumer contract tests described in [CLAUDE.md](../../CLAUDE.md#15-test-coverage-policy).
- If a source adapter changes, update its `docs/architecture/backend/sources-*.md` doc in the same commit.
