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

import type { PartyColor } from "./resolver";
import { CATEGORICAL_PALETTES } from "./palettes";

// Two colour systems, deliberately kept apart (plan section 0.4):
//   - Directional choropleth ramps get their hue from
//     `indicators.ts::hueForDirection` (DIRECTION picks the hue, so dark always
//     means high value). Topic / family hues NEVER feed a directional ramp.
//   - Categorical breakdowns (this file) get curated anchor maps
//     (POWER_SOURCE_ANCHORS) first, then may fall back to a named
//     CATEGORICAL_PALETTES set assigned by index via `paletteAnchors`.

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

/**
 * Build an anchor map for `codes` from a named CATEGORICAL_PALETTES palette,
 * assigning palette colours by the codes' sorted index (deterministic, and
 * wrapping when there are more codes than swatches). For dimensions that have
 * NO curated anchor map but still want stable, well-spaced categorical
 * colours; pair with `registerDimensionAnchors` to wire it into the resolver.
 * Returns {} when the palette name is unknown. Curated maps (e.g.
 * POWER_SOURCE_ANCHORS) always win - call this only as a categorical fallback,
 * never for a directional ramp (see the split comment at the top of file).
 */
export function paletteAnchors(
  codes: readonly string[],
  paletteName: string,
): Record<string, PartyColor> {
  const palette = CATEGORICAL_PALETTES[paletteName];
  if (!palette || palette.length === 0) return {};
  const out: Record<string, PartyColor> = {};
  const sorted = [...codes].sort();
  sorted.forEach((code, i) => {
    out[code] = { fill: palette[i % palette.length] };
  });
  return out;
}
