# Agent Bootstrap

**Last Updated**: 2026-05-15

Every persona — whether invoked through Claude Code (`.claude/skills/bootstrap`) or through VS Code Copilot Chat (`.github/agents/*.agent.md`) — runs this loading ritual before answering. The duplicated "read CLAUDE.md, read docs/architecture, read the umbrella plan…" preamble that used to live in every agent file has moved here so there is one place to update it.

This is the *what to load*. The companion doc [`guardrails.md`](guardrails.md) is the *what not to do*. Bootstrap loads guardrails as one of its steps.

## The ritual (in order)

1. **Read [`CLAUDE.md`](../../CLAUDE.md) end-to-end.** It is the engineering contract. Identify which Holy Laws (#1–#10) are load-bearing for the current task and be ready to cite them by number.
2. **Read [`guardrails.md`](guardrails.md).** Holy Laws restated, project-level non-goals, forbidden git operations, escalation rules. These constrain every recommendation you make.
3. **Read the relevant subsystem doc(s) under `docs/architecture/<area>/`.** Pick the area that matches the task surface — e.g. `docs/architecture/ingest/` for a new source adapter, `docs/architecture/schemas/` for a contract change, `docs/architecture/frontend/` for a UI change. Don't critique what you haven't read.
4. **Read the relevant ADR(s) under `docs/architecture/decisions/`** if one is cited from the subsystem doc or referenced in the task.
5. **Read the relevant concept doc(s) under `docs/concepts/`.** Especially [`citizen-first.md`](../concepts/citizen-first.md) for any citizen-facing work, and the pillar / domain concept doc that matches.
6. **Read the umbrella plan [`TODO/SOCIO-ECONOMIC-EXPANSION.md`](../../TODO/SOCIO-ECONOMIC-EXPANSION.md)** if the task touches socio-economic indicators.
7. **Skim recent git history** (`git log --oneline -20`) for in-flight work that overlaps the task.
8. **State, in your first paragraph back to the user, which Holy Laws and which docs are load-bearing for this answer.** This makes the load explicit and easy to challenge.

## When bootstrap is mandatory

- Any persona invocation (Citizen, Hans, Max, Gregor, Fowler, Jony) — they all start here.
- Any default-agent task that crosses a subsystem boundary (touches ≥ 2 of: `backend/`, `frontend/`, `datasets/`, `admin/`, `tools/`, schemas).
- Any task escalated to Correction Level 2 or higher (`CLAUDE.md §6`).

## When bootstrap is optional

- Level-0 / Level-1 changes inside a single file (typo, comment, log string, isolated bug fix).
- Pure read questions ("where is X defined?") that don't propose any change.

## Why this exists as a doc, not duplicated in every agent file

`CLAUDE.md` Holy Law #4 says docs are agent memory and duplication is forbidden. Each `.github/agents/*.agent.md` file used to repeat the same six bullets ("Read CLAUDE.md… read docs/architecture… read TODO/SOCIO…"). Six files × six bullets = 36 lines of guaranteed-to-drift boilerplate. Lifting it into one canonical doc with thin wrappers (`.claude/skills/bootstrap/SKILL.md` for Claude, one-line pointer in each `.agent.md` for Copilot) gives both harnesses the same loading behaviour from a single source.

## See also

- [`guardrails.md`](guardrails.md) — the rules every persona must honour.
- [`../concepts/citizen-first.md`](../concepts/citizen-first.md) — the doctrine behind the `distill` pipeline.
- [`../how-to/distill.md`](../how-to/distill.md) — the seven-step citizen-question pipeline.
- [`../../CLAUDE.md`](../../CLAUDE.md) — the engineering contract.
