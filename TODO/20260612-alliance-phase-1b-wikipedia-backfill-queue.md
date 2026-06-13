# Alliance backfill Phase 1b — Wikipedia per-event curation queue — 2026-06-12

**Status:** READY-FOR-CURATION (curator-led; opens after Phase 1 ships)
**Correction level:** Level-3 (data curation, multiple per-event PRs)
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §0a (Hans owns alliance fact framing; Max owns OWID-alignment) · §12 provenance · §10 anti-patterns.
**Predecessor:** [TODO/20260612-alliance-phase-1-structural-fix-plan.md](./20260612-alliance-phase-1-structural-fix-plan.md) — Phase 1 ships the schema v2.0 + loader fix + FK repair. This plan opens AFTER Phase 1 merges.

## Why this exists

Phase 1 lit up the 4 already-curated events (general-2024, assembly-2024 Maharashtra, assembly-2026 Tamil Nadu, assembly-2021 West Bengal). Phase 1b backfills the next set of high-citizen-interest events from Wikipedia per the Hans + Max joint verdict on 2026-06-12.

This is curator-led work, not autonomous-agent work. Hans's STOP-AND-SURFACE #3 explicitly bans an autonomous agent from ruling on contested alliance attributions (e.g. National Front 1989, was X member or supporter?). Each per-event PR requires Hans curation review before merge.

## Source discipline

Per Max R5.4 + Hans R3.6 + CLAUDE.md §12: every new alliance row carries `source_id` FK to a row in `datasets/data/entities/source.csv` keyed `(producer, title, vintage)`. `source_id` is deterministic via `backend.yen_gov.canonical.citation.derive_source_id`. Never hand-author src-ids.

Producer = "Wikipedia" for every Phase 1b row. Title pattern: the article title as published. Vintage = `YYYY-MM` of the polling window for that election. URL = the enwiki article URL.

## Per-event curation queue

Each event below is a separate PR. Each PR opens a per-event handover-doc with the Wikipedia article citations + the per-party alliance assignments + Hans curation sign-off. Order = highest citizen interest first.

### Q1 — National Parliament

| # | Event | URL | Wikipedia primary | Wikipedia secondary | Estimated rows | Notes |
| - | --- | --- | --- | --- | :---: | --- |
| 1 | `general-2019` | `/t/elections/general-2019` | https://en.wikipedia.org/wiki/2019_Indian_general_election | NDA: https://en.wikipedia.org/wiki/National_Democratic_Alliance ; UPA: existing src-0c15367b3cab | ~30 | NDA-II composition: BJP + SHS (then-unified) + AGP + AIADMK + JD(U) + LJP + RLSP + SAD + AD(S) + 14 NE/regional + various state parties. UPA: INC + DMK + NCP + RJD + JMM + JD(S) + others. Third-Front-style outliers (BSP, BJD, YSRCP, TRS) sit unallied or with regional fronts. |
| 2 | `general-2014` | `/t/elections/general-2014` | https://en.wikipedia.org/wiki/2014_Indian_general_election | NDA: ditto ; UPA: https://en.wikipedia.org/wiki/United_Progressive_Alliance | ~28 | NDA-II at formation: BJP + SHS + LJP + SAD + AD(S) + TDP + RLSP + AGP + JD(U) [dropped pre-poll] + others. UPA-II: INC + NCP + RJD + IUML + JMM + JKN + KC(M). |
| 3 | `general-2009` | `/t/elections/general-2009` | https://en.wikipedia.org/wiki/2009_Indian_general_election | UPA-II + NDA-II + Third Front + Fourth Front | ~35 | More fragmented; Third Front (CPI(M) + CPI + BSP + AIADMK + TDP + TRS + BJD + JD(S) + RLD) + Fourth Front (SP + RJD + LJP). Hans review CRITICAL for outside-support vs in-alliance distinctions. |

### Q2 — State Assemblies (biggest seat counts, post-2018)

