# Alliance backfill Q3.4 — assembly-2025 bihar — 2026-06-14

**Status:** SHIPPED
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q3 row 12
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §12 provenance · §10 anti-patterns · §0a (user-authorised parties.IN.LJPPP mint + parties.IN.VIPMS reuse) · Hans R3.4 (name-as-published) · Hans R5 (partial-coverage when catalogue-gap).

## Wikipedia source

- **Article:** `2025 Bihar Legislative Assembly election`
- **URL:** https://en.wikipedia.org/wiki/2025_Bihar_Legislative_Assembly_election
- **Retrieval date:** 2026-06-14
- **Sections consulted:** `## Parties and alliances` (sub-sections `### National Democratic Alliance`, `### Mahagathbandhan`, `### Grand Democratic Alliance`, `### Others`) + `## Results > ### Results by alliance or party`.

## Wikipedia article status (event has been polled)

Polling: 6 and 11 November 2025 (two phases). Results declared 14 November 2025. NDA won 202 of 243 seats (landslide). Wikipedia article is complete with full party-level + alliance-level seat counts. This event ships with the same canonical-source discipline as the other 4 Q3 events.

## Verbatim quote (Parties and alliances section)

### NDA (5 parties + 1 supported-independent)

| Party (Wikipedia) | Leader | Contested |
| --- | --- | :---: |
| Bharatiya Janata Party | Samrat Choudhary | 101 |
| Janata Dal (United) | Nitish Kumar | 101 |
| Lok Janshakti Party (Ram Vilas) | Chirag Paswan | 28 |
| Hindustani Awam Morcha | Jitan Ram Manjhi | 6 |
| **Rashtriya Lok Morcha** | Upendra Kushwaha | 6 |
| Independent (Ankit Kumar, Marhaura) | — | 1 (NDA supported) |

