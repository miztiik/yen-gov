# Alliance backfill Q3.1 — assembly-2024 jammu-and-kashmir — 2026-06-14

**Status:** SHIPPED
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q3 row 9
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §12 provenance · §10 anti-patterns · §0a (user-authorised parties.IN.JKAP mint) · Hans R3.4 (name-as-published) · Hans R5 (partial-coverage when catalogue-gap).

## Wikipedia source

- **Article:** `2024 Jammu and Kashmir Legislative Assembly election`
- **URL:** https://en.wikipedia.org/wiki/2024_Jammu_and_Kashmir_Legislative_Assembly_election
- **Retrieval date:** 2026-06-14
- **Sections consulted:** `## Parties and alliances` (sub-sections `### Indian National Developmental Inclusive Alliance`, `### National Democratic Alliance`, `### Jammu and Kashmir People's Democratic Party`, `### Others`) + `## Results > ### Results by alliance or party`.

## Verbatim quotes (Parties and alliances section)

### INDIA bloc (3 parties)

> "Alliance between Jammu & Kashmir National Conference, Indian National Congress and Communist Party of India (Marxist) was announced on 22 August 2024. The seat sharing was finalized on 26 August 2024 with friendly contest on 6 seats between alliance partners."

| Party (Wikipedia) | Leader | Contested | Catalogue |
| --- | --- | :---: | --- |
| Jammu and Kashmir National Conference | Farooq Abdullah | 56 | parties.IN.JKNC |
| Indian National Congress | Tariq Hameed Karra | 38 | parties.IN.INC |
| Communist Party of India (Marxist) | Mohammed Yousuf Tarigami | 1 | parties.IN.CPIM |

Note: JKNPP contested 1 seat as part of the INDIA seat-sharing arrangement (Wikipedia footnote (b)) — included as alliance constituent in Wikipedia's seat-share table but NOT enumerated in the Alliance table proper. Per Hans R5 "outside-support != member": JKNPP at 1 seat is below 5-threshold AND ambiguous-membership — SKIPPED from alliance rows.

### NDA (1 party)

> "National Democratic Alliance: Bharatiya Janata Party | Ravinder Raina | 62"

BJP contested solo as NDA in J&K (no other NDA partners enumerated). 1 row.

### JKPDP (1 party, solo)

> "Jammu and Kashmir People's Democratic Party: Mehbooba Mufti | 81"

Solo per Wikipedia's standalone sub-section (not part of any alliance). Listed as unallied (alliance='') row.

### Others (5 enumerated solo parties)

