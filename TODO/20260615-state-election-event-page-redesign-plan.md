# State election event page redesign + MH 266->288 writer rip

**Last Updated**: 2026-06-15
**Level**: 4 (structural; touches backend writer + new frontend route + per-event page IA rework + new Sankey + alliance honesty caption)
**Status**: APPROVED-for-execution (persona debate converged 2026-06-15: Jony + Max + Fowler in DEBATE not parallel-review; user-named UX hierarchy ratified; 266->288 root-cause receipt below). Executing autonomously per the EXECUTION BLOCK in section 8.

> This plan rebuilds `/<state>/elections/<event>` (today: [frontend/src/routes/StateElection.svelte](frontend/src/routes/StateElection.svelte)) and mints the missing parent route `/<state>/elections/`. It also fixes the live `/maharashtra/elections/assembly-2024` "266 of 288" bug by switching MH 2024 onto the existing ECI Form-10 XLSX adapter (the XLSX HAS all 288 ACs; the current writer reads the wrong file). Plan-doc carries its own EXECUTION BLOCK; executing agent runs rows R1-R6 end-to-end without further dictation.

## Section 0 - Operating contract

### Why this plan exists

User reviewed the live page <https://miztiik.github.io/yen-gov/maharashtra/elections/assembly-2024> on 2026-06-15 and named seven gaps. Investigation against the actual code/data confirmed:

1. **Section IA is not citizen-first.** Today's order on [StateElection.svelte](frontend/src/routes/StateElection.svelte): Header -> Races-by-competitiveness (line ~900) -> SeatDonut+KPIs (~920) -> map (~972) -> PartyBar (~995) -> AllianceTotals (~1020) -> InlineCounterfactualSwing (~1035) -> flat constituency table (~1050) -> Scatter (~1110) -> AllPartiesDirectory (~1120) -> ConstituenciesByDistrict (~1175). User wants the Scatter ABOVE the constituency list, Races repositioned, ConstituenciesByDistrict folded + searchable, the flat 288-row table removed (redundant with the grouped surface), and a new vote-flow Sankey appended.
2. **No hero glyphs.** Today's KPI strip is text-only tiles. User wants icon glyphs for seats / voters / polled / turnout, plus a turnout-delta glyph (up/down vs previous same-body event).
3. **No semantic prev/next election navigation.** Today, the compare-CTA lives in the page header as a slate-grey link. User explicitly rules out arrows ("no ugly arrows") - wants a text-only sibling-events strip naming the prior event + its winning party.
4. **No state-assembly LANDING page.** `/<state>/elections/` returns 404 today. The indiavotes Vidhan-Sabha pattern (table of all assembly events for the state, year-as-link to detail) is the citizen's mental model and is missing.
5. **House-comp + top-parties are two separate visuals.** SeatDonut (radial) + PartyBar (horizontal) carry overlapping facts. User wants ONE composite showing seats + vote-share + alliance affiliation + party symbol per party.
6. **No cross-event vote-flow chart.** ADR-0048 (in [docs/architecture/frontend/charts/election-views.md](docs/architecture/frontend/charts/election-views.md) lines 30-65) pre-approved a 2-election capped Sankey ("top-6 parties + Others, Flow (beta), collapsed by default") - never built. [frontend/src/lib/SwingSankey.svelte](frontend/src/lib/SwingSankey.svelte) exists as the rendering primitive (used in Psephlab for actuals->scenario approximate flow) and is reusable.
7. **MH 266-of-288 data bug.** Live page shows 266 constituencies; state has 288 ACs (constitutional). Investigation receipt in section 0.2: the ECI XLSX user-named at `datasets/ephemeral/2024_MH_10-Detailed_Results_1744893339.xlsx` HAS all 288 distinct ACs (verified via openpyxl: AC NO. range 1..288, zero missing). The current writer `backend/yen_gov/canonical/adapters/thecont1_mh_ae2024.py` reads the `thecont1` GitHub mirror CSV, not the ECI XLSX, and silently drops 22 ACs that fail fuzzy-name resolution. Fix is one-row append to the existing `JOBS` tuple in `eci_form10_ae.py` + delete the thecont1 adapter (rip-and-replace).

### Hard-coded scope

In scope:

- **Backend writer**: Add MH 2024 to [backend/yen_gov/canonical/adapters/eci_form10_ae.py](backend/yen_gov/canonical/adapters/eci_form10_ae.py) JOBS tuple. Re-emit MH 2024 candidacies + summary + per-state `maharashtra_election_results.csv` to land all 288 ACs. DELETE [backend/yen_gov/canonical/adapters/thecont1_mh_ae2024.py](backend/yen_gov/canonical/adapters/thecont1_mh_ae2024.py) + its tests + its CLI registration in the SAME PR per the user-mandated rip-and-replace doctrine.
- **Frontend new route**: Mint `/<state>/elections/` -> NEW `frontend/src/routes/StateElectionsLanding.svelte`. Table of all events for the state (one row per event_id, year-as-link, body + winner + seats columns). Per-state hero of the latest event by body.
- **Frontend component extraction**: Refactor [StateElection.svelte](frontend/src/routes/StateElection.svelte) (~800 LOC) into named subcomponents (`StateEventHero.svelte`, `StateEventMap.svelte`, `StateEventPartyComposite.svelte`, `StateEventScatter.svelte`, `StateEventConstituencyList.svelte`) at the route level. STRUCTURAL ONLY in this row; behaviour unchanged.
- **Frontend behavioural reorder + new chrome**: New hero KPI strip with icon glyphs from `frontend/public/icons/` + turnout-delta glyph. NEW sibling-events strip (text-only "Prev: Assembly 2019 - BJP led | Next: (none) | Compare 2019 vs 2024 ->"). PartyComposite extends PartyBar to per-party-row table with `[symbol] [short] [alliance-chip] [seats-bar] [seats-count] [vote-share%]`. Fold + search on ConstituenciesByDistrict; integrate compare-CTA as its last row. DELETE InlineCounterfactualSwing on this surface (moved to Psephlab where it belongs); DELETE the flat 288-row constituency table (redundant with the grouped surface).
- **Frontend Sankey**: NEW `frontend/src/lib/elections/StateEventCrossEventSankey.svelte` wrapping the existing `SwingSankey.svelte`. Default-off (button "Show vote-flow" expands). Always-on diverging-bar above it shows net seat-delta per top-6 parties + Others (structurally honest baseline; the Sankey is the approximate add-on).
- **Frontend alliance honesty**: Add `formation` column to `datasets/data/entities/party_alliances.csv` schema (enum `pre_poll` / `post_poll` / `hybrid`, nullable defaulting to `pre_poll`) - additive minor bump on the column schema. Render `<AllianceTotals>` ONLY when `(event_id, state)` has at least one alliance row; suppress the existing amber "pending" pill (silence on uncurated events). Add the Max-authored honesty caption above the panel.

Out of scope (named so an executing agent does not pull them in):

