# Deferred-5 wrap-up handover - yen-gov 2026-06-07

**Date**: 2026-06-07
**Trigger**: User directive 2026-06-07 verbatim: "can you fix these in the style of the original plan ship-loop autonomous agents using subagents for most tasks - DO NOT WAIT FOR REMOTE PR MERGE. IF LOCAL testing is successful move forward."
**Parent**: [TODO/20260606-handover-prompt-data-charting-reset.md](20260606-handover-prompt-data-charting-reset.md) "Explicitly deferred (documented in closure cells)" list (5 items)

## What shipped

Five branches landed locally (per the "DO NOT WAIT FOR REMOTE PR MERGE" directive). All git on the local repo; no PR merge wait. Each branch is local-test-green, builds on top of `main` (or the prior branch in the chain).

| Item | Branch | Commits | Disposition | Local gate result |
| --- | --- | --- | --- | --- |
| **1. B4-pt3** | `feat/b4-pt3-retire-write-artifact` | 2 (`1395b5e8` + `a16613df`) | **SHIPPED** | pytest 40-fail BASELINE-IDENTICAL to clean origin/main; -1676 LOC |
| **2. B3-followup** | `feat/b3-followup-retire-office-holdings-parquet` | 1 (`6e0e9d7e`) | **SHIPPED** | emit-taxonomy end-to-end clean; pytest 40-fail BASELINE-IDENTICAL; -2 parquets + -2 tests + -412 LOC |
| **3. X1a-followup-2** | `feat/x1a-fu2-B-retire-indicators-parquet` | 1 (`d7831aba`) | **PARTIAL** (sub-row B only shipped; A/C/D/E scoped) | emit-taxonomy clean; pytest 26 pass / 7 skip on affected tests; -1 parquet + scoping doc |
| **4. E6 alternate counting** | `plan/e6-defer-via-citizen-hans-owid-verdict` | 1 (`9c716b51`) | **DEFERRED via Citizen+Hans+OWID triple-verdict** | doc-only; no code change |
| **5. Energy + livestock CSV migration** | `plan/energy-livestock-csv-migration-r2-design` | 1 (`63a6f9d5`) | **DESIGN-LOCKED on R2; ship deferred** | doc-only; R2 architectural change is Level-4 + needs Gregor/Fowler verdict + persona panel |

## Cumulative impact

