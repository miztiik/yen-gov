// Tests for extract-intent.ts.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-17. The model adapter is mocked end-to-end: we hand-feed the raw
// strings the adapter would return and assert the parse + retry contract.

import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  extractJsonObject,
  buildSystemPrompt,
  extractIntent,
  substringFallback,
} from "./extract-intent";
import {
  CONCEPT_CATALOGUE,
  __resetConceptEmbeddingsForTests,
} from "./catalogue-embed";
import type { EmbedFn } from "./catalogue-embed";
import type { SemanticCatalogue } from "./types";
import type {
  ChatMessage,
  GenerateOptions,
  GenerateResult,
  ModelAdapter,
  ReadinessStatus,
} from "./model-adapter";
import type { ModelEntry } from "./model-registry";

// ----- fixtures --------------------------------------------------------------

const CATALOGUE: SemanticCatalogue = {
  tables: [],
  states: [
    { partition_id: "in_s22", eci_code: "S22", display_name: "Tamil Nadu" },
  ],
  election_periods: [
    {
      period_label: "AcGenMay2026",
      display_name: "Tamil Nadu AC General — May 2026",
      state_partition_id: "in_s22",
    },
  ],
  parties: [],
  sources: [],
  manifest: {} as never,
};

const MODEL: ModelEntry = {
  id: "test-model",
  task: "text-generation",
  display_name: "Test",
  params_label: "10M",
  provider: "transformers-js",
  repo_id: "test/repo",
  dtype: "q4f16",
  device: "wasm",
  estimated_download_mb: 1,
  notes: "",
};

/** Build a synthetic GenerateResult around a raw text. */
function asResult(text: string): GenerateResult {
  return {
    text,
    tokens_in: Math.max(1, Math.round(text.length / 4)),
    tokens_out: Math.max(1, Math.round(text.length / 4)),
    tokens_approximate: true,
    wall_ms: 1,
    // D-22 (Slice A): transformers-js provider returns null for the
    // four finer-grained phase timings. Tests faithfully mirror the
    // shape so plumbing assertions remain meaningful.
    encode_ms: null,
    generate_ms: null,
    decode_ms: null,
    ttft_ms: null,
  };
}

function fakeAdapter(
  responses: readonly string[],
): { adapter: ModelAdapter; calls: ChatMessage[][] } {
  const calls: ChatMessage[][] = [];
  let i = 0;
  const status: ReadinessStatus = { kind: "ready" };
  const adapter: ModelAdapter = {
    model: MODEL,
    status: () => status,
    prepare: async () => undefined,
    generate: async (
      messages: readonly ChatMessage[],
      _opts?: GenerateOptions,
    ): Promise<GenerateResult> => {
      calls.push([...messages]);
      if (i >= responses.length) {
        throw new Error("fakeAdapter exhausted");
      }
      return asResult(responses[i++]!);
    },
  };
  return { adapter, calls };
}

// ----- extractJsonObject -----------------------------------------------------

describe("extractJsonObject", () => {
  it("parses a bare JSON object", () => {
    expect(extractJsonObject('{"a":1}')).toEqual({ a: 1 });
  });

  it("strips ```json fences", () => {
    expect(extractJsonObject('```json\n{"a":2}\n```')).toEqual({ a: 2 });
  });

  it("ignores prose before and after the object", () => {
    expect(
      extractJsonObject('Sure! Here you go: {"a":3} — hope that helps.'),
    ).toEqual({ a: 3 });
  });

  it("handles nested objects + escaped strings", () => {
    expect(
      extractJsonObject('text {"a":{"b":"he said \\"hi\\""}} done'),
    ).toEqual({ a: { b: 'he said "hi"' } });
  });

  it("throws when no { is present", () => {
    expect(() => extractJsonObject("nothing useful")).toThrow(
      /no JSON object/,
    );
  });

  it("throws on unbalanced braces", () => {
    expect(() => extractJsonObject('{"a":1')).toThrow(/unbalanced/);
  });
});

// ----- buildSystemPrompt -----------------------------------------------------

