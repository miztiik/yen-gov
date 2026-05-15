# Citizen-First: We Work Question-First, Not Data-First

**Last Updated**: 2026-05-15

This is the doctrine that decides the order in which yen-gov's six personas (Citizen, Hans, Max, Gregor, Fowler, Jony) collaborate on any new citizen-facing feature. The procedural form lives in [`../how-to/distill.md`](../how-to/distill.md); this doc is the *why* behind that order.

## The principle

A feature begins with a citizen's question, not with a dataset that happens to be available. The pipeline starts with **Citizen** (what is being asked?) and ends with **Citizen** (did we actually answer it?). Citizen bookends the work; everything in between is in service of that question.

This inverts the historical default of "ingest dataset → figure out who cares." That default produces beautiful charts that nobody came looking for. yen-gov is a governance-transparency product for Indian citizens — its load-bearing input is an actual citizen's question, surfaced from civic curiosity ("is my state doing better than the one next door on health?"), not from data-supply.

## Why Hans precedes Max

In the older mental model, Max (Indicator Scout) went first — scout the data, then frame it. We invert that: **Hans (Governance) frames the question first, then Max scouts the source that honestly answers the framed question.** The reason is that the framing decides what would *count* as an answer. Without Hans's framing pass, Max can scout a perfectly authoritative dataset that answers the wrong question — e.g. "GST collected by state" looks like a state-performance metric but is actually a measure of where consumption was billed (Roy's standing rule). Framing first protects against authoritative-but-misleading acquisition.

Max remains *upstream* of the engineering personas (Gregor, Fowler) — he still answers "what indicator should we acquire and from where?" — but he is now downstream of Hans, not upstream.

## The full order

1. **Citizen** — *what question is being asked? what decision does it inform?* Problem definition in plain language.
2. **Hans** — *given that question, what indicator(s) in the Indian fiscal-federal context would honestly answer it? what's the framing trap?* Framing memo.
3. **Max** — *which upstream sources can support that framing? are they comparable across years and states?* Source memo with acquisition recommendation.
4. **Gregor** — *schema and contract for the chosen indicator(s).* Contract proposal.
5. **Fowler** — *ingest adapter, fixtures, tests, small commits.* Implementation.
6. **Jony** — *how it surfaces in the UI (legend, color ramp, comparison view).* UI spec.
7. **Citizen** *(again)* — *does the page actually answer the question from step 1?* Comprehension check.

The Citizen step is intentionally repeated. The opening Citizen pass is the *brief*; the closing Citizen pass is the *audit*. Skipping either is a doctrinal violation.

## What failure looks like when this is violated

- **Skip step 1 (Citizen at start).** "We have NCRB data, what should we do with it?" → produces a crime-by-state choropleth that no citizen came looking for, with framing traps Hans would have caught (population denominator? reporting-rate confound? state-police-data discretion?).
- **Run Max before Hans.** Max scouts an authoritative source; Hans is then asked to frame what was already acquired and either has to defend a poor framing or send Max back to re-scout. Wasted acquisition cycle.
- **Skip step 7 (Citizen at end).** Page ships, builds clean, schema validates, tests pass — and the citizen who clicked the WhatsApp link still can't figure out whether their state is doing well. The *engineering* loop closed; the *product* loop didn't.

## What's not in scope for this doctrine

- Internal pipeline / infrastructure / schema-only / tooling changes. These don't have a citizen-question shape and don't need to run the full loop. They still honour `CLAUDE.md` Holy Laws and the rest of the engineering contract.
- Bug fixes inside an existing citizen feature. Those need step 7 (does the fix actually fix the citizen-visible problem?) but rarely the full loop.

## See also

- [`../how-to/distill.md`](../how-to/distill.md) — the seven-step procedure with artifact per step.
- [`../agents/bootstrap.md`](../agents/bootstrap.md) — what each persona loads before contributing to the loop.
- [`../agents/guardrails.md`](../agents/guardrails.md) — the rules that constrain every step.
- [`../../CLAUDE.md`](../../CLAUDE.md) — the engineering contract.
- [`../../TODO/SOCIO-ECONOMIC-EXPANSION.md`](../../TODO/SOCIO-ECONOMIC-EXPANSION.md) — the umbrella plan that lists candidate citizen questions per pillar.
