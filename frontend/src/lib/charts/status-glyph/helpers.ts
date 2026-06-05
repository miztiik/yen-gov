// Status-glyph verdict helpers.
//
// Per parent plan section 20.11 (Max + Hans): when a state line is shown
// against a national reference line (pop-weighted national OR
// median-of-states), the citizen needs a tiny direction-coloured glyph
// at the latest visible point telling them whether the state is above /
// below / on the reference, AND whether that is good / bad / neutral.
//
// The verdict is the product of TWO axes:
//
//   1. position = sign(state_value - reference_value)
//   2. direction = the indicator's higher_is_better / lower_is_better /
//      neutral semantics (the existing `Direction` enum on
//      `indicators.ts`).
//
// The HARD GATE (Hans, plan section 20.11): direction MUST be set
// (`higher_is_better` or `lower_is_better`) for the glyph to carry
// colour. A `neutral`-direction indicator gets a `"neutral"` verdict
// (no colour) - a state can be above a reference without that being
// "good". Population, sex-ratio, urbanisation, cybercrime, fiscal-
// deficit, per-capita energy are all `neutral` until further design
// work resolves the citizen reading.
//
// The "missing" verdict fires when either side has no data; the
// renderer skips the glyph entirely for that series.
//
// This helper is a tiny pure function. The colour mapping + the SVG
// drawing live in `StatusGlyph.svelte`. The reference-line render
// (thin grey dashed) lives in `TimeSeriesLine.svelte` once it accepts
// a `reference_series` prop.

import type { Direction } from "../../indicators";

/** Citizen-facing verdict for a (state, reference, direction) triple. */
export type StatusVerdict =
  | "better"
  | "worse"
  | "equal"
  | "neutral"
  | "missing";

/**
 * Compare a state's latest value to a reference value under the
 * indicator's direction semantics. Returns a closed-union verdict the
 * `StatusGlyph` renderer maps to a colour + an SVG primitive.
 *
 *  - Either side null / NaN / undefined -> `"missing"`.
 *  - direction === `"neutral"` -> `"neutral"` (no colour even if
 *    the two values differ; the citizen reading is undecided).
 *  - state === reference -> `"equal"`.
 *  - (state > reference && higher_is_better)
 *    || (state < reference && lower_is_better) -> `"better"`.
 *  - otherwise -> `"worse"`.
 *
 * Mirrors the existing `gapDirection`/`verdict` logic in
 * `ranked-comparison/helpers.ts`, distilled to verdict-only (the
 * caller already has the numeric values; only the verdict matters
 * for the glyph).
 */
export function computeStatusVerdict(
  state_value: number | null | undefined,
  reference_value: number | null | undefined,
  direction: Direction,
): StatusVerdict {
  if (
    state_value === null
    || state_value === undefined
    || Number.isNaN(state_value)
    || reference_value === null
    || reference_value === undefined
    || Number.isNaN(reference_value)
  ) {
    return "missing";
  }
  if (direction === "neutral") {
    return "neutral";
  }
  if (state_value === reference_value) {
    return "equal";
  }
  const above = state_value > reference_value;
  if (above && direction === "higher_is_better") return "better";
  if (!above && direction === "lower_is_better") return "better";
  return "worse";
}
