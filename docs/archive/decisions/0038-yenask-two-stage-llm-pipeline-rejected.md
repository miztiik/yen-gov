# ADR-0038: YENASK two-stage LLM pipeline — Rejected (deterministic router preserved as a deferred option)

**Last Updated**: 2026-05-24
**Status**: rejected
**Related**: [yenask subsystem doc](../frontend/yenask.md), plan-doc [TODO/20260518-browser-governance-insight-assistant-plan.md](../../../TODO/20260518-browser-governance-insight-assistant-plan.md) §17 D-25 + D-26

## Context

PR-3 (commit `63a62a4e`, deployed `2026-05-24T17:55:01Z`) shipped the YENASK browser governance-insight assistant at `/dev/yenask` with the **single-stage** model adapter contract: one call to `extractIntent(question, catalogue, adapter)`, the model returns a JSON `InsightIntent`, the existing deterministic `compile-intent.ts` (~91 lines) translates that intent into the DuckDB SQL pair (main + provenance) under Holy Law #9 (provenance JOIN constructed, not generated). Per-attempt diagnostics — `tokens_in`, `tokens_out`, `tokens_approximate`, `wall_ms`, raw model output, `parse_status` — already land in the `ExtractAttempt[]` log (per plan-doc D-20) and the Debug log surface (per D-21).

On 2026-05-24 the user asked for an "ABCD" sprint that included a Slice D: introduce a **second LLM stage** to YENASK to make the pipeline more capable. Three architectural cuts were proposed during planning:

- **Cut 1 — Classifier + reasoner**: tiny classifier model (~50M params) decides which of N concept categories (currently 4 — `vote_share_by_party`, `winning_party_per_ac`, `top_candidates_per_ac`, `seat_count_by_party`) the question maps to; medium reasoner (Phi-3.5-mini / Qwen2.5-1.5B class) extracts the rest of the `InsightIntent` fields and produces narrative text. Compile path unchanged.
- **Cut 2 — Intent extractor + code-tuned SQL generator**: replace `compile-intent.ts` with a second model (StarCoder-class) that writes the DuckDB SQL directly. Sandbox via sqlglot allowlist + DuckDB `EXPLAIN` dry-run.
- **Cut 3 — Hybrid**: classifier-first dispatch — if the classifier hits a registered concept, use deterministic Stage 2 (today's compile-intent); otherwise fall back to model-writes-SQL (Cut 2's shape).

A four-persona panel — Jony (UX, on the user-visible delta), Gregor (Architect, on the contracts), Fowler (Engineering, on craft + reversal cost), Max (Indicator Scout, on model availability + cold-load economics) — reviewed all three cuts.

## Decision

**All three cuts are rejected as currently scoped.** The convergent panel finding:

1. **Pre-architecting a second model stage is premature.** The pipeline has 4 concepts registered today and ZERO published failure-mode evidence from the `ExtractAttempt[]` log that the single-stage extraction is the blocker on adding more concepts. PR-3 shipped the `attempts_log` observability surface for exactly this purpose — to identify which failure modes are real BEFORE architecting around them. Adding the next 6–10 concepts on the single-stage path is the structurally cheaper move and produces the evidence that any future Stage 2 decision must rest on.
2. **Cut 2's "model writes SQL" frontally violates Holy Law #9 + D-12 + D-16.** Today the provenance JOIN is **constructed** in TypeScript (`compile-intent.ts` knows exactly which `source_id` FK to project from which fact table); under Cut 2 the model is asked to **generate** SQL that happens to include a provenance JOIN of the right shape. This converts a CONSTRUCTION-time invariant into a GENERATION-time hope. sqlglot allowlist + DuckDB `EXPLAIN` dry-run as the safety boundary are insufficient: allowlists prevent unauthorized table access but not semantically wrong joins; `EXPLAIN` tells you the SQL is parseable, not that it answers the question asked. D-12 explicitly rejected `deriveConceptId` as the "model invents concept slugs" band-aid; Cut 2 is that pattern applied one layer down (model invents SQL).
3. **Cut 3 inherits Cut 2's failure modes on the fallback path AND re-introduces the `concept_id = "unknown"` sentinel** that D-12 rejected. The hybrid bundles two architectures whose failure modes are different — operators debugging a "wrong answer" turn would have to first determine which branch executed before they can reason about the failure. Rule-of-three-before-abstraction fires hard: there is no third concept beyond "extractor" and "compiler" that justifies a dispatcher between them yet.
4. **Cut 1's classifier shape is the right altitude but wrong tool.** A neural classifier of any size for a 4-element closed enum is over-engineering by an order of magnitude versus deterministic keyword routing. If a Stage 1 router is ever justified by attempts_log evidence, it should be a pure-TypeScript `routeIntent(question, catalogue): RouterResult` that pattern-matches against the bounded catalogue vocabulary (party names, AC names, year tokens, comparison keywords) — same architectural slot as a neural classifier, but inspectable, deterministic, reversible, and zero-cold-load. Cut 1 reduced to a deterministic router is preserved as a **deferred option** below.
5. **Cold-load economics for any second model are hostile under current registry.** Per Max's HF inventory: Phi-3.5-mini @ q4f16 ≈ 2.32 GB (20× current 118 MB SmolLM2-135M cold-load); Qwen2.5-3B has no verified ONNX port; Llama-3.2-1B has a restrictive Meta license; Gemma-2-2B license + ONNX availability unverified. The only Apache-2.0 + verified-available reasoner in the 1B–2B band is Qwen2.5-1.5B-Instruct at 1.22 GB — still 14× the current cold-load. The lab IS /dev-only today, but cold-load size affects how operators dogfood it; every persona test cycle pays the size cost.

