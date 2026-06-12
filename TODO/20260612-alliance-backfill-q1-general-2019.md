# Alliance backfill Q1.1 — general-2019 (17th Lok Sabha) — 2026-06-12

**Status:** SHIPPED
**Parent plan:** [TODO/20260612-alliance-phase-1b-wikipedia-backfill-queue.md](./20260612-alliance-phase-1b-wikipedia-backfill-queue.md) Q1 row 1
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §12 provenance · §10 anti-patterns (no silent demotion) · plan-doc §V2 (alliance naming) · Hans R3.4 (name-as-published) · Hans R5 (curator-led; skip when contested).

## Wikipedia source

- **Article:** `2019 Indian general election`
- **URL:** https://en.wikipedia.org/wiki/2019_Indian_general_election
- **Retrieval date:** 2026-06-12
- **Section consulted:** `## Parties and alliances` → `### Political alliances` + `## Results` (per-party seat counts)
- **Cross-reference:** https://en.wikipedia.org/wiki/National_Democratic_Alliance § Electoral performance + § Timeline § 2019 (NDA additions / departures)

### Verbatim quotes (Parties and alliances section)

> "There were three main national pre-poll alliances. They are the National Democratic Alliance (NDA) headed by the BJP, the United Progressive Alliance (UPA) headed by the INC and the Left Front of the communist leaning parties."

> "The INC did not form alliances in states where it was in direct contest with the BJP. These states included Himachal Pradesh, Uttarakhand, Rajasthan, Gujarat, Madhya Pradesh, and Chhattisgarh. It formed alliances with regional parties in Jammu and Kashmir, Bihar, Tamil Nadu, Maharashtra, Karnataka, Jharkhand, and Kerala."

> "The left parties, most notably the Communist Party of India (Marxist) contested on its own in its strongholds West Bengal, Tripura and Kerala, confronting both NDA and UPA. In Tamil Nadu, it was part of the Secular Progressive Alliance led by DMK while it was allied with the Jana Sena Party in Andhra Pradesh."

> "In January 2019, Bahujan Samaj Party and Samajwadi Party announced a grand alliance (Mahagathbandhan) to contest 76 out of the 80 seats in Uttar Pradesh leaving two seats, namely Amethi and Rae Bareli, for INC and another two for other political parties."

### Hans verdict on the Mahagathbandhan (UP)

The 2019 BSP+SP+RLD Mahagathbandhan is a STATE-LEVEL pre-poll alliance, NOT a national alliance. Per Hans R3.4 + V4 (state-disambiguation), state-level alliances belong on per-state rows, not the national `general-2019` event. Phase 1b Q2 may add it as a state-event row if/when state alliance backfill happens. This PR leaves BSP, SP, RLD unallied on `general-2019` (UPA membership was nullified by the BSP+SP+RLD UP-Mahagathbandhan opting out of UPA in UP; RLD is the exception — was UPA pre-2014, defected for UP-MGB 2019, returned to UPA in some accounts, but the Mahagathbandhan was effectively independent of UPA in UP. RLD remains unallied for general-2019.).

## NDA-2019 composition (20 parties)

Source signal: NDA Wikipedia § Timeline § 2019 + 2019 election results table (party seat counts under NDA umbrella). At time of polling (Apr-May 2019), the following parties were NDA pre-poll constituents:

| # | Party | party_id | 2019 LS seats won | Notes |
| - | --- | --- | :---: | --- |
| 1 | Bharatiya Janata Party | parties.IN.BJP | 303 | Lead party |
| 2 | Shiv Sena (then-unified, pre-2022 split) | parties.IN.SHS | 18 | Pre-split; left NDA in Nov 2019 after polls |
| 3 | Janata Dal (United) | parties.IN.JDU | 16 | Rejoined NDA Aug 2017 |
| 4 | All India Anna Dravida Munnetra Kazhagam | parties.IN.AIADMK | 1 | Joined NDA-2019 on 19 Feb 2019 (TN) |
| 5 | Lok Janshakti Party | parties.IN.LJP | 6 | Unified LJP (pre-2021 split into LJP(RV) + RLJP) |
| 6 | Shiromani Akali Dal | parties.IN.SAD | 2 | Left NDA only in Sep 2020 |
| 7 | Asom Gana Parishad | parties.IN.AGP | 0 | Rejoined NDA on 12 March 2019 (Assam) |
| 8 | Apna Dal (Soneylal) | parties.IN.ADS | 2 | UP NDA partner |
| 9 | All India N.R. Congress | parties.IN.AINRC | 0 | Puducherry NDA partner |
| 10 | Mizo National Front | parties.IN.MNF | 1 | NEDA / NE-NDA |
| 11 | Naga People's Front | parties.IN.NPF | 1 | NEDA / NE-NDA |
| 12 | National People's Party | parties.IN.NPP | 1 | NEDA / NE-NDA |
| 13 | Nationalist Democratic Progressive Party | parties.IN.NDPP | 1 | Nagaland NDA |
| 14 | Indigenous People's Front of Tripura | parties.IN.IPFT | 0 | Tripura NDA |
| 15 | Bodoland People's Front | parties.IN.BOPF | 0 | Assam NDA (left in 2020 ahead of 2021 Assam election) |
| 16 | All Jharkhand Students Union | parties.IN.AJSU | 1 | Jharkhand NDA (severed ties Nov 2019 post-LS) |
| 17 | Sikkim Krantikari Morcha | parties.IN.SKM | 1 | Joined NDA on 8 March 2019 |
| 18 | Pattali Makkal Katchi | parties.IN.PMK | 0 | Joined NDA-2019 on 19 Feb 2019 (TN) |
| 19 | Desiya Murpokku Dravida Kazhagam | parties.IN.DMDK | 0 | Joined NDA-2019 on 10 March 2019 (TN) |
| 20 | Republican Party of India (Athawale) | parties.IN.RPIA | 0 | Maharashtra NDA |