| # | Event | URL | Wikipedia primary | Estimated rows | Notes |
| - | --- | --- | --- | :---: | --- |
| 4 | `assembly-2023` (Karnataka) | `/karnataka/elections/assembly-2023` | https://en.wikipedia.org/wiki/2023_Karnataka_Legislative_Assembly_election | ~5 | No formal pre-poll alliance for INC; BJP solo; JD(S) solo. Three rows minimum (one per major party, alliance=null). |
| 5 | `assembly-2022` (Uttar Pradesh) | `/uttar-pradesh/elections/assembly-2022` | https://en.wikipedia.org/wiki/2022_Uttar_Pradesh_Legislative_Assembly_election | ~10 | NDA: BJP + ADAL + NISHAD. SP-led: SP + RLD + SBSP + JKP. BSP solo. INC solo. |
| 6 | `assembly-2020` (Bihar) | `/bihar/elections/assembly-2020` | https://en.wikipedia.org/wiki/2020_Bihar_Legislative_Assembly_election | ~12 | NDA: BJP + JD(U) + HAM(S) + VIP. Mahagathbandhan: RJD + INC + CPI-ML-L + CPI + CPI(M). LJP outside NDA. |
| 7 | `assembly-2021` (Tamil Nadu — separate from WB which is Phase 1 already) | `/tamil-nadu/elections/assembly-2021` | https://en.wikipedia.org/wiki/2021_Tamil_Nadu_Legislative_Assembly_election | ~12 | SPA: DMK + INC + CPI + CPI(M) + VCK + MDMK + IUML. AIADMK+: AIADMK + PMK + BJP + DMDK. NTK solo. |
| 8 | `assembly-2021` (Kerala) | `/kerala/elections/assembly-2021` | https://en.wikipedia.org/wiki/2021_Kerala_Legislative_Assembly_election | ~12 | LDF: CPI(M) + CPI + KC(M) + JD(S)-state + LJD + NSC + NCK + others. UDF: INC + IUML + KC(J) + RSP + JKC. NDA: BJP + BDJS. |

### Q3 — State Assemblies (recent, post-2024)

| # | Event | URL | Wikipedia primary | Estimated rows | Notes |
| - | --- | --- | --- | :---: | --- |
| 9 | `assembly-2024` (Jammu & Kashmir) | `/jammu-and-kashmir/elections/assembly-2024` | https://en.wikipedia.org/wiki/2024_Jammu_and_Kashmir_Legislative_Assembly_election | ~8 | INDIA bloc: JKNC + INC + CPI(M). PDP solo. BJP solo. Apni Party solo. |
| 10 | `assembly-2024` (Haryana) | `/haryana/elections/assembly-2024` | https://en.wikipedia.org/wiki/2024_Haryana_Legislative_Assembly_election | ~5 | BJP solo. INC + AAP coalition (limited). JJP solo. INLD solo. |
| 11 | `assembly-2025` (Delhi) | `/delhi/elections/assembly-2025` | https://en.wikipedia.org/wiki/2025_Delhi_Legislative_Assembly_election | ~4 | BJP solo. AAP solo. INC solo. (Pre-poll INDIA pact broke before polling.) |
| 12 | `assembly-2025` (Bihar) | `/bihar/elections/assembly-2025` | https://en.wikipedia.org/wiki/2025_Bihar_Legislative_Assembly_election | ~12 | NDA + Mahagathbandhan composition shifts post-2020 (JD(U) realignment; LJP-RV / LJP-PP split). |

## Per-PR workflow

For each event:

1. **Open per-event handover-doc** at `TODO/20260612-alliance-backfill-q<N>-<event>.md` with: Wikipedia article URL + retrieval date + verbatim "Parties and alliances" section quote + per-party alliance assignments (party_id → alliance).
2. **Hans curation review** — explicit sign-off in the handover-doc ledger ("Hans review 2026-XX-XX: composition consistent with Wikipedia as of <vintage>; outside-support cases handled as: <verdict>").
3. **Implementation PR** authored by a subagent: append rows to `datasets/data/entities/party_alliances.csv` + one new source.csv row per (producer, title, vintage) triple via `derive_source_id`.
4. **Gates:** Tier-A schema validator + vitest + playwright + §13 browser smoke on the just-lit-up event page.
5. **Squash-merge** + post-merge cleanup.

