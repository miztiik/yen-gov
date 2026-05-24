// Tests for catalogue-embed.ts.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-32 (Slice E.1 retrieval-augmented intent extraction) and ADR-0039.
//
// Test strategy:
//   1. Pure math helpers (cosineSimilarity, rankByCosine) — tested with
//      hand-crafted vectors. Deterministic; no network, no model load.
//   2. findTopKConcepts orchestration — tested with a stub EmbedFn that
//      returns a deterministic embedding scheme. The stub maps each known
//      concept passage and matching test question to a one-hot vector
//      pointing at the expected concept index, so cosine = 1 for the right
//      concept and ~0 for the others. This asserts the orchestration
//      (cache, ordering, top-K cap) without depending on MiniLM accuracy.
//   3. Eval-set regression alarm — loops through fixtures/intent-eval.json
//      with the same stub embedder and asserts every fixture's top-1
//      matches its expected concept_id. The alarm exists so adding a new
//      fixture but FORGETTING to update the stub mapping fails the build;
//      Slice E.2 PR-C runs the same fixture against a real MiniLM and
//      asserts ≥80% accuracy (the actual model regression gate).

import { describe, expect, it, beforeEach } from "vitest";
import {
  CONCEPT_CATALOGUE,
  COSINE_THRESHOLD,
  cosineSimilarity,
  rankByCosine,
  findTopKConcepts,
  __resetConceptEmbeddingsForTests,
  type EmbedFn,
} from "./catalogue-embed";
import type { ConceptId } from "./contracts/insight-intent";
import intentEval from "./fixtures/intent-eval.json";
import { substringFallback } from "./extract-intent";

// -----------------------------------------------------------------------------
// Stub embedder
// -----------------------------------------------------------------------------
//
// Returns a one-hot vector keyed by concept_id matching. If a passage starts
// with "<concept_id>:" we read the id directly; otherwise we substring-match
// the passage against each ConceptId's fixture questions. The vector has one
// dimension per concept in CONCEPT_CATALOGUE; the matched concept's index gets
// 1, others get 0.
//
// This is a DETERMINISTIC stand-in for MiniLM — it never produces NaN, never
// touches the network, and never depends on test order. Slice E.2 PR-C swaps
// the stub for a real model adapter and runs the same fixtures.

const CONCEPT_IDS: readonly ConceptId[] = CONCEPT_CATALOGUE.map((e) => e.concept_id);

interface IntentFixture {
  id: string;
  question: string;
  expected_intent: ConceptId;
  notes?: string;
}

const FIXTURE_ROWS: readonly IntentFixture[] = (
  intentEval.fixtures as readonly IntentFixture[]
);

function buildOneHot(matched: ConceptId | null): number[] {
  return CONCEPT_IDS.map((id) => (id === matched ? 1 : 0));
}

function lookupConceptForQuestion(question: string): ConceptId | null {
  for (const row of FIXTURE_ROWS) {
    if (row.question === question) return row.expected_intent;
  }
  return null;
}

function lookupConceptForPassage(passage: string): ConceptId | null {
  // Concept passages start with "<concept_id>:".
  for (const id of CONCEPT_IDS) {
    if (passage.startsWith(`${id}:`)) return id;
  }
  return null;
}

const stubEmbed: EmbedFn = async (texts) => {
  return texts.map((t) => {
    // Try passage-prefix match first (for the concept catalogue).
    const fromPassage = lookupConceptForPassage(t);
    if (fromPassage) return buildOneHot(fromPassage);
    // Fall back to fixture-question match (for eval queries).
    const fromFixture = lookupConceptForQuestion(t);
    return buildOneHot(fromFixture);
  });
};

beforeEach(() => {
  __resetConceptEmbeddingsForTests();
});

// -----------------------------------------------------------------------------
// Pure math helpers
// -----------------------------------------------------------------------------

describe("cosineSimilarity", () => {
  it("returns 1 for parallel unit vectors", () => {
    expect(cosineSimilarity([1, 0, 0], [1, 0, 0])).toBeCloseTo(1, 6);
  });

  it("returns 0 for orthogonal vectors", () => {
    expect(cosineSimilarity([1, 0, 0], [0, 1, 0])).toBeCloseTo(0, 6);
  });

  it("returns -1 for anti-parallel vectors", () => {
    expect(cosineSimilarity([1, 0, 0], [-1, 0, 0])).toBeCloseTo(-1, 6);
  });

  it("returns 0 when either vector is the zero vector (no NaN)", () => {
    expect(cosineSimilarity([0, 0, 0], [1, 2, 3])).toBe(0);
    expect(cosineSimilarity([1, 2, 3], [0, 0, 0])).toBe(0);
  });

  it("is scale-invariant", () => {
    expect(cosineSimilarity([2, 0, 0], [5, 0, 0])).toBeCloseTo(1, 6);
    expect(cosineSimilarity([1, 2, 3], [2, 4, 6])).toBeCloseTo(1, 6);
  });

  it("throws on length mismatch", () => {
    expect(() => cosineSimilarity([1, 0], [1, 0, 0])).toThrow(/length mismatch/);
  });
});

