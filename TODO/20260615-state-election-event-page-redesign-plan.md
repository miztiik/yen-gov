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
3. **The mart writer is missing the U08 row** for assembly-2024 despite all the input data being present. Suspected root cause: slug-drift between the on-disk directory naming (`state=jammu-and-kashmir/`) and the writer's `_build_slug_to_eci_via_catalogue()` slug-to-ECI-code map (which derives slug from `entities.json` display name `"Jammu and Kashmir (UT)"` -> slug `"jammu-and-kashmir-ut"`). This is the same slug-drift trap recorded in user-memory `lessons-2026-06-13` for `/<state>` route slugs (U08 seed `jammu-and-kashmir` vs runtime `jammu-and-kashmir-ut`). The fix lives in the writer.
4. **Per-state audit ledger** (catalogue assembly count vs mart assembly count, all 36 state/UT entries):

   | code | cat_ae | mart_ae | gap | notes |
   | --- | --- | --- | --- | --- |
   | S01-S29 (excl. S04, S09) | as-is | matches | 0 | clean |
   | **S04 Bihar** | **12** | **11** | **-1** | catalogue has TWO rows with event_id=`assembly-2005` (Feb 2005 hung + Nov 2005 re-poll); mart PK `(event_id, state_code)` collapses them. Catalogue identity bug; out of scope (Hans/Max own). |
   | **U08 J&K** | **1** | **0** | **-1** | slug-drift between disk path and writer's slug-to-eci map. Fix in R1.5. |
   | U01 / U02 / U03 / U09 | 0 | 0 | 0 | no-legislature UTs; correct (NO_ASSEMBLY_UT_SLUGS) |
   | U04 / U06 | 0 | 0 | 0 | U04 Daman+Diu pre-merger (retired); U06 Lakshadweep no-legislature; correct |

5. **Bigger latent issue, out of scope of this plan**: per-state on-disk dirs have FAR more summary.csv files than the catalogue lists (J&K: 22 disk dirs vs 10 catalogue events; Bihar: 41 disk dirs vs 23 catalogue events). The extras are historical bye-polls / by-elections / President's-Rule-era assembly events that have data on disk but no catalogue entry. This is Hans/Max territory (catalogue completeness doctrine) and deferred to a separate plan-doc. The current rip targets ONLY the in-catalogue-but-missing-from-mart cases (J&K assembly-2024) plus the Bihar identity question (deferred to Hans/Max).

**Decision**: add NEW Row R1.5 (between R1 and R2) for the mart-coverage fix. Scope: identify the writer's slug-drift line, fix it, regen mart, verify J&K U08 lights up. Bihar S04 + the broader catalogue-completeness work stays out of scope per ESCALATE trigger (Hans/Max sign-off required).

## Section 0.4 - J&K event-count claim CLOSED (was 0.3 in the prior revision)

User reported on 2026-06-15: "for some UT - the # of events is not accurate - for example Jammu (refer screenshot) says 10 events but home" (sentence truncated). After follow-up investigation:

- [StateOverview.svelte](frontend/src/routes/StateOverview.svelte) line 980 reads `"10 elections on record"` for J&K, which IS correct (10 = 1 assembly + 9 parliament in `election_events.json` for U08).
- The page the user was actually concerned about is `/t/elections/assemblies` (the AssemblyElections route), which renders the J&K card as `"No election in the catalogue yet."`. That bug is diagnosed in Section 0.3 (mart-coverage drop due to slug-drift in the writer) and ripped in Row R1.5.

No separate row for this header-count claim; closed by R1.5.

## Section 1 - Status Reckoner

