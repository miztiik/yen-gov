# X1a-followup-2: residual parquet readers - scoping + handover

**Date**: 2026-06-07
**Status**: SCOPED-NOT-SHIPPED (this PR documents the work; subsequent PRs ship per-row)
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) Execution ledger row `X1a-followup elections residuals` STOP-AND-SURFACE
**Sibling**: [TODO/20260606-handover-prompt-data-charting-reset.md](20260606-handover-prompt-data-charting-reset.md)

## Premise

X1a (PR #809) + X1a-followup (PR #811) + X1b (PR #814) + YA-apply (PR #813) flipped most production parquet reads onto CSV. Five residual parquet readers survive across 4 frontend files. The user's 2026-06-07 directive ("fix these in the style of the original plan ship-loop autonomous agents") authorises the next pass.

Each row below carries one of: **(a) reader-only CSV swap** (CSV emit already shipped under `datasets/data/`; mechanical reader flip), or **(b) BLOCKED-NEEDS-CSV-EMIT** (the canonical CSV does NOT exist yet; a B2b-family writer must ship first).

## The 5 residual parquets + their readers

| # | Parquet | Frontend reader(s) | CSV emit status | Action |
| --- | --- | --- | --- | --- |
| 1 | `datasets/elections/state=in_<S>/election_results.parquet` | (a) `frontend/src/lib/charts/composition-bar/adapter-elections-seats.ts:181` `registerSlice` <br> (b) `frontend/src/lib/view-models/election-seats-trend.ts:92` `registerSlice` <br> (c) `frontend/src/lib/view-models/india-leading-parties.ts:60` `registerTable` | **PARTIAL** - `summary.csv` + `candidacies.csv` exist per (state, year) but NOT the long-format observation rows the parquet carries (winner_party_id, margin_pct, votes_polled, turnout_pct as per-AC obs rows) | **BLOCKED-NEEDS-CSV-EMIT** - a new B2b writer must transcode `election_results.parquet` to either (i) one wide per-AC CSV (`datasets/data/datapoints/elections/...`) or (ii) join the existing `summary.csv` + `candidacies.csv` at view-model time. (i) is mechanical but doubles disk; (ii) is cheap but more SQL in each view-model. **Recommend option (ii)**: rewrite each of the 3 readers to compose from the existing CSVs via DuckDB-WASM JOINs. Per-route §13 smoke MANDATORY. |
| 2 | `datasets/elections/dim_party_alliances.parquet` | `frontend/src/lib/view-models/state-overview.ts:200` `registerTable` | **MISSING** - no `data/entities/party_alliances.csv` today | **BLOCKED-NEEDS-CSV-EMIT** - author `backend/yen_gov/canonical/party_alliances_csv.py` (B2a-style hand-authored CSV from `datasets/taxonomy/parties.json` alliance fields) + add to manifest + add reader flip in state-overview.ts. |
| 3 | `datasets/taxonomy/entities.parquet` | (a) `frontend/src/lib/view-models/districts.ts:64,157` `registerTable` <br> (b) `frontend/src/lib/view-models/states.ts:142` `registerTable` <br> (c) `frontend/src/lib/canonical/indicator-from-canonical.ts:310,360` `registerTable(descriptor.table_id)` (only fires for allowlisted indicators that opt-in via `descriptor.table_id`) | **READY** - `datasets/data/entities/geo.csv` already emitted (per `office_holdings_seed`/B2a). Today the parquet has 857 rows after my B3-followup run; the CSV has different shape per OWID adoption (3-CSV `geo.csv` + `electoral.csv` + `state_codes.csv`). Per (a)(b) `loadDistricts` / `loadStates` already-CSV path via `registerCsvAsTable`-style seam exists for parties+sources; same pattern applies. | **READY-TO-FLIP** - rewrite `view-models/districts.ts` + `view-models/states.ts` to inline `read_csv('datasets/data/entities/geo.csv', columns={...})` filtered by `entity_kind` (the X1a-followup precedent at `view-models/ac-crosswalk.ts:10`). Update `vi.mock("../duckdb", ...)` factories. Update `lib/duckdb.ts:76` to drop the `"taxonomy.entities": "entity.schema.json"` line. |
| 4 | `datasets/taxonomy/indicators.parquet` | (none in `registerTable("taxonomy.indicators")` form today; the parquet IS still emitted by `cli.py emit-taxonomy` step 7, and the existing `canonical/indicator-allowlist.ts` + `indicator-from-canonical.ts` use `descriptor.table_id` which CAN reference it) | **PARTIAL** - `datasets/data/variables.csv` already emitted (the long-format catalogue). The parquet is largely redundant with the CSV. | **DEFER** - the citizen reader path goes through `indicator-allowlist.ts`. Audit per-descriptor `table_id` strings; flip any `taxonomy.indicators` references to `variables.csv`. ZERO live frontend readers as of 2026-06-07 grep. Safe to retire the parquet WITHOUT a reader flip - just stop emitting it in cli.py step 7 + delete the file. |
| 5 | `datasets/boundaries/boundary_layers.parquet` | (a) `frontend/src/lib/boundaries.ts:32` documentation comment <br> (b) `frontend/src/lib/boundaries.contract.test.ts:4` contract assertion <br> (c) `frontend/src/lib/boundaries.integration.test.ts:5` integration assertion <br> (d) `frontend/src/contracts/boundaries-conform.test.ts:132,142,143` schema + path conformance | **PARTIAL** - the parquet carries provenance + simplification + inventory for every boundary geojson (per ADR-0031 Amendment 2026-05-22). A `data/entities/boundary_layer.csv` does NOT exist today. | **BLOCKED-NEEDS-CSV-EMIT** - lift `boundary_layers.parquet` to `data/entities/boundary_layer.csv` via a new `backend/yen_gov/canonical/boundary_layers_csv.py` (B2a-style emit from `boundary_layers_seed.py` build_rows result). The geojson files themselves are NOT migrated (they're geometry, not tabular). Reader-flip across 4 frontend files. Last in queue because the contract surface is the largest. |

## Per-row ship plan (sub-rows in execution order)

### Sub-row X1a-fu2-A: `taxonomy/entities` reader flip (READY-TO-FLIP)

**Estimated effort**: medium. Reads: 4 frontend files + 1 test file. CSV exists.

1. Read `data/entities/geo.csv` schema from `datasets/data/_schema/columns.json` (probably ~7 columns: `entity_id, name, parent, entity_kind, aliases, lgd_code, iso_3166_2`).
2. Rewrite `view-models/states.ts::loadStates()`:
   - Replace `await registerTable("taxonomy.entities"); query<...>("SELECT ... FROM entities WHERE entity_type='state' OR entity_type='ut' ...")` with inline `query<...>("SELECT entity_id, name, ... FROM read_csv('datasets/data/entities/geo.csv', columns={...}) WHERE entity_kind='state'")`.
   - Drop `registerTable` import if no other caller in the file.
3. Same for `view-models/districts.ts::loadDistricts(state_slug)` - filter `entity_kind='district' AND parent='<state>'`. Note: `parent` column on geo.csv carries the parent slug NOT the `IN-<eci_code>` form; verify the join key.
4. `canonical/indicator-from-canonical.ts` lines 310 + 360 use `descriptor.table_id` from allowlist - if any descriptor declares `table_id: "taxonomy.entities"`, flip that descriptor too (likely zero hits; grep first).
5. Update `lib/duckdb.ts:76` `_TABLE_TO_SCHEMA["taxonomy.entities"]` to remove or redirect.
6. Update `view-models/districts.test.ts` + `view-models/states.test.ts` mocks: drop `mockedRegister.toHaveBeenCalledWith("taxonomy.entities")` assertions; the new path uses inline `query` so no `registerTable` call site.
7. §13 §13 browser smoke MANDATORY on `/home`, `/india`, `/india/tamil-nadu`, `/india/tamil-nadu/chennai` (any district route).

Gates: `dual-read-parity`-style assertion (add to `backend/tests/test_dual_read_parity.py` if file survives, else inline check at view-model boundary); §13 smoke 0 parquet requests + ≥1 CSV request.

Then: drop `datasets/taxonomy/entities.parquet` emit from `cli.py emit-taxonomy` step 5 + `git rm` the file. (Note: this is downstream from B3-followup, which made step 6 stop emitting parquets to disk; step 5 still does.) Audit whether the in-process tempdir + CSV emit pattern from B3-followup applies here too - probably yes since `entities_seed.compile_to_parquet` is structurally similar.

### Sub-row X1a-fu2-B: `taxonomy/indicators` quiet retirement (zero-reader)

**Estimated effort**: trivial. Reads: zero live frontend.

1. Grep `frontend/src/**` for `taxonomy.indicators` - confirm zero `registerTable` call.
2. Grep `canonical/indicator-allowlist.ts` for any descriptor's `table_id: "taxonomy.indicators"` - confirm zero.
3. Drop step 7 `_compile_indicators` call from `cli.py emit-taxonomy`.
4. `git rm datasets/taxonomy/indicators.parquet`.
5. Audit AGENTS.md + canonical-store.md + indicator-naming.md for stale references.
6. Update manifest if it lists the table.

Gates: pytest baseline-identical. No frontend smoke needed (zero readers).

### Sub-row X1a-fu2-C: `elections/dim_party_alliances` reader flip (CSV WRITE + READER FLIP)

**Estimated effort**: medium. Reads: 1 frontend file. CSV needs authoring.

1. Author `backend/yen_gov/canonical/party_alliances_csv.py` - hand-authored CSV emit from `datasets/taxonomy/parties.json` alliance fields (`primary_alliance`, `historical_alliances[]`). Output: `datasets/data/entities/party_alliances.csv` with columns `party_id, alliance_id, alliance_name, from_year, to_year` (long-format).
2. Add cli.py command or fold into `emit-taxonomy` step 5b (after entities).
3. Rewrite `view-models/state-overview.ts:200` to inline `read_csv('datasets/data/entities/party_alliances.csv', columns={...})` filtered as needed.
4. Update test mock `vi.mock("../duckdb", ...)` to drop the `registerTable("elections.dim_party_alliances")` expectation.
5. `git rm datasets/elections/dim_party_alliances.parquet` + drop writer from `canonical/writer.py`.
6. §13 smoke on `/india/<any-state>`.

Gates: dual-read-parity assertion; §13 smoke ZERO parquet, ≥1 CSV.

### Sub-row X1a-fu2-D: `elections/election_results` per-AC observation reader flip (LARGEST - 3 readers)

**Estimated effort**: large (decide CSV-emit vs join-at-view-model first).

**Decision needed**: option (i) wide CSV emit (~50MB) vs option (ii) JOIN at view-model time. **Recommend (ii)** per `summary.csv` + `candidacies.csv` already carrying the underlying facts; per-AC `winner_party_id`/`margin_pct`/`votes_polled` are recomputable in SQL via `SELECT ... FROM summary.csv JOIN candidacies.csv USING (state, year, ac_no)`.

1. **Audit pass**: for each of the 3 readers, inventory the SELECT columns they pull from `election_results.parquet`. If any column is NOT recomputable from summary+candidacies, ship option (i) for that column (write a single new CSV).
2. **Rewrite** `composition-bar/adapter-elections-seats.ts:181`, `view-models/election-seats-trend.ts:92`, `view-models/india-leading-parties.ts:60` - replace `registerSlice("elections.election_results", ...)` / `registerTable(...)` with inline `read_csv` JOINs.
3. **Update tests**: 3+ test files (`adapter-elections-seats.test.ts`, `election-seats-trend.test.ts`, `india-leading-parties.test.ts`).
4. **Delete parquets**: `datasets/elections/state=*/election_results.parquet` (1 per state). The Hive partition tree retires too.
5. **Strip writer**: `backend/yen_gov/canonical/writer.py::_emit_observations` retires the per-state shard logic.
6. §13 smoke on `/india`, `/india/<state>`, `/india/<state>/ac/<N>`, `/lab/election-experience` if any election-page route survives.

Gates: dual-read-parity assertion for each of the 3 view-models; §13 smoke ZERO `election_results` requests + per-route CSV count.

**STOP-AND-SURFACE**: if any view-model needs a column NOT recomputable from summary+candidacies, surface to user with the column name + recommend per-column CSV emit.

### Sub-row X1a-fu2-E: `boundaries/boundary_layers` CSV emit + reader flip (LAST; CONTRACT-HEAVY)

**Estimated effort**: large. Reads: 4 frontend test files + 1 production comment.

1. Author `backend/yen_gov/canonical/boundary_layers_csv.py` - lift `boundary_layers_seed.build_rows()` result to `data/entities/boundary_layer.csv`. Same columns as the parquet (15 cols per ADR-0031). FK to `data/entities/source.csv`.
2. Add to `cli.py boundaries-snapshot` flow or new `lift-boundaries` command.
3. **No production frontend reader** (parquet only consumed by tests today). Rewrite the 4 test files to assert against the CSV instead.
4. `git rm datasets/boundaries/boundary_layers.parquet`.
5. Drop writer from `boundary_layers_seed.py` (use the B3-followup tempdir-detour pattern if in-process tests still need parquet shape).
6. Update `boundaries-conform.test.ts` schema + path conformance assertions to point at the CSV.

Gates: every boundary geojson under `datasets/boundaries/**` still has a `data/entities/boundary_layer.csv` row asserting provenance + simplification metadata; cross-format parity if a partial CSV exists in the interim.

## Sequencing rationale

A → B → C → D → E in **increasing blast radius**. A + B are mechanical and ship in 1-2 PRs each; C + D + E each need a CSV-writer authoring + a reader flip + tests + smoke. C + D + E should each be a separate PR with their own STOP-AND-SURFACE on any new data-shape question.

## Ship discipline

Per umbrella plan section 22.3 + 22.6:
- Each sub-row gets its own branch (e.g. `feat/x1a-fu2-A-entities-csv-flip`).
- Per-chunk DoD: writer-unit + dual-read-parity + §13 smoke + AGENTS.md doctrine-marker-audit.
- `gh pr merge --squash --admin --delete-branch` admin-merge ONLY when vitest + build + targeted §13 smoke all green.
- The user's 2026-06-07 directive ("DO NOT WAIT FOR REMOTE PR MERGE. IF LOCAL testing is successful move forward") authorises local-only ship at the green-gate boundary.

## Out-of-scope (deferred to a later session)

- `dim_acs` + `dim_persons` + `dim_candidates` remaining canonical-allowlist readers per `indicator-from-canonical.ts`. The allowlist seam IS itself a future migration target but is its own arc (it has its own backend writers + entity-id translation logic).
- Any historical schema retention - `datasets/schemas/archive/...` stays.
- The `_emit_observations` per-state shard logic in `writer.py` - retires WITH X1a-fu2-D, not before.

## Local-test gates that survive the chunk sequence

- `pytest -q --deselect=<standing-list>`: 40-fail baseline (per CLAUDE.md test flakes section). No new failures per chunk.
- `bun run test` (frontend vitest): full suite green or strict-improvement; specific test file deltas per chunk.
- `bun run build`: green.
- §13 in-browser smoke (`bun run dev` + Playwright): 0 console errors, 0 failed requests, expected URL transfer counts per chunk.

## Status

- **Sub-row X1a-fu2-A** entities reader flip: **READY** (CSV exists, just needs reader rewrite + test mock update).
- **Sub-row X1a-fu2-B** indicators quiet retirement: **READY** (zero readers; drop emit + delete file + audit doctrine).
- **Sub-row X1a-fu2-C** dim_party_alliances: **READY-WITH-WRITE** (needs CSV writer authored first).
- **Sub-row X1a-fu2-D** election_results: **NEEDS-DECISION** (option (i) vs (ii)) + ship.
- **Sub-row X1a-fu2-E** boundary_layers: **READY-WITH-WRITE** + reader-flip + test rewrite.

Next session: pick A or B first (cheapest); spawn subagent per sub-row; user signoff before D unless option (ii) confirmed cheap enough.
