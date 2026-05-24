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
 */
export function buildSystemPrompt(catalogue: SemanticCatalogue): string {
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
    `  "concept_id": "party_totals" | "closest_contests" | "constituency_result" | "turnout_extremes",`,
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
    ...(Object.entries(CONCEPT_GLOSS) as [ConceptId, string][]).map(
      ([id, gloss]) => `- ${id}: ${gloss}`,
    ),
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
  const systemPrompt = buildSystemPrompt(catalogue);
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
    },
  };
}
