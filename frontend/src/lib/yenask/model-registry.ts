// YENASK model registry — config-driven, swappable.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-11 (config-driven registry) and D-15 (PR-2 seed entry + swappability
// contract).
//
// Adding / swapping a model is a PURE config edit — append (or replace) a
// `ModelEntry` here and the lab picks it up. Each entry declares the
// runtime provider, the repo, the quantisation, and the headline numbers
// the UI shows on the Prepare-assistant panel. The adapter dispatches on
// `provider`; new providers (e.g. `litert-mediapipe`) are added when
// genuinely needed, not pre-emptively (rule of three).
//
// The DEFAULT entry is the seed candidate, not a locked choice. Swapping
// the default is one-line change. The choice is intentionally NOT locked
// behind a roundtable — per user direction, the coding work must not
// stall on model-shopping.

export type ModelProvider = "transformers-js";

export type ModelDevice = "webgpu" | "wasm" | "auto";

/**
 * Model task — what the model is FOR.
 *
 * Slice E.1 (ADR-0039) introduces this discriminator so registry entries
 * can declare whether they're text-generation models (the SmolLM2
 * extractor + future LLMs) or embedding models (MiniLM-L6-v2 for catalogue
 * retrieval). The model-adapter dispatches on `task` in PR C — text-gen
 * entries get a `pipeline("text-generation", ...)`, embedding entries get
 * a `pipeline("feature-extraction", ...)`. Adding a third task (e.g.
 * `"reranker"`) = new arm here + new adapter dispatch arm + new helper.
 *
 * The discriminated-union shape is intentional. Both variants reuse the
 * ModelEntryBase fields (id, display_name, dtype, device, etc.); only
 * the task tag distinguishes them at the type level. This stops the
 * extract-intent.ts code from accidentally `generate()`-ing on an
 * embeddings entry — a compile error fires before the runtime explodes.
 */
export type ModelTask = "text-generation" | "embeddings";

/**
 * Fields shared by every registry entry regardless of task. Kept private
 * to the module — consumers always see the discriminated `ModelEntry`.
 */
interface ModelEntryBase {
  /** Stable kebab-case slug. Persisted in localStorage as the user pick. */
  readonly id: string;
  /** Citizen-facing model name shown in the picker. */
  readonly display_name: string;
  /** Parameter-count label (e.g. "135M", "0.5B"). Used in the UI panel. */
  readonly params_label: string;
  /** Which runtime adapter handles this entry. */
  readonly provider: ModelProvider;
  /** HuggingFace repo id (or equivalent for other providers). */
  readonly repo_id: string;
  /**
   * Quantisation / precision tag passed to the runtime. For
   * transformers.js, one of: "fp32" | "fp16" | "q8" | "int8" | "uint8"
   * | "q4" | "bnb4" | "q4f16". A wrong dtype is a runtime failure, not a
   * compile error — keep entries narrow until verified.
   */
  readonly dtype: string;
  /**
   * Target device. "auto" lets the runtime pick (usually webgpu when
   * available, falling back to wasm).
   *
   * Per-entry policy:
   * - SmolLM2-360M / SmolLM2-135M are pinned to "wasm" because
   *   onnxruntime-web's WebGPU backend reproducibly crashes on q4f16
   *   SmolLM2 (`Failed to download data from buffer: Mapping WebGPU
   *   buffer failed: Invalid buffer`) on multiple GPUs/drivers. Wasm
   *   is slower (~1-2 tok/s vs ~10-15 tok/s on WebGPU) but stable.
   *   See plan-doc §17 D-19.
   * - TinyLlama / Qwen2.5-1.5B / Phi-3.5-mini are set to "auto". The
   *   transformers.js-examples gallery ships WebGPU demos for Phi-3.5
   *   and Qwen builds; we let the runtime pick WebGPU when supported
   *   (10× speedup) and fall back to wasm on failure. The earlier
   *   blanket "wasm" pin on these three was inherited copy-paste
   *   discipline, not a verified bug — corrected per user direction
   *   2026-05-24.
   * - Re-pin to "wasm" on any entry where attempts_log records a
   *   reproducible WebGPU runtime failure; add the symptom to the
   *   `notes` field so the next reviewer doesn't undo it.
   */
  readonly device: ModelDevice;
  /**
   * Download size estimate in megabytes. Approximate; only used to set
   * expectations on the Prepare-assistant panel. Re-measure if you swap
   * dtypes. Per D-24 (graduated friction): values >1024 MB trigger the
   * Large-tier two-step confirm in the picker; the picker promotes the
   * unit to GB at the same boundary (`~1.4 GB` not `~1400 MB`).
   */
  readonly estimated_download_mb: number;
  /**
   * Optional peak-RAM estimate in megabytes for the model + KV cache +
   * runtime overhead. Per D-24: "when present, the row renders a
   * second-line micro-string `Needs ~<N> GB RAM`; when absent, render
   * nothing". Re-measure if you swap dtypes or device. Citizens use this
   * to avoid OOM-class failures; the picker uses it for nothing else
   * today, but a future "this is too big for your device" check could
   * read it.
   */
  readonly estimated_ram_mb?: number;
  /** Free-text operator note. */
  readonly notes: string;
}

