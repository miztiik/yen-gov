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
   * available, falling back to wasm). For the seed entry we lock to
   * "auto" so first-run users on hardware without WebGPU still work.
   */
  readonly device: ModelDevice;
  /**
   * Download size estimate in megabytes. Approximate; only used to set
   * expectations on the Prepare-assistant panel. Re-measure if you swap
   * dtypes.
   */
  readonly estimated_download_mb: number;
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
    id: "smollm2-135m-instruct",
    display_name: "SmolLM2-135M-Instruct",
    params_label: "135M",
    provider: "transformers-js",
    repo_id: "HuggingFaceTB/SmolLM2-135M-Instruct",
    dtype: "q4f16",
    device: "auto",
    estimated_download_mb: 88,
    notes:
      "Seed candidate per D-10 (smallest viable first). Swap by editing " +
      "DEFAULT_MODEL_ID or this entry. q4f16 ONNX is the smallest variant " +
      "the HuggingFaceTB repo publishes; falls back to wasm when WebGPU " +
      "is unavailable.",
  },
] as const;

/**
 * The model the lab loads when the user clicks "Prepare assistant".
 * Change this string to swap the default; no other code edit needed.
 */
export const DEFAULT_MODEL_ID = "smollm2-135m-instruct";

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
