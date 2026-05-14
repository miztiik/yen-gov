// Domain-anchor maps for non-party dimensions (per ADR-0024 / stacked-trend.md).
//
// Pure presentation — like `anchors.ts`, these hexes live in the frontend,
// not under `datasets/reference/`. Each map keys a stable category id to a
// `PartyColor` ({ fill, text? }) so the same `categoryColour` resolver
// handles every dimension (party, power_source, expenditure_head, …).
//
// Adding an anchor is a citizen-recall decision: pick a colour the citizen
// reads as the thing without checking the legend. Reasons for each
// power-source choice are in `docs/architecture/frontend/charts/stacked-trend.md`
// §"Why these power-source hexes (UI-UX-validated)".

import type { PartyColor } from "./anchors";

/** Coal grey, gas cyan, hydro deep blue, nuclear purple, renewable indigo,
 * other_thermal burnt amber. Reconciled to the actual CEA per-fuel files
 * (6 facets, not 8) — see ADR-0024 §"Reconciliation". */
export const POWER_SOURCE_ANCHORS: Record<string, PartyColor> = {
  coal:          { fill: "#374151", text: "#f3f4f6" }, // slate-700
  gas:           { fill: "#0891b2" },                  // cyan-600
  hydro:         { fill: "#1e3a8a" },                  // blue-800
  nuclear:       { fill: "#a855f7" },                  // purple-500
  renewable:     { fill: "#10b981" },                  // emerald-500
  other_thermal: { fill: "#a16207" },                  // amber-700 (lignite + diesel residual)
};

/** Placeholder for the fiscal-composition chart that lands later. */
export const EXPENDITURE_HEAD_ANCHORS: Record<string, PartyColor> = {};

/** Dimension id → anchor map. Must stay in lockstep with
 * `datasets/reference/dimensions.json` once that file lands. */
const REGISTRY: Record<string, Record<string, PartyColor>> = {
  power_source: POWER_SOURCE_ANCHORS,
  expenditure_head: EXPENDITURE_HEAD_ANCHORS,
};

export function dimensionAnchors(dimension: string): Record<string, PartyColor> {
  return REGISTRY[dimension] ?? {};
}

/** Allow late registration so future dimensions (and tests) can plug in
 * without editing this file. */
export function registerDimensionAnchors(
  dimension: string,
  anchors: Record<string, PartyColor>,
): void {
  REGISTRY[dimension] = anchors;
}
