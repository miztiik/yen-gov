// Party colour resolver — 3-tier graceful fallover.
//
// Per TODO/20260527-party-symbol-assets-plan.md Section 11 + Jony (UI/UX) +
// Hans (Governance) red-team verdicts (PR #560).
//
// Pure module: no DOM, no Svelte runes, no localStorage. Reads party data
// passed as an argument (caller fetches from dim_parties / parties.json).
//
// Resolution chain (graceful fallover — no field is mandatory):
//
//   1. `anchor`   — frontend/src/lib/colors/anchors.ts has a curated iconic
//                   colour for this party_id. Full-bleed fill allowed anywhere.
//   2. `brand`    — party row carries a `brand_colour` from Wikipedia and
//                   `confidence` is 'high' or 'medium'. May fill data marks
//                   (map polygon, bar segment) but NOT chrome (chip / badge
//                   background); chip uses accent stripe or ring with
//                   paper-neutral body.
//   3. `fallback` — algorithmic hash-to-hue from party-colour.ts.
//                   Decoration only; label MUST carry the meaning.
//
// Resolver MUST NOT mutate the returned hex (no auto-darken / lighten /
// contrast-tune). Identity must not mutate; legibility is a canvas problem
// solved by anchor overrides authored by humans.
//
// IMPORTANT: do NOT import this module's `ANCHORS_BY_PID` from anywhere except
// `resolver.ts`. The contract test in PR-SYM-6d will lint for direct imports
// of the underlying maps outside this module.

import { ANCHORS } from "./anchors";
import { generateOkLChPalette, oklchToHex, stringHash } from "./oklch";

/** The data tier the resolver chose. Drives downstream affordance rules. */
export type ColorSource = "anchor" | "brand" | "fallback";

/**
 * Resolver result. Consumers read `source` to know what they may render:
 *
 * | source     | may fill large region                  | requires paired label | chip treatment                                |
 * | ---------- | -------------------------------------- | --------------------- | --------------------------------------------- |
 * | `anchor`   | yes                                    | no                    | full-bleed allowed                            |
 * | `brand`    | yes for data marks; NO for chrome      | yes                   | accent stripe or ring; chip body paper-neutral|
 * | `fallback` | no                                     | yes                   | swatch + label pair; never swatch alone       |
 */
export interface ResolvedPartyColor {
  /** `#RRGGBB`. Returned verbatim from the chosen tier; never mutated. */
  hex: string;
  /** Which tier produced `hex`. */
  source: ColorSource;
  /** The party_id the resolver was asked about. */
  party_id: string;
}

/**
 * Minimal party-row shape the resolver needs. Caller projects a
 * `dim_parties` or `parties.json` row into this shape.
 *
 * `brand_colour` is OPTIONAL — absent rows are graceful-fallover.
 */
export interface PartyRowForResolver {
  party_id: string;
  eci_code?: string | null;
  brand_colour?: {
    hex: string;
    confidence: "high" | "medium" | "low";
  } | null;
}

/**
 * Anchor lookup by `party_id`. Mirrors the citizen-recall calls in
 * `anchors.ts` (which keys on ECI numeric code) and adds the `parties.IN.*`
 * key our taxonomy uses. Hand-maintained — only iconic colour-party pairings
 * that the average voter recognises without thinking.
 */
const ANCHORS_BY_PID: Record<string, string> = {
  "parties.IN.BJP": ANCHORS["369"].fill,    // saffron lotus
  "parties.IN.INC": ANCHORS["742"].fill,    // Congress hand blue
  "parties.IN.CPIM": ANCHORS["547"].fill,   // deeper red
  "parties.IN.CPI": ANCHORS["544"].fill,    // red
  "parties.IN.DMK": ANCHORS["582"].fill,    // rising sun red
  "parties.IN.AIADMK": ANCHORS["75"].fill,  // twin leaves green
  "parties.IN.PMK": ANCHORS["1272"].fill,   // mango yellow
  "parties.IN.IUML": ANCHORS["772"].fill,   // green
  "parties.IN.AITC": ANCHORS["140"].fill,   // Trinamool green
  "parties.IN.AGP": ANCHORS["83"].fill,     // AGP saffron
  "parties.IN.AIUDF": ANCHORS["145"].fill,  // crescent dark green
  "parties.IN.NOTA": ANCHORS["NOTA"].fill,
  "parties.IN.IND": ANCHORS["IND"].fill,
};

/** Algorithmic palette (shared with party-colour.ts spec). */
const PALETTE = generateOkLChPalette({
  hueSlots: 36,
  reservedHueRanges: [], // resolver does not de-dupe against in-use; that's a consumer concern
  lightnessBands: [0.62, 0.50],
  chroma: 0.16,
});

function algorithmicFallback(party_id: string): string {
  if (PALETTE.length === 0) {
    return "#94a3b8"; // pathological config; slate-400
  }
  const slot = stringHash(party_id) % PALETTE.length;
  return oklchToHex(PALETTE[slot]);
}

/**
 * Resolve the canvas-aware colour for a single party.
 *
 * Pure: same inputs → same output. No I/O, no shared mutable state.
 * MUST NOT be called inside a render-loop without memoisation; the
 * algorithmic fallback hashes a string and indexes a 36-slot palette,
 * which is cheap but not free.
 *
 * @param party_id `parties.IN.<SLUG>` taxonomy id.
 * @param row      Optional party row carrying `brand_colour`. Pass `null`
 *                 when the consumer hasn't joined dim_parties; the resolver
 *                 skips the `brand` tier and goes anchor → fallback.
 */
export function getPartyColor(
  party_id: string,
  row: PartyRowForResolver | null = null,
): ResolvedPartyColor {
  // Tier 1: anchor (iconic, citizen-recall colours)
  const anchor = ANCHORS_BY_PID[party_id];
  if (anchor) {
    return { hex: anchor, source: "anchor", party_id };
  }

  // Tier 2: brand (Wikipedia editorial consensus). Skip if confidence='low'
  // per Hans verdict — low-confidence brand colours are faction-split
  // assignments where the assignment may be disputed; fall through to the
  // algorithmic tier rather than render a guessed faction colour.
  const brand = row?.brand_colour;
  if (brand && brand.confidence !== "low") {
    return { hex: brand.hex, source: "brand", party_id };
  }

  // Tier 3: algorithmic fallback (decoration only)
  return { hex: algorithmicFallback(party_id), source: "fallback", party_id };
}
