# Alliance backfill Q2.4 — assembly-2020 bihar — 2026-06-13 — **DEFERRED**

**Status:** DEFERRED-NEEDS-PARTY-CATALOGUE-EXTENSION
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q2 row 6
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §10 STOP-AND-SURFACE; brief's stop-condition "Party Wikipedia names with ≥5 seats doesn't exist in parties.csv → STOP, report".

## Why deferred

Wikipedia BR AE 2020 NDA composition lists **Vikassheel Insaan Party (VIP)** as the 3rd partner with **11 seats contested** under Mukesh Sahani. This party is **NOT in `datasets/data/entities/parties.csv`** (2705-row catalogue).

Audit:
- `parties.IN.VIP` exists but maps to "Vanchitsamaj Insaaf Party" — DIFFERENT party (the Vanchit Samaj-aligned VSIP).
- `parties.IN.VKSHELJNTP` exists ("Vikassheel Janta Party") — DIFFERENT party (a UP-based formation).
- No row with "Insaan" / "Sahani" / "Sahni" / "Mukesh" anywhere across `full` / `aliases` / `short`.

Per brief STOP rule: **>=5 seats + missing from catalogue = STOP, surface**. VIP has 11 seats contested in the Wikipedia NDA seat-sharing table — exceeds the 5-seat threshold by 2.2x. Surfacing per CLAUDE.md §10.

Per brief partial-Q2-fine rule: this single event deferral does NOT block the other 5 Q2 events (MH AE 2019 priority + KA AE 2023 + UP AE 2022 + TN AE 2021 + KL AE 2021), all of which shipped in this PR.

## Wikipedia source (for reference; will be the input when this event is re-attempted)

- **Article:** `2020 Bihar Legislative Assembly election`
- **URL:** https://en.wikipedia.org/wiki/2020_Bihar_Legislative_Assembly_election
- **Retrieval date:** 2026-06-13
- **Section consulted:** `## Parties and alliances` (sub-sections `### National Democratic Alliance`, `### Mahagathbandhan`, `### Grand Democratic Secular Front`, `### Others`).

### Verbatim NDA composition (4 parties; will ship once VIP is in catalogue)

| # | Party | Wikipedia name | party_id (hypothetical) | 2020 contested | Notes |
| - | --- | --- | --- | :---: | --- |
| 1 | JD(U) | Janata Dal (United) | parties.IN.JDU | 115 | Lead party (Nitish Kumar) |
| 2 | BJP | Bharatiya Janata Party | parties.IN.BJP | 110 | Sanjay Jaiswal |
| 3 | **VIP** | **Vikassheel Insaan Party** | **NOT IN CATALOGUE** | **11** | **Mukesh Sahani; BLOCKER** |
| 4 | HAM(S) | Hindustani Awam Morcha (Secular) | parties.IN.HAM_SECULAR | 7 | Jitan Ram Manjhi |

Note: LJP (Lok Janshakti Party, Chirag Paswan, 134 contested) is listed in the Wikipedia NDA seat-sharing table BUT under the row "Parties part of the National Democratic alliance at the center but not in state", and Wikipedia confirms: "the Bharatiya Janata Party officially cut ties with the Lok Janshakti Party stating that the National Democratic Alliances in Bihar consisted of the four parties." So LJP is OUT of state-level NDA = unallied (when this event is re-attempted).

### Verbatim Mahagathbandhan composition (5 parties; all in catalogue)

| # | Party | party_id | 2020 contested | Notes |
| - | --- | --- | :---: | --- |
| 1 | Rashtriya Janata Dal | parties.IN.RJD | 144 | Lead party (Tejashwi Yadav) |
| 2 | Indian National Congress | parties.IN.INC | 70 | Madan Mohan Jha |
| 3 | Communist Party of India (Marxist-Leninist) Liberation | parties.IN.CPIMLL | 19 | Dipankar Bhattacharya |
| 4 | Communist Party of India | parties.IN.CPI | 6 | Ram Naresh Pandey |
| 5 | Communist Party of India (Marxist) | parties.IN.CPIM | 4 | Awadhesh Kumar |

### Verbatim Grand Democratic Secular Front (GDSF) composition (6 parties; all in catalogue)