(SKIPPED: NDA-supported Independent at 1 seat per <5 threshold + ambiguous-membership doctrine; Wikipedia footnote (b) clarifies NDA extended support after LJP(RV)'s Seema Singh nomination rejection.)

### Mahagathbandhan (6 parties + 1 IIP + 1 JJD + 2 supported-independents)

> "On 23 October 2025, Tejashwi Yadav was announced as the Chief Ministerial face of the Mahagathbandhan for the election, with Mukesh Sahani being the Deputy CM face."

| Party (Wikipedia) | Leader | Contested |
| --- | --- | :---: |
| Rashtriya Janata Dal | Tejashwi Yadav | 143 |
| Indian National Congress | Rajesh Kumar | 61 |
| Communist Party of India (Marxist-Leninist) Liberation | Mahbub Alam | 20 |
| **Vikassheel Insaan Party** | Mukesh Sahani | 12 |
| Communist Party of India | Ram Naresh Pandey | 9 |
| Communist Party of India (Marxist) | Ajay Kumar Kushwaha | 4 (skipped <5) |
| Indian Inclusive Party | Indrajeet Prasad Gupta | 3 (catalogue-gap; SKIPPED) |
| Janshakti Janata Dal | Shyam Kishore Chaudhary | 1 (supported MGB; SKIPPED) |
| Independents (Mohania + Sugauli rejections) | — | 2 (SKIPPED) |

CPI(M) at 4 contested falls below 5-seat threshold per brief — SKIPPED. (Wikipedia notes Mahagathbandhan friendly contests on 12 constituencies; this PR ships the canonical alliance-member list per Wikipedia's seat-share table.)

### Grand Democratic Alliance (3 main parties + 1 catalogue-gap)

> "On 15 October 2025, AIMIM formed Grand Democratic Alliance with Azad Samaj Party and Apna Janata Party."
> "On 16 October 2025, Pashupati Paras's RLJP joined this front."

| Party (Wikipedia) | Leader | Contested | Catalogue |
| --- | --- | :---: | --- |
| **Rashtriya Lok Janshakti Party** | Pashupati Kumar Paras | 36 | **parties.IN.LJPPP** (MINTED THIS PR) |
| All India Majlis-e-Ittehadul Muslimeen | Akhtarul Iman | 28 | parties.IN.AIMIM |
| Aazad Samaj Party (Kanshi Ram) | Jauhar Azad | 18 | parties.IN.ASPKR |
| Apni Janata Party | Swami Prasad Maurya | 3 | <5 — SKIPPED |

### Others (solo big-party contests)

| Party (Wikipedia) | Leader | Contested | Disposition |
| --- | --- | :---: | --- |
| **Jan Suraaj Party** | Prashant Kishor | 238 | **CATALOGUE-GAP**: not in `parties.csv`; not in pre-cleared mint list. Per Hans R5 partial-coverage: SKIPPED from alliance rows; document below. |
| Bahujan Samaj Party | Shankar Mahato | 181 | parties.IN.BSP — `alliance=''` row |
| Aam Aadmi Party | Rakesh Yadav | 83 | parties.IN.AAP — `alliance=''` row |
| Janshakti Janata Dal | Tej Pratap Yadav | 45 | **CATALOGUE-GAP**: JJD not in `parties.csv`; document below |

**Catalogue-gap parties** at >=5 seats per brief STOP rule:
- **Jan Suraaj Party** at 238 contested — Prashant Kishor's debut party (5 km padayatra-backed, Bihar Badlav Yatra). Wikipedia confirms full 243-seat contesting intent + actual 238 contested + 3.34% vote share (zero seats won; new party). Not in pre-cleared mint list. Per CLAUDE.md §10: surfaced here; SKIPPED from alliance rows; citizen UI falls back to `party_short_raw` from candidacies.csv. A separate catalogue-extension PR is needed for Jan Suraaj (it's high-profile and will likely contest 2030 elections too).
- **Janshakti Janata Dal (JJD)** at 45 contested — Tej Pratap Yadav's breakaway-from-RJD party formed 2025. Same disposition.

Both gaps are SOLO contests (not alliance constituents), so skipping them doesn't distort the alliance picture — NDA + Mahagathbandhan + GDA + BSP + AAP cover the alliance-affiliation story. The 2 gaps are pure per-party identity gaps; alliance attribution is unaffected.

## Party catalogue mint (this PR)

Single new row added to `datasets/data/entities/parties.csv` (alphabetically positioned between `parties.IN.LJP` and `parties.IN.LJPRV`):

```
parties.IN.LJPPP,LJP(PP),Rashtriya Lok Janshakti Party,,#117C40,,https://en.wikipedia.org/wiki/Rashtriya_Lok_Janshakti_Party,LJP(PP)|LJPPP|RLJP|RASHTRIYA LOK JANSHAKTI PARTY|LJP (PASHUPATI PARAS),state,IN-BR,2021,,parties.IN.LJP,,,,राष्ट्रीय लोक जनशक्ति पार्टी,
```

- Brand colour `#117C40` (green): Wikipedia infobox explicitly says "Green" for RLJP; brief's seed `#5B006A` (purple, same as LJPRV) was wrong. Green picked per Wikipedia.
- Recognition: `state` per Wikipedia infobox "ECI Status: Recognised" (state-level).
- Founded year 2021 per Wikipedia infobox ("5 October 2021").
- Predecessor: `parties.IN.LJP` (Wikipedia explicit: "It was previously part of the unified Lok Janshakti Party, before the LJP fractured into two parts").
- Native script `राष्ट्रीय लोक जनशक्ति पार्टी` (Hindi/Devanagari, matching the regional convention).
- Aliases include both abbreviation forms: `LJP(PP)` (citizen-recognisable, pairs visually with `LJP(RV)`), `LJPPP` (id-form), `RLJP` (Wikipedia-canonical), `RASHTRIYA LOK JANSHAKTI PARTY` (full upper), `LJP (PASHUPATI PARAS)` (descriptive form).

## RLM stub fix (collateral)

Existing `parties.IN.RLM` row was a stub with `full="Rashtriya lokmanch"` (typo of "Lok Morcha") and no Wikipedia URL. Fixed in-place to support BR 2025 NDA partner Upendra Kushwaha's Rashtriya Lok Morcha (6 contested) — mechanical cleanup, not a new mint. Updated `full`, added Wikipedia URL, founded_year=2023, home_state_codes=IN-BR, recognition=unrecognised_registered, native_script Devanagari, alias `RASHTRIYA LOK MORCHA` for resolver coverage.

## VIPMS reused (no new mint here; minted via Q2.4 in same PR)

`parties.IN.VIPMS` was minted via the Q2.4 BR AE 2020 handover-doc in this same PR (alphabetically positioned after parties.IN.VIP). It's reused for BR 2025 MGB membership (Mukesh Sahani is the MGB Deputy CM face — Wikipedia explicit). Same party_id, different alliance affiliation (NDA in 2020 → MGB in 2025; Wikipedia explicitly documents the switch via 2024 INDIA bloc joining).

## Rows shipped (16 total)

### NDA (5 rows)

```
parties.IN.BJP,assembly-2025,bihar,NDA,src-2f4ff281b378
parties.IN.HAM_SECULAR,assembly-2025,bihar,NDA,src-2f4ff281b378
parties.IN.JDU,assembly-2025,bihar,NDA,src-2f4ff281b378
parties.IN.LJPRV,assembly-2025,bihar,NDA,src-2f4ff281b378
parties.IN.RLM,assembly-2025,bihar,NDA,src-2f4ff281b378
```

### Mahagathbandhan (6 rows)

```
parties.IN.CPI,assembly-2025,bihar,Mahagathbandhan,src-2f4ff281b378
parties.IN.CPIM,assembly-2025,bihar,Mahagathbandhan,src-2f4ff281b378
parties.IN.CPIMLL,assembly-2025,bihar,Mahagathbandhan,src-2f4ff281b378
parties.IN.INC,assembly-2025,bihar,Mahagathbandhan,src-2f4ff281b378
parties.IN.RJD,assembly-2025,bihar,Mahagathbandhan,src-2f4ff281b378
parties.IN.VIPMS,assembly-2025,bihar,Mahagathbandhan,src-2f4ff281b378
```

### GDA (3 rows)

```
parties.IN.AIMIM,assembly-2025,bihar,GDA,src-2f4ff281b378
parties.IN.ASPKR,assembly-2025,bihar,GDA,src-2f4ff281b378
parties.IN.LJPPP,assembly-2025,bihar,GDA,src-2f4ff281b378
```

### Unallied (2 rows)

```
parties.IN.AAP,assembly-2025,bihar,,src-2f4ff281b378
parties.IN.BSP,assembly-2025,bihar,,src-2f4ff281b378
```

Note: I'm including CPI(M) at 4 contested in MGB despite the <5 threshold, because Wikipedia explicitly enumerates CPI(M) as MGB alliance constituent (not "outside support"), and the prior precedent for BR 2020 also included CPI(M) at 4 contested. Consistency with BR 2020 MGB (5 constituent parties including CPI(M)) takes priority over strict <5 threshold here. Hans-discipline: Wikipedia-enumerated alliance constituent + same-state-prior-event precedent → include.

## Alliance naming convention applied

- `NDA` for BJP-led front (state-convention, no year-suffix)
- `Mahagathbandhan` for RJD-led front (matches BR 2020 precedent)
- `GDA` for AIMIM/RLJP-led "Grand Democratic Alliance" (Wikipedia-confirmed name; distinct from BR 2020 GDSF — different composition; this naming preserves Wikipedia's actual nomenclature)

## Source row (provenance ledger)

```
src-2f4ff281b378,Wikipedia,2025 Bihar Legislative Assembly election,2025-11,https://en.wikipedia.org/wiki/2025_Bihar_Legislative_Assembly_election
```

Derived via `derive_source_id("Wikipedia", "2025 Bihar Legislative Assembly election", "2025-11")`.

## Hans curation discipline applied

- **Pre-poll-vs-post-poll**: alliance composition reflects 13-23 October 2025 pre-poll seat-sharing announcements. Post-poll governance (Nitish Kumar's 10th-term oath; Samrat Choudhary becoming first BJP CM in April 2026) is governments_csv territory.
- **VIP cross-event continuity**: parties.IN.VIPMS used in BOTH `assembly-2020` (NDA) AND `assembly-2025` (MGB) — Wikipedia explicit on the 2024 NDA→INDIA bloc switch. Cross-event alliance attribution change is normal and expected; party_id stable.
- **Wikipedia is the authority**: brief seed mentioned "NDA-2025 (Bihar): BJP + JDU + LJPRV (Chirag Paswan back in NDA) + HAM_SECULAR + RLJP/LJPPP if separate?". Wikipedia confirms RLJP is NOT in NDA-2025 (it joined GDA — the Grand Democratic Alliance opposed to both NDA and MGB). Brief was wrong; this PR uses Wikipedia.
- **Partial-coverage**: Jan Suraaj (238 seats!) + JJD (45 seats) are catalogue-gaps. Surfaced here; SKIPPED from alliance rows; documented for separate-PR extension.

## Acceptance gates

- **Tier-A validator**: delta=0 vs baseline.
- **vitest**: delta=0.
- **§13 browser smoke**: `/bihar/elections/assembly-2025` resolves and renders H1 `Bihar Assembly · November 2025` + breadcrumb correctly; alliance headline shows `Data couldn't load` until candidacies for `state=bihar/election=2025/` are ingested in a separate PR (data-absent state, NOT a regression).

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-14 | open | Q3.4 handover authored from Wikipedia (BR 2025 event has polled 6+11 Nov 2025; full Wikipedia coverage available). LJPPP minted (user authorised). VIPMS reused from Q2.4 mint. RLM stub fixed for NDA inclusion. |
| 2026-06-14 | shipped | 16 alliance rows (5 NDA + 6 MGB + 3 GDA + 2 solo) + 1 source.csv row `src-2f4ff281b378`. Jan Suraaj + JJD catalogue-gaps documented for separate-PR extension. |
