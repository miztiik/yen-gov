// Row C of TODO/20260617-party-page-polish-and-cdn-config-plan.md (Jony P2).
//
// The /parties/<slug> page previously rendered FIVE inline per-card
// "Source: ..." pill rows (4x ECI on the data cards + 1x Wikipedia on
// the alliance card) plus a standalone "About this page" footer link.
// Row C collapses that into ONE page-foot provenance sentence: each
// publisher is stated ONCE, the ECI(official)-vs-Wikipedia(community)
// distinction is preserved, and every publisher name stays clickable
// (Holy Law #9 - provenance is mandatory; no publisher may be dropped).
//
// This module owns the pure grouping projector. It maps the per-card
// `PartyProvenance` envelope (one `PublisherPill[]` per card, built by
// `buildPartyProvenance` in `../view-models/party-sources`) into the
// TWO mapped-sentence clauses Jony specified:
//
//   Clause A "Seats, vote-share and strongholds"
//     = the DISTINCT publishers across the four data cards
//       [parliament, state_assembly, strongholds, current_strength].
//   Clause B "Alliance line-ups"
//     = the DISTINCT publishers across the [alliance_context] card.
//
// The two clauses partition all five cards, so the union of their
// pills is EXHAUSTIVE over every publisher present in any card - no
// attribution is lost (Holy Law #9). A clause whose pill list is
// empty is omitted (e.g. a party with no alliance data shows only
// clause A; a sentinel party with no data yields zero clauses).
//
// Pure: no DOM, no fetch. `PartyProvenanceFooter.svelte` renders the
// output; vitest (node env) pins the grouping contract.

import type { PublisherPill } from "../sources";
import type { PartyProvenance } from "../view-models/party-sources";

/** One mapped-sentence clause: a citizen-readable label plus the
 *  DISTINCT publisher pills that attribute the cards it covers. */
export interface ProvenanceFooterClause {
  /** Clause heading rendered as "<label>: " before the pills. */
  label: string;
  /** Deduped pills (one per publisher `label`), first-seen order. */
  pills: PublisherPill[];
}

/** Clause labels - Jony's mapped-sentence grouping. Exported so the
 *  contract test pins them without re-typing the literals. */
export const FOOTER_CLAUSE_LABELS = {
  data: "Seats, vote-share and strongholds",
  alliance: "Alliance line-ups",
} as const;

/** Pure: dedupe pills across one or more cards by `label`. A publisher
 *  cited on several cards collapses to ONE pill; first-seen order is
 *  preserved. On merge the first non-null `url` and the first non-empty
 *  `vintage_summary` win (a url-less publisher stays `url: null` - it
 *  renders as plain text, never a fabricated link); `count` accumulates
 *  so the merged pill keeps its `>= 1` invariant. */
function distinctPillsByLabel(
  ...cards: readonly (readonly PublisherPill[])[]
): PublisherPill[] {
  const byLabel = new Map<string, PublisherPill>();
  const order: string[] = [];
  for (const card of cards) {
    for (const p of card) {
      const existing = byLabel.get(p.label);
      if (existing === undefined) {
        order.push(p.label);
        byLabel.set(p.label, {
          label: p.label,
          vintage_summary: p.vintage_summary,
          url: p.url,
          count: p.count,
        });
        continue;
      }
      if (existing.url === null && p.url !== null) existing.url = p.url;
      if (
        existing.vintage_summary.length === 0 &&
        p.vintage_summary.length > 0
      ) {
        existing.vintage_summary = p.vintage_summary;
      }
      existing.count += p.count;
    }
  }
  return order.map((label) => byLabel.get(label)!);
}

/** Pure: project the per-card `PartyProvenance` into the page-foot
 *  clause list. Returns 0, 1, or 2 clauses (empty clauses omitted).
 *  The union of all returned clause pills covers EVERY publisher
 *  present in any of the five cards (Holy Law #9 exhaustiveness),
 *  because the two clauses partition all five cards. */
export function buildProvenanceFooterClauses(
  provenance: PartyProvenance,
): ProvenanceFooterClause[] {
  const cards = provenance.pills_per_card;
  const clauses: ProvenanceFooterClause[] = [];

  const dataPills = distinctPillsByLabel(
    cards.parliament,
    cards.state_assembly,
    cards.strongholds,
    cards.current_strength,
  );
  if (dataPills.length > 0) {
    clauses.push({ label: FOOTER_CLAUSE_LABELS.data, pills: dataPills });
  }

  const alliancePills = distinctPillsByLabel(cards.alliance_context);
  if (alliancePills.length > 0) {
    clauses.push({ label: FOOTER_CLAUSE_LABELS.alliance, pills: alliancePills });
  }

  return clauses;
}
