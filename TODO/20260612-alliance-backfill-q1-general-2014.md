# Alliance backfill Q1.2 — general-2014 (16th Lok Sabha) — 2026-06-12

**Status:** SHIPPED
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q1 row 2
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §12 provenance · §10 anti-patterns (no silent demotion) · plan-doc §V2 (alliance naming) · Hans R3.4 (name-as-published) · Hans R5 (curator-led; skip when contested).

## Wikipedia source

- **Article:** `2014 Indian general election` (with `Results of the 2014 Indian general election` for the explicit per-alliance party table)
- **URL:** https://en.wikipedia.org/wiki/2014_Indian_general_election
- **Companion article:** https://en.wikipedia.org/wiki/Results_of_the_2014_Indian_general_election (carries the explicit `Results by Alliance` table)
- **Retrieval date:** 2026-06-12
- **Section consulted:** `Results by Alliance` (per-alliance seat distribution) + NDA Wikipedia § Timeline § 2014 (NDA additions for that cycle)

### Verbatim quotes (Results by Alliance section, 2014 Results article)

NDA (336 seats, vote share 38.5%):
> "BJP | SS | TDP | LJP | SAD | RLSP | AD | PMK | SWP | AINRC | NPP | NPF"
> seats: "282 | 18 | 16 | 6 | 4 | 3 | 2 | 1 | 1 | 1 | 1 | 1"

UPA (60 seats, vote share 23%):
> "RSP | KC(M) | JMM | IUML | RJD | NCP | INC"
> seats: "1 | 1 | 2 | 2 | 4 | 6 | 44"

### Hans verdict on DMK / JD(U) / TRS / BJD / AAP exclusions

- **DMK** left UPA in March 2013 over Sri Lankan Tamils issue; contested 2014 LS independently → NOT in UPA-2014.
- **JD(U)** left NDA on 16 June 2013 over Modi as PM candidate; contested 2014 LS independently → NOT in NDA-2014.
- **TDP** rejoined NDA only on 6 April 2014 (per NDA Wikipedia timeline), AFTER nominations had been filed. But per the 2014 Results table the TDP IS tagged "(NDA)" with 16 seats. Include in NDA-2014.
- **TRS** went on to win 11 seats in Telangana as separate party; per 2014 Results "Telangana Rashtra Samithi" was not tagged with NDA or UPA. Skip.
- **BJD** was solo in Odisha (won 20 seats); 2014 Results table tags it under "Others (Non-Allied)". Skip.
- **AAP** solo (4 seats); not in either alliance. Skip.
- **JKNC** was UPA pre-2014 but won 0 seats in 2014 LS; per UPA Wikipedia § Former Members and per state-tag "(UPA)" on JKNC-2014 row, include in UPA-2014.
- **RLD** UPA pre-2014 per UPA Wikipedia § Former Members "RLD | UP | 2014 | Decided to leave after 2014 election performance" → was in UPA at time of 2014 LS polling; include. Won 0 seats.

## NDA-2014 composition (14 parties)

| # | Party | party_id | 2014 LS seats won | Notes |
| - | --- | --- | :---: | --- |
| 1 | Bharatiya Janata Party | parties.IN.BJP | 282 | Lead party (first solo majority since 1984) |
| 2 | Shiv Sena (unified) | parties.IN.SHS | 18 | Maharashtra Mahayuti partner |
| 3 | Telugu Desam Party | parties.IN.TDP | 16 | Rejoined NDA on 6 April 2014 |
| 4 | Lok Janshakti Party | parties.IN.LJP | 6 | Bihar NDA (rejoined 27 Feb 2014) |
| 5 | Shiromani Akali Dal | parties.IN.SAD | 4 | Punjab NDA |
| 6 | Rashtriya Lok Samta Party | parties.IN.RLSP | 3 | Bihar NDA (joined 23 Feb 2014); later left in Dec 2018 |
| 7 | Apna Dal (Soneylal) | parties.IN.ADS | 2 | UP NDA |
| 8 | Pattali Makkal Katchi | parties.IN.PMK | 1 | TN NDA |
| 9 | All India N.R. Congress | parties.IN.AINRC | 1 | Puducherry NDA (joined 13 March 2014) |
| 10 | National People's Party | parties.IN.NPP | 1 | NE NDA (Meghalaya) |
| 11 | Naga People's Front | parties.IN.NPF | 1 | NE NDA (Nagaland) |
| 12 | Marumalarchi Dravida Munnetra Kazhagam | parties.IN.MDMK | 0 | TN NDA (rejoined 1 Jan 2014) |
| 13 | Desiya Murpokku Dravida Kazhagam | parties.IN.DMDK | 0 | TN NDA (DMDK+BJP-NDA alliance confirmed Feb 2014) |
| 14 | Republican Party of India (Athawale) | parties.IN.RPIA | 0 | Maharashtra Mahayuti partner (joined 2011) |

**NDA-2014 row total: 14**

## UPA-2014 composition (9 parties)