/**
 * Text-generation model entry — the LLM doing intent extraction or chat.
 * All five Slice A–D registry entries (SmolLM2-360M, SmolLM2-135M,
 * TinyLlama, Qwen2.5-1.5B, Phi-3.5-mini) are this variant.
 */
export interface TextGenerationModelEntry extends ModelEntryBase {
  readonly task: "text-generation";
}

/**
 * Embedding model entry — produces a fixed-dim vector per input string.
 * Slice E.1 (ADR-0039) adds the first such entry, MiniLM-L6-v2, for
 * catalogue retrieval. The model-adapter dispatch in PR C loads these
 * via the `"feature-extraction"` pipeline (transformers.js convention).
 *
 * `embedding_dim` is declared explicitly so callers can size buffers
 * before the first generate() call; matches the model's output dim.
 */
export interface EmbeddingsModelEntry extends ModelEntryBase {
  readonly task: "embeddings";
  /** Output vector dimensionality (e.g. 384 for MiniLM-L6-v2). */
  readonly embedding_dim: number;
}

/**
 * Discriminated union over `task`. Consumers narrow with a type guard:
 *
 *   if (entry.task === "embeddings") { entry.embedding_dim ... }
 *
 * which makes it a compile error to call generate() on an embeddings
 * entry, or to read `embedding_dim` off a text-gen entry.
 */
export type ModelEntry = TextGenerationModelEntry | EmbeddingsModelEntry;

/**
 * Seed registry. Order matters: the first entry whose id matches
 * DEFAULT_MODEL_ID becomes the default.
 *
 * To swap the seed model: change DEFAULT_MODEL_ID below (or just edit the
 * first entry's fields in place). To add an alternative: append a new
 * entry; users select it via the picker (PR-2 UI does not expose a picker
 * yet but the data model is ready for it).
 *
 * The current seed entry is SmolLM2-135M-Instruct because it's the
 * smallest mainstream instruction-tuned model with an ONNX build that
 * transformers.js can load. The user explicitly directed "smallest viable
 * model first" — see plan-doc §17 D-10.
 */
