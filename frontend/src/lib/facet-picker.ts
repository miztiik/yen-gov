// Pure helpers for FacetPicker.svelte + IndicatorCard.svelte facet wiring —
// extracted so the unique-facet enumeration and default-facet selection
// logic can be exercised by vitest without touching the DOM or fetch.
//
// FacetPicker is the controlled pill-row primitive used inside
// IndicatorCard.svelte when an indicator's rows carry per-facet values
// (e.g. RPO compliance ships {solar, non-solar, total}). Picking one
// segment pre-filters the rows before they flow through latestForEntity /
// seriesForEntity / rankForEntity — those helpers do not know about
// facets and would sum across them, producing meaningless aggregates.
//
// Design verdict: Jony PR-D (commit body) — pill-row pattern, "most
// non-null rows for home_entity, declaration-order tiebreaker" default-
// facet rule, no schema bump.
//
// Doctrine: docs/concepts/schema-is-the-design-system.md (composition
// over the existing renderer set, not a new renderer family).

import type { IndicatorRow } from "./indicators";

/** Distinct facet identifiers in the order they first appear in `rows`.
 *  Null and empty facets are skipped. Returns an empty array when no
 *  row carries a non-empty facet (i.e. the indicator is not faceted). */
export function uniqueFacetsInOrder(
  rows: readonly IndicatorRow[],
): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const r of rows) {
    const f = r.facet;
    if (f == null || f === "") continue;
    if (seen.has(f)) continue;
    seen.add(f);
    out.push(f);
  }
  return out;
}

/** Default-selected facet for an indicator's per-state card, per Jony's
 *  PR-D verdict section 3: pick the facet with the most non-null rows
 *  for `home_entity`; break ties using `facets` declaration order. Falls
 *  back to the first declared facet when `home_entity` is null or no
 *  facet has any data for the home entity. Returns null when `facets`
 *  is empty (caller treats this as "not faceted").
 *
 *  Why "most non-null" beats the alternatives:
 *    - declaration-order-always: leaks arbitrary catalogue ordering into
 *      the UX.
 *    - "total" always: reinforces the citizen-honesty trap (citizen
 *      lands on `total`, never taps a sibling pill, leaves believing
 *      total = solar + non-solar even though RPO's descriptor flags
 *      otherwise).
 *    - per-descriptor `default_facet` hint: schema escalation not
 *      justified by RPO or the projected ICED capacity-by-source family.
 *    - most-non-null is citizen-anchored ("show me the slice with the
 *      most data about MY state") and degrades gracefully when coverage
 *      ties (declaration order takes over). */
export function pickDefaultFacet(
  rows: readonly IndicatorRow[],
  home_entity: string | null,
  facets: readonly string[],
): string | null {
  if (facets.length === 0) return null;
  if (home_entity === null) return facets[0];
  let best_facet: string | null = null;
  let best_count = -1;
  for (const f of facets) {
    let count = 0;
    for (const r of rows) {
      if (r.entity_id !== home_entity) continue;
      if (r.facet !== f) continue;
      if (r.value == null) continue;
      count++;
    }
    // Strict inequality preserves declaration-order tiebreaker (the
    // first facet to hit the max wins; later ties do not displace it).
    if (count > best_count) {
      best_count = count;
      best_facet = f;
    }
  }
  // best_count === 0 means no facet has any data for home — fall back
  // to declaration order. Returning facets[0] keeps the picker
  // deterministic and avoids a "no facet selected" empty state.
  if (best_count <= 0) return facets[0];
  return best_facet;
}
