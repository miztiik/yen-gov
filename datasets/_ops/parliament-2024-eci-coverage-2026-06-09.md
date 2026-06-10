# Parliament (Parliament) 2024 ingest coverage (G16, 2026-06-09)

Source: ECI Statement 33 raw CSV (`datasets/ephemeral/2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv`). Bound to the 2008-delim PC entities in `electoral.csv` (the 2024 delimitation order takes effect for the LS2029 cycle). `unbound` counts ECI PCs that did not resolve to an `electoral.csv` PC entity at delim=2008. NOTA rows are excluded (ballot option, not a candidate); Surat is absent from the raw (unopposed return; ECI excluded it from Statement 33).

| election | states | candidacies | summary PCs | unbound | raw rows |
| --- | --- | --- | --- | --- | --- |
| 2024 | 36 | 8359 | 542 | 0 | 8909 |

## Unbound (state_slug, ECI PC name)

(none — all 543 publishable LS2024 PCs minus Surat (1 unopposed) bind to spine entities after the UT-PC eci<N> fallback backfill landed.)

## Progression

| PR | unbound | candidacies | summary PCs | states | notes |
| --- | --- | --- | --- | --- | --- |
| (G16 baseline) | 50 | 7511 | 492 | 30 | pre-alias-backfill, pre-fallback |
| #844 (G16 alias backfill) | 14 | 8105 | 528 | 31 | 36 publisher-name aliases on existing PC spine rows |
| #849 (LGD-export-gap fallback) | 10 | 8161 | 532 | 33 | 4 metro PCs added via `eci<N>` fallback (Mumbai South + Lucknow + Kolkata Dakshin + Kolkata Uttar) |
| this PR (UT-PC eci<N> fallback) | 0 | 8359 | 542 | 36 | 10 UT PCs added via `eci<N>` fallback (Delhi x7 + Chandigarh + Andaman & Nicobar + Dadar & Nagar Haveli) |

The 10 UT PCs closed by this PR are UT-classification gaps: the upstream LGD register omits UT Parliament seats for UTs with limited Assembly status (Delhi has an Assembly but its PC enumeration was absent at delim=2008; Chandigarh + A&N + DNH+DD have no Assembly and their PC entries were also absent). The `eci<N>` suffix follows the same round-7-compatible natural-publisher id pattern as PR #849; citation `src-bfb4e7fb9785` REUSED per ADR-0042 (one-row-per-(producer, title, vintage); no new source_id minted).

