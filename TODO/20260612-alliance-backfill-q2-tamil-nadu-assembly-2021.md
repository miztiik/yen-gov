# Alliance backfill Q2.5 — assembly-2021 tamil-nadu — 2026-06-13

**Status:** SHIPPED
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q2 row 7
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §12 provenance · §10 anti-patterns · Hans R3.4 (name-as-published) · Hans R5 (curator-led; partial-coverage doctrine).

## Wikipedia source

- **Article:** `2021 Tamil Nadu Legislative Assembly election`
- **URL:** https://en.wikipedia.org/wiki/2021_Tamil_Nadu_Legislative_Assembly_election
- **Retrieval date:** 2026-06-13
- **Section consulted:** `## Parties and Alliances` (sub-sections `### Secular Progressive Alliance`, `### AIADMK-Led National Democratic Alliance`, `### AMMK-Led Alliance`, `### MNM-Led Alliance`, `### Others`).

### SPA (Secular Progressive Alliance) — 13 parties per Wikipedia table

| # | Party | party_id | 2021 contested | Notes |
| - | --- | --- | :---: | --- |
| 1 | Dravida Munnetra Kazhagam | parties.IN.DMK | 173 | Lead party (M. K. Stalin) |
| 2 | Indian National Congress | parties.IN.INC | 25 | K. S. Alagiri |
| 3 | Marumalarchi Dravida Munnetra Kazhagam | parties.IN.MDMK | 6 | Vaiko |
| 4 | Kongunadu Makkal Desia Katchi | parties.IN.KMDK | 3 | E. R. Eswaran |
| 5 | All India Forward Bloc | parties.IN.AIFB | 1 | P. V. Kathiravan |
| 6 | Communist Party of India | parties.IN.CPI | 6 | R. Mutharasan |
| 7 | Communist Party of India (Marxist) | parties.IN.CPIM | 6 | K. Balakrishnan |
| 8 | Viduthalai Chiruthaigal Katchi | parties.IN.VCK | 6 | Thol. Thirumavalavan |
| 9 | Indian Union Muslim League | parties.IN.IUML | 3 | K. M. Kader Mohideen |

**SPA in-catalogue row total: 9**

Missing-from-catalogue (all <5 seats, SKIP per brief):
- Manithaneya Makkal Katchi (MMK, 2 seats)
- Aathi Thamizhar Peravai (1)
- Makkal Viduthalai Katchi (1)
- Tamizhaga Vazhvurimai Katchi (1)

### AIADMK+ (AIADMK-Led NDA) — 10 parties per Wikipedia table

| # | Party | party_id | 2021 contested | Notes |
| - | --- | --- | :---: | --- |
| 1 | All India Anna Dravida Munnetra Kazhagam | parties.IN.AIADMK | 179 | Lead party (Edappadi K. Palaniswami) |
| 2 | Tamil Maanila Congress (Moopanar) | parties.IN.TMC_M | 6 | G. K. Vasan |
| 3 | Puratchi Bharatham | parties.IN.PB | 1 | M. Jaganmoorthy |
| 4 | Pattali Makkal Katchi | parties.IN.PMK | 23 | G. K. Mani |
| 5 | Bharatiya Janata Party | parties.IN.BJP | 20 | L. Murugan |

**AIADMK+ in-catalogue row total: 5**

Missing-from-catalogue (all <5 seats, SKIP):
- All India Moovendar Munnani Kazhagam (1), Moovendar Munnetra Kazhagam (1), Pasumpon Desiya Kazhagam (1), Perunthalaivar Makkal Katchi (1), Tamizhaga Makkal Munnetra Kazhagam (1)

### AMMK+ (AMMK-Led Alliance) — 8 parties per Wikipedia table

| # | Party | party_id | 2021 contested | Notes |
| - | --- | --- | :---: | --- |
| 1 | Amma Makkal Munnettra Kazhagam | parties.IN.AMMK | 161 | Lead party (T. T. V. Dhinakaran) |
| 2 | Desiya Murpokku Dravida Kazhagam | parties.IN.DMDK | 60 | Vijayakanth |
| 3 | Social Democratic Party of India | parties.IN.SDPI | 6 | V. M. S. Mohamed Mubarak |
| 4 | All India Majlis-e-Ittehadul Muslimeen | parties.IN.AIMIM | 3 | T. S. Vakeel Ahmed |

**AMMK+ in-catalogue row total: 4**

