// YENASK size-tier helpers — pure functions for picker download UX.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-24 (graduated download friction by size tier) and D-26 (default-model
// upgrade — separately consumed by Slice D-1).
//
// Why a separate module: the picker (Yenask.svelte) was getting an
// inline mess of `if (mb > 1024) ...` branches across THREE concerns
// (tier classification, size formatting, RAM-label formatting, OOM-error
// detection). Extracting them into a pure module makes each concern
// testable in isolation and prevents the picker's reactivity layer
// from accidentally re-deriving tier-classification on every render.
//
// All thresholds are MB-based for parity with `ModelEntry.estimated_*`
// fields. The 1024-MB boundary is the unit-promotion threshold; the
// 500-MB boundary is the medium/small split (chosen so SmolLM2-360M
// at ~273 MB stays "small" — Jony D-24: friction kicks in only when
// the download would genuinely surprise a citizen on /lab/yenask).

/**
 * Tier classification for the model picker's Download button friction.
 *
 *   - `"small"`  (≤ 500 MB)         → plain Download button, no friction
 *   - `"medium"` (501 MB – 1024 MB) → plain Download button + size shown clearly
 *   - `"large"`  (> 1024 MB)        → two-step inline confirm (D-24 Jony)
 *
 * Non-finite / non-positive inputs degrade to `"small"` — defensive
 * default so a malformed registry entry can't accidentally hide its
 * Download button entirely.
 */
export type SizeTier = "small" | "medium" | "large";

const MEDIUM_THRESHOLD_MB = 500;
const LARGE_THRESHOLD_MB = 1024;

export function classifySizeTier(sizeMb: number): SizeTier {
  if (!Number.isFinite(sizeMb) || sizeMb <= 0) return "small";
  if (sizeMb > LARGE_THRESHOLD_MB) return "large";
  if (sizeMb > MEDIUM_THRESHOLD_MB) return "medium";
  return "small";
}

/**
 * Citizen-facing size label. Promotes to GB at the 1024-MB boundary
 * (D-24: "Size unit promotes at 1 GB (one decimal: `~1.4 GB` not
 * `~1400 MB`)"). Sub-MB and non-finite inputs render as an em-dash so
 * the UI never shows `0 MB` or `NaN MB`.
 */
export function formatModelSize(sizeMb: number): string {
  if (!Number.isFinite(sizeMb) || sizeMb <= 0) return "—";
  if (sizeMb >= LARGE_THRESHOLD_MB) {
    return `${(sizeMb / 1024).toFixed(1)} GB`;
  }
  return `${Math.round(sizeMb)} MB`;
}

/**
 * Optional micro-string for the picker: `"Needs ~2.3 GB RAM"`. Returns
 * `null` when no RAM estimate is available — the picker then renders
 * nothing (D-24: "when absent, render nothing"). Same unit-promotion
 * rule as `formatModelSize`.
 */
export function formatRamLabel(ramMb: number | undefined): string | null {
  if (ramMb === undefined || !Number.isFinite(ramMb) || ramMb <= 0) {
    return null;
  }
  if (ramMb >= LARGE_THRESHOLD_MB) {
    return `Needs ~${(ramMb / 1024).toFixed(1)} GB RAM`;
  }
  return `Needs ~${Math.round(ramMb)} MB RAM`;
}

/**
 * OOM-class error detection. Per D-24: "OOM-class failures (error
 * message contains `out of memory`, `OOM`, `allocation`,
 * `WebAssembly.Memory`) render specific copy". Case-insensitive
 * substring match; `null` / empty / non-string inputs return false.
 */
export function isOutOfMemoryError(message: unknown): boolean {
  if (typeof message !== "string" || message.length === 0) return false;
  const m = message.toLowerCase();
  return (
    m.includes("out of memory") ||
    m.includes("oom") ||
    m.includes("allocation") ||
    m.includes("webassembly.memory")
  );
}

/**
 * The OOM-class failure copy. Hoisted as a constant so the picker
 * template and the vitest renderer assertion reference the same
 * source-of-truth string.
 */
export const OOM_FAILURE_COPY =
  "Model too large for this device. Free up RAM or try a smaller model.";
