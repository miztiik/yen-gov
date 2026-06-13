# Alliance backfill Q2.1 — assembly-2019 maharashtra — 2026-06-13

**Status:** SHIPPED (user-named priority for PR Q2)
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q2
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §12 provenance · §10 anti-patterns · plan-doc §V2 (state-event alliance naming) · Hans R3.4 (name-as-published) · Hans R5 (curator-led; skip when contested).

## Wikipedia source

- **Article:** `2019 Maharashtra Legislative Assembly election`
- **URL:** https://en.wikipedia.org/wiki/2019_Maharashtra_Legislative_Assembly_election
- **Retrieval date:** 2026-06-13
- **Section consulted:** `## Political parties and campaign` (sub-sections `### National Democratic Alliance` + `### United Progressive Alliance` + `### Others` + `### Maha Yuti Campaign` + `### Maha Aaghadi Campaign`), `## Party-wise results` (per-party seat counts), `## Alliance fight results`.

### Verbatim quotes (Political parties and campaign section)

> "Pre-election alliance of National Democratic Alliance (NDA) was formed between Bharatiya Janata Party (BJP) and Shiv Sena (SHS). Later, however, SHS left NDA and formed Three-Party Alliance Government Maha Vikas Aghadi seeing inability to share power with each other."

> "Pre-election alliance of United Progressive Alliance (UPA) was formed with Indian National Congress (INC) and Nationalist Congress Party (NCP). INC filled nominations on 145 seats and NCP on 123. Other parties that supported the UPA alliance were Raju Shetti-led Swabhimani Shetkari Saghtana (4 seats), the Peasants and Workers Party (6 seats), Samajwadi Party (3 seats), Bahujan Vikas Aghadi (3 seats) and Ravi Rana-led Swabhiman Sanghatana (1 seat). The opposition finalised common nominee of 2 seats of Mankhatao and Kothrud constituency. Peoples Republican Party (3 seats) and Bahujan Republican Socialist Party (2 seats) will be fielding their candidates on the symbols of INC and NCP. The Samajwadi Party later rescinded its support for the alliance, to contest for 7 seats separately instead. Shiv Sena later joined UPA after leaving NDA."

> "Various prominent parties in the Maharashtra's political scenario did not join hands with either of the two alliances. This includes Vanchit Bahujan Aghadi that will be contesting all 288 seats. All India Majlis-e-Ittehadul Muslimeen will be contesting from 44 seats, mostly from Muslim predominant constituencies. Maharashtra Navnirman Sena will be contesting from 103 seats."

### Critical pre-poll-vs-post-poll discipline (Hans R5)

The famous "Maha Vikas Aghadi" (MVA: INC + NCP + SHS-UBT) formed AFTER the 2019 result, when SHS broke from BJP. The PRE-poll alliance was **different**:
- SHS was IN Mahayuti with BJP (per Wikipedia: "Pre-election alliance of National Democratic Alliance (NDA) was formed between Bharatiya Janata Party (BJP) and Shiv Sena (SHS)").
- INC-NCP-led pre-poll alliance was called "Maha Aghadi" (Wikipedia spelling: "Maha Aaghadi Campaign"; also referred to as UPA in MH context).

Per CLAUDE.md §10 anti-pattern "no silent demotion" + Hans R5 "pre-poll-vs-post-poll discipline": this PR uses the **pre-poll** composition (SHS in Mahayuti, NOT in MVA). The post-poll MVA government formation is governments_csv territory, not party_alliances.csv.

## Mahayuti composition (2 parties verbatim from Wikipedia)

| # | Party | party_id | 2019 contested | 2019 won | Notes |
| - | --- | --- | :---: | :---: | --- |
| 1 | Bharatiya Janata Party | parties.IN.BJP | 164 | 105 | Lead party (Devendra Fadnavis) |
| 2 | Shiv Sena (pre-2022 split, unified) | parties.IN.SHS | 126 | 56 | Pre-split SHS; left NDA AFTER election (Nov 2019) |

**Mahayuti row total: 2**

NDA Others (12 candidates per the Political parties table) NOT enumerated by Wikipedia by name; SKIPPED (composition not verifiable per Hans R5 + R3.4).

## Maha Aghadi composition (5 parties verbatim from Wikipedia prose)

| # | Party | party_id | 2019 contested | 2019 won | Notes |
| - | --- | --- | :---: | :---: | --- |
| 1 | Indian National Congress | parties.IN.INC | 147 | 44 | Lead party (Balasaheb Thorat) |
| 2 | Nationalist Congress Party (pre-2023 split, unified) | parties.IN.NCP | 121 | 54 | Co-lead (Sharad Pawar) |
| 3 | Swabhimani Paksha (Raju Shetti) | parties.IN.SWP | 5 | 1 | Wikipedia: "Raju Shetti-led Swabhimani Shetkari Saghtana (4 seats)"; table shows 5 contested, 1 won |
| 4 | Peasants and Workers Party of India | parties.IN.PWP | 24 | 1 | Wikipedia: "the Peasants and Workers Party (6 seats)"; table shows 24 contested, 1 won |
| 5 | Bahujan Vikas Aghadi | parties.IN.BVA | 31 | 3 | Wikipedia: "Bahujan Vikas Aghadi (3 seats)"; table shows 31 contested, 3 won |

