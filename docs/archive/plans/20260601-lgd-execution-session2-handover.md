# LGD-canonical execution: session 2 handover

**Date:** 2026-06-01
**Session shipped:** PRs #552, #553, #554, #555, #556, #557 (six merges, F5 paths)
**Parent plan:** [TODO/20260601-lgd-canonical-plan.md](20260601-lgd-canonical-plan.md)
**Execution split:** [TODO/20260601-lgd-execution-handover.md](20260601-lgd-execution-handover.md)
**STOP rationale:** every remaining live row crosses a real-network / real-data correctness boundary that needs operator-supervised verification, per the user memory's `STOP-AT-USER-JUDGMENT-BOUNDARY` rule.

## Shipped this session

| PR | Row | Title | Merge SHA |
| --: | --- | --- | --- |
| #552 | (pre-flight) | docs(boundaries): clarify districts ship as one national file | `7ccc88e3` |
| #553 | A1 | ADR-0050: folder-naming convention `state=<lgd-name-slug>` | `62f63419` |
| #554 | A2 | docs(concepts): lgd-authority concept doc | `2dc09369` |
| #555 | L1a | seed `datasets/taxonomy/lgd_states.json` (36 states/UTs) | `91c31230` |
| #556 | L1b | seed `datasets/taxonomy/lgd_districts.json` (784 districts) | `3ed5426d` |
| #557 | A3 | `docs/architecture/data/lgd-canonical-keys.md` (join contract) | `de6c7423` |

Wave 1 + 2 of the execution-handover are complete, except for L1c (AC seed) and L1d (Tier-A FK tests), both blocked below.

## Status reckoner (post-session)

| # | Row | Status | Blocked on |
| :-: | --- | --- | --- |
| L1a | states seed | DONE #555 | - |
| L1b | districts seed | DONE #556 | - |
| L1c | ACs seed (~4123 rows) | **BLOCKED** | LGD AC-directory snapshot (no in-repo CSV) |
| L1d | Tier-A FK tests | BLOCKED-on-L1c | L1c |
| A1 | ADR-0050 | DONE #553 | - |
| A2 | concept doc | DONE #554 | - |
| A3 | join-contract doc | DONE #557 | - |
| M1 | rename tool (design + tests) | **NEXT-UP, UNBLOCKED** | none (L1a complete) |
| M2 | execute rename on `datasets/boundaries/**` | BLOCKED-on-M1 | M1 |
| M3 | execute rename on `datasets/elections/**` | BLOCKED-on-M2 | M2 |
| M4 | execute rename on residual `datasets/**` | BLOCKED-on-M3 | M3 |
| F1 | frontend redirect map + golden-path e2e | BLOCKED-on-M2 | M2 |
| AC1a | per-state AC geometry (Sikkim canary first) | BLOCKED-on-L1c | L1c |
| AC1b | stamp `lgd_ac_id` on AC features | BLOCKED-on-L1c+AC1a | L1c + AC1a |
| D1' | retire `apply_ac_no_rewrite_by_name` + S01 frontend rework | BLOCKED-on-AC1b-S01 | AC1b for S01 |
| CLOSE | distill + archive | BLOCKED-on-all-above | - |

## Why STOP here (not push deeper)

The remaining rows split into two flavours, both of which need a human-in-the-loop boundary that a single autonomous session cannot honestly cross:

### Flavour 1: real-data correctness

- **L1c** needs the LGD AC directory (~4123 rows). The in-repo `datasets/taxonomy/lgd/` folder has states + districts + subdistricts CSV snapshots but NO AC CSV. Options:
  - Scrape LGD portal `globalviewstateforcitizen.do` per state (~36 round-trips; portal is session-based and often flaky on autonomous probes).
  - Fetch a community mirror (ramSeraph or similar) — but the GoI-only doctrine in the parent handover-doc requires the citation to name the LGD authority. Mirror-as-fetch-path is acceptable; mirror-as-citation is not.
  - Either path, the row-level correctness needs a per-state spot-check against existing boundary `AC_ID` values to catch silent ECI<->LGD numbering divergences (the same kind of trap that motivated ADR-0049). One agent session cannot do that spot-check at 4123-row scale.