export const MODEL_REGISTRY: readonly ModelEntry[] = [
  {
    // Default per D-26 (Slice D-1) — SmolLM2-360M is the strict
    // upgrade Max scouted: ~3× better instruction-following than
    // SmolLM2-135M at only ~2.3× the download size, same Apache-2.0
    // licence + same family (drop-in tokenizer/chat-template), same
    // wasm-pin (D-19 WebGPU bug applies to all SmolLM2 q4f16 builds).
    // Stays under the D-24 Small-tier 500-MB threshold so no
    // download friction for the default citizen flow.
    id: "smollm2-360m-instruct",
    task: "text-generation",
    display_name: "SmolLM2-360M-Instruct",
    params_label: "360M",
    provider: "transformers-js",
    repo_id: "HuggingFaceTB/SmolLM2-360M-Instruct",
    dtype: "q4f16",
    device: "wasm",
    estimated_download_mb: 273,
    estimated_ram_mb: 520,
    notes:
      "Default per D-26 (Slice D-1) — strict upgrade from 135M: ~3× " +
      "better instruction-following per Max's scouting, same Apache-2.0 " +
      "licence + family, ~2.3× the download size, stays Small-tier so " +
      "no D-24 friction. Wasm-pinned per D-19 (WebGPU crashes on q4f16 " +
      "SmolLM2).",
  },
  {
    id: "smollm2-135m-instruct",
    task: "text-generation",
    display_name: "SmolLM2-135M-Instruct",
    params_label: "135M",
    provider: "transformers-js",
    repo_id: "HuggingFaceTB/SmolLM2-135M-Instruct",
    dtype: "q4f16",
    device: "wasm",
    // Corrected 88 → 118 per D-26 (Max). The 88 figure pre-dated the
    // HuggingFaceTB GQA-conversion + tokenizer-shard restructure; the
    // q4f16 ONNX directory sum is now ~118 MB on current main.
    estimated_download_mb: 118,
    estimated_ram_mb: 280,
    notes:
      "Former seed per D-10. Retained in registry as the smallest " +
      "option for very-low-RAM devices; D-26 promoted 360M to default " +
      "because the 135M's instruction-following was the bottleneck on " +
      "free-text extraction. Device pinned to \"wasm\" per D-19 — " +
      "WebGPU backend in onnxruntime-web currently crashes on q4f16 " +
      "SmolLM2 with `Invalid buffer` mapping errors; wasm is slower " +
      "but stable. Size corrected 88 → 118 MB per D-26.",
  },
  {
    // Added per D-24 (Slice C registry expansion). TinyLlama is in the
    // registry as an alternative option but is NOT a default-flip
    // candidate (D-26 reason c: project frozen since 2023, weaker
    // instruction-following). Citizens who explicitly pick it get it.
    id: "tinyllama-1-1b-chat",
    task: "text-generation",
    display_name: "TinyLlama-1.1B-Chat-v1.0",
    params_label: "1.1B",
    provider: "transformers-js",
    repo_id: "Xenova/TinyLlama-1.1B-Chat-v1.0",
    dtype: "q4",
    device: "auto",
    estimated_download_mb: 600,
    estimated_ram_mb: 1500,
    notes:
      "Added per D-24 (Slice C registry expansion). Older Xenova-era " +
      "ONNX build — project frozen since 2023; weaker instruction-" +
      "following than SmolLM2 despite ~3× the params (D-26 reason c). " +
      "Included for citizens who explicitly want a 1B-class model on " +
      "a modest device. Device \"auto\" (not the D-19 wasm pin): the " +
      "q4 build is a different quantisation from SmolLM2 q4f16 and " +
      "the WebGPU crash is q4f16-SmolLM2 specific — let the runtime " +
      "pick WebGPU when supported (corrected 2026-05-24).",
  },
  {
    // Added per D-24. The onnx-community repo publishes q4f16 builds
    // that transformers.js v4.x loads cleanly on the WASM backend.
    id: "qwen2-5-1-5b-instruct",
    task: "text-generation",
    display_name: "Qwen2.5-1.5B-Instruct",
    params_label: "1.5B",
    provider: "transformers-js",
    repo_id: "onnx-community/Qwen2.5-1.5B-Instruct",
    dtype: "q4f16",
    device: "auto",
    estimated_download_mb: 1220,
    estimated_ram_mb: 2300,
    notes:
      "Added per D-24 (Slice C registry expansion). Crosses the >1024 " +
      "MB Large-tier threshold so the picker shows the D-24 two-step " +
      "confirm. Multilingual; strong on Indic prompts per Qwen2.5 card. " +
      "Device \"auto\" (not the D-19 wasm pin): Qwen2.5 has shipped " +
      "WebGPU demos in the transformers.js-examples gallery; the " +
      "q4f16-SmolLM2 WebGPU crash does not generalise to other model " +
      "families. Let the runtime pick WebGPU when supported (corrected " +
      "2026-05-24).",
  },
  {
    // Added per D-24. The `-onnx-web` suffix is the canonical
    // onnx-community repo for browser-side Phi-3.5 deployment.
    id: "phi-3-5-mini-instruct",
    task: "text-generation",
    display_name: "Phi-3.5-mini-Instruct",
    params_label: "3.8B",
    provider: "transformers-js",
    repo_id: "onnx-community/Phi-3.5-mini-instruct-onnx-web",
    dtype: "q4f16",
    device: "auto",
    estimated_download_mb: 2320,
    estimated_ram_mb: 4500,
    notes:
      "Added per D-24 (Slice C registry expansion). Largest registry " +
      "entry — D-24 Large-tier two-step confirm applies. May OOM on " +
      "phones / low-RAM laptops; the picker surfaces the D-24 OOM-class " +
      "copy on failure. Strong instruction-following for its tier. " +
      "Device \"auto\" (not the D-19 wasm pin): the upstream repo is " +
      "literally named `-onnx-web` and Phi-3.5 ships in the " +
      "transformers.js-examples WebGPU gallery. The q4f16-SmolLM2 " +
      "WebGPU crash does not generalise to Phi-3.5. Let the runtime " +
      "pick WebGPU when supported (corrected 2026-05-24).",
  },
  {
    // Slice E.1 (ADR-0039): first embeddings entry. Sentence-transformers'
    // all-MiniLM-L6-v2 — the de-facto small embedding model. 23 MB q8,
    // 384-dim, Apache-2.0, WebGPU-capable, ~30 ms cold per query on a
    // mid-tier laptop CPU and sub-10 ms on WebGPU. Loaded ONCE per lab
    // session via the model-adapter "feature-extraction" dispatch
    // (added in Slice E.2 / PR C). Catalogue concept embeddings are
    // pre-computed at first use in catalogue-embed.ts; per-question
    // embedding fires inside extract-intent.ts before the SmolLM2 call
    // so the LLM receives a top-K constraint list instead of the full
    // catalogue gloss.
    //
    // The entry is NOT a default-flip candidate — it does not produce
    // text. The picker UI in Slice C/D ignores entries where
    // `task !== "text-generation"`; the embeddings model is loaded
    // implicitly by the lab pipeline, not picked by the citizen.
    //
    // Size is well under the D-24 Small-tier 500-MB threshold so no
    // friction copy applies; size-tier helpers are text-gen-shaped
    // anyway and don't run on embeddings entries.
    id: "minilm-l6-v2-embeddings",
    task: "embeddings",
    display_name: "all-MiniLM-L6-v2",
    params_label: "22M",
    provider: "transformers-js",
    repo_id: "Xenova/all-MiniLM-L6-v2",
    dtype: "q8",
    // "auto" — no analogue of the D-19 q4f16-SmolLM2 WebGPU crash on
    // MiniLM. The Xenova MiniLM build is the canonical transformers.js
    // example for browser embeddings; WebGPU works on supported
    // browsers and the wasm fallback is fast enough for ~130 catalogue
    // entries + 1 query per turn.
    device: "auto",
    estimated_download_mb: 23,
    estimated_ram_mb: 90,
    embedding_dim: 384,
    notes:
      "Added per Slice E.1 (ADR-0039) — catalogue retrieval for the " +
      "LLM-OS shape. Pre-computes concept embeddings at first " +
      "findTopKConcepts() call, then runs once per citizen question to " +
      "narrow the LLM's constraint surface. Sentence-transformers' " +
      "all-MiniLM-L6-v2 (Apache-2.0, 384-dim, 22M params). The model " +
      "is loaded implicitly by the pipeline, NOT selected by the " +
      "citizen via the picker — entries where task !== " +
      "\"text-generation\" are filtered out of the picker UI.",
  },
] as const;