| Row | Title                                                                                                                            | Status        | PR  | Effort  |
| --- | -------------------------------------------------------------------------------------------------------------------------------- | ------------- | --- | ------- |
| R1  | MH 266->288 writer rip: add MH 2024 to `eci_form10_ae.py` JOBS; DELETE `thecont1_mh_ae2024.py`; regen 288 ACs                       | [ ] PENDING   |     | S       |
| R1.5| AssemblyElections mart coverage: fix slug-drift in `event_summary.py` so J&K U08 (and any other slug-qualified UT) lights up; regen mart | [ ] PENDING   |     | S       |
| R2  | NEW `/<state>/elections/` landing route -> `StateElectionsLanding.svelte`                                                          | [ ] PENDING   |     | S       |
| R3  | Structural-only: extract 5 named subcomponents from `StateElection.svelte` (no behaviour change; Beck two-hat)                       | [ ] PENDING   |     | M       |
| R4  | Behavioural reorder + HeroCards + **year-chip rail (no arrows)** + PartyComposite + fold/search ConstituenciesByDistrict + delete deadwood | [ ] PENDING   |     | L       |
| R5  | NEW `StateEventCrossEventSankey.svelte` (diverging-bar always-on + Sankey collapsed) + opt-in caption                                | [ ] PENDING   |     | M       |
| R6  | Alliance honesty: `formation` column + render-when-data-exists + caption above panel + first-event-no-prior gating                  | [ ] PENDING   |     | M       |

Effort key: S = single sitting; M = a few hours; L = a day plus.

Hard dependencies: **R1, R1.5, R2, and R3 are independent** (parallel-safe; all touch different files). **R4 depends on R3** (consumes the extracted subcomponents). **R5 depends on R3** (mounts inside the extracted Scatter+Sankey region). **R6 depends on R4 + R5** (caption + gating tie into rearranged panels and the new Sankey button).

Parallel front: `{R1, R1.5, R2, R3}` may ship simultaneously; then `R4 -> R5 -> R6` sequential.

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

**Scope**: Diagnose + fix the slug-drift in [backend/yen_gov/canonical/derived/event_summary.py](backend/yen_gov/canonical/derived/event_summary.py) that drops J&K U08 from the `event_summary.csv` mart. Regen the mart. Verify J&K's card on `/t/elections/assemblies` flips from "No election in the catalogue yet" to a real "Latest: 2024 / JKNC / N of M / turnout%" cell.

**Root cause hypothesis** (verified by audit in Section 0.3, but the exact writer line is left for the row author to localise to keep this row scoped):

- On-disk per-event dir is `datasets/elections/assembly/state=jammu-and-kashmir/election=2024/summary.csv` (slug `jammu-and-kashmir`, no UT qualifier).
- Catalogue `entities.json` display name for U08 is `"Jammu and Kashmir (UT)"` -> slugify -> `"jammu-and-kashmir-ut"`.
- Writer's `_build_slug_to_eci_via_catalogue()` (line ~108 of `event_summary.py`) builds slug->eci_code map from catalogue. If it slugifies the display name, the map key is `jammu-and-kashmir-ut`. On-disk path is `state=jammu-and-kashmir/`. Lookup misses. Row dropped.
- Same trap recorded in user-memory `lessons-2026-06-13` for `/<state>` route slugs; the resolution there was "use eci_code as join key, not slug". The writer-side fix is symmetric.

**Files touched**:

| File                                                                                                                          | Change |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| [backend/yen_gov/canonical/derived/event_summary.py](backend/yen_gov/canonical/derived/event_summary.py)                      | Fix `_build_slug_to_eci_via_catalogue()` to canonicalise via `state_codes.csv` AND tolerate the on-disk seed-slug form (`jammu-and-kashmir`) alongside the catalogue-display form (`jammu-and-kashmir-ut`). Use eci_code as the join key; slug is an alias. |
| `backend/tests/test_event_summary_writer.py`                                                                                  | Extend with a parameterised case: stub catalogue declaring U08 display `"Jammu and Kashmir (UT)"`; stub on-disk path `state=jammu-and-kashmir/election=2024/summary.csv` with 3 winners; assert mart row for `(event_id=assembly-2024, state_code=U08)` emits with the correct seats / turnout. |
| [datasets/data/marts/elections/event_summary.csv](datasets/data/marts/elections/event_summary.csv)                            | REGEN. Pre-R1.5: 312 rows. Post-R1.5: 313 rows (+1 for U08 assembly-2024). |
| `docs/architecture/data/canonical-store.md` (or wherever event_summary mart is documented)                                   | +1 paragraph naming the slug-drift trap + the eci_code-as-join-key resolution. |

