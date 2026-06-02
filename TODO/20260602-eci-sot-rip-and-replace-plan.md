# Level-4 plan: rip `datasets/reference/in/states/<S>/constituencies.json` SoT, standardise on LGD taxonomy

**Last Updated**: 2026-06-02

**Predecessor**: [docs/archive/plans/20260530-eci-to-lgd-acid-migration-plan.md](../docs/archive/plans/20260530-eci-to-lgd-acid-migration-plan.md) (LGD AC_ID join-key migration; merged through PRs #530-#539). That plan landed the `taxonomy/ac_crosswalk.parquet` spine; this plan retires the **per-state ECI-keyed SoT shards** that the spine made redundant.

**Mandate** (verbatim, 2026-06-02): *"dont need a fig - just rip and replace. and retire all eci - use taxonomy and standardize on LGD ... first plan-doc and then follow the plan with big-bang"*. User authorisation per CLAUDE.md section 0a: no strangler-fig, no parallel-read window, single-PR rip-and-replace authorised.

---

## section 0. Why this plan-doc exists

The post-PR-#539 audit confirmed: ~85% of every `datasets/reference/in/states/<S>/constituencies.json` shard is now redundant with `datasets/taxonomy/ac_crosswalk.parquet` (4113 AC rows with `eci_state, eci_no, lgd_ac_id, name, reservation, status`). Two facts only live on the SoT shards and must be lifted before the rip:

1. **AC->district FK** (`district_id` per AC; declared on every constituency row in the SoT shard but absent from `ac_crosswalk.parquet`).
2. **Per-state ECI provenance** (`sources[]` per shard: which ECI XLSX produced this state's roster + `fetched_at`; not in `taxonomy/sources.parquet` at `(scope=state, body=AC)` granularity).

Once both facts are lifted to the taxonomy, the 36 SoT shards become pure duplication and the 7 consumers can be rewritten to read from the taxonomy.

---

## section 1. Hard scope (in)

- Lift `district_id` per AC into `taxonomy/ac_crosswalk.parquet` (additive column; nullable for the few SoT rows that lack it).
- Lift per-state ECI provenance rows into `taxonomy/sources.parquet` with `scope_kind=state`, `scope_value=<eci_state_code>`, `body=AC`, one row per (state, ECI XLSX URL).
- Rewrite **7 consumers** to read from `taxonomy/ac_crosswalk.parquet` + `taxonomy/lgd_acs.json` + `taxonomy/sources.parquet` instead of the SoT shards:
  1. `tools/boundaries/snapshot.py` — replace `sot_ref` field stamping with crosswalk pointer
  2. `tools/boundaries/verify_ac_parity.py` — replace `(state, eci_no, name)` join against SoT with crosswalk query
  3. `tools/boundaries/s03_t4_district_fallback.py` — replace S03 SoT load with `taxonomy/ac_crosswalk.parquet WHERE eci_state='S03'`
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

## section 3. Status Reckoner

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| R1 | Lift `district_id` per AC into `taxonomy/ac_crosswalk.parquet` (schema bump minor, harvest script, deterministic emit) | [ ] PENDING | _pending_ | M |
| R2 | Lift per-state ECI provenance into `taxonomy/sources.parquet` (1 row per (state, XLSX) tuple) | [ ] PENDING | _pending_ | M |
| R3 | Rewrite 7 consumers + delete 36 SoT shards + fix 4 incidental ECI residues + update CLAUDE.md anti-pattern; **single big-bang PR** | [ ] PENDING | _pending_ | L |
| R4 | Distill: archive this plan-doc + update [docs/reference/data-coverage-report.md](../docs/reference/data-coverage-report.md) + emit lesson | [ ] PENDING | _pending_ | S |

---

## section 4. Per-row acceptance gates

### R1 - Lift `district_id` per AC

- Bump `datasets/schemas/ac-crosswalk.schema.json` x-version to minor (additive `district_id?` column).
- Harvester script `tools/taxonomy/lift_ac_district_from_sot.py` walks `datasets/reference/in/states/<S>/constituencies.json`, joins on `(eci_state, eci_no)`, fills `district_id` column in `ac_crosswalk.parquet`.
- Emit deterministic: sorted by `(eci_state, eci_no)`; idempotent re-run is a no-op.
- Coverage gate: >=95% of crosswalk rows resolve to a `district_id` (the residual <5% are SoT rows where `district_id` was absent upstream; left null).
- Tier-A: new unit test `backend/tests/test_lift_ac_district_from_sot.py` asserts the harvest is deterministic + total >=3900 ACs filled.
- Tier-B: `python -m yen_gov validate --root .` green.

### R2 - Lift per-state ECI provenance

- Each SoT shard's `sources[]` array becomes N rows in `taxonomy/sources.parquet` with `scope_kind=state, scope_value=<S01..U09>, body=AC, producer=ECI, url, fetched_at`.
- `source_id` derived via existing `backend.yen_gov.canonical.citation.derive_source_id` (CLAUDE.md section 12).
- Deduplicate when the same XLSX URL covers multiple states (one row per (state, url)).
- Tier-A: new unit test asserts every emitted row has `source_id` FK + non-null `url` + valid `fetched_at`.
- Tier-B: `python -m yen_gov validate --root .` green.

### R3 - The rip (single big-bang PR)

- All 7 consumer rewrites land in ONE commit (irreversible; once SoT is gone, every consumer must read the new spine OR break).
- `git rm -r datasets/reference/in/states/` deletes 31 dirs + 36 files in the same commit.
- 4 incidental fixes co-land:
  - `datasets/elections/_inventory.json`: flip residual `state: "S01"` -> `state: "andhra-pradesh"`.
  - `datasets/grapher/election_tile_layouts.json`: re-key all 36 `state: "S\d{2}|U\d{2}"` -> LGD slug.
  - 2 schema regexes loosened.
- CLAUDE.md anti-pattern entry added: "Do not create new files under `datasets/reference/in/states/`. Lift to `taxonomy/ac_crosswalk.parquet` instead. Retired 2026-06-02 by [TODO/20260602-eci-sot-rip-and-replace-plan.md](TODO/20260602-eci-sot-rip-and-replace-plan.md)."
- 5-gate DoD:
  - Gate 1 (validate): `python -m yen_gov validate --root .` green.
  - Gate 2 (pytest): backend pytest green (post-baseline; the only delta should be the 7 consumer tests + 2 new lift tests).
  - Gate 3 (svelte-check): 0 errors.
  - Gate 4 (vitest): 0 new failures; `golden-path.spec.ts` updated.
  - Gate 5 (browser smoke): home + 3 state hubs (TN/KL/BR) + 1 AC drill render with no console `[error]` and no new `404` for `/data/reference/in/states/**`.

### R4 - Distillation

- `git mv TODO/20260602-eci-sot-rip-and-replace-plan.md docs/archive/plans/`
- Append "Plan complete" closure block with per-row PR distillation map per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).
- Update `docs/reference/data-coverage-report.md` to remove the `reference/in/states/<S__>/constituencies.json` entry and replace with `taxonomy/ac_crosswalk.parquet` row.
- Emit a `notes/20260602-eci-sot-rip-handover.md` lesson if any surprises hit during R3.

---

## section 5. Risk + rollback

**Risk**: R3 is irreversible-from-disk in a single commit; if Gate 5 (browser smoke) reveals a runtime regression a consumer missed, the rollback path is `git revert <R3-commit-sha>` which restores all 36 shards + all 7 consumer files in one operation.

**Pre-flight insurance**: before committing R3, run each consumer test in isolation against a tmp_path-injected canonical store to catch wiring bugs before the deletion lands.

**No staging window**: per user mandate, no parallel-read fallback ("dont need a fig"). The rip + consumer rewrite are atomic.

---

## section 6. Sequencing

R1 -> R2 -> R3 -> R4. R1 + R2 are independent and could parallelise, but they're both small enough that serialising them avoids merge-conflict risk on `taxonomy/sources.parquet` + `taxonomy/ac_crosswalk.parquet`. R3 has hard dependencies on BOTH R1 and R2 being on main (the consumer rewrites read the new columns + rows R1/R2 emit). R4 is post-merge cleanup.

---

## section 7. Open questions

None blocking. Strategy is explicit per user mandate; deliverables are mechanical; consumer list is closed.
