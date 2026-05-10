// Three-layer party-colour resolution: override → anchor → algorithm.
//
// Pure module: no DOM, no Svelte runes, no localStorage. Testable in isolation
// via vitest. The reactive store in `store.svelte.ts` calls into here for the
// algorithmic + anchor layers; it owns the override layer on top.
//
// See TODO/PARTY-COLORS-REWORK.md for the full design rationale.

import {
  generateOkLChPalette,
  oklchToHex,
  stringHash,
  type OkLCh,
} from "./oklch";
import { ANCHORS, ANCHOR_RESERVED_HUE_RANGES, type PartyColor } from "./anchors";

/** Default algorithmic palette specification. */
const PALETTE: OkLCh[] = generateOkLChPalette({
  hueSlots: 36,
  reservedHueRanges: ANCHOR_RESERVED_HUE_RANGES,
  lightnessBands: [0.62, 0.50],
  chroma: 0.16,
});

/**
 * Resolve the colour for a single ECI party code given the set of party codes
 * currently visible in the same view. The `inUseCodes` argument is critical:
 * the function guarantees no two algorithmically-assigned visible parties
 * share a swatch, by walking forward in palette order when a hash-collision
 * would force a clash.
 *
 * Resolution order:
 *
 *   1. `overrides[code]` if present (user explicit override; wins always).
 *   2. `ANCHORS[code]` if present (curated iconic colour; wins over algorithm).
 *   3. Algorithmic OkLCh swatch, with in-use de-duplication.
 *
 * Determinism: same `code` + same `inUseCodes` + same `overrides` always
 * returns the same hex. Different render passes for the same chart will
 * agree on colours. The de-duplication walks codes in lexicographically-
 * sorted order so the assignment is order-independent in the caller.
 *
 * Anchors never consume palette slots, so an anchor party in `inUseCodes`
 * doesn't push subsequent algorithmic parties off their "natural" hash slot.
 */
export function partyColour(
  code: string,
  inUseCodes: readonly string[],
  overrides: Record<string, PartyColor> = {},
): PartyColor {
  if (overrides[code]) return overrides[code];
  if (ANCHORS[code]) return ANCHORS[code];
  if (PALETTE.length === 0) {
    // Pathological config — should never happen with the default spec.
    return { fill: "#94a3b8" };
  }

  // De-duplicate against already-assigned non-anchor codes. Sort to make the
  // assignment independent of caller-side ordering.
  const sorted = [...inUseCodes].sort();
  const taken = new Set<number>();
  for (const c of sorted) {
    if (overrides[c]) continue;
    if (ANCHORS[c]) continue;
    let slot = stringHash(c) % PALETTE.length;
    while (taken.has(slot)) {
      slot = (slot + 1) % PALETTE.length;
      if (taken.size >= PALETTE.length) break; // palette exhausted; fall through
    }
    taken.add(slot);
    if (c === code) {
      return { fill: oklchToHex(PALETTE[slot]) };
    }
  }

  // Caller passed a code that isn't in `inUseCodes` — give it a deterministic
  // swatch without considering collisions.
  const slot = stringHash(code) % PALETTE.length;
  return { fill: oklchToHex(PALETTE[slot]) };
}

/** Just the fill hex; convenience for chart code that doesn't need text. */
export function partyFill(
  code: string,
  inUseCodes: readonly string[],
  overrides: Record<string, PartyColor> = {},
): string {
  return partyColour(code, inUseCodes, overrides).fill;
}

/** Re-exports so call sites only import one file. */
export type { PartyColor } from "./anchors";
export { ANCHORS } from "./anchors";