**Out of R1.5 scope** (do NOT pull these in; ESCALATE if needed):

- Bihar S04 catalogue identity bug (TWO `assembly-2005` rows for Feb + Nov 2005). Catalogue-doctrine question owned by Hans + Max.
- Catalogue completeness for the ~30 historical J&K assembly events (1962, 1967, ..., 2014, 2016) whose `summary.csv` files exist on disk but are NOT in `election_events.json`. Hans + Max territory.
- Any other slug-drifted state (probe via the audit script `.runtime/audit_mart.py` post-fix; if any other state still mismatches, STOP-AND-SURFACE).

**Acceptance gates**:

| # | Oracle                                  | Command                                                                                              | Expected |
| - | --------------------------------------- | ---------------------------------------------------------------------------------------------------- | -------- |
| 1 | Writer test                             | `cd backend && pytest -q backend/tests/test_event_summary_writer.py -k jammu`                        | exit 0 |
| 2 | Mart regen idempotent                   | `python -m yen_gov derive-event-summary --root .`; rerun; `git diff --stat datasets/data/marts/elections/event_summary.csv` | second run: 0 changed |
| 3 | Mart row count delta                    | `python -c "import csv; print(len(list(csv.DictReader(open('datasets/data/marts/elections/event_summary.csv')))))"` | `313` (was 312) |
| 4 | U08 row present                         | `grep ',U08,' datasets/data/marts/elections/event_summary.csv \| wc -l`                              | `1` (was 0) |
| 5 | Per-state audit clean (except S04 Bihar) | `python .runtime/audit_mart.py 2>&1 \| grep -i "discrepan"`                                          | only `S04` listed; U08 absent |
| 6 | Browser smoke                           | start dev server; navigate `/t/elections/assemblies`; J&K card reads "Latest: 2024 / JKNC / N of M / turnout%"; cross-check NCT of Delhi / Puducherry / TN / other slug-qualified UTs still render correctly | passing |

**Oracle (load-bearing single check)**: oracle 4 (`grep ',U08,' ... | wc -l` returns 1). If U08 row lands, the slug-drift fix succeeded.

**Dependencies**: none (parallel-safe with R1, R2, R3).

**Reviewers**: Fowler (writer slug-resolution discipline); Max (data shape - no contract change, just join-key correction).

## Section 3 - Row R2: NEW state-elections landing route

**Scope**: Mint `/<state>/elections/` as a route. Today it 404s. New file [frontend/src/routes/StateElectionsLanding.svelte](frontend/src/routes/StateElectionsLanding.svelte) renders: breadcrumb, page header `"{State} elections"`, hero card of the LATEST event per body (one for assembly, one for parliament if both exist), two parallel tables (Vidhan Sabha + Lok Sabha rows) each with year-as-link, cross-link to `/<state>` welfare context. Mounted in [frontend/src/main.ts](frontend/src/main.ts) BEFORE the existing `/<state>/elections/<event>` route.

**Files touched**:

