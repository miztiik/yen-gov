// YENASK intent extractor — prompt + JSON-mode + Zod retry loop.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-17 (prompt design + retry contract).
//
// Pipeline: citizen question + semantic catalogue → system prompt + chat
// → model.generate() → extractJsonObject() → Zod parse → InsightIntent.
//
// On Zod failure: re-prompt ONCE with a brief "your output failed
// validation: <error>" hint and parse again. Two failures = surface the
// last error to the caller; the UI shows the parser error verbatim
// (citizen-debuggable) rather than smoothing it over.
//
// The compiler/executor run AFTER this returns — see compile-intent.ts +
// execute-plan.ts. This file is the model-facing seam only.

import type {
  InsightIntent,
  ConceptId,
} from "./contracts/insight-intent";
import { safeParseInsightIntent } from "./contracts/insight-intent";
import type { SemanticCatalogue } from "./types";
import type { ChatMessage, ModelAdapter } from "./model-adapter";
import {
  CONCEPT_CATALOGUE,
  COSINE_THRESHOLD,
  findTopKConcepts,
  type EmbedFn,
  type TopKMatch,
} from "./catalogue-embed";

// -----------------------------------------------------------------------------
// JSON extraction.
// -----------------------------------------------------------------------------
//
// Small models often wrap the JSON in prose ("Sure! Here's the JSON: { ...
// }") or fence it. We grab the first top-level `{...}` block and parse
// it; if that fails we surface the parse error.

export function extractJsonObject(raw: string): unknown {
  // Strip common fences.
  const stripped = raw
    .replace(/^```(?:json)?/i, "")
    .replace(/```\s*$/, "")
    .trim();
  // Find the first {...} balanced span. We scan once because the model
  // sometimes emits trailing commentary after the JSON object.
  const start = stripped.indexOf("{");
  if (start < 0) {
    throw new Error("no JSON object found in model output");
  }
  let depth = 0;
  let end = -1;
  let inString = false;
  let escape = false;
  for (let i = start; i < stripped.length; i++) {
    const ch = stripped[i];
    if (escape) {
      escape = false;
      continue;
    }
    if (ch === "\\") {
      escape = true;
      continue;
    }
    if (ch === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) {
        end = i;
        break;
      }
    }
  }
  if (end < 0) {
    throw new Error("unbalanced braces in model output");
  }
  const slice = stripped.slice(start, end + 1);
  return JSON.parse(slice);
}

// -----------------------------------------------------------------------------
// Prompt builder.
// -----------------------------------------------------------------------------

const CONCEPT_GLOSS: Record<ConceptId, string> = {
  party_totals:
    "Aggregate seats won + total votes per party across a state's election event.",
  closest_contests:
    "Constituencies in a state's election event with the smallest winner margin.",
  constituency_result:
    "Top-5 candidates + collapsed others + NOTA for one AC in one event.",
  turnout_extremes:
    "Highest and lowest turnout constituencies in a state's election event.",
};

/**
 * Builds the system prompt. The prompt is intentionally TERSE because
 * the seed model (SmolLM2-135M) has a 2048-token context window.
 *
 * The catalogue is included as a compact JSON object listing only the
 * fields the model is allowed to reference. We do NOT include the full
 * tables / parties / sources — only the discriminators the compiler
 * accepts as filter values.
 *
 * Slice E.2 (ADR-0039 / D-32): when `allowedConceptIds` is provided, the
 * "Concepts:" block lists ONLY those ids — the LLM picks from a narrowed
 * set instead of inferring from the full catalogue gloss. `null` / empty
 * means "no narrowing; show all 4 concepts" (pre-Slice-E behaviour).
 */
