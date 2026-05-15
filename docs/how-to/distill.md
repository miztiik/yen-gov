# Distill: From Citizen Question to Shipped Answer

**Last Updated**: 2026-05-15

This is the seven-step procedure for taking a citizen question and turning it into a shipped, citizen-readable answer in yen-gov. The doctrine behind the order is in [`../concepts/citizen-first.md`](../concepts/citizen-first.md). This doc is the *how*.

The procedure is invokable as the `distill` skill (Claude Code) or by name in Copilot Chat. Either invocation drives the same seven steps below.

## When to run distill

Run `distill` for any new citizen-facing feature, indicator, or page that begins with a citizen question. Do NOT run it for internal pipeline / schema-only / infrastructure changes — those follow `CLAUDE.md`'s correction-level workflow directly.

## Inputs

- One citizen question, in plain language. Example: *"Is my state's police force getting bigger or smaller, and how does that compare to its population growth?"*
- Pillar (People / Money / Infrastructure / Politics) the question lives in.

## The seven steps

Each step has an owning persona, an input, and a concrete artifact. The artifact of step N is the input of step N+1. No step may begin without the previous step's artifact in hand.

### 1. Citizen — frame the question

**Owner**: Citizen User persona.
**Input**: the raw question.
**Artifact**: a one-paragraph brief stating: the question in citizen language, the decision it informs ("would I vote differently?", "would I file an RTI?"), the place the citizen would naturally land (state hub? indicator page? cross-state compare?), and one or two failure modes ("if the page just shows a national average, I'm gone").

### 2. Hans — frame the indicator

**Owner**: Hans (Governance) persona.
**Input**: step 1 brief.
**Artifact**: a framing memo answering: what indicator(s) honestly answer the citizen's question; the right denominator (per-capita / per-household / absolute); the right time grain; the right peer group (all states / income tier / agro-climatic zone); the methodology breaks to surface; the trap interpretation to defuse on the page; the input-vs-output-vs-outcome label. Filed under `docs/research/<slug>.md` or extending an existing pillar concept doc.

### 3. Max — scout the source

**Owner**: Max (Indicator Scout) persona.
**Input**: step 2 framing memo.
**Artifact**: a source memo with: candidate sources in priority order (issuing authority → re-publisher → research-grade), licence and refresh cadence per source, state × year coverage, methodology-break risk, confidence (gold/silver/bronze), and an explicit `acquire | queue | defer | reject` recommendation. Filed under `docs/research/<slug>.md`.

### 4. Gregor — name the contract

**Owner**: Gregor (Architect) persona.
**Input**: steps 2 + 3.
**Artifact**: schema design — does it extend an existing schema (minor bump) or need a new one? what's the canonical shape? where does it slot in the indicator catalogue? what does the contract foreclose? Documented in the relevant subsystem doc under `docs/architecture/schemas/`. If genuinely cross-cutting and irreversible, an ADR.

### 5. Fowler — implement the ingest

**Owner**: Fowler (Engineering) persona, but the default agent does the actual code.
**Input**: steps 3 + 4.
**Artifact**: the ingest adapter under `backend/yen_gov/sources/<source>/`, real-fixture tests under `backend/tests/`, the emitted artifact under `datasets/indicators/<pillar>/<slug>.json` with `sources` array per `CLAUDE.md §12`, schema bump if any, all in small reversible commits with two-hat discipline (structural and behavioural changes never share a commit).

### 6. Jony — surface in the UI

**Owner**: Jony (UI/UX) persona.
**Input**: step 5 dataset + step 1 brief.
**Artifact**: UI spec — default view that answers the citizen's first question; controls in priority order with the gesture for each; legend / labelling rules; provenance placement (`SourceList`); component impact (extend existing schema-driven generic vs new component, with strong preference for the former). Implementation by the default agent against `frontend/src/lib/`.

### 7. Citizen — comprehension audit

**Owner**: Citizen User persona, against the running dev server (`http://localhost:5173/`).
**Input**: the deployed-locally page from step 6.
**Artifact**: a citizen-walkthrough — landed at, see in 3 seconds, came wanting to know, try to do, get stuck because, would stay if. The walkthrough must literally answer the question from step 1 in citizen language; if it can't, the loop returns to whichever step is responsible (often step 6 for clarity, sometimes step 2 for framing).

## Handoff discipline

- No step may begin without the previous step's artifact filed and linked.
- Each artifact carries a date and the persona that produced it.
- All artifacts for one citizen question live under one slug — `docs/research/<slug>.md` for steps 2 + 3, `docs/architecture/schemas/<slug>.md` (or extension thereof) for step 4, the dataset path for step 5, the UI route for step 6, the walkthrough appended to `docs/research/<slug>.md` for step 7.

## What "done" looks like

- Step 1 brief filed.
- Step 2 framing memo filed.
- Step 3 source memo filed with `acquire` recommendation.
- Step 4 schema or schema-extension landed.
- Step 5 dataset emitted with `sources` array; tests green per `CLAUDE.md §15` tier appropriate to the change.
- Step 6 UI spec landed; new route or updated route renders without console errors / 404s per `CLAUDE.md §13`.
- Step 7 walkthrough appended; the citizen could answer their own question from the page in under 30 seconds.
- Docs updated in the same commit as code per Holy Law #4.

## See also

- [`../concepts/citizen-first.md`](../concepts/citizen-first.md) — the doctrine behind this order.
- [`../agents/bootstrap.md`](../agents/bootstrap.md) — what each persona loads before contributing.
- [`../agents/guardrails.md`](../agents/guardrails.md) — the rules every step must honour.
- [`../../CLAUDE.md`](../../CLAUDE.md) §15 — the test-tier table that step 5 must satisfy.
- [`../../CLAUDE.md`](../../CLAUDE.md) §13 — the UI verification policy that step 7 satisfies.
