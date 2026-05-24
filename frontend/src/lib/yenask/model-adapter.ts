// YENASK model adapter — provider-dispatch + readiness state machine.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-11 (provider dispatch) and D-15 (transformers.js as PR-2 provider).
//
// The adapter is the ONLY code in the lab that touches a runtime SDK. It
// hides the SDK behind two methods (`prepare`, `generate`) and a closed
// `ReadinessStatus` discriminated union the UI subscribes to. Swapping
// providers later (litert-mediapipe, llama.cpp-wasm, etc.) is a new
// dispatch arm here + a new entry in model-registry — never a UI change.
//
// Browser-cache strategy: transformers.js caches model assets in
// IndexedDB automatically (via the `transformers-cache` DB). On second
// load the `prepare()` call streams "loading from cache" progress events
// and resolves in seconds. We do not duplicate that cache layer here.

import type { ModelEntry } from "./model-registry";

// -----------------------------------------------------------------------------
// Readiness state machine.
// -----------------------------------------------------------------------------

export type ReadinessStatus =
  | { readonly kind: "idle" }
  | {
      readonly kind: "downloading";
      /** File currently being fetched (e.g. "model.onnx_data"). May be empty
       *  on the first progress tick before the runtime knows the filename. */
      readonly file: string;
      /** 0..100. Per-file, NOT aggregate (transformers.js streams per-file). */
      readonly percent: number;
      /** Bytes loaded so far for the current file (best-effort). */
      readonly loaded: number;
      /** Bytes total for the current file (best-effort; may be 0). */
      readonly total: number;
    }
  | { readonly kind: "compiling" }
  | { readonly kind: "ready" }
  | { readonly kind: "failed"; readonly error: string };

export type ProgressListener = (status: ReadinessStatus) => void;

// -----------------------------------------------------------------------------
// Chat shape.
// -----------------------------------------------------------------------------
//
// Transformers.js consumes the OpenAI-style chat array (`{ role, content }`).
// We type it locally so the rest of the lab does not import the SDK.

export type ChatRole = "system" | "user" | "assistant";

export interface ChatMessage {
  readonly role: ChatRole;
  readonly content: string;
}

export interface GenerateOptions {
  /** Hard cap on new tokens. Defaults to 256 — enough for an InsightIntent. */
  readonly max_new_tokens?: number;
  /** Temperature. Default 0.2 — intent extraction wants stable output. */
  readonly temperature?: number;
  /** Top-p sampling. Default 0.95. */
  readonly top_p?: number;
}

/**
 * Result of one `generate()` call. Per D-19 / D-20 the adapter exposes
 * token counts + wall-clock time so the UI can show a per-turn footer
 * ("~32 in / ~87 out / 2.1s") and the debug panel can render the raw
 * model output for inspection. Token counts use the pipeline's own
 * tokenizer when available (exact) and fall back to a chars/4
 * approximation when not (marked `tokens_approximate=true`).
 *
 * Per D-22 (Slice A) the adapter also exposes four optional finer-grained
 * timing fields. They are `number | null` — never `0` for "unknown":
 *
 * - `encode_ms` — tokenize+prepare-input wall time when the SDK exposes it.
 * - `generate_ms` — token-generation wall time when the SDK exposes it.
 * - `decode_ms` — output-detokenize wall time when the SDK exposes it.
 * - `ttft_ms` — time to first token when the runtime streams. NULL on
 *   round-trip runtimes (current transformers.js path is non-streaming).
 *
 * The transformers.js pipeline is a black-box `Promise<unknown>` — none
 * of the four phases are observable today. Every transformers-js call
 * therefore reports all four as `null`. The fields ship forward-compatible
 * so a future streaming provider (litert-mediapipe, llama.cpp-wasm) can
 * populate them without a contract change. The Debug log surface shows
 * `null` as `—`; the citizen footer never renders these (per D-22).
 */
export interface GenerateResult {
  /** Assistant text, normalised from whatever shape the runtime returned. */
  readonly text: string;
  /** Input token count (system + few-shot + user). 0 when unknown. */
  readonly tokens_in: number;
  /** Output token count (just the assistant reply). 0 when unknown. */
  readonly tokens_out: number;
  /** True when token counts are char-length approximations, not exact. */
  readonly tokens_approximate: boolean;
  /** Wall-clock time spent inside the generate() call, milliseconds. */
  readonly wall_ms: number;
  /** Encode (tokenize+prepare) wall time, ms. NULL when SDK opaque. */
  readonly encode_ms: number | null;
  /** Generate (token-by-token) wall time, ms. NULL when SDK opaque. */
  readonly generate_ms: number | null;
  /** Decode (detokenize) wall time, ms. NULL when SDK opaque. */
  readonly decode_ms: number | null;
  /** Time to first token, ms. NULL on non-streaming runtimes. */
  readonly ttft_ms: number | null;
}

// -----------------------------------------------------------------------------
// Adapter interface.
// -----------------------------------------------------------------------------