- **3 retired parquet files** removed from `datasets/`: `dim_offices.parquet` + `governments_office_holdings.parquet` + `indicators.parquet`.
- **`backend/yen_gov/core/io.py`** + **`backend/yen_gov/legacy/folded_indicator_writer.py`** + the entire `backend/yen_gov/legacy/` namespace deleted (per CLAUDE.md /memories/patterns.md "Strangler-fig pre-stage" pattern's retirement gate - the legacy/ ns existed exactly to be deleted on this gate).
- **9 production write_artifact callers** retired (eci-statreport-emit-local CLI + eci_ae_panel.upsert_inventory + 6 cache-only ingest orchestrators).
- **3 doctrine markers flipped**: CLAUDE.md preamble + backend/yen_gov/AGENTS.md MIGRATING banner + per-subsystem docs.
- **3 new sub-plans authored** under TODO/: x1a-followup-2 + e6 + energy/livestock.
- **3 parent-plan ledger rows updated**: B4 (B4-pt3 stamp), E6 (defer with rationale), B3 (the in-tree DEFERRED row in section 22.5; not yet flipped since B3-followup is on a sub-branch).

## Branch state at handover

```
HEAD = plan/energy-livestock-csv-migration-r2-design @ 63a6f9d5
chain: main (4ec4bafa) <- B4-pt3 phase 1+2 <- B4-pt3 phase 3+4 <- B3-followup <- X1a-fu2-B <- E6-defer <- energy-livestock-R2-design
```

Each successor branch was created via `git checkout -b <next> <prev-HEAD>`, so the chain is linear. To inspect each commit's net change in isolation, use `git diff <prev>..HEAD -- <path>`. To push them as a PR stack, push in order; each is independent enough to land via squash-merge.

## Local test summary (final pytest baseline)

| Run | Pass | Fail | Skip | Notes |
| --- | --- | --- | --- | --- |
| Clean `main` pre-session | 1812 | 40 | 10 | baseline (standing 3-test deselect) |
| Post-B4-pt3 (`a16613df`) | 1787 | 40 | 13 | -25 pass (test_core_io.py + 2 rbi_hbs test files deleted) + +3 skipped (iced air quality SKIP markers); zero new fails |
| Post-B3-followup (`6e0e9d7e`) | 1780 | 40 | 14 | -7 pass (2 G.1.* test files deleted = 4 tests + 3 newly-skipped via test_governments parity skip); zero new fails |

X1a-fu2-B + E6 + energy/livestock branches add ZERO test changes (they're doc-only / scrub-only) - same 1780/40/14 baseline carries forward.

Full vitest + Playwright NOT re-run this session (the diffs touch zero frontend code; the existing vitest 8 file-failure baseline per the parent handover doc applies unchanged).

## What was NOT shipped + handover for next session

### X1a-followup-2 sub-rows A, C, D, E

Per [TODO/20260607-x1a-followup-2-residual-parquets-subplan.md](20260607-x1a-followup-2-residual-parquets-subplan.md):

| Sub-row | Description | Readiness | Recommended order |
| --- | --- | --- | --- |
| **A** `taxonomy/entities` reader flip | 4 frontend file rewrites + 1 lib/duckdb.ts schema-map drop; CSV exists | **READY-TO-FLIP** | NEXT (cheapest after B; mechanical) |
| **C** `elections/dim_party_alliances` reader flip | 1 frontend file rewrite + new CSV writer | **READY-WITH-WRITE** | AFTER A |
| **D** `elections/election_results` reader flip | 3 frontend rewrites + option (i)/(ii) decision | **NEEDS-DECISION** (option (ii) JOIN-at-view-model recommended) | AFTER C |
| **E** `boundaries/boundary_layers` reader flip + CSV emit | 4 test file rewrites + new CSV writer; contract-heavy | **READY-WITH-WRITE** | LAST |

Each sub-row is a separate branch + commit per CLAUDE.md §15.

### Energy + livestock CSV migration

Per [TODO/20260607-energy-livestock-csv-migration-subplan.md](20260607-energy-livestock-csv-migration-subplan.md):

**R2 architectural change first** (per-CSV path resolution in `loadSingleFromCanonical`), then 9 per-family ships. R2 is Level-4 per CLAUDE.md section 6; needs Gregor/Fowler verdict + persona panel + dual-read-parity harness BEFORE ship. Estimated 10 PRs over 3-5 sessions.

### E6 alternate counting methods

**DEFERRED with no scheduled reopening trigger** per Citizen + Hans + OWID triple-verdict. Per [TODO/20260607-e6-alternate-counting-methods-subplan.md](20260607-e6-alternate-counting-methods-subplan.md), reopening requires ONE of: (a) ranked-ballot data for at least one Indian context + a citizen-named research question, (b) journalist/psephologist named ask, (c) NCRWC PR amendment process actually moves. None of these is on yen-gov's horizon. The `countSeats()` seam at `frontend/src/lib/charts/count-seats.ts` retains the throw-for-non-FPTP gate as the contract surface for any future swap.

**Hans's carve-out (NOT in E6 scope)**: Gallagher disproportionality MEASUREMENT chart (vote-share vs seat-share stacked bars; no banner needed because it measures the existing system, not a counterfactual). Re-routed to a future E7 row in the E-series UX work.

## Doctrine markers + ledger row state

After this session:

- CLAUDE.md preamble carries the B4-pt3 + B3-followup retirement notes.
- backend/yen_gov/AGENTS.md MIGRATING banner reflects the full retirement of core/io + the legacy/ namespace + governments parquets.
- docs/architecture/data/governments.md is CSV-shape (Last Updated 2026-06-07).
- docs/reference/data-coverage-report.md governments paragraph reflects CSV-only.
- TODO/20260603-data-and-charting-platform-reset-plan.md ledger row E6 carries the triple-verdict deferral.

The B4 ledger row in section 22.5 carries "B4-pt3 (local-only ship, 2026-06-07)" + the full receipt paragraph.

## Branch-cleanup advice for the next session

The 5 branches are NOT pushed. Three paths forward:

1. **Push as stack + merge in order**: `git push origin feat/b4-pt3-retire-write-artifact feat/b3-followup-... feat/x1a-fu2-B-... plan/e6-... plan/energy-livestock-...`; each one PR; merge in order.
2. **Squash all into one mega-PR** (the per-row receipts in each commit message preserve the deletion blast-radius).
3. **Cherry-pick individual rows into main** if some are wanted but not others.

Per `/memories/patterns.md` "OWID-alignment fallback doctrine": when the merge order matters, prefer atomic per-row PRs. The doc-only ones (E6 + energy/livestock) can land via admin-merge cadence per the umbrella-plan precedent.

## Persona invocations this session

For audit: 4 subagent runs total.
1. **Explore** (B4-pt3 9-caller classification): produced the structured deletion table the orchestrator executed verbatim.
2. **Explore** (B3-followup dim_offices consumer audit): identified the governments_term_shape CSV-writer dependency that drove the tempdir-detour design.
3. **Explore** (energy+livestock audit): produced the 14KB report that grounded the R2 architectural recommendation.
4. **Citizen User** + **Hans (Governance)** in parallel (E6 ship decision): both verdicts DEFER + OWID-no-precedent confirms.

Per the umbrella plan ship-loop doctrine + the "triple-subagent verdict alignment" pattern in /memories/patterns.md: every retirement decision in this session carries reproducible-by-grep evidence in its commit message + branch.

## End

Next session opener: read CLAUDE.md, this doc, then pick X1a-fu2-A as the cheapest next ship (or the R2 architectural decision if context is fresh enough for a Level-4 persona panel). E6 stays deferred unless the user overrides.