**Maha Aghadi row total: 5**

## Unallied (deliberate per Wikipedia)

Wikipedia EXPLICITLY names these as NOT joining either alliance ("Others" sub-section + SP-withdrew note):

| Party | party_id | 2019 contested | 2019 won | Reason |
| --- | --- | :---: | :---: | --- |
| Maharashtra Navnirman Sena | parties.IN.MNS | 101 | 1 | Wikipedia: "Maharashtra Navnirman Sena will be contesting from 103 seats" (final table 101) — explicit solo |
| All India Majlis-e-Ittehadul Muslimeen | parties.IN.AIMIM | 44 | 2 | Wikipedia: "AIMIM will be contesting from 44 seats" — explicit solo |
| Vanchit Bahujan Aghadi | parties.IN.VBA | 236 | 0 | Wikipedia: "Vanchit Bahujan Aghadi that will be contesting all 288 seats" — explicit solo (Prakash Ambedkar's front; later table 236 final) |
| Samajwadi Party | parties.IN.SP | 7 | 2 | Wikipedia: "The Samajwadi Party later rescinded its support for the alliance, to contest for 7 seats separately instead" — withdrew pre-poll = unallied |

**Unallied row total: 4**

## Skipped parties (with reason)

| Party | seats | Reason |
| --- | :---: | --- |
| Swabhiman Sanghatana (Ravi Rana) | 1 contested | Not in `parties.csv` AND <5 seats per brief threshold |
| Peoples Republican Party | 3 contested | Per Wikipedia: contested ON INC symbol (not separate alliance row) |
| Bahujan Republican Socialist Party | 2 contested | Per Wikipedia: contested ON NCP symbol (not separate alliance row) |
| CPI(M) | 8 contested, 1 won | Wikipedia does NOT name CPI(M) in either alliance; per Hans R5 outside-support-vs-member rule = unallied. NOT shipped as alliance='' row to avoid implying a missing alliance attribution |
| Prahar Janshakti Party (PJP) | 26 contested, 2 won | Bachchu Kadu's party; Wikipedia does NOT name in either alliance; Hans R5 same rule |
| Krantikari Shetkari Party, Rashtriya Samaj Paksha, Jan Surajya Shakti | various 1-6 | Wikipedia does NOT name in either alliance |

## Hans curation discipline applied

- **Pre-poll-vs-post-poll**: SHS stays in Mahayuti (its pre-poll affiliation) regardless of post-poll MVA fracture.
- **Outside-support != member**: parties Wikipedia does NOT explicitly enumerate as alliance constituents (CPI(M), PJP, smaller parties) stay UNREPRESENTED in CSV (not even as alliance='' rows) to avoid silent miscategorisation. Citizen UI will fall back to `party_short_raw` from `dim_candidates`.
- **State-level naming**: Wikipedia uses BOTH "NDA"/"Mahayuti" and "UPA"/"Maha Aghadi"/"Maha Aaghadi". Per existing MH AE 2024 convention ("Mahayuti"/"MVA"), this PR uses **"Mahayuti"** (lead-party-suffix-free, mirrors existing 2024 row) and **"Maha Aghadi"** (pre-poll, distinct from post-poll MVA).

## Source row (provenance ledger)

```
src-6be1c4cb7a81,Wikipedia,2019 Maharashtra Legislative Assembly election,2019-10,https://en.wikipedia.org/wiki/2019_Maharashtra_Legislative_Assembly_election
```

Derived via `backend.yen_gov.canonical.citation.derive_source_id("Wikipedia", "2019 Maharashtra Legislative Assembly election", "2019-10")`. All 11 alliance rows for `(event_id=assembly-2019, state=maharashtra)` carry this `source_id`.

## Acceptance gates

- **Tier-A validator** (`python -m yen_gov validate --root .`): delta=0 vs master baseline.
- **vitest (frontend)**: delta=0 vs master baseline.
- **§13 browser smoke**: see PR body for the per-surface walk-through. The chronic JK-CSV-sniffer issue documented in `/memories/lessons.md` was RESOLVED by PR #988 on 2026-06-12; alliance pills now light up on the (event, state) pages.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-13 | open | Q2.1 handover authored from Wikipedia article + composition cross-verified against the in-article tables (Political parties and campaign / Party-wise results / Alliance fight results) + prose quote. |
| 2026-06-13 | shipped | 11 rows landed in `datasets/data/entities/party_alliances.csv` (Mahayuti: 2 + Maha Aghadi: 5 + unallied: 4) + 1 new row in `datasets/data/entities/source.csv` (`src-6be1c4cb7a81`). Sorted by `(event_id, alliance, party_id)`. |
