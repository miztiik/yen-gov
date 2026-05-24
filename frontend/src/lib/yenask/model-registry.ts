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

export interface ModelEntry {
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
   * available, falling back to wasm). The seed entry is pinned to
   * "wasm" because onnxruntime-web's WebGPU backend currently crashes
   * on q4f16 SmolLM2 (`Failed to download data from buffer: Mapping
   * WebGPU buffer failed: Invalid buffer`) on multiple GPUs/drivers.
   * Wasm is slower (~1-2 tok/s vs ~10-15 tok/s on WebGPU) but produces
   * stable output. Future entries can opt back into "webgpu" or
   * "auto" once the upstream bug is fixed. See plan-doc §17 D-19.
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
    display_name: "TinyLlama-1.1B-Chat-v1.0",
    params_label: "1.1B",
    provider: "transformers-js",
    repo_id: "Xenova/TinyLlama-1.1B-Chat-v1.0",
    dtype: "q4",
    device: "wasm",
    estimated_download_mb: 600,
    estimated_ram_mb: 1500,
    notes:
      "Added per D-24 (Slice C registry expansion). Older Xenova-era " +
      "ONNX build — project frozen since 2023; weaker instruction-" +
      "following than SmolLM2 despite ~3× the params (D-26 reason c). " +
      "Included for citizens who explicitly want a 1B-class model on " +
      "a modest device.",
  },
  {
    // Added per D-24. The onnx-community repo publishes q4f16 builds
    // that transformers.js v4.x loads cleanly on the WASM backend.
    id: "qwen2-5-1-5b-instruct",
    display_name: "Qwen2.5-1.5B-Instruct",
    params_label: "1.5B",
    provider: "transformers-js",
    repo_id: "onnx-community/Qwen2.5-1.5B-Instruct",
    dtype: "q4f16",
    device: "wasm",
    estimated_download_mb: 1220,
    estimated_ram_mb: 2300,
    notes:
      "Added per D-24 (Slice C registry expansion). Crosses the >1024 " +
      "MB Large-tier threshold so the picker shows the D-24 two-step " +
      "confirm. Multilingual; strong on Indic prompts per Qwen2.5 card.",
  },
  {
    // Added per D-24. The `-onnx-web` suffix is the canonical
    // onnx-community repo for browser-side Phi-3.5 deployment.
    id: "phi-3-5-mini-instruct",
    display_name: "Phi-3.5-mini-Instruct",
    params_label: "3.8B",
    provider: "transformers-js",
    repo_id: "onnx-community/Phi-3.5-mini-instruct-onnx-web",
    dtype: "q4f16",
    device: "wasm",
    estimated_download_mb: 2320,
    estimated_ram_mb: 4500,
    notes:
      "Added per D-24 (Slice C registry expansion). Largest registry " +
      "entry — D-24 Large-tier two-step confirm applies. May OOM on " +
      "phones / low-RAM laptops; the picker surfaces the D-24 OOM-class " +
      "copy on failure. Strong instruction-following for its tier.",
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
