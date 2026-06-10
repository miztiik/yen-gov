# AGENTS.md - frontend/src

**Last Updated**: 2026-06-08

Canonical frontend rationale lives in `docs/architecture/frontend/`; this file is only a fast module map for agents.

ASCII only: use plain keyboard characters; write "-", "->", ">=", "section", and "INR" instead of fancy symbols.

> **MIGRATING (2026-06-04, updated 2026-06-08 post-X1a + X1b + X1a-followup + YA-apply + X1a-fu2 A/B/C/D/E).** Per the [CLAUDE.md](../../CLAUDE.md) doctrine-in-migration banner + [the platform-reset plan](../../TODO/20260603-data-and-charting-platform-reset-plan.md), the production read path is moving from Hive-partitioned Parquet to long-format CSV under `datasets/data/`, read via DuckDB-WASM `read_csv(columns=...)`. X1a flipped the `dim_parties` + `taxonomy.sources` readers + every F1.3 view-model (constituency / state-overview / national-elections / psephlab / explore / yenask) onto the canonical CSV store via the `registerCsvAsTable` seam in `lib/duckdb.ts`. X1b (#814) retired the 14 zero-reader parquets (dim_acs, elections_candidacies, dim_persons, ac_crosswalk, etc.). X1a-fu2 (2026-06-07) retired the final 5 residual parquets and flipped every remaining reader: A=`entities` -> `data/entities/geo.csv` + `data/entities/electoral.csv`; B=`indicators` (zero-reader quiet retirement); C=`dim_party_alliances` -> `data/entities/party_alliances.csv`; D=`election_results` (36 state shards) -> per-state CSV under `data/datapoints/electoral/<slug>_election_results.csv`; E=`boundary_layers` -> `data/entities/boundary_layer.csv` (no frontend reader pre-rip; inventory ledger only). **ZERO residual canonical parquet reads remain.** Still NO JSON projections of canonical data.

## Canonical Docs

- [Frontend overview](../../docs/architecture/frontend/overview.md)
- [Frontend data loading](../../docs/architecture/frontend/data-loading.md)
- [Indicators UI](../../docs/architecture/frontend/indicators.md)
- [Map architecture](../../docs/architecture/frontend/map.md)
- [Colour system](../../docs/architecture/frontend/colours.md)
- [Compare flows](../../docs/architecture/frontend/compare.md)
- [Deployment](../../docs/architecture/deployment.md)
- [Canonical store (long-format CSV + DuckDB-WASM)](../../docs/architecture/data/canonical-store.md) - runtime data path (ZERO residual parquet reads post-X1a-fu2 2026-06-07; all reads use `data/entities/*.csv` + `data/datapoints/{geo,electoral}/*.csv` + a small set of typed JSON for taxonomy)

## Invariants

- Static GitHub Pages app; anything needed at runtime ships in the bundle (including the DuckDB-WASM engine).
- Do not import from `backend/`.
- Do not commit generated data from `frontend/`; the only writer of `datasets/` is `backend/`.
- **Canonical pivot.** Production read path is DuckDB-WASM in the browser executing SQL over long-format CSV under `datasets/data/` via `read_csv(columns=...)` for X1a-flipped surfaces (per-(state,year) candidacies + summary CSV; `dim_parties` via `registerCsvAsTable('elections.dim_parties')` -> `data/entities/parties.csv`; `taxonomy.sources` via `registerCsvAsTable('taxonomy.sources')` -> `data/entities/source.csv`). Post-X1a-fu2 (2026-06-07): ZERO residual canonical parquet reads. The X1b + X1a-fu2 sweeps cleared `dim_acs`, `elections_candidacies`, `dim_persons`, `ac_crosswalk`, `entities`, `indicators`, `dim_party_alliances`, `election_results`, `boundary_layers` - all now CSV (or zero-reader quiet retirement for `indicators`). **No JSON projections of canonical data.** Pre-pivot per-shard JSON (per-event `datasets/elections/<event>/<state>/{results/<ac>.json,parties.json,result.summary.json}`) is **superseded**; no new readers are allowed against that shape. See [`docs/architecture/canonical-pivot-deletion-manifest.md`](../../docs/architecture/canonical-pivot-deletion-manifest.md).
- Citizen-visible URL grammar is preserved across the pivot - only the loader internals change (touch points: `src/lib/data.ts`, `src/lib/paths.ts:15`).
- Citizen-visible route changes need frontend tests and integrated-browser smoke verification per [CLAUDE.md](../../CLAUDE.md#13-ui-verification-mandatory-for-frontend--admin-changes).
- Catalogue-driven UI should read schemas/catalogues instead of hardcoding one-off dataset lists.

## View-model collapse - `loadElectionResults(scope)` is canonical

PR-W2b (2026-06-10) introduced the generic
[view-models/election-results.ts](lib/view-models/election-results.ts):
`loadElectionResults({event, state?, eci_no?})`. This is the canonical
loader for any election-results query (NATIONAL-PC, STATE-AC, CONSTITUENCY
drill-down). The three bespoke loaders covered by the golden-row oracle
(`loadNationalPcWinners`, `loadStateAcWinners`, `loadConstituencyResult`)
stay live for one release; call-sites flip in PR-W3b / PR-W3c / PR-W3d;
bespoke loaders deleted in PR-W5a.

Use `loadElectionResults` for any NEW code. The two projection helpers
(`projectAsWinnersByEntity`, `projectAsConstituencyRanks`) narrow the
union row shape to the bespoke-loader shapes when the caller needs them.
Do not import the bespoke loaders in new files.

`loadIndiaLeadingParties` is INTENTIONALLY OUT OF SCOPE for this collapse:
it reads a different underlying table (the long-format party-aggregate
CSV under `data/datapoints/electoral/`), takes a multi-event map, and
answers a structurally different question. It stays bespoke until a
future PR either widens the generic to a fourth scope shape or leaves
it as a separate concern.

## Validation

- Run `npm test` in `frontend/` for frontend code changes.
- Run `npm run test:e2e` in `frontend/` for citizen-visible route changes.
- If package manifests change, regenerate and stage the matching `bun.lock`.
