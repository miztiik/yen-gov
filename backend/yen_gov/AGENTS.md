# AGENTS.md - backend/yen_gov

**Last Updated**: 2026-05-15

Canonical backend rationale lives in `docs/architecture/backend/`; this file is only a fast module map for agents.

## Canonical Docs

- [Backend overview](../../docs/architecture/backend/overview.md)
- [Backend core](../../docs/architecture/backend/core.md)
- [Pipeline](../../docs/architecture/backend/pipeline.md)
- [Dataset coverage](../../docs/architecture/backend/coverage.md)
- [ECI source adapter](../../docs/architecture/backend/sources-eci.md)
- [Data provenance](../../docs/concepts/data-provenance.md)
- [Dataset shapes](../../docs/concepts/dataset-shapes.md)

## Invariants

- Local pipeline only; no production backend assumption.
- Producers write schema-validated artifacts to `datasets/`; consumers treat those artifacts as contracts.
- Cross-runtime sharing is data only: JSON, SQLite, CSV, schemas. No frontend imports.
- Core/domain code must not import adapters or infrastructure.
- Persisted paths are POSIX-relative, never absolute or Windows-style.
- Every emitted data file carries `sources[]` and schema metadata.
- Provenance timestamps (`fetched_at`, `generated_at`, doc footers) are DERIVED from upstream content change, never from `datetime.now()` at write time. Use a content-hash identity check at the Fetcher or input-mtime at the doc emitter. Unconditional `path.write_text` at a write seam that holds a stamp is a smell — prefer `write_text_if_changed`. Composers union `sources[]` per-`url`, not per-`(url, fetched_at)`. Counter-example to copy: `sources/datagovin_ogd/ingest.py` derives `fetched_at` from cached file `st_mtime`. See [data provenance](../../docs/concepts/data-provenance.md) and `TODO/20260516-fetched-at-content-hash-gate-handover.md`.

## Validation

- Backend behaviour changes need `pytest -q` in `backend/`.
- Dataset/schema changes need the producer validator tests and consumer contract tests described in [CLAUDE.md](../../CLAUDE.md#15-test-coverage-policy).
- If a source adapter changes, update its `docs/architecture/backend/sources-*.md` doc in the same commit.