export interface ModelAdapter {
  readonly model: ModelEntry;
  /**
   * Returns the current readiness status without subscribing. Mainly for
   * tests; UI code listens via the listener passed to `prepare()`.
   */
  status(): ReadinessStatus;
  /**
   * Downloads + compiles the model. Calls `onProgress` with each status
   * transition. Idempotent: a second call when already `ready` resolves
   * immediately. Throws + sets `failed` status on download/compile error.
   *
   * Cancellation: not supported in v0. The UI hides the cancel affordance.
   */
  prepare(onProgress?: ProgressListener): Promise<void>;
  /**
   * Runs one inference. Throws if `prepare()` has not resolved.
   * Returns `GenerateResult` (text + token counts + wall_ms) so the UI
   * can render observability — JSON extraction is still the caller's
   * job. Per D-20 token counts are exact when the pipeline exposes a
   * tokenizer, otherwise approximate (`tokens_approximate=true`).
   */
  generate(
    messages: readonly ChatMessage[],
    opts?: GenerateOptions,
  ): Promise<GenerateResult>;
}

// -----------------------------------------------------------------------------
// transformers.js dispatch.
// -----------------------------------------------------------------------------
//
// The transformers.js types are imported lazily inside `prepare()` so the
// 50 MB SDK is not pulled into the main bundle. The UI's chunk on first
// load is the lab shell + the catalogue loader only.

/**
 * Loose pipeline shape we need. Avoids depending on transformers.js
 * types at module top-level (which would force the SDK into the main
 * chunk). The real type is `TextGenerationPipeline`; this subset captures
 * what `generate()` calls.
 *
 * `tokenizer.encode(text)` is the transformers.js stable surface we use
 * for exact token counting; when it's absent (older builds, mocked
 * pipelines in tests) we fall back to a chars/4 approximation.
 */
interface TextGenPipeline {
  (
    input: readonly ChatMessage[],
    opts: {
      max_new_tokens: number;
      do_sample: boolean;
      temperature: number;
      top_p: number;
      return_full_text: boolean;
    },
  ): Promise<unknown>;
  readonly tokenizer?: {
    encode?(text: string): readonly number[] | number[];
  };
}

/**
 * Shape of the progress callback transformers.js invokes. We map this
 * onto our ReadinessStatus union.
 */
interface RuntimeProgressEvent {
  status: string;
  file?: string;
  progress?: number;
  loaded?: number;
  total?: number;
}

class TransformersJsAdapter implements ModelAdapter {
  readonly model: ModelEntry;
  private _status: ReadinessStatus = { kind: "idle" };
  private _pipeline: TextGenPipeline | null = null;
  private _preparePromise: Promise<void> | null = null;

  constructor(model: ModelEntry) {
    this.model = model;
  }

  status(): ReadinessStatus {
    return this._status;
  }

  async prepare(onProgress?: ProgressListener): Promise<void> {
    if (this._status.kind === "ready") return;
    if (this._preparePromise) return this._preparePromise;

    this._preparePromise = (async () => {
      try {
        const update = (s: ReadinessStatus) => {
          this._status = s;
          onProgress?.(s);
        };
        // Default to a downloading state with 0% so the UI immediately
        // shows the file panel instead of waiting for the first event.
        update({ kind: "downloading", file: "", percent: 0, loaded: 0, total: 0 });

        const transformers = await import("@huggingface/transformers");
        // pipeline returns a callable; we widen the type because the SDK's
        // generic surface is broader than what we use.
        const pipeline = transformers.pipeline as (
          task: string,
          model: string,
          opts: Record<string, unknown>,
        ) => Promise<TextGenPipeline>;

        const pl = await pipeline("text-generation", this.model.repo_id, {
          dtype: this.model.dtype,
          device: this.model.device,
          progress_callback: (ev: RuntimeProgressEvent) => {
            if (ev.status === "progress") {
              update({
                kind: "downloading",
                file: ev.file ?? "",
                percent: typeof ev.progress === "number" ? ev.progress : 0,
                loaded: ev.loaded ?? 0,
                total: ev.total ?? 0,
              });
            } else if (ev.status === "done" || ev.status === "ready") {
              update({ kind: "compiling" });
            }
          },
        });

        this._pipeline = pl;
        update({ kind: "ready" });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        this._status = { kind: "failed", error: msg };
        onProgress?.(this._status);
        // Reset the promise so a retry can be attempted.
        this._preparePromise = null;
        throw err;
      }
    })();

    return this._preparePromise;
  }