export function buildSystemPrompt(
  catalogue: SemanticCatalogue,
  allowedConceptIds: readonly ConceptId[] | null = null,
): string {
  const conceptIds: readonly ConceptId[] =
    allowedConceptIds && allowedConceptIds.length > 0
      ? allowedConceptIds
      : (Object.keys(CONCEPT_GLOSS) as ConceptId[]);
  const states = catalogue.states.map((s) => ({
    state_partition_id: s.partition_id,
    display_name: s.display_name,
  }));
  const periods = catalogue.election_periods.map((p) => ({
    period_label: p.period_label,
    state_partition_id: p.state_partition_id,
    display_name: p.display_name,
  }));
  return [
    `You translate citizen questions about Indian election results into a STRICT JSON object called InsightIntent.`,
    ``,
    `Output rules:`,
    `- Output ONE JSON object. No prose, no markdown fences.`,
    `- Use ONLY values from the catalogue below for state_partition_id and period_label.`,
    `- If the question cannot be answered by one of the four concepts, pick the closest one and explain why in "reasoning".`,
    `- "reasoning" is at most one sentence.`,
    ``,
    `Schema:`,
    `{`,
    `  "version": "insight.intent.v0",`,
    `  "question": "<verbatim citizen question>",`,
    `  "concept_id": ${conceptIds.map((id) => `"${id}"`).join(" | ")},`,
    `  "filters": {`,
    `    "state_partition_id"?: "in_<state-code>",`,
    `    "period_label"?: "<event-label>",`,
    `    "ac_no"?: <positive integer>,`,
    `    "party_short_code"?: "<short-code>",`,
    `    "limit"?: <1..100>`,
    `  },`,
    `  "reasoning": "<one sentence>"`,
    `}`,
    ``,
    `Concepts:`,
    ...conceptIds.map((id) => `- ${id}: ${CONCEPT_GLOSS[id]}`),
    ``,
    `Catalogue (only these values are valid):`,
    JSON.stringify({ states, election_periods: periods }),
  ].join("\n");
}

/**
 * One-shot exemplar so the model sees the JSON shape with concrete
 * values. Kept tiny — one example, not a long few-shot block — because
 * SmolLM2-135M's context window is small.
 */
export function buildFewShot(): readonly ChatMessage[] {
  return [
    {
      role: "user",
      content: "Show me seat totals for parties in Tamil Nadu 2026.",
    },
    {
      role: "assistant",
      content: JSON.stringify({
        version: "insight.intent.v0",
        question: "Show me seat totals for parties in Tamil Nadu 2026.",
        concept_id: "party_totals",
        filters: {
          state_partition_id: "in_s22",
          period_label: "AcGenMay2026",
          limit: 10,
        },
        reasoning:
          "Party seat totals for a state event maps directly to party_totals.",
      }),
    },
  ];
}

// -----------------------------------------------------------------------------
// Public entry point.
// -----------------------------------------------------------------------------

export interface ExtractOptions {
  /** Hard upper bound on retries after the first attempt. Default 1. */
  readonly max_retries?: number;
  /**
   * Slice E.2 (ADR-0039 / D-32): optional embedding function. When
   * provided, extractIntent runs `findTopKConcepts(question, top_k, embed)`
   * BEFORE the LLM call and narrows the system prompt's "Concepts:" block
   * to the top-K matches. If the top-1 cosine is below COSINE_THRESHOLD,
   * the substring-match fallback runs instead (Gregor D-32 graceful
   * degradation lock). When omitted, behaviour is unchanged from PR B —
   * the full 4-concept catalogue is shown to the LLM (back-compat).
   */
  readonly embed?: EmbedFn;
  /** Top-K concepts to pass to the LLM. Defaults to 2. Ignored when embed is omitted. */
  readonly top_k?: number;
}