describe("buildSystemPrompt", () => {
  it("includes all four concept ids", () => {
    const p = buildSystemPrompt(CATALOGUE);
    for (const id of [
      "party_totals",
      "closest_contests",
      "constituency_result",
      "turnout_extremes",
    ]) {
      expect(p).toContain(id);
    }
  });

  it("includes the catalogue states", () => {
    const p = buildSystemPrompt(CATALOGUE);
    expect(p).toContain("in_s22");
    expect(p).toContain("Tamil Nadu");
  });

  it("includes the catalogue election periods", () => {
    const p = buildSystemPrompt(CATALOGUE);
    expect(p).toContain("AcGenMay2026");
  });
});

// ----- extractIntent ---------------------------------------------------------

describe("extractIntent", () => {
  const VALID_RAW = JSON.stringify({
    version: "insight.intent.v0",
    question: "Who won TN 2026?",
    concept_id: "party_totals",
    filters: {
      state_partition_id: "in_s22",
      period_label: "AcGenMay2026",
    },
    reasoning: "Seat totals for a state event.",
  });

  it("returns ok on a valid first attempt", async () => {
    const { adapter, calls } = fakeAdapter([VALID_RAW]);
    const r = await extractIntent("Who won TN 2026?", CATALOGUE, adapter);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.intent.concept_id).toBe("party_totals");
      expect(r.intent.filters.state_partition_id).toBe("in_s22");
      expect(r.diagnostics.attempts).toBe(1);
    }
    // 1 call = system + few-shot + user (single attempt).
    expect(calls.length).toBe(1);
  });

  it("retries once on invalid first attempt, succeeds on the second", async () => {
    const { adapter, calls } = fakeAdapter(["not json at all", VALID_RAW]);
    const r = await extractIntent("Who won TN 2026?", CATALOGUE, adapter);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.diagnostics.attempts).toBe(2);
    expect(calls.length).toBe(2);
    // The second call MUST include a "previous output failed" hint.
    const lastTurn = calls[1]!.at(-1)!;
    expect(lastTurn.role).toBe("user");
    expect(lastTurn.content).toMatch(/previous output failed/i);
  });

  it("returns failure after max_retries with last raw output in diagnostics", async () => {
    const { adapter } = fakeAdapter(["junk one", "junk two"]);
    const r = await extractIntent("Q?", CATALOGUE, adapter, { max_retries: 1 });
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.diagnostics.attempts).toBe(2);
      expect(r.diagnostics.last_raw_output).toBe("junk two");
      expect(r.error).toBeTruthy();
    }
  });

  it("returns failure when the JSON parses but fails Zod (bad concept_id)", async () => {
    const bad = JSON.stringify({
      version: "insight.intent.v0",
      question: "Q?",
      concept_id: "not_a_concept",
      filters: {},
    });
    const { adapter } = fakeAdapter([bad, bad]);
    const r = await extractIntent("Q?", CATALOGUE, adapter, { max_retries: 1 });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/concept_id/);
  });

  it("calls generate with temperature 0.1 for stable extraction", async () => {
    const generateSpy = vi.fn<
      (
        messages: readonly ChatMessage[],
        opts?: GenerateOptions,
      ) => Promise<GenerateResult>
    >(async () => asResult(VALID_RAW));
    const adapter: ModelAdapter = {
      model: MODEL,
      status: () => ({ kind: "ready" }),
      prepare: async () => undefined,
      generate: generateSpy,
    };
    await extractIntent("Q?", CATALOGUE, adapter);
    expect(generateSpy).toHaveBeenCalledTimes(1);
    const opts = generateSpy.mock.calls[0]![1];
    expect(opts?.temperature).toBe(0.1);
  });

  it("records per-attempt diagnostics (D-20)", async () => {
    const { adapter } = fakeAdapter(["not json", VALID_RAW]);
    const r = await extractIntent("Q?", CATALOGUE, adapter);
    expect(r.diagnostics.attempts_log.length).toBe(2);
    const [first, second] = r.diagnostics.attempts_log;
    expect(first!.attempt).toBe(1);
    expect(first!.parse_status).toBe("json_error");
    expect(first!.tokens_in).toBeGreaterThan(0);
    expect(first!.tokens_approximate).toBe(true);
    expect(first!.parse_error).toBeTruthy();
    expect(second!.attempt).toBe(2);
    expect(second!.parse_status).toBe("ok");
    expect(second!.parse_error).toBeUndefined();
  });

  it("records generate_error attempts when the adapter throws", async () => {
    const adapter: ModelAdapter = {
      model: MODEL,
      status: () => ({ kind: "ready" }),
      prepare: async () => undefined,
      generate: async () => {
        throw new Error("WebGPU boom");
      },
    };
    const r = await extractIntent("Q?", CATALOGUE, adapter, { max_retries: 0 });
    expect(r.ok).toBe(false);
    expect(r.diagnostics.attempts_log.length).toBe(1);
    const att = r.diagnostics.attempts_log[0]!;
    expect(att.parse_status).toBe("generate_error");
    expect(att.parse_error).toMatch(/WebGPU boom/);
    expect(att.tokens_in).toBe(0);
    expect(att.tokens_out).toBe(0);
    expect(att.raw_output).toBe("");
    // D-22 (Slice A): generate_error attempts MUST set all four phase
    // timings to null — there is no SDK response from which to derive
    // them. Renderer shows em-dash; sum-invariant row is hidden.
    expect(att.encode_ms).toBeNull();
    expect(att.generate_ms).toBeNull();
    expect(att.decode_ms).toBeNull();
    expect(att.ttft_ms).toBeNull();
  });

  // D-22 (Slice A): the four finer-grained phase timings on
  // GenerateResult MUST plumb through to ExtractAttempt verbatim, so
  // the Debug log can render whatever the SDK reported. The current
  // transformers-js adapter always returns null; this test mirrors
  // that AND covers the forward-looking case where a future SDK
  // populates real numbers.
  it("plumbs encode/generate/decode/ttft timings from GenerateResult to ExtractAttempt", async () => {
    // Case 1: nulls (current transformers-js shape)
    const { adapter: nullAdapter } = fakeAdapter([VALID_RAW]);
    const r1 = await extractIntent("Q?", CATALOGUE, nullAdapter);
    expect(r1.diagnostics.attempts_log.length).toBe(1);
    const att1 = r1.diagnostics.attempts_log[0]!;
    expect(att1.encode_ms).toBeNull();
    expect(att1.generate_ms).toBeNull();
    expect(att1.decode_ms).toBeNull();
    expect(att1.ttft_ms).toBeNull();

    // Case 2: populated values (forward-looking — when an SDK reports
    // real phase timings, ExtractAttempt MUST preserve them verbatim).
    const populatedAdapter: ModelAdapter = {
      model: MODEL,
      status: () => ({ kind: "ready" }),
      prepare: async () => undefined,
      generate: async (): Promise<GenerateResult> => ({
        text: VALID_RAW,
        tokens_in: 10,
        tokens_out: 20,
        tokens_approximate: false,
        wall_ms: 1500,
        encode_ms: 80,
        generate_ms: 1300,
        decode_ms: 120,
        ttft_ms: 350,
      }),
    };
    const r2 = await extractIntent("Q?", CATALOGUE, populatedAdapter);
    expect(r2.diagnostics.attempts_log.length).toBe(1);
    const att2 = r2.diagnostics.attempts_log[0]!;
    expect(att2.encode_ms).toBe(80);
    expect(att2.generate_ms).toBe(1300);
    expect(att2.decode_ms).toBe(120);
    expect(att2.ttft_ms).toBe(350);
  });
});

