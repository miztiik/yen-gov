# F1 sub-plan - CSV loaders + parity-oracle rewrite

**Last Updated**: 2026-06-05
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk F1
**Status**: IN-FLIGHT (spawned 2026-06-05 after B2b.6 closure #776 unblocked F1)
**Authority**: Gregor (reader contract, query surface, FK seam) / Fowler (writer-side cutover sequence, test tier) per CLAUDE.md section 0a

---

## Why this exists

Parent chunk F1 reads as one row in the parent Execution Ledger (22.5) - "CSV loaders + oracle-rewrite". But the actual delivery is FOUR distinct surfaces that each need their own diff + gate:

1. **Backend parity oracle rewrite.** `backend/tests/test_canonical_parity_oracle.py` reads four Parquet files (`election_results.parquet`, `elections_candidacies.parquet`, `dim_persons.parquet`, `dim_acs.parquet`) under `datasets/elections/` and asserts per-AC FPTP winner + margin against the frozen `canonical_winners_2026_05_19.json` fixture. The same fixture is the post-X1a oracle, so the test must re-target the NEW long-format CSV under `datasets/elections/assembly/state=<slug>/election=<yr>/{candidacies,summary}.csv` (per plan 21.3, already shipped by B2b.5.x).
2. **Frontend loader seam.** `frontend/src/lib/canonical/duckdb.ts` exposes `queryParquet<T>(sql)` and its caller-template uses `read_parquet('datasets/<family>/<table>.parquet')`. Per plan 21.5, the function name + caller-template must flip to `queryCsv(sql)` issuing `read_csv('datasets/data/<...>.csv', columns=...)` against the new long-format files. `indicator-allowlist.ts` carries doctrine references to `<family>/<table>.parquet` that need rewording to `datasets/data/datapoints/<class>/<variable_id>.csv`.
3. **Frontend view-model SQL flip.** Six call sites in `frontend/src/lib/{view-models,psephlab,explore,yenask}/*.ts` issue `read_parquet(...)` SQL joining `dim_persons`, `dim_acs`, `elections_candidacies`, `election_results`. These must flip to `read_csv(columns=...)` over the per-(state,year) candidacies + entities/electoral.csv layout per 21.3. Biographic cols (`sex, age, education, profession`) move from the `dim_persons` JOIN (about to be deleted) to inline columns on `candidacies.csv` per 21.3.
4. **Closure.** Distil the seam shape into [docs/architecture/frontend/data-loading.md](../docs/architecture/frontend/data-loading.md) + [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md) "Parity oracle" section; flip parent ledger F1 row to MERGED; archive this sub-plan to `docs/archive/plans/`.

Per CLAUDE.md correction-level discipline (>=4 files structural -> propose breakdown first) and parent plan section 24.5, the right shape is a thin parent row + this sub-plan. Same pattern as U1 / U2 / U5 / B1 / B2a / B2b / B2b.4 / B2b.5 / D-DOC3.

This sub-plan is the merge-queue authority for F1. The parent ledger row stays `DEFERRED-TO-SUBPLAN` until F1.4 (closure) merges, at which point parent flips to `MERGED` with the closure PR# stamped.

## Scope

In scope: the four surfaces above. Each is a separate PR with its own branch, its own gate, and its own §13 in-browser smoke (where it touches a citizen route).

Out of scope (deliberately deferred to other chunks):

- **X1a reader flip** (the binding cutover that says "the citizen frontend reads CSV, not Parquet, from this commit onwards"). That's its own PR + dual-read-parity gate per 22.6. F1 lays down the CSV loaders but leaves the Parquet readers ALSO in place until X1a flips the seam atomically.
- **X1b parquet delete + kill-50MB measurement**: blocks on X1a.
- **B3 / B4 producer + fetch deletions**: block on X1b.
- **Render / chart chunks (F2*/F3/F4)**: block on X1b.
- **YA yen-ask re-point**: blocks on F1.3 (yenask/concepts.ts) + X1a.

## Sub-row Execution Ledger

| Sub-row | Blocks on | Gate | PR# | Status |
| --- | --- | --- | --- | --- |
| F1.1 backend parity-oracle rewrite (`backend/tests/test_canonical_parity_oracle.py` reads CSV; same `canonical_winners_2026_05_19.json` fixture; same per-AC zero-tolerance assertion) | - | parity-oracle-CSV + oracle-non-skip (must actually RUN, not skipif-parquet-absent) | - | TODO |
| F1.2 frontend loader seam (`canonical/duckdb.ts` `queryParquet` -> `queryCsv`; `canonical/indicator-allowlist.ts` docstring + descriptor doctrine scrub; `canonical/manifest.ts` if it carries parquet path references) | - | loader-unit (vitest) + §13 in-browser smoke on one canonical-backed route | _pending_ | IN-FLIGHT |
| F1.3 frontend view-model SQL flip (6 callers: `view-models/constituency.ts`, `psephlab/canonical-loaders.ts`, `view-models/state-overview.ts`, `view-models/national-elections.ts`, `yenask/concepts.ts`, `explore/duckdb-views.ts`) | F1.2 | per-view-model vitest + §13 in-browser smoke on 3 routes (StateOverview, National, Constituency) | - | TODO |
| F1.4 close sub-plan (flip parent F1 row to MERGED; distil seam shape into [docs/architecture/frontend/data-loading.md](../docs/architecture/frontend/data-loading.md) + [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md) "Parity oracle" section; archive this sub-plan to `docs/archive/plans/`) | F1.1, F1.2, F1.3 | docs-review | - | TODO |

Parallel-safe groups:

- Wave A (no blockers): F1.1, F1.2. Independent (backend vs frontend; different file trees). F1.2 may ship before F1.3 because the 6 view-models still issue `read_parquet(...)` SQL against the surviving Parquet (the duckdb.ts API rename is the only F1.2 surface).
- F1.3 blocks on F1.2 (the 6 view-models will call the new `queryCsv` helper signed by F1.2's API rename).
- Closure: F1.4.

If F1.3 grows beyond one PR (6 view-models x non-trivial SQL rewrites + 6 vitest updates + 3 in-browser smokes), spawn a sub-sub-plan `TODO/20260605-f1-3-view-model-sql-flip-subplan.md` with per-view-model rows per 24.5.

## Per-sub-row notes

### F1.1 backend parity-oracle rewrite

Reads (today):

- `datasets/elections/election_results.parquet`
- `datasets/elections/elections_candidacies.parquet`
- `datasets/elections/dim_persons.parquet`
- `datasets/elections/dim_acs.parquet`

Reads (after rewrite):

- `datasets/elections/assembly/state=<slug>/election=<yr>/candidacies.csv` (per 21.3; emitted by B2b.5.2-5.3)
- `datasets/data/entities/electoral.csv` (AC + PC structure; emitted by B2b.5.0c)
- `datasets/data/entities/state_codes.csv` (LGD spine; emitted by B2b.5.0b)
- Frozen fixture: `backend/tests/fixtures/canonical_winners_2026_05_19.json` (unchanged - the trust anchor)

Rewrite shape: DuckDB SQL changes from `read_parquet(...)` four-way JOIN to a per-slice CSV scan + `entities/electoral.csv` join for AC labels. The fixture key shape `(event_id, state_code)` may need re-projection from the candidacies.csv key `(election_year, state)` - one column rename, one type cast (year int vs event_id string). NOTA exclusion identical. Per-AC zero-tolerance assertion unchanged.

Skipif condition flips from "parquet absent" to "CSV absent". `oracle-non-skip` gate (per 22.6) asserts the test ACTUALLY RUNS in CI (not skipped) - one assertion: `assert SLICES, "parity fixture not on disk"` becomes a hard failure not a skip, because after X1a the CSV path is mandatory.

### F1.2 frontend loader seam

`canonical/duckdb.ts` changes:

- Rename `queryParquet<T>(sql)` -> `queryCsv<T>(sql)`. Callers (F1.3 territory) update in subsequent PR. F1.2 ships the rename PLUS a deprecation re-export `export const queryParquet = queryCsv` so the existing 6 callers keep compiling until F1.3 lands.
- Internal SQL handling unchanged (still `con.query(sql)`; the rename is API-naming only). DuckDB-WASM `read_csv(...)` is already supported by the WASM bundle without code change.
- Doc-comment scrub: line 40 says "read_parquet(...)" - flip to "read_csv(...)".

`canonical/indicator-allowlist.ts` changes:

- Doctrine block (lines 1-65) references `/data/<family>/<table>.parquet` in three places - flip to `/data/datapoints/<class>/<variable_id>.csv`.
- `table_id: "energy.energy_demand_supply"` field semantics: in the CSV world, `table_id` no longer maps to a Parquet "family.table" - it maps to a per-variable CSV path. Decide: rename field to `csv_path` or keep `table_id` semantically as the variable's canonical path-fragment. Land the decision in the PR body; mirror in `indicator-from-canonical.ts` and the test fixtures.
- Two `canonical_indicator_id`s in scope: `peak-electricity-demand-mw` + `peak-electricity-supplied-mw`. Both already have canonical CSV siblings under `datasets/data/datapoints/geo/` (emitted by B2b.1 energy reingest #691).

`canonical/manifest.ts` changes:

- The manifest tracks "which canonical artifacts exist" - currently entries point at `<family>/<table>.parquet`. Flip to long-format CSV paths.
- `manifest.test.ts` fixtures (line 26: `elections/election_results.parquet`) update to per-(state,year) CSV references.

Gate: vitest pass; one §13 smoke on the `/s/<state>` page that mounts `IndicatorCard` for `state-peak-electricity-demand-mw` (Phase B precedent route from PR #171); verify zero new console errors + zero failed requests for the legacy Parquet path.

### F1.3 frontend view-model SQL flip

Six call sites. Each issues SQL of shape `SELECT ... FROM read_parquet('elections_candidacies.parquet') ec JOIN read_parquet('dim_persons.parquet') p ON p.person_id = ec.person_id ...`. The new shape uses the per-election CSV directly:

```sql
SELECT ... FROM read_csv('datasets/elections/assembly/state=<slug>/election=<yr>/candidacies.csv', columns={...}) ec
  JOIN read_csv('datasets/data/entities/electoral.csv', columns={...}) e ON e.entity_id = ec.entity_id
```

Biographic cols (`sex, age, education, profession`) are NOW on `candidacies.csv` directly (per 21.3); the `dim_persons` JOIN dies in this PR. The `display_name` lookup ALSO dies (candidacies.csv carries `candidate_name`). This is the migration the B2b.4.7 DROP receipt anticipated.

Per-file SQL rewrites:

- `view-models/constituency.ts` (line 163 JOIN): drop `dim_persons` join; project `ec.sex, ec.age, ec.education, ec.profession, ec.candidate_name`.
- `psephlab/canonical-loaders.ts` (line 151 JOIN): same drop.
- `view-models/state-overview.ts` (line 355 LEFT JOIN): same drop.
- `view-models/national-elections.ts` (line 136 LEFT JOIN): same drop; parliament CSV under `datasets/elections/parliament/election=<yr>/candidacies.csv` per 21.3 (no state shard).
- `yenask/concepts.ts` (line 236 JOIN): same drop; 4 concept SQL templates re-pointed per YA1 directive (parent plan §181).
- `explore/duckdb-views.ts` (line 110 JOIN): same drop; Explore concept view re-bound to CSV.

Per-view-model vitest updates: existing tests already mock `queryParquet` -> rename to `queryCsv` per F1.2's deprecation re-export.

In-browser §13 smoke (3 routes): `/s/tamil-nadu` (state overview); `/s/tamil-nadu/c/AC-1-thiruvallur` (constituency); `/?election=ge2024` or similar national-elections route. Verify (a) candidate names render verbatim from candidacies.csv, (b) biographic cols (age, education, profession) render unchanged from the new inline path, (c) ZERO requests for `dim_persons.parquet`, `elections_candidacies.parquet`, `election_results.parquet`, `dim_acs.parquet`, (d) at least one request for the per-(state,year) candidacies.csv + entities/electoral.csv.

### F1.4 closure

- Extend [docs/architecture/frontend/data-loading.md](../docs/architecture/frontend/data-loading.md) with a "CSV loader seam" section listing the four surfaces lifted in F1.1..F1.3 and the new `queryCsv` API.
- Extend [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md) "Parity oracle" section with the new CSV-shape SQL + fixture invariants.
- Flip the parent F1 ledger row to MERGED in this same PR and stamp the closure PR number.
- Archive this sub-plan to `docs/archive/plans/20260605-f1-csv-loaders-and-oracle-rewrite-subplan.md` with a "Plan complete" block per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).
- Confirm: X1a (reader flip) may now proceed because both the backend oracle AND the frontend canonical/+view-model layer read CSV; the legacy Parquet readers SURVIVE in-tree (as the `queryParquet` deprecation alias) so X1a's dual-read-parity gate has both formats to compare.

## Contract invariants (inherited from parent 21.5 / 22.4)

1. **Typed read at the boundary.** Every `read_csv(...)` call passes the `columns={...}` map generated from `datasets/data/_schema/columns.json`. The frontend never `read_csv_auto`s. The map generator + a vitest assertion ("for every file_class in columns.json, the frontend codegen produces a matching `read_csv` columns map") ship in F1.2.
2. **Provenance preserved.** Every row returned from a `queryCsv` call carries `source_id` resolvable via `entities/source.csv` (the FK is enforced at the writer; the reader just respects it).
3. **No mocks at the seam.** `duckdb.ts` is the integration seam; unit tests mock the `queryCsv` API surface for view-model logic but the integration test (one Playwright run per the §13 smoke) issues a real `read_csv` against real on-disk CSV (Holy Law #7).
4. **F1 does NOT delete the Parquet readers.** That is X1a (the atomic reader flip; both formats coexist until then). F1 is purely additive in the cutover sense - all Parquet writers + readers SURVIVE.

## Tracking

The parent Execution Ledger row F1 is `DEFERRED-TO-SUBPLAN -> TODO/20260605-f1-csv-loaders-and-oracle-rewrite-subplan.md` in the SAME PR that lands this sub-plan. Sub-row status updates land inside each F1.x PR per 24.3.

## See also

- Parent plan: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) (sections 21.5 build-list, 22.6 gates, 23.2 column home, 23.4 elections wide model, 24.5 sub-plan spawning).
- B2b parent sub-plan (closure): [docs/archive/plans/20260604-b2b-reingest-subplan.md](../docs/archive/plans/20260604-b2b-reingest-subplan.md) - elections CSV layout was shipped here.
- B2b.5 elections sub-sub-plan (closure): [docs/archive/plans/20260604-b2b5-elections-reingest-subplan.md](../docs/archive/plans/20260604-b2b5-elections-reingest-subplan.md) - per-election candidacies.csv shape.
- Phase B strangler precedent: PR #171 (allowlist + indicator-from-canonical adapter) - the loader seam pattern this sub-plan generalises.
- Canonical writer doc: [docs/architecture/backend/canonical-writer.md](../docs/architecture/backend/canonical-writer.md).
- Frontend data-loading doc: [docs/architecture/frontend/data-loading.md](../docs/architecture/frontend/data-loading.md).
- Sub-plan spawning rule: parent section 24.5.
