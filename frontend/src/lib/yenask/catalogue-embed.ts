// YENASK catalogue embedding + top-K concept retrieval.
//
// Slice E.1 (ADR-0039) — implements the retrieval-augmented intent
// extraction pipeline. See:
//   - docs/architecture/decisions/0039-yenask-retrieval-augmented-intent-extraction.md
//   - docs/architecture/frontend/yenask.md  §"Approved evolution — Slice E pipeline"
//   - TODO/20260518-browser-governance-insight-assistant-plan.md  §17 D-32
//
// Pipeline role:
//
//   citizen question                                 ← (input)
//        │
//        ▼
//   ┌──────────────────────────────────────────┐
//   │  findTopKConcepts(question, k)           │  ← THIS MODULE
//   │   - embed question (MiniLM-L6-v2)        │
//   │   - cosine against concept embeddings    │
//   │   - top-K sorted desc                    │
//   └──────────────────────────────────────────┘
//        │
//        ▼
//   if top-1 cosine < 0.6 → substring-match fallback  (Gregor lock)
//        │
//        ▼
//   SmolLM2-360M extraction (top-K injected as system-prompt constraints)
//        │
//        ▼
//   deterministic compile + DuckDB-WASM execute
//
// Boundaries:
//   - This module is PURE TypeScript. No transformers.js import at
//     module top-level. The embedding function is dependency-injected
//     via the `EmbedFn` interface — Slice E.2 (PR C) wires this to the
//     model-adapter "feature-extraction" pipeline at the seam where
//     extract-intent.ts calls findTopKConcepts.
//   - No DuckDB-WASM. Concept embeddings are derived from a hand-authored
//     constant array (CONCEPT_CATALOGUE) below, NOT from the semantic
//     catalogue's runtime fact-table queries. The concepts are the LLM's
//     dispatch surface — they live in code, not data, per D-04.
//   - findTopKConcepts is the ONLY public API. Helpers are exported for
//     unit testability; consumers should not depend on them.
//
// Cache semantics:
//   - Concept embeddings are computed ONCE per page load and cached in a
//     module-level `Promise`. The cache key is the FROZEN content of
//     CONCEPT_CATALOGUE; adding a new concept = the cache invalidates on
//     next reload (no stale-embedding bug). Per-question embeddings are
//     not cached — the question changes each turn.
//
// Threshold tuning (D-32 Gregor lock):
//   - `COSINE_THRESHOLD = 0.6` is the floor below which we treat
//     "embeddings shrugged" and fall back to substring matching. The
//     value is calibrated empirically; tune in a follow-up PR with
//     attempts_log evidence, not a guess.

import type { ConceptId } from "./contracts/insight-intent";

// -----------------------------------------------------------------------------
// Concept catalogue — what the embeddings index.
// -----------------------------------------------------------------------------
//
// Each entry is one of the 4 PR-1 ConceptId values plus a short embedding
// passage. The passage is a CONCATENATION of:
//   1. the canonical concept_id (helps the LLM ground if it sees the id)
//   2. a one-line description (the citizen-readable gloss)
//   3. a few example phrasings (synonyms / paraphrases citizens might use)
//
// Embedding models embed PHRASES, not enums — the more natural-language
// variation in the passage, the more robust top-K becomes. Length is kept
// to ~40-80 words per concept; longer hurts more than it helps for MiniLM.
//
// Adding a new concept = add a new entry here AND add a new id to
// ConceptIdEnum in contracts/insight-intent.ts AND add a handler in
// concepts.ts. The eval-set fixture (fixtures/intent-eval.json) MUST
// gain at least 3 new labelled questions for the new concept (Andre +
// Hamel + Fowler lock — eval-set-as-contract; see Slice E.2).
//
// Frozen with `as const` so the type system pins the ConceptId literal.

export interface ConceptCatalogueEntry {
  /** The closed-enum dispatch key. Must match a ConceptId. */
  readonly concept_id: ConceptId;
  /** Embedding passage — id + gloss + example phrasings. */
  readonly passage: string;
}