/**
 * The model the lab loads when the user clicks "Prepare assistant".
 * Change this string to swap the default; no other code edit needed.
 *
 * Per D-26 (Slice D-1, 2026-05-24): flipped from `smollm2-135m-instruct`
 * to `smollm2-360m-instruct` — strict upgrade: ~3× better instruction
 * following at ~2.3× the download size, same Apache-2.0 family, stays
 * Small-tier so no D-24 friction. The 135M entry is retained in the
 * registry as a low-RAM-device fallback.
 */
export const DEFAULT_MODEL_ID = "smollm2-360m-instruct";

/**
 * Look up a model entry by id. Returns undefined if not found — callers
 * (e.g. UI restoring a localStorage pick) decide whether to fall back to
 * the default or surface an error.
 */
export function getModelById(id: string): ModelEntry | undefined {
  return MODEL_REGISTRY.find((m) => m.id === id);
}

/**
 * Returns the default model entry. Throws if DEFAULT_MODEL_ID does not
 * match any entry — that's a config-integrity bug, not a runtime fault.
 */
export function getDefaultModel(): ModelEntry {
  const entry = getModelById(DEFAULT_MODEL_ID);
  if (!entry) {
    throw new Error(
      `[yenask] DEFAULT_MODEL_ID="${DEFAULT_MODEL_ID}" not found in MODEL_REGISTRY`,
    );
  }
  return entry;
}

/**
 * Returns only the text-generation entries — what the picker UI should
 * show as user-selectable choices. Embedding-model entries (Slice E.1)
 * are loaded implicitly by the lab pipeline and never listed in the
 * picker; surfacing them would invite "I picked the wrong model" bug
 * reports from citizens who chose MiniLM expecting it to chat.
 *
 * Narrowed by the discriminated-union tag so callers get
 * `TextGenerationModelEntry[]` (not `ModelEntry[]`) — the extra type
 * precision lets the picker code reason about text-gen-only fields
 * without re-checking the tag.
 */
export function listTextGenerationModels(): readonly TextGenerationModelEntry[] {
  return MODEL_REGISTRY.filter(
    (m): m is TextGenerationModelEntry => m.task === "text-generation",
  );
}

/**
 * Returns only the embeddings entries. Catalogue-embed.ts calls this
 * to pick the embedding model (today there's exactly one — MiniLM-L6-v2;
 * a future PR might add multilingual-e5-small for Indic queries).
 *
 * Returns `EmbeddingsModelEntry[]` so callers can read `embedding_dim`
 * without narrowing.
 */
export function listEmbeddingsModels(): readonly EmbeddingsModelEntry[] {
  return MODEL_REGISTRY.filter(
    (m): m is EmbeddingsModelEntry => m.task === "embeddings",
  );
}