/**
 * Substring fallback for the Gregor D-32 lock — when top-1 cosine is
 * below COSINE_THRESHOLD the embedding shrugged, so we fall back to
 * literal substring matches between the citizen question and each
 * concept's passage. Returns the concepts whose passages contain the
 * MOST tokens from the (lowercased, split-on-non-word) question.
 *
 * This is a tiny in-code retrieval that costs zero ms and is
 * deterministic. It is the safety net under embedding; both paths feed
 * the same `selectedConceptIds` output downstream so the prompt-narrowing
 * happens identically regardless of which path picked the concepts.
 *
 * Returns at most `k` ConceptId values, ranked by token-overlap score
 * descending. Always returns at least one entry (the first catalogue
 * entry) so the LLM is never given an empty concept list.
 */
export function substringFallback(
  question: string,
  k: number,
): readonly ConceptId[] {
  if (k <= 0) return [];
  const qTokens = new Set(
    question
      .toLowerCase()
      .split(/[^\p{L}\p{N}]+/u)
      .filter((t) => t.length >= 3),
  );
  const scored = CONCEPT_CATALOGUE.map((entry) => {
    const passageTokens = entry.passage
      .toLowerCase()
      .split(/[^\p{L}\p{N}]+/u)
      .filter((t) => t.length >= 3);
    let score = 0;
    for (const t of passageTokens) {
      if (qTokens.has(t)) score += 1;
    }
    return { concept_id: entry.concept_id, score };
  });
  scored.sort((a, b) => b.score - a.score);
  const picked = scored.slice(0, k).map((s) => s.concept_id);
  // Safety net: never return an empty list — fall back to first catalogue
  // entry so the LLM always has at least one concept to pick from.
  return picked.length > 0 ? picked : [CONCEPT_CATALOGUE[0].concept_id];
}

/**
 * One model call's observability record. Per D-20 every attempt is
 * captured so the debug panel can render the full trace (prompt size,
 * token in/out, wall time, parse status). When the model itself threw
 * before returning text, `parse_status` is `"generate_error"` and
 * `raw_output` is empty.
 *
 * Per D-22 (Slice A) every attempt also carries four optional
 * finer-grained timing fields mirrored from `GenerateResult`. They are
 * `number | null` — never `0` for "unknown". The transformers-js
 * adapter reports all four as `null`; a future streaming provider may
 * populate them. The Debug log surface renders `null` as `—`.
 */
export interface ExtractAttempt {
  /** 1-based attempt index. */
  readonly attempt: number;
  /** Approximate character count of the prompt fed to the model. */
  readonly prompt_chars: number;
  /** Input token count reported by the adapter (0 if unknown). */
  readonly tokens_in: number;
  /** Output token count reported by the adapter (0 if unknown). */
  readonly tokens_out: number;
  /** True when tokens_* are approximations (chars/4). */
  readonly tokens_approximate: boolean;
  /** Wall-clock time inside the generate() call, milliseconds. */
  readonly wall_ms: number;
  /** Encode (tokenize+prepare) wall time, ms. NULL when SDK opaque. */
  readonly encode_ms: number | null;
  /** Generate (token-by-token) wall time, ms. NULL when SDK opaque. */
  readonly generate_ms: number | null;
  /** Decode (detokenize) wall time, ms. NULL when SDK opaque. */
  readonly decode_ms: number | null;
  /** Time to first token, ms. NULL on non-streaming runtimes. */
  readonly ttft_ms: number | null;
  /**
   * Slice E.2 (D-32): wall time spent embedding the question and ranking
   * concept similarity. NULL when no embedder was provided to extractIntent.
   * On retries the value mirrors the first attempt — we embed once per
   * question, not per attempt.
   */
  readonly embed_ms: number | null;
  /** Raw assistant text on this attempt (empty on generate error). */
  readonly raw_output: string;
  /** Outcome of the parse step for this attempt. */
  readonly parse_status:
    | "ok"
    | "json_error"
    | "zod_error"
    | "generate_error";
  /** Error message when parse_status !== "ok". */
  readonly parse_error?: string;
}