export const CONCEPT_CATALOGUE: readonly ConceptCatalogueEntry[] = [
  {
    concept_id: "party_totals",
    passage:
      "party_totals: Total seats and votes won by each party in a state's " +
      "election. Examples: 'How many seats did DMK win?', 'Party-wise vote " +
      "share in Tamil Nadu', 'Which parties won the most seats?', 'AIADMK " +
      "vs DMK seat totals', 'Vote share breakdown by party in Bihar 2025', " +
      "'How did INC do in Karnataka?', 'BJP seat count in UP'.",
  },
  {
    concept_id: "closest_contests",
    passage:
      "closest_contests: Constituencies with the narrowest victory margins — " +
      "the seats where the winner barely beat the runner-up. Examples: " +
      "'Which seats were closest?', 'Narrowest wins in TN', 'Tightest " +
      "margins by less than 1000 votes', 'Knife-edge constituencies', " +
      "'Photo-finish seats in Bihar', 'Seats decided by a small gap', " +
      "'Closest contests in the state'.",
  },
  {
    concept_id: "constituency_result",
    passage:
      "constituency_result: Top candidates plus NOTA plus collapsed others " +
      "for ONE specific assembly constituency (AC) in one election. " +
      "Examples: 'What happened in Mylapore?', 'AC 167 result', 'Who won " +
      "from Coimbatore South?', 'Top candidates in seat 234', 'Constituency " +
      "breakdown for Chennai Central', 'Who came second in Madurai East?', " +
      "'AC result Anna Nagar'.",
  },
  {
    concept_id: "turnout_extremes",
    passage:
      "turnout_extremes: Highest and lowest voter turnout constituencies in " +
      "a state's election — extremes of participation. Examples: 'Highest " +
      "and lowest turnout seats', 'Where did voters turn out most?', " +
      "'Worst turnout constituencies', 'Top 10 turnout ACs', 'Voter " +
      "participation extremes', 'Best and worst turnout seats in TN', " +
      "'Which constituencies had the most/least voting?'.",
  },
] as const;

// -----------------------------------------------------------------------------
// Embedding function interface (DI seam).
// -----------------------------------------------------------------------------
//
// `EmbedFn` is what the model-adapter exposes once Slice E.2 wires the
// "feature-extraction" pipeline. Embed a batch of strings, get back a
// batch of L2-normalised dense vectors. The contract is intentionally
// runtime-agnostic — a future swap to a different embedding backend
// (e.g. multilingual-e5-small) requires only a new EmbedFn impl, not
// a change to this module.
//
// Vectors are returned as plain `number[]` (not Float32Array) so vitest
// assertions stay readable. Embedding dim is implicit in the output;
// callers should verify it matches the registry entry's `embedding_dim`.

export type EmbedFn = (texts: readonly string[]) => Promise<readonly number[][]>;

// -----------------------------------------------------------------------------
// Pure math helpers (testable in isolation).
// -----------------------------------------------------------------------------

/**
 * Cosine similarity between two equal-length vectors.
 *
 * Returns 0 when either vector is the zero vector (avoids divide-by-zero
 * NaN). Returns the dot-product divided by the product of L2 norms
 * otherwise. Range is [-1, 1] but normalised embeddings cluster in
 * [0, 1] in practice.
 *
 * Throws if the vectors differ in length — that's a contract violation
 * upstream (callers mixed vectors from different embedding models), not
 * something to silently coerce.
 */
