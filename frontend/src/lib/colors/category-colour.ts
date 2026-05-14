// Generic dimension-aware colour resolver — extends the existing party-colour
// pattern to any categorical dimension (power_source, expenditure_head, …).
//
// The party path stays in `party-colour.ts` so the existing 15 vitest cases
// keep passing untouched. New chart code (StackedTrend) calls
// `categoryColour(code, inUse, dimension, overrides)` instead.

import {
  generateOkLChPalette,
  oklchToHex,
  stringHash,
  type OkLCh,
} from "./oklch";
import type { PartyColor } from "./anchors";
import { dimensionAnchors } from "./anchors-domain";
import { ANCHORS, ANCHOR_RESERVED_HUE_RANGES } from "./anchors";
import { partyColour } from "./party-colour";

const FALLBACK_PALETTE: OkLCh[] = generateOkLChPalette({
  hueSlots: 36,
  reservedHueRanges: ANCHOR_RESERVED_HUE_RANGES,
  lightnessBands: [0.62, 0.50],
  chroma: 0.16,
});

/**
 * Resolve a colour for `code` within `dimension`, given the codes that share
 * the chart (`inUseCodes`) and any overrides.
 *
 * Resolution order:
 *   1. `overrides[code]` — caller wins always.
 *   2. For dimension="party": delegates to `partyColour` (existing module).
 *   3. `dimensionAnchors(dimension)[code]` — curated mnemonic colour.
 *   4. Algorithmic OkLCh swatch (deterministic on `code`, dedup-aware vs
 *      other algorithmic codes in `inUseCodes`).
 */
export function categoryColour(
  code: string,
  inUseCodes: readonly string[],
  dimension: string,
  overrides: Record<string, PartyColor> = {},
): PartyColor {
  if (overrides[code]) return overrides[code];
  if (dimension === "party") return partyColour(code, inUseCodes, overrides);

  const anchors = dimensionAnchors(dimension);
  if (anchors[code]) return anchors[code];

  if (FALLBACK_PALETTE.length === 0) return { fill: "#94a3b8" };

  const sorted = [...inUseCodes].sort();
  const taken = new Set<number>();
  for (const c of sorted) {
    if (overrides[c]) continue;
    if (anchors[c]) continue;
    if (ANCHORS[c]) continue; // never collide with party anchors either
    let slot = stringHash(c) % FALLBACK_PALETTE.length;
    while (taken.has(slot)) {
      slot = (slot + 1) % FALLBACK_PALETTE.length;
      if (taken.size >= FALLBACK_PALETTE.length) break;
    }
    taken.add(slot);
    if (c === code) return { fill: oklchToHex(FALLBACK_PALETTE[slot]) };
  }

  const slot = stringHash(code) % FALLBACK_PALETTE.length;
  return { fill: oklchToHex(FALLBACK_PALETTE[slot]) };
}

export function categoryFill(
  code: string,
  inUseCodes: readonly string[],
  dimension: string,
  overrides: Record<string, PartyColor> = {},
): string {
  return categoryColour(code, inUseCodes, dimension, overrides).fill;
}
