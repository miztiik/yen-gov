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
- [Folded indicator](../../docs/concepts/folded-indicator.md)
- [Collection inventory](../../docs/concepts/collection-inventory.md)
- [Data quality stance](../../docs/concepts/data-quality.md)

## Invariants

- Local pipeline only; no production backend assumption.
- Producers write schema-validated artifacts to `datasets/`; consumers treat those artifacts as contracts.
- Cross-runtime sharing is data only: JSON, SQLite, CSV, schemas. No frontend imports.
- Core/domain code must not import adapters or infrastructure.
- Persisted paths are POSIX-relative, never absolute or Windows-style.
- Every emitted data file carries `sources[]` and schema metadata.
- Provenance timestamps (`fetched_at`, `generated_at`, doc footers) are DERIVED from upstream content change, never from `datetime.now()` at write time. Use a content-hash identity check at the Fetcher or input-mtime at the doc emitter. Composers union `sources[]` per-`url`, not per-`(url, fetched_at)`. Counter-example to copy: `sources/datagovin_ogd/ingest.py` derives `fetched_at` from cached file `st_mtime`. See [data provenance](../../docs/concepts/data-provenance.md) and `TODO/20260516-fetched-at-content-hash-gate-handover.md`.
- Indicators are folded: a single JSON per indicator carries `indicator + rows[] + license + coverage + sources` AND `methodology + series_spec + divergence`. No sidecars. `series_spec` is `{description}` only since schema v4.0. `write_artifact` derives nothing operational into the artifact — `methodology` / `series_spec` / `divergence` are caller-wins-then-prior-then-stub. Per-indicator operator state (`frozen`, `refetch_requested`, `unavailable_periods`) lives in the sparse overlay `datasets/reference/in/indicators-operator-state.json`. Citizen completeness lives in the derived index `datasets/reference/in/indicators-completeness.json`. See [folded indicator](../../docs/concepts/folded-indicator.md) and [ADR-0026](../../docs/architecture/decisions/0026-lift-collection-inventory-out-of-indicator-artifact.md).
- Adapter owns its source's period vocabulary. Planner round-trips `{key, label, frequency}` tokens opaquely. No normaliser, no LLM, no canonical-form transformer.
- Planner reads operator state from the overlay (`indicators-operator-state.json` — `frozen`, `refetch_requested`) and observed periods from the artifact's `rows[]`. Pending = (publisher schedule) − (observed); the publisher schedule is adapter-owned, not in the artifact. `rm` of `.runtime/raw/` is the only force-recollect — see [how-to: force re-collection](../../docs/how-to/force-recollect.md).

## Validation

- Backend behaviour changes need `pytest -q` in `backend/`.
- Dataset/schema changes need the producer validator tests and consumer contract tests described in [CLAUDE.md](../../CLAUDE.md#15-test-coverage-policy).
- If a source adapter changes, update its `docs/architecture/backend/sources-*.md` doc in the same commit.
