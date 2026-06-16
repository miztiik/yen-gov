// Named colour-palette registry - directional ramp hues + categorical palettes.
//
// Pure module: no Svelte, no DOM imports beyond the guarded `getComputedStyle`
// read in `rampHue` (mirrors the SSR/node guard in
// frontend/src/lib/charts/TileCartogram.svelte). Exercised directly by vitest.
//
// Two colour systems live here and they MUST stay separate (plan section 0.4
// binding doctrine):
//
//   1. Directional ramp hues (RAMP_HUES / rampHue) - the single source of the
//      CHOROPLETH ramp hue. DIRECTION (not topic) picks the hue so "dark
//      always means high value": positive=teal, negative=red, neutral=blue.
//      `indicators.ts::hueForDirection` is the only consumer.
//   2. Categorical palettes (CATEGORICAL_PALETTES) - qualitative swatch sets
//      for CATEGORICAL breakdowns (e.g. power_source) and topic-family chrome.
//      NEVER used to colour a directional ramp (that would destroy the
//      good/bad valence - see topic-palette.ts).

/**
 * The 3 directional ramp hues (degrees), as a named registry. These are the
 * constant fallbacks; `rampHue` reads the matching `--ramp-<name>` CSS var
 * first so the ramp is re-themeable without a recompile.
 *
 *   positive -> 160 (teal)  : higher_is_better
 *   negative ->  25 (red)   : lower_is_better
 *   neutral  -> 250 (blue)  : neutral direction
 */
export const RAMP_HUES = { positive: 160, negative: 25, neutral: 250 } as const;

/**
 * Resolve a directional ramp hue (degrees). Reads the themeable CSS var
 * `--ramp-<name>` (a bare number) from `:root` at runtime when
 * `getComputedStyle` is available and the value parses as a finite number;
 * otherwise returns the `RAMP_HUES[name]` constant.
 *
 * Mirrors the SSR/node guard in TileCartogram.svelte: when `getComputedStyle`
 * is undefined (server render, vitest node env) the constant is returned, so
 * `hueForDirection` keeps emitting 160/25/250 with no DOM.
 */
export function rampHue(name: keyof typeof RAMP_HUES): number {
  const fallback = RAMP_HUES[name];
  if (typeof getComputedStyle === "undefined") return fallback;
  try {
    const raw = getComputedStyle(document.documentElement)
      .getPropertyValue(`--ramp-${name}`)
      .trim();
    const parsed = Number.parseFloat(raw);
    return Number.isFinite(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

/**
 * Named qualitative palettes for CATEGORICAL breakdowns only (NOT ramps).
 * Hex values are the canonical ColorBrewer qualitative schemes (Set2, Paired)
 * - perceptually well-spaced, citizen-distinguishable without a legend lookup.
 */
export const CATEGORICAL_PALETTES: Record<string, readonly string[]> = {
  // ColorBrewer Set2 (8-class qualitative).
  set2: [
    "#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3",
    "#a6d854", "#ffd92f", "#e5c494", "#b3b3b3",
  ],
  // ColorBrewer Paired (12-class qualitative).
  paired: [
    "#a6cee3", "#1f78b4", "#b2df8a", "#33a02c",
    "#fb9a99", "#e31a1c", "#fdbf6f", "#ff7f00",
    "#cab2d6", "#6a3d9a", "#ffff99", "#b15928",
  ],
};
