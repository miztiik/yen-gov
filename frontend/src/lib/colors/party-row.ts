// `PartyRowForResolver` builder for loader-shaped party rows.
//
// PR-2 of TODO/20260612-party-rendering-and-party-pages-plan.md:
// every `<PartyPill>` site wants a `row` prop for the 3-tier
// resolver's brand tier, but loader projections carry the brand colour
// as flat `brand_colour_hex` / `brand_colour_confidence` columns
// alongside `party_id` / `party_short` / `party_eci_code` rather than
// the nested `{ hex, confidence }` shape the resolver expects.
//
// This helper is the SINGLE projection point. Three consumer surfaces
// (StateOverview, Constituency winner card, Gallagher / Psephlab chart
// rows) call it; if a future loader returns yet another shape, extend
// the input type here, never inline the shape at the call site.
//
// Returns `null` when no brand colour is sourced - the resolver then
// falls through to anchor / algorithmic tier, which is the right
// degraded path for the long tail.
//
// Pure: no DOM, no I/O, no state. Tested via the contract tests'
// existing PartyPill resolver coverage; the call sites trust the
// projection.

import type { PartyRowForResolver } from "./resolver";

/** Minimum loader-shape contract. Any narrower row type that carries
 *  these fields (PartyTotals, ElectionResultRow, PartyResult,
 *  CandidateTally, GallagherRow) can be passed without a cast. */
export interface PartyRowFromLoader {
  party_id?: string | null;
  party_short?: string | null;
  party_eci_code?: string | null;
  brand_colour_hex?: string | null;
  brand_colour_confidence?: "high" | "medium" | "low" | string | null;
}

/** Synthesise a stable `parties.IN.<X>` id when the loader hasn't
 *  joined dim_parties yet. Mirrors the fallback ladder in
 *  `psephlab/colour-bridge.ts::partyIdFor` (eci_code preferred,
 *  short-name upper-cased fallback). */
function synthesizePartyId(r: PartyRowFromLoader): string {
  if (r.party_id) return r.party_id;
  if (r.party_eci_code === "NOTA") return "parties.IN.NOTA";
  if (r.party_eci_code === "IND") return "parties.IN.IND";
  if (r.party_eci_code) return `parties.IN.${r.party_eci_code}`;
  return `parties.IN.${(r.party_short ?? "UNK").trim().toUpperCase()}`;
}

/** Build the `PartyRowForResolver` shape the PartyPill `row` prop +
 *  the 3-tier resolver expect. Returns null when no brand colour is
 *  sourced so the resolver skips its brand tier (anchor + algorithmic
 *  tiers still fire). */
export function partyRowForResolver(
  r: PartyRowFromLoader,
): PartyRowForResolver | null {
  if (!r.brand_colour_hex) return null;
  const confidence: "high" | "medium" | "low" =
    r.brand_colour_confidence === "high" ||
    r.brand_colour_confidence === "low"
      ? r.brand_colour_confidence
      : "medium";
  return {
    party_id: synthesizePartyId(r),
    eci_code: r.party_eci_code ?? null,
    brand_colour: {
      hex: r.brand_colour_hex,
      confidence,
    },
  };
}
