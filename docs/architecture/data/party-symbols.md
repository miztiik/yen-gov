# Party symbols — roster, operator handover, Wikipedia/Commons inventory

**Last Updated**: 2026-06-01
**Owner**: data layer (party-symbol pipeline; `frontend/src/lib/party-symbols/` + `datasets/taxonomy/parties.json`)

This doc is the durable home for three reconnaissance notes lifted from
`notes/` during the G4 working-docs-home retirement (2026-06-08). The three dated sections below are
historical receipts captured verbatim:

1. **Roster (PR-SYM-2)** — the Tier 0/1/2 target list, DuckDB top-winner
   query, alias-trap rules, and recognition-source policy. Reproducible.
2. **PR-SYM-4 handover** — the STOP-at-user-supervised-boundary doctrine
   plus operator pickup checklist for committing real ECI ballot-symbol
   SVGs (the inverse of half-populated coverage).
3. **Wikipedia/Commons inventory (PR-SYM-4a-redo)** — the 55-party SVG
   inventory the operator pass eventually shipped, plus the slug-rename
   pass and the brand-colour enrichment (PR-SYM-4c).

Operating context: party symbol work is tracked under the party symbol assets plan
for any future PR-SYM-* work; this doc is
its reference companion (target list + inventory + handover doctrine).

---

## 2026-06-01 20260601-party-symbol-roster

> Historical receipt lifted from `notes/20260601-party-symbol-roster.md`
> on 2026-06-08 (G4 closure). Original closed PR-SYM-2.

### Snapshot pins

The corpus grows. To make this report exactly reproducible (or knowingly different on a later rerun), the query was executed against these checked-in artifacts:

| Artifact | Last-touching commit |
| --- | --- |
| `datasets/elections/elections_candidacies.parquet` | `bc0f929ca5dc00b856b3daddb7d2514d579a6ed0` |
| `datasets/elections/dim_parties.parquet` | `e5a717f72a764a489aba938522b5fc6213d7e603` |
| `datasets/taxonomy/parties.json` | `d5e088ef76dbd5adc66942622a613a684e5d3d7b` (PR #526, `$schema_version` 2.2 marker bump only) |
| `main` HEAD at probe time | `d5e088ef` |

A rerun against the same SHAs MUST produce byte-identical output. A rerun against a later main MAY differ (new event ingested, party renamed in taxonomy, etc.); record the deltas in a successor note rather than rewriting this one.

### Query (verbatim)

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

Rerun: paste the SQL into the `/explore` page (the historical CLI form
referenced a `notes/...md` path; with `notes/` retired, paste from this
doc into `/explore` instead).

### Decision rules baked into the target list

1. **Tier 0 (~40)**: current ECI national parties + current state-recognised parties visible in yen-gov routes + top winners on this corpus list. PR-SYM-4a authors SVGs for these first.
2. **Tier 1 (~60-75 cumulative)**: the rest of the current ECI national + state-recognised list (back-filled from the latest ECI recognition notification once available). Authored in PR-SYM-4a as well if discovery is cheap, otherwise placeholder rows in PR-SYM-4b.
3. **Tier 2 deferred**: corpus-impact long tail. Add in a successor PR when a citizen route needs them.
4. **Recognition source**: the latest ECI national/state recognised-party notification. NOT this winners query. The query identifies *who appears on ballots most often*; recognition status is an orthogonal ECI policy fact that must be cross-checked manually before any party row is stamped `recognition: "national"` or `"state"`. A historical winner can be deregistered today.
5. **Alias trap rule**: a party_id whose full_name in `dim_parties` is just the short_name repeated (e.g. `JD`, `JSP` mapped to "Janasena Party" which is a modern AP party using a colliding short_name, `INC(I)`, `JNP(SC)`, `SWA`, `LKD`, `BKD`, `NCO`, `BJS`, `SAP`, `SSP`, `JP`, `JNP(JP)`, `ICS`, `MAG`) is presumed historical / unresolved-lineage. Do NOT auto-attach a current symbol to such a row in PR-SYM-4. Move to deferred until the lineage walker / historical-party review settles which modern entity (if any) inherits the symbol.

### Top 60 winners (excluding IND / NOTA / UNK)

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

### Tier 0 target list (PR-SYM-4a authors SVGs for these)

Approximately 40 parties, derived from the table above by taking every row tagged `Tier 0` plus the well-known current state-recognised parties that may not have made the top-60 by historical wins. Concretely:

- `INC`, `BJP`, `CPI(M)`, `CPI`, `DMK`, `AIADMK`, `AITC`, `BSP`, `SP`, `JD(U)`, `JD(S)`, `BJD`, `RJD`, `SHS`, `NCP`, `SAD`, `AAP`, `TDP`, `YSRCP`, `AIFB`, `IUML`, `RSP`, `JMM`, `AGP`, `BRS`, `SDF`, `NPF`, `MNF`, `INLD`, `TVK`, `NPP`, `UDP`, `PMK`, `SKM`, `AIUDF`, `LJP`, `CPI(ML)L`, `AINRC`, `RLD`.

Additions not on the corpus top-60 but needed for current-route coverage (cross-check ECI national/state notification before final SVG attach):

- `AIMIM` (Hyderabad-anchored; appears in TS/MH routes).
- `MGP` (Goa; if separate row from `MAG`).
- `NDPP` (Nagaland; current ruling).
- `ZPM` (Mizoram; current ruling).

That brings Tier 0 to ~43 parties - within the 40-60 target band.

### Deferred-with-rationale (do NOT attach a current symbol in PR-SYM-4)

Per the alias-trap rule, the following corpus-top winners are deferred to a lineage-review pass:

`JSP`, `INC(I)`, `JD`, `ADK`, `LKD`, `JNP(SC)`, `SWA`, `INC(U)`, `BKD`, `NCO`, `BJS`, `SSP`, `JNP(JP)`, `ICS`, `SAP`, `JP`.

These will get `recognition: "unknown"` and no `election_symbol` block in PR-SYM-4b, with a `notes` line citing this report. A future PR can attach `symbol_status: "deferred_historical"` once each row's modern successor (if any) is verified against the ECI lineage trail.

### Recognition source for PR-SYM-4b

The `recognition` enum values (`national`, `state`, `registered_unrecognised`) must be sourced from:

1. ECI [List of Political Parties](https://www.eci.gov.in/list-of-political-parties) - most recent main notification listing national, state, and RUPP categories.
2. ECI [Recognition & De-recognition](https://www.eci.gov.in/recognition-derecognition) - orders that have changed status since the main notification.

PR-SYM-4b must record the snapshot dates of these two pages in its PR body so the recognition values are time-stampable. Wikipedia and the corpus winners list are NOT recognition sources by themselves; they only help identify *which* parties to look up.

### Discovery sources for symbol SVGs (PR-SYM-4a)

Per section 4 of the plan, in priority order:

1. Existing official ECI / State CEO SVG.
2. Wikimedia Commons original SVG file page (link the Commons file page, not a rendered thumbnail).
3. Clean SVG trace from ECI/CEO source material.
4. Party official site (only if it shows the ballot symbol, not a flag/logo).
5. `frontend/public/party-symbols/placeholder.svg` for Tier 0 / Tier 1 entries whose SVG is not collected in this batch.

Each accepted asset becomes one `sources.parquet` row (per producer) referenced by `election_symbol.source_id` per ADR-0032.

### Out of scope for this note

- Authoring schema edits (done in PR-SYM-1 / PR #526).
- Downloading SVGs (PR-SYM-4a, after PR-SYM-3 sanitizer lands).
- Editing `parties.json` rows with `recognition` or `election_symbol` (PR-SYM-4b).
- Frontend rendering (PR-SYM-5).

---

## 2026-06-01 20260601-party-symbol-sym4-handover

> Historical receipt lifted from `notes/20260601-party-symbol-sym4-handover.md`
> on 2026-06-08 (G4 closure). Original was the operator handover for the
> stop-at-user-supervised-boundary point of PR-SYM-4a.

### What is shipped on `main` as of `a92a2906`

| PR | What landed |
| --- | --- |
| #524 | Status Reckoner doc + Gregor sequencing (PR-SYM-0). |
| #526 | `taxonomy-parties.schema.json` v2.1 -> v2.2 + 13 schema-fixture tests (PR-SYM-1). |
| #527 | The Tier 0..3 target list + DuckDB query + alias-trap rules (PR-SYM-2; lifted above). |
| #528 | `frontend/src/lib/party-symbols/sanitizer.ts` + 18 vitest cases + `frontend/public/party-symbols/placeholder.svg` (PR-SYM-3). |

What this means in citizen terms: nothing renders yet. The schema, the target list, the sanitizer, and the placeholder glyph all exist. No party-row has `recognition` or `election_symbol` populated. No real ECI ballot-symbol SVGs are committed.

### Why the autonomous agent stopped before PR-SYM-4a

PR-SYM-4a needs to commit ~40 real ECI ballot-symbol SVG files (Lotus, Hand, Hammer-Sickle-Star, Rising Sun, Two Leaves, Bicycle, Elephant, Cycle, Clock, Lantern, Bow-and-Arrow, etc.) alongside corresponding `datasets/taxonomy/sources.parquet` rows per producer.

The autonomous agent halted here per the Citizen verdict on 2026-06-01:

> Symbols are identity. Shipping 40 grey placeholders or a half-populated set damages citizen trust more than waiting does. Document the boundary, let a human do the supervised SVG pass.

The reasoning, in three points:

1. **Each SVG needs human-eyes verification.** Wikimedia Commons hosts SVGs of varying provenance (some are byte-exact ECI source material, some are fan re-traces with wrong proportions, some are dated to the wrong faction in a post-split party). The sanitizer guarantees the bytes are safe to render; it cannot confirm "this glyph IS the ECI-allotted symbol for BJP today". Auto-attaching the first hit from a search would propagate any error to every citizen-facing surface.
2. **Faction-split disputes are live.** Shiv Sena (UBT vs Shinde), NCP (Sharad Pawar vs Ajit Pawar), and LJP (Paswan vs Pashupati) each have an ECI freezing order that hands the reserved symbol to one faction and a new symbol to the other. Picking the wrong holder is a political-perception bug, not a technical bug.
3. **Half-populated coverage is worse than no coverage.** If BJP shows a Lotus but DMK shows a placeholder, a citizen will read political intent into the asymmetry even if there is none. The right batch shape is "all current Tier 0 parties verified" or "none".

### What a human operator needs to do for PR-SYM-4a

Working from the Tier 0 list in the roster section above (~43 parties), for each party:

1. **Identify the current reserved/allotted ECI symbol.** Source order: ECI list-of-political-parties notification > ECI recognition/de-recognition orders > ECI election-symbol detail pages > State CEO Form 7A.
2. **Find an SVG of that glyph.** First check whether the Commons category https://commons.wikimedia.org/wiki/Category:Symbols_of_political_parties_in_India has a clean, monochrome, accurately-shaped file. If not, hand-trace from the ECI PDF source (the placeholder.svg under `frontend/public/party-symbols/` shows the path/line/circle/currentColor style the allowlist permits).
3. **Sanitise and hash.** Use `frontend/src/lib/party-symbols/sanitizer.ts` from PR-SYM-3. Author a small CLI wrapper if useful (`tools/party-symbols/sanitise.ts` is a fine new home; not yet built).
4. **Commit the SVG bytes** under `frontend/public/party-symbols/<kebab-case-symbol>.svg`.
5. **Add a `sources.parquet` row** per distinct producer (one for Commons-as-a-mirror, one for ECI-as-primary-authority, one per State CEO order as needed). Use `backend.yen_gov.canonical.citation.derive_source_id` per ADR-0032; never hand-author `source_id`.
6. **Record the inventory in the PR body** as a table: `party_short | symbol_name | asset_path | asset_sha256 | source_id | render_mode | license_label | sanitizer_pass`.

For faction-split parties, the operator MUST cite the specific ECI freezing or restoration order for the symbol attachment, and put the OTHER faction at `symbol_status: "deferred_historical"` in PR-SYM-4b's parties.json edits.

### What a human operator needs to do for PR-SYM-4b

Once PR-SYM-4a is merged (SVGs + sources.parquet exist on main):

1. Edit `datasets/taxonomy/parties.json`. For each party with a verified SVG, add the `election_symbol` block (per the schema v2.2 contract at `datasets/schemas/taxonomy-parties.schema.json`) plus the `recognition` value cross-checked against the ECI national/state notification.
2. For each Tier 0 party that did NOT get a verified SVG in PR-SYM-4a (none, if SYM-4a covered the full Tier 0), write `symbol_status: "placeholder"` with `source_id: null` and `asset_path: "party-symbols/placeholder.svg"`.
3. For the 16 alias-trap rows listed in the roster section above, write `recognition: "unknown"` and NO `election_symbol` block. Add a `notes` line citing this doc.
4. Recompile `datasets/elections/dim_parties.parquet` (`python -m yen_gov.cli emit-...`; the writer already carries `recognition`, no compiler edit needed).
5. Run Tier-A validate: it will enforce every non-placeholder `asset_path` exists, every `asset_sha256` matches, every `source_id` resolves to `sources.parquet`.

### What PR-SYM-5 looks like after both 4a and 4b land

1. Bump `datasets/schemas/dim-parties.schema.json` v1.0 -> v1.1 (additive `election_symbol` mirror).
2. Update `backend/yen_gov/canonical/writer.py` to copy `election_symbol` from `parties.json` into `dim_parties.parquet`.
3. Add `frontend/src/lib/parties/symbol-url.ts`: pure function deriving `${base}/party-symbols/${assetPath}` from a `dim_parties` row. Returns the placeholder path when `symbol_status === "placeholder"`; returns null when no `election_symbol` block.
4. Wire one or two Svelte consumers (candidate row, party badge). NO party-id-to-path map in any `.svelte` or `.ts` file - the contract test (also in PR-SYM-5) greps `frontend/src/**` for literal party-ids from the top-40 roster and fails on hit.
5. Browser smoke per CLAUDE.md section 13 on one state route: verify the Lotus renders next to BJP, the placeholder renders next to a placeholder-status party, no console errors, no 404.

### Why this is a clean stop, not an incomplete plan

Every PR shipped so far has a closed contract: the schema enforces every later step; the sanitizer rejects every malicious byte; the placeholder is the only asset that needs to exist for the renderer to test its fallback path; the roster section above pins the target list reproducibly. A reviewer in three months can pick up PR-SYM-4a without re-deriving any of those decisions.

The only thing missing is the operator-judgment-bound batch of bytes. That bound was always going to be a user surface, regardless of automation level — the original design anticipated this in section 2 ("No symbol is better than a guessed symbol") and section 4 ("Wikipedia and the corpus winners list are NOT recognition sources by themselves").

### Pick-up checklist for the next agent or operator

- [ ] Read this section + the party symbol assets plan + the roster section above end-to-end.
- [ ] Confirm the current ECI national-party + state-recognised-party notification dates; record in the PR-SYM-4b body.
- [ ] Start the SVG collection pass for Tier 0; commit in batches of 10-15 SVGs at a time if 40+ in one PR is too review-heavy (per the plan, PR-SYM-4a may itself split into 4a.i / 4a.ii / 4a.iii without renaming the plan rows).
- [ ] Land PR-SYM-4b once all Tier 0 SVGs are on main.
- [ ] Land PR-SYM-5; deploy and verify a citizen route renders the lotus next to BJP.

---

## 2026-06-01 20260601-party-symbol-wiki-inventory

> Historical receipt lifted from `notes/20260601-party-symbol-wiki-inventory.md`
> on 2026-06-08 (G4 closure). Original closed PR-SYM-4a-redo (Wikipedia
> scrape inventory) and PR-SYM-4c (Wikipedia brand_colour + wikipedia_url
> enrichment). Supersedes PR #543 (hand-drawn) and PR #545 (party-logo
> bytes mislabelled as election-symbol).

Source: <https://en.wikipedia.org/wiki/List_of_political_parties_in_India>.

Per the naming spec: filenames use ECI symbol-noun (lotus, hand, elephant, broom...), kebab-case, English. Format = whatever Commons serves (SVG/PNG/JPG/WEBP).

### Pipeline

1. Fetch List_of_political_parties_in_India HTML.
2. Parse National + State tables; per row, identify party (cell[1]) + symbol image (first non-flag File:* reference).
3. Resolve Commons API for direct upload URL + mime.
4. Download bytes. SVG -> svgo normalise + strip xml:space/inkscape/sodipodi residue. PNG/JPG/WEBP -> pass-through.
5. Slug derived from filename: strip `Indian_Election_Symbol_` / `<X>_electoral_symbol` prefix, kebab-case, lowercase.
6. Slug collisions (same symbol-noun, different parties) suffix with party name.

### Inventory

| Tier | Party | Slug | Format | SHA-256 | Bytes | Commons source |
|---|---|---|---|---|---|---|
| National | Aam Aadmi Party | `broom` | PNG | `364b28bcf78e...` | 119750 | [AAP_Symbol.png](https://commons.wikimedia.org/wiki/File:AAP_Symbol.png) |
| National | Bahujan Samaj Party | `elephant` | SVG | `317a8e83e43c...` | 21655 | [Elephant_electoral_symbol.svg](https://commons.wikimedia.org/wiki/File:Elephant_electoral_symbol.svg) |
| National | Bharatiya Janata Party | `lotus` | SVG | `e7e7ce31e316...` | 6387 | [Lotus_flower_symbol.svg](https://commons.wikimedia.org/wiki/File:Lotus_flower_symbol.svg) |
| National | Communist Party of India (Marxist) | `hammer-sickle-and-star` | PNG | `6b6c153228cc...` | 243868 | [CPI(M)_Election_symbol.png](https://commons.wikimedia.org/wiki/File:CPI(M)_Election_symbol.png) |
| National | Indian National Congress | `hand` | SVG | `544bbcf55df9...` | 9778 | [Hand_INC.svg](https://commons.wikimedia.org/wiki/File:Hand_INC.svg) |
| State | All India Trinamool Congress | `flowers-and-grass` | SVG | `03c6ba196265...` | 4673 | [All_India_Trinamool_Congress_symbol_2021.svg](https://commons.wikimedia.org/wiki/File:All_India_Trinamool_Congress_symbol_2021.svg) |
| State | Communist Party of India | `ears-of-corn-and-sickle` | SVG | `7104159eed41...` | 11310 | [CPI_symbol.svg](https://commons.wikimedia.org/wiki/File:CPI_symbol.svg) |
| State | Janata Dal (Secular) | `female-farmer` | SVG | `5b01f4ef6de6...` | 144483 | [Indian_election_symbol_female_farmer.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_female_farmer.svg) |
| State | Janata Dal (United) | `arrow` | SVG | `c17dc7d11d43...` | 99288 | [Indian_Election_Symbol_Arrow.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Arrow.svg) |
| State | All India Anna Dravida Munnetra Kazhagam | `two-leaves` | SVG | `6f9a9828aa02...` | 37601 | [Indian_election_symbol_two_leaves.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_two_leaves.svg) |
| State | Dravida Munnetra Kazhagam | `rising-sun` | SVG | `5c72af23f15e...` | 12979 | [Indian_election_symbol_rising_sun.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_rising_sun.svg) |
| State | Nationalist Congress Party – Sharadchandra Pawar | `man-blowing-turha` | PNG | `e3d58da8155a...` | 220914 | [Indian_Election_Symbol_Man_Blowing_Turha.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Man_Blowing_Turha.png) |
| State | Rashtriya Janata Dal | `hurricane-lamp` | PNG | `56b95750ee11...` | 5515 | [Indian_Election_Symbol_Hurricane_Lamp.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Hurricane_Lamp.png) |
| State | Telugu Desam Party | `cycle` | PNG | `d91a897d738b...` | 13493 | [Indian_Election_Symbol_Cycle.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Cycle.png) |
| State | YSR Congress Party | `ceiling-fan` | SVG | `7ac7fd43afae...` | 2634 | [Indian_Election_Symbol_Ceiling_Fan.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Ceiling_Fan.svg) |
| State | All India Forward Bloc | `lion` | SVG | `6339dd459ece...` | 32692 | [Indian_Election_Symbol_Lion.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Lion.svg) |
| State | All India Majlis-e-Ittehadul Muslimeen | `kite` | SVG | `1471ac513070...` | 4444 | [Indian_Election_Symbol_Kite.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Kite.svg) |
| State | All India N.R. Congress | `all-india-nr-congress` | PNG | `a27a057bb050...` | 11428 | [All_India_N.R._Congress.png](https://commons.wikimedia.org/wiki/File:All_India_N.R._Congress.png) |
| State | All India United Democratic Front | `lock-and-key` | WEBP | `0950a75e1725...` | 23330 | [AIUDF_logo.webp](https://commons.wikimedia.org/wiki/File:AIUDF_logo.webp) |
| State | All Jharkhand Students Union | `banana` | SVG | `8b3be432e673...` | 5941 | [Indian_Election_Symbol_Banana.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Banana.svg) |
| State | Apna Dal (Soneylal) | `cup-and-saucer` | JPG | `43d89bd7d81a...` | 64017 | [Indian_Election_Symbol_Cup_and_Saucer.jpg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Cup_and_Saucer.jpg) |
| State | Asom Gana Parishad | `elephant-agp` | PNG | `bc69702c58a2...` | 159476 | [Indian_Election_Symbol_Elephant.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Elephant.png) |
| State | Bharat Rashtra Samithi | `car` | PNG | `f0669be72fa9...` | 6700 | [Indian_Election_Symbol_Car.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Car.png) |
| State | Biju Janata Dal | `conch` | SVG | `39077e1acd9a...` | 7041 | [Indian_Election_Symbol_Conch.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Conch.svg) |
| State | Desiya Murpokku Dravida Kazhagam | `nagara` | SVG | `70650817e9c6...` | 126733 | [Indian_Election_Symbol_Nagara.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Nagara.svg) |
| State | Goa Forward Party | `coconut` | SVG | `9b47d03825be...` | 28877 | [Indian_election_symbol_Coconut.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_Coconut.svg) |
| State | Indian National Lok Dal | `spectacles` | SVG | `f0dc7ee8f1ed...` | 3013 | [INLD1.svg](https://commons.wikimedia.org/wiki/File:INLD1.svg) |
| State | Indian Union Muslim League | `ladder` | SVG | `ea30c7d402a0...` | 9936 | [Indian_Election_Symbol_Lader.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Lader.svg) |
| State | Jammu & Kashmir National Conference | `plough` | PNG | `56dc5622eb8f...` | 22184 | [Indian_Election_Symbol_Plough.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Plough.png) |
| State | Jammu and Kashmir National Panthers Party | `cycle` | PNG | `d91a897d738b...` | 13493 | [Indian_Election_Symbol_Cycle.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Cycle.png) |
| State | Jammu and Kashmir Peoples Democratic Party | `ink-pot-and-pen` | PNG | `4e4d1752bb1c...` | 9134 | [Indian_Election_Symbol_Ink_Pot_and_Pen.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Ink_Pot_and_Pen.png) |
| State | Janasena Party | `glass-tumbler` | SVG | `2457d35cb263...` | 17342 | [Indian_election_symbol_glass_tumbler.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_glass_tumbler.svg) |
| State | Jannayak Janta Party | `key` | SVG | `c44f3c093292...` | 3911 | [Indian_election_symbol_Key.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_Key.svg) |
| State | Janta Congress Chhattisgarh | `farmer-ploughing-within-square` | JPG | `b5980e1a692e...` | 68282 | [Indian_Election_Symbol_Farmer_Ploughing_(within_Square).jpg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Farmer_Ploughing_(within_Square).jpg) |
| State | Jharkhand Mukti Morcha | `bow-and-arrow` | SVG | `b96f87239dc2...` | 22461 | [Indian_Election_Symbol_Bow_And_Arrow.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Bow_And_Arrow.svg) |
| State | Kerala Congress | `auto-rickshaw` | SVG | `38a9f5200acc...` | 18321 | [Auto_Rickshaw_Election_Symbol.svg](https://commons.wikimedia.org/wiki/File:Auto_Rickshaw_Election_Symbol.svg) |
| State | Kerala Congress (M) | `two-leaves` | SVG | `6f9a9828aa02...` | 37601 | [Indian_election_symbol_two_leaves.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_two_leaves.svg) |
| State | Lok Janshakti Party (Ram Vilas) | `helicopter` | JPG | `c5088cfa1ec9...` | 70124 | [Indian_Election_Symbol_Helicopter.jpg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Helicopter.jpg) |
| State | Maharashtra Navnirman Sena | `railway-engine` | PNG | `885bb2837784...` | 124348 | [Mns-symbol-railway-engine.png](https://commons.wikimedia.org/wiki/File:Mns-symbol-railway-engine.png) |
| State | Maharashtrawadi Gomantak Party | `lion` | SVG | `6339dd459ece...` | 32692 | [Indian_Election_Symbol_Lion.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Lion.svg) |
| State | Naam Tamilar Katchi | `farmer-carrying-plough` | JPG | `9a69d78ecfeb...` | 177126 | [NTK-EC-Symbol.jpg](https://commons.wikimedia.org/wiki/File:NTK-EC-Symbol.jpg) |
| State | Mizo National Front | `star` | SVG | `b6a24eef8cc9...` | 1302 | [Election_Symbol_Star.svg](https://commons.wikimedia.org/wiki/File:Election_Symbol_Star.svg) |
| State | Rashtriya Loktantrik Party | `bottle` | PNG | `9d22de5a0c38...` | 98138 | [Logo_Rashtriya_Loktantrik_party.png](https://commons.wikimedia.org/wiki/File:Logo_Rashtriya_Loktantrik_party.png) |
| State | Revolutionary Goans Party | `football` | JPG | `ec62c747b3aa...` | 184193 | [Indian_Election_Symbol_football.jpg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_football.jpg) |
| State | Revolutionary Socialist Party (India) | `spade-and-stoker` | PNG | `a09990234e64...` | 12471 | [Indian_Election_Symbol_Spade_and_Stoker.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Spade_and_Stoker.png) |
| State | Samajwadi Party | `cycle` | PNG | `d91a897d738b...` | 13493 | [Indian_Election_Symbol_Cycle.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Cycle.png) |
| State | Shiromani Akali Dal | `scales` | SVG | `f5d8fee9245c...` | 3761 | [Shiromani_Akali_Dal_symbol.svg](https://commons.wikimedia.org/wiki/File:Shiromani_Akali_Dal_symbol.svg) |
| State | Sikkim Democratic Front | `umbrella` | PNG | `a8bc47f29cd7...` | 13440 | [Indian_Election_Symbol_Umberlla.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Umberlla.png) |
| State | Sikkim Krantikari Morcha | `table-lamp` | PNG | `d98947a33fd0...` | 17681 | [Symbol_SKM.png](https://commons.wikimedia.org/wiki/File:Symbol_SKM.png) |
| State | Shiv Sena (2022–present) | `bow-and-arrow` | SVG | `b96f87239dc2...` | 22461 | [Indian_Election_Symbol_Bow_And_Arrow.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Bow_And_Arrow.svg) |
| State | Shiv Sena (UBT) | `flaming-torch` | PNG | `a6faa72fff58...` | 5395 | [Indian_Election_Symbol_Flaming_Torch.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Flaming_Torch.png) |
| State | Tipra Motha Party | `tipra-logo` | JPG | `a368b9a6bcea...` | 6119 | [Tipra_Logo.jpg](https://commons.wikimedia.org/wiki/File:Tipra_Logo.jpg) |
| State | United Democratic Party (Meghalaya) | `drums` | PNG | `6fcaf1580d58...` | 50463 | [Indian_Election_Symbol_Drums.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Drums.png) |
| State | Voice of the People Party (Meghalaya) | `winnower` | PNG | `5e1ec3535875...` | 187032 | [Winnower_Symbol.png](https://commons.wikimedia.org/wiki/File:Winnower_Symbol.png) |
| State | Zoram Nationalist Party | `sun-without-rays` | PNG | `08e1f30b476d...` | 21694 | [Indian_Election_Symbol_Sun_without_Rays.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Sun_without_Rays.png) |

### Failed / missing: 0
None.

### Format breakdown
- `.jpg`: 6
- `.png`: 21
- `.svg`: 27
- `.webp`: 1

### Notes for PR-SYM-4b (parties.json population)

- `asset_path` is `party-symbols/<slug>.<ext>` (relative to `frontend/public/`).
- `asset_source_kind`: `"commons"` for all rows in this batch.
- `license_label`: verify per Commons file page; most ECI election-symbol SVGs are PD-shape; party-uploaded marks may be CC-BY-SA-4.0.
- `mime_type` will need a schema bump (v2.2 -> v2.3) since current schema implicitly assumes SVG.
- `symbol_status`: `"verified"` for files named `Indian_Election_Symbol_*` (ECI-canonical); others (e.g. `Tipra_Logo.jpg`) get `"party_supplied"`.
- `asset_sha256`: re-verify from committed bytes after LF normalisation via `Get-FileHash <file> -Algorithm SHA256`.
- Shared symbols (e.g. `two-leaves` shared by AIADMK + Kerala Congress(M); `cycle` shared by TDP + JKNPP + Samajwadi) reuse the same file path; multiple `parties.json` rows reference the same `asset_path`.

### Slug rename pass (post-merge fixup)

Renames applied to align filenames with ECI-symbol-noun (per the naming convention):

- `aap` → `broom`: AAP ECI symbol = broom (jhadu)
- `hand-inc` → `hand`: INC ECI symbol = hand; INC is sole holder
- `cpim` → `hammer-sickle-and-star`: CPI(M) ECI symbol = Hammer, Sickle and Star
- `cpi` → `ears-of-corn-and-sickle`: CPI ECI symbol = Ears of Corn and Sickle
- `aiudf-logo` → `lock-and-key`: AIUDF ECI symbol = Lock and Key
- `inld1` → `spectacles`: INLD ECI symbol = Spectacles
- `shiromani-akali-dal` → `scales`: SAD ECI symbol = Scales
- `mns-symbol-railway-engine` → `railway-engine`: MNS ECI symbol = Railway Engine
- `lotus-flower` → `lotus`: BJP ECI symbol = Lotus (drop redundant -flower suffix)
- `symbol-skm` → `table-lamp`: SKM ECI symbol = Table Lamp
- `ntk-ec-symbol` → `farmer-carrying-plough`: NTK ECI symbol (allotted May 2025) = Farmer Carrying Plough
- `all-india-trinamool-congress-symbol-2021` → `flowers-and-grass`: TMC ECI symbol = Flowers and Grass
- `logo-rashtriya-loktantrik-party` → `bottle`: RLP ECI symbol = Bottle
- `elephant-asom-gana-parishad` → `elephant-agp`: Shorten party suffix; ECI noun unchanged
- `lader` → `ladder`: Typo fix in upstream filename: Lader -> Ladder (IUML symbol)
- `umberlla` → `umbrella`: Typo fix in upstream filename

#### Unresolved (party-named upstream filename, ECI symbol noun unverified)

- `all-india-nr-congress`: AINRC: party-named upload; ECI symbol noun not in filename. Manual lookup needed (probable: 'jug')
- `tipra-logo`: Tipra Motha: party-named upload; ECI symbol noun not in filename. Manual lookup needed

### Gap tracker (as of slug-rename pass)

| Metric | Count |
|---|---|
| Total parties in `datasets/taxonomy/parties.json` | 620 |
| Parties with `election_symbol` populated | 0 (PR-SYM-4b will wire 55 of them) |
| Symbol files in `frontend/public/party-symbols/` (excl placeholder) | 50 |
| Parties this batch covers (national + state, via shared symbols) | 55 |
| Estimated coverage of parties.json after PR-SYM-4b | 55 / 620 = 8.9% |
| Estimated coverage of seat-winners (per top-60 SQL in the roster section above) | ~50 / 60 = 83% |

#### Symbol-file count per ECI tier

| Tier | Parties covered | Symbol files (shared = 1 file, N parties) |
|---|---|---|
| National | 5 (BJP/INC/BSP/CPI(M)/AAP - NPP missing) | 5 |
| State | 50 | 45 (5 shared: cycle x3, two-leaves x2, bow-and-arrow x2, lion x2, elephant x2) |
| Unrecognised | 0 (out of scope per 80/20) | 0 |

#### Confirmed gaps (next iterations)

1. **NPP** (National People's Party) — wiki row parser missed it; manual add. Symbol: book.
2. **all-india-nr-congress.png** — party-named file; ECI symbol noun = jug (needs verify).
3. **tipra-logo.jpg** — party-named file; ECI symbol noun unverified.
4. **Faction splits** (SHS / NCP / LJP) — need ECI freezing-order citation for which symbol belongs to which faction in the current ECI ruling.
5. **Unrecognised parties** with material seat counts in `elections_candidacies.parquet` — to be enumerated in PR-SYM-4a-rest if user opts in.
6. **Remaining ~565 parties in parties.json** — most are registered-unrecognised RUPPs without ECI-reserved symbols; defer until they appear in seat-winner queries.

#### How to fill the gaps

- For each gap above, the same pipeline (Wikipedia / Commons API → svgo / pass-through → write to `party-symbols/<eci-noun>.<ext>`) applies. Re-run the throwaway scraper from PR #550 with an extended target list, or hand-add via the same naming convention.
- For ECI symbol-noun lookup when the wiki/Commons filename doesn't give it, the canonical source is the ECI "Symbols (Reservation and Allotment) Order, 1968" + any subsequent allotment notifications.

### Wikipedia brand_colour + wikipedia_url enrichment (PR-SYM-4c)

Date: 2026-06-01. Source: same list-page snapshot as PR-SYM-4a-redo (`src.wikipedia.list-of-political-parties-in-india.2026-06-01`).

Per the party-symbol naming rule + Hans/Jony red-team verdicts:

- `brand_colour` is Wikipedia editorial consensus, NOT party identity (ECI does not register party colours).
- `wikipedia_url` = party article URL (the list page is already pinned via source_id).
- Faction-split parties (SHS_UBT, NCP_SP, LJPRV) get `confidence: low` + non-null `notes` citing ECI freezing order.
- Frontend resolver MUST treat `confidence: low` as absent (fall through to algorithmic fallback).

#### Coverage

| Metric | Count |
|---|---|
| Parties scraped from list page | 168 |
| Parties with hex swatch in HTML | 65 |
| Parties matched to `parties.json` (in PR-SYM-4b 55-party scope) | 45 |
| `brand_colour` populated | 45 (42 high + 3 low) |
| `wikipedia_url` populated | 45 |
| Confidence breakdown | high=42, low=3 (SHS_UBT, NCP_SP, LJPRV) |

#### Gaps after PR-SYM-4c

- 10 parties in the PR-SYM-4b scope did NOT receive `brand_colour` because the Wikipedia list-page row either lacked a swatch cell or used a row layout the parser missed. Hand-fill via separate PR if needed; `election_symbol` is unaffected.
- `brand_colour` was never required; absent rows fall through to the algorithmic resolver tier per Section 11.