export function cosineSimilarity(
  a: readonly number[],
  b: readonly number[],
): number {
  if (a.length !== b.length) {
    throw new Error(
      `[yenask] cosineSimilarity: length mismatch ${a.length} vs ${b.length}`,
    );
  }
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  if (normA === 0 || normB === 0) return 0;
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

export interface TopKMatch {
  readonly concept_id: ConceptId;
  readonly cosine_score: number;
}

/**
 * Returns the top-K matches sorted by cosine_score descending. Stable on
 * ties (preserves input order). Caps k at the candidate count.
 *
 * Pure function: takes pre-computed concept vectors + the question
 * vector + the catalogue order; returns the ranked list. No I/O. No
 * embedding calls. Trivially unit-testable.
 */
export function rankByCosine(
  questionVec: readonly number[],
  candidates: readonly { concept_id: ConceptId; vector: readonly number[] }[],
  k: number,
): readonly TopKMatch[] {
  const scored = candidates.map((c) => ({
    concept_id: c.concept_id,
    cosine_score: cosineSimilarity(questionVec, c.vector),
  }));
  // Stable sort: scored is the same order as candidates; ties keep input order.
  scored.sort((x, y) => y.cosine_score - x.cosine_score);
  return scored.slice(0, Math.max(0, Math.min(k, scored.length)));
}

// -----------------------------------------------------------------------------
// Threshold lock (D-32 Gregor — "graceful degradation when embeddings shrug").
// -----------------------------------------------------------------------------

/**
 * Cosine-score floor below which top-1 is considered an unreliable match
 * and the caller should fall back to substring matching against concept
 * passages. Empirically calibrated; tune with attempts_log evidence, not
 * guesses. Slice E.2 (PR C) wires the fallback at the extract-intent
 * seam.
 */
export const COSINE_THRESHOLD = 0.6;

// -----------------------------------------------------------------------------
// Concept embedding cache (module-level, per-load).
// -----------------------------------------------------------------------------

/**
 * Cached embeddings for CONCEPT_CATALOGUE. Built lazily on first
 * findTopKConcepts call, then reused for the rest of the page's life.
 * The cache key is implicitly the frozen CONCEPT_CATALOGUE — adding a
 * new entry requires a page reload (and a fixture update) to take
 * effect.
 *
 * The cache is a Promise so concurrent first-callers share one
 * computation (no double-embed race). On failure the promise is reset
 * so a retry can re-enter.
 */
interface CachedConceptEmbeddings {
  readonly entries: readonly { concept_id: ConceptId; vector: readonly number[] }[];
}

let conceptEmbeddingsCache: Promise<CachedConceptEmbeddings> | null = null;

async function buildConceptEmbeddings(
  embed: EmbedFn,
): Promise<CachedConceptEmbeddings> {
  const passages = CONCEPT_CATALOGUE.map((e) => e.passage);
  const vectors = await embed(passages);
  if (vectors.length !== CONCEPT_CATALOGUE.length) {
    throw new Error(
      `[yenask] embed(): expected ${CONCEPT_CATALOGUE.length} vectors, got ${vectors.length}`,
    );
  }
  return {
    entries: CONCEPT_CATALOGUE.map((e, i) => ({
      concept_id: e.concept_id,
      vector: vectors[i],
    })),
  };
}

/**
 * Test-only: reset the module cache so a fresh embed() call runs in the
 * next test. NOT for production use.
 */
export function __resetConceptEmbeddingsForTests(): void {
  conceptEmbeddingsCache = null;
}

// -----------------------------------------------------------------------------
// Public API.
// -----------------------------------------------------------------------------

/**
 * Embed the citizen question and return the top-K matching concepts by
 * cosine similarity to the concept catalogue.
 *
 * Slice E.2 (PR C) calls this from extract-intent.ts BEFORE the SmolLM2
 * generate() call. The returned top-K is injected into the LLM's system
 * prompt as the constraint surface — the LLM picks from k options
 * instead of inferring from the full catalogue gloss.
 *
 * The Gregor lock (cosine < COSINE_THRESHOLD → substring fallback) is
 * the CALLER's responsibility — this function returns the ranked list
 * verbatim. extract-intent.ts implements the threshold check + fallback
 * so the substring path is observable in attempts_log alongside the
 * embedding path.
 *
 * Determinism: MiniLM is deterministic for a given input + seed; the
 * embed function should be too. No randomness here.
 *
 * Performance: ~30 ms cold per question on a mid-tier CPU, sub-10 ms on
 * WebGPU. Concept embeddings are cached after the first call so only
 * the question embedding fires on every subsequent turn.
 */
export async function findTopKConcepts(
  question: string,
  k: number,
  embed: EmbedFn,
): Promise<readonly TopKMatch[]> {
  if (k <= 0) return [];
  if (!conceptEmbeddingsCache) {
    conceptEmbeddingsCache = buildConceptEmbeddings(embed);
    // Reset on error so a retry can re-enter the build path.
    conceptEmbeddingsCache.catch(() => {
      conceptEmbeddingsCache = null;
    });
  }
  const cached = await conceptEmbeddingsCache;
  const questionVectors = await embed([question]);
  if (questionVectors.length !== 1) {
    throw new Error(
      `[yenask] embed(question): expected 1 vector, got ${questionVectors.length}`,
    );
  }
  return rankByCosine(questionVectors[0], cached.entries, k);
}
