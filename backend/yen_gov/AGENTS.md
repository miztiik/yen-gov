# AGENTS.md - backend/yen_gov

**Last Updated**: 2026-06-13

Canonical backend rationale lives in `docs/architecture/backend/`. This file is only a fast module map for agents.

ASCII only: use plain keyboard characters; write "-", "->", ">=", "section", and "INR" instead of fancy symbols.

> **Current canonical store.** Canonical tabular data is long-format CSV under `datasets/data/`. The browser reads it through DuckDB-WASM `read_csv(columns=...)`; provenance FK targets `datasets/data/entities/source.csv`. There are zero canonical Parquet readers or writers in the citizen-facing store. Any Parquet residue belongs only under `datasets/ephemeral/` or transient in-process compatibility paths.

## Canonical Docs

- [Backend overview](../../docs/architecture/backend/overview.md)
- [Backend core](../../docs/architecture/backend/core.md)
- [Pipeline](../../docs/architecture/backend/pipeline.md)
- [Dataset coverage](../../docs/architecture/backend/coverage.md)
- [ECI source adapter](../../docs/architecture/backend/sources-eci.md)
- [Canonical store](../../docs/architecture/data/canonical-store.md)
- [CSV column contract](../../docs/architecture/data/csv-column-contract.md)
- [Backend validator](../../docs/architecture/backend/validator.md)
- [Governments data family](../../docs/architecture/data/governments.md)
- [Data provenance](../../docs/concepts/data-provenance.md)
- [Dataset shapes](../../docs/concepts/dataset-shapes.md)
- [Data quality stance](../../docs/concepts/data-quality.md)

## Invariants

- Local pipeline only; no production backend assumption.
- Producers write schema-validated artifacts to `datasets/`; consumers treat those artifacts as contracts.
- Cross-runtime sharing is data only: JSON, CSV, schemas. No frontend imports.
- Core/domain code must not import adapters or infrastructure.
- Persisted paths are POSIX-relative, never absolute or Windows-style.
- Canonical CSV writes go through `backend/yen_gov/canonical/csv_writer.py` and the column contract in `datasets/data/_schema/columns.json`.
- Route-shaped derived read models live under `backend/yen_gov/canonical/derived/` and emit small CSV marts under `datasets/data/marts/`. They are reproducible from canonical CSV inputs and must carry a freshness receipt validated by Tier-B.
- Cross-file CSV integrity lives in `backend/yen_gov/canonical/csv_validator.py` and Tier-B validator checks.
- Every emitted observation carries `source_id` FK to `datasets/data/entities/source.csv`.
- Retired surfaces are enforced by code, not by archived ledgers: new folded indicator shards, legacy boundary sidecars, legacy election JSON/sqlite readers, and retired canonical Parquets are blocked by `backend/yen_gov/validate.py`, `datasets/_ops/*.txt` allowlists, and the owning subsystem docs.
- `datasets/taxonomy/office_holdings.json` is the hand-authored source-of-truth for office holdings. `emit-taxonomy` compiles it to `datasets/data/entities/office.csv`, `datasets/data/entities/holder.csv`, and `datasets/data/datapoints/office_holdings.csv`.

## Validation

- Backend behaviour changes need `pytest -q` in `backend/`.
- Dataset/schema changes need producer validator tests and consumer contract tests described in [CLAUDE.md](../../CLAUDE.md#15-test-coverage-policy).
- Source adapter changes update the matching `docs/architecture/backend/sources-*.md` doc in the same commit.
