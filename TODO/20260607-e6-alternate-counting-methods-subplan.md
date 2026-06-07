# E6 alternate counting methods - sub-plan

**Date**: 2026-06-07
**Status**: **DEFERRED via triple-verdict convergence** (Citizen + Hans + OWID-no-precedent)
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) Execution ledger row `E6 alternate counting methods (25.6b)` (was DEFERRED-TO-SUBPLAN; this is the sub-plan)
**Gate (user-named)**: Citizen + Hans second opinion + "hypothetical recount, not the official result" honesty banner (parent plan section 25.6b)

## Premise

Per the 2026-06-07 user directive ("fix these in the style of the original plan ship-loop autonomous agents"), the E6 deferred item was investigated end-to-end. Citizen + Hans personas were dispatched in parallel via `runSubagent`. Both verdicts converged on DEFER. The OWID-alignment fallback doctrine (per `docs/concepts/owid-alignment.md`) confirms no canonical precedent. This sub-plan codifies the verdict so the next agent does not re-litigate.

## Verdict matrix

| Persona | Verdict | Load-bearing finding |
| --- | --- | --- |
| **Citizen** | **DEFER INDEFINITELY** (rejects even sandbox-only ship on yen-gov.in) | "I'd see 'BJP would have won 145 seats' and store '145' even with a banner. yen-gov starting to show alternate numbers makes me wonder if the real result was unfair. I cannot think of one real question this answers; I came to find who my MLA is." Prioritisation: this is below dark mode for me; ship (a) district-level budgets, (b) Hindi+regional language, (c) mobile map performance, (d) more state coverage FIRST. |
| **Hans (Governance)** | **DEFER** (Option C); reject Option A (production) AND Option B (sandbox) | (1) Data adequacy: Indian EVMs do not record ranked or approval ballots. Of 3 methods, 2 (RCV, approval) are not honestly simulatable from data we have; PR is half-honest only when reframed as disproportionality *measurement* of the existing system. (2) Political sensitivity: Type 2 (Rosling - data-fabrication) failure mode dominates Type 1 (Pramit - screenshot-out-of-context); both fire. (3) Banner discipline cannot save an indefensible underlying claim. (4) OWID has explicitly stayed out of election-system counterfactuals. (5) Option B sandbox still leaks via screenshots + the committed code IS the precedent. |
| **OWID precedent** | **NO PRECEDENT** | OWID publishes democracy indices, turnout, and seat-share-vs-vote-share *measured* disproportionality (Gallagher index). They have explicitly stayed out of "what-if recount" features. Per `docs/concepts/owid-alignment.md`: "OWID doesn't have an election problem." |

## Decision

**E6 is DEFERRED with no scheduled reopening trigger.** The existing `countSeats` seam at `frontend/src/lib/charts/count-seats.ts` already throws with the right gate language ("ranked-choice / approval / proportional throw per orchestrator anti-pattern" per the X1a-followup ledger). That seam stays in place; the future code-swap is a single-file change. The architectural cost of waiting is small.

**Reopening triggers** (any ONE of these is necessary, none is sufficient):

1. Ranked-ballot data exists for at least one Indian context (student-union STV, municipal-experiment, etc.) AND there is a citizen-named research question that explicitly demands the recount visualisation.
2. A psephologist or named journalist asks for the feature with a specific use case (Pramit-style "I want to ask citizens this question, and yen-gov is the place").
3. The Indian Constitution amendment process actually moves on PR (NCRWC report → JPC → bill); citizens then have a real "how would this affect my AC" question.

None of these is on yen-gov's horizon as of 2026-06-07.

## Hans's carve-out (in-scope for E-series, NOT E6)

Hans recommended one feature that is NOT a recount and therefore NOT subject to the E6 gate:

> **Gallagher disproportionality chart on national + state pages.**
>
> Two stacked bars - "this party got X% of votes" vs "this party got Y% of seats" - with the gap labelled as the disproportionality (positive = over-translated, negative = under-translated). This is a **measurement of the existing system**, not a recount; it uses only data we already have; no simulating assumption; no banner needed.
>
> Belongs in the **E-series UX work** (after E5; possibly slotted as E7 or folded into E4 highlight modes) - NOT in E6.

If we ship Hans's carve-out, the ledger should add a new row (e.g. `E7 Gallagher disproportionality chart`) with normal E-series gates (build + visual + 23-vitest-pattern; no Citizen + Hans gate because the data is honest). Per parent plan section 22.5, that row depends on E5 (which is MERGED, PR #820) but blocks nothing.

## What the agent does NOT do here

- **No new code in `frontend/src/lib/charts/`** for RCV / approval / PR. The `countSeats` throw stays.
- **No `/lab/election-experience` sandbox prototype**. Per Hans Option B rejection, building the simulator at all encodes its assumptions in committed code; the code becomes the precedent.
- **No banner-design component** for "hypothetical recount". Per Hans: "banner discipline is a mitigation, not a defence against an indefensible underlying claim".
- **No flips to existing chart seams** to make them counterfactual-friendly.

## What the agent DOES do here (this sub-plan PR's diff)

1. This sub-plan markdown file is the entire diff.
2. The parent plan's E6 row stays `DEFERRED-TO-SUBPLAN` but the `Status` column is rewritten to `DEFERRED via Citizen+Hans+OWID-no-precedent triple-verdict (this sub-plan)` so the next reader sees the verdict without re-running the persona panel.
3. No code changes. No test changes. No `frontend/src/**` touched.

## Follow-up if user overrides

Per CLAUDE.md section 0a, the user can override Citizen + Hans + OWID at any time by saying "ship E6 anyway". In that case the next-session plan should:

1. Open a NEW sub-plan that captures the user override verbatim per CLAUDE.md section 0a authority-assignment.
2. Author a strong banner component first (Jony persona; the "fabricated-input" primitive Hans named as a prerequisite outliving E6).
3. Ship Hans's Option C carve-out (Gallagher chart) first as the measurement-vs-counterfactual distinction's exemplar.
4. Only THEN spawn an E6 sandbox build, gated on the banner component AND a citizen-test usability run.

## Status update for parent ledger

Replace ledger row E6 status `DEFERRED-TO-SUBPLAN` with:

> `DEFERRED via Citizen+Hans+OWID-no-precedent triple-verdict (sub-plan TODO/20260607-e6-alternate-counting-methods-subplan.md). countSeats() seam at frontend/src/lib/charts/count-seats.ts retains the throw-for-non-FPTP gate. Hans Option C carve-out (Gallagher disproportionality measurement chart) re-routed to E-series as a future E7 row; NOT in E6 scope.`
