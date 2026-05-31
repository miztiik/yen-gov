# Frontend e2e Runtime Trim Plan

**Last Updated**: 2026-05-31
**Status**: PROPOSED - no PRs opened yet. Pick up PR-1 first; PR-2 and PR-3 depend on PR-1 landing.
**Correction level**: 3 - cross-cutting cleanup across Playwright config, e2e specs, and a CI workflow addition. Escalate to Level 4 if a row needs to delete or relocate existing vitest/contract coverage.
**Doc-class**: plan-doc per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md). On close, distill into [docs/architecture/testing.md](../docs/architecture/testing.md) under a new "e2e scope and canary subset" section.
**Base branch discipline**: every execution PR branches from `origin/main`, never from this plan-doc branch or another in-flight worktree.
**Subagent doctrine**: each row dispatches a `runSubagent` (Fowler for engineering craft, Jony+Citizen if any copy/UX change leaks in) BEFORE the commit, not after. Verdict is applied verbatim, not re-interpreted.

## 0. Mandate

User request, 2026-05-31:

> does it make any sense to test all states? ... What is the golden e2e testing - that is also taking a very long time ... can write down these 4 PR plan in the TODO, so we can pick it up for some other agent - execution as subagents, and eventually distill the plan to /docs to document the decision.

The e2e suite is taking ~tens of minutes on PR CI because (a) the AC coverage matrix runs all 31 states, (b) Playwright runs `workers: 1` and `fullyParallel: false`, (c) `mobile-pixel-5` runs every spec, not just the breakpoint-sensitive ones, (d) `golden-path.spec.ts` has accreted assertions that belong in unit/contract tests. This plan turns the trim into four small PRs.

## 1. Load-bearing context

- [CLAUDE.md](../CLAUDE.md) Holy Laws #3, #5, #10.
- [docs/agents/bootstrap.md](../docs/agents/bootstrap.md) - load before any execution turn.
- [docs/architecture/testing.md](../docs/architecture/testing.md) - tier matrix; this plan adds an e2e-scope section on close.
- [docs/architecture/frontend/data-loading.md](../docs/architecture/frontend/data-loading.md) - Vite `serveDatasets()` GET-only middleware (why the spec hooks the map's own GET).
- [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md) - boundary loader contract.
- [docs/concepts/citizen-first.md](../docs/concepts/citizen-first.md) - what golden-path must actually prove for a citizen.
- [docs/archive/plans/20260529-boundary-rip-and-replace-plan.md](../docs/archive/plans/20260529-boundary-rip-and-replace-plan.md) Phase A.4 - origin of the 31-state matrix (one-time migration receipt, not a permanent gate).
- [frontend/playwright.config.ts](../frontend/playwright.config.ts), [frontend/e2e/state-ac-coverage.spec.ts](../frontend/e2e/state-ac-coverage.spec.ts), [frontend/e2e/golden-path.spec.ts](../frontend/e2e/golden-path.spec.ts), [frontend/e2e/boundary-benchmark.spec.ts](../frontend/e2e/boundary-benchmark.spec.ts).
- Sibling unit/contract anchors: [frontend/src/contracts/state-ac-registry-coverage.test.ts](../frontend/src/contracts/state-ac-registry-coverage.test.ts), [frontend/src/contracts/boundaries-conform.test.ts](../frontend/src/contracts/boundaries-conform.test.ts).

## 2. Doctrine

Cheap tiers own exhaustive coverage; Playwright owns representative citizen journeys.

- Schema/registry symmetry and shard presence are **contract** concerns, not e2e. If a fact can be proven by reading on-disk files + a TS module, it belongs in vitest.
- Per-state Playwright matrices are appropriate **only** as one-time migration receipts (Phase A.4 shape), not as standing PR gates.
- `mobile-pixel-5` runs only where a breakpoint-specific code path exists. Doubling CI to test identical desktop/mobile code paths is waste.
- Performance benchmarks are not citizen invariants; they ship behind an opt-in tag.
- Golden-path stays under the citizen journey it advertises (home -> state -> AC -> party): mounts, no `pageerror`, one `SourceList` assertion per data-bearing route. Theme/option/copy assertions belong in vitest or in spec files dedicated to those surfaces.

## 3. Status ready reckoner (UPDATE AFTER EVERY PR)

| Row | PR scope | PR | Status | SHA | Notes |
|---|---|---|---|---|---|
| PR-1 | Playwright config: `fullyParallel: true`, `workers: CI?2:4`, scope `mobile-pixel-5` to breakpoint-sensitive specs only, tag `boundary-benchmark.spec.ts` `@bench` and exclude by default. | #520 | DONE | b027aaa4 | Pure config; no spec body changes. CI Playwright e2e ran in 6m41s; wall-time delta vs pre-#520 baseline will surface on PR-2 CI. |
| PR-2 | AC coverage canary: reduce `STATE_CODES` to 5 canaries; full 31 behind `process.env.AC_COVERAGE_FULL`. Add path-filtered + nightly workflow that sets the env var. | #_pending_ | DONE | _pending_ | Canary covers ordinary LGD (S24), LGD-with-rewrite (S01), district-fallback (S03), elected UT (U05), non-LGD seat_id (U08). Full matrix runs nightly + on path-filtered PRs touching sources.ts / AC shards / taxonomy / contract / this spec via .github/workflows/e2e-ac-full.yml. |
| PR-3 | Golden-path slim-down: move theme-dropdown + temporal-caption assertions to dedicated specs or vitest. Target <= 80 lines. | _pending_ | PROPOSED | - | Touch most files; do last so PR-1+PR-2 have proven the new shape. |
| PR-4 | Distill doctrine: add "e2e scope and canary subset" section to [docs/architecture/testing.md](../docs/architecture/testing.md); archive this plan-doc per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md). | _pending_ | PROPOSED | - | Closes the plan. Only ship after PR-1+PR-2+PR-3 are merged and wall-time delta is verified. |

