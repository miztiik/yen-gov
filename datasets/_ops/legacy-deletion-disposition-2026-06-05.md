# Legacy-deletion disposition — B2b.5 PR-stage 0d-del (2026-06-05)

PR-stage **0d-del** of the B2b.5 elections clean-start reingest
([TODO/20260604-b2b5-elections-reingest-subplan.md](../../TODO/20260604-b2b5-elections-reingest-subplan.md))
is "DELETE `ac_crosswalk.*` + old `electoral_lgd_xwalk.csv` + the legacy
`electoral_csv.py`/test + `lgd_acs`/`lgd_pcs.json` consumers LAST, once no live
reader remains".

## Outcome: delete NOTHING now — the plan's delete-list is stale

A grep audit + a thorough read-only subagent investigation found that **four of
the five 0d-del targets are LIVE, actively-tested canonical entities owned by
OTHER chunks**, and the fifth is entangled with a live test of another chunk.
The plan's 0d-del language was written against a topology that did not
materialise (it assumed `electoral_lgd_xwalk.csv` would be *renamed* to
`electoral_district_membership.csv` and that `ac_crosswalk.csv` was the synthetic
`state_code*1000+eci_no` crosswalk). On the current `main` neither assumption
holds. Deleting any target now would hard-fail live tests + a parity gate — a
regression. Mirroring the 0e disposition, this stage **emits this receipt +
forward-pointers and deletes nothing**; the legacy cleanup is re-scoped to the
chunks that own each artifact.

The B2b.5 **deliverable is complete without these deletions**: the spine (0a-0e)
+ the full assembly corpus (30 states, 474 CSVs) + parliament (11 LS cycles) are
merged. 0d-del was a tidy-up, not a delivery gate.

## Per-target disposition

| Target | Reality on `main` | Owning chunk | Disposition |
| --- | --- | --- | --- |
| `datasets/data/entities/ac_crosswalk.csv` | LIVE B2b.4.6 canonical entity (authoritative `eci_no -> lgd_ac_id` per delim, sourced from `datasets/taxonomy/ac_crosswalk.parquet` via `reingest/ac_crosswalk.py`). `columns.json` declares it (line ~320) and **explicitly distinguishes it** from `electoral_lgd_xwalk.csv`. Hard-fail tests: `test_reingest_ac_crosswalk.py`, `test_csv_parquet_parity::test_ac_crosswalk`, `test_build_ac_crosswalk.py`. NOT the synthetic crosswalk the plan meant. | **B2b.4.6** | FORWARD — retire (if ever) under the chunk that owns the `ac_crosswalk.parquet` lineage; NOT a B2b.5 deletion. |
| `datasets/data/entities/electoral_lgd_xwalk.csv` | LIVE B2a.7 entity (253-row boundary-overlap decay-receipt, `seed/electoral_lgd_xwalk_csv.py`). `columns.json` declares it (line ~89). 0c-2 created a **NEW** `electoral_district_membership.csv` and **left xwalk in place** (a distinct concept per the columns.json note), so the plan's "rename" never happened. Hard-fail test: `test_seed_electoral_lgd_xwalk_csv.py` (16 cases). | **B2a.7** | FORWARD — retire under B2a.7 / the boundary-decay owner if it is genuinely superseded; NOT a B2b.5 deletion. |
| `backend/yen_gov/canonical/seed/electoral_csv.py` (legacy emitter) | SUPERSEDED by `electoral_csv_from_snapshot.py` (0c-2, per its docstring), and no live pipeline imports it — BUT it is still imported by `test_seed_electoral_csv.py` AND by the **live B2a.7 test** `test_seed_electoral_lgd_xwalk_csv.py:332` (`from …seed.electoral_csv import emit`). Deleting it now would hard-fail that B2a.7 test. | **B2a.6 / B2a.7** | FORWARD — retire only after the B2a.7 xwalk test is repointed off the legacy emitter (a B2a-owned change); deleting it from B2b.5 would break a cross-chunk test. |
| `datasets/taxonomy/lgd_acs.json` | LIVE taxonomy oracle read by TWO emitters (`seed/electoral_csv.py` B2a.6, `seed/electoral_lgd_xwalk_csv.py` B2a.7) AND from disk by `test_lgd_taxonomy.py` (8-case FK-closure chain, hard-fail). Has a committed `lgd-acs.schema.json`. | **taxonomy / X1b** | FORWARD — the round-8 doctrine keeps the legacy taxonomy JSON as a cross-check oracle, replaced at source by the LGD snapshot but deleted only when the taxonomy layer retires (X1b), not by B2b.5. |
| `datasets/taxonomy/lgd_pcs.json` | LIVE taxonomy oracle read by `seed/electoral_csv.py` (B2a.6) + from disk by `test_lgd_taxonomy.py` (3-case, hard-fail). Has `lgd-pcs.schema.json`. | **taxonomy / X1b** | FORWARD — same as `lgd_acs.json`. |

## Gate `full validator green + grep no live reader`

The gate's precondition ("no live reader remains") is **not met** for any target —
each has a live emitter and/or hard-fail test. The gate therefore correctly
*blocks* deletion; this receipt records that the blocker is real (the targets are
live), not a missed cleanup. When each owning chunk retires its artifact, the
grep-no-live-reader check will pass there and the deletion lands in that chunk's
PR.

## Reproduction

```
git grep -nE 'ac_crosswalk'          -- backend frontend datasets/data/_schema
git grep -nE 'electoral_lgd_xwalk'   -- backend frontend datasets/data/_schema
git grep -nE 'seed\.electoral_csv'   -- backend
git grep -nE 'lgd_acs|lgd_pcs'       -- backend
```
