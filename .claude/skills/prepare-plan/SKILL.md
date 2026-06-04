---
name: prepare-plan
description: Turn a rough idea or draft into an execution-ready plan-doc under TODO/ that an autonomous agent can run end-to-end with no further instruction. Use when the user says "make a plan", "prepare a plan", "plan this", or "write an execution-ready plan". The output plan-doc carries its own embedded EXECUTION BLOCK (orchestrator + subagent-PR topology, worktree hygiene, ship loop, persona debate, context-offload, stop-on-ambiguity) so that at run time the user only adds the plan to context and says "implement it" - no metadata is re-dictated. This skill AUTHORS the plan; it does NOT execute it.
---

# prepare-plan

Author a plan-doc that is execution-ready: every "how to work" rule the user would otherwise repeat is baked into the plan itself, so execution is blind rule-following with no further dictation.

Run [`bootstrap`](../bootstrap/SKILL.md) first (skip only for Level-0/1). The plan-doc is a living doc on `main`, never a frozen artifact.

## When this fires

User says: "make a plan", "prepare a plan", "plan this out", "write an execution-ready plan for X". You produce ONE file: `TODO/<YYYYMMDD>-<slug>-plan.md`. You do NOT start coding the work.

## Procedure

1. **Investigate against the code, not the draft.** Read the actual files the work touches. Verify every load-bearing claim directly (read the enforcement predicate / the consumer call site / the row-count), never via a subagent summary alone. If a draft says "X violates Y", open Y and confirm. Dispatch `Explore` subagents for breadth so the main context does not overflow. Spot-check any FK/id-overlap claim with a real `set(a) & set(b)` sample before trusting it.
2. **Size and split into PR-rows.** One row = one PR = one branch = one reviewable unit. Phase the rows with hard dependency lines (A -> B -> ... ), reader-before-writer for any schema/contract change. Bundle only where the work itself is one atomic surface; never bundle mixed risk profiles.
3. **Resolve ambiguity by naming the deciding authority inline.** Use the CLAUDE.md section 0a authority table. Where a decision is contested, run the relevant personas (`gregor-hohpe`, `fowler`, `hans`, `max`, `jony`, `citizen-user`, `andre`) in DEBATE - they converge to ONE written ruling baked into the row, not independent parallel reviews. Red-team passes are research-only and return exact old -> new text.
4. **Set the Level + ESCALATE triggers.** Per CLAUDE.md section 6. Anything Level-5 (core design / data model / runtime) PAUSES for user sign-off; write the trigger explicitly so the executing agent stops there and nowhere else.
5. **Write the plan-doc** using the structure below. Stamp the EXECUTION BLOCK verbatim near the top. STOP after writing. Do not implement.

## Plan-doc structure (what you emit)

- **H1 title + `Last Updated` + Level.**
- **Section 0 - Operating contract:** why the plan exists; hard-coded scope; ESCALATE triggers; chosen strategy with the persona ruling that set it.
- **Section 1 - Status Reckoner:** table `| Row | Title | Status | PR | Effort |`. Rows are PRs. Status starts `[ ] PENDING`, flips to `[x] DONE` with the merged PR number.
- **Section 2+ - Per-row spec:** for each row: scope, files touched, acceptance gates, and ONE load-bearing oracle (the single check that proves the row is correct - a bijection/coverage test, a contract test, a parity assertion).
- **The EXECUTION BLOCK** (below), pasted verbatim. This is the part that makes "implement it" sufficient.

## EXECUTION BLOCK (paste verbatim into every plan-doc)

```markdown
## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on.
2. **One row = one PR = one branch.** Park master on a `scratch-master-parking` branch so no worktree owns `main` (clean gh-merge). Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change.
3. **Ship loop, non-stop.** Keep PRs in flight; never idle. As soon as one row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next row. Pre-existing unrelated test failures are not gating - document the baseline, do not block.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked.
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (CLAUDE.md section 0a) in debate, not parallel review; bake the single written verdict into the row and proceed.
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into subagents so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (Level-5), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3 (the loop is lossy - escalate with Path A/B/C options, do not ship a 4th audit). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt (the command + its zero result). Archive the plan-doc with a per-row distillation map per `docs/how-to/distill-a-plan.md`.
```

## See also

- [`docs/how-to/ship-a-pr.md`](../../../docs/how-to/ship-a-pr.md) - the PR lifecycle the EXECUTION BLOCK references.
- [`docs/how-to/distill-a-plan.md`](../../../docs/how-to/distill-a-plan.md) - closure + archive ritual.
- [`docs/how-to/handle-scope-change.md`](../../../docs/how-to/handle-scope-change.md) - STOP-AND-SURFACE.
- [`CLAUDE.md`](../../../CLAUDE.md) - authority table (section 0a), correction levels (section 6), anti-patterns (section 10).
- [`bootstrap`](../bootstrap/SKILL.md) - run before authoring.