## 4. PR specifications

### PR-1 Playwright runtime config

**Files touched**: [frontend/playwright.config.ts](../frontend/playwright.config.ts) only.

**Changes**:
- `fullyParallel: true`.
- `workers: process.env.CI ? 2 : 4`.
- Per-project `testMatch`: `mobile-pixel-5` runs only `golden-path.spec.ts`, `extended-routes.spec.ts`, `indicator-ranked-polish.spec.ts` (the breakpoint-sensitive set per existing spec comments). `chromium` runs everything except `boundary-benchmark.spec.ts`.
- Add `grepInvert: /@bench/` to default config; add a project or env-gated path that includes `@bench` for manual perf runs.
- Tag `boundary-benchmark.spec.ts` with `@bench` (`test.describe('boundary benchmark @bench', ...)` or per-test).

**Acceptance gates**:
- Gate 3 svelte-check green.
- Gate 4 vitest green.
- Gate 5: `bun run test:e2e` locally and report wall-time before/after in PR body. No spec regressions.
- Validate-skipped (no datasets).

**Subagent**: dispatch `Fowler (Engineering)` with prompt "research only; review the config diff; flag any Playwright worker-state assumption broken by parallel + workers>1 (e.g. shared dev server, port 5173 singleton, fixture cleanup)". Apply verdict verbatim before commit.

**Risk**: a spec that secretly assumes serial execution flakes under parallel. Mitigation: run twice locally; if flake appears, lower workers to 2 for non-CI and document.

### PR-2 AC coverage canary + opt-in full matrix

**Files touched**: [frontend/e2e/state-ac-coverage.spec.ts](../frontend/e2e/state-ac-coverage.spec.ts), new `.github/workflows/e2e-ac-full.yml`.

**Changes**:
- In `state-ac-coverage.spec.ts`, replace `STATE_CODES` with:
  - `CANARY_CODES = ["S24", "S01", "S03", "U08", "U05"]` (one per representative shape: ordinary large LGD, LGD-with-rewrite bifurcation, district-fallback geometry, non-LGD `seat_id` join, elected UT on the ordinary path).
  - `FULL_CODES` = the existing 31.
  - `const STATE_CODES = process.env.AC_COVERAGE_FULL ? FULL_CODES : CANARY_CODES;`.
  - Update the file's docstring to explain the canary doctrine + how to run the full matrix.
- New workflow `.github/workflows/e2e-ac-full.yml`:
  - Triggers: `schedule` nightly, plus `pull_request` with `paths:` filter covering `frontend/src/lib/maplibre/sources.ts`, `datasets/boundaries/in/ac/**`, `datasets/taxonomy/entities.json`, `datasets/taxonomy/election_events.json`, `frontend/src/lib/boundaries.ts`, `frontend/src/contracts/state-ac-registry-coverage.test.ts`, `frontend/e2e/state-ac-coverage.spec.ts`.
  - Sets `AC_COVERAGE_FULL=1` and runs only the AC coverage spec.