| File                                                                                                                | Change |
| ------------------------------------------------------------------------------------------------------------------- | ------ |
| [frontend/src/routes/StateElectionsLanding.svelte](frontend/src/routes/StateElectionsLanding.svelte)                | NEW |
| [frontend/src/main.ts](frontend/src/main.ts) or `app.svelte` route table                                            | Register `/<state>/elections/` BEFORE `/<state>/elections/:event` (route order matters - the bare path must not be captured by `:event`) |
| `frontend/src/routes/StateElectionsLanding.test.ts`                                                                 | NEW unit; synthetic catalogue projection; assert "2 tables rendered when both bodies have events" + "1 table when only assembly" + "no panel when state has 0 events" |
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
| `frontend/src/lib/elections/StateElection.section-order.test.ts`                                                  | NEW static-source contract test (readFileSync + grep pattern from [frontend/src/lib/IndicatorCard.no-cross-family-chrome.test.ts](frontend/src/lib/IndicatorCard.no-cross-family-chrome.test.ts)): "Scatter mount MUST appear before ConstituencyList mount"; "InlineCounterfactualSwing mount must NOT appear"; "flat constituency table HTML must NOT appear" |
| `frontend/src/lib/elections/StateEventConstituencyList.fold-search.test.ts`                                       | NEW unit; assert all-collapsed-on-paint, search filters per-AC by name (case-insensitive), tap-to-expand inline |
| `frontend/src/lib/elections/StateEventHero.test.ts`                                                               | NEW unit; assert delta-row present when delta non-null; assert delta-row OMITTED when delta is null (first-event edge case); assert glyph emerald vs rose |
| [frontend/e2e/state-event-view.spec.ts](frontend/e2e/state-event-view.spec.ts)                                    | Extend: assert hero glyphs render; assert sibling-events strip; assert ConstituencyList collapsed; assert ScatterPlot appears ABOVE ConstituencyList in DOM order |

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

## Ledger

| Date       | Row | Notes |
| ---------- | --- | ----- |
| 2026-06-15 | plan | Authored by orchestrator (prepare-plan skill). Personas (Jony / Max / Fowler) dispatched in parallel DEBATE; verdicts converged. XLSX probed via openpyxl: 288 distinct ACs, range 1..288, zero missing. MH baseline captured: summary.csv = 266 data rows, candidacies.csv = 3825 data rows. `eci_form10_ae.py` verified to already support 13 state-events; MH 2024 absent. `thecont1_mh_ae2024.py` confirmed as the current writer for MH 2024 (reads thecont1 mirror, not ECI XLSX). J&K event count (10) verified consistent between election_events.json and StateOverview.svelte rendering - no row added; STOP-AND-SURFACE if user re-confirms with concrete repro. |
| 2026-06-15 | revision | User pushback (1): the AssemblyElections route at `/t/elections/assemblies` shows J&K card as "No election in the catalogue yet" despite assembly-2024 being in catalogue + on-disk. Audit ran (`.runtime/audit_mart.py` + `.runtime/probe_per_event.py`): mart at `datasets/data/marts/elections/event_summary.csv` (312 rows). 2 coverage gaps found: U08 J&K (1 cat, 0 mart - slug-drift bug; this plan) + S04 Bihar (12 cat, 11 mart - duplicate `assembly-2005` event_id collapses under composite PK; Hans/Max territory; out of scope). Added Row R1.5 (Section 2.5) for the slug-drift fix. User pushback (2): "no arrows for compare - 2027 ready not 1990 ready". Re-convened Jony; verdict: YEAR-CHIP RAIL (Spotify/IG/Linear pill rail) replaces the text-only Prev/Next strip; zero arrows, zero chevrons, zero Prev/Next labels; winner-color underline per chip; horizontal-scroll on mobile; current pill scroll-into-view on mount; reuses ElectionsRouteTabs.svelte pill family. Updated Section 0.1 verdict + Section 5 R4 spec. User pushback (3): RATIFIED the hero turnout-delta sourcing rule (use event_summary.csv if shipped, fallback to per-event summary.csv). Section 0.1 + R4 spec updated to mark as RATIFIED. Status Reckoner now has 7 rows (R1, R1.5, R2, R3, R4, R5, R6); parallel front is `{R1, R1.5, R2, R3}`. |