**NDA-2019 row total: 20**

## UPA-2019 composition (12 parties)

Source signal: UPA Wikipedia § Former Members (members at dissolution + members-left-before-dissolution table) + 2019 election results table.

| # | Party | party_id | 2019 LS seats won | Notes |
| - | --- | --- | :---: | --- |
| 1 | Indian National Congress | parties.IN.INC | 52 | Lead party |
| 2 | Dravida Munnetra Kazhagam | parties.IN.DMK | 24 | DMK left UPA in March 2013 over Sri Lanka; reconciled by 2019 LS (SPA alliance with DMK as lead) |
| 3 | Nationalist Congress Party | parties.IN.NCP | 5 | Unified NCP (pre-2023 split) |
| 4 | Rashtriya Janata Dal | parties.IN.RJD | 0 | Bihar UPA-aligned |
| 5 | Indian Union Muslim League | parties.IN.IUML | 3 | Kerala UDF (UPA-aligned) |
| 6 | Jharkhand Mukti Morcha | parties.IN.JMM | 1 | Jharkhand UPA |
| 7 | Jammu & Kashmir National Conference | parties.IN.JKNC | 3 | J&K UPA |
| 8 | Kerala Congress (M) | parties.IN.KECM | 1 | Kerala UDF; left in 2020 to join LDF |
| 9 | Viduthalai Chiruthaigal Katchi | parties.IN.VCK | 1 | TN SPA via DMK (UPA-aligned) |
| 10 | Marumalarchi Dravida Munnetra Kazhagam | parties.IN.MDMK | 0 | TN SPA via DMK |
| 11 | Revolutionary Socialist Party | parties.IN.RSP | 1 | Kerala UDF (UPA-aligned); listed in UPA Former Members |
| 12 | All India United Democratic Front | parties.IN.AIUDF | 1 | Assam UPA-aligned; expelled in 2021 |

**UPA-2019 row total: 12**

## Skipped parties (with reasons)

Parties that contested 2019 LS but are NOT in NDA-2019 or UPA-2019:

| Party | party_id | 2019 LS seats | Reason for skip |
| --- | --- | :---: | --- |
| All India Trinamool Congress | parties.IN.AITC | 22 | Contested WB independently; neither NDA nor UPA |
| Bahujan Samaj Party | parties.IN.BSP | 10 | UP-Mahagathbandhan state-level (with SP); NOT national UPA per Hans R3.4 state-vs-national rule |
| Samajwadi Party | parties.IN.SP | 5 | UP-Mahagathbandhan state-level (with BSP) |
| YSR Congress Party | parties.IN.YSRCP | 22 | Contested AP independently |
| Telugu Desam Party | parties.IN.TDP | 3 | Quit NDA in March 2018; contested 2019 independently in AP |
| Communist Party of India (Marxist) | parties.IN.CPIM | 3 | Contested independently in WB/KL/TR; SPA-aligned only in TN — per Hans R3.4 + R5.2 "outside support / regional bloc != UPA member" — leave unallied |
| Communist Party of India | parties.IN.CPI | 2 | Same as CPIM |
| Biju Janata Dal | parties.IN.BJD | 12 | Solo in Odisha |
| Telangana Rashtra Samithi | parties.IN.BRS (then TRS) | 9 | Solo in Telangana |
| Aam Aadmi Party | parties.IN.AAP | 1 | Contested Delhi+others independently; UPA talks failed |
| Jana Sena Party | parties.IN.JSP | 0 | AP CPI(M)-allied bloc (not UPA) |
| Shiromani Akali Dal (Mann), etc. | various | 0 | <5 seats, regional, not in NDA/UPA pre-poll declarations |
| Rashtriya Lok Dal | parties.IN.RLD | 0 | UP-Mahagathbandhan via BSP+SP; not in UPA national bloc |
| Rashtriya Lok Samta Party | parties.IN.RLSP | 0 | Left NDA in Dec 2018; allied with UPA later but Bihar-specific (skip for national row pending state-event backfill) |
| Janata Dal (Secular) | parties.IN.JDS | 1 | Karnataka INC+JD(S) alliance was state-level; left UPA after 2019 per UPA Former Members |
| Suheldev Bharatiya Samaj Party | parties.IN.SBSP | 0 | Joined NDA only in July 2023 (post-2019); not in NDA pre-poll 2019 |

