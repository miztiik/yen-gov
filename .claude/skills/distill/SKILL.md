---
name: distill
description: Drive a citizen question through the seven-step yen-gov pipeline (Citizen → Hans → Max → Gregor → Fowler → Jony → Citizen). Citizen bookends the loop — opens with the question, closes with the comprehension audit. Use for any new citizen-facing feature, indicator, or page that begins with a citizen question. Do NOT use for internal pipeline / schema-only / tooling changes.
---

# distill

This skill is a thin wrapper. The canonical procedure lives in [`docs/how-to/distill.md`](../../../docs/how-to/distill.md). The doctrine behind the order lives in [`docs/concepts/citizen-first.md`](../../../docs/concepts/citizen-first.md). Read both before driving the loop.

## What you must do

1. Run `bootstrap` first.
2. Open [`docs/how-to/distill.md`](../../../docs/how-to/distill.md) and execute the seven steps in order.
3. For each step: invoke the owning persona (via the `.github:<Persona>` subagent or by handing off to the user), produce the named artifact, file it under the slug-scoped path the doc specifies, and only then proceed to the next step.
4. Do not skip step 1 (Citizen frames the question) or step 7 (Citizen audits comprehension). Skipping either is a doctrinal violation per [`docs/concepts/citizen-first.md`](../../../docs/concepts/citizen-first.md).

## See also

- [`docs/concepts/citizen-first.md`](../../../docs/concepts/citizen-first.md) — why this order, why Hans precedes Max, why Citizen bookends.
- [`docs/agents/bootstrap.md`](../../../docs/agents/bootstrap.md) — what each persona loads before contributing.
- [`docs/agents/guardrails.md`](../../../docs/agents/guardrails.md) — the rules every step must honour.
