# Alliance backfill Q3.3 — assembly-2025 delhi — 2026-06-14

**Status:** SHIPPED
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q3 row 11
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §12 provenance · §10 anti-patterns · Hans R3.4 (name-as-published) · Hans R5 (no-silent-misalignment).

## Wikipedia source

- **Article:** `2025 Delhi Legislative Assembly election`
- **URL:** https://en.wikipedia.org/wiki/2025_Delhi_Legislative_Assembly_election
- **Retrieval date:** 2026-06-14
- **Sections consulted:** `## Parties and alliances` (table) + `## Results > ### Results by alliance or party`.

## Verbatim quote (Parties and alliances section)

Wikipedia's `## Parties and alliances` table enumerates AAP solo + NDA (BJP+JD(U)+LJP(RV)) + INC solo + BSP + NCP + ASP(KR) + AIMIM. No INDIA bloc was formed in DL 2025 (the pre-poll INDIA pact between AAP and INC broke before polling — Wikipedia's queue-plan-doc seed cite was correct).

| Party / Alliance | Leader | Contested |
| --- | --- | :---: |
| Aam Aadmi Party | Arvind Kejriwal | 70 |
| **NDA**: Bharatiya Janata Party | Rekha Gupta | 68 |
| **NDA**: Janata Dal (United) | Shailendra Kumar | 1 |
| **NDA**: Lok Janshakti Party (Ram Vilas) | Deepak Tanwar | 1 |
| Indian National Congress | Devender Yadav | 70 |
| Bahujan Samaj Party | (party-level) | 68 |
| Nationalist Congress Party | (party-level) | 17 |
| Aazad Samaj Party (Kanshi Ram) | (party-level) | 14 |
| All India Majlis-e-Ittehadul Muslimeen | Shoaib Jamei | 2 |

## Critical Hans R5 + brief threshold application

- **NDA in Delhi**: BJP 68 + JD(U) 1 + LJP(RV) 1. JD(U) and LJP(RV) are NDA partners under the seat-sharing agreement but each contested only 1 seat. Per the brief's <5 threshold rule + Hans R5 partial-coverage doctrine: SKIP JD(U) and LJP(RV) as alliance-NDA rows. Ship BJP only as `alliance='NDA'` for citizen explicitness.
- **AAP**: 70 solo. Despite being INDIA-bloc-member nationally, no DL state pact. `alliance=''`.
- **INC**: 70 solo. Same reasoning — no DL state pact. `alliance=''`.
- **BSP**: 68 contested >> 5; solo per Wikipedia. `alliance=''`.
- **NCP**: 17 contested >> 5; solo per Wikipedia. `alliance=''`.
- **ASP(KR)**: 14 contested >> 5; solo per Wikipedia. `alliance=''`.
- **AIMIM**: 2 contested < 5. SKIPPED.

## Rows shipped (6 total)

```
parties.IN.BJP,assembly-2025,delhi,NDA,src-5340fdfa9ce7
parties.IN.AAP,assembly-2025,delhi,,src-5340fdfa9ce7
parties.IN.ASPKR,assembly-2025,delhi,,src-5340fdfa9ce7
parties.IN.BSP,assembly-2025,delhi,,src-5340fdfa9ce7
parties.IN.INC,assembly-2025,delhi,,src-5340fdfa9ce7
parties.IN.NCP,assembly-2025,delhi,,src-5340fdfa9ce7
```

Breakdown: **1 NDA + 5 solo unallied** = 6 rows. Citizen frontend will render headline as `NDA M / Others J` (or `BJP M / AAP P / INC R / Others J` depending on the AllianceTotals breakdown logic), with the 5 solo parties contributing to the "Others" bucket.

## Alliance naming convention applied

Used `NDA` for BJP solo (consistent with HR 2024 / KL 2021 / UP 2022 precedent where BJP got alliance='NDA' even when alone). All solo non-NDA parties get alliance='' per state-convention.

## Source row (provenance ledger)

```
src-5340fdfa9ce7,Wikipedia,2025 Delhi Legislative Assembly election,2025-02,https://en.wikipedia.org/wiki/2025_Delhi_Legislative_Assembly_election
```

Derived via `derive_source_id("Wikipedia", "2025 Delhi Legislative Assembly election", "2025-02")`.

## Hans curation discipline applied

- **Pre-poll-vs-post-poll**: alliance composition reflects the pre-poll DL 2025 picture — no INDIA bloc (per Wikipedia confirmation that the pact broke before polling). Post-poll BJP majority (48 of 70 seats; CM Rekha Gupta sworn 20 Feb 2025) is reflected in governments_csv, not here.
- **NDA partial-coverage**: JD(U) + LJP(RV) at 1 seat each are NDA-affiliated by national doctrine but BELOW the <5 threshold. Their 1-seat contests don't materially shape DL's alliance picture. Skipping prevents noisy single-seat alliance rows that could confuse the citizen-facing alliance headline.
- **Wikipedia is the authority**: brief's seed of "3 rows (BJP/AAP/INC) all unallied" was incomplete — Wikipedia's BSP/NCP/ASP(KR) solo entries at >>5 seats need representation per partial-coverage doctrine. This PR ships 6 rows.

## Acceptance gates

- **Tier-A validator**: delta=0 vs baseline.
- **vitest**: delta=0.
- **§13 browser smoke**: `/nct-of-delhi/elections/assembly-2025` (citizen-facing slug is `nct-of-delhi` per state-entity display name `NCT of Delhi`; the frontend reduces this to filesystem-slug `delhi` for data loading — matches my alliance-row `state` column). Page resolves and renders H1 `NCT of Delhi Assembly · February 2025` + breadcrumb correctly; alliance headline shows `Data couldn't load` until candidacies for `state=delhi/election=2025/` are ingested in a separate PR (data-absent state, NOT a regression).

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-14 | open | Q3.3 handover authored; brief's "3 rows BJP/AAP/INC" seed corrected to include BSP+NCP+ASP(KR) >=5-seat solo entries. |
| 2026-06-14 | shipped | 6 alliance rows (1 NDA + 5 solo) + 1 source.csv row `src-5340fdfa9ce7`. JD(U)+LJP(RV) NDA partners at 1 seat each skipped per <5 threshold. |
