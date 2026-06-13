# Alliance backfill Q2.4 — assembly-2020 bihar — 2026-06-14 — **CLOSED**

**Status:** SHIPPED (closes the 2026-06-13 deferred handover)
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q2 row 6
**Predecessor deferred-doc:** [TODO/20260612-alliance-backfill-q2-bihar-assembly-2020-deferred.md](./20260612-alliance-backfill-q2-bihar-assembly-2020-deferred.md) (now CLOSED via this PR)
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §12 provenance · §10 anti-patterns · §0a (explicit user authorisation for parties.IN.VIPMS mint) · Hans R3.4 (name-as-published) · Hans R5 (pre-poll vs post-poll discipline; partial-coverage when contested).

## Wikipedia source

- **Article:** `2020 Bihar Legislative Assembly election`
- **URL:** https://en.wikipedia.org/wiki/2020_Bihar_Legislative_Assembly_election
- **Retrieval date:** 2026-06-14
- **Sections consulted:** `## Parties and alliances` (sub-sections `### National Democratic Alliance`, `### Mahagathbandhan`, `### Grand Democratic Secular Front`, `### Others`) + `## Results > ### Summary` (alliance-wise vote/seat tables).

## Why this was deferred and is now closed

The 2026-06-13 Q2.4-deferred handover-doc flagged that the NDA-2020 partner **Vikassheel Insaan Party (VIP)** under Mukesh Sahani (11 contested seats, 4 won) was missing from `datasets/data/entities/parties.csv`. The existing `parties.IN.VIP` slot maps to a different party (Vanchitsamaj Insaaf Party). Per CLAUDE.md §10 STOP-AND-SURFACE the event was deferred pending party-catalogue extension.