| # | Party | party_id | 2014 LS seats won | Notes |
| - | --- | --- | :---: | --- |
| 1 | Indian National Congress | parties.IN.INC | 44 | Lead party (historic low) |
| 2 | Nationalist Congress Party | parties.IN.NCP | 6 | Maharashtra UPA |
| 3 | Rashtriya Janata Dal | parties.IN.RJD | 4 | Bihar UPA |
| 4 | Jharkhand Mukti Morcha | parties.IN.JMM | 2 | Jharkhand UPA |
| 5 | Indian Union Muslim League | parties.IN.IUML | 2 | Kerala UDF (UPA-aligned) |
| 6 | Kerala Congress (M) | parties.IN.KECM | 1 | Kerala UDF (UPA-aligned) |
| 7 | Revolutionary Socialist Party | parties.IN.RSP | 1 | Kerala UDF (UPA-aligned, won Kollam) |
| 8 | Jammu & Kashmir National Conference | parties.IN.JKNC | 0 | J&K UPA |
| 9 | Rashtriya Lok Dal | parties.IN.RLD | 0 | UP UPA (left in 2014 after performance per UPA Former Members) |

**UPA-2014 row total: 9**

## Skipped parties (with reasons)

| Party | party_id | 2014 LS seats | Reason for skip |
| --- | --- | :---: | --- |
| Janata Dal (United) | parties.IN.JDU | 2 | Left NDA on 16 June 2013; contested 2014 independently |
| Dravida Munnetra Kazhagam | parties.IN.DMK | 0 | Left UPA in March 2013 over Sri Lanka; contested 2014 independently |
| All India Anna Dravida Munnetra Kazhagam | parties.IN.AIADMK | 37 | Solo in TN (won 37/39); third-front-style independent |
| All India Trinamool Congress | parties.IN.AITC | 34 | Solo in WB (left UPA 2012); third-front-style |
| Biju Janata Dal | parties.IN.BJD | 20 | Solo in Odisha |
| Telangana Rashtra Samithi (now BRS) | parties.IN.BRS | 11 | Solo in Telangana |
| Samajwadi Party | parties.IN.SP | 5 | Solo in UP |
| Communist Party of India (Marxist) | parties.IN.CPIM | 9 | LDF Kerala + WB/Tripura solo; not in UPA-2014 |
| Communist Party of India | parties.IN.CPI | 1 | LDF Kerala; not in UPA-2014 |
| YSR Congress Party | parties.IN.YSRCP | 9 | Solo in AP |
| Aam Aadmi Party | parties.IN.AAP | 4 | Solo nationwide |
| Bahujan Samaj Party | parties.IN.BSP | 0 | Solo, 0 seats |
| Bodoland People's Front | parties.IN.BOPF | 0 | Joined NDA only Jan 2016 (post-2014) |
| Asom Gana Parishad | parties.IN.AGP | 0 | Rejoined NDA only March 2016 (post-2014) |
| Indigenous People's Front of Tripura | parties.IN.IPFT | 0 | Joined NDA only 2018 (post-2014) |
| Swabhimani Paksha | (not in parties.csv top) | 1 | Maharashtra NDA-2014 per 2014 Results; NOT in parties.csv (small Maharashtra party); skip per rule "<5 seats minor + not in parties.csv" |

## Hans curation discipline applied

- **DMK and JD(U) explicit exclusions** documented above. The 2014 cycle was the rare LS election where both parties were OUTSIDE their long-standing alliances. Including either would be a doctrine violation.
- **State-level UDF / Mahayuti not promoted to national rows**: Kerala UDF parties (INC, IUML, KECM, RSP, JKC, etc.) are routed to UPA national row only when UPA Wikipedia explicitly lists them; the smaller UDF-only state parties (JKC, SJD, etc.) stay unallied for the national event.
- **Swabhimani Paksha** is a real NDA-2014 Maharashtra partner (won 1 seat per 2014 Results) but no canonical `party_id` exists in `parties.csv` for it. Per the brief's rule "small splinter / regional party with <5 seats: skip; document the skip", skipped here. Adding it would require Hans+Max minting a new party_id (out of this PR's scope).

## Source row (provenance ledger)

```
src-74ac21d52e3d,Wikipedia,2014 Indian general election,2014-05,https://en.wikipedia.org/wiki/2014_Indian_general_election
```

Derived via `backend.yen_gov.canonical.citation.derive_source_id("Wikipedia", "2014 Indian general election", "2014-05")`. All 23 NDA-2014 + UPA-2014 alliance rows carry this `source_id`.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-12 | open | Q1.2 handover authored from Wikipedia main + Results sub-article (explicit per-alliance table) + NDA timeline. |
| 2026-06-12 | shipped | 23 rows landed in `datasets/data/entities/party_alliances.csv` (NDA-2014: 14 + UPA-2014: 9) + 1 new row in `datasets/data/entities/source.csv`. Sorted by `(event_id, alliance, party_id)`. |
