# Phase 2 completion handover — operational prompt for the next agent

**Last Updated**: 2026-05-25
**Doc class**: plan-doc per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md). This is the operational runbook the next coding agent reads at session-start to continue the canonical long-format pivot autonomously.
**Anchors to**: [`TODO/20260517-canonical-long-format-pivot.md`](20260517-canonical-long-format-pivot.md) (the umbrella plan; this handover advances its §0e.8a pending tracker).
**Authority**: User mandate 2026-05-25 ("park livestock NDLM as last in Phase 2; focus on the other items; work autonomously; invoke custom agents on doubt; structural fixes only").

---

## 1. What this handover is for

The canonical long-format pivot has been stuck in Phase 2 (per-family ingestion) for weeks. P.1 Energy is partly done; ~10 other families queued; Phases 3-5 are sketches. The user wants the next agent to drive the §0e.8a pending list to zero so Phase 2 can close. This document is the entry-point.

**Your scope**: drive every row in the umbrella plan's §0e.8a pending tracker to ✅ DONE, **except** the two livestock-NDLM rows — park those as the **LAST** Phase 2 deliverables. A parallel agent is already on livestock-NDLM (PRs #276 / #278 / #281 shipped); your work must not collide with theirs.

**Your operating mode**: autonomous PRs against `origin/main` from worker worktrees. When you ship a PR, **update the umbrella plan §0e.8a in the same PR** to flip the row's status from ◻ READY / ◻ NEXT to ✅ DONE (with PR # + commit SHA). If a row turns out to be already done, flip it with a verification citation (`git log` / `gh pr view`).

---

## 2. Rules of engagement (non-negotiable)

These are CLAUDE.md restatements specialised to the Phase-2 closing context. **Treat as binding.**

1. **Multi-agent isolation.** Never commit on the master worktree. Spawn a worker worktree per PR (`git worktree add ..\yen-gov-<slice-id> -b <branch> origin/main`). Other worktrees (`yen-gov-7c-residue-a` / `yen-gov-slice-e-docs` / `yen-gov-yenask-brand` / `yen-gov-yenask-device` / `yen-gov-yenask-ortrun`, plus whatever exists when you start) are parallel-agent territory — read-only to you.

2. **Park livestock-NDLM.** Two rows in §0e.8a relate to livestock-NDLM (the family slice + the `agriculture` topic rollout). Do those LAST in Phase 2, after all other §0e.8a rows close. The parallel livestock agent is currently shipping PRs against `feat/livestock-state-rollup-b01`; verify their state via `gh pr list --state open --search livestock` before scoping any livestock work.