## Out of scope (Phase 2 plan-docs)

- Pre-2009 LS events (general-2004, general-1999, etc.) — methodology unstable, Wikipedia coverage thinner, deferred.
- Pre-2014 state assembly events — same reasoning.
- Per-state slice of national LS alliances (e.g. NDA-Bihar-2019 carried LJP as state constituent that national-Wikipedia doesn't break out per-state) — Phase 2 if citizen interest warrants.
- Map filter by alliance (new `cellTreatment` mode `"alliance_won"`) — see Max R4.4; ~165 LOC; Phase 2 chart-extension plan-doc.
- Partial-attribution inline copy on `AllianceTotals` ("Some smaller parties are uncategorised…") — Jony Phase 1b polish; bundle when convenient.
- Alliance-tag layout overflow on long labels in `PartyBar` — Jony polish; bundle when convenient.
- Year-suffix discipline retrofit on state-event alliance names — revisit after this queue ships.

## Curator role

Until a sustained curator is named, each Q-row falls to whoever opens the per-event handover-doc + cites Wikipedia + secures Hans review. Estimated effort: ~1-2 hours per (state, event) tuple per Max R5.3.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-12 | open | Plan-doc opened alongside Phase 1 implementation plan. 11 events queued across Q1/Q2/Q3. Wikipedia confirmed as Phase 1b source per Hans+Max joint verdict. |
| 2026-06-12 | Q1 partial | Q1.1 (general-2019) + Q1.2 (general-2014) shipped (55 alliance rows + 2 source.csv rows). Q1.3 (general-2009) deferred per Hans R5.3 STOP-AND-SURFACE (Third Front + Fourth Front composition ambiguous; TRS joined NDA mid-poll then disavowed; SP+RJD+LJP Fourth Front simultaneously declared UPA support). See per-event handover-docs: [Q1.1](./20260612-alliance-backfill-q1-general-2019.md) + [Q1.2](./20260612-alliance-backfill-q1-general-2014.md) + [Q1.3-deferred](./20260612-alliance-backfill-q1-general-2009-deferred.md). |
| 2026-06-13 | Q2 partial | 5 of 6 Q2 events shipped (68 alliance rows + 5 source.csv rows): MH AE 2019 (user-named priority, 11 rows: Mahayuti 2 + Maha Aghadi 5 + unallied 4), KA AE 2023 (3 unallied solos; no pre-poll alliances per Wikipedia), UP AE 2022 (12 rows: NDA 3 + SP+ 7 + unallied 2), TN AE 2021 (25 rows: SPA 9 + AIADMK+ 5 + AMMK+ 4 + unallied 7; MNM+ dropped per partial-coverage doctrine), KL AE 2021 (17 rows: LDF 9 + UDF 5 + NDA 3). BR AE 2020 DEFERRED per CLAUDE.md §10 STOP-AND-SURFACE — Vikassheel Insaan Party (Mukesh Sahani's VIP) with 11 contested seats in NDA is NOT in `datasets/data/entities/parties.csv` (parties.IN.VIP maps to a different "Vanchitsamaj Insaaf Party"). Per-event handover-docs: [Q2.1](./20260612-alliance-backfill-q2-maharashtra-assembly-2019.md) + [Q2.2](./20260612-alliance-backfill-q2-karnataka-assembly-2023.md) + [Q2.3](./20260612-alliance-backfill-q2-uttar-pradesh-assembly-2022.md) + [Q2.4-deferred](./20260612-alliance-backfill-q2-bihar-assembly-2020-deferred.md) + [Q2.5](./20260612-alliance-backfill-q2-tamil-nadu-assembly-2021.md) + [Q2.6](./20260612-alliance-backfill-q2-kerala-assembly-2021.md). |