- Re-publishing the General-elections route `/t/elections` (covered by sibling plan [TODO/20260615-elections-redesign-plan.md](TODO/20260615-elections-redesign-plan.md) rows E1-E5; this plan does not block on E2, see R4 sourcing rule).
- Per-AC drill-down page rework (`/<state>/elections/<event>/<ac-slug>` - retained as-is).
- StateOverview (`/<state>`) page redesign - the bottom "Seat composition over time" trend stays; this plan only borrows the `buildKpiTiles()` pattern.
- New per-event boundary corrections (PC boundaries for Parliament events deferred per [PR #954 closure ledger](TODO/20260612-election-event-page-ux-polish-plan.md)).
- The 13 other state-events already in the `eci_form10_ae.py` JOBS tuple - those already work; we only ADD MH 2024.
- Indicator catalogue / topic catalogue changes; election-events.json changes.
- Schema MAJOR bump on any schema (party_alliances.csv goes 1.x -> 1.(x+1), additive minor).
- a11y / WCAG / aria-* enforcement at project level ([CLAUDE.md section 0](CLAUDE.md) non-goal). Where ARIA annotations land (e.g. role="button" on the Sankey expand toggle), they land because they are <= 4 LOC per occurrence.

### ESCALATE triggers (PAUSE and ask user)

- R1 oracle 6 (Tier-C parity vs thecont1) shows mismatches > 0 on the 266 overlap rows. That is a party-resolution drift across two publishers = Max sign-off required per [CLAUDE.md section 10](CLAUDE.md) "no silent demotion".
- R1 produces a candidacy count outside the band `[4100, 4300]` (XLSX has 4717 candidate-shaped rows minus NOTA + TURNOUT marker rows; sanity band derived from 22 missing ACs * avg ~16 candidates).
- The user-reported "J&K shows 10 events but home shows different" claim is RE-CONFIRMED with a concrete repro path. Investigation in section 0.3 below could not reproduce; current StateOverview rendering and `election_events.json` agree on 10.
- Adding the `formation` column to `party_alliances.csv` would require a MAJOR x-version bump (i.e. non-additive). The current design is additive minor (new column, nullable, default `pre_poll`).
- Any row pull would close a row a curator did not author (e.g. mutate party_alliances.csv attribution).

All other ambiguities are pre-resolved in this plan-doc (sections 0.1 personas, 0.2 root-cause, 2-7 per-row spec). The orchestrator does NOT re-ask.

### Chosen strategy (binding)

Six PR-rows, rip-and-replace doctrine per [TODO/20260615-elections-redesign-plan.md section 0.2](TODO/20260615-elections-redesign-plan.md). R1 (writer) and R2 (new landing route) are independent and may ship in parallel. R3 (structural extraction) precedes R4-R6 (behavioural changes built on the extracted components). Section reorder uses Beck two-hat discipline: R3 is pure refactor (extract, no behaviour change); R4 is pure rearrange + new chrome; the reviewer can tell them apart at a glance. No strangler-fig route, no V2 query-param, no parallel surface - git is the rollback.

## Section 0.1 - Persona-debate convergence (Jony + Max + Fowler, 2026-06-15)

The three personas were dispatched in DEBATE not parallel-review per [prepare-plan SKILL](.claude/skills/prepare-plan/SKILL.md) step 3. Verdict transcripts compressed; full verbatim available in section 9.

| Question                                                | Persona owners        | Converged verdict (baked into the row spec below) |
| ------------------------------------------------------- | --------------------- | ------------------------------------------------- |
| Final section order on `/<state>/elections/<event>`     | Jony + Citizen        | 11 sections (1 deleted, 1 merged, 1 added Sankey). Section R4. |
| Hero card spec + delta glyph rule                       | Jony + Citizen        | 4 cards (Seats/Voters/Polled/Turnout); only turnout + voters + polled carry delta; first-event-on-record OMITS the delta row (not "0"). Section R4. |
| Semantic prev/next without arrows                       | Jony + Citizen        | **YEAR-CHIP RAIL** (no arrows, no chevrons, no Prev/Next labels). Horizontal pill rail of year chips for every same-body event for the state; current year filled (`bg-slate-900 text-white`); other years outline (`border-slate-300 text-slate-700 hover:bg-slate-100`); 2px winner-color underline per chip (`border-bottom-color: {party_color}`). Compare = a single trailing pill labeled `Compare with {prior_year}` (NO arrow on it). Horizontal-scroll on mobile (IG story-tray gesture); current pill `scrollIntoView({inline:"center"})` on mount. Reuses [ElectionsRouteTabs.svelte](frontend/src/lib/elections/ElectionsRouteTabs.svelte) pill family; zero new visual vocabulary. Section R4. |
| House-comp + top-parties combined visual                | Jony + Fowler         | Extend PartyBar -> per-party-row table; RETIRE SeatDonut on this surface. Columns: `[symbol] [short] [alliance-chip] [seats-bar] [seats-count] [vote-share%]`. Section R4. |
| Alliance summary visual + honesty caption               | Jony + Max            | Keep `<AllianceTotals>`; extend to the screenshot's winner-runner-up-others diverging-bar pattern; MANDATORY caption "Pre-poll alliance composition as reported by [source.title]. Post-election government formation may differ. Uncategorised parties shown under 'Others'." Section R6. |
| Constituencies-by-district fold + search + Compare CTA  | Jony + Citizen        | Sticky search input inside section scroll-boundary; ALL districts collapsed on first paint; tap-to-expand inline; Compare CTA is the LAST row, slate-700 link not a button. Section R4. |
| Sankey gating + caption + no-prior copy                 | Max + Jony + Citizen  | Ship BOTH: always-on diverging-bar (default), Sankey collapsed behind "Show vote-flow" pill; caption (always visible): "Approximate flow: each party's net seat loss is redistributed to gainers in proportion to each gainer's net seat gain. We do not track constituency-level flips; this is a state-total estimate." No-prior: section header reads "Vote-flow comparison needs a prior election; this is the first {body} event on record for {state}." Section R5. |
| State-elections landing `/<state>/elections/`           | Jony + Citizen        | Full standalone route. Sections: Breadcrumb / PageHeader / latest-by-body hero / two parallel tables (assembly + parliament) / cross-link to `/<state>` welfare context. Section R2. |
| Alliance render-when-data rule                          | Max + Hans            | Render the panel ONLY when `party_alliances.csv` has >= 1 row for `(event_id, state)`. No "pending" pill (silence on uncurated events). Section R6. |
| `formation` column shape                                | Max + Hans            | Add column to `party_alliances.csv` (enum `pre_poll` / `post_poll` / `hybrid`, nullable defaulting to `pre_poll`). Schema bump additive minor. Section R6. |
| Hero turnout-delta sourcing                             | Max + Fowler          | **RATIFIED 2026-06-15 by user ("understood on delta on turnout on sibling, lets just plan this")**. If E2 from [20260615-elections-redesign-plan.md](TODO/20260615-elections-redesign-plan.md) has shipped at R4 execution time (now CONFIRMED shipped per PR #1037; mart at `datasets/data/marts/elections/event_summary.csv`), read `event_summary.csv`. Otherwise (mart absent on local dev): fall back to per-event `summary.csv` files. First-event-on-record: delta field OMITTED (not "0"). Section R4. |
| MH 266->288 writer fix                                  | Max + Fowler          | Add MH 2024 to existing `eci_form10_ae.py` JOBS tuple (1 EciEventSpec row). DELETE `thecont1_mh_ae2024.py` + its 1 test file + its CLI registration in the SAME PR (rip-and-replace). source.csv attribution already correct; no curator edit needed. Section R1. |
| Section reorder safety                                  | Fowler                | Beck two-hat: R3 pure structural extract (5 named subcomponents, no behaviour change). R4 pure behavioural rearrange + new chrome. NOT in-place reorder (mixes hats), NOT V2 route (strangler-fig banned by user 2026-06-15). |

## Section 0.2 - The 266->288 root-cause receipt (verified 2026-06-15)

User claim: live page shows 266 ACs for MH 2024; expected 288 (constitutional); user asked to "force regingest from the ECI XLSX".

Verified findings (do NOT re-investigate):

1. **The XLSX has 288 ACs**, not 266. Probe via `openpyxl.load_workbook('datasets/ephemeral/2024_MH_10-Detailed_Results_1744893339.xlsx')`:
   - Sheet: `Worksheet` (1 sheet)
   - Header row 3: `STATE/UT NAME, AC NO., AC NAME, CANDIDATE NAME, GENDER, AGE, CATEGORY, PARTY, SYMBOL, GENERAL, POSTAL, TOTAL` (+ 3 trailing pct/elector cols)
   - Distinct `AC NO.` values: **288** (range 1..288, zero missing)
   - Total candidate-shaped rows: 4717 (data starts row 5)
2. **The current writer reads the WRONG file.** [backend/yen_gov/canonical/adapters/thecont1_mh_ae2024.py](backend/yen_gov/canonical/adapters/thecont1_mh_ae2024.py) reads `datasets/ephemeral/thecont1-india-votes-data/2024/Assembly-Maharashtra.csv` (the thecont1 GitHub mirror), NOT the ECI XLSX. Its docstring explicitly says "track but don't fail on missing ACs - the canonical electoral.csv corpus for MH delim=2008 has 22 known gaps".
3. **source.csv already correctly cites the ECI XLSX**. Row `src-0c04cb845d7e`:
   - producer: `Election Commission of India`
   - title: `Statistical Report Section 10 (Detailed Results) - S13 AcGenNov2024`
   - vintage: `AcGenNov2024`
   - url: `https://www.eci.gov.in/eci-backend/public//all_files/election_report/Maharashtra_Legislative_Assembly_Election__2024_2024/10-Detailed_Results_1744893339.xlsx`
   - **No curator edit is needed.** The writer just needs to actually consume that XLSX.
4. **The fix is one-row JOBS append.** [backend/yen_gov/canonical/adapters/eci_form10_ae.py](backend/yen_gov/canonical/adapters/eci_form10_ae.py) already supports 13 state-events via the `JOBS` tuple. Each row is one `EciEventSpec(file_name, state_slug, state_code, state_display, expected_state_name, election_year, event_id, polled_on, period_label)`. MH 2024 is missing from the tuple. Adding it makes the existing CLI `python -m yen_gov ingest-eci-ae-form10` regen MH 2024 with all 288 ACs (the writer keys to `(state_code, AC NO.)` not name-fuzzy-match).
5. **Current on-disk baseline** (captured 2026-06-15 08:18 IST):
   - `datasets/elections/assembly/state=maharashtra/election=2024/summary.csv`: 267 lines (1 header + **266** data rows)
   - `datasets/elections/assembly/state=maharashtra/election=2024/candidacies.csv`: 3826 lines (1 header + **3825** data rows)
   - `datasets/data/datapoints/electoral/maharashtra_election_results.csv`: contains an MH 2024 segment matching the 266 ACs
6. **Target post-R1**: summary.csv = 289 lines (288 data rows); candidacies.csv in the band `[4100, 4300]` (22 missing ACs at ~16 cand each = ~352 new candidacy rows; ESCALATE if outside the band).

## Section 0.3 - AssemblyElections mart coverage bug (verified 2026-06-15, follow-up to user pushback)

User reported on 2026-06-15: the live `/t/elections/assemblies` page (route shipped via [TODO/20260615-elections-redesign-plan.md](TODO/20260615-elections-redesign-plan.md) PR-E4) renders the J&K (UT) card as "No election in the catalogue yet." - WRONG, because [datasets/taxonomy/election_events.json](datasets/taxonomy/election_events.json) has `assembly-2024` for U08, the per-event `datasets/elections/assembly/state=jammu-and-kashmir/election=2024/summary.csv` exists on disk, AND [backend/yen_gov/canonical/adapters/eci_form10_ae.py](backend/yen_gov/canonical/adapters/eci_form10_ae.py) JOBS already includes `2024_jk_10-Detailed-Results.xlsx`. The bug is at the mart-write seam, not in the catalogue or in the per-event data.

Verified facts (do NOT re-investigate):

1. **The mart lives at `datasets/data/marts/elections/event_summary.csv`** (NOT under `datasets/data/datapoints/electoral/`). 312 rows total: 0 national + 312 state + 0 other. PR-E2 writer at [backend/yen_gov/canonical/derived/event_summary.py](backend/yen_gov/canonical/derived/event_summary.py).
2. **The view-model at [frontend/src/lib/view-models/assembly-elections-model.ts](frontend/src/lib/view-models/assembly-elections-model.ts) reads the mart only, then matches catalogue state-entries against mart rows.** When a state-entry has zero matching mart rows, it renders the card with `latest_event: null` and `total_events_on_record: 0` and the template surfaces the copy `"No election in the catalogue yet."` (path A in the model; path B is the no-legislature 5-UT bucket per `NO_ASSEMBLY_UT_SLUGS`). J&K hits path A because the MART is empty for U08, not because J&K is mis-classified as no-legislature.
3. **The mart writer is missing the U08 row** for assembly-2024 despite all the input data being present. The failure localises to [backend/yen_gov/canonical/derived/event_summary.py](backend/yen_gov/canonical/derived/event_summary.py) `_build_slug_to_eci_via_catalogue()`: it builds a `slug -> eci_code` bridge from [datasets/data/entities/state_codes.csv](datasets/data/entities/state_codes.csv) plus catalogue display strings, then the assembly directory slug `state=jammu-and-kashmir/` misses that bridge. The current on-disk facts show the proximate mismatch: `state_codes.csv` has slug `jammu-and-kashmir`, `lgd_name` `Jammu And Kashmir`, alias `Jammu & Kashmir`; the U08 catalogue assembly display parses as `Jammu & Kashmir`. The existing bridge compares `lgd_name` plus a small set of UT/NCT variants and does not treat aliases / display-normalised names as identities. This is the same class of slug/display drift recorded in user-memory `lessons-2026-06-13` for `/<state>` route slugs. The fix lives in the writer and must make `eci_code` the join key after the slug bridge is resolved; slug is only an alias.
4. **Per-state audit ledger** (catalogue assembly count vs mart assembly count, all 36 state/UT entries):

   | code | cat_ae | mart_ae | gap | notes |
   | --- | --- | --- | --- | --- |
   | S01-S29 (excl. S04) | as-is | matches | 0 | clean |
   | **S04 Bihar** | **12** | **11** | **-1** | catalogue has TWO rows with `event_id=assembly-2005` (Feb 2005 hung + Nov 2005 re-poll), the ONLY duplicate `(eci, kind, event_id)` tuple in the entire catalogue (verified across all 36 polities). Mart PK `(event_id, state_code)` first-match-wins -> Feb identity surfaces; Nov 2005 (the constitutionally consequential election that produced the Nitish Kumar government) is INVISIBLE in citizen data today. Backend `EVENTS_BY_MONTH` at [backend/yen_gov/sources/eci/events.py#L510-L513](backend/yen_gov/sources/eci/events.py) already encodes the split (`AcGenFeb2005` + `AcGenNov2005`); catalogue + mart + URL grammar lag. Promoted to **R1.6** in this plan-doc (not silently deferred). |
    | **U08 J&K** | **1** | **0** | **-1** | writer parses catalogue display string instead of using the catalogue's outer-dict key (which IS the `eci_code`) — a Canonical Data Model violation per Hohpe (EIP ch.8). Fix in R1.5. |
   | U01 / U02 / U03 / U09 | 0 | 0 | 0 | no-legislature UTs; correct (NO_ASSEMBLY_UT_SLUGS) |
   | U04 / U06 | 0 | 0 | 0 | U04 Daman+Diu pre-merger (retired); U06 Lakshadweep no-legislature; correct |

5. **Bigger latent issue, out of scope of THIS plan**: per-state on-disk dirs hold FAR more `summary.csv` files than the catalogue lists. Verified end-to-end (2026-06-15): catalogue total 303 assembly events; disk total 870 dirs; **gap = 567 across 31 of 36 polities, NOT just J&K + Bihar**. Top-10 gaps: AP=40, UP=37, MP=36, WB=30, Bihar=29, Karnataka=28, MH=28, Rajasthan=26, Gujarat=25, Punjab=23 (J&K=21). Disk-only events carry REAL winner rows (sample: AP 1962=300 rows, AP 1967=287 rows, AP 1964/1968 small by-election years). Catalogue `kind` enum is ALREADY v1.3 = `{assembly, parliament, general_bye, assembly_bye, by_election}` and the `assembly-bye-<YYYY>-<seat-slug>` event_id grammar is already used on disk (Karnataka `state=karnataka/election=2024-channapatna-bye/` is the precedent). **The 567-gap is POPULATION debt, not SCHEMA debt** (Max correction, 2026-06-15). Promoted out to spawned sibling plan-doc [TODO/20260615-elections-catalogue-completeness-handover.md](TODO/20260615-elections-catalogue-completeness-handover.md) (Hans + Max + Citizen authority per CLAUDE.md §0a; priority ranking d > b > a > c per Max).

**Decision**: add Row R1.5 (writer fix per Gregor's framing — delete the display-string-parsing bridge; iterate the catalogue's outer-dict key directly) AND Row R1.6 (catalogue identity rip for Bihar 2005; minor schema bump 1.3 -> 1.4 to extend event_id grammar with `<kind>-<YYYY>-<month-slug>` for collision cases). Both rows are NAMED in this plan-doc so the next agent does not re-discover them; the 567-event coverage-extension work spawns [TODO/20260615-elections-catalogue-completeness-handover.md](TODO/20260615-elections-catalogue-completeness-handover.md) per Max's outline.

## Section 0.4 - J&K event-count claim CLOSED (was 0.3 in the prior revision)

User reported on 2026-06-15: "for some UT - the # of events is not accurate - for example Jammu (refer screenshot) says 10 events but home" (sentence truncated). After follow-up investigation:

- [StateOverview.svelte](frontend/src/routes/StateOverview.svelte) line 980 reads `"10 elections on record"` for J&K, which IS correct (10 = 1 assembly + 9 parliament in `election_events.json` for U08).
- The page the user was actually concerned about is `/t/elections/assemblies` (the AssemblyElections route), which renders the J&K card as `"No election in the catalogue yet."`. That bug is diagnosed in Section 0.3 (mart-coverage drop due to the writer slug/display bridge) and ripped in Row R1.5.

No separate row for this header-count claim; closed by R1.5.

## Section 0.5 - Jony's full-page 2027 elevation (re-convened 2026-06-15)

User pushback 2026-06-15: "jony the entire page should be ready for 2027 - futuristic look feel responsiveness intuitiveness not just compare, this is your chance to shine and delight citizens of the world, rise up to the challenge". The previous Jony verdict was correct but FLAT - chrome lists, not experience design. This section elevates the ENTIRE state-event page (`/<state>/elections/<event>`) to 2027-ready and replaces / amends the corresponding R4 / R5 / R6 specs below.

Citizen co-signs. Reference class: Linear (interaction craft), Vercel Analytics (data-dense + light), Apple big-type cards (clarity), Numeric + Copilot Money (storytelling-with-numbers), OWID renderer (doctrinal north-star), Spotify NPE (delight without ego). Citizen target: 30-yo Indian on a Redmi Note over 4G - delight that lives on the device they own, not an M3 Pro.

**The motion + chrome contract** (binding for R4 / R5 / R6; reuses existing tokens, zero new deps):

| Token / class                                                                              | Source                                                                                          | Use on this page |
| ------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- | ---------------- |
| `var(--dur-fast)` = 120ms                                                                  | [app-tokens.css](frontend/src/app-tokens.css)                                                   | Hover state, tap-down flash, chip-active swap |
| `var(--dur)` = 200ms                                                                       | app-tokens.css                                                                                  | Hero-card delta-pill fade-in, alliance bar grow, fold/expand of Constituency list |
| `var(--dur-slow)` = 320ms                                                                  | app-tokens.css                                                                                  | View-transition cross-fade between events, choropleth wave reveal, Sankey ribbon stagger |
| `var(--ease-out)` cubic-bezier(0.16, 1, 0.3, 1)                                           | app-tokens.css                                                                                  | All width / opacity / transform animations |
| `var(--ease-spring)` cubic-bezier(0.34, 1.56, 0.64, 1)                                    | app-tokens.css                                                                                  | Active year-chip in the sibling rail (the ONE moment - see J-elevated-10) |
| `prefers-reduced-motion` auto-collapse to 1ms                                              | app-tokens.css `@media` block                                                                   | Free; no per-component check needed |
| `sticky top-12 lg:top-0 z-20 bg-white/80 backdrop-blur border-b border-line`              | [Breadcrumb.svelte](frontend/src/lib/Breadcrumb.svelte) + [IndicatorJump.svelte](frontend/src/lib/IndicatorJump.svelte) | Year-chip rail when it sticks on scroll |
| `var(--e1)` / `var(--e2)` elevation shadows                                                | app-tokens.css                                                                                  | Hero card resting (`e1`); hovered (`e2`); active year-chip (`e1`) |
| `rounded-yen-pill`                                                                         | Tailwind config token                                                                           | Year-chip rail pills, Compare pill, Body-toggle pills |
| `animate-pulse bg-slate-50` / `bg-slate-100`                                               | [Home.svelte:276](frontend/src/routes/Home.svelte) + [StateOverview.svelte:802](frontend/src/routes/StateOverview.svelte) | Skeleton state for HeroCards + choropleth + alliance bars |
| `tabular-nums`                                                                             | 15+ existing sites incl. [Yenask.svelte](frontend/src/routes/Yenask.svelte)                     | Every numeric cell on the page (HeroCards headline, PartyComposite seats/share, ConstituencyList margins) |
| `<Skeleton />` component                                                                   | [frontend/src/lib/Skeleton.svelte](frontend/src/lib/Skeleton.svelte) + ChartShell loading slot  | Per-section loading states |
| View Transitions API (`document.startViewTransition()`)                                    | NEW: greenfield; native to Chrome / Edge / Safari (96%+ India share)                            | Year-chip rail tap -> next event cross-fade (R4); feature-detect, fall back to instant nav |

**J-elevated-1: PAGE-LEVEL motion contract.**

(a) First paint hierarchy: Breadcrumb (instant; HTML) -> YearChipRail (instant chips from `election_events.json` ~5KB; winner-color underlines hydrate as party-meta arrives) -> HeroCards skeletons (`animate-pulse bg-slate-50 h-24 rounded-xl ring-1 ring-slate-200/70` per StateOverview L802) -> Choropleth faded-outline placeholder -> all other sections lazy. Target TTI ~1.4s on 4G; LCP is the YearChipRail's active pill (already in DOM at first paint). (b) Year-chip tap: feature-detect View Transitions; if available `document.startViewTransition(() => navigate(href))` with a default 320ms cross-fade between two snapshots (the OLD and NEW page hero share `view-transition-name: hero` so it morphs in place); fallback to instant nav. (c) Scroll: year-chip rail sticks under the breadcrumb using the existing glass pattern (`sticky top-12 lg:top-0 z-20 bg-white/80 backdrop-blur border-b border-line` from Breadcrumb.svelte L58); section reveals are NOT animated (no scroll-triggered fade-ins - decoration, not feedback); scroll-snap on the rail itself uses `scroll-snap-type: x mandatory` + `scroll-snap-align: center` per chip (mobile thumb-flick lands the next year centered). (d) `prefers-reduced-motion`: nothing extra needed - the `--dur*` token auto-collapse handles everything.

**J-elevated-2: STORYTELLING ORDER.**

The page answers ONE question in the first 100vh: "Who runs this state right now and how did they win?" Sequence on initial paint: (1) Breadcrumb (50px) - context. (2) YearChipRail (60px) - WHERE the citizen is in time, instantly. (3) HeroCards (~140px on mobile in 2x2 grid; ~110px on desktop in 4-up grid) - Seats + Turnout dominate the eye; Voters + Polled are scale-context. (4) Choropleth (full container width, ~480px) - the winner-coloured map IS the answer to "who won". Section 100vh on a 6.5" Redmi Note (~640px) shows breadcrumb + rail + hero - the map starts entering view at scroll-y ~250px. **Section order CHANGE from prior R4 verdict**: PartyComposite moves UP from position 6 to position 4.5 (immediately after the map, BEFORE AllianceTotals), so the "WHO won" map and "BY HOW MUCH per party" composite read as a single story. AllianceTotals moves to position 5 (was 7); RacesBoard stays at 8; everything else preserved. The flat 288-row constituency table DELETION (already in R4) is the right call - it carried 0 story, only data.

**J-elevated-3: HERO CARDS elevated.**

Headline number: `text-4xl font-semibold tabular-nums leading-none text-slate-900` on mobile, `lg:text-5xl`; label is `text-xs uppercase tracking-wide text-slate-500 font-medium`. Numeric count-up: YES for the headline number on first paint, 600ms `var(--ease-out)`, requestAnimationFrame-driven (`linear(t) * target`); under `prefers-reduced-motion` snap to final value instantly (the existing `--dur*` collapse doesn't catch JS animation - hand-check `window.matchMedia('(prefers-reduced-motion: reduce)').matches` once in `onMount`; total cost ~15 LOC). Background: flat `bg-white` resting; on hover `shadow-[var(--e2)]` + 1px border-line accent; keyboard-focus `ring-2 ring-sky-500/40`. Delta pill (turnout / voters / polled): `inline-flex items-center gap-1 px-2 py-0.5 rounded-yen-pill text-xs font-medium`; positive `bg-emerald-50 text-emerald-700`, negative `bg-rose-50 text-rose-700`; the glyph (trending-up.svg / trending-down.svg) lives BEFORE the number; the pill itself fades in at `var(--dur)` 200ms `ease-out` with a `translateY(2px) -> 0` so it feels SETTLED not stamped. Tabular numerals mandatory. **The ONE micro-touch for hero cards**: when the data lands and counts up, the icon glyph gets a 1-frame `scale(0.92 -> 1)` over `var(--dur-fast)` 120ms - a subtle "wake up" pulse. Cost: a single CSS keyframe; <0.5ms paint.

**Amendment (Jony re-review 2026-06-15): first-event-on-record card-collapse pin.** When the (body, state) tuple has no prior event in the catalogue (e.g. `/jammu-and-kashmir-ut/elections/assembly-2024`), the delta-pill SLOT is OMITTED from the DOM - not rendered as a zero-state placeholder, not as an em-dash, not as a "first election" badge. The card's vertical height collapses by ~20px (from `min-h-[120px]` to `min-h-[100px]`); the numeric count-up still fires; the empty space below the headline number is empty by ABSENCE, not by token. The visual rhythm of a 4-card row with one card 20px shorter is preserved because the cards sit inside `grid grid-cols-2 lg:grid-cols-4 gap-4 items-stretch` so the row height matches the TALLEST card; the short card aligns to top. Wired via R4's `delta?: ... | undefined` prop optional-typing + R6's `noPriorSameBody` boolean (passed down from `StateElection.svelte`). Tier-A test in `frontend/src/lib/elections/StateEventHero.test.ts` asserts: first-event fixture -> card has no `[data-testid="delta-pill"]`, computed-height is < non-first-event card by >=20px.

**J-elevated-4: YEAR-CHIP RAIL elevated.**

Scroll-snap YES - `scroll-snap-type: x mandatory` on the `<nav>`, `scroll-snap-align: center` on each pill. On mobile a thumb-flick lands the next year dead-center (Spotify Now Playing pattern); on desktop the snap is invisible because hover-and-click is the gesture, not swipe. Active-pill: filled `bg-slate-900 text-white` IS sufficient - we do NOT scale or glow (that competes with the winner-color underline for "spotlight"; pick one signal). Winner-color underline: KEEP at 2px bottom-border (not 3px - 2px reads as accent; 3px starts feeling like a Microsoft Edge tab). NOT a dot-above-year (too Spotify-specific; the underline reads as a constitutional fact about the year). Hover: `var(--dur-fast)` 120ms color shift + `shadow-[var(--e1)]` lift (so the pill telegraphs "tap me" without changing position). Tap-down: instant `scale(0.97)` flash, releases on tap-up - the existing Apple-iOS tap-feedback gesture. Year label: just `2024` - adding `OCT 2024` makes mobile pills wider than the thumb-target (40px), and the polled-on month lives in the HeroCards subtitle anyway. **Compare pill differentiation**: the Compare pill is the SAME pill chrome but with a leading `bg-slate-50` ring (`ring-1 ring-slate-200`) and a 4px gap separator before it - it visually feels like the "more" affordance at the end of a Spotify carousel, not another year. The label is `Compare with {prior_year}` - NO arrow ever, period.

**Amendment (Jony re-review 2026-06-15): single-event rail behaviour pin.** When `events.length === 1` (this state has exactly one event of this body in the catalogue - e.g. J&K U08 has only `assembly-2024` in [datasets/taxonomy/election_events.json](datasets/taxonomy/election_events.json)), the rail collapses to ONE filled pill for the current year, centered (`justify-center` on the `<nav>`), NO Compare pill, NO scroll-snap, NO sticky-on-scroll (the lone pill scrolls off naturally with the breadcrumb via `:has(> *:only-child) { position: static; }`). Honesty: the single-pill row reads as "this is the only data we have for this body for this state" - the citizen does NOT see a Compare pill that would offer them nothing. The `sibling-events-rail-model.ts` projection returns `compare_href: null` when `events.length === 1`; the template's `{#if compare_href && prior_year !== null}` already gates the trailing pill correctly. Tier-A test in `frontend/src/lib/elections/SiblingEventsRail.test.ts` adds: 1-event fixture -> 1 pill rendered, 0 Compare pills, `<nav>` carries `justify-center` class.

**J-elevated-5: CONSTITUENCY CHOROPLETH elevated.**

Initial-paint reveal: do NOT do a wave or district-by-district sweep - delightful in a demo, but on 4G the polygons fade-in IS the bandwidth telling its truth; let it. Add `transition: fill var(--dur) var(--ease-out)` on each polygon so the Winner / Margin toggle (today an instant snap) becomes a smooth color blend - that IS the moment of craft. Hover micro: polygon stroke widens to `1.5px` + brightness +5% via CSS filter on `var(--dur-fast)` 120ms - the polygon feels "lifted" without z-order changes (which would re-paint expensive). Mobile tap: instant tooltip (current behaviour), tap-again navigates to AC drill-down - the iOS Maps pattern (peek then commit). Winner/Margin toggle: REPLACE the current pair with a single Tailwind segmented control - `inline-flex rounded-yen-pill border border-slate-300 p-0.5 text-xs font-medium` parent, two `<button>` children with `bg-slate-900 text-white` for active / `text-slate-600 hover:text-slate-900` for inactive; the sliding-underline effect costs 4 LOC of `transition:transform`. Sub-threshold-marker legend copy elevation: "Tiny urban seats appear as dots so the map stays readable on phones." (was "Circles mark dense urban constituencies too small to render as polygons at this zoom." - the new copy is warmer, names the reason, and tells the citizen WHY rather than apologising for the choice).

**Amendment (Jony re-review 2026-06-15): absorb Item M (per-section deep-zoom).** Tap-and-hold the choropleth chrome (500ms `pointerdown`) reveals a top-right `Expand` chip (`rounded-yen-pill bg-slate-900/90 text-white text-xs px-3 py-1.5 backdrop-blur shadow-[var(--e2)]`); tapping it grows the choropleth to 100vh via `document.startViewTransition()` (same 320ms + `--ease-out` budget as the year-chip rail's wow moment in J-elevated-10). Inside 100vh: a top-right `X` (Apple Photos pattern) collapses back via the inverse view-transition. Dense-urban marker-dots upgrade to OUTLINED POLYGONS in expanded view (the data was always there at 100vh; the dot fallback was bandwidth-honesty, not data-loss). Cost: ~50 LOC in `StateEventMap.svelte` (long-press detection + view-transition trigger + scale-aware polygon-vs-dot switch). Reference class: Apple Photos tap-to-fullscreen; iOS Maps detail expand. Only the choropleth gets this - the Sankey is collapsed-by-default (J-elevated-7), the constituency list scrolls within itself (J-elevated-8), the PartyComposite is a table - none of those three benefit from 100vh the way the choropleth does.

**J-elevated-6: PARTY COMPOSITE elevated.**

Sort default: descending by seats won, FIXED (Linear rule - never give choices the citizen doesn't need). Bar visual: flat solid party-color fill (honesty rule - no gradient that telegraphs depth-where-there-is-none, no stripe-for-alliance that would compete with the alliance-chip column). Symbol rendering: 16x16 inline SVG INSIDE a `rounded-full bg-slate-50 ring-1 ring-slate-200 p-1 w-8 h-8` halo - the halo gives the symbol breathing room and makes the row scannable even when the symbol is light-on-white. Row hover: `bg-slate-50 cursor-pointer`; row click navigates to `/parties/<slug>` for that party - this is data-density paying off (the citizen sees the row, recognises the party, taps to dive deep, all in one motion). Show top N: top 7 parties expanded; 8th row is `<button>` showing `Show {N - 7} more parties` (text-only, slate-600); on click reveals the rest with `transition:slide` from `svelte/transition` 200ms `var(--ease-out)`. Alliance chip: tiny outline `inline-flex items-center px-1.5 py-0 rounded-yen-pill text-[10px] font-medium border-slate-300 text-slate-600` - reads as metadata, not as a primary affordance; the alliance NAME repeats in AllianceTotals below so the citizen connects the two without us having to draw a line.

**J-elevated-7: ALLIANCE TOTALS visual elevated.**

Bar typography: alliance name `text-base font-semibold text-slate-900`; member parties below `text-xs text-slate-500` (one line, comma-separated, truncate with `+N` overflow indicator per the user's reference screenshot pattern); seat count `text-2xl font-bold tabular-nums text-slate-900` right-aligned; percentage `text-xs text-slate-400 tabular-nums` below the count. Bar fill: the WINNER party color for the leading alliance, runner-up alliance gets its own leading party's color, "Others" stays slate-400 - this preserves the data spine's color contract (party-color resolver already in `frontend/src/lib/colors/resolver.ts`). First-paint animation: bar width grows from 0 to actual over `var(--dur-slow)` 320ms `var(--ease-out)` - this IS narrative (the seat count revealing itself); skipped under `prefers-reduced-motion`. No-data state: silent suppression (per R6); a one-line caption below the SiblingEventsRail saying "Alliance attribution not yet curated for this event." is warmer than a missing card but ONLY if alliance is the only missing piece - if data is generally pending the page-level error handles it; ship suppression-only for v1 and revisit if Citizen tests show confusion.

**J-elevated-8: SECTION-LEVEL spacing + rhythm.**

Section gap: `space-y-8` (32px) on mobile, `lg:space-y-12` (48px) on desktop - matches the existing StateOverview rhythm. Section header: small uppercase eyebrow + larger title, e.g. `<p class="text-xs uppercase tracking-wide font-medium text-slate-500">Race competitiveness</p><h2 class="text-xl font-semibold leading-tight text-slate-900">288 constituencies, by margin</h2>` - this echoes Apple HIG's hero-section grammar and gives each section a SECOND label that tells the citizen "what is the citizen-question here". Dividers: NO horizontal rules between sections; the white space IS the divider (Vercel rule). Sticky element: YES the YearChipRail sticks under the Breadcrumb on scroll (`sticky top-12 lg:top-0 z-20` per the existing glass pattern) - so the citizen always knows WHICH event they are reading even when they scroll into ConstituencyList; on scroll-up past the original position, the rail un-sticks gracefully (CSS handles automatically).

**Amendment (Jony re-review 2026-06-15): absorb Item K (section anchor links).** Each section header gets a stable `id` matching its eyebrow slug: `#hero`, `#sibling-rail`, `#map`, `#parties`, `#alliance`, `#races`, `#scatter`, `#constituencies`, `#flow`, `#all-parties`. On hover, a `#` icon (`inline-flex w-4 h-4 text-slate-300 hover:text-slate-500 ml-1 opacity-0 group-hover:opacity-100 transition-opacity duration-[var(--dur-fast)]`) appears next to the title; clicking it calls `history.replaceState(null, "", "#<section-id>")` (replaceState NOT pushState - the citizen does not want each anchor-tap creating a back-button entry; GitHub README + Vercel docs both ship this exact pattern). On first paint with non-empty `location.hash`, AFTER hydration completes (`onMount(() => { if (location.hash) setTimeout(() => document.getElementById(location.hash.slice(1))?.scrollIntoView({block: "start", behavior: "smooth"}), 50); })`; the 50ms delay lets Svelte 5's `$effect` settle the DOM before scrolling). Cost: ~15 LOC. Citizen value: every section becomes a shareable WhatsApp link (`/maharashtra/elections/assembly-2024#alliance` jumps straight to the alliance panel). Reference class: GitHub README anchors, Vercel docs anchors, MDN sidebar anchors.

**J-elevated-9: LOADING / EMPTY / ERROR states with grace.**

HeroCards loading: 4 skeleton tiles using the existing pattern `animate-pulse bg-slate-100 rounded-xl h-24 ring-1 ring-slate-200/70` (verbatim from StateOverview.svelte L802 - reuse, do not invent). Choropleth loading: a faded outline of the state's bounding box rendered at 20% opacity from the cached topojson metadata (we already know the bbox before the polygons load); on data-arrival the polygons fade in to full opacity over `var(--dur)` 200ms. YearChipRail TWO-PASS hydration: render all year pills IMMEDIATELY on first paint from `election_events.json` (5KB; already cached); the winner-color underline starts as `border-slate-200` 1px and hydrates to the party-color 2px as `event_summary.csv` lands (typically <300ms after first paint) - the citizen sees the rail INSTANT, the colour is the "loaded" cue. Alliance no-data state: silent (per R6). Error copy tone: keep "Data could not load." (slate-500, no border, no panel chrome) - the citizen is on patchy 4G; this is the honest message; do not invent a witty error.

**J-elevated-10: THE ONE MOMENT (the wow).**

When the citizen taps a year-chip in the sibling rail, the active-pill spring-snaps to the tapped year via `transition: all var(--dur-slow) var(--ease-spring)` (the `cubic-bezier(0.34, 1.56, 0.64, 1)` spring already in our tokens), the OLD page's hero cards + map cross-fade out via `document.startViewTransition()`, and the NEW page's hero cards + map cross-fade in at the same 320ms - all three motions choreographed to one tick. Citizen tells their friend: "watch what happens when I tap a year." The whole page feels like ONE surface that transforms, not eleven sections that reload. Cost: ~30 LOC of view-transition CSS + 5 LOC of feature-detect; works native in Chrome / Edge / Safari (96%+ India share); falls back to instant nav otherwise. THIS beats "hero card count-up" (cute but in-card), "Sankey reveal" (collapsed by default), "choropleth wave" (cute but eats 4G), and "alliance bar grow" (subtle, not memorable) because this moment is the ENTIRE page becoming a navigation surface - a primitive that nothing else on the Indian civic web does today.

**Amendment (Jony re-review 2026-06-15): absorb Item I (haptic) + reject Item J (sound) + RELIABILITY re-spend.** On tap-down of a year-chip, `navigator.vibrate?.(10)` fires (feature-detected, no opt-in needed - Vibration API is not a fingerprinting vector and the 10ms tick is below the "annoying" threshold per iOS HIG). Sound REJECTED - civic data is read silently; the citizen is on a bus / in a meeting / with kids; sound competes with the environment whereas haptic COMPLETES the perception (Brichter rule: add a sensory layer only if it COMPLETES the perception). Only the wow moment is haptic; haptic-on-every-tap becomes annoying within 30 seconds. The +50 LOC budget for the wow moment goes to RELIABILITY across the long-tail of devices, NOT to a second wow moment competing with the first:

| LOC | Investment |
| ---:| ---------- |
| 5   | Haptic tick: `navigator.vibrate?.(10)` on tap-down; feature-detect; no opt-in. |
| 10  | Battery-saver detection: `navigator.getBattery?.()` -> if `level < 0.2 \|\| (!charging && level < 0.5)` skip the spring-snap; use a linear 200ms fade instead. |
| 5   | save-data fallback: `navigator.connection?.saveData === true` -> skip the cross-fade entirely; instant nav. |
| 10  | Safari spring-overshoot calibration: iOS Safari renders `cubic-bezier(0.34, 1.56, 0.64, 1)` with a more aggressive overshoot than Chromium; `@supports (-webkit-touch-callout: none)` branch uses `cubic-bezier(0.32, 1.40, 0.64, 1)` as the Safari-tuned variant. |
| 5   | View-transition fallback for Firefox (no API support as of 2026-06): falls back to instant nav, no flicker. |
| 5   | Dev-only `console.debug` of the actual measured transition duration so the developer verifies in the field (gated by `import.meta.env.DEV`; stripped at production build). |
| 5   | Component comment naming all five fallbacks so the next agent does not re-derive them. |
| 5   | Margin. |

The wow moment lands as: visible spring-snap on the active pill + 10ms haptic tick + 320ms cross-fade of hero + map. It DEGRADES gracefully through battery-save -> save-data -> Firefox-no-API -> always-on instant nav. The citizen on a Redmi Note with 18% battery on patchy 4G gets the right experience for THEIR device, not the developer's M3 Pro. This is the more honest 2027 commitment: the moment is reliable AS the moment across the long tail of devices and conditions, rather than a second moment that competes with the first.

**J-elevated-11: TIME-COMPARE OVERLAY on the choropleth.**

Today the year-chip rail lets the citizen JUMP between events. To COMPARE two events without navigating, long-press a year-chip (mobile, 500ms `pointerdown`) or shift-click (desktop) to PIN it as a baseline. The active chip then shows a tiny `vs 2019` inset (`text-[10px] text-slate-500 ml-1`); the choropleth re-renders in year-B colours with a per-AC swing overlay (a small SVG `<polygon>` triangle per AC centroid: up = gain, down = loss, sized by margin from `triangleScale = d3.scaleSqrt().domain([0, max_margin]).range([2, 8])`). The constituency-list section re-orders by `Math.abs(margin_swing)` desc instead of alphabetical. URL stays unchanged - this is in-memory state per the IndicatorJump non-navigation-state precedent in [frontend/src/lib/IndicatorJump.svelte](frontend/src/lib/IndicatorJump.svelte). Tap the pinned chip again to unpin; tap a different year-chip with no shift / long-press to navigate normally and clear the compare state.

**Why 2027 not 2017.** Split-screen (the original Item A in the brief) was rejected because 640px / 2 = 320px kills the choropleth and forks the gesture grammar. Linear-style diff-overlay on the same canvas is the 2027 pattern: one canvas, two timestamps, one gesture, zero new URLs. Comparison lives ON the page, not on a sibling tab.

**Mechanism.** Reuses the R3-extracted `StateEventMap.svelte`. Adds `compareYearId: string | null` prop; when set, the d3 `colorScale` swaps to `colorScaleB`, and an SVG `<g class="swing-overlay">` mounts with `<polygon>` triangles. Long-press detection: `pointerdown` -> `setTimeout(500, () => { compareYearId = chipId; navigator.vibrate?.(15); })`; `pointerup` / `pointercancel` / `pointermove > 10px` clears the timeout. Shift-click is a one-line conditional on the existing click handler (`if (event.shiftKey) { pin(...); return; }`). New pure helper `frontend/src/lib/elections/swing-overlay-builder.ts` (~60 LOC): `({ current_winners, baseline_winners, ac_centroids }) => SwingOverlayRow[]`.

**Cost.** ~120 LOC across `StateEventMap.svelte` + `swing-overlay-builder.ts`. Zero new lib. Zero extra bytes on first paint (alternate event's `summary.csv` fetches lazily on pin).

**Reference class.** Apple Photos compare-two-photos long-press; Linear cycle-diff overlay; OWID "vs world" chart overlay; FiveThirtyEight election-night swing-map.

**Row.** R4 (folds into the choropleth section via the R3-extracted `StateEventMap.svelte`).

**J-elevated-12: ONE AUTO-NARRATED INSIGHT per section.**

Each section header gets ONE italic slate-600 line below the eyebrow + title (`<p class="text-sm italic text-slate-600 mt-2 leading-snug">{narrative}</p>`). The line is auto-generated from `event_summary.csv` + the per-state long-format CSV; never editorial; always machine-derivable from a mart aggregation already on disk. Examples: HeroCards -> "Highest turnout in Maharashtra Assembly history since 1995."; AllianceTotals -> "Mahayuti's 230 seats is the largest single-alliance majority in Maharashtra since 1990."; PartyComposite -> "BJP gained 27 seats vs 2019, its best Maharashtra Assembly result on record."; Choropleth -> "23 of 36 districts flipped to Mahayuti from MVA control."; Scatter -> "Mumbai and Pune drove the highest turnout (>74%) in the state."

**Why 2027 not 2017.** OWID variable-page "Key insights"; Numeric "Notable" line; Copilot Money "vs last month" callouts. The citizen tells their friend the STORY the chart told them, not the numbers. Civic data needs a narrative layer or it stays a spreadsheet; this is OWID's load-bearing innovation re-applied to electoral data.

**Mechanism.** New `frontend/src/lib/elections/narrative-generator.ts` (~150 LOC of pure functions, one per section): `({ event_summary_row, peer_rows_for_state, peer_rows_for_event_id }) => string | null`. Each runs a bounded aggregation (max / min / rank over the state's history; cross-state percentile for the current event) and emits either a templated string or `null`. Generator is honest: 8 templates max, one per section; SILENT when the mart cannot derive a fact at >=80% confidence (e.g. first-event-on-record has no historical superlative to claim). Every claim is anchored to a specific (state, body, year) tuple already on the row - no synthetic copy, no editorial padding.

**Cost.** ~150 LOC pure helper + ~30 LOC integration (one prop per section header component). Zero new lib. Zero extra bytes (data already loaded).

**Reference class.** OWID variable-page Key insights cards; Numeric Notable line; Copilot Money insights; FiveThirtyEight callout-strip.

**Row.** R4 (mounts inside the extracted section headers; each R3 subcomponent gains a `narrative?: string | null` prop).

**J-elevated-13: PINCH + DOUBLE-TAP ZOOM on the choropleth.**

Two-finger pinch (mobile), scroll-wheel-up (desktop), or double-tap zooms the choropleth from 1x state-view up to 4x. A `Reset` pill appears top-right when zoomed (`rounded-yen-pill bg-slate-900/90 text-white text-xs px-3 py-1.5`). One-finger pan when zoomed; pan disabled at 1x so the citizen cannot drift off the state bounds by accident. Dense-urban marker-dots upgrade to OUTLINED POLYGONS past 2x (the data was always there; bandwidth, not the data shape, was the bottleneck). Reset returns to 1x via `transition.duration(320).call(zoom.transform, zoomIdentity)`.

**Why 2027 not 2017.** Mumbai has 36 ACs in ~300 sq.km; on a 640px viewport, those polygons are <10px wide. The citizen with a Redmi Note deserves to read the data their device can render. Maps, not metaphors. iOS Maps + Apple Maps + Google Maps + every Mapbox-powered map in 2025 ships pinch-zoom; civic data without it feels archaic.

**Mechanism.** `d3-zoom` is already in the dep tree (transitive via d3) - zero new bytes. ~40 LOC of `d3.zoom().scaleExtent([1, 4]).on("zoom", (event) => g.attr("transform", event.transform))` hookup in `StateEventMap.svelte`. Touch event surface is the browser's native pinch (d3-zoom routes it). Reset is a 10-LOC `<button>` with the d3 transition above.

**Cost.** ~80 LOC. Zero new lib. Zero extra bytes on first paint; zero impact on 4G TTI.

**Reference class.** Apple Maps; Google Maps; Mapbox; the canonical Observable choropleth tutorial.

**Row.** R4.

**J-elevated-14: PER-EVENT SHARE-CARD PNG generated at build time.**

When a citizen shares `/maharashtra/elections/assembly-2024` on WhatsApp, Twitter, LinkedIn, or Signal, the unfurl preview shows a 1200x630 PNG: state map in winner colours, headline `Mahayuti 230 of 288`, small subtitle `Maharashtra Assembly 2024`, yen-gov wordmark in the corner. The citizen telling their friend IS the distribution mechanism for civic-tech in India.

**Why 2027 not 2017.** OG-card-on-share is the 2025 default for every product surface (Vercel, Linear, GitHub, every SaaS landing page). It is the FIRST visual a citizen's friend sees BEFORE deciding to click. No Indian civic-tech site ships this; it is the single highest-leverage discoverability move available. Free at the build seam because the site is static.

**Mechanism.** New `frontend/scripts/build-share-cards.ts` (~120 LOC). Reads `datasets/data/marts/elections/event_summary.csv` + the topojson state map; builds an SVG per row using `d3-geo` + the same projection helpers `StateAcMapD3` uses; converts SVG -> PNG via `@resvg/resvg-js` (NEW devDep, justified per Holy Law #8: pure-WASM, ~2MB on disk, zero native binary deps so every CI host works without rebuild; preferred over `sharp` which needs native `libvips` and per-platform binaries). Output: `frontend/public/share/<state>/<event_id>.png` (~120 events across in-catalogue assembly + parliament rows at ~50KB each = ~6MB of CDN-cached static assets). Route's `<svelte:head>` reads `<meta property="og:image" content="/yen-gov/share/<state>/<event>.png">` + paired `og:title` + `og:description` + Twitter Card variants. Wired via `frontend/package.json` script: `"build": "vite build && bun scripts/build-share-cards.ts"`.

**Cost.** ~120 LOC script + ~12 LOC head meta in `StateElection.svelte`. +1 devDep `@resvg/resvg-js`. +6MB static assets (CDN-cached, zero runtime cost). Build time +~30s (~250ms per PNG; one-time per event, parallelisable across CPU cores).

**Reference class.** Vercel OG image generator (`@vercel/og`); Linear / GitHub project share cards; OWID Grapher chart-preview PNGs.

**Row.** **NEW R7** (structurally orthogonal to R1-R6; a build-step row, not a chrome row; can ship in parallel with R5+R6 because it only depends on `event_summary.csv` already existing post-R1.5).

**J-elevated-15: RECENT EVENT MEMORY on the landing page.**

When the citizen returns to `/maharashtra/elections/` (the R2 landing page) after having previously visited any state-event, the most-recently-viewed event for that state lights up with a small `Last viewed` badge (`text-xs text-slate-500 font-medium ring-1 ring-slate-200 rounded-yen-pill px-2 py-0.5`). No copy CHANGE; just an additional badge next to the year-as-link. Per-state, expires after 30 days so a stale memory does not dominate forever.

**Why 2027 not 2017.** Spotify "Recently played", Netflix "Continue watching", YouTube "Continue", Apple News "Continue reading" - every consumer surface tracks last-viewed and offers one-tap re-entry. Civic data deserves the same affordance; the citizen's WhatsApp-link-from-yesterday should not require them to remember which year they were reading.

**Mechanism.** Per-state localStorage: key `yen-gov:last-event:<state_slug>`, value `{event_id, viewed_at_iso, body}`. Write on every `/<state>/elections/<event>` page mount (`onMount` in `StateElection.svelte`, ~8 LOC). Read in `StateElectionsLanding.svelte` (~12 LOC). Expiry: `viewed_at_iso > Date.now() - 30 * 86400000` else ignore. NO server roundtrip, NO telemetry, NO PII (key is per-state-slug, contains zero device info, citizen can clear via browser settings). Total ~25 LOC.

**Reference class.** Spotify Recently Played; Apple News Continue Reading; Notion Recent Pages.

**Row.** R2 (amends the landing route).

**J-elevated-16: NATIONAL-CONTEXT MICRO-COPY on HeroCards.**

Each HeroCard whose metric has a national-average peer gets a single slate-500 line under the headline number: `above the all-India AE average of 67%` / `below the all-India AE average of 67%` / `matches the all-India AE average`. Honesty-first: only renders for metrics where cross-state comparison is meaningful (turnout, voter-share). Does NOT render for state-specific absolute counts (seats / voters / polled - those are state-scale facts and a national comparison would be misleading at best).

**Why 2027 not 2017.** OWID doctrine: context, not the number alone. The citizen who sees "65%" does not know if that is good. The citizen who sees "65% (above the all-India AE average of 67%)" knows immediately. Citizen-first: their question is "is my state doing well?", not "what is the number?".

**Mechanism.** Reads from `event_summary.csv` (already loaded for the hero turnout-delta in R4). New pure helper `frontend/src/lib/elections/national-context.ts` (~40 LOC): `({ metric, value, all_events_for_same_kind_and_year }) => string | null`. Renders below the headline number in the existing HeroCard slot (`text-xs text-slate-500 font-normal mt-1`). Silent when the mart cannot derive a national average for the (metric, body, year) tuple (e.g. <5 peer state-events of the same body and year).

**Cost.** ~50 LOC. Zero new lib. Zero extra bytes.

**Reference class.** OWID variable-page comparison band; FiveThirtyEight "vs the average"; Copilot Money "vs last month".

**Row.** R4 (mounts inside `StateEventHero.svelte`).

### Routed to sibling plans (NOT this plan)

The user's "2027-ready entire page" pushback explicitly invites elevations that are NOT page-scoped. Two of those belong in sibling plans that this plan-doc will NOT pretend to solve:

- **Site-wide command palette (Cmd+K / Ctrl+K + mobile floating search pill).** Linear / Vercel / Raycast / GitHub all ship this in 2025. It mounts in `App.svelte` or `main.ts`, not in any per-route component. Belongs in a future `TODO/202606XX-site-command-palette-plan.md` (not yet authored). When that plan ships, the state-event page gets one free thing: the citizen can jump from `/maharashtra/elections/assembly-2024` directly to `/karnataka/elections/assembly-2023` via search, no breadcrumb walk required.
- **Dark mode opt-in.** A sun/moon toggle in the header, defaults to `prefers-color-scheme`. 2027 expectation across the web (Apple HIG, Material You, Vercel, Linear). [frontend/src/app-tokens.css](frontend/src/app-tokens.css) already pre-wires the surface (see its `:root` comment about future dark theme without a recompile); dark-mode is a site-wide chrome contract, not a per-page concern. Belongs in a future `TODO/202606XX-site-dark-mode-plan.md` (not yet authored). When that plan ships, this state-event page's colour tokens flip with the rest of the site for free.

### Rejected 2027-tests (with reason, one sentence each)

The brief tested ~10 candidate elevations beyond what shipped. The rejects:

- **Read-progress bar** under the breadcrumb (Medium / Substack pattern): civic-data is reference, not narrative; "47% read" carries no civic meaning; the sticky year-chip rail already gives the citizen the "where I am" cue.
- **Sound on the wow moment** (Apple Settings tick): civic data is read silently; the citizen is on a bus / in a meeting / with kids; sound competes with the environment whereas haptic completes the perception silently (Brichter rule).
- **AI-generated voiceover** of the page: production cost + 4G bandwidth + harder to verify than visuals; civic data is read, not heard; not a 2027 commitment we are equipped to ship at quality.
- **Real-time Twitter / X sentiment overlay**: sentiment is editorial; yen-gov does not ship editorial; civic data is a factual surface.
- **AR view of the state**: WebXR is unreliable on the Redmi Note target; gimmick; does not help the citizen understand the data.
- **Gamification** (badges for visiting all states): cheapens civic data; the citizen is here to learn, not to collect.
- **Animated emoji reactions on alliance totals**: emoji feedback signals "comment thread"; civic data is reference, not chat.
- **Auto-playing video explainer**: belongs on a future learn-page sibling, not on the data surface.
- **Login / accounts**: violates the project's no-tracking promise (Holy Law #1 implication); we ship anonymous citizen access.
- **Push notifications for new election results**: requires service worker + permissions UX + push infra; static-only contradicts this (Holy Law #1 + #2); the citizen comes to us, not vice versa.
- **Swipe-between-events gesture** (left-swipe = prev year): conflicts with the browser back-swipe (right edge on iOS) and the side-nav drawer (left edge); Brichter rule: never reuse a platform gesture.
- **Pull-to-refresh on the page**: the browser already provides a refresh affordance (swipe-down on the URL bar); two correct answers to the same question is one too many.
- **Velocity-aware tooltips on the choropleth**: too granular; would over-tune for the 5% of citizens who hover-and-scrub.

## Section 1 - Status Reckoner

| Row  | Title                                                                                                                                                                                                                                              | Status                  | PR                          | Effort |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | --------------------------- | ------ |
| R1   | MH 266->288 writer rip: add MH 2024 to `eci_form10_ae.py` JOBS; DELETE `thecont1_mh_ae2024.py`; regen 288 ACs                                                                                                                                       | [x] MERGED              | #1061                       | S      |
| R1.5 | AssemblyElections mart coverage: DELETE display-string-parsing bridge in `event_summary.py`; iterate catalogue's outer-dict key (`eci_code`); use existing `eci_to_lgd_slug()` helper; regen mart so J&K U08 lights up                              | [x] MERGED              | #1065                       | S      |
| R1.6 | Bihar 2005 catalogue identity rip: catalogue schema 1.3 -> 1.4 (extend event_id grammar); split `assembly-2005` -> `assembly-2005-feb` + `assembly-2005-nov`; fan out on-disk `election=2005/` dir; regen mart; freeze catalogue PK invariant test  | [D] DECIDED — Path A'   |                             | L      |
| R2   | NEW `/<state>/elections/` landing route -> `StateElectionsLanding.svelte`                                                                                                                                                                          | [x] MERGED              | #1066 (gap-close #1072)     | S      |
| R3   | Structural-only: extract 5 named subcomponents from `StateElection.svelte` (no behaviour change; Beck two-hat)                                                                                                                                      | [x] MERGED              | #1067 + #1068               | M      |
| R4   | Behavioural reorder + HeroCards + **year-chip rail (no arrows)** + PartyComposite + fold/search ConstituenciesByDistrict + delete deadwood                                                                                                          | [x] MERGED              | #1071                       | L      |
| R5   | NEW `StateEventCrossEventSankey.svelte` (diverging-bar always-on + Sankey collapsed) + opt-in caption                                                                                                                                                | [~] IN-FLIGHT (no PR)   | branch `feat/r5-cross-event-sankey` @ pre-R4 base | M      |
| R6   | Alliance honesty: `formation` column + render-when-data-exists + caption above panel + first-event-no-prior gating                                                                                                                                  | [ ] PENDING             |                             | M      |
| R7   | NEW build-step: per-event share-card PNG at `bun run build` (`frontend/scripts/build-share-cards.ts` + `@resvg/resvg-js` devDep + `<svelte:head>` og:* + twitter:card meta on `StateElection.svelte`); J-elevated-14                                  | [ ] PENDING — stub branch only | (`feat/r7-share-cards` exists, 0 commits)  | M      |

**Status legend**: `[x] MERGED` = on origin/main; `[~] IN-FLIGHT` = work-in-progress branch exists with commits, no PR; `[D] DECIDED` = persona panel converged, executor brief drafted, awaiting dispatch; `[ ] PENDING` = not yet started; `[!] BLOCKED-NEEDS-SIGNOFF` = STOP-AND-SURFACE per CLAUDE.md §10.

Effort key: S = single sitting; M = a few hours; L = a day plus.

Hard dependencies: **R1, R1.5, R2, and R3 are independent** (parallel-safe; all touch different files). **R1.6 depends on R1.5** (mart writer must be sound before catalogue regen surfaces the split rows). **R4 depends on R3** (consumes the extracted subcomponents). **R5 depends on R3** (mounts inside the extracted Scatter+Sankey region). **R6 depends on R4 + R5** (caption + gating tie into rearranged panels and the new Sankey button). **R7 depends on R1.5** (`event_summary.csv` must include J&K U08 before share-card iteration) and on R4 (head-meta references the right state slug + event_id grammar); R7 can run in parallel with R5 + R6 once R4 ships.

Parallel front: `{R1, R1.5, R2, R3}` may ship simultaneously; then `R1.6 -> R4 -> {R5, R6, R7}` sequential at the R4 boundary, with R5/R6/R7 then running concurrently. R1.6 can also be parallel with R4 if their reviewers split cleanly.

## Section 2 - Row R1: MH 266->288 writer rip

**Scope**: Add one `EciEventSpec` row to the `JOBS` tuple in [backend/yen_gov/canonical/adapters/eci_form10_ae.py](backend/yen_gov/canonical/adapters/eci_form10_ae.py); DELETE [backend/yen_gov/canonical/adapters/thecont1_mh_ae2024.py](backend/yen_gov/canonical/adapters/thecont1_mh_ae2024.py) + its tests + its CLI registration in `backend/yen_gov/cli.py`; re-run `python -m yen_gov ingest-eci-ae-form10 --root .` to regen MH 2024 with all 288 ACs.

**Files touched**:

| File                                                                                                                        | Change |
| --------------------------------------------------------------------------------------------------------------------------- | ------ |
| [backend/yen_gov/canonical/adapters/eci_form10_ae.py](backend/yen_gov/canonical/adapters/eci_form10_ae.py)                  | +1 `EciEventSpec` row in `JOBS` tuple; +1 line in module docstring state-list |
| [backend/yen_gov/canonical/adapters/thecont1_mh_ae2024.py](backend/yen_gov/canonical/adapters/thecont1_mh_ae2024.py)        | DELETE |
| `backend/tests/test_thecont1_mh_ae2024.py` (or equivalent test name; search `grep -rn thecont1_mh_ae2024 backend/tests/`)   | DELETE |
| [backend/yen_gov/cli.py](backend/yen_gov/cli.py)                                                                            | DELETE the `ingest-mh-ae-2024-thecont1` (or equivalent) command registration; verify `ingest-eci-ae-form10` stays |
| `backend/tests/test_eci_form10_ae.py`                                                                                       | +1 fixture or +1 parameterised case proving MH 2024 lands all 288 ACs from a 3-AC stub XLSX |
| [datasets/elections/assembly/state=maharashtra/election=2024/candidacies.csv](datasets/elections/assembly/state=maharashtra/election=2024/candidacies.csv) | REGEN (target band [4100, 4300] rows) |
| [datasets/elections/assembly/state=maharashtra/election=2024/summary.csv](datasets/elections/assembly/state=maharashtra/election=2024/summary.csv) | REGEN (target 288 data rows) |
| [datasets/data/datapoints/electoral/maharashtra_election_results.csv](datasets/data/datapoints/electoral/maharashtra_election_results.csv) | REGEN (the MH 2024 segment) |

**EciEventSpec row to append** (place between the 2024 Bihar 2025 entry and the existing 2024 Jharkhand entry per chronological ordering convention; copy the field names verbatim from the existing rows):

```python
EciEventSpec(
    "2024_MH_10-Detailed_Results_1744893339.xlsx",
    "maharashtra", "S13", "Maharashtra", "Maharashtra",
    2024, "assembly-2024", "2024-11-20", "AcGenNov2024",
),
```

The XLSX `STATE/UT NAME` column 1 value is verbatim `Maharashtra` (verified by openpyxl probe 2026-06-15); `expected_state_name` matches. `polled_on` 2024-11-20 matches the assembly poll date.

**Acceptance gates** (all 7 oracles MUST pass; failure of 1, 2, 6, or 7 = revert):

| # | Oracle                            | Command                                                                                                                     | Expected |
| - | --------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | -------- |
| 1 | summary row count                 | `python -c "import csv; print(len(list(csv.DictReader(open('datasets/elections/assembly/state=maharashtra/election=2024/summary.csv')))))"` | `288` |
| 2 | summary AC range                  | `python -c "import csv; acs=sorted(int(r['constituency_no'] if 'constituency_no' in r else r['ac_no']) for r in csv.DictReader(open('datasets/elections/assembly/state=maharashtra/election=2024/summary.csv'))); assert acs==list(range(1,289)), set(range(1,289))-set(acs); print('ok')"` | `ok` |
| 3 | Tier-A clean                      | `cd backend && pytest -q -k "form10 or assembly_results"`                                                                   | exit 0 |
| 4 | Tier-B clean                      | `python -m yen_gov validate --root .`                                                                                       | exit 0 |
| 5 | Idempotence                       | re-run `python -m yen_gov ingest-eci-ae-form10 --root .`; `git diff --stat datasets/elections/assembly/state=maharashtra/election=2024/` | `0 files changed` |
| 6 | Tier-C parity vs thecont1 baseline | save baseline summary BEFORE R1 to `.runtime/mh2024-summary-baseline.csv`; after R1 regen, diff on `(constituency_no, winner_party_id, winner_votes)` for the 266 overlap ACs. Asserts: `matches=266, mismatches=0, new_landed=22`. | mismatches=0 (otherwise STOP-AND-SURFACE per ESCALATE) |
| 7 | source.csv FK + no-thecont1 row   | `grep "src-0c04cb845d7e" datasets/elections/assembly/state=maharashtra/election=2024/summary.csv | wc -l` -> `288`; `grep -i "thecont1" datasets/data/entities/source.csv | wc -l` -> `0` (no thecont1 row should ever have been minted; if found, separate STOP) | as stated |
| 8 | Frontend smoke                    | start dev server; navigate `/maharashtra/elections/assembly-2024`; assert page reads "288 constituencies" (or equivalent); zero `[error]` console events | passing |

**Oracle 6 setup**: before R1 mutates the disk, the executing agent MUST capture `cp datasets/elections/assembly/state=maharashtra/election=2024/summary.csv .runtime/mh2024-summary-baseline.csv` to `.runtime/` (gitignored). After regen, the parity diff runs against this baseline. ANY mismatch on the 266 overlap rows = party-resolution drift across publishers = STOP-AND-SURFACE per [CLAUDE.md section 10](CLAUDE.md).

**Tests** (per [docs/architecture/testing.md](docs/architecture/testing.md) tier matrix):

- **Unit**: extend `backend/tests/test_eci_form10_ae.py` with a parameterised case for MH 2024 using a tmp_path XLSX fixture (3 ACs synthetic). Assert: `summary` row count = 3; `candidacies` row count matches stub; source_id derivation = `derive_source_id('Election Commission of India', 'Statistical Report Section 10 (Detailed Results) - S13 AcGenNov2024', 'AcGenNov2024')`.
- **Contract**: no new file needed; existing Tier-A schema-conformance covers the regen.
- **Integration**: oracle 5 (idempotence) is the integration test.
- **E2E**: oracle 8 (browser smoke per [CLAUDE.md section 13](CLAUDE.md)).

**Oracle (load-bearing single check)**: oracle 2 (`AC NO. range is 1..288 with zero gaps`). If this passes, the user-reported bug is fixed.

**Dependencies**: none.

**Reviewers** (named because the row crosses authority lines): Max (data shape - source identity, processing_level), Fowler (writer rip safety + idempotence).

## Section 2.5 - Row R1.5: AssemblyElections mart coverage fix

**Scope**: DELETE the display-string-parsing bridge in [backend/yen_gov/canonical/derived/event_summary.py](backend/yen_gov/canonical/derived/event_summary.py); invert the writer loop to iterate the catalogue's `states.items()` directly (the outer dict key IS the `eci_code`); derive each state's disk slug via the existing canonical helper `eci_to_lgd_slug()` at [backend/yen_gov/canonical/adapters/eci/state_slug.py](backend/yen_gov/canonical/adapters/eci/state_slug.py). Regen the mart. Verify J&K U08 lights up on `/t/elections/assemblies` and 35 sibling cards do not regress.

**Root cause** (5-persona review 2026-06-15; supersedes the earlier "ignores aliases" framing):

The writer's `_build_slug_to_eci_via_catalogue()` parses the LEADING TOKEN of each catalogue `display` string (e.g. `"Jammu & Kashmir Assembly..."` -> `"Jammu & Kashmir"`) and matches it against `state_codes.csv.lgd_name`, with a 6-variant hard-coded fallback set (`NCT of {name}`, `{name} (UT)`, etc.). This is wrong by construction: the catalogue's OUTER DICT KEY is the `eci_code` itself (`states["U08"] -> [...]`). The writer is re-deriving via string parsing what the contract already hands it as a structural key - a Canonical Data Model violation per Hohpe (EIP ch.8).

The correct shape (Gregor's verdict, ratified by Fowler + Max):

1. Iterate `for eci_code, events in catalogue["states"].items():` - `eci_code` is the join key.
2. Derive disk slug once via `eci_to_lgd_slug(eci_code)` - the single canonical helper, already used by [backend/yen_gov/canonical/derived/party_pages.py](backend/yen_gov/canonical/derived/party_pages.py) (precedent).
3. Glob `state=<slug>/election=<year>/summary.csv`.
4. Delete `_build_slug_to_eci_via_catalogue` + `_parse_state_name` + the 6-variant hard-coded set.

Why the brief's "add aliases" framing was rejected: `state_codes.csv.aliases` is correctly load-bearing for the OTHER 3 bridges (`mcc_seizures`, `tcpd_pc`, `bhukyavenkatamahesh` - they do `publisher_name -> slug`, an open-vocabulary job that legitimately needs aliases). The event_summary writer does NOT need aliases because it does NOT need to bridge slug-or-name to eci_code - the catalogue already gives it eci_code. Reading aliases would have patched the U08 symptom while preserving the architectural smell (Rule of Three not yet met: only this one site has Job A `eci_code -> slug`; the other three do Job B `publisher_name -> slug`).

**Files touched**:

| File | Change |
| --- | --- |
| [backend/yen_gov/canonical/derived/event_summary.py](backend/yen_gov/canonical/derived/event_summary.py) | DELETE `_build_slug_to_eci_via_catalogue()` + `_parse_state_name()` + the 6-variant hard-coded set. Invert the main loop to iterate `catalogue["states"].items()`. Replace each per-state slug derivation with `eci_to_lgd_slug(eci_code)` imported from `backend.yen_gov.canonical.adapters.eci.state_slug`. Add a module-level docstring sentence: "State_code is recovered from the catalogue's outer dict key, never from display-string parsing." Net LOC: deletion-heavy (approx -40 / +15). |
| `backend/tests/test_event_summary_writer.py` | Extend with a parameterised fixture: stub catalogue declaring U08 display `"Jammu & Kashmir Assembly - September-October 2024"`; stub on-disk path `state=jammu-and-kashmir/election=2024/summary.csv` with 3 winners; assert mart row for `(event_id=assembly-2024, state_code=U08)` emits. Add 2 control cases (NCT Delhi U05, Puducherry U07) proving the variant-set deletion did not break the already-working states. |
| [datasets/data/marts/elections/event_summary.csv](datasets/data/marts/elections/event_summary.csv) | REGEN. Pre-R1.5: 312 rows. Post-R1.5: 313 rows (+1 for U08 assembly-2024). |
| [docs/architecture/data/canonical-store.md](docs/architecture/data/canonical-store.md) | +1 paragraph under a "Bridges and identity" subsection: "The slug<->ECI state-code bridge is `datasets/taxonomy/lgd_states.json` consumed via `backend.yen_gov.canonical.adapters.eci.state_slug.eci_to_lgd_slug`. Writers MUST NOT recover `state_code` from display-string parsing when the contract already exposes it as a structural key or column." Cite the R1.5 deletion as the precedent. |

**Out of R1.5 scope** (concretely deferred with named follow-ups, NOT silent punts):

- **Bihar S04 catalogue identity bug** (TWO rows with `event_id="assembly-2005"` for Feb 2005 hung + Nov 2005 re-poll; the ONLY duplicate `(eci, kind, event_id)` tuple in the entire catalogue): promoted to NEW **Row R1.6** in this plan-doc (Section 2.6). Catalogue schema minor bump 1.3 -> 1.4; event_id grammar extended to `assembly-<YYYY>-<month-slug>`; writer fan-out + frozen-URL alias. Reviewers per CLAUDE.md \u00a70a: Hans + Max (data shape) + Gregor (schema-version + URL grammar contract). Not silently deferred: Nov 2005 (the constitutionally consequential election that produced the Nitish Kumar government) is INVISIBLE in citizen data today; silence is a Generalisation + Blame double violation per Rosling.
- **567 disk-only assembly events** across 31 of 36 polities (NOT just J&K + Bihar - top-10 gaps: AP=40, UP=37, MP=36, WB=30, Bihar=29, Karnataka=28, MH=28, Rajasthan=26, Gujarat=25, Punjab=23; J&K=21). Spawned sibling plan-doc: [TODO/20260615-elections-catalogue-completeness-handover.md](TODO/20260615-elections-catalogue-completeness-handover.md). Per Max's review: catalogue schema v1.3 ALREADY supports `kind \u2208 {assembly, parliament, general_bye, assembly_bye, by_election}` and the `assembly-bye-<YYYY>-<seat-slug>` event_id grammar (precedent: `state=karnataka/election=2024-channapatna-bye/`). The 567-gap is POPULATION debt, not SCHEMA debt - no schema bump in the spawned plan.
- **Any other display-drifted state/UT** uncovered by the post-fix per-state audit (gate 6): STOP-AND-SURFACE per [CLAUDE.md \u00a710](CLAUDE.md). The Gregor fix expects to rescue 0 OTHER states (the hard-coded variants already handled NCT Delhi etc.; iterating the catalogue's outer key gives every polity the same correct treatment), so any unexpected drift = scope-creep, not silent absorption.

**Acceptance gates**:

| # | Oracle | Command | Expected |
| - | --- | --- | --- |
| 1 | Writer test | `cd backend && pytest -q backend/tests/test_event_summary_writer.py` | exit 0 |
| 2 | Mart regen idempotent | `python -m yen_gov derive-event-summary --root .`; rerun; `git diff --stat datasets/data/marts/elections/event_summary.csv` | second run: 0 changed |
| 3 | Mart row count delta | `python -c "import csv; print(len(list(csv.DictReader(open('datasets/data/marts/elections/event_summary.csv')))))"` | `313` (was 312) |
| 4 | U08 row present | `grep ',U08,' datasets/data/marts/elections/event_summary.csv \| wc -l` | `1` (was 0) |
| 5 | Diff-shape invariant | `git diff datasets/data/marts/elections/event_summary.csv \| grep -E "^[+-][^+-]" \| wc -l` | exactly `1 +` data line; `0 -` data lines - proves the Gregor fix did not silently flush other rows |
| 6 | Per-state audit clean (except S04 Bihar) | re-run the bounded per-state catalogue-vs-mart audit used in Section 0.3 | only `S04` listed; U08 absent; every other state still clean |
| 7 | Doctrine doc updated | `grep -n "Bridges and identity" docs/architecture/data/canonical-store.md` | non-empty match |

**Section 13 browser smoke** (10 routes per Jony 2026-06-15 review; `read_page` sufficient - no `screenshot_page`, this is a pure text-content fix):

1. `/t/elections/assemblies` - full grid; expect EXACTLY 36 cards; each card matches one of the three known copy states (live / no-legislature / catalogue-empty).
2. `/t/elections/assemblies` J&K U08 card - expect FLIPPED from "No election in the catalogue yet." to "Latest: 2024 / JKNC / N of M / X% turnout". **Load-bearing.**
3. `/t/elections/assemblies` NCT Delhi U05 card - expect UNCHANGED live row (control for the "NCT of" display-prefix drift class).
4. `/t/elections/assemblies` Puducherry U07 card - expect UNCHANGED live row (control for UTs WITH legislature).
5. `/t/elections/assemblies` Andaman & Nicobar U01 card - expect UNCHANGED `No state legislature.` (control for the "&" drift class on a no-legislature polity).
6. `/t/elections/assemblies` DNHDD U03 card - expect UNCHANGED `No state legislature.` (control for the long-slug drift class).
7. `/t/elections/assemblies` Lakshadweep U06 card - expect UNCHANGED `No state legislature.` (non-drifted no-legislature UT control).
8. `/t/elections/assemblies` Bihar S04 card - expect UNCHANGED with the known `-1` audit gap (Feb 2005 wins via first-match; R1.6 is what fixes it).
9. `/t/elections/assemblies` Tamil Nadu S22 card - expect UNCHANGED (pure non-drifted control).
10. `/jammu-and-kashmir/elections/assembly-2024` direct event page - expect NO regression (R1.5 does not touch this seam; verifies no spillover into per-event pages).

**Non-goal**: R1.5 does NOT touch AssemblyElections card copy. The 3-state grammar (live / no-legislature / catalogue-empty) is preserved verbatim; only the underlying mart row that selects WHICH grammar to render changes.

**Oracle (load-bearing single check)**: oracle 4 (`grep ',U08,' ... | wc -l` returns 1) AND smoke route #2 (J&K card flips). Both must hold.

**Dependencies**: none (parallel-safe with R1, R1.6, R2, R3).

**Correction level**: 2 per [CLAUDE.md \u00a76](CLAUDE.md) (1-2 files + explicit behaviour change; deletion is structural but at the single-file level).

**Reviewers**: Gregor (canonical-data-model contract - outer-dict-key as join key); Fowler (writer rip discipline + Beck two-hat: pure structural deletion); Max (no schema change; aliases column stays sparse for the other 3 bridges); Jony (10-route smoke list); Hans (verify no Bihar regression spillover).

## Section 2.6 - Row R1.6: Bihar 2005 catalogue identity rip

**Scope**: Resolve the duplicate-`event_id` PK collision at S04 Bihar 2005 in [datasets/taxonomy/election_events.json](datasets/taxonomy/election_events.json). Bump the catalogue schema `x-version` 1.3 -> 1.4 (additive: extend `event_id` regex to allow `<kind>-<YYYY>-<month-slug>` for collision cases; precedent: v1.3 already allows `assembly-bye-<YYYY>-<seat-slug>`). Mint `assembly-2005-feb` + `assembly-2005-nov`; carry forward existing `event_id_aliases` `["AcGenFeb2005"]` and `["AcGenNov2005"]` (already in catalogue + already encoded in backend `EVENTS_BY_MONTH` at [backend/yen_gov/sources/eci/events.py#L506-L513](backend/yen_gov/sources/eci/events.py)); also add the prior canonical `"assembly-2005"` to BOTH rows' `event_id_aliases` so frozen URL inbound links resolve. Fan out the on-disk `state=bihar/election=2005/` dir into `election=2005-feb/` + `election=2005-nov/`. Regen the mart; freeze the catalogue PK invariant via a new contract test.

**Why this row exists in this plan and is not silently deferred**: doctrine at [docs/architecture/backend/sources-eci.md](docs/architecture/backend/sources-eci.md) names Bihar 2005 as "the anchor: February 2005 and October-November 2005 are distinct Assembly elections and must not collapse onto one `event_id`" - directly violated by the catalogue's current shape today. Backend `EVENTS_BY_MONTH` ALREADY encodes the split (`("S04",2005,2): EventInfo("AcGenFeb2005",False)`, `("S04",2005,11): EventInfo("AcGenNov2005",False)`); the catalogue + mart + URL grammar are the lagging surfaces. Hans's verdict (2026-06-15): the November 2005 election (which ended ~15 years of Lalu/Rabri rule and produced the Nitish Kumar government) is INVISIBLE in citizen data today; silent deferral would be a Generalisation + Blame double violation per Rosling's ten instincts.

**Files touched**:

| File | Change |
| --- | --- |
| [datasets/schemas/election-events.schema.json](datasets/schemas/election-events.schema.json) | Bump `x-version` 1.3 -> 1.4; extend the `event_id` pattern to accept `<kind>-<YYYY>-<month-slug>` (one of `feb` / `mar` / `apr` / `may` / `jun` / `jul` / `aug` / `sep` / `oct` / `nov` / `dec` to cover any future same-year multi-phase collision); add `x-changelog` entry "1.4: extend `event_id` grammar with `<kind>-<YYYY>-<month-slug>` for same-year same-state same-kind collision cases (anchor: Bihar 2005 Feb/Nov)". |
| [datasets/taxonomy/election_events.json](datasets/taxonomy/election_events.json) | S04 Bihar: rename the row at line ~833 (`polled_on=2005-02-23`) `event_id` from `"assembly-2005"` to `"assembly-2005-feb"`; rename the row at line ~845 (`polled_on=2005-11-19`) from `"assembly-2005"` to `"assembly-2005-nov"`. Carry existing aliases (`AcGenFeb2005` and `AcGenNov2005`) forward unchanged; ADD `"assembly-2005"` to BOTH rows' `event_id_aliases` so the old canonical id remains resolvable for frozen URLs. |
| `datasets/elections/assembly/state=bihar/election=2005/` -> `election=2005-feb/` + `election=2005-nov/` | `git mv` plus partition: split the 486-row `summary.csv` + matching `candidacies.csv` by `polled_on`-prefix or by source-XLSX provenance. Hans + Max own the precise partition rule; the safe default is to split by the entity_id form already used at the source (Feb constituencies use the pre-2008-delim AC enumeration; Nov uses the post-2008-delim AC enumeration where applicable). If partition is ambiguous, STOP-AND-SURFACE. |
| [backend/yen_gov/canonical/derived/event_summary.py](backend/yen_gov/canonical/derived/event_summary.py) | After R1.5 lands, the iterating loop picks up both new event_ids automatically; the first-match-wins issue at [event_summary.py `_find_assembly_event`](backend/yen_gov/canonical/derived/event_summary.py) dissolves once the catalogue carries distinct ids. NO writer code change in R1.6 itself beyond regen. Optionally (forward-defense): detect any future same-PK collision and emit a `processing_note: "Catalogue PK collision pending; see R1.6 doctrine"` on the surviving row. Orchestrator's call. |
| [backend/yen_gov/sources/eci/events.py](backend/yen_gov/sources/eci/events.py) | NO change. `EVENTS_BY_MONTH` already returns the right backend slugs (`AcGenFeb2005`, `AcGenNov2005`). The catalogue was the lagging surface. |
| `backend/tests/test_election_events_consistency.py` (NEW or extend) | Assert NO duplicate `(eci_code, kind, event_id)` tuples in `election_events.json` across all states. Freezes the doctrine that the PK collision class cannot recur. |
| `backend/tests/test_event_summary_writer.py` | +1 case: Bihar 2005 stub with both new event_ids in the catalogue stub; assert both rows surface in the mart with the right `(event_id, state_code)` PK and the right winner identities. |
| [docs/architecture/frontend/url-grammar.md](docs/architecture/frontend/url-grammar.md) | +1 line under the relevant URL-grammar section: "Same-year same-state same-kind collisions disambiguate via `<kind>-<YYYY>-<month-slug>` (anchor: Bihar 2005 Feb/Nov). Query-param variants are forbidden - path encodes identity per ADR-0052 and the catalogue PK." |
| [datasets/data/marts/elections/event_summary.csv](datasets/data/marts/elections/event_summary.csv) | REGEN. Bihar S04 rows pre-R1.6: 11 (with `assembly-2005` carrying Feb's identity ambiguously). Post-R1.6: 12 (`assembly-2005-feb` + `assembly-2005-nov` as separate rows). Net +1. |

**Frozen URL surface** (Jony + Hans pick which of these two ships; default = redirect):
- Option A (default): `/bihar/elections/assembly-2005` issues a 200 + renders a small chooser page ("This election ran in two phases - pick February 2005 or November 2005") with two prominent links. Preserves bookmarks; one citizen-visible click cost.
- Option B: `/bihar/elections/assembly-2005` issues an in-app redirect to `/bihar/elections/assembly-2005-feb` (the chronologically earlier event); no click cost; loses the chance to teach the citizen there were two distinct elections. Hans: weaker; pick A.

**Acceptance gates**:

| # | Oracle | Command | Expected |
| - | --- | --- | --- |
| 1 | Schema bump clean | `python -m yen_gov validate --root .` | exit 0 |
| 2 | Catalogue no-duplicate-PK invariant | `cd backend && pytest -q backend/tests/test_election_events_consistency.py` | exit 0 |
| 3 | Bihar 2005 both rows in mart | `grep ',S04,' datasets/data/marts/elections/event_summary.csv \| grep '2005' \| wc -l` | `2` (was 1) |
| 4 | Frozen URL still resolves | dev server: GET `/bihar/elections/assembly-2005` returns 200 + chooser per Option A | passing |
| 5 | New URLs render | `/bihar/elections/assembly-2005-feb` and `/bihar/elections/assembly-2005-nov` both 200 + populated HeroCards | passing |
| 6 | Tier-A schema-conformance | `cd backend && pytest -q -k election_events` | exit 0 |
| 7 | Tier-B FK closure | `python -m yen_gov validate --root .` | exit 0 |

**Citation requirements** (per [CLAUDE.md \u00a712](CLAUDE.md)):
- Source IDs for both new mart rows derive deterministically via `derive_source_id`:
  - `("Election Commission of India", "Statistical Report on the General Election 2005 to the Legislative Assembly of Bihar - February 2005", "AcGenFeb2005")`
  - `("Election Commission of India", "Statistical Report on the General Election 2005 to the Legislative Assembly of Bihar - November 2005", "AcGenNov2005")`
- `polled_on` values `2005-02-23` (Feb 3-phase poll last phase) and `2005-11-19` (Oct-Nov 5-phase poll last phase) are already in the catalogue + already encoded in `EVENTS_BY_MONTH`. NOT curator-guessed.

**Out of R1.6 scope**:
- Other potential same-year same-kind collisions: none found per the 2026-06-15 catalogue audit (Bihar 2005 is the ONLY duplicate tuple across all 36 polities). If a future ingest mints another, gate 2 fails LOUD.
- Phase-splitting historical multi-phase elections where the catalogue does NOT currently carry duplicate ids - R1.6 splits ONLY catalogue rows that already collide. Broader phase-splitting is a separate question owned by Hans + Max.

**Oracle (load-bearing single check)**: gate 2 (catalogue PK invariant passes) AND gate 3 (Bihar 2005 has 2 mart rows). Both must hold.

**Dependencies**: R1.5 (mart writer must be sound before catalogue regen surfaces the split rows).

**Correction level**: 3 per [CLAUDE.md \u00a76](CLAUDE.md) (catalogue schema bump + data fan-out + URL grammar extension cross-cutting 2-3 files; structural at the contract level).

**Reviewers** (per CLAUDE.md \u00a70a): Hans + Max (data shape - identity, partition rule, citation); Gregor (schema-version contract + URL grammar); Fowler (writer regen idempotence + git-mv safety); Jony (frozen-URL chooser surface).

### Section 2.6.1 - R1.6 STOP-AND-SURFACE forensic report + 3-persona panel convergence (2026-06-15)

**Triggered**: R1.6 executor dispatched 2026-06-15; agent ran the brief's verbatim STOP condition after read-only probe of `datasets/elections/assembly/state=bihar/election=2005/`. ZERO files touched by the agent; ZERO commits. The plan-doc's Section 2.6 "safe default" partition heuristic ("Feb uses pre-2008-delim, Nov uses post-2008-delim") is FACTUALLY WRONG: the 2008 Delimitation Order took effect from 2010 onwards, so BOTH Bihar 2005 elections used 1976-delim entity_ids. The on-disk data CANNOT be deterministically partitioned without re-ingest from upstream TCPD.

**Forensic evidence** (read-only by R1.6 agent):

- `candidacies.csv`: 5326 data rows = ~1.97x the ~2700 expected for one Bihar election (243 ACs x ~11 candidates).
- Sample AC `IN-AC-1976-bihar-2` (KARGAHAR): TWO position-1 winners stacked under one entity_id (`PURNAMASI RAM` JD(U) age 52 votes 59151 share 48.99% + `PURNMASI RAM` JD(U) age 52 votes 60794 share 50.70% - same person, one-letter spelling drift, classic TCPD Feb-vs-Nov pair).
- 2092 ACs across the file carry duplicate position-rankings under one entity_id.
- `summary.csv`: 243 data rows but 28 with negative `margin_pct`, 84 with `winner_candidate == runnerup_candidate` - mathematically impossible; writer collapsed two contests/AC into one corrupted row.
- NO row-level attribution columns: no `polled_on`, `month`, `phase`, `event_id`, separate `source_id`. Both elections share `src-0c1b8f274551`.
- All entity_ids are `IN-AC-1976-bihar-<n>` - both Feb 2005 + Nov 2005 used 1976-delim.
- Root cause: path scaffolding at [backend/yen_gov/canonical/reingest/elections.py#L93](backend/yen_gov/canonical/reingest/elections.py) keys dirs by `election_year: int` (NOT `event_id`). Adapter at [backend/yen_gov/canonical/adapters/eci_ae_panel.py#L233](backend/yen_gov/canonical/adapters/eci_ae_panel.py) correctly groups by `(year, month)` and resolves `event_id_for(state_code, year, month)` against `EVENTS_BY_MONTH` at [backend/yen_gov/sources/eci/events.py#L510](backend/yen_gov/sources/eci/events.py) (which has `("S04", 2005, 2) -> AcGenFeb2005` + `("S04", 2005, 11) -> AcGenNov2005` correctly pinned) - but both groups collide into the same `state=bihar/election=2005/` dir; second write overwrites/stacks.
- Mart-writer residual bug at [backend/yen_gov/canonical/derived/event_summary.py#L262](backend/yen_gov/canonical/derived/event_summary.py): `_find_assembly_event` does `polled_on.startswith(f"{year}-")` first-match-wins - would credit ALL Bihar 2005 rows to whichever catalogue row sorts first even after a clean catalogue split.

**3-persona escalation panel convened in parallel** (Hans + Max + Gregor); ZERO disagreement on rejecting Path C (collapse - doctrinally falsifies the Nov-2005 Nitish-Kumar-government formation) and Path B (catalogue-only - would render mathematically nonsensical charts through clean URLs); STRONG convergence on a structural fix.

**Verdicts** (compressed):

- **Hans (Governance)**: Path D - catalogue 2-row split + on-disk untouched + citizen-facing escrow notice + Path A as sibling plan-doc. Constitutional honesty (President's Rule -> dissolution -> fresh poll is a textbook Centre-State fault line; *Rameshwar Prasad v Union of India* struck down Buta Singh's dissolution recommendation). "When the data on disk cannot defend the story the catalogue tells, withdraw the chart before you correct the story."
- **Max (Indicator Scout)**: Path A - full structural fix in one PR; subsume Path B's frozen-URL alias as a sub-step; promote the audit helper from the spawned [TODO/20260615-elections-catalogue-completeness-handover.md](TODO/20260615-elections-catalogue-completeness-handover.md) section 5 into the same PR; add writer-entry assertion at `assembly_*_path` so raw int-year writes fail-loud. Upstream TCPD genuinely carries the month - the adapter is honest; the writer is the corruption surface. Iceberg N today = 1 colliding tuple, but the 567-event population debt anticipates more (any future bye + regular poll same-year). "When the upstream carries the month and the local writer drops it, the structurally honest fix is the writer - never the catalogue, never the doctrine, never the citizen's mental model."
- **Gregor (Architect)**: Path A' - strangler-fig variant of A. EIP framing: Format Transformer at the writer seam + Content-Based Router at the dir seam; the Canonical Data Model promotes its discriminator from `year_int` to `event_id` (the identity it should have had on day one). Migration: (1) additive path-builder kwarg `event_id: str | None` alongside existing `election_year: int`; (2) Bihar-2005-only re-emit via the AE-panel adapter (thread `event_id` from adapter through writer); (3) mart resolver fix in same PR (must address first-match-wins residual bug or Path A fails gate 5); (4) delete `election=2005/` dir + 2 new dirs + migration-ledger rows; (5) leave the other 35 states on year-keyed dirs until a real consumer needs disambiguation. "A Canonical Data Model is a promise about identity - when identity collapses, you fix the model, not the row."

**Converged resolution - Path A' (Gregor's strangler-fig)** with Max's amendments:

1. Catalogue 2-row split (Feb + Nov as `assembly-2005-feb` + `assembly-2005-nov`); inherits Hans's doctrinal truth.
2. Schema 1.3 -> 1.4 grammar extension (no-op - schema v1.3 pattern `^[A-Za-z0-9_-]+$` already accepts these slugs; v1.4 documents the convention).
3. Path-builder additive kwarg `event_id: str | None` in writer; raw `election_year`-only writes for known-colliding `(state_code, year)` tuples fail-loud (writer-entry assertion).
4. AE-panel adapter threads `event_id` through to writer for Bihar 2005 only (one-state re-emit).
5. Mart writer `_find_assembly_event` keys by `(state_code, event_id)` when present; year-fallback otherwise - fixes the first-match-wins residual in the SAME PR.
6. Delete `state=bihar/election=2005/`; add `election=2005-feb/` + `election=2005-nov/` to migration ledger.
7. Frozen-URL alias: legacy `/bihar/elections/assembly-2005` redirects to `assembly-2005-nov` (Nitish-formation event; recency rule) - Hans's escrow notice is dropped because the re-emit lands in the same PR (no intermediate corrupted state ships to citizens).
8. Promote `EVENTS_BY_MONTH` audit helper from sibling handover-doc section 5 into the same PR (cheap; same touch surface).
9. New contract test `backend/tests/test_election_events_consistency.py` freezes the catalogue PK invariant.

**Owner(s) per CLAUDE.md \u00a70a**: Fowler (writer rip + dir migration safety + idempotence) + Gregor (path-builder contract change + mart resolver contract change + migration-ledger shape) + Hans (catalogue identity = event_id; constitutional doctrine; frozen-URL disposition) + Max (writer-entry assertion + audit helper + source-vetting).

**Effort revised**: M -> L (one PR, ~150-200 LOC backend + Bihar-only re-emit + mart regen + 2 new contract tests).

## Section 3 - Row R2: NEW state-elections landing route

**Scope**: Mint `/<state>/elections/` as a route. Today it 404s. New file [frontend/src/routes/StateElectionsLanding.svelte](frontend/src/routes/StateElectionsLanding.svelte) renders: breadcrumb, page header `"{State} elections"`, hero card of the LATEST event per body (one for assembly, one for parliament if both exist), two parallel tables (Vidhan Sabha + Lok Sabha rows) each with year-as-link, cross-link to `/<state>` welfare context. Mounted in [frontend/src/main.ts](frontend/src/main.ts) BEFORE the existing `/<state>/elections/<event>` route.

**Files touched**:

| File                                                                                                                | Change |
| ------------------------------------------------------------------------------------------------------------------- | ------ |
| [frontend/src/routes/StateElectionsLanding.svelte](frontend/src/routes/StateElectionsLanding.svelte)                | NEW. Includes the J-elevated-15 last-viewed-event read pass: `onMount` reads `localStorage.getItem("yen-gov:last-event:" + state_slug)`, checks 30-day expiry, renders a `Last viewed` badge next to the matching year-as-link. |
| [frontend/src/main.ts](frontend/src/main.ts) or `app.svelte` route table                                            | Register `/<state>/elections/` BEFORE `/<state>/elections/:event` (route order matters - the bare path must not be captured by `:event`) |
| [frontend/src/routes/StateElection.svelte](frontend/src/routes/StateElection.svelte) - write pass                   | J-elevated-15 amend: +1 `onMount` block (~8 LOC) writing `localStorage.setItem("yen-gov:last-event:" + state_slug, JSON.stringify({event_id, viewed_at_iso: new Date().toISOString(), body}))`. Pure side-effect; no server roundtrip. |
| `frontend/src/lib/elections/last-event-memory.ts`                                                                   | NEW (~25 LOC). Pure helpers `readLastEvent(state_slug)` + `writeLastEvent(state_slug, event_id, body)` + `isLastEventFresh(timestamp)` (30-day cutoff). Localises the localStorage key contract to one file so future renames stay safe. |
| `frontend/src/lib/elections/last-event-memory.test.ts`                                                              | NEW (~30 LOC). Tier-A unit using `vi.useFakeTimers()`: write -> read returns the value; write -> 30 days + 1 ms later -> read returns null; key contains state_slug verbatim. |
| `frontend/src/routes/StateElectionsLanding.test.ts`                                                                 | NEW unit; synthetic catalogue projection; assert "2 tables rendered when both bodies have events" + "1 table when only assembly" + "no panel when state has 0 events" + "Last viewed badge renders when fresh memory exists for matching event" |
| [frontend/e2e/golden-path.spec.ts](frontend/e2e/golden-path.spec.ts)                                                | +1 case: visit `/maharashtra/elections/`; assert breadcrumb + 2 tables + at least 1 year-as-link points to `/maharashtra/elections/<event>` |
| `docs/architecture/frontend/charts/election-views.md`                                                               | +1 paragraph naming the new route's place in the URL grammar |
| [frontend/src/lib/elections/crumbs.ts](frontend/src/lib/elections/crumbs.ts) (or wherever election breadcrumbs live)| +1 `stateElectionsLandingCrumbs(state_slug)` factory |

**View-model**: consumes the existing `fetchElectionEvents()` + `listEventsForState(catalogue, state_code)`; partitions by `kind === "assembly" | "parliament"`; latest-per-body via `sort by polled_on desc`. No new loader.

**Acceptance gates**:

- `bun run test -- StateElectionsLanding` green.
- `bun run check` 0 NEW errors.
- `bun x playwright test e2e/golden-path.spec.ts -g "elections landing"` green.
- Browser smoke per [CLAUDE.md section 13](CLAUDE.md): navigate `/maharashtra/elections/` (288 ACs landed by R1), `/karnataka/elections/`, `/lakshadweep/elections/` (no-legislature edge); zero `[error]` console events.

**Oracle**: visiting `/maharashtra/elections/` shows two tables (assembly + parliament), the assembly latest hero shows "Maharashtra Assembly 2024 - {winner} {seats}" with the year as a link to `/maharashtra/elections/assembly-2024`. Click the year -> lands on the per-event page.

**Dependencies**: none (R1 makes the per-event detail accurate; R2 ships the landing whether R1 is merged or not).

**Reviewers**: Jony + Citizen (UX); Fowler (route registration order).

## Section 4 - Row R3: Structural extraction (Beck two-hat, NO behaviour change)

**Scope**: Refactor the ~800-LOC monolithic [frontend/src/routes/StateElection.svelte](frontend/src/routes/StateElection.svelte) into the route file (thin composition) + 5 named subcomponents. NO behaviour change in this row. The route file's rendered DOM, every selector, every test assertion stays IDENTICAL.

**Files touched**:

| New file                                                                                                                              | Lifted from                                                                                                                                   | Approx LOC |
| ------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| [frontend/src/lib/elections/StateEventHero.svelte](frontend/src/lib/elections/StateEventHero.svelte)                                 | StateElection.svelte page-header block + KPI strip (~lines 785-970)                                                                          | ~150 |
| [frontend/src/lib/elections/StateEventMap.svelte](frontend/src/lib/elections/StateEventMap.svelte)                                   | StateAcMapD3 / StatePcMapD3 wrapper (~lines 972-985)                                                                                          | ~80 |
| [frontend/src/lib/elections/StateEventPartyComposite.svelte](frontend/src/lib/elections/StateEventPartyComposite.svelte)             | SeatDonut + PartyBar mounting blocks (~lines 920-1015)                                                                                        | ~120 |
| [frontend/src/lib/elections/StateEventScatter.svelte](frontend/src/lib/elections/StateEventScatter.svelte)                           | Scatter mount + scatter_data $derived block (~lines 1110-1115 + the derived block ~825-850)                                                  | ~90 |
| [frontend/src/lib/elections/StateEventConstituencyList.svelte](frontend/src/lib/elections/StateEventConstituencyList.svelte)         | ConstituenciesByDistrict + the flat 288-row table (~lines 1050-1100 + 1175+)                                                                  | ~180 |

The InlineCounterfactualSwing and AllParticipantsDirectory mounts stay where they are for R3 (R4 deletes them or moves them).

**Discipline**: every $state, $derived, $effect, and prop the lifted blocks reference becomes a prop on the new subcomponent. The route file shrinks to ~200 LOC of composition. No selector renames; no test rewrites. The `data-testid` attributes (if any) MUST be carried by the subcomponents' root elements verbatim.

**Acceptance gates**:

- `bun run check` 0 NEW errors (baseline tracked).
- `bun run test` full suite green; ZERO test files changed in this row (test files would only change if behaviour changed, which it does not).
- `bun x playwright test` full suite green.
- Visual smoke per [CLAUDE.md section 13](CLAUDE.md): `/maharashtra/elections/assembly-2024`, `/maharashtra/elections/general-2024`, `/karnataka/elections/assembly-2023` - all three pages render PIXEL-IDENTICAL to pre-R3 (compare screenshots; minor DOM-order differences from extraction are expected but visual layout is invariant).

**Oracle (load-bearing single check)**: `bun run test` returns a passing summary with zero changed test files. If test files change in this row, the row is mis-scoped (behavioural change snuck in) - revert.

**Dependencies**: none (R3 only depends on `main`).

**Reviewers**: Fowler (extraction discipline; Beck two-hat).

## Section 5 - Row R4: Behavioural reorder + new chrome + delete deadwood

**Scope**: Now that R3 has extracted the named subcomponents, rearrange them at the route level + add new chrome + delete dead components. This is the big citizen-facing change.

**Final section order** (Jony + Citizen ratified; baked into the route template):

| #  | Heading                                | Component                                                                                                                                  | Source |
| -- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------ |
| 1  | Breadcrumb                             | `<Breadcrumb>`                                                                                                                             | Unchanged |
| 2  | Page header (compare link REMOVED)     | inline                                                                                                                                     | Compare link moves to section 9 last-row |
| 3  | **HeroCards** (NEW)                    | extend `StateEventHero` with `KpiTile & { delta?: ... }`                                                                                  | New chrome |
| 4  | **Sibling-events year-chip rail** (NEW)| `frontend/src/lib/elections/SiblingEventsRail.svelte` (NEW)                                                                              | New chrome (Jony year-chip rail; no arrows) |
| 5  | Constituency choropleth                | `<StateEventMap>`                                                                                                                          | Moved up from current section 5 |
| 6  | **PartyComposite** (NEW shape)         | `<StateEventPartyComposite>` extended to per-party-row table with `[symbol][short][alliance-chip][seats-bar][seats-count][vote-share%]`     | Merges current SeatDonut + PartyBar |
| 7  | `<AllianceTotals>`                     | unchanged in R4; R6 adds the caption + render-when-data rule                                                                              | Stays |
| 8  | `<RacesBoard>`                         | unchanged                                                                                                                                  | Moved DOWN from current section 3 |
| 9  | `<StateEventScatter>` (turnout vs margin) | unchanged                                                                                                                              | Moved UP from current section 10 |
| 10 | `<StateEventConstituencyList>` (folded + searchable) | refactored to fold-all-collapsed-on-paint + sticky search; LAST row = inline Compare CTA            | Behavioural change |
| 11 | `<StateEventCrossEventSankey>` (NEW; opt-in) | ships in R5                                                                                                                          | New (R5) |
| 12 | All-parties directory                  | unchanged                                                                                                                                  | Stays last |

**DELETE** in this row:

- `<InlineCounterfactualSwing>` mount + its import - moved to Psephlab where the ephemeral-state ergonomics belong. Component file [frontend/src/lib/elections/InlineCounterfactualSwing.svelte](frontend/src/lib/elections/InlineCounterfactualSwing.svelte) stays on disk (Psephlab uses it); only the mount on StateElection comes off.
- The flat 288-row constituency table (current StateElection lines ~1050-1100) - redundant with `<StateEventConstituencyList>`. Delete the markup + its test cases that scaled with row count (those tests would otherwise violate [CLAUDE.md no-frontend-corpus-explosion](frontend/src/contracts/no-frontend-corpus-explosion.test.ts) once 288 ACs land).

**HeroCards spec**:

```
4 cards (2x2 mobile / 4-up desktop). Extend the StateOverview buildKpiTiles() pattern (lines 32-67).

| Card    | Icon                  | Metric                  | Delta-glyph rule |
| ------- | --------------------- | ----------------------- | ---------------- |
| Seats   | landmark.svg          | total_seats             | NONE (structural) |
| Voters  | users.svg             | total_electors compact  | pct-delta vs prev event; threshold >= 2%; copy "+5.1% vs Assembly 2019" |
| Polled  | vote.svg              | total_polled compact    | pct-delta vs prev event; threshold >= 2%; copy "+5.1% vs Assembly 2019" |
| Turnout | activity.svg          | turnout_pct             | pp-delta ALWAYS shown when prior exists; copy "+2.1pp vs Assembly 2019" |

Glyphs:
- trending-up.svg => emerald-600
- trending-down.svg => rose-600
- Sign convention: positive = larger than prior.

EDGE CASE - first event on record for this state-body:
  the `delta` field on the tile data is OMITTED (NOT zero, NOT em-dash).
  Tile renders without the glyph row. Silent absence is honest;
  "0%" invites comparing against nothing.
```

Source: prev-event lookup uses the existing `previous_same_body` derived in StateElection.svelte (verified lines 712-730). Sourcing the prev `turnout_pct` follows the **RATIFIED 2026-06-15** sourcing rule (user explicit acceptance):

- **If [TODO/20260615-elections-redesign-plan.md](TODO/20260615-elections-redesign-plan.md) row E2 has shipped** (`datasets/data/marts/elections/event_summary.csv` exists on main; CONFIRMED shipped 2026-06-15 per PR #1037), HeroCards loads from there - one row per `(event_id, state_code)`.
- **Otherwise** loads from per-event `datasets/elections/assembly/state=<slug>/election=<year>/summary.csv` (current + previous-same-body, 2 loader calls). Stable on `main` today.

The executing agent MUST detect at runtime which seam is available; do NOT pre-commit to one path. Pattern:

```ts
async function loadPrevTurnout(state_code: string, prev_event_id: string): Promise<number | null> {
  // Try event_summary.csv first; fall back to per-event summary.csv
  // ... implementation details left to the row author
}
```

**Sibling-events YEAR-CHIP RAIL** (NEW; between PageHeader and HeroCards; NO arrows, NO chevrons, NO "Prev"/"Next" labels - user 2026-06-15: "make the app for 2027 ready, not 1990 ready"):

Pattern reference: Spotify "Up Next", Apple Music year-picker, Instagram story-tray, Linear filter chips. Citizen reads left-to-right oldest-to-newest; current year filled; other years outline; 2px winner-color underline per chip cues "who won that year" in the same glance the IG ring cues "who has a story."

```svelte
<script lang="ts">
  type SiblingEvent = {
    event_id: string;
    year: number;
    href: string;
    winner_color: string | null;
    is_current: boolean;
  };
  let {
    events,
    prior_year,
    compare_href,
  }: {
    events: SiblingEvent[];
    prior_year: number | null;
    compare_href: string | null;
  } = $props();
</script>

<nav
  class="-mx-2 flex gap-2 overflow-x-auto whitespace-nowrap px-2 py-2"
  aria-label="Other elections of this body for this state"
  data-testid="sibling-events-rail"
>
  {#each events as ev (ev.event_id)}
    <a
      href={ev.href}
      aria-current={ev.is_current ? "page" : undefined}
      data-active={ev.is_current}
      class="rounded-full border border-b-2 px-4 py-2 text-sm font-medium transition-colors
             {ev.is_current
               ? 'bg-slate-900 text-white border-slate-900'
               : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100'}"
      style={ev.winner_color ? `border-bottom-color: ${ev.winner_color}` : undefined}
    >
      {ev.year}
    </a>
  {/each}
  {#if compare_href && prior_year !== null}
    <a
      href={compare_href}
      data-testid="sibling-events-compare"
      class="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
    >
      Compare with {prior_year}
    </a>
  {/if}
</nav>
```

**Rules baked into the row**:

- Years come pre-sorted ASC from the view-model: `same_body_events_for_state.sort_by_polled_on().map(toSiblingEvent)`. No client-side year arithmetic.
- Winner color comes from `getPartyColor(winner_party_id, partyRow).hex` per [frontend/src/lib/colors/resolver.ts](frontend/src/lib/colors/resolver.ts) - the same resolver every other surface uses; falls back to a 1px slate-300 bottom when null.
- Current pill scroll-into-view on mount: `onMount(() => currentPill?.scrollIntoView({ inline: "center", block: "nearest" }))` so the citizen's year is always centered first paint (IG-tray ergonomic).
- No-prior edge case (`events.length === 1`): rail renders ONE filled pill for the current year; no Compare tail. Honest absence; no "more elections coming" placeholder.
- Compare CTA text is `Compare with {prior_year}` - NO arrow, NO chevron, NO "->" character ever.
- The OLD compare-CTA in the page header is DELETED in R4 (the rail absorbs the role).

**Doctrine receipt**: this rail replaces the previously-planned "text-only Prev/Next strip with -> arrow on Compare" Jony D2 verdict (retired 2026-06-15 per user pushback). The user's binding direction: "dont want arrows for compare - common jony make the app for 2027 ready, not 1990 ready - we want to make social/political to younger generation". The year-chip rail satisfies the 2026-2027 citizen reference class (Spotify/IG/Linear pill chrome) without arrows, chevrons, or Prev/Next labels.

**PartyComposite spec** (extends `<PartyBar>` to per-party-row table):

```
Columns (left to right):
1. [symbol]       16x16 px; <img src="/party-symbols/{slug}.svg"> fallback "placeholder.svg"
2. [short]        e.g. "BJP" (10ch max)
3. [alliance-chip] e.g. "Mahayuti" - slate-500 outline pill, 11px; absent when no alliance attribution
4. [seats-bar]    horizontal bar; width = seats_won / total_seats; bar fill = party color
5. [seats-count]  e.g. "132"
6. [vote-share%]  e.g. "26.8%"

Mobile <640px: columns 5+6 stack under columns 1-4 on the same row.

Rationale for retiring SeatDonut on this surface: 5-30 party donut is colour-soup without legend numbers; row-table is scannable on mobile and carries every fact the donut would, plus the symbol + alliance the donut cannot.
```

**Constituencies-by-district fold + search**:

```
- Search input sits ABOVE the district list, sticky inside the section scroll-boundary (NOT page-top).
- Fold-state default: ALL districts COLLAPSED on first paint (mobile + desktop).
- Each row: [district name] [N constituencies] [winner-party-mix dot-strip]; tap expands inline.
- Last row of the section chrome: "Compare with Assembly 2019 ->" - slate-700 link, NOT a button.
```

**Files touched**:

| File                                                                                                              | Change |
| ----------------------------------------------------------------------------------------------------------------- | ------ |
| [frontend/src/routes/StateElection.svelte](frontend/src/routes/StateElection.svelte)                              | Re-order subcomponent mounts; mount `<SiblingEventsRail>` between PageHeader and HeroCards; delete `<InlineCounterfactualSwing>` import + mount; delete flat constituency table block; DELETE the old compare link from PageHeader (the rail's tail pill absorbs the role) |
| [frontend/src/lib/elections/SiblingEventsRail.svelte](frontend/src/lib/elections/SiblingEventsRail.svelte)         | NEW (year-chip rail per Jony 2026-06-15 verdict above; ~30 LOC); reuses `ElectionsRouteTabs` pill family |
| `frontend/src/lib/elections/sibling-events-rail-model.ts`                                                          | NEW; pure projection: `(catalogue, state_code, current_event_id, body) -> { events: SiblingEvent[], prior_year: number | null, compare_href: string | null }`; sort ASC by polled_on; winner_color via `getPartyColor` |
| `frontend/src/lib/elections/SiblingEventsRail.test.ts`                                                            | NEW unit; assert pill order ASC, current pill carries `aria-current="page"` + `data-active=true`, winner_color stripe present, no-prior edge renders one pill with no compare tail, 5-event fixture renders 5 pills + 1 compare tail |
| [frontend/src/lib/elections/StateEventHero.svelte](frontend/src/lib/elections/StateEventHero.svelte)             | Extend KPI tile shape with `delta?: { glyph, sign_label, prev_event_label }`; render glyph row when delta present; OMIT row when absent |
| [frontend/src/lib/elections/StateEventPartyComposite.svelte](frontend/src/lib/elections/StateEventPartyComposite.svelte) | Replace SeatDonut+PartyBar with per-party-row table; new columns per spec |
| [frontend/src/lib/elections/StateEventConstituencyList.svelte](frontend/src/lib/elections/StateEventConstituencyList.svelte) | Add fold-state ($state collapsedDistricts = $state(new Set())); sticky search input; integrate compare-CTA as last row |
| [frontend/src/lib/elections/PartyBar.svelte](frontend/src/lib/PartyBar.svelte) (or its existing path)              | Extend interface with `vote_share_pct?: number | null` + `party_symbol_slug?: string | null` + `alliance_short?: string | null` (additive; existing call-sites unchanged) |
| `frontend/src/lib/elections/StateElection.section-order.test.ts`                                                  | NEW static-source contract test (readFileSync + grep pattern from [frontend/src/lib/IndicatorCard.no-cross-family-chrome.test.ts](frontend/src/lib/IndicatorCard.no-cross-family-chrome.test.ts)): "Scatter mount MUST appear before ConstituencyList mount"; "InlineCounterfactualSwing mount must NOT appear"; "flat constituency table HTML must NOT appear"; "each section header carries an `id` attribute matching its eyebrow slug" (J-elevated-8 amend); "PartyComposite mount appears immediately after StateEventMap mount per J-elevated-2 storytelling order" |
| `frontend/src/lib/elections/StateEventConstituencyList.fold-search.test.ts`                                       | NEW unit; assert all-collapsed-on-paint, search filters per-AC by name (case-insensitive), tap-to-expand inline |
| `frontend/src/lib/elections/StateEventHero.test.ts`                                                               | NEW unit; assert delta-row present when delta non-null; assert delta-row OMITTED when delta is null (first-event edge case per J-elevated-3 amend); assert first-event card's computed-height is < non-first-event card by >=20px; assert glyph emerald vs rose; assert J-elevated-16 national-context line renders for turnout when peer-count >=5 and is SILENT for absolute counts (seats / voters / polled) |
| `frontend/src/lib/elections/StateEventMap.svelte` (from R3) - amended                                              | (a) absorb J-elevated-5 amend: long-press 500ms reveals `Expand` chip; tap grows to 100vh via `document.startViewTransition()`; `X` collapses; dense-urban dots upgrade to outlined polygons at 100vh. (b) absorb J-elevated-11 time-compare overlay: `compareYearId` prop pins a baseline event; swing-overlay `<g>` mounts with `<polygon>` triangles per AC centroid; constituency-list reorders by `abs(margin_swing)` desc. (c) absorb J-elevated-13 pinch-zoom: `d3.zoom().scaleExtent([1, 4])`; pinch / wheel / double-tap; `Reset` pill at top-right when scale > 1. |
| `frontend/src/lib/elections/swing-overlay-builder.ts`                                                              | NEW (~60 LOC). Pure helper for J-elevated-11: `({ current_winners, baseline_winners, ac_centroids }) => SwingOverlayRow[]`. Each row carries `ac_no`, `centroid: [x, y]`, `direction: "up" \| "down"`, `magnitude: number`. |
| `frontend/src/lib/elections/swing-overlay-builder.test.ts`                                                         | NEW (~40 LOC). Tier-A unit: synthetic 3-AC fixture; assert direction matches (party-flip = up if margin_b > margin_a); magnitude = abs delta; missing baseline => empty list. |
| `frontend/src/lib/elections/StateEventMap.zoom-overlay-expand.test.ts`                                             | NEW (~80 LOC). Tier-A unit: d3-zoom scaleExtent = [1,4]; long-press timer fires after 500ms then resets on pointerup<500ms; swing-overlay polygon count == baseline_winners.length when compareYearId set; view-transition feature-detect falls back to instant nav. |
| `frontend/src/lib/elections/narrative-generator.ts`                                                                | NEW (~150 LOC) per J-elevated-12. 8 templated string-builders, one per section: HeroCards / SiblingRail (skipped - no narrative) / Map / PartyComposite / Alliance / Races / Scatter / Constituencies / Sankey / AllParties (skipped). Each takes `({ event_summary_row, peer_rows_for_state, peer_rows_for_event_id }) => string \| null`. Silent when confidence < 80%. |
| `frontend/src/lib/elections/narrative-generator.test.ts`                                                           | NEW (~120 LOC). Tier-A unit: per-template fixtures asserting silent-on-missing-data + correct string interpolation + no hallucinated facts; one fixture per template with both a positive and a null case. |
| `frontend/src/lib/elections/national-context.ts`                                                                   | NEW (~40 LOC) per J-elevated-16. `({ metric, value, all_events_for_same_kind_and_year }) => string \| null`. Whitelist of metrics: turnout, voter-share. Silent for absolute counts. Silent when peer-count < 5. |
| `frontend/src/lib/elections/national-context.test.ts`                                                              | NEW (~50 LOC). Tier-A unit: cross-state percentile fixture; assert silent on <5 peer events; assert silent on "seats" metric (absolute count); assert renders correctly for turnout above/below/matches national average. |
| `frontend/src/lib/elections/wow-moment-reliability.test.ts`                                                        | NEW (~60 LOC) per J-elevated-10 amend. Tier-A static-source contract: assert the year-chip rail's tap handler contains BOTH `navigator.vibrate` AND `getBattery` AND `connection?.saveData` AND `@supports (-webkit-touch-callout: none)` AND `startViewTransition` references; assert all are feature-detected (no unguarded calls). Reuses the IndicatorCard readFileSync+grep pattern. |
| [frontend/e2e/state-event-view.spec.ts](frontend/e2e/state-event-view.spec.ts)                                    | Extend: assert hero glyphs render; assert sibling-events strip; assert ConstituencyList collapsed; assert ScatterPlot appears ABOVE ConstituencyList in DOM order; assert anchor link `/maharashtra/elections/assembly-2024#alliance` scrolls the alliance panel into view (J-elevated-8); assert long-press on choropleth reveals Expand chip (J-elevated-5); assert pinch-zoom Reset pill appears when scaled (J-elevated-13); assert narrative line renders under at least one section header on a mature-data event (J-elevated-12); assert national-context line renders under turnout HeroCard (J-elevated-16). |

**Acceptance gates**:

- `bun run test -- StateEventHero StateEventConstituencyList StateElection.section-order` green.
- `bun run check` 0 NEW errors.
- `bun x playwright test e2e/state-event-view.spec.ts` green.
- Browser smoke per [CLAUDE.md section 13](CLAUDE.md): `/maharashtra/elections/assembly-2024` (288 ACs, hero glyphs visible, turnout delta vs 2019 shown, sibling-events strip present, ConstituencyList collapsed-by-default, search input present, flat 288-row table ABSENT); `/maharashtra/elections/general-2024` (parliament event; map placeholder per PR #954 closure; same hero glyphs); `/karnataka/elections/assembly-2023` (state-agnostic smoke); first-event check: a state-event that IS the first on record (e.g. `/jammu-and-kashmir-ut/elections/assembly-2024` if no prior assembly exists - VERIFY: JK U08 has only `assembly-2024`, no earlier) - assert no delta row, no sibling "Prev:" entry, only "Next: (none)".

**Oracle (load-bearing single check)**: the new static-source contract test (`StateElection.section-order.test.ts`) passes. This guarantees the IA verdict in the table above is wired into the template AND will not regress to the old order on a future worktree-staleness merge (the recurring trap from the user-memory PR #1048/#1049 cycle).

**Dependencies**: R3 (consumes extracted subcomponents).

**Reviewers**: Jony + Citizen (UX); Fowler (component shape).

## Section 6 - Row R5: Cross-event Sankey + diverging-bar

**Scope**: Mint NEW [frontend/src/lib/elections/StateEventCrossEventSankey.svelte](frontend/src/lib/elections/StateEventCrossEventSankey.svelte) that wraps the existing [frontend/src/lib/SwingSankey.svelte](frontend/src/lib/SwingSankey.svelte). Mount in StateElection at section 11 (per R4's section table). Sankey is COLLAPSED by default behind a "Show vote-flow" pill button; an always-on diverging-bar above it shows net seat-delta per top-6 parties + Others (structurally honest baseline). When no prior same-body event exists, render the section title + a no-prior copy line (NOT a disabled button).

**Files touched**:

| File                                                                                                                          | Change |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| [frontend/src/lib/elections/StateEventCrossEventSankey.svelte](frontend/src/lib/elections/StateEventCrossEventSankey.svelte)  | NEW. Loads winners for current + previous-same-body event; derives `{ party_id, seats_current, seats_prev, delta }` per top-6 by `max(seats_current, seats_prev)`; bucketed Others. Renders DivergingBar always-on; Sankey collapsed behind pill button. Wraps SwingSankey. |
| `frontend/src/lib/elections/cross-event-sankey-model.ts`                                                                      | NEW. Pure derivation; takes two `ElectionResultRow[]` arrays; returns `{ top6_with_others: PartyDelta[], sankey_actuals: PartyBag, sankey_scenario: PartyBag }`. |
| `frontend/src/lib/elections/cross-event-sankey-model.test.ts`                                                                 | NEW unit; synthetic 2-event fixture; assert top-6 selection, Others bucketing, delta arithmetic, no-prior returns empty state correctly. |
| [frontend/src/routes/StateElection.svelte](frontend/src/routes/StateElection.svelte)                                          | Mount `<StateEventCrossEventSankey>` at section 11 position; pass `current_winners`, `prev_winners`, `body`, `state_name`. |
| [frontend/e2e/state-event-view.spec.ts](frontend/e2e/state-event-view.spec.ts)                                                | +1 case: visit `/maharashtra/elections/assembly-2024`; assert section header "Vote-flow comparison" appears, assert diverging-bar svg present, click "Show vote-flow" pill -> assert SwingSankey svg mounts. Visit a first-event-on-record (e.g. J&K assembly-2024); assert section header reads "Vote-flow comparison needs a prior election" with no button. |

**Diverging bar spec** (the always-on baseline):

```
Horizontal bar per party, top-6 by max(seats_current, seats_prev) + bucketed "Others".
Bar value = seats_current - seats_prev (signed integer).
Positive bars extend right (emerald-600); negative extend left (rose-600).
Row layout: [party_color_dot] [party_short] [bar from 0] [delta value e.g. "+18" / "-12"]
Caption (always visible, italic slate-600):
  "Net seat change vs the previous {body} event ({prev_event_label})."
```

**Sankey gating** (the opt-in chrome):

```
Section header: "Vote-flow comparison ({prev_year} -> {current_year})"
Below header: "Show vote-flow" outline-pill button.
Tap: button collapses into the Sankey rendering (SwingSankey).
Caption (always visible below the SANKEY when expanded):
  "Approximate flow: each party's net seat loss is redistributed to gainers in
   proportion to each gainer's net seat gain. We do not track constituency-level
   flips; this is a state-total estimate, not a voter-panel."
```

**No-prior case** (this is the first same-body event for the state):

```
Section header: "Vote-flow comparison"
Body copy: "Needs a prior election; this is the first {body} event on record for {state_name}."
NO button, NO empty Sankey, NO em-dash placeholder.
```

**Acceptance gates**:

- `bun run test -- cross-event-sankey-model StateEventCrossEventSankey` green.
- `bun x playwright test e2e/state-event-view.spec.ts -g "vote-flow"` green.
- Browser smoke per [CLAUDE.md section 13](CLAUDE.md): `/maharashtra/elections/assembly-2024` (diverging-bar visible by default, "Show vote-flow" pill present, expand works); `/maharashtra/elections/assembly-2019` (same shape, different prev event); `/jammu-and-kashmir-ut/elections/assembly-2024` (no-prior copy, no button); zero `[error]` console events.

**Oracle (load-bearing single check)**: the cross-event-sankey-model unit test passes - it proves top-6 selection, Others bucketing, signed-delta arithmetic, and the no-prior empty-state contract. If THAT passes, the visual is wired off a correct projection.

**Dependencies**: R3 (consumes the extracted Scatter + Sankey region structure).

**Reviewers**: Max (data-shape - approximate-flow caption honesty); Jony (gating + no-prior copy); Fowler (model shape + test coverage).

## Section 7 - Row R6: Alliance honesty + first-event-no-prior gating

**Scope**: Add `formation` column to `datasets/data/entities/party_alliances.csv` schema (additive minor bump). Update existing alliance rows to declare `formation = pre_poll` (the default; curator may relabel selected post-poll arrangements in follow-up curator PRs). Update `<AllianceTotals>` to render ONLY when `(event_id, state)` has at least one alliance row (suppress the existing amber "pending" pill). Add the Max-authored honesty caption above the panel. Wire the first-event-no-prior gating into R4's HeroCards delta AND R5's Sankey button (one shared `noPriorSameBody` boolean derived in StateElection.svelte; passed down).

**Files touched**:

| File                                                                                                                | Change |
| ------------------------------------------------------------------------------------------------------------------- | ------ |
| [datasets/data/_schema/columns.json](datasets/data/_schema/columns.json)                                            | Add `formation` to the `party_alliances.csv` column block (additive minor bump); bump `$schema_version` per the schema-versioning policy in [CLAUDE.md section 11](CLAUDE.md). |
| [datasets/data/_schema/columns.schema.json](datasets/data/_schema/columns.schema.json)                              | Bump `x-version` minor; add `x-changelog` entry "Add party_alliances.csv formation column (pre_poll/post_poll/hybrid; nullable; default pre_poll)". |
| [datasets/data/entities/party_alliances.csv](datasets/data/entities/party_alliances.csv)                            | Add `formation` column; backfill all existing rows to `pre_poll` (the default per Max verdict). |
| [frontend/src/lib/elections/AllianceTotals.svelte](frontend/src/lib/elections/AllianceTotals.svelte)                | Render guard: ONLY mount if `alliances.length > 0`; delete the "pending" amber pill. Add honesty caption above the panel: `"Pre-poll alliance composition as reported by {source.title}. Post-election government formation may differ. Uncategorised parties shown under 'Others'."` Caption colour slate-600; placement immediately under section header. |
| [frontend/src/lib/elections/StateEventHero.svelte](frontend/src/lib/elections/StateEventHero.svelte) (from R4)      | Accept `noPriorSameBody: boolean` prop; gate delta-row rendering on `!noPriorSameBody`. |
| [frontend/src/lib/elections/StateEventCrossEventSankey.svelte](frontend/src/lib/elections/StateEventCrossEventSankey.svelte) (from R5) | Accept `noPriorSameBody: boolean` prop; gate the "Show vote-flow" button rendering on `!noPriorSameBody`; render the no-prior copy when true. |
| [frontend/src/routes/StateElection.svelte](frontend/src/routes/StateElection.svelte)                                | Derive `noPriorSameBody = $derived(previous_same_body === null)`; pass down to Hero and Sankey. |
| `backend/tests/test_party_alliances_formation_column.py`                                                            | NEW. Read `party_alliances.csv`; assert `formation` column present, all values in enum, no nulls (per default backfill). |
| `frontend/src/lib/elections/AllianceTotals.no-pending-pill.test.ts`                                                 | NEW static-source contract: assert AllianceTotals.svelte template does NOT contain the strings "Alliance data pending" / "pending" / amber-pill chrome. |
| `frontend/src/lib/elections/AllianceTotals.test.ts` (or NEW)                                                        | Unit: empty `alliances` prop -> component renders nothing (or `null`); non-empty -> caption + bars render. |
| [docs/architecture/data/canonical-store.md](docs/architecture/data/canonical-store.md)                              | Document the new `formation` column + the values + the citizen-honesty motivation; cross-link to [docs/concepts/owid-alignment.md](docs/concepts/owid-alignment.md). |

**Acceptance gates**:

- `cd backend && pytest -q -k party_alliances_formation` green.
- `bun run test -- AllianceTotals` green.
- `python -m yen_gov validate --root .` exit 0 (schema-version + FK closure clean).
- `bun run check` 0 NEW errors.
- Browser smoke per [CLAUDE.md section 13](CLAUDE.md): `/maharashtra/elections/assembly-2024` (alliance panel renders with caption + Mahayuti / MVA / Others bars - data already curated per the recent alliance-backfill PRs; assert caption text present); `/karnataka/elections/assembly-2023` (alliance panel renders with INC/JDS/BJP per the curated KA data); `/some-uncurated-event/` (NO alliance panel mounts, no "pending" pill); first-event smoke: `/jammu-and-kashmir-ut/elections/assembly-2024` (HeroCards omit delta row, Sankey shows no-prior copy with no button).

**Oracle (load-bearing single check)**: `AllianceTotals.no-pending-pill.test.ts` passes - this freezes the doctrine that uncurated events render silence, not a debt-tracking pill.

**Dependencies**: R4 (Hero accepts the new prop) + R5 (Sankey accepts the new prop).

**Reviewers**: Max + Hans (data shape + formation column semantics); Jony + Citizen (caption copy); Fowler (schema bump discipline).

## Section 7.5 - Row R7: Build-time share-card PNG generation (J-elevated-14)

**Scope**: Generate a 1200x630 PNG per (state, event_id) at `bun run build` time. Each PNG: state choropleth in winner-colours + headline `{winning_alliance|party} {seats} of {total}` + subtitle `{state} {body} {year}` + yen-gov wordmark. Wire `<svelte:head>` og:* + twitter:card meta on `StateElection.svelte` so WhatsApp / Twitter / LinkedIn / Signal show the card on share. Structurally orthogonal to R1-R6 - this is a build-step row, not a frontend chrome row.

**Files touched**:

| File                                                                                                                | Change |
| ------------------------------------------------------------------------------------------------------------------- | ------ |
| `frontend/scripts/build-share-cards.ts`                                                                              | NEW (~120 LOC). Reads `datasets/data/marts/elections/event_summary.csv`; builds an SVG per row using `d3-geo` + the same projection helpers `StateAcMapD3` uses; converts SVG -> PNG via `@resvg/resvg-js`; writes to `frontend/public/share/<state>/<event_id>.png`. Idempotent: re-runs overwrite, never append. Parallelised across CPU cores via `os.cpus().length`. |
| [frontend/package.json](frontend/package.json)                                                                       | +1 devDep `"@resvg/resvg-js": "^2.x"`; update `"build"` script: `"vite build && bun scripts/build-share-cards.ts"`. |
| [frontend/bun.lock](frontend/bun.lock)                                                                               | Regenerate in the same commit (Holy Law #9 DoD). |
| [frontend/src/routes/StateElection.svelte](frontend/src/routes/StateElection.svelte)                                 | +12 LOC in `<svelte:head>`: `<meta property="og:image" content="/yen-gov/share/{state_slug}/{event_id}.png">` + `og:title` + `og:description` + `twitter:card content="summary_large_image"` + `twitter:image` + `og:url`. |
| `frontend/scripts/build-share-cards.test.ts`                                                                         | NEW (~80 LOC). Tier-A unit: read 3 fixture event_summary rows; assert 3 PNGs written to a tmpdir; assert PNG dimensions = 1200x630 via `@resvg/resvg-js`'s metadata; assert file size in band [20KB, 80KB]; assert idempotent (re-run -> 0 file content changes via byte-compare). |
| `frontend/public/share/.gitignore`                                                                                   | NEW. Single line `*.png` to ignore generated artefacts (regenerated at every build; not source). |
| [docs/architecture/frontend/og-share-cards.md](docs/architecture/frontend/og-share-cards.md)                         | NEW. Doc the build-step: data source + image spec + WhatsApp / Twitter / LinkedIn / Signal unfurl behaviour + `@resvg/resvg-js` choice (pure-WASM justified per Holy Law #8 vs sharp + libvips). Cross-link to J-elevated-14. |

**devDep justification (Holy Law #8 "open source first")**: `@resvg/resvg-js` is the pure-WASM port of Mozilla's `resvg` Rust crate. ~2MB on disk, zero native binary deps; vs `sharp` which is ~28MB on disk and needs `libvips` per-platform binaries (every CI host needs the right libvips version pre-installed). `@vercel/og` is functionally equivalent but bundles Satori (a TSX-to-SVG renderer) which we do not need - we write SVG directly. `@resvg/resvg-js` is the minimal dependency.

**Build-time cost**: ~30s on a 12-core CI runner (~250ms per PNG, parallelisable). One-time per `bun run build`. Output ~6MB across ~120 events; CDN-cached; zero runtime cost.

**Acceptance gates**:

- `bun run test -- build-share-cards` green.
- `bun run build` exits 0 AND produces `frontend/public/share/<state>/<event_id>.png` for every row in `datasets/data/marts/elections/event_summary.csv`.
- Per-PNG inspection: open `frontend/public/share/maharashtra/assembly-2024.png` - asserts winner colour visible, headline reads `Mahayuti 230 of 288` (or equivalent), wordmark present.
- Live unfurl smoke (manual, manual-only because GitHub Pages production URL is the only one unfurl-services index): paste `https://miztiik.github.io/yen-gov/maharashtra/elections/assembly-2024` into a WhatsApp message draft (do NOT send); unfurl preview shows the generated PNG. Repeat for 1 Twitter + 1 LinkedIn share-draft as cross-platform sanity.

**Oracle (load-bearing single check)**: `bun run build` exits 0 AND `(Get-ChildItem frontend/public/share -Recurse -Filter *.png | Measure-Object).Count -ge (Import-Csv datasets/data/marts/elections/event_summary.csv | Measure-Object).Count`. If counts match, every event has its share-card.

**Dependencies**: R1.5 (`event_summary.csv` must have J&K U08 row) + R4 (page is laid out; head-meta references the right state slug + event_id grammar).

**Reviewers**: Fowler (devDep justification + build-step idempotence + script-test discipline); Jony + Citizen (image visual sign-off on 3 sample states - MH AE 2024 + KA AE 2023 + a no-prior event like JK AE 2024 to confirm copy degrades gracefully when alliance is unknown).

## Section 8 - EXECUTION BLOCK (paste verbatim into every plan-doc)

```markdown
## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on.
2. **One row = one PR = one branch.** Park master on a `scratch-master-parking` branch so no worktree owns `main` (clean gh-merge). Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change.
3. **Ship loop, non-stop.** Keep PRs in flight; never idle. As soon as one row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next row. Pre-existing unrelated test failures are not gating - document the baseline, do not block.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked.
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (CLAUDE.md section 0a) in debate, not parallel review; bake the single written verdict into the row and proceed.
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into subagents so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (Level-5), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3 (the loop is lossy - escalate with Path A/B/C options, do not ship a 4th audit). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt (the command + its zero result). Archive the plan-doc with a per-row distillation map per `docs/how-to/distill-a-plan.md`.
```

## Section 9 - Persona debate transcript (compressed, 2026-06-15)

Three personas dispatched in DEBATE (not parallel-review) per the prepare-plan skill. Full verbatim verdicts retained in the conversation that authored this plan; below is the compressed converged ruling baked into rows R1-R6.

**Jony (UI/UX) + Citizen** ruled the IA, hero card spec, prev/next pattern, PartyComposite shape, ConstituenciesByDistrict fold/search, Sankey gating + caption, and the landing route (questions J1-J8 in the brief):

- Final section order = 11 sections (1 deleted: `<InlineCounterfactualSwing>`; 1 merged: SeatDonut into PartyComposite; 1 added: Sankey at position 11). Old position 3 (Races) moves to 8; old position 10 (Scatter) moves to 9; old end (Constituencies-by-district) moves to 10.
- HeroCards: 4 cards (Seats / Voters / Polled / Turnout). Only Voters / Polled / Turnout carry delta. First-event-on-record OMITS the delta row (silent absence).
- Prev/next = text-only sibling-events strip ("Prev: Assembly 2019 - BJP led | Next: (none) | Compare 2019 vs 2024 ->"). No chevrons, no arrows.
- PartyComposite = extend PartyBar to per-party-row table; RETIRE SeatDonut on this surface.
- ConstituenciesByDistrict = sticky search; all collapsed first paint; Compare CTA = last-row slate-700 link.
- Sankey = pill button "Show vote-flow"; collapsed by default; always-on diverging-bar above.
- Landing route = full standalone, breadcrumb + page header + latest-by-body hero + 2 parallel tables + cross-link to `/<state>`.

**Max (Indicator Scout)** ruled alliance honesty, Sankey caption, hero turnout-delta sourcing, and the writer rip (questions M1-M4 in the brief):

- Alliance panel renders ONLY when `party_alliances.csv` has rows for `(event_id, state)`. Delete the amber "pending" pill. Add `formation` column (additive minor). Mandatory caption above panel.
- Sankey: ship both diverging-bar (default) + Sankey (collapsed). Caption: "Approximate flow: each party's net seat loss is redistributed to gainers in proportion to each gainer's net seat gain. We do not track constituency-level flips; this is a state-total estimate."
- Hero turnout-delta: if E2 from sibling plan has shipped, use `event_summary.csv`; else use per-event `summary.csv`. First-event = null.
- MH 266->288: `eci_form10_ae.py` ALREADY EXISTS with 13 state-events. Fix is one `EciEventSpec` row + delete `thecont1_mh_ae2024.py` in same PR. source.csv attribution already correct. No new adapter; no schema change.

**Fowler (Engineering)** ruled the PR row split, writer-rip shape, test-tier matrix, section-reorder safety, and R1 acceptance gates (questions F1-F5 in the brief):

- 6 PR-rows (parallel front {R1, R2, R3}; then R4 -> R5 -> R6 sequential).
- Writer rip = pick (a) "add MH to existing eci_form10_ae.py + delete thecont1" per Max's correction.
- Section reorder safety = pick (c) component extraction first (R3) then rearrange at route level (R4). NOT in-place (Beck two-hat violation); NOT V2 route (strangler-fig banned by user).
- Test tier per row = unit + contract + integration + e2e per [docs/architecture/testing.md](docs/architecture/testing.md); static-source contract tests for "must appear" / "must NOT appear" per the IndicatorCard pattern (user-memory lessons-2026-06-12).
- R1 oracles = 8 gates; load-bearing oracle is AC range 1..288 with zero gaps.

The three personas had ZERO unresolved disagreements; Fowler's initial assumption of a new adapter was corrected by Max's verification that `eci_form10_ae.py` already exists. That correction is now binding in R1.

### Review round 2 - 2026-06-15 (5-persona review of R1.5 wording + Bihar 2005 deferral)

Dispatched in DEBATE per user instruction ("the plan looks half-baked"). Three parallel research subagents seeded the ground truth (state-identity bridge inventory; catalogue-vs-disk completeness across all 36 polities; Bihar 2005 collision schema); five personas (Fowler, Hans, Max, Gregor, Jony) returned written verdicts. Convergence applied in this revision:

**Gregor (Architect) - structural correction**: the R1.5 fix as previously framed ("add aliases to `_build_slug_to_eci_via_catalogue`") would have patched the U08 symptom while preserving a Canonical Data Model violation. The writer parses display strings to recover `state_code` even though the catalogue's outer dict key IS the `eci_code`. The correct fix is to DELETE the bridge entirely and iterate `catalogue["states"].items()` directly, deriving each state's disk slug via the EXISTING canonical helper `eci_to_lgd_slug()` at `backend/yen_gov/canonical/adapters/eci/state_slug.py` (already used by `party_pages.py`). Section 2.5 rewritten end-to-end to reflect this framing.

**Max (Indicator Scout) - factual correction + scope discipline**: the prior framing assumed `election-events.schema.json` carries a binary `kind ∈ {assembly, parliament}` enum. Schema v1.3 in fact already supports `kind ∈ {assembly, parliament, general_bye, assembly_bye, by_election}` and the `assembly-bye-<YYYY>-<seat-slug>` event_id grammar (precedent on disk: `state=karnataka/election=2024-channapatna-bye/`). The 567-event gap is POPULATION debt, not SCHEMA debt - no schema bump in the spawned coverage-extension plan-doc. Priority for spawned doc: d > b > a > c (latest-decade contemporary by-elections first; historical bye-elections last). Section 0.3 audit corrected accordingly. The `display_norm.py` normaliser Max proposed for R1.5 is also unnecessary once the Gregor framing applies (the writer no longer parses display strings).

**Hans (Governance) - citizen-honesty escalation**: deferring Bihar 2005 as "Hans + Max territory" without a named follow-up is a silent demotion of canonical doctrine (`docs/architecture/backend/sources-eci.md` names Bihar 2005 as the anchor). November 2005 (Nitish Kumar government formation, ending ~15 years of Lalu/Rabri rule) is INVISIBLE in citizen data today; that is a Generalisation + Blame double violation per Rosling. Promoted to **Row R1.6** with full spec (Section 2.6); not silently deferred. Hans's broader citizen-honesty footer requirement for catalogue-empty surfaces moves into the spawned [TODO/20260615-elections-catalogue-completeness-handover.md](TODO/20260615-elections-catalogue-completeness-handover.md) (Jony agreed: ship doctrine first, copy second).

**Jony (UI/UX) - smoke-list expansion**: R1.5's old oracle 6 ("navigate the J&K card") was undercover - a writer-rip touching every state should verify EVERY state-class did not regress. Replaced with a 10-route enumerated smoke checklist that exercises the live class (NCT Delhi, Puducherry, TN) + the no-legislature class (A&N, DNHDD, Lakshadweep) + the known-broken class (Bihar S04, still expected broken under R1.5 alone) + the per-event-page seam (`/jammu-and-kashmir/elections/assembly-2024`). `read_page` sufficient; no `screenshot_page` (pure text-content fix). Non-goal explicit: card copy doctrine is preserved verbatim. Jony also pre-decided the Bihar 2005 URL grammar for R1.6: `assembly-2005-feb` / `assembly-2005-nov` (path encodes identity per ADR-0052; query-param variants forbidden).

**Fowler (Engineering) - splitting consideration RESOLVED in favour of Gregor**: Fowler's instinct was to split R1.5 into R1.5a (tactical fix) + R1.5b (extract shared `state_identity.py` module). Resolution: Gregor's framing dissolves the splitting question - the writer no longer needs a shared identity module because it stops doing identity work at the wrong layer. Rule of Three is not yet met (only one site has the `eci_code -> slug` direction; the other three bridges do `publisher_name -> slug`, a different job that legitimately needs aliases). R1.5 stays Level-2; no new module; the existing `eci_to_lgd_slug()` is the canonical seam. Fowler's contract-test discipline ("static-source test asserting the deleted helper does not return") folds into R1.5's writer test.

All five personas converged on: (a) Gregor's structural framing for R1.5, (b) promoting Bihar 2005 to R1.6 in this plan-doc, (c) spawning [TODO/20260615-elections-catalogue-completeness-handover.md](TODO/20260615-elections-catalogue-completeness-handover.md) for the 567-gap, (d) replacing R1.5 oracle 6 with Jony's 10-route smoke. ZERO unresolved disagreements after the round.

## Section 10 - References

- [CLAUDE.md](CLAUDE.md) - section 0a (authority table), section 6 (correction levels), section 9 (DoD), section 10 (anti-patterns including STOP-AND-SURFACE + no-mocks + rip-and-replace), section 11 (schema versioning), section 13 (UI verification).
- [docs/agents/bootstrap.md](docs/agents/bootstrap.md) - 8-step ritual.
- [docs/agents/guardrails.md](docs/agents/guardrails.md) - Holy Laws restated.
- [docs/concepts/citizen-first.md](docs/concepts/citizen-first.md) - distill doctrine.
- [docs/concepts/schema-is-the-design-system.md](docs/concepts/schema-is-the-design-system.md) - one-card-per-measure rule.
- [docs/concepts/data-spine.md](docs/concepts/data-spine.md) - 5 non-negotiables.
- [docs/concepts/owid-alignment.md](docs/concepts/owid-alignment.md) - named divergences.
- [docs/concepts/data-provenance.md](docs/concepts/data-provenance.md) - source.csv citation ledger.
- [docs/architecture/frontend/charts/election-views.md](docs/architecture/frontend/charts/election-views.md) - ADR-0048 sankey doctrine.
- [docs/architecture/frontend/psephlab.md](docs/architecture/frontend/psephlab.md) - SwingSankey approximate-flow precedent.
- [docs/architecture/backend/validator.md](docs/architecture/backend/validator.md) - Tier-A/B/C validation.
- [docs/architecture/testing.md](docs/architecture/testing.md) - 4-tier test matrix.
- [docs/architecture/data/canonical-store.md](docs/architecture/data/canonical-store.md) - long-format CSV doctrine.
- [docs/how-to/ship-a-pr.md](docs/how-to/ship-a-pr.md) - 2-commit-then-squash + 5-gate DoD + post-merge cleanup.
- [docs/how-to/distill-a-plan.md](docs/how-to/distill-a-plan.md) - plan-doc archive ritual.
- [docs/how-to/handle-scope-change.md](docs/how-to/handle-scope-change.md) - STOP-AND-SURFACE.
- [TODO/20260615-elections-redesign-plan.md](TODO/20260615-elections-redesign-plan.md) - sibling plan for `/t/elections` parent routes; R4 sourcing rule defers to E2.
- [TODO/20260612-election-event-page-ux-polish-plan.md](TODO/20260612-election-event-page-ux-polish-plan.md) - PR #954 closure; predecessor polish work.
- [TODO/20260612-alliance-phase-1-structural-fix-plan.md](TODO/20260612-alliance-phase-1-structural-fix-plan.md) - alliance schema v2.0 history.
- [backend/yen_gov/canonical/adapters/eci_form10_ae.py](backend/yen_gov/canonical/adapters/eci_form10_ae.py) - the adapter R1 extends.
- [backend/yen_gov/canonical/adapters/thecont1_mh_ae2024.py](backend/yen_gov/canonical/adapters/thecont1_mh_ae2024.py) - the adapter R1 deletes.
- [frontend/src/routes/StateElection.svelte](frontend/src/routes/StateElection.svelte) - the route R3 extracts + R4 reorders.
- [frontend/src/lib/SwingSankey.svelte](frontend/src/lib/SwingSankey.svelte) - the primitive R5 wraps.
- [frontend/src/lib/IndicatorCard.no-cross-family-chrome.test.ts](frontend/src/lib/IndicatorCard.no-cross-family-chrome.test.ts) - the static-source contract test pattern R4 + R6 reuse.
- [frontend/src/app-tokens.css](frontend/src/app-tokens.css) - motion + colour token vocabulary (`--dur-fast` / `--dur` / `--dur-slow` / `--ease-out` / `--ease-spring` / `--e1` / `--e2`) referenced throughout Section 0.5.
- [frontend/src/routes/StateOverview.svelte](frontend/src/routes/StateOverview.svelte) - `buildKpiTiles()` + skeleton patterns reused by HeroCards (J-elevated-3) + first-event card-collapse pin.
- [frontend/src/lib/elections/ElectionsRouteTabs.svelte](frontend/src/lib/elections/ElectionsRouteTabs.svelte) - pill family reused by SiblingEventsRail (J-elevated-4).
- [frontend/src/lib/IndicatorJump.svelte](frontend/src/lib/IndicatorJump.svelte) - non-navigation-state precedent reused by J-elevated-11 (time-compare overlay).
- [frontend/src/lib/colors/resolver.ts](frontend/src/lib/colors/resolver.ts) - party-color contract used by year-chip winner-underlines AND share-card winner colours (R7).
- View Transitions API - `https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API` - used for J-elevated-10 wow moment + J-elevated-5 choropleth deep-zoom.
- d3-zoom - `https://d3js.org/d3-zoom` - already in dep tree; used for J-elevated-13 pinch + double-tap zoom.
- Vibration API - `https://developer.mozilla.org/en-US/docs/Web/API/Vibration_API` - feature-detected at J-elevated-10 (wow haptic) and J-elevated-11 (long-press confirmation).
- Battery Status API - `https://developer.mozilla.org/en-US/docs/Web/API/Battery_Status_API` - feature-detected at J-elevated-10 reliability spend (battery-saver branch).
- Network Information API (`navigator.connection.saveData`) - `https://developer.mozilla.org/en-US/docs/Web/API/NetworkInformation` - feature-detected at J-elevated-10 reliability spend (save-data branch).
- @resvg/resvg-js - pure-WASM SVG-to-PNG renderer; chosen for R7 share-card build step per Holy Law #8 (open source first, minimal dep).
- @vercel/og + Satori - rejected as an alternative for R7 because they bundle a TSX-to-SVG renderer we do not need.

## Ledger

| Date       | Row | Notes |
| ---------- | --- | ----- |
| 2026-06-15 | plan | Authored by orchestrator (prepare-plan skill). Personas (Jony / Max / Fowler) dispatched in parallel DEBATE; verdicts converged. XLSX probed via openpyxl: 288 distinct ACs, range 1..288, zero missing. MH baseline captured: summary.csv = 266 data rows, candidacies.csv = 3825 data rows. `eci_form10_ae.py` verified to already support 13 state-events; MH 2024 absent. `thecont1_mh_ae2024.py` confirmed as the current writer for MH 2024 (reads thecont1 mirror, not ECI XLSX). J&K event count (10) verified consistent between election_events.json and StateOverview.svelte rendering - no row added; STOP-AND-SURFACE if user re-confirms with concrete repro. |
| 2026-06-15 | revision | User pushback (1): the AssemblyElections route at `/t/elections/assemblies` shows J&K card as "No election in the catalogue yet" despite assembly-2024 being in catalogue + on-disk. Runtime audit found the mart at `datasets/data/marts/elections/event_summary.csv` (312 rows) and 2 coverage gaps: U08 J&K (1 cat, 0 mart - slug/display bridge bug; this plan) + S04 Bihar (12 cat, 11 mart - duplicate `assembly-2005` event_id collapses under composite PK; Hans/Max territory; out of scope). Added Row R1.5 (Section 2.5) for the bridge fix. User pushback (2): "no arrows for compare - 2027 ready not 1990 ready". Re-convened Jony; verdict: YEAR-CHIP RAIL (Spotify/IG/Linear pill rail) replaces the text-only Prev/Next strip; zero arrows, zero chevrons, zero Prev/Next labels; winner-color underline per chip; horizontal-scroll on mobile; current pill scroll-into-view on mount; reuses ElectionsRouteTabs.svelte pill family. Updated Section 0.1 verdict + Section 5 R4 spec. User pushback (3): RATIFIED the hero turnout-delta sourcing rule (use event_summary.csv if shipped, fallback to per-event summary.csv). Section 0.1 + R4 spec updated to mark as RATIFIED. Status Reckoner now has 7 rows (R1, R1.5, R2, R3, R4, R5, R6); parallel front is `{R1, R1.5, R2, R3}`. |
| 2026-06-15 | revision | User pushback (4): "jony the entire page should be ready for 2027 - futuristic look feel responsiveness intuitiveness not just compare, this is your chance to shine and delight citizens of the world, rise up to the challenge". Re-dispatched Jony for self-review of Section 0.5 (the prior J-elevated-1..10 list); the prior verdict was correct chrome-craft but the user named that as insufficient for a 2027 commitment. Verdict (full transcript embedded in Section 0.5 prose, distilled here): 5 of 10 AMENDED - J-elevated-3 first-event card-collapse pin (~20px collapse, slot omitted not zeroed); J-elevated-4 single-event rail behaviour pin (1-chip centered, no Compare, no sticky); J-elevated-5 absorb Item M per-section deep-zoom (long-press -> 100vh via View Transitions + dot-to-polygon upgrade); J-elevated-8 absorb Item K section anchor links (per-section `id` + `#`-icon-on-hover + `history.replaceState`); J-elevated-10 absorb Item I haptic + reject Item J sound + 50-LOC RELIABILITY re-spend across battery-save / save-data / Safari spring / Firefox / dev-debug. 6 NEW added - J-elevated-11 time-compare overlay on choropleth (long-press / shift-click pins baseline; swing-overlay polygons; URL unchanged); J-elevated-12 one auto-narrated insight per section (`narrative-generator.ts` with 8 templates, silent at <80% confidence); J-elevated-13 pinch + double-tap zoom on choropleth (d3-zoom 1x-4x, already in deps); J-elevated-14 per-event share-card PNG at build time (NEW R7; `@resvg/resvg-js` devDep); J-elevated-15 recent-event memory on landing (localStorage 30-day; `Last viewed` badge); J-elevated-16 national-context micro-copy on HeroCards (turnout + voter-share only; silent for absolute counts). 2 routed to SIBLING PLANS (site-wide command palette + site-wide dark mode; both site-scoped not page-scoped). 13 REJECTED with one-sentence reasons (read-progress bar; sound on wow; AI voiceover; twitter sentiment; AR view; gamification; emoji reactions; auto-playing video; accounts; push notifications; swipe-between-events; pull-to-refresh; velocity-aware tooltips). Status Reckoner gains R7 (build-step share-card PNGs); reordering: parallel front is now `{R1, R1.5, R2, R3}` then `R1.6 -> R4 -> {R5, R6, R7}` with R5/R6/R7 concurrent after R4 ships. Net plan-doc growth: ~250 lines. The wow moment's reliability spend (battery / save-data / Safari spring / Firefox / dev-debug) makes the 2027 commitment honest across the long tail of Redmi-Note + patchy-4G devices, not a developer-laptop fantasy. New Section 7.5 mints R7 with full file-touched table + acceptance gates + devDep justification + load-bearing oracle. |
| 2026-06-15 | review-round-2 | User: "the plan looks half-baked - convene the custom agents and review the plan and make amendments; runSubagent for research with tool access, main thread for orchestration". Orchestrator dispatched 3 parallel fact-finding subagents (state-identity bridge inventory; catalogue-vs-disk completeness audit; Bihar 2005 collision schema) then 5 parallel persona verdicts (Fowler, Hans, Max, Gregor, Jony). All five converged with ZERO unresolved disagreements. Amendments applied: (a) Section 2.5 R1.5 spec rewritten per Gregor's structural correction (DELETE the display-string-parsing bridge; iterate the catalogue's outer-dict key; use existing `eci_to_lgd_slug()` helper from `state_slug.py`); (b) Section 0.3 audit numbers corrected (J&K cat_asm=1 vs disk=22 gap=21, NOT the prior "10 catalogue events" misread; Bihar cat_asm=12 vs disk=41 gap=29; 567-event wider gap spans 31 of 36 polities with top-10 named); (c) Max's factual correction propagated: catalogue schema v1.3 ALREADY supports `kind ∈ {assembly, parliament, general_bye, assembly_bye, by_election}` and the `assembly-bye-<YYYY>-<seat-slug>` event_id grammar - the 567-gap is POPULATION debt not SCHEMA debt; (d) Hans's escalation honored: Bihar 2005 catalogue identity bug PROMOTED to Row R1.6 (Section 2.6 full spec, catalogue schema minor bump 1.3 -> 1.4 to extend event_id grammar with `<kind>-<YYYY>-<month-slug>`, fan out `state=bihar/election=2005/` into Feb + Nov dirs); Status Reckoner now carries 8 rows (R1, R1.5, R1.6, R2, R3, R4, R5, R6); (e) Jony's 10-route smoke list replaces the old single-route oracle 6 (live / no-legislature / known-broken / per-event-page classes all covered); (f) spawned sibling plan-doc [TODO/20260615-elections-catalogue-completeness-handover.md](TODO/20260615-elections-catalogue-completeness-handover.md) per Max's bullet outline + Hans's citizen-honesty footer requirement, owned by Hans + Max + Citizen per CLAUDE.md §0a. Section 9 persona transcript appended with the round-2 converged verdicts. Hard-dependencies updated: R1.6 depends on R1.5 (parallel front stays `{R1, R1.5, R2, R3}`; R1.6 ships after R1.5 lands, optionally parallel with R4). |
| 2026-06-15 | execution-cycle | Execution cycle dispatched per Section 8 EXECUTION BLOCK. Status sync: R1 (#1061), R1.5 (#1065), R2 (#1066) + gap-close R2.1 (#1072), R3 (#1067 + #1068), R4 (#1071) all MERGED to origin/main. R1.6 BLOCKED at executor STOP-AND-SURFACE (forensic evidence in Section 2.6.1): on-disk state=bihar/election=2005/ cannot be deterministically partitioned (5326 candidacy rows ~1.97x expected, 2092 ACs with stacked position-1 winners, 28 negative-margin + 84 winner==runnerup summary rows, all entity_ids 1976-delim contradicting plan-doc heuristic). 3-persona escalation panel (Hans + Max + Gregor) convened in parallel; converged on Path A' (Gregor's strangler-fig + Max's writer-entry assertion + Hans's doctrinal truth via catalogue split). R1.6 effort revised M -> L (one PR, ~150-200 LOC backend + Bihar-only re-emit + mart regen). Stale-branch discovery: R5 work-in-progress at eat/r5-cross-event-sankey worktree (3 new files + 1 modified, pre-R4 base, no PR) and R7 stub branch eat/r7-share-cards (0 commits beyond R2.1 main) discovered during execution-cycle audit; both queued for finalize-dispatch after R1.6 closes. Worktree hygiene: duplicate yen-gov-r4-reorder removed (R4 was already done in parallel by another agent at eat/r4-state-event-page-ia worktree); 2-landing re-detached so no worktree owns main. This ledger row + Section 2.6.1 + Status Reckoner sync compose this docs-PR. |