**Acceptance gates**:
- All five DoD gates.
- Gate 5: confirm canary run locally; confirm `AC_COVERAGE_FULL=1 bun run test:e2e -- state-ac-coverage.spec.ts` still iterates 31.

**Subagent**: dispatch `Fowler (Engineering)` to review canary selection (which 5 cases preserve the unique-risk coverage of the 31). Apply verdict.

**Risk**: a future state ships a non-canary regression that the canary misses. Mitigation: path-filter triggers the full matrix on the exact files that would introduce such regressions.

### PR-3 Golden-path slim-down

**Files touched**: [frontend/e2e/golden-path.spec.ts](../frontend/e2e/golden-path.spec.ts) (shrink), possibly [frontend/e2e/extended-routes.spec.ts](../frontend/e2e/extended-routes.spec.ts) or [frontend/e2e/indicator-ranked-polish.spec.ts](../frontend/e2e/indicator-ranked-polish.spec.ts) (gain), possibly new vitest files under `frontend/src/lib/` for theme dropdown + temporal caption.

**Changes**:
- Keep in golden-path: mounts for home/state/AC/party; no `pageerror`; one `SourceList` assertion per data-bearing route.
- Move out: theme-dropdown humanised label assertions, temporal-caption vocabulary regex, anything that asserts content not on the citizen's first-visit critical path.
- Net target: <= 80 lines.

**Acceptance gates**:
- All five DoD.
- Gate 4 vitest: any moved assertion has a passing replacement in unit/contract or a sibling e2e.
- Gate 5: golden-path still green; the spec that gained the moved assertion still green.

**Subagent**: dispatch `Fowler (Engineering)` AND `Citizen User` (Citizen vetos any assertion removal that hides a real first-visit citizen experience).

**Risk**: removing an assertion that was secretly the only coverage of a real bug class. Mitigation: every removed assertion lands an equivalent in a cheaper tier in the SAME commit; PR body lists the move map.

### PR-4 Distill + archive

**Files touched**: [docs/architecture/testing.md](../docs/architecture/testing.md) (new section), this plan-doc moved to `docs/archive/plans/`.

**Changes**:
- Add `## e2e scope and canary subset` section to testing.md covering: cheap-tier-owns-exhaustive doctrine; canary selection criteria; `@bench` tag; `mobile-pixel-5` scoping rule; `AC_COVERAGE_FULL` env-gated full matrix.
- `git mv TODO/20260531-e2e-runtime-trim-plan.md docs/archive/plans/`.
- Stamp this plan-doc's status reckoner rows with PR numbers; append "Plan complete" block with per-row distillation map per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).
- Sweep `git grep` for backlinks to this plan-doc; update to archive path.

**Acceptance gates**: Gate 3 (svelte-check N/A docs-only), Gate 4 (vitest N/A docs-only) - mark explicit N/A in PR body; Gate 1 validate green (no datasets); Gate 2 pytest baseline.

**Subagent**: dispatch `Fowler (Engineering)` to red-team the new testing.md section.

## 5. Anti-patterns (do NOT)

- Bundle PRs 1-4 into one. Each is independently legible; bundling re-introduces the coupling the trim is trying to remove.
- Delete `boundary-benchmark.spec.ts`. It is useful; just stop running it on every PR.
- Delete `state-ac-coverage.spec.ts` outright. The canary subset has value as a citizen-pathway smoke for representative shapes.
- Skip the wall-time-delta number in PR-1 and PR-2 bodies. The whole justification is "stop wasting time"; the proof is the number.
- Add `mobile-pixel-5` coverage for any spec whose production code has no `lg:` / `md:` / mobile-specific branch. The default is desktop-only.
- Move golden-path assertions into a new e2e spec when a vitest unit/contract would prove the same thing cheaper.

## 6. Out of scope

- Any change to backend pytest tier policy.
- Any change to the contract-test (`*.test.ts` under `src/contracts/`) surface beyond adding new unit tests if PR-3 needs them.
- Schema versioning, datasets migration, or pipeline work.
- Adding new e2e specs for features that don't exist yet.

## 7. See also

- [CLAUDE.md](../CLAUDE.md) sections 9, 14, 15.
- [docs/architecture/testing.md](../docs/architecture/testing.md) - destination for PR-4 distillation.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) - PR-4 procedure.
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - 5-gate DoD + post-merge cleanup applied to every PR in this plan.
