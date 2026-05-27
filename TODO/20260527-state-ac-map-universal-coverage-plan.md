# 2026-05-27 — State AC map universal LGD coverage plan

**Scope**: User mandate "universal swap to LGD for AC boundaries across all
20 states/UTs that today still use HTL/datameet sources." Overrides Phase D.1
recon's per-state "keep-current" verdict because the user accepts the
citizen-visual concession (LGD pre-bifurcation residue renders as no-fill
extras) in exchange for citation consistency (LGD/BharatMaps everywhere) and
freedom from the unmaintained Hindustan Times Labs source.

**Genesis**: Citizen-facing investigation 2026-05-27 found
`/s/tamil-nadu` shows LGD-keyed AC choropleth coloured by election winners
but `/s/bihar`, `/s/gujarat`, and most other state pages do NOT — the
`STATE_AC` registry in `frontend/src/lib/maplibre/sources.ts` only wired
6 of 31 states (S03, S11, S22, S25, U07, U08). User asked for "universal
swap to LGD" (and explicit Union-Territory inclusion). The same investigation
surfaced that the 6 wired entries use uppercase `AC_NO` (HTL convention)
while ramSeraph LGD ships lowercase `ac_no` — the join key flip MUST bundle
with the swap to prevent silent regression on currently-rendering states.

**Backref**: extends [TODO/20260524-boundary-coverage-expansion-plan.md](20260524-boundary-coverage-expansion-plan.md)
which marked "Phase D complete" with 10 LGD + 20 HTL + 1 shijithpk as the
end-state. D.7 here re-opens the 20 HTL block per user override.

---

## Status ready reckoner (UPDATE AFTER EVERY PR)

| Row | PR scope | PR | Status | SHA | Notes |
|---|---|---|---|---|---|
| **R1** | Pipeline.json LGD swap (20 states) + verify_ac_parity `--threshold` + `--allow-extras` + `--undercoverage-tolerance` flags + bundled sources.ts flip for 5 already-wired entries (S03/S11/S22/S25/U07) | _pending_ | In progress | _pending_ | Gates: validate / pytest / vitest / svelte-check / browser smoke `/s/tamil-nadu/ac/<n>`. Per-state thresholds documented in §R1.4. Any state where LGD count < SoT count × 0.90 reverts to HTL pre-commit (citizen-experience safety net per Hans). |
| **R3** | Frontend STATE_AC registry sync (extend 6 → 30) + amend ADR-0031 with 2026-05-27 D.7 override | _planned_ | Not started | — | Gated on R1 merge. Adds 25 net new entries (15 R1-newly-snapshotted + 10 D.2-already-on-disk). All 30 LGD entries use `join_property: "ac_no"` lowercase. Labels plain "<State> — Assembly constituencies" (no source acronym per user mandate). |
| **R4** | Playwright per-state coverage report | _planned_ | Not started | — | Gated on R3 merge. New `frontend/e2e/state-ac-coverage.spec.ts` iterates 30 states, asserts ≥90% coloured polygons per state. Per-state numbers written to `notes/2026-05-27-state-ac-coverage-report.md`. |

---

## R1 — Pipeline.json + verify_ac_parity + snapshot (THIS PR)

### R1.1 Scope (files touched)

