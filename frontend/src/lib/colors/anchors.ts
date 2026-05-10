// Anchor party colours — iconic, citizen-recognisable hues.
//
// This file replaces the bulk of the old `parties.default.ts`. Per the P3
// plan in TODO/PARTY-COLORS-REWORK.md, only parties whose flag/symbol
// colour is unambiguous AND nationally / strongly-regionally recognised
// belong here. Everything else falls through to the algorithmic palette
// in `party-colour.ts`.
//
// Pure presentation — colours live in the frontend, not under
// `datasets/reference/`. Per CLAUDE.md §3 keys are ECI party codes
// (never invented; verified against parties.json artifacts).
//
// Adding an anchor is a citizen-recall decision, not a curation reflex:
// only add a party here if the average voter recognises the colour-party
// pairing without thinking. Two anchors must not collide perceptually.
// If they do, the curation is wrong — fix it here, not in the algorithm.

export interface PartyColor {
  /** Primary fill (`#rrggbb`, no alpha). */
  fill: string;
  /**
   * Optional foreground text colour when text sits on top of `fill`. When
   * omitted, the consumer should pick black/white by luminance.
   */
  text?: string;
}

/** Curated iconic colours, keyed by ECI party code. */
export const ANCHORS: Record<string, PartyColor> = {
  // National parties
  "369": { fill: "#ea580c" },                  // BJP — saffron lotus
  "742": { fill: "#1d4ed8" },                  // INC — Congress hand blue
  "547": { fill: "#991b1b" },                  // CPI(M) — deeper red (distinct from CPI/DMK)
  "544": { fill: "#b91c1c" },                  // CPI — red

  // Tamil Nadu (S22)
  "582": { fill: "#dc2626" },                  // DMK — rising sun red
  "75":  { fill: "#16a34a" },                  // ADMK — twin leaves green
  "1272": { fill: "#facc15", text: "#1f2937" }, // PMK — mango yellow
  "772":  { fill: "#15803d" },                  // IUML — green

  // West Bengal / pan-India
  "140": { fill: "#15803d" },                  // AITC — Trinamool green

  // Assam
  "83":  { fill: "#f97316" },                  // AGP — saffron flag (distinct from BJP saffron)
  "145": { fill: "#166534" },                  // AIUDF — dark green crescent

  // Specials
  "NOTA": { fill: "#64748b" },                 // slate-500 — canonical NOTA stand-in
  "IND":  { fill: "#94a3b8" },                 // slate-400 — independents
};

/**
 * Hue ranges (in degrees) reserved by anchors above. The algorithmic
 * palette skips these so an algorithmic-assigned party won't end up
 * looking like BJP or INC.
 *
 * Approximate hue extraction is fine — this is to keep the algorithm out
 * of confusing bands, not to match anchor hexes exactly. Iconic colours
 * collected here:
 *
 *   - 369 BJP saffron / 83 AGP saffron: roughly 25-45° in OkLCh.
 *   - 742 INC Congress-blue: roughly 250-275°.
 *   - 582 DMK red / 544 CPI red / 547 CPI(M) red: roughly 25° on the
 *     OPPOSITE side, ~5-25° AND magenta-leaning 350-360°. Reserve 0-20°.
 *   - 75 ADMK green / 140 AITC green / 772 IUML green / 145 AIUDF green:
 *     roughly 130-160°.
 *   - 1272 PMK yellow: roughly 95-105°.
 */
export const ANCHOR_RESERVED_HUE_RANGES: Array<[number, number]> = [
  [0, 20],     // reds (DMK / CPI / CPI(M))
  [25, 45],    // saffrons (BJP / AGP)
  [95, 110],   // PMK yellow
  [130, 160],  // greens (ADMK / AITC / IUML / AIUDF)
  [250, 275],  // INC blue
];
