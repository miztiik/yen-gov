// Colour bridge for psephlab PartyResult rows.
//
// PR-SYM-6g: psephlab's `PartyResult` and `CandidateTally` were extended
// with optional `party_id` + brand colour fields so consumers
// (ParliamentArc, SwingSankey, Compare) can use the 3-tier resolver
// (anchor -> brand -> fallback) instead of the legacy `colors.fill`
// from `lib/colors/store.svelte.ts`.
//
// Helper exists because:
//   1. `party_id` is OPTIONAL on the psephlab types (hand-built fixtures
//      under fptp.test.ts / engine.test.ts construct rows inline without
//      backfilling). The bridge synthesises `parties.IN.<eci_code>` when
//      the canonical loader hasn't populated it -- this is the same
//      shape the anchor map in `lib/colors/resolver.ts` keys on, so
//      iconic-party fixtures (DMK, AIADMK, BJP, INC, NOTA) still hit
//      Tier 1.
//   2. The `PartyRowForResolver` shape the resolver expects is mildly
//      different from `PartyResult` (`brand_colour` is a `{hex, confidence}`
//      object vs the two flat columns the loader returns). Bridging once
//      here means three consumers don't each copy the same projection.
//
// Pure: no DOM, no Svelte runes, no I/O.

import { getPartyColor } from "../colors/resolver";
import type { CandidateTally, PartyResult } from "./types";

/**
 * Minimal row shape -- accepts either `PartyResult` or `CandidateTally`
 * (which both share the optional `party_id` + brand fields per PR-SYM-6g).
 */
type ColourableRow = Pick<
  PartyResult | CandidateTally,
  "party_eci_code" | "party_id" | "brand_colour_hex" | "brand_colour_confidence"
>;

/**
 * Resolve `party_id` for a psephlab row. Returns the row's own
 * `party_id` when present; otherwise synthesises `parties.IN.<eci_code>`
 * so anchor + fallback tiers still fire. Special-cases NOTA / IND so the
 * `parties.IN.NOTA` and `parties.IN.IND` anchors are honoured.
 */
export function partyIdFor(row: ColourableRow): string {
  if (row.party_id) return row.party_id;
  if (row.party_eci_code === "NOTA") return "parties.IN.NOTA";
  if (row.party_eci_code === "IND") return "parties.IN.IND";
  return `parties.IN.${row.party_eci_code}`;
}

/**
 * Resolver-ready party row. Wraps the loader's flat `brand_colour_hex` +
 * `_confidence` columns into the `{hex, confidence}` shape the resolver's
 * Tier 2 expects.
 */
export function partyColourHex(row: ColourableRow): string {
  const party_id = partyIdFor(row);
  return getPartyColor(party_id, {
    party_id,
    brand_colour: row.brand_colour_hex
      ? {
          hex: row.brand_colour_hex,
          confidence: row.brand_colour_confidence ?? "medium",
        }
      : null,
  }).hex;
}
