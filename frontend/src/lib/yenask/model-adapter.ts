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
   * Returns the raw assistant text — JSON extraction is the caller's job.
   */
  generate(messages: readonly ChatMessage[], opts?: GenerateOptions): Promise<string>;
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
  ): Promise<string> {
    if (this._status.kind !== "ready" || !this._pipeline) {
      throw new Error(
        `[yenask] generate() called before prepare() resolved; ` +
          `status=${this._status.kind}`,
      );
    }
    const temperature = opts.temperature ?? 0.2;
    const result = await this._pipeline(messages, {
      max_new_tokens: opts.max_new_tokens ?? 256,
      do_sample: temperature > 0,
      temperature,
      top_p: opts.top_p ?? 0.95,
      return_full_text: false,
    });
    return extractAssistantText(result);
  }
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