describe("rankByCosine", () => {
  const candidates = [
    { concept_id: "party_totals" as ConceptId, vector: [1, 0, 0, 0] },
    { concept_id: "closest_contests" as ConceptId, vector: [0, 1, 0, 0] },
    { concept_id: "constituency_result" as ConceptId, vector: [0, 0, 1, 0] },
    { concept_id: "turnout_extremes" as ConceptId, vector: [0, 0, 0, 1] },
  ];

  it("returns the top-K matches in descending cosine order", () => {
    const ranked = rankByCosine([1, 0, 0, 0], candidates, 2);
    expect(ranked).toHaveLength(2);
    expect(ranked[0].concept_id).toBe("party_totals");
    expect(ranked[0].cosine_score).toBeCloseTo(1, 6);
    expect(ranked[1].cosine_score).toBeLessThan(ranked[0].cosine_score);
  });

  it("caps k at the candidate count", () => {
    const ranked = rankByCosine([1, 0, 0, 0], candidates, 999);
    expect(ranked).toHaveLength(candidates.length);
  });

  it("returns empty for k <= 0 candidates count", () => {
    expect(rankByCosine([1, 0, 0, 0], candidates, 0)).toHaveLength(0);
  });

  it("handles a partial-match query (cosine ~ 0.7 for diagonal)", () => {
    const ranked = rankByCosine([1, 1, 0, 0], candidates, 4);
    expect(ranked[0].cosine_score).toBeCloseTo(1 / Math.sqrt(2), 6);
    expect(ranked[1].cosine_score).toBeCloseTo(1 / Math.sqrt(2), 6);
    expect(ranked[2].cosine_score).toBeCloseTo(0, 6);
  });
});

// -----------------------------------------------------------------------------
// COSINE_THRESHOLD lock (Gregor D-32)
// -----------------------------------------------------------------------------

describe("COSINE_THRESHOLD", () => {
  it("is the D-32 Gregor-locked value 0.6 (tune in a follow-up PR with evidence)", () => {
    // The threshold lives in code so a casual rebase / refactor can't
    // silently shift the fallback behaviour. ADR-level decision; Slice E.2
    // (PR C) wires the cosine<threshold → substring fallback at the
    // extract-intent seam.
    expect(COSINE_THRESHOLD).toBe(0.6);
  });
});

// -----------------------------------------------------------------------------
// findTopKConcepts orchestration
// -----------------------------------------------------------------------------

describe("findTopKConcepts", () => {
  it("returns the top-1 concept for a canonical fixture question", async () => {
    const result = await findTopKConcepts(
      "Which parties won the most seats in Tamil Nadu 2026?",
      1,
      stubEmbed,
    );
    expect(result).toHaveLength(1);
    expect(result[0].concept_id).toBe("party_totals");
    expect(result[0].cosine_score).toBeCloseTo(1, 6);
  });

  it("returns top-K ordered by cosine descending", async () => {
    const result = await findTopKConcepts(
      "Highest and lowest turnout seats in Bihar",
      3,
      stubEmbed,
    );
    expect(result).toHaveLength(3);
    expect(result[0].concept_id).toBe("turnout_extremes");
    expect(result[0].cosine_score).toBeGreaterThanOrEqual(result[1].cosine_score);
    expect(result[1].cosine_score).toBeGreaterThanOrEqual(result[2].cosine_score);
  });

  it("returns empty for k <= 0", async () => {
    const result = await findTopKConcepts("anything", 0, stubEmbed);
    expect(result).toHaveLength(0);
  });

  it("caches concept embeddings across calls (embed called once for catalogue)", async () => {
    let calls = 0;
    const countingEmbed: EmbedFn = async (texts) => {
      calls += 1;
      return stubEmbed(texts);
    };
    await findTopKConcepts(
      "Which parties won the most seats in Tamil Nadu 2026?",
      1,
      countingEmbed,
    );
    await findTopKConcepts(
      "What were the tightest contests in TN 2026?",
      1,
      countingEmbed,
    );
    // Expected: 1 call for the concept catalogue (cached) + 2 calls for
    // the two question embeddings = 3 total. NOT 4 (would mean the cache
    // was rebuilt for the second question).
    expect(calls).toBe(3);
  });

  it("resets the cache after __resetConceptEmbeddingsForTests so the next call re-builds", async () => {
    let calls = 0;
    const countingEmbed: EmbedFn = async (texts) => {
      calls += 1;
      return stubEmbed(texts);
    };
    await findTopKConcepts(
      "Which parties won the most seats in Tamil Nadu 2026?",
      1,
      countingEmbed,
    );
    __resetConceptEmbeddingsForTests();
    await findTopKConcepts(
      "What were the tightest contests in TN 2026?",
      1,
      countingEmbed,
    );
    // After reset the catalogue is re-embedded: 1 + 1 + 1 + 1 = 4 calls.
    expect(calls).toBe(4);
  });

  it("re-throws and resets on embed failure so a retry can re-enter", async () => {
    let failOnce = true;
    const flakyEmbed: EmbedFn = async (texts) => {
      if (failOnce) {
        failOnce = false;
        throw new Error("[test] simulated embed failure");
      }
      return stubEmbed(texts);
    };
    await expect(
      findTopKConcepts("any question", 1, flakyEmbed),
    ).rejects.toThrow(/simulated embed failure/);
    // Retry should succeed because the cached promise was reset on rejection.
    const result = await findTopKConcepts(
      "Which parties won the most seats in Tamil Nadu 2026?",
      1,
      flakyEmbed,
    );
    expect(result).toHaveLength(1);
  });
});

