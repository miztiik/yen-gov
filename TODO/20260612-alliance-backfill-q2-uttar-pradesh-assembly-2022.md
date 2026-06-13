# Alliance backfill Q2.3 — assembly-2022 uttar-pradesh — 2026-06-13

**Status:** SHIPPED
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q2 row 5
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §12 provenance · §10 anti-patterns · Hans R3.4 (name-as-published) · Hans R5 (curator-led).

## Wikipedia source

- **Article:** `2022 Uttar Pradesh Legislative Assembly election`
- **URL:** https://en.wikipedia.org/wiki/2022_Uttar_Pradesh_Legislative_Assembly_election
- **Retrieval date:** 2026-06-13
- **Section consulted:** `## Parties and alliances` (sub-sections `### National Democratic Alliance`, `### Samajwadi Party+`, `### Bahujan Samaj Party`, `### Indian National Congress`).

### Verbatim quotes

**National Democratic Alliance:**
> "During the month of September, the NDA confirmed an alliance between BJP, AD(S) and the NISHAD Party. ... On 13 Jan the national democratic alliance sealed their seat sharing pact with NISHAD Party getting 16 and Apna Dal getting 17 and BJP competing on remaining 370 seats. 6 NISHAD Party candidates would fight on BJP symbol."

NDA seat-sharing table (3 parties):
| Party | Leader | Seats contested |
| --- | --- | :---: |
| Bharatiya Janata Party | Yogi Adityanath | 370 |
| NISHAD Party | Shravan Nishad / Sanjay Nishad | 16 |
| Apna Dal (Sonelal) | Anupriya Patel | 17 |

**Samajwadi Party+:**
> "RLD was the first to join the alliance. The NCP and RJD too joined the alliance later. Various other smaller parties too joined while SBSP broke away from its alliance to join SP alliance. ... Aam Aadmi Party and Samajwadi Party began talks for alliance, however they couldn't agree on seat sharing. Pragatisheel Samajwadi Party (Lohiya) joined the alliance later."

SP+ seat-sharing table (8 parties):
| Party | Leader | Seats contested |
| --- | --- | :---: |
| Samajwadi Party | Akhilesh Yadav | 347 |
| Pragatisheel Samajwadi Party (Lohiya) | Shivpal Singh Yadav | 1 |
| Mahan Dal | Keshav Dev Maurya | 2 |
| Janvadi Party (Socialist) | Sanjay Chauhan | 1 |
| Apna Dal (Kamerawadi) | Dr. Pallavi Patel / Krishna Patel | 1 + 4 = 5 |
| Rashtriya Lok Dal | Jayant Chaudhary | 33 |
| Suheldev Bharatiya Samaj Party | Om Prakash Rajbhar | 17 |
| Nationalist Congress Party | KK Sharma | 1 |
| _RJD (mentioned in prose, NOT in table)_ | _-_ | _0 in table_ |

**Bahujan Samaj Party (unallied):**
> "Unlike in previous years, the Bahujan Samaj Party announced that it would compete in the election all by itself. BSP went into an alliance with ten small political parties, namely the India Janshakti Party, Pacchasi Parivartan Samaj Party, Vishwa Shanti Party, Sanyukt Janadesh Party, Adarsh Sangram Party, Akhand Vikas Bharat Party, Sarvajan Awaz Party, Jagruk Janata Party and Sarvajan Sewa Party for their extended support to BSP."

Per Hans R5 outside-support-vs-member rule: the 10 micro-parties are "extended support" NOT alliance members; BSP listed as unallied.

## NDA composition (3 parties verbatim)

| # | Party | party_id | 2022 contested | Notes |
| - | --- | --- | :---: | --- |
| 1 | Bharatiya Janata Party | parties.IN.BJP | 370 | Lead party (Yogi Adityanath) |
| 2 | Apna Dal (Sonelal) | parties.IN.ADS | 17 | Anupriya Patel; "AD(S)" in Wikipedia |
| 3 | Nirbal Indian Shoshit Hamara Aam Dal (NISHAD Party) | parties.IN.NINSHAD | 16 | Sanjay Nishad; "NISHAD Party" in Wikipedia |

**NDA row total: 3**

## SP+ composition (7 in-catalogue parties; 1 missing-and-skipped <5)

| # | Party | party_id | 2022 contested | Notes |
| - | --- | --- | :---: | --- |
| 1 | Samajwadi Party | parties.IN.SP | 347 | Lead party (Akhilesh Yadav) |
| 2 | Pragatishil Samajwadi Party (Lohia) | parties.IN.PSPL | 1 | Shivpal Singh Yadav; Wikipedia spelling "Pragatisheel Samajwadi Party (Lohiya)" |
| 3 | Mahan Dal | parties.IN.MD | 2 | Keshav Dev Maurya |
| 4 | Apna Dal (Kamerawadi) | parties.IN.APNDLK | 5 | Pallavi Patel + Krishna Patel (table shows 1 + 4 split) |
| 5 | Rashtriya Lok Dal | parties.IN.RLD | 33 | Jayant Chaudhary; "first to join the alliance" per article |
| 6 | Suheldev Bharatiya Samaj Party | parties.IN.SBSP | 17 | Om Prakash Rajbhar; "SBSP broke away from its alliance to join SP" per article |
| 7 | Nationalist Congress Party | parties.IN.NCP | 1 | KK Sharma; "NCP and RJD too joined the alliance later" per article |

**SP+ row total: 7**

## Skipped parties (with reason)

| Party | Seats | Reason |
| --- | :---: | --- |
| Janvadi Party (Socialist) | 1 contested | NOT in `parties.csv` AND <5 seats per brief threshold (different from "Bharatiya Janvadi Party" in catalogue) |
| Rashtriya Janata Dal (RJD) | 0 in table | Mentioned in prose as "joined later" but NOT in Wikipedia's seat-sharing table — likely 0 candidates fielded; per Hans R5 "table is authoritative" SKIP |
| 10 BSP "extended support" parties | 0 each | Wikipedia explicitly labels as "extended support" not "alliance members"; per Hans R5 outside-support rule = NOT alliance members |

## Unallied (deliberate per Wikipedia)

| Party | party_id | 2022 contested | Reason |
| --- | --- | :---: | --- |
| Bahujan Samaj Party | parties.IN.BSP | 403 | Wikipedia: "BSP announced that it would compete in the election all by itself" |
| Indian National Congress | parties.IN.INC | 399 | Wikipedia's INC section describes solo campaign; SP-INC alliance "couldn't agree on seat sharing" per article |

**Unallied row total: 2**

## Hans curation discipline applied

- **Outside-support != member**: 10 micro-parties named in BSP section as "extended support" NOT shipped as alliance rows.
- **Table-authoritative over prose**: RJD mentioned in prose "joined later" but absent from seat-sharing table — SKIPPED.
- **Wikipedia label verbatim**: "NDA" and "SP+" are the Wikipedia section titles; both shipped as-is.

## Source row (provenance ledger)

```
src-861d0a089c96,Wikipedia,2022 Uttar Pradesh Legislative Assembly election,2022-03,https://en.wikipedia.org/wiki/2022_Uttar_Pradesh_Legislative_Assembly_election
```

Derived via `derive_source_id`. All 12 rows carry this `source_id`.

## Acceptance gates

See parent PR body.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-13 | open | Q2.3 handover authored from Wikipedia article. NDA + SP+ tables verbatim. |
| 2026-06-13 | shipped | 12 rows landed (NDA: 3 + SP+: 7 + unallied: 2) + 1 new source.csv row. |