| # | Party | party_id | 2020 contested | Notes |
| - | --- | --- | :---: | --- |
| 1 | Rashtriya Lok Samta Party | parties.IN.RLSP | 104 | Upendra Kushwaha |
| 2 | Bahujan Samaj Party | parties.IN.BSP | 80 | Ramji Gautam |
| 3 | Samajwadi Janata Dal Democratic | parties.IN.SJDD | 25 | Devendra Prasad Yadav |
| 4 | All India Majlis-e-Ittehadul Muslimeen | parties.IN.AIMIM | 19 | Akhtarul Iman |
| 5 | Suheldev Bharatiya Samaj Party | parties.IN.SBSP | 5 | Om Prakash Rajbhar |
| 6 | Janvadi Party (Socialist) | NOT IN CATALOGUE | 5 | Dr. Sanjay Singh Chauhan; at-threshold (5 contested) — borderline STOP |

## Recommended forward sequence

1. **Separate party-catalogue PR**: add `parties.IN.VIP_SAHANI` (or rename existing `parties.IN.VIP` → `parties.IN.VSIP` and use `parties.IN.VIP` for Mukesh Sahani's party). This requires Hans + Max consult since:
   - The party-resolver lookup map and per-state recon adapters cross-reference these party_ids.
   - The 4 PRs Z + W+S+PC class campaigns landed in 2026-06-10 / 2026-06-11 (PR #899-#929 cohort) all rely on stable party_ids; renaming requires alias bookkeeping.
2. **Also add `parties.IN.JANVADI_SOC`** (Janvadi Party (Socialist), Sanjay Chauhan) at the same time — appears in both UP SP+ (1 seat, skipped) and BR GDSF (5 seats, borderline STOP). Catalogue addition unblocks both events.
3. **Re-attempt this event** by re-running the Q2 row-emission script — `EVENTS[('assembly-2020', 'bihar')]` is pre-staged in the script preamble for trivial uncommenting.

## Estimated row count (when re-attempted)

- NDA: 4 (JDU + BJP + VIP + HAM_SECULAR)
- Mahagathbandhan: 5 (RJD + INC + CPIMLL + CPI + CPIM)
- GDSF: 6 (RLSP + BSP + SJDD + AIMIM + SBSP + JVPSOC)
- Unallied (LJP per article): 1
- **TOTAL: ~16 rows**

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-13 | open | Q2.4 handover authored. NDA composition extracted from Wikipedia; VIP (Vikassheel Insaan Party, Mukesh Sahani, 11 seats) flagged as STOP-AND-SURFACE per brief. |
| 2026-06-13 | DEFERRED | Event deferred pending party-catalogue extension for `Vikassheel Insaan Party` (separate PR; needs Hans + Max consult per party-identity doctrine). Mahagathbandhan + GDSF compositions pre-extracted in this handover for trivial uncomment when VIP lands. |
| 2026-06-14 | **CLOSED** | Q2.4 deferral resolved: `parties.IN.VIPMS` (Vikassheel Insaan Party, Mukesh Sahani) minted in the Q2.4+Q3 PR (user-authorised 2026-06-14 — "go on do it"). 15 alliance rows shipped (4 NDA + 5 Mahagathbandhan + 5 GDSF + 1 unallied LJP) + 1 new source.csv row `src-d5fb5fb008fc`. Replacement handover-doc: [20260614-alliance-backfill-q2-4-bihar-assembly-2020.md](./20260614-alliance-backfill-q2-4-bihar-assembly-2020.md). This deferred-doc archived as historical record; the live citation is now the 2026-06-14 closure handover-doc. |

## CLOSURE 2026-06-14

This deferred-doc is CLOSED. Q2.4 shipped via the Q2.4+Q3 PR on 2026-06-14. See [the closure handover-doc](./20260614-alliance-backfill-q2-4-bihar-assembly-2020.md) for:
- Wikipedia source citation with verbatim alliance-composition quote
- The `parties.IN.VIPMS` mint row (alphabetically positioned between `parties.IN.VIP` and `parties.IN.VJC`)
- All 15 shipped alliance rows (4 NDA + 5 Mahagathbandhan + 5 GDSF + 1 unallied LJP)
- Hans-discipline rationale (pre-poll-vs-post-poll, partial-coverage on Janvadi-Soc, no silent demotion)

The original deferred-doc above remains for historical context.