This PR mints `parties.IN.VIPMS` (Mukesh Sahani's Vikassheel Insaan Party — see [parties.csv](../datasets/data/entities/parties.csv) line ~733) and unblocks the event. Authorised by user instruction 2026-06-14 ("go on do it" for the 3 mints VIPMS / JKAP / LJPPP).

## Verbatim quotes (Parties and alliances section)

### National Democratic Alliance (4 parties in state-NDA per Wikipedia)

> "The Bharatiya Janata Party officially cut ties with the Lok Janshakti Party stating that the National Democratic Alliances in Bihar consisted of the four parties."

| No. | Party (Wikipedia) | Leader | Contested |
| --- | --- | --- | :---: |
| 1 | Janata Dal (United) | Nitish Kumar | 115 |
| 2 | Bharatiya Janata Party | Sanjay Jaiswal | 110 |
| 3 | **Vikassheel Insaan Party** | Mukesh Sahani | 11 |
| 4 | Hindustani Awam Morcha | Jitan Ram Manjhi | 7 |

LJP (Chirag Paswan, 134 seats) is listed in Wikipedia's NDA table under the row "Parties part of the National Democratic alliance at the center but not in state". Per Wikipedia's explicit text above, **LJP is OUT of state-NDA** → unallied (alliance='') row in this PR.

### Mahagathbandhan (5 parties)

> "the alliance after negotiations were joined in by the left–wing parties in Bihar; namely the Communist Party of India (Marxist–Leninist) Liberation, the Communist Party of India and the Communist Party of India (Marxist)."

| No. | Party (Wikipedia) | Leader | Contested |
| --- | --- | --- | :---: |
| 1 | Rashtriya Janata Dal | Tejashwi Yadav | 144 |
| 2 | Indian National Congress | Madan Mohan Jha | 70 |
| 3 | Communist Party of India (Marxist–Leninist) | Dipankar Bhattacharya | 19 |
| 4 | Communist Party of India | Ram Naresh Pandey | 6 |
| 5 | Communist Party of India (Marxist) | Awadhesh Kumar | 4 |

### Grand Democratic Secular Front (5 parties + 1 catalogue-gap)

> "Samaj Party were merged into a single coalition called the Grand Democratic Secular Front (GDSF), the alliance additionally included the Suheldev Bharatiya Samaj Party. Among the constituent parties, only the All India Majlis-e-Ittehadul Muslimeen had representation in the assembly through a single legislator."

| No. | Party (Wikipedia) | Leader | Contested | Catalogue |
| --- | --- | --- | :---: | --- |
| 1 | Rashtriya Lok Samta Party | Upendra Kushwaha | 104 | parties.IN.RLSP |
| 2 | Bahujan Samaj Party | Ramji Gautam | 80 | parties.IN.BSP |
| 3 | Samajwadi Janata Dal Democratic | Devendra Prasad Yadav | 25 | parties.IN.SJDD |
| 4 | All India Majlis-e-Ittehadul Muslimeen | Akhtarul Iman | 19 | parties.IN.AIMIM |
| 5 | Suheldev Bharatiya Samaj Party | Om Prakash Rajbhar | 5 | parties.IN.SBSP |
| 6 | Janvadi Party (Socialist) | Sanjay Singh Chauhan | 5 | **SKIPPED** — at-threshold and not in catalogue per brief partial-coverage rule |

## Party catalogue mint (this PR)

Single new row added to `datasets/data/entities/parties.csv` (alphabetically positioned between `parties.IN.VIP` and `parties.IN.VJC`):

```
parties.IN.VIPMS,VIPMS,Vikassheel Insaan Party,,#0055A4,,https://en.wikipedia.org/wiki/Vikassheel_Insaan_Party,VIP (Sahani)|VIKASSHEEL INSAAN PARTY|VKSIP|VKSP,unrecognised_registered,IN-BR,2018,,,,,,विकासशील इंसान पार्टी,
```

- Brand colour `#0055A4` (blue): Wikipedia infobox lists Orange/Blue/Green; blue picked as primary per brief default.
- Aliases avoid bare `VIP` to prevent resolver collision with `parties.IN.VIP` (Vanchitsamaj Insaaf Party). Disambiguating forms used.
- Founded year 2018 per Wikipedia infobox ("4 November 2018").
- Native script `विकासशील इंसान पार्टी` (Hindi/Devanagari, per Wikipedia article body Hindi quote).

**Known follow-up (out of this PR's scope):** existing BR 2020 candidacies.csv has raw `party_short_raw = "VIP"` for Mukesh Sahani's candidates. The party-resolver currently routes raw `VIP` to `parties.IN.VIP` (Vanchitsamaj) — wrong target for the BR context. A separate state-context-aware resolver PR is needed to route BR-state raw `VIP` to `parties.IN.VIPMS`. This PR establishes the canonical alliance attribution; the per-row candidacy routing follow-up is downstream.

## Rows shipped (15 total)

### NDA (4 rows)

```
parties.IN.BJP,assembly-2020,bihar,NDA,src-d5fb5fb008fc
parties.IN.HAM_SECULAR,assembly-2020,bihar,NDA,src-d5fb5fb008fc
parties.IN.JDU,assembly-2020,bihar,NDA,src-d5fb5fb008fc
parties.IN.VIPMS,assembly-2020,bihar,NDA,src-d5fb5fb008fc
```

### Mahagathbandhan (5 rows)

```
parties.IN.CPI,assembly-2020,bihar,Mahagathbandhan,src-d5fb5fb008fc
parties.IN.CPIM,assembly-2020,bihar,Mahagathbandhan,src-d5fb5fb008fc
parties.IN.CPIMLL,assembly-2020,bihar,Mahagathbandhan,src-d5fb5fb008fc
parties.IN.INC,assembly-2020,bihar,Mahagathbandhan,src-d5fb5fb008fc
parties.IN.RJD,assembly-2020,bihar,Mahagathbandhan,src-d5fb5fb008fc
```

### GDSF (5 rows)

```
parties.IN.AIMIM,assembly-2020,bihar,GDSF,src-d5fb5fb008fc
parties.IN.BSP,assembly-2020,bihar,GDSF,src-d5fb5fb008fc
parties.IN.RLSP,assembly-2020,bihar,GDSF,src-d5fb5fb008fc
parties.IN.SBSP,assembly-2020,bihar,GDSF,src-d5fb5fb008fc
parties.IN.SJDD,assembly-2020,bihar,GDSF,src-d5fb5fb008fc
```

### Unallied (1 row)

```
parties.IN.LJP,assembly-2020,bihar,,src-d5fb5fb008fc
```

(LJP explicitly outside state-NDA per Wikipedia; 134 seats contested all over the state.)

## Alliance naming convention applied

Per existing state-event convention (see [TODO/20260612-alliance-backfill-q2-maharashtra-assembly-2019.md](./20260612-alliance-backfill-q2-maharashtra-assembly-2019.md) precedent + queue plan-doc note "Year-suffix discipline retrofit on state-event alliance names — revisit after this queue ships"), this PR uses state-level labels WITHOUT year-suffix: `NDA`, `Mahagathbandhan`, `GDSF`. The brief's seed of `NDA-2020`/`Mahagathbandhan-2020` would have broken the convention; I applied the corrected pattern.

## Source row (provenance ledger)

```
src-d5fb5fb008fc,Wikipedia,2020 Bihar Legislative Assembly election,2020-11,https://en.wikipedia.org/wiki/2020_Bihar_Legislative_Assembly_election
```

Derived via `backend.yen_gov.canonical.citation.derive_source_id("Wikipedia", "2020 Bihar Legislative Assembly election", "2020-11")`. All 15 alliance rows for `(event_id=assembly-2020, state=bihar)` carry this `source_id`.

## Hans curation discipline applied

- **Pre-poll-vs-post-poll**: the alliance composition reflects the pre-poll seat-sharing (formalised 6-7 October 2020 per Wikipedia citation #18 Hindustan Times). Post-poll defections (e.g. all 3 VIP MLAs defected to BJP in March 2022) are NOT reflected in this row — that's governments_csv territory.
- **Outside-support != member**: LJP gets alliance='' (unallied) NOT alliance='NDA', because Wikipedia explicitly states BJP cut ties with LJP for the state-NDA. Wikipedia's "Parties part of the National Democratic alliance at the center but not in state" footnote is the receipt.
- **Threshold rule**: Janvadi Party (Socialist) 5 seats sits exactly at the brief's <5 threshold. Not in catalogue. Skipped to avoid silently miscategorising the small party; citizen UI will fall back to `party_short_raw` from `dim_candidates`.

## Acceptance gates

- **Tier-A validator** (`python -m yen_gov validate --root .`): delta=0 vs master baseline (5 Tier-A + 2 Tier-B chronic).
- **vitest (frontend)**: delta=0 vs master baseline.
- **§13 browser smoke**: see PR body for the per-surface walk-through. `/bihar/elections/assembly-2020` shows NDA / Mahagathbandhan / GDSF headline split.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-13 | open (deferred) | Q2.4 handover authored from Wikipedia; VIP (Mukesh Sahani, 11 seats) flagged as STOP-AND-SURFACE per brief. Event deferred pending catalogue extension. |
| 2026-06-13 | DEFERRED | Mahagathbandhan + GDSF compositions pre-extracted in the deferred handover for trivial closure when VIP lands. |
| 2026-06-14 | shipped | This PR mints `parties.IN.VIPMS` (user authorised) + ships 15 alliance rows (4 NDA + 5 Mahagathbandhan + 5 GDSF + 1 unallied LJP) + 1 new source.csv row `src-d5fb5fb008fc`. Sorted by `(event_id, alliance, party_id)`. The 2026-06-13 deferred handover-doc closed simultaneously (closure stanza appended). |
