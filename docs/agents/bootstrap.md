# Agent Bootstrap

**Last Updated**: 2026-05-30

Every persona - whether invoked through Claude Code (`.claude/skills/bootstrap`) or through VS Code Copilot Chat (`.github/agents/*.agent.md`) - runs this loading ritual before answering. The duplicated "read CLAUDE.md, read docs/architecture, read the umbrella plan..." preamble that used to live in every agent file has moved here so there is one place to update it.

This is the *what to load*. The companion doc [`guardrails.md`](guardrails.md) is the *what not to do*. Bootstrap loads guardrails as one of its steps.

When editing agent/customization Markdown, use ASCII only: "-", "->", ">=", "section", "INR".

## The ritual (in order)

1. **Read [`CLAUDE.md`](../../CLAUDE.md) end-to-end.** It is the engineering contract. Identify which Holy Laws (#1-#10) are load-bearing for the current task and be ready to cite them by number.
2. **Read [`guardrails.md`](guardrails.md).** Holy Laws restated, project-level non-goals, git hygiene and stop conditions, escalation rules. These constrain every recommendation you make.
3. **Read the relevant subsystem doc(s) under `docs/architecture/<area>/`.** Pick the area that matches the task surface - e.g. `docs/architecture/ingest/` for a new source adapter, `docs/architecture/schemas/` for a contract change, `docs/architecture/frontend/` for a UI change. Don't critique what you haven't read.
4. **Read the relevant ADR(s) under `docs/architecture/decisions/`** if one is cited from the subsystem doc or referenced in the task.
5. **Read the relevant concept doc(s) under `docs/concepts/`.** Especially [`citizen-first.md`](../concepts/citizen-first.md) for any citizen-facing work, and the pillar / domain concept doc that matches.
6. **Read the umbrella plan [`TODO/SOCIO-ECONOMIC-EXPANSION.md`](../../TODO/SOCIO-ECONOMIC-EXPANSION.md)** if the task touches socio-economic indicators.
7. **Skim recent git history** (`git log --oneline -20`) for in-flight work that overlaps the task.
8. **State, in your first paragraph back to the user, which Holy Laws and which docs are load-bearing for this answer.** This makes the load explicit and easy to challenge.

## When bootstrap is mandatory

- Any persona invocation (Citizen, Hans, Max, Gregor, Fowler, Jony, Andre) - they all start here, with one carve-out: Andre may skip the ritual for generic LLM-app design questions that do not touch yen-gov code. The moment Andre is asked about YENASK, an in-bundle SLM, or any other yen-gov surface, the ritual is mandatory.
- Any default-agent task that crosses a subsystem boundary (touches >= 2 of: `backend/`, `frontend/`, `datasets/`, `admin/`, `tools/`, schemas).
- Any task escalated to Correction Level 2 or higher (`CLAUDE.md section 6`).

## When bootstrap is optional

- Level-0 / Level-1 changes inside a single file (typo, comment, log string, isolated bug fix).
- Pure read questions ("where is X defined?") that don't propose any change.

## Why this exists as a doc, not duplicated in every agent file

`CLAUDE.md` Holy Law #4 says docs are agent memory and duplication is forbidden. Each `.github/agents/*.agent.md` file used to repeat the same six bullets ("Read CLAUDE.md... read docs/architecture... read TODO/SOCIO..."). Six files x six bullets = 36 lines of guaranteed-to-drift boilerplate. Lifting it into one canonical doc with thin wrappers (`.claude/skills/bootstrap/SKILL.md` for Claude, one-line pointer in each `.agent.md` for Copilot) gives both harnesses the same loading behaviour from a single source.

## Autonomous plan execution  -  AUTO is the default

When a user authorises an agent to execute a plan-doc autonomously (verbatim mandates like "run autonomous", "merge the PRs to main and move onto next step until end of plan"), the default stance is:

- **AUTO** every row: execute the work, run the 5-gate DoD, `gh pr merge --squash --delete-branch`, advance to the next row. No DRAFT-PR-and-wait state. No mid-row CONSULT-USER pause.
- **Personas** (Citizen, Hans, Max, Gregor, Fowler, Jony, Andre) MAY be dispatched as Explore subagents to gather facts; their verdicts inform the agent's action  -  they are not a request-for-approval surface.
- **ESCALATE only** for genuine triggers: schema major bump (1.x -> 2.x), new ADR proposal, election-results data deletion, persona-conflict-unresolved, or 3x cost overrun. Otherwise AUTO.
- **Pre-resolve ambiguities at planning time**, not at execution time. Bake state codes, feature counts, source-suitability verdicts into the plan-doc as facts (e.g. section 0.2 of [TODO/20260530-boundary-followups-execution-plan.md](../../TODO/20260530-boundary-followups-execution-plan.md)) so the executing agent faces zero decision points within user-mandated scope.
- **When user is unavailable mid-execution**, stay in scope, progress the in-flight mandate, do not invent new scope or contract existing scope.

This stanza is the canonical reference for "what autonomy means in yen-gov plan execution". Plan-docs that need the long-form version cite this doc rather than re-explaining.

## See also

- [`guardrails.md`](guardrails.md) - the rules every persona must honour.
- [`../concepts/citizen-first.md`](../concepts/citizen-first.md) - the doctrine behind the `distill` pipeline.
- [`../how-to/distill.md`](../how-to/distill.md) - the seven-step citizen-question pipeline.
- [`../../CLAUDE.md`](../../CLAUDE.md) - the engineering contract.
