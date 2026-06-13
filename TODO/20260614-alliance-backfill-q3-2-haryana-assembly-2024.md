# Alliance backfill Q3.2 — assembly-2024 haryana — 2026-06-14

**Status:** SHIPPED
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q3 row 10
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §12 provenance · §10 anti-patterns · Hans R3.4 (name-as-published) · Hans R5 (no-silent-misalignment).

## Wikipedia source

- **Article:** `2024 Haryana Legislative Assembly election`
- **URL:** https://en.wikipedia.org/wiki/2024_Haryana_Legislative_Assembly_election
- **Retrieval date:** 2026-06-14
- **Sections consulted:** `## Parties and alliances` (table + prose) + `## Results > ### By alliance/party`.

## Verbatim quote (Parties and alliances section)

> "The BJP contested in 89 seats. On 12 September, the Congress announced an alliance with the Communist Party of India (Marxist). In July 2024, the Indian National Lok Dal (INLD) and Bahujan Samaj Party (BSP) announced an alliance for the assembly elections, with Abhay Singh Chautala as the chief ministerial face. In August 2024, the JJP announced an alliance with the Azad Samaj Party (Kanshi Ram)."

Wikipedia's "Parties and alliances" table enumerates four alliance groupings + "Others" (which lists AAP, HLP, CPI, NCP-SP, NCP — all solo).

### NDA (1 party — BJP solo)

| Party (Wikipedia) | Leader | Contested |
| --- | --- | :---: |
| Bharatiya Janata Party | Nayab Singh Saini | 89 |

(No NDA partners in HR 2024 per Wikipedia.)

### INDIA — INC+CPIM Alliance (2 parties)

| Party (Wikipedia) | Leader | Contested |
| --- | --- | :---: |
| Indian National Congress | Bhupinder Singh Hooda | 89 |
| Communist Party of India (Marxist) | Surendra Singh Malik | 1 |

### INLD-BSP Alliance (2 parties; using `INLD+` short label per state-convention)

| Party (Wikipedia) | Leader | Contested |
| --- | --- | :---: |
| Indian National Lok Dal | Abhay Singh Chautala | 51 |
| Bahujan Samaj Party | Rajbir Sorkhi | 35 |

### JJP-ASP Alliance (2 parties; using `JJP+` short label per state-convention)

| Party (Wikipedia) | Leader | Contested |
| --- | --- | :---: |
| Jannayak Janata Party | Dushyant Chautala | 66 |
| Azad Samaj Party | Chandrashekhar Azad | 12 |

### Others (solo entries)

| Party (Wikipedia) | Leader | Contested | Disposition |
| --- | --- | :---: | --- |
| Aam Aadmi Party | Sushil Gupta | 88 | **alliance='' row** (88 seats >> 5; clearly solo per Wikipedia explicit exclusion from INC+CPIM alliance) |
| Haryana Lokhit Party | Gopal Kanda | 4 | <5 threshold — SKIPPED |
| Communist Party of India | Dariyav Singh Kashyap | 2 | <5 — SKIPPED |
| Nationalist Congress Party (Sharadchandra Pawar) | Virender Verma | 1 | <5 — SKIPPED |
| Nationalist Congress Party | Ranbir | 1 | <5 — SKIPPED |

## Critical pre-poll-vs-post-poll discipline (Hans R5)

Wikipedia EXPLICITLY excludes AAP from the HR 2024 INDIA bloc — Congress made an alliance only with CPI(M), not AAP. The brief's seed of "INC + AAP coalition" was wrong. This PR uses **AAP as alliance='' (solo)** per Wikipedia's "Others" listing.

The Wikipedia table heading at `## Parties and alliances` labels INC+CPIM as the INDIA bloc; INLD-BSP and JJP-ASP are separate non-INDIA fronts. Per Wikipedia's `## Results > ### By alliance/party`, the row labels are: NDA / INDIA / INLD+ / JJP+ / Others.

## Rows shipped (8 total)

```
parties.IN.CPIM,assembly-2024,haryana,INDIA,src-7b64de7a1ba5
parties.IN.INC,assembly-2024,haryana,INDIA,src-7b64de7a1ba5
parties.IN.BSP,assembly-2024,haryana,INLD+,src-7b64de7a1ba5
parties.IN.INLD,assembly-2024,haryana,INLD+,src-7b64de7a1ba5
parties.IN.ASPKR,assembly-2024,haryana,JJP+,src-7b64de7a1ba5
parties.IN.JJP,assembly-2024,haryana,JJP+,src-7b64de7a1ba5
parties.IN.BJP,assembly-2024,haryana,NDA,src-7b64de7a1ba5
parties.IN.AAP,assembly-2024,haryana,,src-7b64de7a1ba5
```

Breakdown: **2 INDIA + 1 NDA + 2 INLD+ + 2 JJP+ + 1 solo unallied** = 8 rows.

## Alliance naming convention applied

- `INDIA` for INC+CPIM (per JK 2024 precedent established in same PR)
- `NDA` for BJP solo (consistent with KL 2021 / UP 2022 NDA-solo precedent where BJP got alliance='NDA' even though sometimes alone)
- `INLD+` for INLD-BSP (mirrors UP 2022 `SP+` and TN 2021 `AIADMK+` `AMMK+` "+" convention)
- `JJP+` for JJP-ASP (same `+` convention)

## Source row (provenance ledger)

```
src-7b64de7a1ba5,Wikipedia,2024 Haryana Legislative Assembly election,2024-10,https://en.wikipedia.org/wiki/2024_Haryana_Legislative_Assembly_election
```

Derived via `derive_source_id("Wikipedia", "2024 Haryana Legislative Assembly election", "2024-10")`.

## Hans curation discipline applied

- **Pre-poll-vs-post-poll**: alliance composition reflects the August-September 2024 pre-poll seat-sharing announcements. Post-poll BJP majority government (sworn 17 October 2024) does NOT change alliance attributions for the 2024 election — that's governments_csv territory.
- **No silent demotion**: AAP correctly listed as solo per Wikipedia's explicit non-inclusion in INC+CPIM alliance, NOT as INDIA-bloc partner per brief's wrong seed.
- **State-convention naming**: `INLD+` + `JJP+` follow the established UP/TN/KL "+" suffix pattern for state-event mini-coalitions (as opposed to national-LS year-suffix `NDA-2024` / `INDIA-2024`).

## Acceptance gates

- **Tier-A validator**: delta=0 vs baseline.
- **vitest**: delta=0.
- **§13 browser smoke**: `/haryana/elections/assembly-2024` resolves and renders H1 `Haryana Assembly · October 2024` + breadcrumb correctly; alliance headline shows `Data couldn't load` until candidacies for `state=haryana/election=2024/` are ingested in a separate PR (data-absent state, NOT a regression).

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-14 | open | Q3.2 handover authored from Wikipedia; AAP correctly identified as solo (not in INDIA bloc per Wikipedia) — overrode brief's wrong seed. |
| 2026-06-14 | shipped | 8 alliance rows (2 INDIA + 1 NDA + 2 INLD+ + 2 JJP+ + 1 solo) + 1 source.csv row `src-7b64de7a1ba5`. |