export interface ExtractDiagnostics {
  /** Number of attempts that ran (1 + retries actually used). */
  readonly attempts: number;
  /** Raw model output on the LAST attempt — exposed for debugging. */
  readonly last_raw_output: string;
  /** Per-attempt observability records for the debug panel. */
  readonly attempts_log: readonly ExtractAttempt[];
  /**
   * Slice E.2 (D-32): the top-K matches returned by the embedder, or
   * NULL when extractIntent ran without an `embed` function. When the
   * Gregor fallback fired (top-1 cosine < COSINE_THRESHOLD), the
   * `cosine_score` on each row reflects the EMBEDDED score, not the
   * substring rank — callers detect fallback via `top_concepts[0].cosine_score < COSINE_THRESHOLD`
   * OR via the `fallback_reason` field below.
   */
  readonly top_concepts?: readonly TopKMatch[];
  /**
   * Slice E.2 (D-32): when set, the system prompt was narrowed via the
   * named path. `"embed"` = top-K cosine ranking was good enough.
   * `"substring"` = cosine fallback fired (Gregor D-32 lock). `"none"`
   * (or omitted) = no narrowing happened.
   */
  readonly concept_selection?: "embed" | "substring" | "none";
  /** The concept ids actually passed into the system prompt's narrowed list. */
  readonly selected_concept_ids?: readonly ConceptId[];
}

export interface ExtractSuccess {
  readonly ok: true;
  readonly intent: InsightIntent;
  readonly diagnostics: ExtractDiagnostics;
}

export interface ExtractFailure {
  readonly ok: false;
  readonly error: string;
  readonly diagnostics: ExtractDiagnostics;
}

export type ExtractResult = ExtractSuccess | ExtractFailure;

/**
 * Runs question → intent through the adapter, with one validate-or-retry.
 * Returns a discriminated union; the caller decides how to surface
 * failure to the citizen.
 */
