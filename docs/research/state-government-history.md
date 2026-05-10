# Research: State government history (CM terms)

**Last Updated**: 2026-05-10
**Status**: planned — Phase B (must land before Phase C ruling-party overlay)

## Question

For the colour-by-government overlay, we need `(state, term_start, term_end, party_code, alliance, cm_name)` tuples, verifiable, going back at least to 1990. This is the join key for "is Tamil Nadu doing better on health since 2014?"

## Candidates

### A. Wikipedia "List of Chief Ministers of <state>" (primary, hand-curated)

- Pages: e.g. <https://en.wikipedia.org/wiki/List_of_chief_ministers_of_Tamil_Nadu>
- License: CC BY-SA 3.0 (text). Quoting individual rows is fair-use; transcribing the full table requires SA.
- Pros: structured tables, cross-referenced citations, broad coverage of dates and party affiliations.
- Cons: party names drift across decades; alliance attribution often missing; SA license attaches to derived works.

### B. Election Commission of India past results

- Portal: <https://results.eci.gov.in/>
- For each general election, the ECI publishes the winning party per state. Implies start date; end date inferred from the next election.
- Pros: authoritative party codes (which we already use).
- Cons: doesn't capture mid-term changes (defections, government collapses, dismissals, President's rule).

### C. Government of India Official Gazette / state portals

- For mid-term changes (resignations, dissolutions), the gazette is canonical.
- Burden of acquisition is high; reserve for verification when Wikipedia + ECI conflict.

## Decision

**v1**: hand-author per state from Wikipedia + ECI cross-check. One file per state at `datasets/governments/in/states/<S>/cm_terms.json`. Each term has `sources[]` listing the Wikipedia URL and the relevant ECI election URL.

License of the artifact: **note that hand-author from Wikipedia inherits CC BY-SA 3.0 obligations on the table data**. Mitigation: only the *facts* (start, end, party) are taken — facts are not copyrightable. Names and citation links are stored as references to upstream, not transcribed prose. Document this in `docs/research/license-handling.md`.

**v2**: scrape Wikipedia tables programmatically with citation anchors.

**v3**: dispute-resolution pass against gazette PDFs only when an inconsistency surfaces.

## Open follow-ups

- President's Rule / Governor's Rule: model as a special "term" with `party_code: null`, `regime: "presidents_rule"`. Confirms for Punjab, Uttar Pradesh, J&K historical periods.
- Coalition / alliance: party belonging to an alliance is a separate concept from party identity. Include `alliance: "UPA" | "NDA" | "Third Front" | null` per term — this is what we colour by, by default, in the overlay.
- Tamil Nadu first (matches the existing election slice). Karnataka, Kerala, West Bengal, Assam next (the four states our boundary GeoJSONs cover).

## References

- Wikipedia "List of CMs of TN" (visited 2026-05-10): <https://en.wikipedia.org/wiki/List_of_chief_ministers_of_Tamil_Nadu>
- ECI archives: <https://results.eci.gov.in/>
- CC BY-SA 3.0 terms: <https://creativecommons.org/licenses/by-sa/3.0/>
