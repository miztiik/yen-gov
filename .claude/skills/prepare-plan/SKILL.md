---
name: prepare-plan
description: Turn a rough idea or draft into an execution-ready plan-doc under TODO/ that an autonomous agent can run end-to-end with no further instruction. Use when the user says "make a plan", "prepare a plan", "plan this", or "write an execution-ready plan". The output plan-doc carries its own embedded EXECUTION BLOCK (orchestrator + subagent-PR topology, worktree-per-subagent, parallel fan-out, delegated git ops, no-idle-on-CI, persona debate, subagent brief budget, stop-on-ambiguity) so that at run time the user only adds the plan to context and says "implement it" - no metadata is re-dictated. This skill AUTHORS the plan; it does NOT execute it.
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

The plan is a tabular instrument for parallel dispatch, not a narrative. It contains only what ships, what was decided, and what was evaluated-and-rejected. No fluff, no chatter, no verbatim user quotes (CLAUDE.md section 10 anti-pattern).

- **H1 title + `Last Updated` + Level.** Nothing else above section 0.
- **Section 0 - Operating contract** (table, not prose):

  | Field | Value |
  | --- | --- |
  | Why this plan exists | one sentence |
  | Hard scope - in | bullets, no narrative |
  | Hard scope - out | bullets |
  | ESCALATE triggers | enumerated |
  | Chosen strategy | one line + the persona that ruled it |

- **Section 1 - Status Reckoner** (the authoritative parallelization + agent-tracking table):

  | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |

  - `#` integer ordinal.
  - `Depends-on` lists `#` values that must be DONE before this row can start; `-` means no predecessor.
  - `Parallel-group` is a letter; rows sharing a letter are mutually independent and dispatched together.
  - `Status` starts `PENDING`, flips through `IN-FLIGHT` to `DONE #<pr>` or `COLLAPSED` (with cited rationale).
  - `Worktree` is the isolated absolute path the orchestrator created for the row (or `-` until dispatched).
  - `Subagent` names the dispatched agent (or `-` until dispatched).

- **Section 2+ - one section per row, fixed shape, no prose padding:**

  ### Row #N - <title>
  - **Scope:** one sentence, what ships.
  - **Files touched:** bullet list of exact paths.
  - **Acceptance gates:** bullet list (tests, lint, type-check, browser-verify ...).
  - **Oracle:** ONE load-bearing check (bijection / coverage / contract / parity) that proves correctness.
  - **Decisions** (enumerated table):

    | # | Decision | Authority |

  - **Rejected alternatives** (enumerated table):

    | # | Option | Why rejected | Authority |

- **The EXECUTION BLOCK** (below), pasted verbatim. This is the part that makes "implement it" sufficient.

### Plan-doc style rules (enforced; reviewers reject violations)

- No narrative paragraphs outside section 0 and the per-row Scope sentence.
- No agent chatter (no "I will ...", "let me ...", "we should ...").
- No verbatim user quotes from chat. Capture intent in neutral agent prose; cite who decided and when.
- No "future work" / "nice to have" / "if time permits" sections. If it is not a row, it is not in the plan.
- No restatement of CLAUDE.md or skill rules. Link, do not copy.
- Every claim that drove a decision lives in a Decisions row or a Rejected alternatives row - nowhere else.

## EXECUTION BLOCK (paste verbatim into every plan-doc)

```markdown
## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology - subagent owns the full row lifecycle.** Main agent owns the Status Reckoner and the row-dependency graph; never lets its own context overflow; does NOT do git ops. Each ready PR-row is dispatched to a stateless `runSubagent` that owns the row end-to-end: branch, edit, commit, push, open PR, watch CI, fix-loop on its own PR, merge with `gh pr merge --squash --delete-branch`, post-merge hygiene (delete remote branch, prune `: gone` locals, remove `.tmp_*`), and the per-row distillation map per `docs/how-to/distill-a-plan.md`. The orchestrator only reads back the merged PR number and ticks the Reckoner.

2. **Worktree-per-subagent (mandatory isolation).** Before dispatch the orchestrator creates an isolated worktree: `git worktree add <ABS_PATH> -b <row-branch> origin/main` and passes that absolute path to the subagent. The subagent works ONLY inside that path. NEVER share a worktree across subagents - cross-agent contamination of the shared working tree is the #1 ship-time bug. Park master on `scratch-master-parking` so no worktree owns `main` (clean `gh pr merge`).

3. **Parallel fan-out, never idle on CI.** From the section-1 dependency graph the orchestrator dispatches all rows whose predecessors are DONE, concurrently, up to N (default N = 3; overridable per plan in section 0). The orchestrator MUST NOT wait for one row's CI to go green before dispatching the next non-blocked row - CI-watch and fix-loop are the subagent's job. As soon as a merge lands, the orchestrator recomputes the ready-set and re-saturates the fan-out.

4. **Subagent brief budget.** A brief is: (a) the row's section verbatim, (b) this EXECUTION BLOCK verbatim, (c) the absolute worktree path, (d) a pointer to the `bootstrap` skill. NOT the whole plan-doc. Target <= 200 lines of input context. The subagent reads more from disk on demand; the orchestrator does not push it.

5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (`gregor-hohpe`, `fowler`, `hans`, `max`, `jony`, `citizen-user`, `andre`) per CLAUDE.md section 0a in DEBATE - not parallel review. Bake the single written verdict into the row's Decisions table and proceed.

6. **PR lifecycle.** Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify any frontend/admin runtime change. Tests ship with the row. Full suite green at merge. No new mocks unless asked. Pre-existing unrelated failures are not gating - document the baseline, do not block.

7. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (Level-5), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3 (the loop is lossy - escalate with Path A/B/C options, do not ship a 4th audit). Otherwise do not pause; the user is not watching.

8. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt (the command + its zero result). Archive the plan-doc with a per-row distillation map per `docs/how-to/distill-a-plan.md`.
```

## See also

- [`docs/how-to/ship-a-pr.md`](../../../docs/how-to/ship-a-pr.md) - the PR lifecycle the EXECUTION BLOCK references.
- [`docs/how-to/distill-a-plan.md`](../../../docs/how-to/distill-a-plan.md) - closure + archive ritual.
- [`docs/how-to/handle-scope-change.md`](../../../docs/how-to/handle-scope-change.md) - STOP-AND-SURFACE.
- [`CLAUDE.md`](../../../CLAUDE.md) - authority table (section 0a), correction levels (section 6), anti-patterns (section 10).
- [`bootstrap`](../bootstrap/SKILL.md) - run before authoring.
