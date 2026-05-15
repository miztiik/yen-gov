---
name: bootstrap
description: Load yen-gov project context before answering. Reads CLAUDE.md, guardrails, the relevant subsystem and concept docs, and the umbrella plan. Every persona (Citizen, Hans, Max, Gregor, Fowler, Jony) and every default-agent task crossing a subsystem boundary runs this first. Skip only for Level-0 / Level-1 single-file changes.
---

# bootstrap

This skill is a thin wrapper. The canonical procedure lives in [`docs/agents/bootstrap.md`](../../../docs/agents/bootstrap.md). Read that file in full and follow the eight-step ritual it specifies before producing any answer.

The wrapper exists so the `.claude/` harness can invoke the same loading behaviour that `.github/agents/*.agent.md` invokes via a one-line pointer. There is one source of truth — the doc — not two copies.

## What you must do

1. Open [`docs/agents/bootstrap.md`](../../../docs/agents/bootstrap.md).
2. Execute the eight-step ritual it specifies, in order.
3. In your first paragraph back to the user, name the Holy Laws and docs that are load-bearing for the answer (step 8 of the ritual).

## See also

- [`docs/agents/guardrails.md`](../../../docs/agents/guardrails.md) — the rules every persona must honour, loaded as part of bootstrap.
- [`docs/concepts/citizen-first.md`](../../../docs/concepts/citizen-first.md) — load this for any citizen-facing work.
- [`CLAUDE.md`](../../../CLAUDE.md) — the engineering contract.
