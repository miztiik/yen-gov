// E2 pure helper module for PartyPill (parent plan §25.3). Resolves
// a party id to a `{hex, source, label, treatment}` payload the
// component can render. Lives separately so vitest covers the
// tier-selection + neutral-fallback logic without DOM.
//
// Doctrine ties:
//   - Pure functions only. No DOM, no fetches, no Svelte runes.
//   - Calls the canonical 3-tier resolver `getPartyColor`; never
//     hand-picks a colour.
//   - Null/undefined `party_id` AND `fallback` tier -> NEUTRAL
//     (`--party-neutral` token), NOT algorithmic hash. The
//     fallback-is-unknown doctrine: an unmapped party MUST read as
//     unknown, not as a "best guess" colour.
//   - Brand-tier parties get the chip "accent" treatment (paper-
//     neutral body + coloured stripe/ring) per the resolver doctrine
//     contract; anchor-tier gets "full-bleed"; fallback gets
//     "swatch+label". Null id gets "neutral".
//   - Tested by `party-pill-resolve.test.ts` (sibling file).

import { getPartyColor, type PartyRowForResolver } from "../colors/resolver";

/** The visual treatment the pill should apply per resolver doctrine. */
export type PartyPillTreatment = "anchor" | "brand" | "fallback" | "neutral";

/** Resolved render payload for a single pill. */
export interface PartyPillResolved {
  /** Hex colour from the resolver, or the neutral token when null. */
  hex: string | null;
  /** Which doctrine tier produced the colour (drives treatment). */
  treatment: PartyPillTreatment;
  /** The label text the pill renders. ALWAYS present (resolver
   *  contract: bare swatch never allowed). */
  label: string;
}

/**
 * Resolve a `(party_id, label, row)` triple to a render payload.
 *
 * - When `party_id` is null/empty AND no label, returns `treatment: "neutral"`
 *   with the canonical "Unknown" label.
 * - When `party_id` is null/empty but label is supplied, still neutral.
 * - When `party_id` is supplied, delegates to `getPartyColor()`:
 *   - tier === "anchor" -> treatment: "anchor", hex = anchor hex
 *   - tier === "brand"  -> treatment: "brand",  hex = brand hex
 *   - tier === "fallback" -> treatment: "fallback", hex = algorithmic hex
 *     (the pill renders a SWATCH + label paired; no full fill)
 */
export function resolvePartyPill(args: {
  party_id?: string | null;
  party_short?: string | null;
  row?: PartyRowForResolver | null;
}): PartyPillResolved {
  const { party_id, party_short, row = null } = args;
  const label = (party_short ?? "").trim() || "Unknown";

  if (party_id == null || party_id === "") {
    return { hex: null, treatment: "neutral", label };
  }

  const resolved = getPartyColor(party_id, row);
  if (resolved.source === "anchor") {
    return { hex: resolved.hex, treatment: "anchor", label };
  }
  if (resolved.source === "brand") {
    return { hex: resolved.hex, treatment: "brand", label };
  }
  // fallback tier: paired swatch + label; never a full fill
  return { hex: resolved.hex, treatment: "fallback", label };
}

/**
 * Citizen-legible foreground (text) colour for a pill BODY. For full-
 * bleed anchor pills this MUST contrast with `hex`. Brand + fallback +
 * neutral all render text on the neutral body, so they read against
 * `--ink`. The luminance-based pick mirrors WCAG-AA contrast advice
 * without the full APCA calculation (an empirically-good cousin for
 * pill-sized text). Returns either "#0f172a" (--ink) or "#ffffff".
 */
export function pickInkForFill(hex: string | null | undefined): string {
  if (!hex) return "#0f172a";
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
  if (!m) return "#0f172a";
  const r = parseInt(m[1], 16);
  const g = parseInt(m[2], 16);
  const b = parseInt(m[3], 16);
  // WCAG luminance-style brightness (not the full sRGB-linear math
  // but close enough for pill-sized text; deliberately cheaper).
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness > 140 ? "#0f172a" : "#ffffff";
}
