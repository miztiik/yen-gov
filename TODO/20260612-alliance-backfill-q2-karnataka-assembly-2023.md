# Alliance backfill Q2.2 — assembly-2023 karnataka — 2026-06-13

**Status:** SHIPPED
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q2 row 4
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §12 provenance · §10 anti-patterns · Hans R3.4 (name-as-published) · Hans R5 (curator-led).

## Wikipedia source

- **Article:** `2023 Karnataka Legislative Assembly election`
- **URL:** https://en.wikipedia.org/wiki/2023_Karnataka_Legislative_Assembly_election
- **Retrieval date:** 2026-06-13
- **Section consulted:** per-party sections (`### Bharatiya Janata Party`, `### Indian National Congress`, `### Janata Dal (Secular)`). Wikipedia article has NO `Parties and alliances` parent section AND NO sub-section enumerating pre-poll alliances — the structure jumps directly from `## Background` -> per-party campaign sections.

### Verbatim quote (no alliance section, per-party only)

Each party has its own H3 section describing its solo campaign and manifesto:
- `### Bharatiya Janata Party`: "Karnataka chief minister Basavaraj Bommai and former chief minister B. S. Yediyurappa started the 'Jana Sankalpa Yatra' for the Bharatiya Janata Party on 11 October 2022..."
- `### Indian National Congress`: "The Indian National Congress campaign was marked by allegations of corruption by the BJP government in the state... The party deployed local-level leaders Siddaramaiah, DK Shivakumar, Parameshwar, MB Patil..."
- `### Janata Dal (Secular)`: per-party seat-sharing table showing JD(S) contested 209 seats with H. D. Kumaraswamy as leader.

Wikipedia article structure confirms: **no pre-poll alliance for any of the 3 major parties** in KA AE 2023. BJP solo, INC solo, JD(S) solo.

## Composition (3 unallied parties)

Per brief: "If Wikipedia names no pre-poll alliances, ship 3 rows with `alliance=` empty (per Phase 1 contract: empty cell = unallied, NOT 'Others')."

| # | Party | party_id | 2023 contested | 2023 won | Notes |
| - | --- | --- | :---: | :---: | --- |
| 1 | Bharatiya Janata Party | parties.IN.BJP | ~224 | 66 | Solo per Wikipedia (no pre-poll alliance section) |
| 2 | Indian National Congress | parties.IN.INC | ~223 | 135 | Solo per Wikipedia |
| 3 | Janata Dal (Secular) | parties.IN.JDS | 209 | 19 | Solo per Wikipedia (per-party section table) |

**Total: 3 unallied rows** (`alliance` column empty per Phase 1 contract).

## Hans curation discipline applied

- **No invented alliance**: per CLAUDE.md §10 anti-pattern + the brief's "empty cell = unallied" contract, the three majors are shipped as alliance='' rows. NOT collapsed into a synthesized "Others" alliance.
- **Smaller parties skipped**: KCM, KCVP, KJP and other regional parties (under 5 seats contested or under 5 won) are NOT shipped as alliance rows. Citizen UI falls back to `party_short_raw` for any unmapped party.

## Source row (provenance ledger)

```
src-725f300a8a5d,Wikipedia,2023 Karnataka Legislative Assembly election,2023-05,https://en.wikipedia.org/wiki/2023_Karnataka_Legislative_Assembly_election
```

Derived via `backend.yen_gov.canonical.citation.derive_source_id("Wikipedia", "2023 Karnataka Legislative Assembly election", "2023-05")`. All 3 rows carry this `source_id`.

## Acceptance gates

See parent PR body.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-13 | open | Q2.2 handover authored. Wikipedia confirmed no pre-poll alliance structure in 2023 KA. |
| 2026-06-13 | shipped | 3 unallied rows + 1 new source.csv row. |