What survives:

- **Default-model upgrade SmolLM2-135M → SmolLM2-360M** (per plan-doc D-26) — strict accuracy upgrade with no architecture change; ships as Slice D-1 (PR-7).
- **Deferred deterministic intent-router** (per plan-doc D-27 if/when justified) — pure-TypeScript `intent-router.ts` + existing model fallback; no second model; no new cold-load. Requires attempts_log evidence demonstrating a routing-class failure mode that the current single-stage flow cannot resolve via prompt tightening or catalogue refactor.

## Consequences

**Positive**:

- All five existing Zod contracts (`InsightIntent`, `DuckDBPlan`, `AnswerViewModel`, `GenerateResult`, `ExtractAttempt`) stay frozen; no breaking changes to the subsystem doc's [pipeline](../frontend/yenask.md).
- Holy Law #9 (provenance JOIN constructed) and D-12 (no model-invented concept slugs) remain enforced by the existing `compile-intent.ts`, which is NOT deleted.
- The 91 lines of `compile-intent.ts` retain their property: SQL safety is a construction-time invariant, not a validation-time hope.
- Operators can grow the concept catalogue from 4 → 10+ on the proven single-stage path while attempts_log accrues real evidence on which question shapes the single-stage extraction handles vs fumbles.
- The user-asked-for Slice D delivers something tangible (D-26 default flip) without speculative architectural debt.

**Negative**:

- The user's "two-stage" mental model goes unsatisfied at the LLM level for this sprint. Partial compensation: the existing pipeline IS already two-stage at the right altitude (model → deterministic compiler); D-26's accuracy lift is in the EXTRACTION stage where it matters most for the current bottleneck.
- Any future "let's add a second model stage" proposal MUST cite this ADR and surface new evidence (attempts_log failure-mode counts, named-question regression set, comparative cold-load economics) justifying revisit. This is a feature, not a bug — speculative re-architecting is what got rejected.
- Operators who want to handle "free-text question outside the 4-concept enum" today still see the "no matching concept" path; broadening that requires concept catalogue growth, not a second model.

## Alternatives considered

### A. Cut 1 — Tiny classifier + medium reasoner (50M classifier + Phi-3.5-mini or Qwen2.5-1.5B reasoner)

Rejected because (a) deterministic keyword routing against a 4-element closed enum is the right tool — a neural classifier is order-of-magnitude over-engineering with worse properties (non-inspectable, non-deterministic, cold-load cost). (b) Reasoner cold-load economics: 1.22 GB (Qwen2.5-1.5B) – 2.32 GB (Phi-3.5-mini) versus current 118 MB — 10–20× cost for unmeasured accuracy lift in a pipeline where the bottleneck is unknown. (c) Even Cut 1's classifier was framed as eagerly downloaded in `prepare()`; lazy-on-first-need is the only economic shape, but laziness doesn't avoid the size cost on the first free-text question. (d) The "what does the classifier choose between" set is FOUR items today; the model is not the missing piece, the catalogue is.

**Reversal cost**: rejecting Cut 1 costs nothing today (no code shipped). Adopting Cut 1 later costs (a) the cold-load economics above, (b) a new contract `RouterDecision` adjacent to `InsightIntent`, (c) two model registry entries with their own readiness state machines, (d) telemetry overhead to track which path produced each answer.

### B. Cut 2 — Single intent extractor + code-tuned SQL generator (replace compile-intent.ts)