// ----- substringFallback (Slice E.2 / D-32) ----------------------------------

describe("substringFallback", () => {
  it("returns the requested number of concept ids", () => {
    const picks = substringFallback("party seats won", 2);
    expect(picks.length).toBeLessThanOrEqual(2);
    expect(picks.length).toBeGreaterThanOrEqual(1);
    for (const id of picks) {
      expect(CONCEPT_CATALOGUE.map((c) => c.concept_id)).toContain(id);
    }
  });

  it("ranks party_totals first for a 'party seats' question", () => {
    const picks = substringFallback("party seats won by parties", 1);
    expect(picks[0]).toBe("party_totals");
  });

  it("ranks turnout_extremes first for a 'turnout' question", () => {
    const picks = substringFallback("which constituency had highest turnout", 1);
    expect(picks[0]).toBe("turnout_extremes");
  });

  it("returns at least one entry even for an empty / nonsense question", () => {
    const picks = substringFallback("xxx yyy zzz", 2);
    expect(picks.length).toBeGreaterThanOrEqual(1);
  });

  it("returns empty when k <= 0", () => {
    expect(substringFallback("anything", 0)).toEqual([]);
  });
});

// ----- extractIntent + embed (Slice E.2 / D-32) ------------------------------

describe("extractIntent with embed (D-32)", () => {
  // The concept-embedding cache in catalogue-embed.ts is module-level
  // (so production code embeds the 4 passages once per page-load). Reset
  // it between tests so each test's stub embedder gets re-asked for
  // concept vectors instead of inheriting whichever shape ran first.
  beforeEach(() => {
    __resetConceptEmbeddingsForTests();
  });

  /** Count "- " prefixed lines AFTER the "Concepts:" header. */
  function countConceptLines(prompt: string): number {
    const lines = prompt.split("\n");
    const start = lines.indexOf("Concepts:");
    if (start < 0) return 0;
    let count = 0;
    for (let i = start + 1; i < lines.length; i++) {
      const l = lines[i]!;
      if (l.startsWith("- ")) count += 1;
      else if (l.trim() === "") break;
    }
    return count;
  }

  const VALID_RAW = JSON.stringify({
    version: "insight.intent.v0",
    question: "Who won TN 2026?",
    concept_id: "party_totals",
    filters: {
      state_partition_id: "in_s22",
      period_label: "AcGenMay2026",
    },
    reasoning: "Seat totals for a state event.",
  });

  /**
   * Stub embedder returning fixed vectors. The first vector (for the
   * question) is engineered to be ALIGNED with the second vector (the
   * first concept passage) so cosine ~ 1.0 — comfortably above the
   * 0.6 threshold.
   */
  function highCosineEmbedder(): EmbedFn {
    let call = 0;
    return async (texts: readonly string[]) => {
      call += 1;
      // Concept-embedding precompute pass: one vector per CONCEPT_CATALOGUE entry.
      if (call === 1) {
        return CONCEPT_CATALOGUE.map((_, i) => {
          // Concept 0 gets [1,0,0,0,...]; concept 1 gets [0,1,0,0,...]; etc.
          const v = new Array<number>(CONCEPT_CATALOGUE.length).fill(0);
          v[i] = 1;
          return v;
        });
      }
      // Question pass: align with concept 0 → top-1 cosine = 1.0.
      return texts.map(() => {
        const v = new Array<number>(CONCEPT_CATALOGUE.length).fill(0);
        v[0] = 1;
        return v;
      });
    };
  }

  /**
   * Stub embedder where the question's vector is the ZERO vector. The
   * cosine of zero vs anything is 0 (per the catalogue-embed contract,
   * which short-circuits zero-norm to 0.0), which is below the 0.6
   * COSINE_THRESHOLD and triggers the Gregor D-32 substring fallback.
   */
  function lowCosineEmbedder(): EmbedFn {
    let call = 0;
    return async (texts: readonly string[]) => {
      call += 1;
      if (call === 1) {
        // Concept passages: orthogonal unit vectors as before.
        return CONCEPT_CATALOGUE.map((_, i) => {
          const v = new Array<number>(CONCEPT_CATALOGUE.length).fill(0);
          v[i] = 1;
          return v;
        });
      }
      // Question pass: zero vector → cosine = 0 against every concept.
      return texts.map(() =>
        new Array<number>(CONCEPT_CATALOGUE.length).fill(0),
      );
    };
  }

  it("back-compat: when embed is omitted, no top_concepts surfaced", async () => {
    const { adapter } = fakeAdapter([VALID_RAW]);
    const r = await extractIntent("Who won TN 2026?", CATALOGUE, adapter);
    expect(r.ok).toBe(true);
    expect(r.diagnostics.top_concepts).toBeUndefined();
    expect(r.diagnostics.concept_selection).toBe("none");
    expect(r.diagnostics.selected_concept_ids).toBeUndefined();
    expect(r.diagnostics.attempts_log[0]!.embed_ms).toBeNull();
  });

  it("embed path with high cosine: concept_selection='embed', prompt narrowed", async () => {
    const { adapter, calls } = fakeAdapter([VALID_RAW]);
    const r = await extractIntent("Show me party seat totals", CATALOGUE, adapter, {
      embed: highCosineEmbedder(),
      top_k: 2,
    });
    expect(r.ok).toBe(true);
    expect(r.diagnostics.concept_selection).toBe("embed");
    expect(r.diagnostics.top_concepts).toBeDefined();
    expect(r.diagnostics.top_concepts!.length).toBe(2);
    expect(r.diagnostics.top_concepts![0]!.cosine_score).toBeCloseTo(1, 5);
    expect(r.diagnostics.selected_concept_ids!.length).toBe(2);
    // System prompt was narrowed: only the 2 selected concept ids appear
    // in the Concepts: block.
    const systemMsg = calls[0]!.find((m) => m.role === "system")!;
    const conceptLineCount = countConceptLines(systemMsg.content);
    expect(conceptLineCount).toBe(2);
    expect(r.diagnostics.attempts_log[0]!.embed_ms).not.toBeNull();
    expect(r.diagnostics.attempts_log[0]!.embed_ms).toBeGreaterThanOrEqual(0);
  });

  it("embed path with low cosine: concept_selection='substring' (Gregor D-32)", async () => {
    const { adapter } = fakeAdapter([VALID_RAW]);
    const r = await extractIntent("party seats", CATALOGUE, adapter, {
      embed: lowCosineEmbedder(),
      top_k: 2,
    });
    expect(r.ok).toBe(true);
    expect(r.diagnostics.concept_selection).toBe("substring");
    // top_concepts is still surfaced (the embed call succeeded; the
    // cosine just wasn't confident enough).
    expect(r.diagnostics.top_concepts).toBeDefined();
    expect(r.diagnostics.top_concepts![0]!.cosine_score).toBeLessThan(0.6);
    // Substring fallback picked the concept ids; selected_concept_ids
    // came from substringFallback, not from top_concepts.
    expect(r.diagnostics.selected_concept_ids!.length).toBeGreaterThanOrEqual(1);
    expect(r.diagnostics.attempts_log[0]!.embed_ms).not.toBeNull();
  });

  it("embed throws: silently degrades to no narrowing", async () => {
    const { adapter, calls } = fakeAdapter([VALID_RAW]);
    const brokenEmbedder: EmbedFn = async () => {
      throw new Error("WebGPU embeddings boom");
    };
    const r = await extractIntent("party seats", CATALOGUE, adapter, {
      embed: brokenEmbedder,
    });
    expect(r.ok).toBe(true);
    expect(r.diagnostics.concept_selection).toBe("none");
    expect(r.diagnostics.top_concepts).toBeUndefined();
    expect(r.diagnostics.selected_concept_ids).toBeUndefined();
    // System prompt was NOT narrowed: all 4 concepts appear.
    const systemMsg = calls[0]!.find((m) => m.role === "system")!;
    const conceptLineCount = countConceptLines(systemMsg.content);
    expect(conceptLineCount).toBe(4);
    // embed_ms is still recorded even when embedder threw.
    expect(r.diagnostics.attempts_log[0]!.embed_ms).not.toBeNull();
  });

  it("embed_ms mirrors across retries (embedding runs once per question)", async () => {
    const { adapter } = fakeAdapter(["not json", VALID_RAW]);
    const r = await extractIntent("party seats", CATALOGUE, adapter, {
      embed: highCosineEmbedder(),
      top_k: 2,
    });
    expect(r.ok).toBe(true);
    expect(r.diagnostics.attempts_log.length).toBe(2);
    const [first, second] = r.diagnostics.attempts_log;
    expect(first!.embed_ms).toBe(second!.embed_ms);
    expect(first!.embed_ms).not.toBeNull();
  });
});