## Hans curation discipline applied

- **Outside-support parties NOT counted as members** per Hans R5: CPI/CPIM/BSP/SP/RLD all sit unallied for the national general-2019 event, even though some (CPI, CPIM, RLD) had state-level UPA-style relationships in 2019. Hans's "outside support != member" rule honoured.
- **State-level alliances NOT promoted to national rows** per V4: UP-Mahagathbandhan (BSP+SP+RLD), TN-SPA (DMK+CPI+CPIM+VCK+MDMK+IUML — but DMK/IUML/VCK/MDMK are *also* UPA national members so included via that path; CPI+CPIM stay unallied on the national row).
- **Pre-poll vs post-poll discipline**: SHS exited NDA in November 2019 (AFTER LS polling); included as NDA-2019 because at time of LS polling (Apr-May 2019) it was unified-NDA. AJSU severed ties in November 2019 (AFTER LS polling); included as NDA-2019. BOPF left ahead of 2021 Assam election (AFTER LS-2019); included.
- **NCP/SHS pre-split**: Both included as `parties.IN.NCP` and `parties.IN.SHS` per the 2019-as-of policy (NCP split was 2023; SHS split was 2022).

## Source row (provenance ledger)

```
src-2d20f783ae5a,Wikipedia,2019 Indian general election,2019-05,https://en.wikipedia.org/wiki/2019_Indian_general_election
```

Derived via `backend.yen_gov.canonical.citation.derive_source_id("Wikipedia", "2019 Indian general election", "2019-05")`. All 32 NDA-2019 + UPA-2019 alliance rows carry this `source_id`.

## Acceptance gates

- **Tier-A validator** (`python -m yen_gov validate --root .`): delta=0 vs master baseline (7 pre-existing errors on `lgd-*.schema.json` + `_ops` files; none touch `party_alliances.csv` / `source.csv` / new `src-2d20f783ae5a`).
- **vitest (frontend)** (`bun run test --pool=forks --reporter=basic`): delta=0 vs master baseline. Total: 5650 passed, 15 skipped, 3 chronic-red failures (`acSlugs ⊥ stateSlugs ['chandigarh', 'bihar']`, `acSlugs ⊥ RESERVED_PATH_TOKENS ['i']`, `partySlugs ⊥ acSlugs ['amb']`) — all 3 reproduced on `origin/main` head with identical messages. The critical contract test `src/contracts/datasets-conform.test.ts` (271 tests, 1872ms) PASSED, which is the strongest validation that the new alliance + source rows are schema-conformant.

## §13 browser smoke — limitation

Smoke executed via the user-memory "copy data to master + use master's vite" pattern (worktree's bun-install had no d3-ease issue but the cleaner master vite was already known-good).

Verified:
- `/data/data/entities/party_alliances.csv` served HTTP 200 with 32 rows for `general-2019` (correct shape: `parties.IN.<code>,general-2019,IN,NDA-2019|UPA-2019,src-2d20f783ae5a`).
- `/data/data/entities/source.csv` served HTTP 200 with `src-2d20f783ae5a` row present.
- No NEW console errors versus master baseline (verified by reload-on-master-then-reload-on-worktree-data comparison).

Visual "NDA-2019 N / UPA-2019 M / Others K" headline did NOT light up on `/t/elections/general-2019` because the page shows `Total seats: 0` due to a **pre-existing chronic DuckDB-WASM CSV sniffer failure** on `/data/data/datapoints/electoral/jammu-and-kashmir_election_results.csv` ("It does not match the number of columns found by the sniffer: 1"; file is clean, 9 columns, no BOM, LF-only). Same error reproduced on `origin/main` head with identical messages on `general-2019`, `general-2024`, and `/maharashtra/elections/general-2019`. The alliance-totals model's `has_any` flag is gated by AT LEAST ONE winner row having an alliance match — when zero winners load (any cause), the "Alliance data pending" pill renders regardless of whether `party_alliances.csv` has rows for the event. This pre-existing winner-loader failure is OUT OF SCOPE for Phase 1b Q1 (which is purely a citation-ledger backfill PR). When the chronic CSV sniffer issue is fixed (separate PR), the NDA-2019 / UPA-2019 headline will light up automatically with zero code change to the alliance loader.

Forward-fix candidates: (a) DuckDB-WASM version pin in `frontend/package.json`, (b) explicit `delim=','` parameter on the inline `read_csv()` in the loader's SQL, (c) inspect whether the file has invisible-character contamination that the byte-level audit missed.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-12 | open | Q1.1 handover authored from Wikipedia main article + NDA + UPA sub-articles. |
| 2026-06-12 | shipped | 32 rows landed in `datasets/data/entities/party_alliances.csv` (NDA-2019: 20 + UPA-2019: 12) + 1 new row in `datasets/data/entities/source.csv`. Sorted by `(event_id, alliance, party_id)`. Acceptance gates green vs master baseline (delta=0); §13 smoke limited by pre-existing chronic JK CSV sniffer issue (see above). |