Rejected because (a) Holy Law #9 violation: the provenance JOIN moves from constructed to generated, and `EXPLAIN` dry-run + sqlglot allowlist don't restore the property — they only verify SQL is parseable and accesses allowed tables, not that it answers the citizen's question with the correct provenance. (b) D-12 explicit precedent: `deriveConceptId` was rejected as the "model invents concept slugs" band-aid; "model invents SQL" is the same pattern one layer down with worse failure modes (wrong SQL returns plausible-looking numbers with the wrong source citation). (c) `compile-intent.ts` is a 91-line module with a precise contract; replacing it with a SQL-validation + injection-screen + provenance-enforcement layer is structurally larger (250+ lines on a generous estimate) and has worse properties (validates after the fact instead of constructing-safely). (d) §14 Open Questions item on "SLM safety gate (sqlglot allowlist or DuckDB EXPLAIN dry-run)" is unresolved; building Cut 2 before that question resolves is building on sand.

**Reversal cost**: rejecting Cut 2 costs nothing today. Adopting Cut 2 later costs (a) the 91-line compile-intent deletion, (b) the 250+-line validator layer, (c) reopening Holy Law #9's "provenance is constructed not generated" invariant for renegotiation, (d) full revisit of D-12.

### C. Cut 3 — Classifier-first hybrid (classifier-routes-to-deterministic-OR-code-model-fallback)

Rejected because (a) inherits 100% of Cut 2's failure modes on the fallback path (model writes SQL); the hybrid does not solve Cut 2's problems, it conditionally introduces them. (b) re-introduces `concept_id = "unknown"` as the sentinel for the fallback branch — exactly the value D-12 rejected. (c) bundles two architectures whose failure modes are different (deterministic-wrong vs model-wrong), making operator triage strictly harder than either alone. (d) violates rule-of-three: there are TWO existing concepts (extractor + compiler), no third concept justifying a dispatcher between them yet. (e) the "fallback" framing presupposes the deterministic path covers most cases — which is exactly the question attempts_log is currently gathering evidence on, so Cut 3 prejudges the answer.

**Reversal cost**: rejecting Cut 3 costs nothing today. Adopting Cut 3 later inherits Cut 2's reversal cost PLUS the dispatcher contract + the `concept_id = "unknown"` reintroduction.

### D. Replace YENASK's single-stage path with a server-hosted LLM (OpenAI / Anthropic / Gemini)

Not formally proposed during the roundtable, listed here for completeness. Rejected because (a) Holy Law #1 (static-first production, no production backend) — yen-gov has no server to host an API key behind; shipping the key in the static bundle is an immediate security incident. (b) Holy Law #9 (provenance is mandatory) — server-side LLM responses carry no source FK; rebuilding the provenance JOIN client-side after the fact reintroduces the Cut 2 failure mode. (c) cost ladder — every citizen visit becomes a per-token bill; defeats the "static site, scales to zero" property. (d) data-residency concerns for any future india-as-default routing.

**Reversal cost**: rejecting Server-LLM costs nothing today. Adopting it later costs Holy Law #1 itself — a fundamental architectural premise of the project, not a tactical decision.

## Preserved future option (NOT this ADR's decision)

A **deterministic pure-TypeScript intent router** sitting in front of the existing model adapter — same Stage-1 architectural slot Cut 1 proposed, implemented as `frontend/src/lib/yenask/intent-router.ts` with signature `routeIntent(question: string, catalogue: Catalogue): RouterResult` — is preserved as a deferred option per plan-doc D-27 (to be authored when justified). It would:

- Pattern-match `question` against the bounded catalogue vocabulary (party names, AC names, state names, year tokens, comparison keywords like "compare", "vs", "between") to produce `{ concept_id, hints }` directly.
- Short-circuit the model call when match confidence exceeds a tunable threshold; fall through to the existing single-stage model path otherwise.
- Add zero cold-load cost (pure TS).
- Add a golden-question regression harness (`route-question.test.ts`) BEFORE shipping — to detect silent misroutes that would otherwise present as correct-looking-but-wrong answers.
- Cite this ADR explicitly and produce attempts_log evidence justifying its addition.

The router is NOT adopted in this ADR. This section exists so a future ADR adopting it has a clear "the deferred path was this shape, here's why we held it" reference.

## Notes

This is the first YENASK ADR. The subsystem doc [docs/architecture/frontend/yenask.md](../frontend/yenask.md) is the living-shape home; this ADR is the rejected-decision register. Future YENASK ADRs land here only when they meet the [ADR-0034](0034-documentation-routing-contract.md) two-criterion test: credible rejected alternative with non-trivial reversal cost AND cross-cutting (no single subsystem doc is the natural home). The "second LLM stage" question meets both criteria; "which model is the default" (D-26) does not — it lives in the plan-doc decision log and the subsystem doc's Model registry section only.
