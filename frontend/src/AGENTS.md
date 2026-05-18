# AGENTS.md - frontend/src

**Last Updated**: 2026-05-17

Canonical frontend rationale lives in `docs/architecture/frontend/`; this file is only a fast module map for agents.

## Canonical Docs

- [Frontend overview](../../docs/architecture/frontend/overview.md)
- [Frontend data loading](../../docs/architecture/frontend/data-loading.md)
- [Indicators UI](../../docs/architecture/frontend/indicators.md)
- [Map architecture](../../docs/architecture/frontend/map.md)
- [Colour system](../../docs/architecture/frontend/colours.md)
- [Compare flows](../../docs/architecture/frontend/compare.md)
- [Deployment](../../docs/architecture/deployment.md)
- [Canonical store (Parquet + DuckDB-WASM)](../../docs/architecture/data/canonical-store.md) — runtime data path

## Invariants

- Static GitHub Pages app; anything needed at runtime ships in the bundle (including the DuckDB-WASM engine).
- Do not import from `backend/`.
- Do not commit generated data from `frontend/`; the only writer of `datasets/` is `backend/`.
- **Canonical pivot (ADR-0030).** Production read path is DuckDB-WASM in the browser executing SQL over Hive-partitioned Parquet under `datasets/<family>/` fetched via HTTP Range. **No JSON projections of canonical data.** Pre-pivot per-shard JSON (per-event `datasets/elections/<event>/<state>/{results/<ac>.json,parties.json,result.summary.json}`) is **superseded** by the canonical Parquet but still sits on disk pending the per-family cleanup sub-rows (THE PLAN 1.8b–1.8f); no new readers are allowed against that shape. See [`docs/architecture/canonical-pivot-deletion-manifest.md`](../../docs/architecture/canonical-pivot-deletion-manifest.md).
- Citizen-visible URL grammar is preserved across the pivot — only the loader internals change (touch points: `src/lib/data.ts`, `src/lib/paths.ts:15`).
- Citizen-visible route changes need frontend tests and integrated-browser smoke verification per [CLAUDE.md](../../CLAUDE.md#13-ui-verification-mandatory-for-frontend--admin-changes).
- Catalogue-driven UI should read schemas/catalogues instead of hardcoding one-off dataset lists.

## Validation

- Run `npm test` in `frontend/` for frontend code changes.
- Run `npm run test:e2e` in `frontend/` for citizen-visible route changes.
- If package manifests change, regenerate and stage the matching `bun.lock`.
