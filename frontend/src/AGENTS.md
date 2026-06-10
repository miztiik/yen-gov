# AGENTS.md - frontend/src

**Last Updated**: 2026-06-10

Canonical frontend rationale lives in `docs/architecture/frontend/`. This file is only a fast module map for agents.

ASCII only: use plain keyboard characters; write "-", "->", ">=", "section", and "INR" instead of fancy symbols.

> **Current canonical store.** The production read path is DuckDB-WASM in the browser executing SQL over long-format CSV under `datasets/data/` via typed `read_csv(columns=...)`. There are zero residual canonical Parquet reads. No JSON projections of canonical data.

## Canonical Docs

- [Frontend overview](../../docs/architecture/frontend/overview.md)
- [Frontend data loading](../../docs/architecture/frontend/data-loading.md)
- [Indicators UI](../../docs/architecture/frontend/indicators.md)
- [Map architecture](../../docs/architecture/frontend/map.md)
- [Colour system](../../docs/architecture/frontend/colours.md)
- [Compare flows](../../docs/architecture/frontend/compare.md)
- [Deployment](../../docs/architecture/deployment.md)
- [Canonical store](../../docs/architecture/data/canonical-store.md)
- [CSV column contract](../../docs/architecture/data/csv-column-contract.md)

## Invariants

- Static GitHub Pages app; anything needed at runtime ships in the bundle, including DuckDB-WASM.
- Do not import from `backend/`.
- Do not commit generated data from `frontend/`; the only writer of `datasets/` is `backend/`.
- Read canonical CSV through typed DuckDB seams (`read_csv(columns=...)`, `registerCsvAsTable`, and per-view-model loaders). Do not fetch retired JSON shards or guess dataset paths.
- Retired canonical-pivot surfaces are not current authority. The live blockers are validator gates, allowlists under `datasets/_ops/`, and the owning subsystem docs.
- Citizen-visible URL grammar is preserved across data-store changes; only loader internals should change.
- Citizen-visible route changes need frontend tests and integrated-browser smoke verification per [CLAUDE.md](../../CLAUDE.md#13-ui-verification-mandatory-for-frontend--admin-changes).
- Catalogue-driven UI should read schemas/catalogues instead of hardcoding one-off dataset lists.

## View-model collapse - `loadElectionResults(scope)` is canonical

PR-W2b (2026-06-10) introduced the generic [view-models/election-results.ts](lib/view-models/election-results.ts): `loadElectionResults({event, state?, eci_no?})`. This is the canonical loader for election-results queries at NATIONAL-PC, STATE-AC, and CONSTITUENCY scopes. All W3 + W4 call-sites flipped to the generic loader.

PR-W5a (2026-06-10) retired the bespoke loaders that had been replaced end-to-end and moved the two not yet replaced to `view-models/legacy/`:

- `loadNationalPcWinners` - deleted. New code uses `loadElectionResults({event})`.
- `loadStateAcWinners` - deleted. New code uses `loadElectionResults({event, state})` plus projection helpers.
- `loadConstituencyResult` - kept under [view-models/legacy/constituency.ts](lib/view-models/legacy/constituency.ts) because `Constituency.svelte` still needs candidate bio, symbol asset, margin votes, NOTA split, top-N, and others bucket fields.
- `loadIndiaLeadingParties` - kept under [view-models/legacy/india-leading-parties.ts](lib/view-models/legacy/india-leading-parties.ts) because it reads party-aggregate CSV and accepts a multi-event `Record<state, event>` map.

Use `loadElectionResults` for any new election-results work. Do not import legacy loaders in new files.

## Validation

- Run `npm test` in `frontend/` for frontend code changes.
- Run `npm run test:e2e` in `frontend/` for citizen-visible route changes.
- If package manifests change, regenerate and stage the matching `bun.lock`.
