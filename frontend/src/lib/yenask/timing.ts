// YENASK Slice A — per-attempt timing helpers.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-22 (Jony AMEND verdict on Slice A). The Debug log table renders four
// optional finer-grained timing fields (`encode_ms`, `generate_ms`,
// `decode_ms`, `ttft_ms`) per attempt. When the SDK populates the first
// three, this module computes the sum-invariant delta vs `wall_ms` so
// operators can see when measurement is partial.
//
// Pure functions only. No I/O. No imports from svelte / vitest / runtime.

/**
 * Per D-22: when encode + generate + decode are all measured for an
 * attempt, the sum vs `wall_ms` exposes how much wall time was NOT
 * captured by SDK-reported phases. The Debug log renders an
 * `untracked: <N>ms` row when the delta is large enough to be a signal
 * (not measurement rounding noise).
 *
 * Returns:
 * - `null` when any of the three phase timings is `null` — the invariant
 *   is not computable; renderer hides the row.
 * - `null` when the absolute delta is below threshold — measurement is
 *   tight enough that calling out the gap would be noise.
 * - the signed delta (`wall_ms - sum`) otherwise. Positive = wall has
 *   slack beyond the phases (SDK reported partial). Negative = phase
 *   sum exceeds wall (SDK over-counted, e.g. phases overlap).
 *
 * Threshold: `max(5ms, 10% of wall_ms)`. The 5ms floor avoids triggering
 * on sub-50ms turns where single-digit rounding dominates; the 10% wall
 * ceiling avoids spamming the row on every 2-second turn that happens
 * to have an 8ms gap.
 */
export function untrackedDelta(att: {
  encode_ms: number | null;
  generate_ms: number | null;
  decode_ms: number | null;
  wall_ms: number;
}): number | null {
  if (
    att.encode_ms === null ||
    att.generate_ms === null ||
    att.decode_ms === null
  ) {
    return null;
  }
  const sum = att.encode_ms + att.generate_ms + att.decode_ms;
  const delta = att.wall_ms - sum;
  const threshold = Math.max(5, Math.round(att.wall_ms * 0.1));
  if (Math.abs(delta) < threshold) return null;
  return delta;
}
