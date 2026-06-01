# Party Symbol Roster - PR-SYM-2

**Created**: 2026-06-01
**Plan row**: PR-SYM-2 of [TODO/20260527-party-symbol-assets-plan.md](../TODO/20260527-party-symbol-assets-plan.md)
**Purpose**: Pick the first 40-60 parties to collect election-symbol SVGs for, without hand-picking in chat. The list below is the reproducible output of the DuckDB top-winner query against the current canonical election corpus, joined to the latest `dim_parties` view, with historical / alias-heavy rows flagged for lineage review per the plan.

## Snapshot pins

The corpus grows. To make this report exactly reproducible (or knowingly different on a later rerun), the query was executed against these checked-in artifacts:

| Artifact | Last-touching commit |
| --- | --- |
| `datasets/elections/elections_candidacies.parquet` | `bc0f929ca5dc00b856b3daddb7d2514d579a6ed0` |
| `datasets/elections/dim_parties.parquet` | `e5a717f72a764a489aba938522b5fc6213d7e603` |
| `datasets/taxonomy/parties.json` | `d5e088ef76dbd5adc66942622a613a684e5d3d7b` (PR #526, `$schema_version` 2.2 marker bump only) |
| `main` HEAD at probe time | `d5e088ef` |

A rerun against the same SHAs MUST produce byte-identical output. A rerun against a later main MAY differ (new event ingested, party renamed in taxonomy, etc.); record the deltas in a successor note rather than rewriting this one.

## Query (verbatim)

```sql
WITH cand AS (
  SELECT
    c.party_id,
    regexp_extract(c.ac_id, 'IN-(S[0-9]{2}|U[0-9]{2})-', 1) AS state_code,
    c.election_id,
    c.won,
    c.votes_polled
  FROM read_parquet('datasets/elections/elections_candidacies.parquet') c
  WHERE c.party_id IS NOT NULL
    AND c.party_id NOT IN ('parties.IN.IND', 'parties.IN.NOTA', 'parties.IN.UNK')
), agg AS (
  SELECT
    party_id,
    COUNT(*) FILTER (WHERE won) AS wins,
    COUNT(DISTINCT state_code) FILTER (WHERE won) AS win_states,
    COUNT(DISTINCT election_id) FILTER (WHERE won) AS win_events,
    COUNT(*) AS candidacies,
    SUM(votes_polled) AS total_votes
  FROM cand
  GROUP BY party_id
)
SELECT a.party_id, p.eci_code, p.short_name, p.full_name,
       a.wins, a.win_states, a.win_events, a.candidacies,
       CAST(a.total_votes AS BIGINT) AS total_votes
FROM agg a
LEFT JOIN read_parquet('datasets/elections/dim_parties.parquet') p USING (party_id)
ORDER BY a.wins DESC, a.win_states DESC, a.total_votes DESC
LIMIT 60
```

Rerun: from repo root, `python -c "import duckdb, pathlib; print(duckdb.sql(pathlib.Path('notes/20260601-party-symbol-roster.md').read_text().split('```sql')[1].split('```')[0]).fetchall())"` (or paste the SQL into the `/explore` page).

## Decision rules baked into the target list

1. **Tier 0 (~40)**: current ECI national parties + current state-recognised parties visible in yen-gov routes + top winners on this corpus list. PR-SYM-4a authors SVGs for these first.
2. **Tier 1 (~60-75 cumulative)**: the rest of the current ECI national + state-recognised list (back-filled from the latest ECI recognition notification once available). Authored in PR-SYM-4a as well if discovery is cheap, otherwise placeholder rows in PR-SYM-4b.
3. **Tier 2 deferred**: corpus-impact long tail. Add in a successor PR when a citizen route needs them.
4. **Recognition source**: the latest ECI national/state recognised-party notification. NOT this winners query. The query identifies *who appears on ballots most often*; recognition status is an orthogonal ECI policy fact that must be cross-checked manually before any party row is stamped `recognition: "national"` or `"state"`. A historical winner can be deregistered today.
5. **Alias trap rule**: a party_id whose full_name in `dim_parties` is just the short_name repeated (e.g. `JD`, `JSP` mapped to "Janasena Party" which is a modern AP party using a colliding short_name, `INC(I)`, `JNP(SC)`, `SWA`, `LKD`, `BKD`, `NCO`, `BJS`, `SAP`, `SSP`, `JP`, `JNP(JP)`, `ICS`, `MAG`) is presumed historical / unresolved-lineage. Do NOT auto-attach a current symbol to such a row in PR-SYM-4. Move to deferred until the lineage walker / historical-party review settles which modern entity (if any) inherits the symbol.

## Top 60 winners (excluding IND / NOTA / UNK)

| # | party_id | eci_code | short_name | full_name | wins | win_states | win_events | candidacies | total_votes | tier |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | parties.IN.INC | 742 | INC | Indian National Congress | 11688 | 30 | 125 | 34557 | 1,004,623,850 | Tier 0 |
| 2 | parties.IN.BJP | 369 | BJP | Bharatiya Janata Party | 8711 | 30 | 103 | 26895 | 899,368,670 | Tier 0 |
| 3 | parties.IN.CPIM | 547 | CPI(M) | Communist Party of India (Marxist) | 2309 | 19 | 78 | 5929 | 183,743,525 | Tier 0 |
| 4 | parties.IN.JSP |  | JSP | Janasena Party | 1939 | 21 | 17 | 5176 | 81,468,115 | ALIAS-TRAP (JSP slot historically also held Janata Party variants; modern JSP is Pawan Kalyan's 2014-founded AP party. Lineage review needed before symbol attach.) |
| 5 | parties.IN.INC_I |  | INC(I) | INC(I) | 1673 | 16 | 6 | 2818 | 60,404,505 | Historical (1969 INC split; absorbed back into INC). Deferred. |
| 6 | parties.IN.JD |  | JD | JD | 1206 | 19 | 17 | 4759 | 90,188,072 | Historical (Janata Dal parent; split into JD(U), JD(S), RJD, BJD, SP). Deferred. |
| 7 | parties.IN.DMK | 582 | DMK | Dravida Munnetra Kazhagam | 1120 | 2 | 19 | 2445 | 117,157,988 | Tier 0 |
| 8 | parties.IN.SP |  | SP | Samajwadi Party | 884 | 9 | 26 | 6150 | 130,373,208 | Tier 0 |
| 9 | parties.IN.AITC | 140 | AITC | All India Trinamool Congress | 802 | 6 | 12 | 2374 | 121,783,267 | Tier 0 |
| 10 | parties.IN.BSP |  | BSP | Bahujan Samaj Party | 690 | 13 | 37 | 16791 | 158,032,150 | Tier 0 |
| 11 | parties.IN.AIADMK | 75 | AIADMK | All India Anna Dravida Munnetra Kazhagam | 616 | 3 | 12 | 1430 | 83,732,874 | Tier 0 |
| 12 | parties.IN.CPI | 544 | CPI | Communist Party of India | 601 | 19 | 62 | 4769 | 58,328,422 | Tier 0 |
| 13 | parties.IN.ADK |  | ADK | ADK | 587 | 3 | 9 | 793 | 31,983,013 | ALIAS-TRAP (historical AIADMK alias before short_name canonicalised). Defer; AIADMK at row 11 already covered. |
| 14 | parties.IN.JDU |  | JD(U) | Janata Dal (United) | 542 | 11 | 26 | 2320 | 48,213,555 | Tier 0 |
| 15 | parties.IN.BJD |  | BJD | Biju Janata Dal | 512 | 1 | 6 | 737 | 45,601,126 | Tier 0 |
| 16 | parties.IN.RJD | 1420 | RJD | Rashtriya Janata Dal | 479 | 6 | 14 | 1743 | 59,624,263 | Tier 0 |
| 17 | parties.IN.SHS |  | SHS | Shiv Sena | 478 | 2 | 10 | 3400 | 62,636,114 | Tier 0 (note 2022 split: SHS vs SHS(UBT); current ECI symbol allotment lives with one faction. Check ECI freezing order before attach.) |
| 18 | parties.IN.NCP |  | NCP | Nationalist Congress Party | 441 | 18 | 35 | 3545 | 56,843,848 | Tier 0 (note 2023 split: NCP vs NCP(SP); same caveat as SHS.) |
| 19 | parties.IN.SAD |  | SAD | Shiromani Akali Dal | 412 | 3 | 13 | 873 | 29,927,226 | Tier 0 |
| 20 | parties.IN.AAP |  | AAP | Aam Aadmi Party | 299 | 5 | 8 | 2260 | 33,082,415 | Tier 0 |
| 21 | parties.IN.TDP |  | TDP | Telugu Desam Party | 277 | 2 | 5 | 570 | 44,162,552 | Tier 0 |
| 22 | parties.IN.LKD |  | LKD | LKD | 252 | 7 | 7 | 1341 | 15,586,870 | Historical (Lok Dal 1980-1988 split lineage). Defer. |
| 23 | parties.IN.YSRCP |  | YSRCP | Yuvajana Sramika Rythu Congress Party | 232 | 2 | 4 | 616 | 42,466,779 | Tier 0 |
| 24 | parties.IN.JDS |  | JD(S) | Janata Dal (Secular) | 214 | 6 | 14 | 1830 | 34,151,418 | Tier 0 |
| 25 | parties.IN.AIFB |  | AIFB | All India Forward Bloc | 212 | 6 | 19 | 957 | 18,156,794 | Tier 0 |
| 26 | parties.IN.IUML | 772 | IUML | Indian Union Muslim League | 197 | 6 | 19 | 809 | 16,702,466 | Tier 0 |
| 27 | parties.IN.RSP | 1534 | RSP | Revolutionary Socialist Party | 195 | 3 | 23 | 466 | 13,711,265 | Tier 0 |
| 28 | parties.IN.JMM |  | JMM | Jharkhand Mukti Morcha | 191 | 3 | 12 | 1042 | 19,895,752 | Tier 0 |
| 29 | parties.IN.AGP | 83 | AGP | Asom Gana Parishad | 164 | 1 | 8 | 583 | 15,355,112 | Tier 0 |
| 30 | parties.IN.BRS |  | BRS | Bharat Rashtra Samithi | 151 | 1 | 2 | 238 | 16,321,075 | Tier 0 (renamed from TRS in 2022; symbol still "Car"). |
| 31 | parties.IN.SDF |  | SDF | Sikkim Democratic Front | 140 | 1 | 7 | 219 | 928,832 | Tier 0 |
| 32 | parties.IN.NPF |  | NPF | Naga People's Front | 124 | 2 | 8 | 296 | 2,008,736 | Tier 0 |
| 33 | parties.IN.JNP_SC |  | JNP(SC) | JNP(SC) | 123 | 6 | 2 | 1158 | 11,982,109 | Historical (Janata Party Secular Chandra Shekhar). Defer. |
| 34 | parties.IN.SWA |  | SWA | SWA | 120 | 4 | 4 | 639 | 5,516,440 | Historical (Swatantra Party 1959-1974). Defer. |
| 35 | parties.IN.MNF |  | MNF | Mizo National Front | 114 | 1 | 8 | 295 | 1,243,945 | Tier 0 |
| 36 | parties.IN.INLD |  | INLD | Indian National Lok Dal | 113 | 2 | 7 | 583 | 12,174,896 | Tier 0 |
| 37 | parties.IN.TVK | 3679 | TVK | Tamilaga Vettri Kazhagam | 110 | 2 | 1 | 305 | 17,445,218 | Tier 0 (recent 2024 reg; verify reserved-symbol order). |
| 38 | parties.IN.INC_U |  | INC(U) | INC(U) | 109 | 7 | 3 | 1111 | 9,369,510 | Historical. Defer. |
| 39 | parties.IN.BKD |  | BKD | BKD | 107 | 2 | 2 | 571 | 6,174,940 | Historical (Bharatiya Kranti Dal). Defer. |
| 40 | parties.IN.NCO |  | NCO | NCO | 97 | 3 | 4 | 894 | 11,530,800 | Historical (Indian National Congress (Organisation), 1969 split). Defer. |
| 41 | parties.IN.BJS |  | BJS | BJS | 92 | 3 | 4 | 991 | 8,338,973 | Historical (Bharatiya Jana Sangh, 1951-1977; precursor to BJP). Defer. |
| 42 | parties.IN.PWP |  | PWP | PWP | 90 | 1 | 8 | 435 | 6,908,578 | Tier 1 candidate (Peasants and Workers Party of India, still active in MH). |
| 43 | parties.IN.NPP |  | NPP | National People's Party | 86 | 5 | 12 | 572 | 3,358,375 | Tier 0 (current national-recognised since 2019). |
| 44 | parties.IN.SSP |  | SSP | SSP | 83 | 2 | 5 | 201 | 944,667 | Historical (Samyukta Socialist Party). Defer. |
| 45 | parties.IN.JNP_JP |  | JNP(JP) | JNP(JP) | 77 | 10 | 5 | 1888 | 10,689,746 | Historical (Janata Party JP faction). Defer. |
| 46 | parties.IN.ICS |  | ICS | ICS | 75 | 7 | 7 | 616 | 6,375,778 | Historical (Indian Congress (Socialist)). Defer. |
| 47 | parties.IN.SAP |  | SAP | SAP | 75 | 6 | 8 | 1172 | 8,569,233 | Historical (Samata Party, 1994-2003). Defer. |
| 48 | parties.IN.TMC_M |  | TMC(M) | Tamil Maanila Congress (Moopanar) | 69 | 2 | 3 | 110 | 4,720,786 | Tier 1 candidate (reformed 2014; verify reserved symbol). |
| 49 | parties.IN.UDP |  | UDP | United Democratic Party | 65 | 1 | 6 | 272 | 1,274,622 | Tier 0 (state-recognised in ML). |
| 50 | parties.IN.KEC | 911 | KEC | Kerala Congress | 61 | 1 | 10 | 128 | 5,011,280 | Tier 1 candidate (multiple Kerala Congress factions; verify which holds reserved symbol). |
| 51 | parties.IN.PMK | 1272 | PMK | Pattali Makkal Katchi | 58 | 2 | 8 | 733 | 13,103,101 | Tier 0 |
| 52 | parties.IN.SKM |  | SKM | Sikkim Krantikari Morcha | 58 | 1 | 3 | 96 | 516,600 | Tier 0 (state-recognised in SK). |
| 53 | parties.IN.JP |  | JP | JP | 56 | 5 | 6 | 1585 | 7,766,506 | Historical (Janata Party parent). Defer. |
| 54 | parties.IN.KECM |  | KEC(M) | Kerala Congress (M) | 51 | 1 | 7 | 99 | 5,044,379 | Tier 1 candidate (Kerala Congress Mani faction). |
| 55 | parties.IN.AIUDF | 145 | AIUDF | All India United Democratic Front | 49 | 1 | 4 | 205 | 6,915,768 | Tier 0 |
| 56 | parties.IN.LJP |  | LJP | Lok Janshakti Party | 48 | 3 | 8 | 1928 | 13,322,688 | Tier 0 (note 2021 split: LJP vs LJP(RV); verify current ECI symbol holder). |
| 57 | parties.IN.CPIMLL |  | CPI(ML)L | Communist Party of India (Marxist-Leninist) Liberation | 46 | 2 | 10 | 1411 | 8,873,019 | Tier 0 |
| 58 | parties.IN.MAG |  | MAG | MAG | 46 | 1 | 8 | 185 | 748,190 | Historical (Maharashtrawadi Gomantak Party - actually still active in GA; promote to Tier 1 candidate on recheck). |
| 59 | parties.IN.AINRC | 126 | AINRC | All India N.R. Congress | 45 | 1 | 4 | 79 | 863,175 | Tier 0 (state-recognised in PY). |
| 60 | parties.IN.RLD |  | RLD | Rashtriya Lok Dal | 44 | 2 | 7 | 862 | 9,620,686 | Tier 0 |

## Tier 0 target list (PR-SYM-4a authors SVGs for these)

Approximately 40 parties, derived from the table above by taking every row tagged `Tier 0` plus the well-known current state-recognised parties that may not have made the top-60 by historical wins. Concretely:

- `INC`, `BJP`, `CPI(M)`, `CPI`, `DMK`, `AIADMK`, `AITC`, `BSP`, `SP`, `JD(U)`, `JD(S)`, `BJD`, `RJD`, `SHS`, `NCP`, `SAD`, `AAP`, `TDP`, `YSRCP`, `AIFB`, `IUML`, `RSP`, `JMM`, `AGP`, `BRS`, `SDF`, `NPF`, `MNF`, `INLD`, `TVK`, `NPP`, `UDP`, `PMK`, `SKM`, `AIUDF`, `LJP`, `CPI(ML)L`, `AINRC`, `RLD`.

Additions not on the corpus top-60 but needed for current-route coverage (cross-check ECI national/state notification before final SVG attach):

- `AIMIM` (Hyderabad-anchored; appears in TS/MH routes).
- `MGP` (Goa; if separate row from `MAG`).
- `NDPP` (Nagaland; current ruling).
- `ZPM` (Mizoram; current ruling).

That brings Tier 0 to ~43 parties - within the 40-60 target band.

## Deferred-with-rationale (do NOT attach a current symbol in PR-SYM-4)

Per the alias-trap rule, the following corpus-top winners are deferred to a lineage-review pass:

`JSP`, `INC(I)`, `JD`, `ADK`, `LKD`, `JNP(SC)`, `SWA`, `INC(U)`, `BKD`, `NCO`, `BJS`, `SSP`, `JNP(JP)`, `ICS`, `SAP`, `JP`.

These will get `recognition: "unknown"` and no `election_symbol` block in PR-SYM-4b, with a `notes` line citing this report. A future PR can attach `symbol_status: "deferred_historical"` once each row's modern successor (if any) is verified against the ECI lineage trail.

## Recognition source for PR-SYM-4b

The `recognition` enum values (`national`, `state`, `registered_unrecognised`) must be sourced from:

1. ECI [List of Political Parties](https://www.eci.gov.in/list-of-political-parties) - most recent main notification listing national, state, and RUPP categories.
2. ECI [Recognition & De-recognition](https://www.eci.gov.in/recognition-derecognition) - orders that have changed status since the main notification.

PR-SYM-4b must record the snapshot dates of these two pages in its PR body so the recognition values are time-stampable. Wikipedia and the corpus winners list are NOT recognition sources by themselves; they only help identify *which* parties to look up.

## Discovery sources for symbol SVGs (PR-SYM-4a)

Per section 4 of the plan, in priority order:

1. Existing official ECI / State CEO SVG.
2. Wikimedia Commons original SVG file page (link the Commons file page, not a rendered thumbnail).
3. Clean SVG trace from ECI/CEO source material.
4. Party official site (only if it shows the ballot symbol, not a flag/logo).
5. `frontend/public/party-symbols/placeholder.svg` for Tier 0 / Tier 1 entries whose SVG is not collected in this batch.

Each accepted asset becomes one `sources.parquet` row (per producer) referenced by `election_symbol.source_id` per ADR-0032.

## Out of scope for this note

- Authoring schema edits (done in PR-SYM-1 / PR #526).
- Downloading SVGs (PR-SYM-4a, after PR-SYM-3 sanitizer lands).
- Editing `parties.json` rows with `recognition` or `election_symbol` (PR-SYM-4b).
- Frontend rendering (PR-SYM-5).