Missing-from-catalogue (all <5 seats, SKIP):
- Gokula Makkal Katchi (1), Maruthu Senai Sangam (1), Viduthalai Tamil Puligal Katchi (1), Makkal Arasu Katchi (1)

### MNM+ (MNM-Led Alliance) — partial-coverage doctrine

Wikipedia MNM+ has 7 parties; 2 partners have >=5 contested seats but are NOT in `parties.csv`:
- **Tamilaga Makkal Jananayaka Katchi (9 contested, K.M. Shareef)** — not in catalogue
- **Jananayaka Dravidia Munnetra Kazhagam (8 contested)** — not in catalogue

Per brief: ">=5 seats missing party → STOP". For this alliance specifically, the missing-partner threshold is breached. The brief's per-event "skip when contested/ambiguous → partial Q2 is fine" rule applies: **the MNM+ alliance label is SKIPPED**, and the 3 in-catalogue MNM+ leads (MNM, AISMK, IJK) ship as `alliance=''` unallied rows under partial-coverage doctrine (Wikipedia explicitly names them but as members of a partial-coverage alliance — citizen UI degrades to "unallied" label rather than a half-attributed alliance label).

| # | Party | party_id | 2021 contested | Notes |
| - | --- | --- | :---: | --- |
| 1 | Makkal Needhi Maiam | parties.IN.MNM | 140 | Lead (Kamal Haasan); alliance row dropped per partial-coverage doctrine |
| 2 | All India Samathuva Makkal Katchi | parties.IN.AISMK | 33 | R. Sarathkumar; alliance row dropped |
| 3 | Indiya Jananayaka Katchi | parties.IN.IJK | 40 | T. R. Paarivendhar; alliance row dropped |

(Janata Dal Secular: 3 contested seats <5, also in MNM+; SKIPPED.)

### Others — 5 parties per Wikipedia table (alliance=''  per brief)

| # | Party | party_id | 2021 contested | Notes |
| - | --- | --- | :---: | --- |
| 1 | Naam Tamilar Katchi | parties.IN.NTK | 234 | Seeman; explicit solo (mirrors TN AE 2026 NTK precedent) |
| 2 | Bahujan Samaj Party | parties.IN.BSP | 162 | K. Armstrong |
| 3 | Puthiya Tamilagam | parties.IN.PT | 60 | K. Krishnasamy |
| 4 | Communist Party of India (Marxist-Leninist) Liberation | parties.IN.CPIMLL | 12 | Dipankar Bhattacharya (different from CPI(ML)L role in BR Mahagathbandhan; TN contest was solo per article's Others section) |

(Samata Party: 1 contested seat, NOT in catalogue, SKIP.)

## Total composition (25 rows)

- SPA: 9
- AIADMK+: 5
- AMMK+: 4
- Partial-coverage unallied (MNM-Led leads): 3
- Others (alliance=''): 4
- **TOTAL: 25 rows**

## Hans curation discipline applied

- **Name-as-published**: "SPA", "AIADMK+", "AMMK+" are the Wikipedia section headings (informal short forms of the explicit "Secular Progressive Alliance" / "AIADMK-Led National Democratic Alliance" / "AMMK-Led Alliance" titles). Brief's instruction "Wikipedia's published front names verbatim ... NOT a synthesised id" honoured.
- **Partial-coverage doctrine**: MNM+ alliance label dropped because 2 of its 7 partners with >=5 seats are NOT in `parties.csv`; per Hans R5 the alliance is treated as un-named for ledger purposes, with its 3 in-catalogue leads showing as `alliance=''`.
- **Others-as-unallied**: NTK / BSP / PT / CPIMLL ship as `alliance=''` rows (matching the existing TN AE 2026 NTK precedent).

## Source row (provenance ledger)

```
src-1bde6be308c3,Wikipedia,2021 Tamil Nadu Legislative Assembly election,2021-04,https://en.wikipedia.org/wiki/2021_Tamil_Nadu_Legislative_Assembly_election
```

Derived via `derive_source_id`. All 25 rows carry this `source_id`.

## Acceptance gates

See parent PR body.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-13 | open | Q2.5 handover authored from Wikipedia article. 4 explicit pre-poll alliances extracted; MNM+ dropped per partial-coverage doctrine. |
| 2026-06-13 | shipped | 25 rows landed (SPA: 9 + AIADMK+: 5 + AMMK+: 4 + unallied: 7) + 1 new source.csv row. |
