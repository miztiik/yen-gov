# Level-4 plan: rip `datasets/reference/in/states/<S>/constituencies.json` SoT, standardise on LGD taxonomy

**Last Updated**: 2026-06-03 (second amendment; see section 0b)

**Predecessor**: [docs/archive/plans/20260530-eci-to-lgd-acid-migration-plan.md](../docs/archive/plans/20260530-eci-to-lgd-acid-migration-plan.md) (LGD AC_ID join-key migration; merged through PRs #530-#539). That plan landed the `taxonomy/ac_crosswalk.parquet` spine; this plan retires the **per-state ECI-keyed SoT shards** that the spine made redundant.

**Mandate** (verbatim, 2026-06-02): *"dont need a fig - just rip and replace. and retire all eci - use taxonomy and standardize on LGD ... first plan-doc and then follow the plan with big-bang"*. User authorisation per CLAUDE.md section 0a: no strangler-fig, no parallel-read window, single-PR rip-and-replace authorised.

---

## section 0. Why this plan-doc exists

The post-PR-#539 audit confirmed that the SoT shards are largely redundant with `taxonomy/ac_crosswalk.parquet`. Two facts initially looked like they only lived on the SoT shards. **Section 0a (below) records the data audit that ran after this plan-doc landed on main**; the audit invalidated one premise and confirmed the other, so the live scope is narrower than the original plan-doc claimed.

---

## section 0a. Data-audit findings (2026-06-02, post-merge of plan-doc PR #605)

Before executing R1, ran a row-count audit of the SoT shards against the taxonomy. Findings:

1. **`district_id` is DEAD.** Of 4113 AC rows across 31 SoT shards, only 824 (20%) have any value, in only 5 states (S03, S11, S22, S25, U07). The populated values are short author-internal strings (`'KOK'`, `'KAS'`, `'TAL'`, `'COB'`, `'puducherry'`) - **NOT LGD district codes**. The proper LGD-keyed hook already exists in the taxonomy: [`datasets/taxonomy/lgd_ac_pc_district_map.json`](../datasets/taxonomy/lgd_ac_pc_district_map.json) (232 rows of `(lgd_state_id, lgd_ac_id) -> [lgd_district_ids]`) + [`datasets/taxonomy/lgd_acs.json`](../datasets/taxonomy/lgd_acs.json) (carries `lgd_pc_id` + `lgd_state_id` per AC). Exactly one consumer ([`tools/boundaries/s03_t4_district_fallback.py`](../tools/boundaries/s03_t4_district_fallback.py)) reads the SoT field, and it already maintains its own hardcoded `SOT_CODE_TO_DIST_LGD` 35-entry translator because the SoT codes are not LGD-joinable. **Consequence: R1 is DROPPED.** No lift; just delete the dead field with the SoT shards and rewire `s03_t4_district_fallback.py` to read from `lgd_ac_pc_district_map.json` in R3.

2. **Per-state ECI provenance IS unique** to the SoT shards (`sources[].url` + `fetched_at` per state). R2 stands as authored.

3. **Lesson distilled**: before executing a multi-PR data-lift plan, verify the plan's load-bearing premises against the actual data, not from one sample row. The plan-doc R1 was authored after reading `S01:1 Ichchapuram` only, where `district_id: null` was apparently misread as `district_id present`. Recording in `/memories/lessons.md`.

---

## 0b. Second audit finding (2026-06-03) -- frontend consumer chain missed

The R3 framing "single big-bang PR rewriting 7 backend consumers" was undersized. A grep across `frontend/src/` surfaced 5 additional consumers of `datasets/reference/in/states/<S>/constituencies.json`, served at runtime as `/reference/in/states/<S>/constituencies.json` via Vite middleware:

- [frontend/src/lib/data.ts](frontend/src/lib/data.ts#L210) -- `loadConstituencies(state)` JSON-fetches the SoT shard. Load-bearing on every state overview page.
- [frontend/src/lib/data.test.ts](frontend/src/lib/data.test.ts#L90) -- vitest unit pinning the above with a URL mock.
- [frontend/src/routes/StateOverview.svelte](frontend/src/routes/StateOverview.svelte#L694) -- consumes `loadConstituencies` behind a 3-state `acs_status` (loading / ready / failed) discriminator that races the DuckDB-WASM summary loader.
- [frontend/src/lib/view-models/districts.ts](frontend/src/lib/view-models/districts.ts#L31) -- reads `constituencies[].district_id`, the very field R1 dropped after the audit showed 80% null and non-LGD values.
- [frontend/src/lib/maplibre/sources.ts](frontend/src/lib/maplibre/sources.ts#L463) -- code comment referencing U08 SoT shard (deletable update).

Consequence: the rip cannot be a single PR. The frontend consumer is NOT mechanical -- it requires a new DuckDB-WASM view exposing AC rows from `taxonomy/ac_crosswalk.parquet`, plus a districts view-model that LGD-joins via `taxonomy/lgd_ac_pc_district_map.json` instead of trusting the SoT `district_id`. Per user mandate (2026-06-03), R3 splits into R3a (frontend migration, parallel-readable) and R3b (the rip, depends on R3a on main). Pattern: Parallel Change -- EXPAND/MIGRATE in R3a, CONTRACT in R3b.

---

## section 1. Hard scope (in)

- ~~Lift `district_id` per AC into `taxonomy/ac_crosswalk.parquet`~~ **DROPPED per section 0a finding 1** (dead field; LGD hook already exists via `taxonomy/lgd_ac_pc_district_map.json`).
- Lift per-state ECI provenance rows into `taxonomy/sources.parquet` with `scope_kind=state`, `scope_value=<eci_state_code>`, `body=AC`, one row per (state, ECI XLSX URL).
- Rewrite **7 consumers** to read from `taxonomy/ac_crosswalk.parquet` + `taxonomy/lgd_acs.json` + `taxonomy/sources.parquet` instead of the SoT shards:
  1. `tools/boundaries/snapshot.py` — replace `sot_ref` field stamping with crosswalk pointer
  2. `tools/boundaries/verify_ac_parity.py` — replace `(state, eci_no, name)` join against SoT with crosswalk query
  3. `tools/boundaries/s03_t4_district_fallback.py` — replace S03 SoT load with crosswalk + LGD join: `ac_crosswalk WHERE eci_state='S03'` JOIN `lgd_ac_pc_district_map.json` ON `lgd_ac_id` -> `lgd_district_ids[]`. **DELETE the hardcoded `SOT_CODE_TO_DIST_LGD` 35-entry translator** (it exists only because the SoT codes were not LGD-joinable; the LGD map replaces it). Output stays `parent_district_id` keyed to LGD numerics (compatible with downstream callers).
  4. `tools/boundaries/pipeline.json` — drop `sot_ref` fields; replace `delimitation_warning` SoT pointers with crosswalk pointers
  5. `tools/bootstrap_constituencies_from_results.py` — RETIRE entirely (it writes the SoT format we're deleting; bootstrap path moves to a single `tools/taxonomy/bootstrap_ac_crosswalk.py` if/when needed)
  6. `frontend/e2e/golden-path.spec.ts` line 153 — replace the `/data/reference/in/states/S22/constituencies.json` mock with a `/data/taxonomy/ac_crosswalk.parquet` mock (or remove the mock if the e2e doesn't need to assert on the AC list)
  7. `docs/reference/data-coverage-report.md` + `docs/reference/boundary-data-sources.md` + `tools/boundaries/README.md` — update all 3 docs to point at the taxonomy as SoT
- Delete the 36 SoT shards: `git rm -r datasets/reference/in/states/`
- Fix the 4 incidental stale ECI residues found in the 2026-06-02 survey:
  - `datasets/elections/_inventory.json` — one residual `state: "S01"` row missed by PR #575
  - `datasets/grapher/election_tile_layouts.json` — re-key `state: "S22"` -> `state: "tamil-nadu"` (cartogram coords; safe slug-rekey)
  - `datasets/schemas/boundary-layers.schema.json` + `datasets/schemas/manifest.schema.json` — loosen the `^[SU]\d{2}$` patterns to accept LGD slugs (or split into a `^[SU]\d{2}$|^[a-z]+(-[a-z]+)*$` union if a transition window is needed)
- Update [CLAUDE.md anti-pattern list](../CLAUDE.md) to forbid future writes under `datasets/reference/in/states/`.

---

## section 2. Hard scope (out)

- `datasets/taxonomy/lgd/` — already clean per 2026-06-02 audit; **DO NOT TOUCH**.
- `datasets/elections/state=<lgd-slug>/` partitions — already migrated (PR #565); **DO NOT TOUCH**.
- `datasets/migration-ledger.csv` audit rows — historical record; **DO NOT REWRITE**.
- `datasets/taxonomy/entities.json` `entity_code` field — still ECI code, by design (ADR-0036 alias model); **DO NOT RENAME**.
- Frontend URL grammar `/s/<state-slug>/ac/<eci_no>-<name-slug>` — kept per Strategy-D-hardened (`eci_no` is the citizen-facing display token); **DO NOT REWRITE**.

---

## section 3. Status Reckoner (revised 2026-06-03)

| Row | Scope | PR# | Status | Depends on |
| --- | --- | --- | --- | --- |
| R1 | ~~Lift `district_id` per AC into `ac_crosswalk.parquet`~~ | -- | DROPPED (§0a audit) | -- |
| R2 | Lift per-state ECI provenance into `taxonomy/sources.parquet` | _pending_ | PENDING | -- |
| R3a | Frontend migration: register `dim_acs` DuckDB-WASM view; rewrite `loadConstituencies` to query view; rewire `districts.ts` to LGD-join; update `data.test.ts` + `StateOverview.svelte` + `golden-path.spec.ts`; SoT shards stay on disk (parallel-readable) | _pending_ | PENDING | R2 |
| R3b | The rip: rewrite 4 backend tools (`snapshot.py`, `verify_ac_parity.py`, `s03_t4_district_fallback.py`, `pipeline.json`); retire `bootstrap_constituencies_from_results.py`; `git rm -r datasets/reference/in/states/`; fix 4 incidental ECI residues; update `sources.ts:463` comment; stamp CLAUDE.md anti-pattern; update 3 docs | _pending_ | PENDING | R3a on main |
| R4 | Distil + archive plan-doc | _pending_ | PENDING | R3b |

Sequencing: R2 -> R3a -> R3b -> R4. R2 and R3a are NOT parallelised: R3a's view registration may reference `source_id` derivation paths R2 introduces; serialising costs ~1 day and removes the merge-order risk.

---

## section 4. Per-row acceptance gates

### ~~R1 - Lift `district_id` per AC~~ DROPPED

See section 0a finding 1. No work to do.

### R2 - Lift per-state ECI provenance

- Each SoT shard's `sources[]` array becomes N rows in `taxonomy/sources.parquet` with `scope_kind=state, scope_value=<S01..U09>, body=AC, producer=ECI, url, fetched_at`.
- `source_id` derived via existing `backend.yen_gov.canonical.citation.derive_source_id` (CLAUDE.md section 12).
- Deduplicate when the same XLSX URL covers multiple states (one row per (state, url)).
- Tier-A: new unit test asserts every emitted row has `source_id` FK + non-null `url` + valid `fetched_at`.
- Tier-B: `python -m yen_gov validate --root .` green.

### R3a - Frontend migration (PR A; EXPAND + MIGRATE phase of Parallel Change)

**Contract decisions (resolve in PR body, not in code):**

- **View shape:** Register a new slice `dim_acs` in [frontend/src/lib/duckdb.ts](frontend/src/lib/duckdb.ts) following the existing `registerSlice` pattern used by elections + observations slices. Source: `taxonomy/ac_crosswalk.parquet` projected to columns `(state_code, eci_no, ac_name, reservation)`. District FK is NOT joined into the slice -- districts.ts joins separately against `lgd_ac_pc_district_map.json` to keep the slice single-source.
- **Return type:** Rename `Constituency` -> `AcRow` in `data.ts`; new shape `{eci_no: number, name: string, reservation: 'GEN'|'SC'|'ST'}`. Drop `district_id` (R1 audit: 80% null, non-LGD values, no longer authoritative). `ConstituenciesCollection` envelope (`{sources, state, body, status, ...}`) collapses -- DuckDB-WASM query is synchronous-after-registration, no envelope needed.
- **`acs_status` discriminator:** Collapses to a single ready-state once both reads go through the same DuckDB-WASM connection. The race window in `StateOverview.svelte:694` is an artifact of the dual-runtime (HTTP fetch vs WASM query); single-runtime removes it.
- **Test fixture:** `data.test.ts` swaps URL mock for in-memory DuckDB fixture per existing vitest pattern (cite the slice-test pattern already used for elections in `frontend/src/lib/__tests__/` or equivalent).

**Gates:**
- [ ] Gate 1: `python -m yen_gov validate --root .` green (no datasets touched, expected n/a)
- [ ] Gate 2: `pytest -q` green (no backend touched)
- [ ] Gate 3: `svelte-check` 0 errors
- [ ] Gate 4: `vitest` green incl. new `dim_acs` slice test + rewritten `data.test.ts`
- [ ] Gate 5 (browser smoke): home + TN + KL + BR state hubs + 1 AC drill, 0 console errors, **0 `/data/reference/in/states/**` 404s** (load-bearing -- proves JSON-fetch is fully gone)
- [ ] Gate 6 (e2e): `golden-path.spec.ts:153` updated; 1.5s-race mock removed or repurposed
- [ ] SoT shards REMAIN on disk post-merge (parallel-readable window for R3b)

### R3b - The rip (PR B; CONTRACT phase of Parallel Change)

**Hard precondition:** Before staging, verify `git log origin/main --oneline | grep <R3a-merge-sha>` returns the R3a squash commit. SoT shards MUST NOT be deleted until origin/main carries the frontend migration. Stamp the R3a PR# in the PR-B body under "Precondition verified".

**Scope (unchanged from original R3 minus the frontend chain):**
- Rewrite `backend/yen_gov/tools/snapshot.py` to read `ac_crosswalk.parquet` instead of SoT shards
- Rewrite `backend/yen_gov/tools/verify_ac_parity.py` similarly
- Rewrite `backend/yen_gov/lifts/s03_t4_district_fallback.py` to use `lgd_ac_pc_district_map.json`
- Update `config/pipeline.json` source refs
- Retire `backend/yen_gov/bootstrap_constituencies_from_results.py` (delete + remove from imports)
- `git rm -r datasets/reference/in/states/` (36 shards)
- Fix 4 incidental ECI residues (per original R3 scope)
- Update [frontend/src/lib/maplibre/sources.ts](frontend/src/lib/maplibre/sources.ts#L463) comment ref to U08
- Stamp CLAUDE.md anti-pattern: "Do not introduce per-state JSON shards as a SoT for canonical-store-derivable facts"
- Update 3 docs (cite the 3 doc paths from the original R3 row)

**Gates:**
- [ ] Gate 1: `validate --root .` green
- [ ] Gate 2: `pytest -q` green
- [ ] Gate 3: `svelte-check` 0 errors (only comment-ref touched in frontend)
- [ ] Gate 4: `vitest` green
- [ ] Gate 5 (browser smoke): same routes as R3a, 0 console errors, 0 `/data/reference/in/states/**` 404s -- now a regression check, not a load-bearing assertion
- [ ] `git status` confirms 36 shards staged for deletion + no untracked residue under `datasets/reference/in/states/`

### R4 - Distillation

- `git mv TODO/20260602-eci-sot-rip-and-replace-plan.md docs/archive/plans/`
- Append "Plan complete" closure block with per-row PR distillation map per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).
- Update `docs/reference/data-coverage-report.md` to remove the `reference/in/states/<S__>/constituencies.json` entry and replace with `taxonomy/ac_crosswalk.parquet` row.
- Emit a `notes/20260602-eci-sot-rip-handover.md` lesson if any surprises hit during R3.

---

## section 5. Sequencing rationale (revised 2026-06-03)

R2 -> R3a -> R3b -> R4.

- **R2 first:** R3a's slice registration may need `source_id` FKs for the `dim_acs` projection if any AC-attributed metadata gets surfaced in the view. Doing R2 first means R3a never needs a follow-up to wire provenance.
- **R3a before R3b:** Parallel Change discipline. R3a is EXPAND + MIGRATE (canonical reader live on main, legacy artifact still on disk). R3b is CONTRACT (legacy artifact deleted). Reversing the order would create a window where the frontend 404s on every state hub.
- **R3a and R2 NOT parallelised:** ~1 day saved if parallelised, but introduces merge-order risk on `taxonomy/sources.parquet` schema and on the `dim_acs` slice's source FK. Serialising is cheap insurance.
- **R3b is the only PR that touches `datasets/reference/in/states/`:** the deletion is atomic with the backend rewires so no commit on main carries an orphaned tool reading deleted shards.
- **R4 after R3b on main:** distillation map must cite the final R3a + R3b PR numbers.

---

## section 6. Risk register (R3a)

**Risk:** [frontend/src/lib/view-models/districts.ts](frontend/src/lib/view-models/districts.ts#L31) currently reads `constituencies[].district_id`, which the §0a audit showed populated on only 824/4113 rows (20%) with non-LGD values (`KOK`, `KAS`, `TAL`, `COB`, `puducherry`). The R3a rewrite joins via `taxonomy/lgd_ac_pc_district_map.json` (232 rows, LGD-keyed, authoritative) instead. Two consumer-side cases must be specified:

1. **LGD lookup miss for a given `(lgd_state_id, lgd_ac_id)`** -- e.g. U08 J&K post-reorg ACs where LGD has not yet published the mapping. **Contract:** view-model returns `district: null`. UI renders an empty district badge slot on the AC card -- no crash, no `"Unknown district"` placeholder string. Citizen reads silence as "data not yet available", which is honest.
2. **The 824 SoT rows where some author manually filled `district_id` with a non-LGD code** -- those values are now discarded. If any of those happen to correspond to an LGD-mapped AC, the LGD join recovers the canonical district FK. If not, falls to case 1.

**Test coverage:** `districts.test.ts` (new or updated) MUST include one fixture per case: (a) AC with LGD mapping -> district populated; (b) AC without LGD mapping -> `district: null`, no exception. Snapshot/render test asserts empty badge slot, not placeholder text.

**Doc impact:** add a one-paragraph "District FK provenance" note to [docs/architecture/frontend/data-loading.md](docs/architecture/frontend/data-loading.md) (if it exists; else to the closest frontend data-loading doc) recording that AC district FKs flow from `lgd_ac_pc_district_map.json`, not from the (deleted) SoT shard. This is the durable lift from R3a.

---

## section 7. Open questions

None blocking. Strategy is explicit per user mandate; deliverables are mechanical; consumer list is closed.
