# AGENTS.md - frontend/src

**Last Updated**: 2026-06-04

Canonical frontend rationale lives in `docs/architecture/frontend/`; this file is only a fast module map for agents.

ASCII only: use plain keyboard characters; write "-", "->", ">=", "section", and "INR" instead of fancy symbols.

> **MIGRATING (2026-06-04).** Per the [CLAUDE.md](../../CLAUDE.md) doctrine-in-migration banner + [the platform-reset plan](../../TODO/20260603-data-and-charting-platform-reset-plan.md), the production read path is moving from Hive-partitioned Parquet to long-format CSV under `datasets/data/`, read via DuckDB-WASM `read_csv(columns=...)`. X1a has flipped the `dim_parties` + `taxonomy.sources` readers + every F1.3 view-model (constituency / state-overview / national-elections / psephlab / explore / yenask) onto the canonical CSV store via the `registerCsvAsTable` seam in `lib/duckdb.ts`. Residual parquet reads remain on `election_results`, `dim_party_alliances`, `dim_acs`, `elections_candidacies`, `dim_persons` (via canonical-allowlist), `entities`, `ac_crosswalk`, `indicators` - they retire via B3/X1b. `boundary_layers` retired in X1a-fu2-E (2026-06-07) - inventory ledger lives at `datasets/data/entities/boundary_layer.csv`; no frontend reader existed pre-rip. Still NO JSON projections of canonical data.

## Canonical Docs

- [Frontend overview](../../docs/architecture/frontend/overview.md)
- [Frontend data loading](../../docs/architecture/frontend/data-loading.md)
- [Indicators UI](../../docs/architecture/frontend/indicators.md)
- [Map architecture](../../docs/architecture/frontend/map.md)
- [Colour system](../../docs/architecture/frontend/colours.md)
- [Compare flows](../../docs/architecture/frontend/compare.md)
- [Deployment](../../docs/architecture/deployment.md)
- [Canonical store (long-format CSV + DuckDB-WASM)](../../docs/architecture/data/canonical-store.md) - runtime data path (X1a flipped dim_parties + taxonomy.sources + F1.3 view-models; residual parquet reads retire B3/X1b)

## Invariants

- Static GitHub Pages app; anything needed at runtime ships in the bundle (including the DuckDB-WASM engine).
- Do not import from `backend/`.
- Do not commit generated data from `frontend/`; the only writer of `datasets/` is `backend/`.
- **Canonical pivot.** Production read path is DuckDB-WASM in the browser executing SQL over long-format CSV under `datasets/data/` via `read_csv(columns=...)` for X1a-flipped surfaces (per-(state,year) candidacies + summary CSV; `dim_parties` via `registerCsvAsTable('elections.dim_parties')` -> `data/entities/parties.csv`; `taxonomy.sources` via `registerCsvAsTable('taxonomy.sources')` -> `data/entities/source.csv`). Residual parquet reads (election_results, dim_party_alliances, dim_acs, elections_candidacies, dim_persons via canonical-allowlist, entities, ac_crosswalk, indicators) retire via B3/X1b. `boundary_layers` retired in X1a-fu2-E (2026-06-07) and now lives at `datasets/data/entities/boundary_layer.csv` (no frontend reader pre-rip). **No JSON projections of canonical data.** Pre-pivot per-shard JSON (per-event `datasets/elections/<event>/<state>/{results/<ac>.json,parties.json,result.summary.json}`) is **superseded**; no new readers are allowed against that shape. See [`docs/architecture/canonical-pivot-deletion-manifest.md`](../../docs/architecture/canonical-pivot-deletion-manifest.md).
- Citizen-visible URL grammar is preserved across the pivot - only the loader internals change (touch points: `src/lib/data.ts`, `src/lib/paths.ts:15`).
- Citizen-visible route changes need frontend tests and integrated-browser smoke verification per [CLAUDE.md](../../CLAUDE.md#13-ui-verification-mandatory-for-frontend--admin-changes).
- Catalogue-driven UI should read schemas/catalogues instead of hardcoding one-off dataset lists.

## Validation

- Run `npm test` in `frontend/` for frontend code changes.
- Run `npm run test:e2e` in `frontend/` for citizen-visible route changes.
- If package manifests change, regenerate and stage the matching `bun.lock`.