- **AC1a per-state** needs Survey of India / Bhuvan / state-portal source-hunting for AC geometry, then per-state ingest. Max-style triage. Sikkim canary first (4-district old / 6-district new discrepancy logged in handover). Each state is its own PR; ~30 states = ~30 PRs. Cohort budgeting + concurrency-cap (5 parallel) is itself a plan-doc-level decision.

### Flavour 2: XL-risk big-bang

- **M1 -> M4** rewrite every Parquet partition key from `state=in_sXX` to `state=<slug>`. Plan-doc tags XL risk. Reversible only via dry-run + manifest + audit before each execute. Fowler-domain refactor work that deserves its own session with dedicated test coverage. Shipping M1 design without M2 execute in the same session is fine; shipping M2 without operator-eyes-on-the-manifest is not.
- **F1** depends on M2 (the partition rename surfaces the new slugs that the redirect-map covers).

## Recommended next-session plan

Pick ONE of these to drive the next session:

1. **L1c-first** (data path): commission a focused source-hunt for the LGD AC directory snapshot. Output: `datasets/taxonomy/lgd/acs-latest.csv` + sidecar provenance. Then ship L1c JSON build per the L1a/L1b pattern. Estimated 1 session.
2. **M1-first** (tool path): author `tools/migrate/rename_partition_keys.py` with dry-run mode + manifest output + tests. Does NOT execute the rename. Output is reviewable by Fowler before M2 commits. Estimated 1 session.
3. **L1d-and-tighten** (validator path): add Tier-A coverage for `lgd_states.json` + `lgd_districts.json` + cross-FK checks. Wire the new schemas into `datasets/schema-compatibility.json` per ADR-0047. Smaller scope; useful to land before L1c so the L1c PR can lean on the FK tests.

Order suggestion (low-to-high risk): **(3) -> (1) -> (2) -> M2 -> M3 -> M4 -> F1 -> AC1a cohort -> AC1b -> D1' -> CLOSE**.

## Process gotchas observed (for the next session's agent)

- **Master worktree owns a sibling branch (`yen-gov-sym-distill` on `main`)**. Every `gh pr merge` in this session produced the cosmetic `fatal: 'main' is already used by worktree` error; the server-side squash + remote-branch delete still ran clean. Verify via `gh pr view <n> --json state,mergeCommit`. Manual remote-branch delete is required after each merge.
- **Builder pattern works**. `tools/migrate/build_lgd_states.py` + `build_lgd_districts.py` are small (one Python file each), deterministic, fail-fast, and reproducible. L1c should follow the same shape: builder takes upstream CSV + cross-joins against `lgd_states.json` + emits JSON + fails on FK violations.
- **Slug uniqueness rules differ per level**. States: slugs are globally unique by construction (no name collisions among 36). Districts: slugs are unique WITHIN a state; cross-state name collisions get a numeric salt (`hamirpur-XX`). ACs: similar pattern expected (~4123 ACs, many name reuses across states).
- **CSV provenance sidecar exists**. `datasets/taxonomy/lgd/states-latest.csv.sources.json` carries the LGD authority citation. The JSON taxonomy emits its own `sources[]` citing LGD directly; the ramSeraph mirror is mentioned in the sidecar as the operator's fetch path, NOT in the JSON's citation.

## See also

- [TODO/20260601-lgd-canonical-plan.md](20260601-lgd-canonical-plan.md) - parent plan
- [TODO/20260601-lgd-execution-handover.md](20260601-lgd-execution-handover.md) - per-row split (this session's source-of-truth)
- [docs/architecture/data/lgd-canonical-keys.md](../docs/architecture/data/lgd-canonical-keys.md) - join contract (PR #557)
- [docs/architecture/decisions/0050-folder-naming-lgd-slug.md](../docs/architecture/decisions/0050-folder-naming-lgd-slug.md) - ADR-0050 (PR #553)
- [docs/concepts/lgd-authority.md](../docs/concepts/lgd-authority.md) - LGD-as-canonical doctrine (PR #554)