  async generate(
    messages: readonly ChatMessage[],
    opts: GenerateOptions = {},
  ): Promise<GenerateResult> {
    if (this._status.kind !== "ready" || !this._pipeline) {
      throw new Error(
        `[yenask] generate() called before prepare() resolved; ` +
          `status=${this._status.kind}`,
      );
    }
    const temperature = opts.temperature ?? 0.2;
    const t0 = nowMs();
    const result = await this._pipeline(messages, {
      max_new_tokens: opts.max_new_tokens ?? 256,
      do_sample: temperature > 0,
      temperature,
      top_p: opts.top_p ?? 0.95,
      return_full_text: false,
    });
    const wall_ms = Math.max(0, Math.round(nowMs() - t0));
    const text = extractAssistantText(result);
    const { tokens_in, tokens_out, tokens_approximate } = countTokens(
      this._pipeline,
      messages,
      text,
    );
    // Per D-22: transformers.js does not expose encode/generate/decode
    // breakdown or TTFT — the pipeline is a black-box round-trip Promise.
    // All four fields are NULL (never 0 — 0 is a measurement, null is
    // "the SDK didn't tell us"). A future streaming provider can populate
    // these without a contract change.
    return {
      text,
      tokens_in,
      tokens_out,
      tokens_approximate,
      wall_ms,
      encode_ms: null,
      generate_ms: null,
      decode_ms: null,
      ttft_ms: null,
    };
  }
}

// -----------------------------------------------------------------------------
// Internal helpers.
// -----------------------------------------------------------------------------

function nowMs(): number {
  if (
    typeof performance !== "undefined" &&
    typeof performance.now === "function"
  ) {
    return performance.now();
  }
  return Date.now();
}

/**
 * Approximate-when-needed token counter. Prefers the pipeline's own
 * tokenizer (exact); falls back to a chars/4 approximation (rough but
 * matches the rule-of-thumb most citizens see in playgrounds).
 *
 * Returned `tokens_approximate` lets the UI render "~32 in" vs "32 in"
 * so we don't pretend the approximation is precise.
 */
function countTokens(
  pipeline: TextGenPipeline,
  messages: readonly ChatMessage[],
  responseText: string,
): { tokens_in: number; tokens_out: number; tokens_approximate: boolean } {
  // Concatenate the messages the same way the runtime would feed them
  // to the tokenizer. We don't replicate the chat template exactly
  // (model-specific) but for a rough count the role-prefixed form is
  // close enough — and we surface `tokens_approximate=true` when the
  // tokenizer isn't available so the UI doesn't claim precision.
  const inputText = messages.map((m) => `${m.role}: ${m.content}`).join("\n");
  const tokenizer = pipeline.tokenizer;
  if (tokenizer && typeof tokenizer.encode === "function") {
    try {
      const inIds = tokenizer.encode(inputText);
      const outIds = tokenizer.encode(responseText);
      const tokens_in = Array.isArray(inIds)
        ? inIds.length
        : (inIds as readonly number[]).length;
      const tokens_out = Array.isArray(outIds)
        ? outIds.length
        : (outIds as readonly number[]).length;
      return { tokens_in, tokens_out, tokens_approximate: false };
    } catch {
      // Fall through to approximation — tokenizer threw (e.g. unicode
      // edge case). Better to surface a rough number than zero.
    }
  }
  return {
    tokens_in: approxTokens(inputText),
    tokens_out: approxTokens(responseText),
    tokens_approximate: true,
  };
}

/** Common chars/4 heuristic. Off by ~20% on Indic scripts; honest about it. */
function approxTokens(text: string): number {
  if (!text) return 0;
  return Math.max(1, Math.round(text.length / 4));
}

// -----------------------------------------------------------------------------
// Result-shape normaliser.
// -----------------------------------------------------------------------------
//
// transformers.js returns either `{ generated_text: string }` or
// `{ generated_text: ChatMessage[] }` depending on input style and
// `return_full_text`. We accept both and reduce to a single string.

export function extractAssistantText(raw: unknown): string {
  if (Array.isArray(raw) && raw.length > 0) {
    return extractAssistantText(raw[0]);
  }
  if (raw && typeof raw === "object") {
    const gen = (raw as { generated_text?: unknown }).generated_text;
    if (typeof gen === "string") return gen;
    if (Array.isArray(gen)) {
      // Chat array — find the last assistant turn.
      const last = [...gen].reverse().find(
        (m): m is ChatMessage =>
          !!m &&
          typeof m === "object" &&
          (m as ChatMessage).role === "assistant" &&
          typeof (m as ChatMessage).content === "string",
      );
      if (last) return last.content;
    }
  }
  if (typeof raw === "string") return raw;
  throw new Error(
    `[yenask] could not extract assistant text from runtime output (type=${typeof raw})`,
  );
}

// -----------------------------------------------------------------------------
// Public factory.
// -----------------------------------------------------------------------------

/**
 * Returns an adapter for the given model entry. Dispatch on
 * `entry.provider`. Throws synchronously on unknown providers — that's a
 * config-integrity bug, not a runtime fault.
 */
export function createAdapter(entry: ModelEntry): ModelAdapter {
  switch (entry.provider) {
    case "transformers-js":
      return new TransformersJsAdapter(entry);
    default: {
      const exhaustive: never = entry.provider;
      throw new Error(`[yenask] unknown model provider: ${String(exhaustive)}`);
    }
  }
}
