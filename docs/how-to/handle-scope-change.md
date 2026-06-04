# How to handle a scope change (STOP-AND-SURFACE)

**Last Updated**: 2026-06-02

The procedure for when in-flight work would reinterpret, downgrade, substitute, or scope-narrow something the user named explicitly. The rule is simple: **do not auto-resolve it, and do not consult an agent to proceed. Stop, surface it, and wait for the user.**

This doc exists because of a real miss. A user said "ingest `All_States_GA.csv`"; the work silently downgraded that file to a "crosswalk / historical fallback only" role inside baked-facts (the lowest-visibility surface) and never ingested the historical series the user asked for. The downgrade was a defensible engineering judgement - the file is an AC-segment file with no electors column - but it was a **contract change the user never approved**, buried where the user could not see it. The fix is procedural, not a schema field.

## When this rule fires

Fire STOP-AND-SURFACE when the next action would do ANY of these to an artifact or instruction the user named explicitly (by filename, source name, indicator, route, or verbatim request):

- **Reinterpret** - treat "ingest X" as "use X to validate Y".
- **Downgrade** - move X from a citizen-visible surface to a fallback / crosswalk / internal-only surface.
- **Substitute** - ship Z instead of the X the user named, even if Z is better.
- **Scope-narrow** - deliver a strict subset (e.g. 9 of 13 indicators, 1 of 31 states) and call the request done.

It does NOT fire for ordinary ambiguity (which column type, which test tier, how to name a helper). Resolve those by consulting the row's named authority per [CLAUDE.md](../../CLAUDE.md) section 0a, applying the verdict, and proceeding.

## What to do

1. **Stop.** Do not ship the reinterpreted/downgraded/substituted/narrowed version. Do not ask an agent how to proceed - no agent can approve a contract change the user owns (section 0a: user approval supersedes every agent).
2. **Set the plan-doc row** status to `BLOCKED-NEEDS-SIGNOFF`.
3. **Write a Scope-change ledger row** in the active plan-doc (a plain markdown table - NO schema enum, NO catalogue field). Columns:

   | Verbatim user instruction | Proposed change | Reason | `signoff:` |
   | --- | --- | --- | --- |
   | the exact words the user used | what you would change it to, and on which surface | the engineering reason the change is tempting | leave EMPTY until the user signs |

4. **Surface it to the user** in plain language: "you asked for A; the honest options are A-as-asked (cost ...) or B (cost ...); which do you want?" Present the trade-off; do not pre-decide it.
5. **Proceed only after** the `signoff:` cell is filled by the user. The user may (a) accept your proposed change, (b) re-mandate the original, or (c) pick a third path. Record whichever in the cell.

## Why a ledger and not a schema enum

An earlier proposal was to add an `INGESTED-AS-ASKED | REINTERPRETED` enum to the ingest handover template. Rejected: the failure was a **process** failure (a contract change made invisibly), not a missing data field. A schema enum would be one more box to tick-and-forget; a visible ledger row in the plan-doc the user is already reading forces the trade-off into the open where the user signs it. Keep the guardrail in process, not in machinery.

## Closure

A plan-doc cannot be declared complete while any Scope-change ledger row has an empty `signoff:`. The Definition of Done checkbox (CLAUDE.md section 9) enforces this.

## See also

- [CLAUDE.md](../../CLAUDE.md) section 0a (user approval supersedes every agent), section 9 (Definition of Done), section 10 (Anti-Patterns)
- [docs/how-to/distill-a-plan.md](distill-a-plan.md)
- [docs/how-to/ship-a-pr.md](ship-a-pr.md)