3. **Structural fixes only.** No band-aids, no temporary hacks, no `# TODO: revisit` markers (CLAUDE.md §1 Holy Law #5). If a fix expands scope (e.g. closing a 7c-N residue shard reveals a missing canonical reader), expand the PR scope to fix the root cause; do not ship a half-fix that defers the structural correction.

4. **Subagents on doubt.** Custom agents are the authority router (CLAUDE.md §0a). On any decision that crosses a subsystem boundary or chooses between competing approaches, invoke the appropriate agent via `runSubagent`:
   - Data shape / column types / period axis / source vetting / indicator framing → **Hans + Max**
   - Contract / schema versioning / write seam / layer boundary → **Gregor**
   - Engineering craft / refactor safety / test tier / module structure → **Fowler**
   - URL grammar / visual bounds / citizen-readable copy → **Jony + Citizen**
   - LLM / model selection / prompt / RAG / agent topology → **Andre**
   - Read-only codebase exploration (large surface, multi-file) → **Explore**

   When subagents converge, their consensus is the spec. When they disagree, surface the disagreement to the user — do not pick autonomously on Level-5 decisions (CLAUDE.md §6).

5. **Documentation discipline.** Every decision worth more than 5 lines of prose lives in `docs/` (subsystem doc / concept doc / ADR per ADR-0034 doc-class routing), NOT in this handover and NOT in the umbrella plan. The plan stays lean — what's NEXT, not what's DONE. When you ship a PR, the prose homes for its rationale are:
   - **Cross-cutting decision with rejected alternatives** → new ADR under `docs/architecture/decisions/`
   - **Subsystem how-it-works** → `docs/architecture/<area>/` or `docs/concepts/<name>.md`
   - **Operator recipe** → `docs/how-to/<name>.md`
   - **What was DONE narrative** → append to `docs/archive/canonical-pivot-plan-20260522-snapshot.md`

6. **5-gate Definition of Done.** Every PR ships green:
   - Gate 1 `python -m yen_gov validate --root .` → OK (0 issues)
   - Gate 2 backend `pytest -q` → 0 failed (some skipped acceptable; verify against current baseline)
   - Gate 3 frontend `bun run check` (svelte-check) → 0 errors (warnings carry over)
   - Gate 4 frontend `bun run test` (vitest) -> 0 NEW failures vs baseline. Boundary gzip budgets are no longer frontend-vitest ratchets; when a PR changes boundary geometry or simplification policy, also run `python tools/boundaries/simplify.py --dry-run --skip-parquet` and fix oversized shards at the tooling seam.
   - Gate 5 §13 browser smoke on at least one citizen-facing route the change touches

7. **No `Start-Sleep`.** Use `get_terminal_output` polling for async PowerShell processes. Use `bun run test` (NOT `bun test` — bun's native runner barfs on Playwright specs).

8. **ASCII-only.** No curly quotes, em-dashes, or non-ASCII in commits, docs, code comments, or log strings (CLAUDE.md §5). Use `-`, `->`, `>=`.

---

## 3. Plan anchor — where we are right now

**Umbrella plan**: [`TODO/20260517-canonical-long-format-pivot.md`](20260517-canonical-long-format-pivot.md).

**5-phase totals** (per the umbrella):

| Phase | Status | Estimate |
|---|---|---|
| Phase 1 — Elections deletion sweep + T.x infrastructure (T.1 / T.2 / T.3 / T.0d / T.0e / G.1 / S.1) | ✅ DONE | — |
| **Phase 2 — Per-family ingestion** (~11 families) | ⏳ ACTIVE — your scope | 1 of ~11 families partly done (P.1 Energy); P.2 Livestock parallel-agent territory |
| Phase 3 — Demography / Fiscal / Education / Health backfill | Sketch only | Opens when Phase 2 closes |
| Phase 4 — SLM dispatcher | Sketch only | Opens when Phase 3 closes |
| Phase 5 — Admin rewrite | Sketch only | Opens when Phase 4 stabilises |

**Plan-doc's own rough completion estimate**: ~18-22% of the full canonical pivot.

**Origin/main tip at handover time**: `febda30e` (PR #283 PR-H caveats merge, 2026-05-25).

---

## 4. Your queue (§0e.8a pending tracker, ordered by recommended priority)

Each row below corresponds to one PR. Priority reflects (a) blast-radius, (b) blocker-unblocking value, (c) parallel-agent safety, (d) user instruction to park livestock last. Re-order only if a subagent (Gregor for contract risk, Fowler for engineering cost) flags a sequencing concern.

### 4.1 PR 1 — P.1 Energy: 7c-N residue triage (10 shards)

**Plan row**: §0e.8a "P.1 Energy - 7c-N residue triage". **Status**: ◻ NEXT.

**Actual disk state at handover** (verified `git ls-tree origin/main -- "datasets/indicators/in/energy/"`):

```
datasets/indicators/in/energy/india_thermal_capacity_retired_mw.json
datasets/indicators/in/energy/installed_capacity_thermal_mw.json
datasets/indicators/in/energy/installed_capacity_total_mw.json
datasets/indicators/in/energy/national_final_energy_consumption_by_sector_mtoe.json
datasets/indicators/in/energy/national_primary_energy_supply_mtoe.json
datasets/indicators/in/energy/state_coal_consumption_mt.json
datasets/indicators/in/energy/state_oil_product_consumption_kt.json
datasets/indicators/in/energy/state_plant_load_factor_pct.json
datasets/indicators/in/energy/state_power_purchase_share_pct.json
datasets/indicators/in/energy/state_rooftop_solar_capacity_mw.json
```

**10 shards, not 13** as the plan-doc says (plan is stale; correct it as part of this PR). Per [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md), each shard must classify into one of three buckets:

| Bucket | Action | Likely candidates |
|---|---|---|
| (a) **composer / compute-on-read** (D33.8) | `git rm`; renderer derives from canonical Parquet at read-time | `installed_capacity_thermal_mw.json` + `installed_capacity_total_mw.json` (fuel-roll-up parents) |
| (b) **future canonical input — P.1.C scope** | `git mv` to `datasets/energy/_meadow/<source>/<vintage>/<file>.json` per ADR-0041; defer adapter wiring to P.1.C | 7 P.1.C indicators (oil / primary energy / final energy / coal / plant-load-factor / power-purchase / rooftop solar) + `india_thermal_capacity_retired_mw` |
| (c) **dead — no consumer** | `git rm`; no canonical successor needed | TBD per audit |

**Mandatory audit step** (per the user's prior lesson on Phase D blast-radius traps): for each shard, run

```powershell
grep_search -query 'load_(shard|meadow)\([^)]*"<basename>' -isRegexp true -includePattern "backend/**/*.py"
```

If ANY hit is in a canonical-adapter lift block, the shard is bucket (b) and needs `git mv` not `git rm`. If hits are only in composer / test code, it may be bucket (a). Zero hits = bucket (c).

**Subagent invocation suggested**:
- **Gregor** — verify the classification of each bucket-(a) candidate against the §2b 5-fact-table lock + D33.8 compute-on-read rule. Risk of regressing canonical-input contracts.
- **Max** — verify each bucket-(b) candidate against the P.1.C indicator list (§2 of [`TODO/20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md)). Risk of orphaning data Max wants in P.1.C.

**Completion criterion** ([ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md)): `git ls-tree origin/main -- datasets/indicators/in/energy/` returns empty.

**Bundled in same PR**:
- Update `datasets/_ops/legacy-folded-indicator-shards.txt` to remove the 10 lines (or whatever count remains after classification).
- Update §0e.8a row in the umbrella plan to ✅ DONE with PR # + commit SHA.

### 4.2 PR 2 — P.1 Energy: Tier-B fence file rename + header rewrite

**Plan row**: §0e.8a "P.1 Energy - Tier-B fence file rename". **Status**: ◻ READY (was DEFERRED from 7c-4 per ADR-0041 §Doc-impact).

**Scope** (rename-in-place + header rewrite):
- `git mv datasets/_ops/legacy-folded-indicator-shards.txt datasets/_ops/meadow-shard-contract.txt`
- Rewrite the file header from "countdown to retirement" → "perimeter for canonical-input contract" (per ADR-0041 §0e.8b).
- Update `backend/yen_gov/validate.py` Tier-B symbol from `tier_b_no_indicator_in_energy_shards` (or whatever the current name is) to `tier_b_meadow_shard_contract`. Verify exact current symbol via `grep_search`.
- Scrub every doc reference to the old filename (paths in `docs/`, in CLAUDE.md, in other plan-docs). Use the "STALE vs HISTORICAL vs GENERATED" scrub-completeness pattern from the prior PR #182 OWASP-scrub lesson — historical references in ADRs and "moved from X to Y" comments PRESERVE; live doc descriptions EDIT.

**Subagent invocation suggested**: **Fowler** — the rename + Tier-B symbol-rename is two-hat (one structural commit for the file rename + Tier-B symbol rename; one behavioural-or-no-op commit for the doc scrub). Fowler can verify the Tidy-First commit grammar.

**Can be folded into PR 1** if the 7c-N residue closure also empties the file (which it should — once `datasets/indicators/in/energy/` is empty, the "fence" becomes the canonical-input contract). Decide at PR 1 scoping time.

### 4.3 PR 3 — sources.parquet vintage backfill + new Tier-B rule

**Plan row**: §0e.8a "P.1 Energy - sources.parquet vintage backfill + Tier-B vintage check". **Status**: ◻ READY.

**Scope** (ADR-0041 non-negotiable #4: meadow path `<vintage>` MUST match the citation row's `vintage` field):

1. Audit every row in `datasets/taxonomy/sources.parquet` against the meadow paths that reference it via `source_id` FK. Use `python -m yen_gov` ad-hoc DuckDB query or a new script under `backend/yen_gov/canonical/`.
2. For ICED + RBI 2024-25 rows that were FK-ed pre-7c with empty `vintage`, backfill the correct vintage (e.g. `"2024-25"`).
3. Add Tier-B rule `tier_b_meadow_vintage_matches_source_id` in `backend/yen_gov/validate.py` that walks `datasets/<family>/_meadow/*/<source>/<vintage>/`, derives `(source, vintage)` from the path, and asserts every observation row's `source_id` resolves to a `sources.parquet` row with `producer = <source>` AND `vintage = <vintage>`.
4. Add Tier-A or Tier-B test in `backend/tests/` that injects a vintage-mismatch case and asserts the rule rejects.

**Subagent invocation suggested**:
- **Hans + Max** — verify the vintage strings against [ADR-0042](../docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md) v3.0 "vintage as period anchor" semantics. Risk of conflating publisher edition with operator snapshot window.
- **Gregor** — Tier-B placement (which validator tier — A or B?) per [`docs/architecture/backend/validator.md`](../docs/architecture/backend/validator.md).

### 4.4 PR 4 — P.1 Energy: PR 7d IA editorial pass (Jony + Citizen)

**Plan row**: §0e.8a "P.1 Energy - PR 7d IA editorial pass". **Status**: ◻ READY.

**Scope** (citizen-facing editorial; the actual sub-bullets need Jony + Citizen scoping):
- Prune the 36-card wall on `/s/<state>/t/energy` per Jony's "removing what isn't essential" doctrine.
- Rewrite ACS-ARR copy per Citizen's "mid-tier Android, 4G, non-technical reader" voice.
- Scroll-narrative cascade — single-screen density (Loren Brichter influence) on the top half.

**Subagent invocation MANDATORY** (this is a UX decision, not a mechanical fix):
- **Jony** — IA decisions + visual prune order. Loop in **Citizen** for the copy pass on each surviving card.
- **Hans** — for any methodology-break visibility decisions that arise during the pruning (per §0e.8b Hans non-negotiable #7: "Methodology breaks render visibly on chart, not just in `methodology_breaks.parquet`").

**Likely cascade**: this PR may surface 2-3 follow-up PRs (FacetPicker polish, choropleth legend rework, etc.) — keep each separately mergeable per CLAUDE.md §8 small-reversible-commit discipline.

### 4.5 PR 5 — Caveat-authoring next batch (extend PR-H pattern)

**Plan row**: §0e.8a "Methodology-break visibility on chart" (Hans non-negotiable §0e.8b #7). **Status**: ⏳ partly done.

**Background**: PRs #279 (PR-E, RPO honesty caveats) + #283 (PR-H, 4 more indicators) shipped the first wave of citizen-facing caveat surfacing via the canonical-allowlist `caveats?: ReadonlyArray<string>` field + the legacy JSON `methodology.known_caveats[]` field, both rendered by `AboutThisData.svelte`. ~30 stub indicators still have `documentation_status: "stub"` or empty `known_caveats[]` and need Hans-curated bullets.

**Scope**:
1. Run `grep_search -query '"known_caveats":\s*\[\s*\]' -isRegexp true -includePattern "datasets/indicators/in/**/*.json"` + the canonical-allowlist equivalent to inventory the gap.
2. Group the gap by family (energy / fiscal / health / education / amenities / governance / schemes / work / judiciary / crime / technology / local_govt_finance).
3. Prioritise the families with the most citizen-visible indicators on `/s/<state>/t/<topic>` routes.
4. For each indicator, invoke **Hans** for the caveat wording. Hans's pattern from PR-H: 3 short citizen-readable bullets per indicator, citing publisher methodology breaks, scope limits, and comparability traps.

**Subagent invocation MANDATORY**: **Hans** is the author of every caveat bullet. Do not author caveats yourself; Hans's voice is non-negotiable.

**Scope-control**: this could be 1 PR for all ~30 indicators, or 1 PR per family. Recommend per-family bundling (5-7 PRs total) to keep each PR ≤ 5 files of JSON edits + smoke test.

### 4.6 PR 6+ — P.1.C remaining energy sub-pivot

**Plan row**: §0e.8a "P.1 Energy - P.1.C + P.1.D remaining energy sub-pivots". **Status**: ◻ QUEUED.

**Scope**: per §4 of [`TODO/20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md) — adds 9 indicators across `energy_fuel_consumption.parquet` + `energy_installed_capacity.parquet` extensions:

```
state_coal_consumption_mt              (re-anchor to Coal Controller)
state_oil_product_consumption_kt       (product-faceted, PPAC)
national_primary_energy_supply_mtoe    (source-faceted)
national_final_energy_consumption_mtoe (sector-faceted)
national_capacity_pipeline_gw
national_thermal_capacity_retired_mw
state_renewable_grid_capacity_mw       (source-faceted, includes rooftop)
state_plant_load_factor_pct            (fuel-faceted)
national_renewable_potential_vs_installed_mw
```

**This sequences AFTER PR 1** (7c-N residue triage) — the bucket-(b) shards from PR 1 become the meadow input for P.1.C.

**Subagent invocation MANDATORY**:
- **Max** — confirm the 9 P.1.C indicator IDs honour [indicator-naming.md](../docs/concepts/indicator-naming.md) + match the OWID precedent.
- **Hans** — confirm `confidence_tier` + `is_issuing_authority` assignments for PPAC / Coal Controller / IEA / MNRE (per §3 Q-d table in the P.1 plan).
- **Gregor** — paired-test discipline: schema bump + Pydantic + DDL + parquet emit + frontend reader switch + Tier-B allowlist removal, all atomic per CLAUDE.md §15.

**Likely sub-PR breakdown** (mirroring the P.1.B Phases B-D pattern): P.1.C.A SHIP-LIFT-ONLY; P.1.C.B frontend allowlist; P.1.C.C topics.json edits; P.1.C.D legacy-shard `git rm`. Could be 1-4 PRs depending on Gregor's atomicity verdict.

### 4.7 PR N — P.1.D Energy sweep + retire-list close-out

**Plan row**: §0e.8a "P.1 Energy - P.1.C + P.1.D remaining energy sub-pivots". **Status**: ◻ QUEUED.

**Scope**: per §4 of the P.1 plan — 3 acquires (`state_electricity_sales_mu` CEA, `state_power_purchase_mix_pct` PFC + FoR, `state_rpo_compliance_pct` if not closed in P.1.B Phase B–D follow-ups) + retirement audit + Tier-B allowlist scrub for the WHOLE family.

**Completion criterion**: P.1 row in the umbrella plan §1 Phase 2 table flips to ✅ DONE.

### 4.8 PR N+1 — Citizen-1 panel: <2s mobile first-paint vs DuckDB-WASM warm-up

**Plan row**: §0e.8a "Citizen-1 panel". **Status**: ◻ OPEN ARCHITECTURE (design question, not a PR yet).

**Scope**: this is a Hans + Gregor §10 carve-out that surfaced during P.1.A and was never resolved. The question is: how does yen-gov hit <2s first-paint on mid-tier Android over 4G when DuckDB-WASM initialisation + first-query takes longer than that?

**Subagent invocation MANDATORY**:
- **Gregor** — architectural verdict on the carve-out shape (precompute a static "first-paint payload" Parquet vs preview-via-CDN-JSON vs other).
- **Hans** — Citizen-facing semantics of the carve-out (what does the citizen see during the warm-up window?).
- **Citizen** — sanity check on whatever Hans + Gregor converge to.
- **Andre** — if any LLM / SLM interaction is in the proposal (yenask first-paint), Andre weighs in on the model-load-vs-canonical-store-load sequencing.

When subagents converge, mint an ADR (`docs/architecture/decisions/004x-citizen-1-panel-first-paint.md`) before shipping any code.

### 4.9 PR FINAL — P.2 Livestock NDLM (PARKED until everything above closes)

**Plan row**: §0e.8a "P.2 Livestock - NDLM ingest". **Status**: ◻ QUEUED. Parallel agent active on this.

**HARD CONSTRAINT**: do not start this until PRs 1-N+1 are all closed AND no parallel agent's livestock branch is open (`gh pr list --state open --search livestock` returns empty).

**Scope when picked up**: per [`TODO/20260525-livestock-ndlm-ingest-plan.md`](20260525-livestock-ndlm-ingest-plan.md). 16 indicators across 5 fact tables (Owner Reg / Pashu Aadhaar / NADCP / Breeding / NAIP IV). Phase 0 (taxonomy seed) → Phase 1 (meadow lifts × 5 endpoints) → Phase 2 (canonical writer + indicators.json) → Phase 3 (frontend allowlist).

**Subagent invocation MANDATORY**: per the livestock plan's `Personas:` block — Max for indicator scoping, Hans for Pashu Aadhaar honest-renderer call (the user verdict), Gregor for meadow-path + LGD resolver + CY/FY duality on PK, Fowler for adapter module split.

---

## 5. Working pattern (per-PR runbook)

This is the shape of every PR you ship. Specialise as needed.

### 5.1 Session start (every PR)

```powershell
# Sanity: where am I?
cd C:\Users\kumarsnaveen\Downloads\NawiN\personal\gitrepos\yen-gov
git fetch origin main --quiet
git log origin/main --oneline -3
git worktree list
git branch --show-current
git status --porcelain | Measure-Object -Line | ForEach-Object { "master-dirty-lines=$($_.Lines)" }
```

If `master-dirty-lines` is > 0, the dirty files are NOT yours (per multi-agent isolation rule). Leave them alone.

### 5.2 Create worker worktree

```powershell
git worktree add ..\yen-gov-<slice-id> -b <branch-name> origin/main
Push-Location ..\yen-gov-<slice-id>
$env:PYTHONPATH = (Resolve-Path backend).Path  # MANDATORY for Python commands
python -c "import yen_gov; print(yen_gov.__file__)"  # MUST point at worker, not master
Pop-Location
```

The `PYTHONPATH` pin is per the 2026-05-24 PR #194/#195 lesson — without it, Python may import the master's editable-installed `yen_gov` package and contaminate the worker.

### 5.3 Do the work + run gates

Edit files on the worker. Then run 5 gates:

```powershell
Push-Location ..\yen-gov-<slice-id>
$env:PYTHONPATH = (Resolve-Path backend).Path

# Gate 1: validate
python -m yen_gov validate --root .

# Gate 2: backend pytest (use deselects for known-flaky tests if they're carry-over)
python -m pytest backend\tests -q

# Gate 3: svelte-check (use *> for log file to avoid pipe-buffering)
Push-Location frontend
bun run check *> ..\.tmp_check.log
Get-Content ..\.tmp_check.log -Tail 15

# Gate 4: vitest (NEVER `bun test` - use `bun run test`)
bun run test *> ..\.tmp_vitest.log
# Tail + verify failure count matches the 283-failure baseline
Get-Content ..\.tmp_vitest.log -Tail 8
Pop-Location

# Gate 5: §13 browser smoke
# Start frontend dev server in async mode, navigate to affected routes
# via open_browser_page + read_page + screenshot_page tools

Pop-Location
```

### 5.4 Commit + push + merge

Use BOM-free UTF-8 commit messages via `create_file` (verify first 3 bytes via `[System.IO.File]::ReadAllBytes($p)[0..2]` — must NOT be `239,187,191`). Then:

```powershell
Push-Location ..\yen-gov-<slice-id>
git status --porcelain  # verify split: MINE staged, parallel-agent files alone
git add <explicit-path-list>  # NEVER `git add .` or `git add -A`
git diff --cached --name-only  # confirm what's staged
git commit -F .tmp_commit_msg.txt
git push -u origin <branch-name>

# Open PR; merge via gh pr merge --squash --delete-branch
gh pr create --title "<title>" --body-file .tmp_pr_body.md
gh pr merge <N> --squash --delete-branch --auto

# Verify merge
gh pr view <N> --json state,mergedAt,mergeCommit

# Cleanup worker (manual remote-branch delete if cosmetic error fired)
Pop-Location
git worktree remove --force ..\yen-gov-<slice-id>
git fetch origin main --quiet
git log origin/main --oneline -1
```

The `gh pr merge` from worker behaviour: if master is on `main` you get a cosmetic local-cleanup error but the merge succeeds server-side. If master is on a feature branch, clean exit. Always verify with `gh pr view`.

### 5.5 Update the umbrella plan in the same PR

In your edits, flip the relevant §0e.8a row from ◻ NEXT / ◻ READY to ✅ DONE with PR # + commit SHA. If the row was stale (e.g. an item was already done by an earlier sprint that didn't update the plan), flip it with a verification citation.

This is the **same-PR update rule** — the plan-doc and the work are two halves of one atomic landing. Per CLAUDE.md §9 DoD "Canonical docs updated in `docs/` (right tier)".

---

## 6. When to escalate

Stop work and request user input when:

1. Two subagent verdicts diverge AND neither has clear authority per CLAUDE.md §0a. Surface both verdicts + ask the user to break the tie.
2. A PR's scope expands past Level 4 (4+ files, structural; per CLAUDE.md §6). Propose breakdown first; do not ship a Level-5 PR autonomously.
3. The §0e.8a queue itself needs re-ordering (e.g. you discover PR 4 must precede PR 1 because of a coupling). Document the discovery + re-order proposal; ask the user to ratify.
4. A row in the queue turns out to be impossible to complete as scoped (e.g. PR 3 vintage backfill finds the underlying sources.parquet schema is wrong). Surface the structural defect; propose the fix scope; ask the user to ratify the expanded scope per CLAUDE.md §6 ("If the scope is expanding because of a fix or unknown issue that we didn't plan during the scope, then expand the scope and fix it").

---

## 7. Stop conditions

Stop and hand back to the user when ANY of:

- All §0e.8a non-livestock rows are ✅ DONE; livestock-NDLM is the only remaining work.
- A Level-5 design decision surfaces (per CLAUDE.md §6; pause + design consultation).
- The user asks you to stop.

When the last non-livestock §0e.8a row closes, write a 1-paragraph summary of what shipped + ask the user whether to proceed to livestock-NDLM OR defer Phase 2 closure for another reason.

---

## 8. References

- **Umbrella plan**: [`TODO/20260517-canonical-long-format-pivot.md`](20260517-canonical-long-format-pivot.md) — your §0e.8a queue
- **P.1 Energy sub-plan**: [`TODO/20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md) — PR-level scope for PRs 6 + 7 above
- **Livestock NDLM sub-plan** (PARKED for last): [`TODO/20260525-livestock-ndlm-ingest-plan.md`](20260525-livestock-ndlm-ingest-plan.md)
- **Meadow tier concept** ([ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md) precedent): [`docs/concepts/meadow-tier.md`](../docs/concepts/meadow-tier.md) — your bucket-(a)/(b)/(c) decision frame
- **Canonical store spec**: [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md)
- **Doc-class routing**: [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md) — where each kind of doc lives
- **Validator tiers**: [`docs/architecture/backend/validator.md`](../docs/architecture/backend/validator.md)
- **Browser smoke discipline**: [CLAUDE.md §13](../CLAUDE.md)
- **Doc archive** (where to lift DONE prose): [`docs/archive/canonical-pivot-plan-20260522-snapshot.md`](../docs/archive/canonical-pivot-plan-20260522-snapshot.md)

---

## 9. Final reminder

You are the agent who closes Phase 2. The user is tired of Phase 2 hanging. Ship small reversible PRs, update the plan in the same PR, lift DONE narrative to `docs/`, invoke subagents on doubt, do not band-aid, do not collide with parallel agents, park livestock for last. When the §0e.8a queue is empty (except livestock), Phase 2 closes and the next agent inherits Phase 3.