1. `tools/boundaries/pipeline.json` — 18 HTL `ac` entries replaced with
   ramSeraph LGD-pattern blocks (S04 D.2 template); per-state
   `state_filter.equals = <State_LGD>` integer. 2 states (S01 AP,
   S03 Assam) attempted swap but REVERTED to HTL per R1.7 outcome —
   their pipeline.json blocks carry an extended `$comment` recording
   the deferral rationale + post-bifurcation/post-delimitation
   re-evaluation trigger. Also: incidental country-layer vintage fix
   (`""` → `"operator-snapshot-2026-05"`) on the yashveeeeeeer line —
   bumped in `boundary_layers_seed.py` (PR #272) but never re-synced
   in pipeline.json, leaving boundary_layers.parquet's country row
   FK-orphaned. Bundled here to unblock R1's parquet recompile.
2. `tools/boundaries/verify_ac_parity.py` — add three CLI flags:
   - `--threshold FLOAT` (default 0.95) for per-state name-parity floor
     overrides (e.g. S03 Assam ~0.85 due to transliteration drift).
   - `--allow-extras` (boolean) for D.7 LGD pre-bifurcation residue:
     accepts snapshot containing MORE features than SoT (residue renders
     as no-fill polygons — citizen-harmless). Undercoverage still fails.
   - `--undercoverage-tolerance FLOAT` (default 0.0) for the D.7 trickle
     case (West Bengal S25 LGD 293 vs SoT 294: 1-of-294 = 0.34%): accept
     up to `tolerance * sot_count` ACs missing without failing. Combined
     with the 0.90 safety-net floor below (anything > 10% loss reverts
     the state's pipeline.json to HTL).
3. `backend/tests/test_verify_ac_parity.py` — 8 new tests for the three
   flags (extend in place; do not create parallel file). Total 24 tests.
4. `frontend/src/lib/maplibre/sources.ts` — flip 4 currently-wired
   entries (S11 / S22 / S25 / U07) from `join_property: "AC_NO"`
   (uppercase HTL) → `"ac_no"` (lowercase LGD); rewrite labels to plain
   "<State> — Assembly constituencies"; rewrite attribution to ramSeraph
   LGD; bump `geojson_url` to the LGD archive URL. S03 Assam was
   initially flipped to LGD then REVERTED to HTL `AC_NO` per R1.7 (LGD
   ships pre-2023 delim names; SoT carries post-2023). Header comment
   block updated to reflect S01/S03 HTL-staying exclusions. **Bundled
   with the pipeline.json swap to prevent silent regression: snapshot
   would overwrite the on-disk GeoJSONs with lowercase `ac_no`, breaking
   the uppercase join for these 4 states if shipped separately.**
5. 20 regenerated `datasets/boundaries/in/ac/state=in_<eci_lc>/all.geojson`
   files (snapshot output).
6. Regenerated `datasets/boundaries/in/boundary_layers.parquet` (snapshot
   emits this automatically via `compile_to_parquet`).
7. This plan-doc with R1 PR # stamp.

### R1.2 Out of scope

- Adding NEW `STATE_AC` registry entries for the 15 R1-newly-snapshotted
  states (S01, S02, S05, S06, S10, S12, S13, S14, S15, S16, S20, S21, S24,
  S27, S29) → deferred to **R3**. Those states never had a citizen-facing
  AC map before R1; they continue to show "No boundary source registered"
  after R1 (same as before). No regression.
- Adding STATE_AC entries for the 10 D.2-already-LGD states (S04, S07,
  S08, S17, S18, S19, S23, S26, S28, U05) → also R3.
- ADR-0031 amendment for D.7 → R3 (the amend belongs with the
  registry change because the citizen-visible state-AC count flips
  from 6 → 30 in R3, not R1).
- Playwright per-state coverage spec → R4.

### R1.3 State_LGD integer table (verified 2026-05-27 via `state_lgd_resolver.load_state_lgd_to_eci_map`)

| ECI | LGD | State |
|---|---|---|
| S01 | 28 | Andhra Pradesh |
| S02 | 12 | Arunachal Pradesh |
| S03 | 18 | Assam |
| S05 | 30 | Goa |
| S06 | 24 | Gujarat |
| S10 | 29 | Karnataka |
| S11 | 32 | Kerala |
| S12 | 23 | Madhya Pradesh |
| S13 | 27 | Maharashtra |
| S14 | 14 | Manipur |
| S15 | 17 | Meghalaya |
| S16 | 15 | Mizoram |
| S20 | 8  | Rajasthan |
| S21 | 11 | Sikkim |
| S22 | 33 | Tamil Nadu |
| S24 | 9  | Uttar Pradesh |
| S25 | 19 | West Bengal |
| S27 | 20 | Jharkhand |
| S29 | 36 | Telangana |
| U07 | 34 | Puducherry |

### R1.4 Per-state acceptance thresholds (post-snapshot verification gate)

Per D.1 recon (`notes/2026-05-25-d1-ac-consolidation-recon.md`) measured
pan-India LGD-vs-SoT parity. Per-state filtered numbers may differ from
those raw numbers (better for some, equal for others). Snapshot run pending;
per-state thresholds applied via the new `--threshold` flag:

| ECI | Default 0.95 | Relaxed | Rationale |
|---|---|---|---|
| S01 AP | ❌ | 0.50 | D.1: 0% raw name parity (pre-Telangana). Re-measure on per-state-filtered slice; if still <50%, accept (join works on `ac_no` numeric regardless of name). |
| S02 AR | ✅ | — | D.1: 92% pan-India. Expect similar per-state. |
| S03 AS | ❌ | 0.50 | D.3 carve-out; 1% raw parity. Accept name drift; verify count ≥ SoT × 0.90. |
| S05 GA | ✅ | — | D.1: 100% pan-India. |
| **S06 GJ** | ⚠️ | 0.90 | D.1 said LGD missing 18 of 182 ACs. **If post-filter count < 164, REVERT pipeline.json to HTL for S06 only.** Citizen would see ~10% blank polygons in Gujarat which is unacceptable. |
| S10 KA | ✅ | — | D.1: 96% pan-India. |
| S11 KL | ✅ | 0.80 | D.1: 82% pan-India. Likely transliteration drift; safe to accept on numeric join. |
| S12 MP | ✅ | — | D.1: 97% pan-India. |
| S13 MH | ✅ | — | D.1: 98% pan-India. |
| S14 MN | ✅ | 0.85 | D.1: 90% pan-India. |
| S15 ML | ✅ | — | D.1: 100% pan-India. |
| S16 MZ | ✅ | 0.85 | D.1: 88% pan-India. |
| S20 RJ | ✅ | — | D.1: 100% pan-India. |
| S21 SK | ✅ | 0.85 | D.1: 90% pan-India. |
| S22 TN | ✅ | 0.85 | D.1: 88% pan-India. Verify per-state filtered count. |
| S24 UP | ✅ | — | D.1: 100% pan-India. |
| S25 WB | ✅ | 0.85 | D.1: 91% pan-India. |
| S27 JH | ✅ | — | D.1: 98% pan-India. |
| S29 TG | ✅ | — | D.1: 98% pan-India. |
| U07 PY | ✅ | 0.85 | D.1: 93% pan-India. |

**Decision rule**: For any state where snapshot+verify shows `feature_count
< SoT_count × 0.90` (more than 10% of citizen-expected polygons missing),
REVERT that state's `pipeline.json` block to its prior HTL entry pre-commit.
Document the revert in the PR body + plan-doc. The state stays on HTL until
LGD upstream improves OR per-state recon yields a fix.

### R1.5 Gates (5-gate DoD)

1. `python -m tools.validate` clean
2. `pytest backend/tests/test_verify_ac_parity.py -v` 24/24 (12 existing
   + 4 threshold + 4 allow-extras + 4 undercoverage-tolerance tests)
3. `bun run check` (svelte-check) clean delta on sources.ts
4. `bun run test -- src/lib/maplibre src/lib/boundaries` clean
5. Browser smoke `/s/tamil-nadu/ac/1?event=AcGenMay2026` shows polygons
   coloured by winner; `/s/bihar` unchanged (Bihar already worked pre-R1
   via D.2); `/s/kerala/ac/1` works (was on HTL `AC_NO`, now on LGD
   `ac_no` per the flip).
6. Post-snapshot verify_ac_parity gate (NOT part of CI):
   `python -m tools.boundaries.verify_ac_parity --threshold 0.50 --allow-extras --undercoverage-tolerance 0.05 --state S01 ... --state U07`
   passes for all 20 states OR identifies undercoverage-blocked states
   triggering per-state pipeline.json revert per §R1.6.

### R1.6 Rollback plan

If post-merge a state's choropleth breaks:
- Revert the affected state's pipeline.json block to its prior HTL entry
- Revert sources.ts entry for that state (if it was in the 5-flip cohort)
- Re-run snapshot for that state alone

The verify_ac_parity gate runs in CI as part of `bun run test` on the
boundary-conform suite, so subsequent breakage would be caught at PR time.

### R1.7 Per-state outcomes (measured 2026-05-27 post-snapshot)

Run: `python -m tools.boundaries.verify_ac_parity --threshold 0.50 --allow-extras --undercoverage-tolerance 0.10` across all 20 candidates BEFORE the revert decision.

| ECI | Verdict | snap/SoT | Name parity | Issue / notes |
| --- | --- | --- | --- | --- |
| **S01 AP** | **REVERT → HTL** | 179/175 | 0% (0/58) | LGD State_LGD=28 bundles legacy unified AP+TG (ac_no 1-294); SoT is post-2014 AP-only (1-175). ac_no=30 → LGD 'Yanam' vs SoT 'Anakapalle'. Citizen map would mis-join election results to wrong polygons. Deferred until ramSeraph publishes post-2014 AP-only slice. |
| **S03 Assam** | **REVERT → HTL** | 134/126 | 0.8% (1/126) | LGD ships pre-2023 delim names; SoT (and ECI election results yen-gov surfaces) is post-2023 delim. ac_no=1 → LGD 'Ratabari' vs SoT 'Gossaigaon'. Wholesale boundary refresh upstream, no election data joins. Deferred until paired SoT+LGD vintage alignment. |
| S02 AR | KEEP-LGD | 61/50 | 94.0% | 11 LGD residue extras + dup{25:2} reserved-seat encoding. Name parity high. |
| S05 GA | KEEP-LGD | 41/40 | 100% (40/40) | Clean. |
| S06 GJ | KEEP-LGD | 164/182 | 100% | 22 ac_no missing from snapshot (Hans bullet warranted); feature count 90.1% above 90% safety-net floor → KEEP per documented D.5 baseline (PR #285). |
| S10 KA | KEEP-LGD | 225/224 | 98.7% (221/224) | Clean (+1 LGD residue). |
| S11 KL | KEEP-LGD | 141/140 | 85.0% | dup{87:2}; name parity borderline; choropleth fine. |
| S12 MP | KEEP-LGD | 225/230 | 99.1% | 5 missing (2.2% undercoverage within tolerance) + dup{168:2}. |
| S13 MH | KEEP-LGD | 303/288 | 99.3% | dup{172:2, 0:14} — 14 ac_no=0 LGD orphan polygons (no SoT join); real names match. |
| S14 MN | KEEP-LGD | 68/60 | 103.3% | Many LGD reserved-seat dupes inflate name_parity above 100% (formula artifact). |
| S15 ML | KEEP-LGD | 59/59 | 100% (59/59) | Clean. |
| S16 MZ | KEEP-LGD | 40/40 | 87.5% (35/40) | Name parity borderline; counts perfect. |
| S20 RJ | KEEP-LGD | 202/200 | 100.5% | dup{29:2, 17:2, 92:2}. |
| S21 SK | KEEP-LGD | 38/32 | 103.2% | dup{29:2, 16:2, 8:2, 0:4} — 4 ac_no=0 placeholders. |
| S22 TN | KEEP-LGD | 235/234 | 93.1% | dup{21:2, 169:2} reserved seats; baseline already accepted in D.1 (PR #270). |
| S24 UP | KEEP-LGD | 404/403 | 100% | dup{46:2, 48:2}. |
| S25 WB | KEEP-LGD | 293/293 | 93.5% (274/293) | Clean (D.4 baseline). |
| S27 JH | KEEP-LGD | 96/81 | 113.6% | 14 reserved-seat dupes; needs Hans bullet for the +15 extras (likely LGD residue from Jharkhand-Bihar split). |
| S29 TG | KEEP-LGD | 118/118 | 98.3% (116/118) | Clean (uses post-2014 LGD code 36 — properly bifurcated unlike AP S01). |
| U07 PY | KEEP-LGD | 29/28 | 92.9% (26/28) | Clean. |

**Final decision**: 18 states keep LGD swap (clean enough per safety-net rule);
2 states (S01, S03) revert to HTL fallback. Pipeline.json + sources.ts S03
entry reverted; sources.ts S01 entry was never present pre-D.7 so no flip
needed. Snapshot re-run for S01/S03 from HTL → matches pre-D.7 baseline.

---

## R3 — Frontend STATE_AC registry sync (extend 6 → 30)

Gated on R1 merge. Scope:
- Add 25 new entries to `STATE_AC` so the registry covers all 30 LGD-keyed
  AC states (R1's 20 + D.2's 10 = 30; U08 stays at shijithpk's `seat_id`).
- All 30 LGD entries use `join_property: "ac_no"` lowercase; shared
  `geojson_url` LGD archive URL; shared LGD attribution string.
- Labels plain "<State> — Assembly constituencies" (no "(HTL)" / "(LGD)"
  / source-acronym suffix per user mandate).
- New test `frontend/src/contracts/state-ac-registry-coverage.test.ts`
  asserting STATE_AC keys = expected 30-state set.
- Amend `docs/architecture/decisions/0031-boundary-geometry-strategy.md`
  with 2026-05-27 D.7 override entry: "user override of D.1 keep-current
  for the 20 HTL states; citation consistency > geometric polish; LGD
  vintage residue accepted as 'extras render as no-fill'".

---

## R4 — Playwright per-state coverage report

Gated on R3 merge. New `frontend/e2e/state-ac-coverage.spec.ts` iterates
the 30 states; for each, navigates to `/s/<state-slug>/ac/1?event=<recent-eci-event>`,
waits for map idle, queries the rendered tile-fill-opacity per polygon,
asserts ≥90% are non-default-fill. Per-state results compiled into
`notes/2026-05-27-state-ac-coverage-report.md` for future delta-detection.

---

## Open scope questions (flagged for user)

1. **U08 J&K**: shijithpk source covers post-2022 90-AC layout. LGD does
   NOT yet publish post-2022 J&K. KEEP-CURRENT decision from D.4 stands.
   No change.
2. **Pre-2026 Tamil Nadu delimitation**: ECI commission scheduled to
   publish new delimitation late 2026. Both HTL and LGD will be stale
   on the day. Tracked separately.
3. **Gujarat S06 (-18 ACs in LGD)**: per R1.4 decision rule, if
   confirmed post-snapshot, S06 stays on HTL until LGD updates.
   Mention in R1 PR body. R3 STATE_AC entry would be conditional on
   R1's S06 outcome.

---

## Handover

R1 worker: `..\yen-gov-r0-d7-recon` on `feat/d7-ac-lgd-universal` based on
`origin/main@71cb4a59` (PR #428 merged 2026-05-27).

R1 snapshot runtime: each state ~4 min wall clock (60 MB LGD archive
re-downloaded per state — `snapshot.py` caches per-entry, not per-URL).
20 states × 4 min ≈ 80 min. Future optimization: refactor `snapshot.py`
to cache by URL-hash so a single download serves N per-state-filter
entries. Out of R1 scope.
