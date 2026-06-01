# LGD-canonical execution: session 3 handover + plan-doc closure

**Date:** 2026-06-01 (session 3)
**Shipped:** PRs #559 (L1c+L1d), #561 (M1), #562 (M2), #565 (M3) - plus this closure PR
**Parent plan:** [`TODO/20260601-lgd-canonical-plan.md`](20260601-lgd-canonical-plan.md)
**Execution split:** [`TODO/20260601-lgd-execution-handover.md`](20260601-lgd-execution-handover.md)
**Successor plan:** [`TODO/20260601-lgd-partition-rename-successor-plan.md`](20260601-lgd-partition-rename-successor-plan.md) - rows M4 + F1 remain
**Session 2 handover:** [`TODO/20260601-lgd-execution-session2-handover.md`](20260601-lgd-execution-session2-handover.md) (PRs #552-#558)

## What landed this session

| PR | Row | Title | Merge SHA |
| --: | --- | --- | --- |
| #559 | L1c+L1d | seed `lgd_acs.json` (3918) + `lgd_pcs.json` (533) + AC-district map + 7 Tier-A FK tests | `9bc286cb` |
| #561 | M1 | `rename_partition_keys` tool + dry-run manifest + Mx successor plan-doc | `c249b81c` |
| #562 | M2 | rename `datasets/boundaries/**` state= partitions (225 dirs + frontend bridge) | `5fd95efd` |
| #565 | M3 | rename `datasets/elections/**` partitions + writer SQL + manifest + tests + 7 docs | `8e14edea` |
| this | CLOSE | session-3 handover + close parent + flag yenask blocker | _pending_ |

## What's complete

- **L1 taxonomy**: 36 states + 784 districts + 3918 ACs + 533 PCs all seeded with cross-FK Tier-A tests
- **A1+A2+A3 doctrine**: ADR-0050 + `docs/concepts/lgd-authority.md` + `docs/architecture/data/lgd-canonical-keys.md`
- **Partition rename**: 261 dirs (225 boundaries + 36 elections) flipped from `state=in_sXX` to `state=<lgd-slug>`
- **Writer + ingest**: canonical writer emits LGD slugs; pincode ingest resolves ECI -> slug via `lgd_states.json` lookup; both reproducible without further sourcing
- **Reader bridges**: frontend `ECI_TO_LGD_SLUG` map exported from `sources.ts`; tests + path resolver + boundaries.ts use it

## What remains (handed off)

### Critical (blocks running yenask end-to-end)

**Yenask `state_partition_id` decouple.** Yenask's `state_partition_id` is BOTH a canonical-id in the InsightIntent CDM AND a Hive partition value. M3 changed the Hive value to `tamil-nadu` but left yenask emitting `in_s22`. Tests fail:
- `src/lib/yenask/extract-intent.test.ts` 12 fails
- `src/lib/yenask/semantic-catalogue.test.ts` 2 fails
- `src/lib/yenask/contracts/insight-intent.test.ts` 3 fails
- `frontend/e2e/duckdb-harness.spec.ts` + `frontend/e2e/yenask.spec.ts` will fail on real runtime

**Decoupling decision (needs Hans + Gregor + Andre dispatch):**
- Option A: yenask's `state_partition_id` becomes the LGD slug everywhere; update extractor + Zod regex + canned intents + semantic-catalogue fixtures.
- Option B: introduce a separate `state_lgd_slug` field; keep `state_partition_id` as the legacy display id; concepts.ts gets a `lgd_slug_for(state_partition_id)` translator at the `slice_registrations` boundary.

The plan-doc this should land under is the existing party-symbol / yenask evolution thread, NOT a new LGD-canonical extension.

### Low-risk (can ship anytime)

- **M4 residual**: per the M3 ship, every `state=in_*` partition under `datasets/` has been renamed by M2+M3. `tools.migrate.rename_partition_keys --root datasets` would now discover 0 pairs. M4 is effectively a no-op; close it WITH the next session's first PR after a fresh discover-and-confirm.
- **F1 redirect map + golden-path**: URLs already use LGD slugs per ADR-0048, so this is also expected no-op. Verify with a smoke pass through `bun run dev` -> `/s/haryana` and a fresh `golden-path.spec.ts` assertion that no `state=in_*` shows up anywhere in network traffic.

### Documentation backlog

- `docs/architecture/decisions/0050-folder-naming-lgd-slug.md` - amend the "Status" section with the M2+M3 retrospective; add a "Migration complete (2026-06-01)" subsection citing the PR chain.
- `docs/concepts/admin-level-sourcing.md` - cross-link to `lgd-authority.md`.
- Lessons file (`/memories/lessons.md`) - this session's key lessons (see below).

## Lessons (for /memories/lessons.md)

1. **Master worktree off `main` is the F5-clean precondition** - confirmed by clean merges for #559, #561, #562, #565 (4 consecutive F5-cleans). When the master worktree is parked on a scratch branch (`scratch-master-parking`) and no other worktree holds `main`, `gh pr merge --squash --delete-branch` runs without the cosmetic worktree error. Single-line cost to set up (`git checkout -b scratch-master-parking`); recovers ~30s per PR cleanup.

2. **Partition-rename PRs need per-surface bundling, not big-bang** - even with the rename tool ready in M1, M2 and M3 each had 9-18 reader files (frontend tests, backend writer SQL, manifest.json, CI, docs) that had to flip in the SAME commit. Splitting M2 (boundaries) from M3 (elections) was correct - M2's frontend bridge (`ECI_TO_LGD_SLUG` map exported from `sources.ts`) is what M3 reuses without writing a second bridge.

3. **DuckDB CASE expressions built from JSON at module-load are the cleanest pattern for ECI->slug lookups in SQL** - `_eci_to_lgd_slug_case_sql()` in writer.py wraps `lgd_states.json` rows into `CASE 'S22' THEN 'tamil-nadu' WHEN ... END`. Cached for the process lifetime; zero per-query overhead. Generalisable to any "Python emits SQL that needs a row-by-row mapping" scenario.

4. **Yenask `state_partition_id` is BOTH CDM-id AND Hive-key - that coupling is the design wart M3 exposed.** Bulk-flipping `in_s22` -> `tamil-nadu` inside yenask code broke 17 tests because the extractor's Zod regex `^in_[a-z][a-z0-9_]+$` rejects slugs AND the canonical-id flows through `IN-<STATE>-...` entity_id construction via `.replace(/^in_/, "").toUpperCase()`. The right fix is to separate the CDM-id from the Hive-key; that's a yenask-evolution PR, not an LGD-canonical PR.

5. **Stale-index lock recovery after `gh pr merge` from a sibling worktree** - when M2 merged in the work worktree while master was on a different branch, the local worktree's index could become stale, leaving `state=in_sXX` paths in the working tree showing as `D` (deleted) status. Recovery: `git fetch origin --quiet; git reset --hard origin/main` from the work worktree resets cleanly.

6. **Test-file flips need MORE care than data flips** - bulk-substituting `in_sXX` -> `<slug>` literals in test files is wrong when those tests use the literal AS A REGEX SOURCE OF TRUTH (e.g. `match(/^state=in_([su]\d{2})$/)`). The right pattern: introduce a `SLUG_TO_ECI` bridge in the test file, change the regex to `state=(.+)`, route through the bridge. M2 + M3 needed this for 6 registry-coverage test files.

## Net effect on the repo

Before this session:
- 261 `state=in_sXX` partition dirs
- writer emits `in_sXX` SQL
- pincode ingest emits `in_sXX` slugs
- manifest.json 72 partition references
- 13+ docs reference legacy slug

After this session:
- 261 `state=<lgd-slug>` partition dirs (haryana, tamil-nadu, jammu-and-kashmir, ...)
- writer emits LGD slugs via `lgd_states.json`-driven CASE
- pincode ingest emits LGD slugs via `lgd_states.json` lookup
- manifest.json fully updated
- 13+ docs updated to LGD-slug examples

## Recommended next-session order

1. **F1 (~30 min)** - verify URL grammar + golden-path assertion; expected no-op
2. **M4 close (~10 min)** - run `rename_partition_keys --root datasets` discover; if 0, close the row
3. **Yenask decouple (~1 session)** - Andre + Gregor dispatch to choose Option A vs B, then ship
4. **Plan-doc archive (~15 min)** - archive parent + successor plan-docs per `distill-a-plan.md`
5. **Lessons distill** - bake session-3 lessons into `/memories/lessons.md`

## See also

- [docs/architecture/decisions/0050-folder-naming-lgd-slug.md](../docs/architecture/decisions/0050-folder-naming-lgd-slug.md)
- [docs/concepts/lgd-authority.md](../docs/concepts/lgd-authority.md)
- [docs/architecture/data/lgd-canonical-keys.md](../docs/architecture/data/lgd-canonical-keys.md)
- [tools/migrate/rename_partition_keys.py](../tools/migrate/rename_partition_keys.py)
- [tools/migrate/rename_partition_keys.sample_manifest.json](../tools/migrate/rename_partition_keys.sample_manifest.json) (frozen reference for the 261-rename surface)