export async function extractIntent(
  question: string,
  catalogue: SemanticCatalogue,
  adapter: ModelAdapter,
  opts: ExtractOptions = {},
): Promise<ExtractResult> {
  const maxRetries = Math.max(0, opts.max_retries ?? 1);
  const topK = Math.max(1, opts.top_k ?? 2);

  // Slice E.2 (D-32) retrieval step. Runs ONCE per question, before any
  // LLM call. When `embed` is omitted, behaviour is unchanged from PR B
  // (full 4-concept catalogue shown to the LLM).
  let topConcepts: readonly TopKMatch[] | undefined;
  let conceptSelection: "embed" | "substring" | "none" = "none";
  let selectedConceptIds: readonly ConceptId[] | null = null;
  let embedMs: number | null = null;
  if (opts.embed) {
    const embedStart =
      typeof performance !== "undefined" ? performance.now() : Date.now();
    try {
      topConcepts = await findTopKConcepts(question, topK, opts.embed);
      const top1 = topConcepts[0];
      if (top1 && top1.cosine_score >= COSINE_THRESHOLD) {
        conceptSelection = "embed";
        selectedConceptIds = topConcepts.map((m) => m.concept_id);
      } else {
        // Gregor D-32 fallback: cosine ranking was not confident enough.
        conceptSelection = "substring";
        selectedConceptIds = substringFallback(question, topK);
      }
    } catch {
      // Embedder threw \u2014 silently degrade to no narrowing rather than
      // failing the whole extraction. The debug panel still records
      // top_concepts=undefined so an operator can see the embed path
      // never produced a ranking.
      conceptSelection = "none";
      selectedConceptIds = null;
      topConcepts = undefined;
    }
    const embedEnd =
      typeof performance !== "undefined" ? performance.now() : Date.now();
    embedMs = Math.max(0, Math.round(embedEnd - embedStart));
  }

  const systemPrompt = buildSystemPrompt(catalogue, selectedConceptIds);
  const fewShot = buildFewShot();
  let lastRaw = "";
  let lastError = "no attempts ran";
  const attempts_log: ExtractAttempt[] = [];

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const messages: ChatMessage[] = [
      { role: "system", content: systemPrompt },
      ...fewShot,
      { role: "user", content: question },
    ];
    if (attempt > 0) {
      messages.push({
        role: "user",
        content:
          `Your previous output failed validation: ${lastError}. ` +
          `Reply with a single valid JSON object that conforms to the schema. ` +
          `Do not add prose.`,
      });
    }
    const prompt_chars = messages.reduce(
      (n, m) => n + m.role.length + 2 + m.content.length,
      0,
    );
    try {
      const gen = await adapter.generate(messages, {
        temperature: 0.1,
        max_new_tokens: 256,
      });
      lastRaw = gen.text;
      try {
        const parsed = extractJsonObject(lastRaw);
        const result = safeParseInsightIntent(parsed);
        if (result.success) {
          attempts_log.push({
            attempt: attempt + 1,
            prompt_chars,
            tokens_in: gen.tokens_in,
            tokens_out: gen.tokens_out,
            tokens_approximate: gen.tokens_approximate,
            wall_ms: gen.wall_ms,
            encode_ms: gen.encode_ms,
            generate_ms: gen.generate_ms,
            decode_ms: gen.decode_ms,
            ttft_ms: gen.ttft_ms,
            embed_ms: embedMs,
            raw_output: lastRaw,
            parse_status: "ok",
          });
          return {
            ok: true,
            intent: result.data,
            diagnostics: {
              attempts: attempt + 1,
              last_raw_output: lastRaw,
              attempts_log,
              top_concepts: topConcepts,
              concept_selection: conceptSelection,
              selected_concept_ids: selectedConceptIds ?? undefined,
            },
          };
        }
        lastError = result.error.issues
          .map((i) => `${i.path.join(".") || "<root>"}: ${i.message}`)
          .join("; ");
        attempts_log.push({
          attempt: attempt + 1,
          prompt_chars,
          tokens_in: gen.tokens_in,
          tokens_out: gen.tokens_out,
          tokens_approximate: gen.tokens_approximate,
          wall_ms: gen.wall_ms,
          encode_ms: gen.encode_ms,
          generate_ms: gen.generate_ms,
          decode_ms: gen.decode_ms,
          ttft_ms: gen.ttft_ms,
          embed_ms: embedMs,
          raw_output: lastRaw,
          parse_status: "zod_error",
          parse_error: lastError,
        });
      } catch (parseErr) {
        lastError =
          parseErr instanceof Error ? parseErr.message : String(parseErr);
        attempts_log.push({
          attempt: attempt + 1,
          prompt_chars,
          tokens_in: gen.tokens_in,
          tokens_out: gen.tokens_out,
          tokens_approximate: gen.tokens_approximate,
          wall_ms: gen.wall_ms,
          encode_ms: gen.encode_ms,
          generate_ms: gen.generate_ms,
          decode_ms: gen.decode_ms,
          ttft_ms: gen.ttft_ms,
          embed_ms: embedMs,
          raw_output: lastRaw,
          parse_status: "json_error",
          parse_error: lastError,
        });
      }
    } catch (err) {
      lastError = err instanceof Error ? err.message : String(err);
      attempts_log.push({
        attempt: attempt + 1,
        prompt_chars,
        tokens_in: 0,
        tokens_out: 0,
        tokens_approximate: true,
        wall_ms: 0,
        encode_ms: null,
        generate_ms: null,
        decode_ms: null,
        ttft_ms: null,
        embed_ms: embedMs,
        raw_output: "",
        parse_status: "generate_error",
        parse_error: lastError,
      });
    }
  }

  return {
    ok: false,
    error: lastError,
    diagnostics: {
      attempts: maxRetries + 1,
      last_raw_output: lastRaw,
      attempts_log,
      top_concepts: topConcepts,
      concept_selection: conceptSelection,
      selected_concept_ids: selectedConceptIds ?? undefined,
    },
  };
}
