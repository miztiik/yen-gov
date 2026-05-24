# ADR-0039: YENASK retrieval-augmented intent extraction (LLM-OS pattern) — Accepted

**Last Updated**: 2026-05-24
**Status**: accepted
**Supersedes**: none
**Amends**: none — ADR-0038 (single-stage LLM rejection of *two-LLM* shapes) remains in force
**Related**: [yenask subsystem doc](../frontend/yenask.md), plan-doc [TODO/20260518-browser-governance-insight-assistant-plan.md](../../../TODO/20260518-browser-governance-insight-assistant-plan.md) §17 D-31..D-33, [ADR-0038](0038-yenask-two-stage-llm-pipeline-rejected.md)

## Context

ADR-0038 (Accepted 2026-05-24) rejected all three "two-LLM" pipeline cuts (classifier+reasoner / model-writes-SQL / hybrid) on grounds that pre-architecting a second model stage was premature given zero published `attempts_log` evidence and that cold-load economics were hostile (1.22 GB – 2.32 GB candidates vs the 273 MB SmolLM2-360M default).

On the same day the user reframed the question: *"what you are describing is a capability for multiple different models — feature extraction, text generation, intent classification. These are different model capabilities and we are trying to do all of them in the same model."*

This is a structurally different proposal from what ADR-0038 rejected. ADR-0038 rejected **two LLMs in sequence** (classifier-LLM + reasoner-LLM, or extractor-LLM + SQL-writer-LLM). The user's reframe is **one LLM plus a non-LLM retrieval primitive**:

- **Catalogue resolution** ("which indicator does this question mean?") is fundamentally a **retrieval** problem, not a generation problem. Cosine similarity over pre-computed concept embeddings is the 50-year-old IR primitive for exactly this. The cost is ~23 MB (`Xenova/all-MiniLM-L6-v2` q8) and ~200 ms inference — versus asking a 360M instruction-tuned SLM to do retrieval, which is the task it is mechanically worst at.
- **Verb classification** (`show / compare / trend / rank`) is a 4-element closed enum solvable by deterministic keyword routing in ~12 lines of TypeScript with zero ms latency and full auditability. ADR-0038 already preserved this as a deferred option (D-27).
- **Slot-filling + answer narration** (extracting state / period / metric mentions from free-text and producing the citizen-readable paragraph) is the irreducible LLM task. Reserve LLM compute for what only LLMs do well.

A six-persona panel — **Andre** (AI/LLM application design, NEW authority per `.github/agents/andre.agent.md`), Citizen, Hans (Governance), Max (Indicator Scout), Gregor (Architect), Fowler (Engineering), Jony (UI/UX) — reviewed the reframe.

## Decision

**Accepted: Slice E — retrieval-augmented intent extraction.** YENASK's pipeline becomes a three-component LLM-OS shape:

1. **MiniLM-L6-v2 embeddings** (Apache-2.0, ~23 MB q8, WebGPU-capable via transformers.js v4.2+) — pre-compute embeddings for every topic + indicator description at lab-startup; expose `findTopKConcepts(question, k=5): {concept_id, cosine_score}[]`. One-time cost; cached in IndexedDB via the existing `model-cache.ts` Cache Storage wrapper.
2. **SmolLM2-360M-Instruct extraction** (unchanged from Slice D-1) — receives `question` + the top-K candidate list as constraints in its system prompt; emits the `InsightIntent` JSON, picking concept_id from the top-K and slot-filling entities + period from free-text.
3. **Deterministic compile + execute** (unchanged) — existing `compile-intent.ts` → `execute-plan.ts` → DuckDB-WASM round-trip with Holy Law #9 provenance JOIN constructed in TypeScript.

