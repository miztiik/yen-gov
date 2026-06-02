// Pure presentation helper for the party-colour source chip (PR-SYM-6b).
//
// Given a `ColorSource` from the 3-tier resolver, returns the visible
// label + tooltip + Tailwind class that the citizen-facing badge renders.
// Kept pure (no DOM, no Svelte) so vitest can pin the contract in node.
//
// Hans (Governance) lens: the chip MUST be honest. `brand` is a claim that
// the hex is the party's Wikipedia-sourced authoritative colour; `anchor`
// is a hand-curated iconic-recall override; `fallback` is a confession
// that the renderer hashed `party_id` because no editorial colour exists.
// Don't paper over the fallback case — citizens deserve to know.
//
// Jony (UX) lens: one chip per badge, secondary visual weight. The chip
// uses a solid / outline / dashed treatment so the SOURCE is readable
// without colour vision (border-style encodes tier).

import type { ColorSource } from "./resolver";

export interface ChipPresentation {
  /** 1-word label rendered in the pill. */
  readonly label: string;
  /** Long-form tooltip explaining provenance (rendered via `title`). */
  readonly tooltip: string;
  /** Tailwind class string for the pill: encodes border-style + body. */
  readonly className: string;
}

/** Map a resolver `source` to chip presentation. Pure. */
export function chipFor(source: ColorSource): ChipPresentation {
  switch (source) {
    case "anchor":
      return {
        label: "anchor",
        tooltip:
          "Hand-curated iconic colour: the colour the average voter recognises for this party (e.g. INC blue, BJP saffron). Edited by humans in lib/colors/resolver.ts.",
        // Solid border, slightly tinted body — anchor is the highest-confidence tier.
        className:
          "border border-solid border-slate-700 bg-slate-50 text-slate-700",
      };
    case "brand":
      return {
        label: "brand",
        tooltip:
          "Wikipedia-sourced brand colour from dim_parties (medium or high confidence). Editorial consensus, not yen-gov's invention.",
        // Outline pill, paper body — citizens see this is sourced, not curated.
        className:
          "border border-solid border-slate-500 bg-white text-slate-600",
      };
    case "fallback":
      return {
        label: "fallback",
        tooltip:
          "No editorial colour available for this party. The hex is a deterministic hash of party_id - decoration only, not an identity claim.",
        // Dashed border, neutral grey body — the chip TELLS you the colour is invented.
        className:
          "border border-dashed border-slate-400 bg-slate-50 text-slate-500",
      };
  }
}