// -----------------------------------------------------------------------------
// Eval-set regression alarm (Andre + Hamel + Fowler lock — eval as contract)
// -----------------------------------------------------------------------------

describe("intent-eval.json fixture coverage", () => {
  it("has 20 fixtures (5 per concept)", () => {
    expect(FIXTURE_ROWS).toHaveLength(20);
    const byConcept = new Map<ConceptId, number>();
    for (const row of FIXTURE_ROWS) {
      byConcept.set(
        row.expected_intent,
        (byConcept.get(row.expected_intent) ?? 0) + 1,
      );
    }
    expect(byConcept.get("party_totals")).toBe(5);
    expect(byConcept.get("closest_contests")).toBe(5);
    expect(byConcept.get("constituency_result")).toBe(5);
    expect(byConcept.get("turnout_extremes")).toBe(5);
  });

  it("every fixture id is unique", () => {
    const ids = FIXTURE_ROWS.map((r) => r.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every expected_intent is one of the four PR-1 concept ids", () => {
    const allowed = new Set<ConceptId>(CONCEPT_IDS);
    for (const row of FIXTURE_ROWS) {
      expect(allowed.has(row.expected_intent)).toBe(true);
    }
  });

  it(
    "with the deterministic stub embedder, every fixture's top-1 matches expected_intent " +
      "(plumbing-correctness alarm — Slice E.2 PR-C asserts ≥80% with real MiniLM)",
    async () => {
      __resetConceptEmbeddingsForTests();
      const wrong: { id: string; expected: ConceptId; got: ConceptId }[] = [];
      for (const row of FIXTURE_ROWS) {
        const top = await findTopKConcepts(row.question, 1, stubEmbed);
        if (top[0]?.concept_id !== row.expected_intent) {
          wrong.push({
            id: row.id,
            expected: row.expected_intent,
            got: top[0]?.concept_id ?? ("<empty>" as ConceptId),
          });
        }
      }
      expect(wrong, JSON.stringify(wrong, null, 2)).toHaveLength(0);
    },
  );

  // Slice E.2 (PR-C) regression alarm per Andre + Hamel + Fowler lock
  // (ADR-0039 / D-32): "Vitest covers top-1 accuracy regression alarm
  // (≥5pp drop on top_concept_id accuracy fails the gate)". The
  // Gregor-locked substring fallback IS the deterministic ground-truth
  // surface — when the embedder is unavailable or the cosine is below
  // threshold, substringFallback picks the concept. If THAT regresses,
  // the production fallback path silently degrades.
  //
  // Baseline measured 2026-05-24 against 20 fixtures: 19/20 = 95.0%
  // (only `cc-05 "Photo-finish results in Tamil Nadu"` misses, falling
  // into party_totals because of the "results" token vs no "closest" or
  // "narrow" token in the question). The −5pp floor is 90.0% — any
  // regression below that breaks the gate.
  it(
    "substringFallback top-1 accuracy on 20-fixture eval set is ≥90% (5pp tolerance under 95% baseline)",
    () => {
      let correct = 0;
      const wrong: { id: string; expected: ConceptId; got: ConceptId | "<empty>" }[] = [];
      for (const row of FIXTURE_ROWS) {
        const top = substringFallback(row.question, 1);
        const got = top[0] ?? ("<empty>" as const);
        if (got === row.expected_intent) {
          correct++;
        } else {
          wrong.push({ id: row.id, expected: row.expected_intent, got });
        }
      }
      const accuracy = correct / FIXTURE_ROWS.length;
      const message = `\nsubstringFallback baseline: ${correct}/${FIXTURE_ROWS.length} = ${(accuracy * 100).toFixed(1)}%\nwrong:\n${JSON.stringify(wrong, null, 2)}`;
      expect(accuracy, message).toBeGreaterThanOrEqual(0.9);
    },
  );
});