**Confidence-threshold fallback** (Gregor's discipline): when `top-1 cosine < 0.6`, fall back to the existing substring-match catalogue resolver and pass NO top-K constraint to the LLM. This keeps the contract intact when the embeddings model is silent or unsure — no silent degradation, no Holy Law #9 risk.

**What this is NOT**:

- NOT a second LLM. The embeddings model is not a generator; it produces a similarity score over a closed catalogue. ADR-0038's two-LLM rejection still holds.
- NOT a vector DB. The catalogue is ~130 entries (topics + indicators); cosine similarity over a flat `Float32Array` lives in 80 lines of TypeScript. A vector DB is a retrieval index, not a memory; this app does not have a retrieval-at-scale problem.
- NOT a framework adoption. No LangChain, no LlamaIndex, no agent orchestrator. The implementation is one new TypeScript module + one new model registry entry.
- NOT a citizen-facing UI change beyond the brand-mark refresh (YENASK → Y-Ask in the logo only; module names, route URLs, LS keys, code comments unchanged — see D-33).

## Consequences

**Positive**:

- **Faster TTFT** — catalogue resolution drops from "wait for the SLM round-trip" (~3–8 s) to "wait for embedding inference" (~200 ms). Citizen sees results faster on every turn after model warm-up.
- **Honest failure mode** — when `top-1 cosine = 0.42`, the answer panel can say *"I'm not sure which indicator you mean. Did you mean A or B?"* — graceful degradation instead of an SLM hallucinating an indicator id.
- **Holy Law #9 strengthened, not weakened** — provenance JOIN still constructed in TypeScript from the resolved `concept_id`. Embeddings just produce a candidate list; the canonical `indicator_id ↔ source_id` mapping read from `manifest.json` is unchanged.
- **+23 MB cold-load (total 296 MB)** — stays under D-24 Small-tier 500 MB threshold; no new download-friction tier; no picker change.
- **Reversal cost is low** — embeddings module is one file; if it underperforms substring-match, delete the file and remove the registry entry. No schema migration, no data corruption.
- **LLM stage gets more accurate, not less** — SmolLM2-360M is bad at retrieval but reasonable at slot-filling once given constraints. Top-K from MiniLM IS the constraint.

**Negative**:

- **Cosine threshold (`0.6`) is a magic number** — will need tuning from `attempts_log` data. Mitigation: start permissive; tighten when data lands; fallback path keeps contract intact regardless. Locked here as a starting value; revisit in 30 days.
- **One new failure surface** — the embeddings model itself can fail to load / time out / return garbage. Mitigation: same readiness-state machine pattern as the existing SLM; if embeddings init fails, fall back to substring-match.
- **MiniLM is English-mostly** — Indic transliteration ("tamizh", "kerala-le", "bihār") may miss. Mitigation: substring fallback catches the misses. Defer promote to `Xenova/multilingual-e5-small` (~118 MB) until `attempts_log` shows Indic gap.
- **Two-component observability** — Debug log gains an `embed_ms` row alongside `extract_ms`. ~10 lines of plumbing. Net positive (tells operator which component is slow); no UX regression.

## Andre's panel verdict (per `.github/agents/andre.agent.md` output format)

**Decision**: Add MiniLM-L6-v2 (Apache-2.0, ~23 MB q8) as a retrieval-augmentation stage before the existing SmolLM2-360M extraction; keep deterministic compile + execute.

**Simplest thing that could work**: One new `frontend/src/lib/yenask/catalogue-embed.ts` module that loads MiniLM via the existing model-adapter pattern, pre-computes ~130 concept embeddings once per session, and exposes `findTopKConcepts(question, k=5)` returning cosine-ranked candidates. Modify `extract-intent.ts` to prepend the top-K list into the system prompt as constraints. ~150 lines total.

**Mechanical gotchas**:
- *Tokenizer surprises*: MiniLM's BPE differs from SmolLM2's; pre-computing concept embeddings is fine but mid-session vocab changes (new indicator landed since lab opened) need a cache-bust. Mitigation: keyed on `manifest.json` content hash.
- *Lost-in-the-middle*: don't inject all 130 concepts into the LLM prompt; only top-5. Lost-in-the-middle bites at N≥10.
- *Prompt injection*: when concatenating user `question` with the system prompt that lists top-K, isolate user input in clear delimiters (`<<<USER>>>...<<<END>>>`) — OWASP LLM01 by reflex. The current `extract-intent.ts` already does this; preserve.
- *Cosine threshold drift*: `0.6` will need tuning. Don't tune it in production; tune it offline against a labelled eval set.

**How you'll know it works**: 20-question labelled eval set (`frontend/src/lib/yenask/fixtures/intent-eval.json`) — citizen-style free-text questions paired with the expected `top_concept_id` and `expected_intent` JSON. Metric: top-1 accuracy on `top_concept_id` AND `intent.entity` extraction recall. Baseline: substring-match's accuracy on the same set. Regression alarm: any drop in top-1 accuracy ≥ 5 percentage points fails the gate.

**Smallest model that passes**: `Xenova/all-MiniLM-L6-v2` q8 (~23 MB cold-load, WebGPU-capable, 384-dim embeddings). Inference ~200 ms on mid-tier Android over WebGPU; ~500 ms WASM fallback. Cached in IndexedDB via existing `model-cache.ts`.

**yen-gov fit**: Holy Law #1 ✓ (in-browser, no backend). Holy Law #7 ✓ (real fixtures in eval set, no mocks). Holy Law #9 ✓ (provenance JOIN still constructed; embeddings only resolve `concept_id`, never `source_id`).

**What to skip**:
- *Vector DB* — 130 entries × 384 dimensions = 200 KB of `Float32Array`. A flat `for` loop with cosine is faster than any vector-DB SDK's initialisation.
- *Multilingual model on day one* — premature; substring fallback covers Indic misses today; promote on attempts_log evidence.
- *Deterministic intent-router* (D-27 / Slice E.3) — this PR's evidence-gathering will tell us whether it's needed. Don't bundle.
- *Fine-tuning anything* — Andre's worldview #5: don't fine-tune to teach facts. The catalogue is already a fact source; embeddings just index it.

## Panel cross-review

- **Citizen**: Faster answers + "did you mean A or B?" honesty when uncertain = clear improvement. No new UI to learn. Approved.
- **Hans (Governance)**: Doesn't change what data the citizen sees; doesn't change what indicators exist. Holy Law #9 stays intact. Indifferent to the embedding layer. Approved.
- **Max (Indicator Scout)**: MiniLM-L6-v2 is the obvious right choice (Apache-2.0, ONNX-ready, shipped in transformers.js-examples WebGPU semantic-search demo). Cold-load economics fine. Future Indic promote path identified. Approved.
- **Gregor (Architect)**: Confidence-threshold + fallback to substring-match is the discipline that keeps the contract clean. Embeddings produce *candidates*; canonical `concept_id ↔ source_id` mapping is unchanged. Holy Law #9 preserved. Approved with the `cosine < 0.6 → fallback` lock.
- **Fowler (Engineering)**: This is a different shape from ADR-0038. Rule-of-three doesn't fire — embeddings-for-retrieval is a 50-year-old IR pattern, not a new abstraction. Reversal cost low (delete one file). Insist on the eval set landing IN Slice E.2 PR, not as a follow-up. Approved with that condition.
- **Jony (UI/UX)**: Embeddings are a silent companion. No new picker, no new toggle, no new modal. Debug log row breakdown gives operator the right visibility. Y-Ask brand-mark refresh (separately decided) lands here. Approved.
- **Andre (AI/LLM)**: See above. Approved with the eval-set-as-contract condition.

**Convergent verdict**: ACCEPTED with two locks — (i) `cosine < 0.6 → substring fallback`, (ii) 20-question labelled eval set ships in Slice E.2 PR.

## Implementation slicing (per Fowler)

- **Slice E.1** (PR after this ADR): `catalogue-embed.ts` module + registry entry + unit tests + eval fixture file authored (not yet wired). Module callable in isolation; vitest covers the cosine + top-K + threshold logic against a `tmp_path` style synthetic catalogue.
- **Slice E.2** (next PR): `extract-intent.ts` integration; `embed_ms` Debug log row; §13 browser smoke at `/dev/yenask`; eval-set regression alarm runs in `bun run test`.
- **Slice E.3** (deferred): deterministic intent-router (ADR-0038 D-27); blocked on `attempts_log` evidence from Slice E.2 deployment. Not in this ADR's decision.

## Y-Ask brand-mark refresh (D-33)

The on-screen logo on the dev-only `/dev/yenask` route renames from "YENASK" to "**Y-Ask**" (with hyphen) in two places: the `<title>` element and the `<h1>` mark. All other instances of "YENASK" / "yenask" are preserved:

- Library / module names: `frontend/src/lib/yenask/...`, `Yenask.svelte`, `yenask.model.id.v1` LS key, `data-route="yenask"`.
- Route URL: `/dev/yenask`.
- ADR titles, plan-doc § titles, subsystem doc title, code comments, agent persona files.
- Citation strings, GitHub PR titles, commit-message subjects.

Rationale: the brand-mark is a citizen-facing affordance; the code identifier is an engineering affordance. They are separately tunable. User direction 2026-05-24: *"This is only for the logo not for library names or anything. Just if you are having a logo or anything in the top left or top right or anywhere we need to use it in that way."*

## Alternatives considered (in this ADR's reframe space; ADR-0038's three cuts remain rejected)

### E-Alt 1 — Embeddings model as a SECOND extractor (replaces SmolLM2-360M)

Rejected because (a) embeddings models don't slot-fill — they produce similarity scores, not JSON. (b) Even if you stretched MiniLM to do classification via prototype-vector trick, you'd lose entity extraction and period parsing, which ARE LLM tasks. (c) This collapses into "no LLM at all", which means no narration — citizens get table rows but no readable answer paragraph.

**Reversal cost**: rejecting costs nothing. Adopting would require building a separate entity-extractor + period-parser + narrator stack, which is strictly larger than the rejected Cut 1 (ADR-0038).

### E-Alt 2 — Defer Slice E entirely until `attempts_log` has 100+ entries of single-stage failure

Considered by Fowler initially; withdrawn after the panel agreed embeddings-for-retrieval is not a rule-of-three abstraction trigger. Substring-match is *known* to be a brittle catalogue resolver (matches "tamil" against any concept containing those 5 chars regardless of semantics); attempting to "wait for more evidence" of a known weakness is procedural overhead. The cosine threshold + substring fallback IS the rule-of-three safety net.

**Reversal cost**: rejecting costs ~30 days of operator friction with a known weakness. Adopting (now) costs the Slice E.1 + E.2 PRs.

### E-Alt 3 — Use a hosted embeddings API (OpenAI text-embedding-3-small, Cohere, etc.)

Rejected on Holy Law #1 (no backend, no API key in static bundle) — same grounds as ADR-0038's Alternative D. Repeated here for completeness because the model-class is different (embeddings vs reasoner) and a future agent might revisit it.

**Reversal cost**: rejecting costs nothing. Adopting later costs Holy Law #1 itself.

### E-Alt 4 — Multilingual-e5-small (~118 MB) on day one instead of MiniLM-L6-v2

Rejected on Max's cold-load economics (296 MB → 391 MB total) and Fowler's evidence discipline (no `attempts_log` evidence yet that Indic transliteration is the bottleneck). Preserved as a parametric swap: `model-registry.ts` accepts a second embeddings entry; the picker just shows it; promote to default when evidence justifies.

**Reversal cost**: rejecting costs ~95 MB of pre-emptive cold-load. Adopting later costs one registry entry edit + one default flip.

## Reversal cost (this decision)

**To reverse Slice E and return to pure single-stage**:
- Delete `frontend/src/lib/yenask/catalogue-embed.ts`.
- Remove the MiniLM entry from `model-registry.ts`.
- Revert the ~30-line modification in `extract-intent.ts`.
- Mark this ADR as `Status: superseded by ADR-NNNN` with the superseding ADR explaining why retrieval-augmentation didn't pay off (which would itself be unusual — it's a 50-year-old pattern).
- No data migration, no schema bump, no breaking change to any of the five frozen Zod contracts.

**To reverse the Y-Ask brand-mark refresh**: two-string revert in `Yenask.svelte`.

Total estimated reversal effort: < 30 minutes if discovered within a week; < 2 hours if discovered after attempts_log integration matures.
