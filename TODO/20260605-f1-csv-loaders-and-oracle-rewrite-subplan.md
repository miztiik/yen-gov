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
| F1.1 backend parity-oracle rewrite (`backend/tests/test_canonical_parity_oracle.py` reads CSV; same `canonical_winners_2026_05_19.json` fixture; same per-AC zero-tolerance assertion) | - | parity-oracle-CSV + oracle-non-skip (must actually RUN, not skipif-parquet-absent) | _pending_ | BLOCKED-NEEDS-SIGNOFF (see "F1.1 STOP-AND-SURFACE" below; rewrite reveals 33/34 slice drift between fixture and post-B2b.5.x CSV corpus; user-named trust anchor cannot be autonomously re-snapshotted or weakened per CLAUDE.md anti-pattern #1) |
| F1.2 frontend loader seam (`canonical/duckdb.ts` `queryParquet` -> `queryCsv`; `canonical/indicator-allowlist.ts` docstring + descriptor doctrine scrub; `canonical/manifest.ts` if it carries parquet path references) | - | loader-unit (vitest) + §13 in-browser smoke on one canonical-backed route | - | TODO |
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

#### F1.1 STOP-AND-SURFACE (2026-06-05) - fixture-vs-CSV drift blocks autonomous ship

**Status**: BLOCKED-NEEDS-SIGNOFF. Cannot proceed without user choice between options A / B / C below.

**Verbatim instruction** (user prompt, 2026-06-05): *"Rewrite `backend/tests/test_canonical_parity_oracle.py` to read CSV instead of parquet ... Same frozen fixture: `backend/tests/fixtures/canonical_winners_2026_05_19.json` (UNCHANGED - the trust anchor) ... Same per-AC zero-tolerance assertion (winner candidate + winner votes + margin votes match byte-exact) ... If it FAILS on any AC, DO NOT silently relax the tolerance."*

**What was done**: oracle rewritten per sub-plan body (read_csv per-(state, year) candidacies.csv; 22-state ECI-code -> LGD-slug map; oracle-non-skip floor at 34 slices; 7 known-absent slices for AcGenMay2026 / Delhi2020 / Rajasthan2023 declared explicitly). `test_oracle_non_skip_gate` PASSES. 1 of 34 per-slice tests passes byte-exact (AcGenFeb2018/S23 - Tripura 2018). 33 fail.

**Evidence (live on branch `feat/f1.1-parity-oracle-csv-rewrite`)**:

- Run cmd: `cd backend && python -m pytest tests/test_canonical_parity_oracle.py --tb=line -q`
- Result: `33 failed, 2 passed in 3.52s`. The 2 passes are `test_oracle_non_skip_gate` + `test_per_ac_fptp_winner_matches_fixture[AcGenFeb2018-S23]`.
- Dominant failure category (271 ACs across 28 slices): `ACs in fixture missing from canonical CSV`. Pattern is non-random: identical AC numbers missing across MULTIPLE election years for the SAME state. Examples (verified live):
  - AcGenApr2016/S03 (Assam 2016) ACs `[42, 103, 107]` missing in CSV
  - AcGenApr2021/S03 (Assam 2021) ACs `[42, 103, 107]` missing in CSV - IDENTICAL set, 5 years later
  - AcGenDec2017/S06 (Gujarat 2017) ACs `[49, 52, 68, 79]` missing in CSV
  - AcGenDec2022/S06 (Gujarat 2022) ACs `[49, 52, 68, 79]` missing in CSV - IDENTICAL set, 5 years later
  - AcGenApr2019/S01 (Andhra 2019) ACs `[1, 2, 3, 4, 5, ...]` missing in CSV (122 of 175)
  - AcGenApr2021/U07 (Puducherry 2021) ACs `[7, 8, 10, 13, 14]` missing
  - AcGenFeb2017/S24 (UP 2017) ACs `[3, 47, 48, 55, 56]` missing
- Secondary category (51 vote diffs across 20 slices): same `(event_id, state, ac_eci_no)` present in both fixture and CSV, but the max-votes candidate differs by 1 to 30k+ votes (per prior session's analysis - not re-verified this turn).

**Root-cause hypotheses** (not exhaustively investigated this turn per "stop, don't dig" discipline):

1. **CSV `constituency_no` is NOT the ECI per-state AC number that the fixture is keyed on.** The same numerical gaps repeating across years for the same state means the rewrite's assumed key (`CSV.constituency_no == fixture.ac_eci_no`) is wrong for those specific AC numbers. Possible: CSV `constituency_no` is post-delimitation LGD AC code; fixture is pre-delimitation ECI AC number.
2. **B2b.5.x reingest dropped specific ACs** (e.g. NOTA-only, vacated, judicially-annulled, or ACs without TCPD raw row). Repeating-across-years pattern supports this for ACs that were perennially dropped from raw.
3. **Person-merge differences from B2b.4.7 DROP** (the parent prompt's hypothesis): plausible for the 51 vote-diff slices where AC is present but max-votes candidate differs; LESS plausible for the 271 AC-missing slices where the entire AC row is absent.

**Why this is a STOP, not a fix-and-ship**: CLAUDE.md anti-pattern #1 (STOP-AND-SURFACE) forbids autonomously demoting a user-named source. `canonical_winners_2026_05_19.json` is the EXPLICITLY user-named trust anchor (parent prompt verbatim: *"Same frozen fixture ... UNCHANGED - the trust anchor"*). Autonomously re-snapshotting it, or autonomously weakening the zero-tolerance assertion to swallow 33 slice failures, would silently demote what the user wrote down.

**Resolution options** (per parent prompt's "STOP-AND-SURFACE with three resolution options A/B/C"):

| ID | Option | Scope | Multi-PR? | Preserves byte-exact rigor? | Re-opens B2b? |
| --- | --- | --- | --- | --- | --- |
| A | Backfill the missing ACs (re-run B2b.5.x reingest to add the dropped AC numbers + reconcile the 51 vote diffs against TCPD raw) | Reopens B2b sub-plan; multi-PR | YES | YES (zero-tolerance preserved, fixture unchanged) | YES (multi-week) |
| B | Relax the assertion at the boundary where structurally impossible: declare "name-normalized + votes within tolerance T" (T to be authored in a new ADR / concept doc) and explicitly cite that the CSV-corpus reshape changed semantics that byte-exact cannot survive | New ADR + test rewrite | 2 PRs (ADR + test) | NO (zero-tolerance becomes "within T") | NO |
| C | Declare the 33 mismatch slices out-of-scope for byte-exact parity; publish a "known mismatch" annex (`backend/tests/fixtures/canonical_winners_2026_05_19.known_mismatch.json`) enumerating the 271 missing ACs + 51 vote diffs; keep zero-tolerance on the 1 passing slice + any future ingest cleanup additions | New annex fixture + test loop split (frozen-trust loop with zero-tolerance, drift-tracked loop with explicit per-slice receipt) | 1 PR | YES on the 1 passing slice (drift-tracked slices are documented receipt, not assertion) | NO |

**Agent recommendation**: C. Preserves the user-signed zero-tolerance assertion on the verified subset; explicitly documents the 33 drift slices as a public receipt (becomes the input for X1a cross-format-parity gate); does NOT autonomously demote the user-named fixture; does NOT block on multi-week B2b reopening; ships F1.1 today; matches Fowler "deletion safety" + Max "OWID one-time receipt" precedent.

**What was NOT done this turn**: (a) the oracle rewrite is on disk under `backend/tests/test_canonical_parity_oracle.py` (uncommitted modifications, can be inspected via `git diff origin/main -- backend/tests/test_canonical_parity_oracle.py` on branch `feat/f1.1-parity-oracle-csv-rewrite`), (b) the branch is NOT pushed, (c) NO PR is opened, (d) the `KNOWN_ABSENT_SLICES` set in the rewrite does NOT yet include the 33 drift slices - that fixture annex is option C's payload and waits on signoff.

**Scope-change ledger row** (per CLAUDE.md section 10):

| Verbatim instruction | Proposed change (one of A / B / C) | Reason | signoff: |
| --- | --- | --- | --- |
| "Same per-AC zero-tolerance assertion (winner candidate + winner votes + margin votes match byte-exact)" | TBD (A, B, or C above) | 33 of 34 on-disk slices fail byte-exact; root cause is fixture-vs-CSV corpus drift that accumulated through B2b.5.x reshape because the old parquet oracle silently SKIPPED on `parquet absent`. The skip is exactly what the parent plan's `oracle-non-skip` gate was added to catch - it is doing its job; we now need a structural answer. | _pending user signoff_ |

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