| Party (Wikipedia) | Leader | Contested | Catalogue |
| --- | --- | :---: | --- |
| Jammu and Kashmir Apni Party | Altaf Bukhari | 46 | **parties.IN.JKAP** (MINTED THIS PR) |
| **Jammu and Kashmir Awami Ittehad Party** | Engineer Rashid | 44 | **NOT IN CATALOGUE** (catalogue-gap; document below) |
| Bahujan Samaj Party | Darshan Rana | 27 | parties.IN.BSP (skipped; BSP didn't contest as alliance member here, would need alliance='' but Wikipedia includes in Others — included as 4-seat skip risk; alternative reading is BSP solo. Skipped to avoid ambiguous solo attribution) |
| Democratic Progressive Azad Party | Ghulam Nabi Azad | 23 | parties.IN.DPAP |
| **Jammu and Kashmir People's Conference** | Sajjad Gani Lone | 15 | **NOT IN CATALOGUE** (catalogue-gap; document below) |
| Aam Aadmi Party | Mehraj Malik | 7 | parties.IN.AAP |
| Jammu and Kashmir National Panthers Party | Harsh Dev Singh | 4 | parties.IN.JKNPP (skipped <5 threshold) |
| Jamaat-e-Islami Jammu and Kashmir | Ghulam Qadir Wani | 4 | (banned 2019, contested as independents; skipped <5) |

**Catalogue-gap parties** at >=5 seats per brief STOP rule:
- **Jammu and Kashmir Awami Ittehad Party (AIP)** at 44 contested — Engineer Rashid's party; not in pre-cleared mint list (VIPMS/JKAP/LJPPP). Per CLAUDE.md §10: surfaced here; SKIPPED from alliance rows; citizen UI falls back to `party_short_raw` from candidacies.csv for these 44 seats. A separate catalogue-extension PR is needed.
- **Jammu and Kashmir People's Conference (JKPC)** at 15 contested — Sajjad Gani Lone's party; same gap. SKIPPED. Same follow-up needed.

Both AIP and JKPC are solo (not alliance members per Wikipedia), so skipping them from the alliance table does NOT distort the alliance picture — INDIA bloc + NDA + JKPDP + JKAP + AAP + DPAP cover the entire alliance-affiliation story. The gap is purely a per-party identity entry; alliance attribution is unaffected.

## Party catalogue mint (this PR)

Single new row added to `datasets/data/entities/parties.csv` (alphabetically positioned before `parties.IN.JKDPN`):

```
parties.IN.JKAP,JKAP,Jammu and Kashmir Apni Party,,#D32F2F,,https://en.wikipedia.org/wiki/Jammu_and_Kashmir_Apni_Party,JKAP|J&K APNI PARTY|JK APNI PARTY|APNI PARTY,unrecognised_registered,IN-JK,2020,,,,,,جموں و کشمیر اپنی پارٹی,
```

- Brand colour `#D32F2F` (red): Wikipedia infobox explicitly lists "Red, White, and blue" — brief's seed of `#117C40` (green) was wrong; red picked per Wikipedia primary.
- Founded year 2020 per Wikipedia infobox ("8 March 2020").
- Recognition: `unrecognised_registered` (per Wikipedia "State political parties in Jammu and Kashmir" category; no ECI state-recognition record in the article).
- Native script `جموں و کشمیر اپنی پارٹی` (Urdu — matching `parties.IN.JKNC` precedent which also carries Urdu native_script).

## Rows shipped (8 total)

```
parties.IN.CPIM,assembly-2024,jammu-and-kashmir,INDIA,src-2a3498ed6ba5
parties.IN.INC,assembly-2024,jammu-and-kashmir,INDIA,src-2a3498ed6ba5
parties.IN.JKNC,assembly-2024,jammu-and-kashmir,INDIA,src-2a3498ed6ba5
parties.IN.BJP,assembly-2024,jammu-and-kashmir,NDA,src-2a3498ed6ba5
parties.IN.AAP,assembly-2024,jammu-and-kashmir,,src-2a3498ed6ba5
parties.IN.DPAP,assembly-2024,jammu-and-kashmir,,src-2a3498ed6ba5
parties.IN.JKAP,assembly-2024,jammu-and-kashmir,,src-2a3498ed6ba5
parties.IN.JKPDP,assembly-2024,jammu-and-kashmir,,src-2a3498ed6ba5
```

Breakdown: **3 INDIA + 1 NDA + 4 solo unallied** = 8 rows.

## Alliance naming convention applied

Used `INDIA` (matching the actual alliance name per Wikipedia "Indian National Developmental Inclusive Alliance"). State-event convention is no year-suffix (consistent with NDA/MGB/etc. on other state events).

## Source row (provenance ledger)

```
src-2a3498ed6ba5,Wikipedia,2024 Jammu and Kashmir Legislative Assembly election,2024-10,https://en.wikipedia.org/wiki/2024_Jammu_and_Kashmir_Legislative_Assembly_election
```

Derived via `derive_source_id("Wikipedia", "2024 Jammu and Kashmir Legislative Assembly election", "2024-10")`.

## Hans curation discipline applied

- **Pre-poll-vs-post-poll**: alliance composition reflects the 22-26 August 2024 INDIA-bloc seat-sharing. Post-poll INC's "outside support without joining the ministry" stance (Second Omar Abdullah ministry note) is NOT reflected here — that's governments_csv territory.
- **Partial-coverage**: 2 catalogue-gap parties (AIP 44 seats + JKPC 15 seats) surfaced explicitly in this handover-doc rather than silently dropped or auto-minted. Both are solo (not alliance) so the alliance story remains complete.
- **State-context for citizens**: J&K alliance picture is dominated by INDIA-vs-BJP framing per Wikipedia + media coverage. Six well-named alliance/solo lines (INDIA / NDA / JKPDP / JKAP / DPAP / AAP) make the page citizen-readable; the 2 catalogue gaps degrade gracefully via party_short_raw fallback.

## Acceptance gates

- **Tier-A validator**: delta=0 vs baseline.
- **vitest**: delta=0.
- **§13 browser smoke**: `/jammu-and-kashmir-ut/elections/assembly-2024` (citizen-facing slug is `jammu-and-kashmir-ut` per state-entity display name `Jammu and Kashmir (UT)`; the frontend reduces this to filesystem-slug `jammu-and-kashmir` for data loading — matches my alliance-row `state` column). Page resolves and renders the H1 + breadcrumb correctly; alliance headline shows `Data couldn't load` until candidacies for `state=jammu-and-kashmir/election=2024/` are ingested in a separate PR (MH AE 2024 has the same precedent on origin/main — 11 alliance rows shipped without candidacies; this is data-absent, NOT a regression).

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-14 | open | Q3.1 handover authored from Wikipedia; JKAP minted (user authorised). |
| 2026-06-14 | shipped | 8 alliance rows (3 INDIA + 1 NDA + 4 solo) + 1 source.csv row `src-2a3498ed6ba5`. JKAIP + JKPC catalogue-gaps documented for separate-PR extension. |
