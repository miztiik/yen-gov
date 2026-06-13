# Alliance backfill Q2.6 — assembly-2021 kerala — 2026-06-13

**Status:** SHIPPED
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q2 row 8
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §12 provenance · §10 anti-patterns · Hans R3.4 (name-as-published) · Hans R5 (curator-led).

## Wikipedia source

- **Article:** `2021 Kerala Legislative Assembly election`
- **URL:** https://en.wikipedia.org/wiki/2021_Kerala_Legislative_Assembly_election
- **Retrieval date:** 2026-06-13
- **Section consulted:** `## Parties and alliances` (sub-sections `### Left Democratic Front`, `### United Democratic Front (Kerala)`, `### National Democratic Alliance`).

### Verbatim quotes

**LDF:** "An alliance of centre-left to left-wing political parties, the LDF is currently in power. The coalition consists of CPI(M), CPI, and several smaller parties."

**UDF:** "It is an alliance of centrist to centre-left political parties in the state, founded by the prominent Congress party leader K. Karunakaran in 1978."

**NDA:** "It is an alliance of right-wing parties. NDA Kerala unit was constituted in 2016. The coalition consists of Bharatiya Janata Party, Bharath Dharma Jana Sena, All India Anna Dravida Munnetra Kazhagam and a variety of other smaller parties."

### LDF composition — 10 parties per Wikipedia table

| # | Party | party_id | 2021 contested | Notes |
| - | --- | --- | :---: | --- |
| 1 | CPI(M) | parties.IN.CPIM | 77 | Lead party (A. Vijayaraghavan) |
| 2 | CPI | parties.IN.CPI | 23 | Kanam Rajendran |
| 3 | Kerala Congress (M) | parties.IN.KECM | 12 | Jose K. Mani |
| 4 | Janata Dal (Secular) | parties.IN.JDS | 4 | Mathew T. Thomas |
| 5 | Nationalist Congress Party | parties.IN.NCP | 3 | T. P. Peethambaran |
| 6 | Loktantrik Janta Dal | parties.IN.LJD | 3 | M. V. Shreyams Kumar |
| 7 | Indian National League | parties.IN.INL | 3 | A. P. Abdul Wahab |
| 8 | Kerala Congress (B) | parties.IN.KEC_B | 1 | R. Balakrishna Pillai |
| 9 | Janadhipathya Kerala Congress | parties.IN.JKC | 1 | K. C. Joseph |

**LDF in-catalogue row total: 9**

Missing-from-catalogue (all <5 seats, SKIP):
- Congress (Secular) / CON(S) (1, Kadannappalli Ramachandran)

### UDF composition — 8 parties per Wikipedia table

| # | Party | party_id | 2021 contested | Notes |
| - | --- | --- | :---: | --- |
| 1 | Indian National Congress | parties.IN.INC | 93 | Lead party (Mullappally Ramachandran) |
| 2 | Indian Union Muslim League | parties.IN.IUML | 25 | Sayed Hyderali Shihab Thangal |
| 3 | Kerala Congress (Joseph) | parties.IN.KEC | 10 | P. J. Joseph |
| 4 | Revolutionary Socialist Party | parties.IN.RSP | 5 | A. A. Aziz |
| 5 | Kerala Congress (Jacob) | parties.IN.KECJ | 1 | Anoop Jacob |

**UDF in-catalogue row total: 5**

Missing-from-catalogue (all <5 seats, SKIP):
- Nationalist Congress Kerala (NCK, 2 contested, Mani C. Kappan)
- Communist Marxist Party (CMP, 1 contested, C. P. John)
- Revolutionary Marxist Party of India (RMPI, 1 contested, N. Venu)

### NDA composition — 5 parties per Wikipedia table

| # | Party | party_id | 2021 contested | Notes |
| - | --- | --- | :---: | --- |
| 1 | Bharatiya Janata Party | parties.IN.BJP | 113 | Lead party (K. Surendran) |
| 2 | Bharath Dharma Jana Sena | parties.IN.BDJS | 21 | Thushar Vellapally |
| 3 | All India Anna Dravida Munnetra Kazhagam | parties.IN.AIADMK | 2 | G. Shobakumar (NDA Kerala partner, distinct from AIADMK's leading TN role) |

**NDA in-catalogue row total: 3**

Missing-from-catalogue (all <5 seats, SKIP):
- Kerala Kamaraj Congress (KKC, 1, Vishnupuram Chandrasekharan)
- Janadhipathya Rashtriya Party (JRP, 1, C. K. Janu)

## Total composition (17 rows)

- LDF: 9
- UDF: 5
- NDA: 3
- **TOTAL: 17 rows**

## Hans curation discipline applied

- **Name-as-published**: "LDF", "UDF", "NDA" are Wikipedia's exact section titles (informal short forms of "Left Democratic Front", "United Democratic Front (Kerala)", "National Democratic Alliance"). No year-suffix per existing TN AE 2026 / MH AE 2024 state-event convention.
- **AIADMK in NDA Kerala**: per Wikipedia's explicit naming. Same `party_id` as TN AIADMK+ lead; the per-event row scoping disambiguates roles correctly.

## Source row (provenance ledger)

```
src-12feeb60dda8,Wikipedia,2021 Kerala Legislative Assembly election,2021-04,https://en.wikipedia.org/wiki/2021_Kerala_Legislative_Assembly_election
```

Derived via `derive_source_id`. All 17 rows carry this `source_id`.

## Acceptance gates

See parent PR body.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-13 | open | Q2.6 handover authored from Wikipedia article. 3 explicit pre-poll alliances extracted verbatim. |
| 2026-06-13 | shipped | 17 rows landed (LDF: 9 + UDF: 5 + NDA: 3) + 1 new source.csv row. |
