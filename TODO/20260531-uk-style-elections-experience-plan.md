# UK-style Elections Experience - execution plan

**Last Updated**: 2026-05-31

> Build a UK-elections-style experience for yen-gov: a generic reusable tile-cartogram, a geographic|cartogram toggle, cross-year change visualisation (swing arrows + snapping time-slider + opt-in sankey), indian_mlas-style faceted filtering at state AND national level, and a new elections drill IA entered from the topic door - funnelling into the existing place/constituency spine. Lok Sabha (Parliamentary Constituency) results ingest is an in-scope, mandatory part of THIS plan (it gates the national view).
>
> Reference apps: UK = https://data-analytics.github.io/uk_elections (geographic vs hex toggle). indian_mlas = https://garudadevdataservices.github.io/indian_mlas/?mode=DEMOGRAPHICS_AGE&f_margin=%3C2&f_party=BJP (faceted filters).
>
> Authorities for this plan: data shape = Hans + Max; contracts/integration = Gregor; engineering craft = Fowler; UX/URL grammar = Jony + Citizen; any LLM bits = Andre. **User approval supersedes every agent** (CLAUDE.md s0a). The user has explicitly approved breaking the "elections is just one topic on the generic state page" constraint for this work.

---

## Section 0 - Operating contract (read before executing ANY row)

This plan is structured for **autonomous parallel execution by subagents**. Three lanes run concurrently; within a lane, rows are sequential. Each row below is a single PR with a self-contained scope, explicit file list, and acceptance gates.

### 0.1 Default stance

- **AUTO.** Execute the next in-scope row in your lane without waiting for human confirmation. Do not invent new scope; do not contract existing scope.
- **Resolve ambiguity by consulting a custom agent, not a human.** If a row is genuinely ambiguous, dispatch the named escalation agent (each row lists one), apply its verdict, record the verdict in the PR body, and proceed. Only stop for a human if a custom agent's verdict would require changing this plan's contract (e.g. dropping a phase).
- **Frugal testing (user mandate).** Run only the gates listed on the row. Do NOT run the full pytest suite for a frontend-only PR, or the full vitest suite for a backend-only PR. Do NOT wait for remote GitHub Pages deployment - local `bun run check` + `bun run test` + integrated-browser Playwright smoke is the bar. Do not repeat a green gate.
- **One in-progress row per lane.** Mark it in the Status Reckoner before starting, stamp the PR# on close.

### 0.2 Baked facts (verified 2026-05-31; do not re-derive)

- **AC (assembly) results: ingested.** 30 states/UTs. Canonical at `datasets/elections/election_results.parquet` + `dim_acs.parquet` + `dim_parties.parquet` + `dim_candidates.parquet`. Observation PK = `(entity_id, year, period_label, indicator_id)`. AC entity_id = `IN-<state>-AC-<delim_year>-<eci_no>`.
- **AC ingest pipeline to mirror for PC:** parser `backend/yen_gov/sources/eci/constituencywise.py`; observations builder `backend/yen_gov/canonical/adapters/eci/observations.py`; rollups `backend/yen_gov/canonical/adapters/eci/rollups.py`; identity `backend/yen_gov/canonical/adapters/eci/identity.py`; envelope/dim rows `backend/yen_gov/canonical/envelope.py`; backfill driver `backend/yen_gov/pipeline/canonical_eci_backfill.py`; writer `backend/yen_gov/canonical/writer.py`; CLI `backend/yen_gov/cli.py`.
- **AC indicator_ids:** `ac-winner-party-id`, `ac-winner-candidate-id`, `ac-margin-pct`, `ac-margin-votes`, `ac-turnout-pct`, `ac-nota-pct`, `ac-nota-votes`, `ac-votes-polled`, `ac-total-electors`, `ac-candidates-total`, `ac-others-votes`, `ac-others-pct`, `ac-effective-candidates-laakso`; candidate-level `candidate-votes-polled`, `candidate-vote-share-pct`, `candidate-rank`; rollups `party-seats-won`, `party-vote-share-pct`, etc. Declared in `datasets/taxonomy/indicators.json` (family `elections`).
- **PC (parliament) results: NOT ingested.** `datasets/taxonomy/election_events.json` has ZERO `kind:"lok_sabha"` rows (all `assembly`). No `dim_pcs` exists. This is Lane A's job.
- **PC raw source (VERIFIED 2026-06-01 by probe).** `datasets/ephemeral/All_States_GA.csv` IS national general election (Lok Sabha / PC) data - NOT state-assembly data. It is the **TCPD `Lok Sabha Election (GE) (AC Segment Wise)`** dataset: 259,078 rows, 43 columns, years **1999/2004/2009/2014/2019 only (NO 2024)**. Columns include `Year, State_Name, PC_No, PC_Name, Constituency_No, Constituency_Name (the AC segment), Candidate, CandID, Party, Party_ID, Votes, Position, Vote_Share_Percentage, Margin, Margin_Percentage, ENOP, Election_Type`. **Row grain = one candidate's votes within ONE assembly segment of a PC**; `Position` is the candidate's rank *within that segment*. So this file is the GE result projected down onto AC segments - it is genuinely PC/Lok-Sabha data, just disaggregated.
- **PC source strategy (resolves the old "ambiguous" tag):**
  - **CSV-ONLY INGEST CONTRACT (set 2026-06-01):** the pipeline reads **`.csv` only**; **no `.xls` / `xlrd` / pandas dependency is added to `backend`.** Every ECI source already ships a `.csv` sibling in `datasets/ephemeral/` (`#33`, `#34`). The leftover `.xls` files are NOT ingest inputs; if a future source arrives `.xls`-only, convert it to CSV in a documented one-time prep step (outside the pipeline) and ingest the CSV. Holy Law #6 / open-source-first: stdlib `csv` + DuckDB over CSV, nothing heavier.
  - **2024 (modern delim, matches the in-repo 2024 PC boundaries): use the direct-PC ECI CSV** `2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv` (VERIFIED 2026-06-01: **545 distinct (state, PC) across 39 states/UTs - full universe incl. non-assembly-UT seats; POSTAL-INCLUSIVE** - columns `State Name, PC Name, Candidate Name, Gender, Age, Category, Party Name, Party Symbol, Total Votes Polled In The Constituency, Valid Votes, General, Postal, Total, % over electors/polled/valid, Total Electors`). Two banner rows precede the real header on **row 3 (0-indexed row 2)**; trailing empty columns present - skip both on read. Already PC-level candidate results, NO aggregation, NO xls. This is the primary 2024 source.
  - **Historical series (1999-2019): prefer TCPD's direct PC-level GE release** (the non-segment "Lok Sabha Election (GE)" file, CSV) if obtainable; it is already PC-level. Only fall back to aggregating `All_States_GA.csv` (also CSV) if the direct-PC TCPD file is unavailable.
  - **Aggregation (only if forced to use the segment file):** it is a plain group-by, NOT hard work - `GROUP BY (Year, State_Name, PC_No, CandID)` then `SUM(Votes)`; the PC winner = max summed votes; PC turnout/electors come from summing segment `Valid_Votes`. DuckDB one-liner over the CSV. Documented here so PR-A1 does not re-derive it. (Caveat: segment files are EVM-only/postal-excluded and drop non-assembly-UT PCs - see PR-A1 Hans+Max verdict.)
  - **`All_States_GA.csv` best secondary use = the AC->PC crosswalk** (which AC segment belongs to which PC), feeding the `pc_id` FK on `dim_acs`. File `2024_india_loksabha_34-Details-Of-Assembly-Segment-Of-PC.csv` is the 2024 crosswalk equivalent (segment grain, EVM-only - crosswalk use only).
  - **PR-A1 deliverable:** confirm the TCPD direct-PC historical CSV exists; if yes, ingest 1999-2024 from direct-PC CSVs (ECI #33 for 2024 + TCPD-PC for history); if no, ingest 2024 direct + 1999-2019 via the documented segment aggregation - all CSV.
- **PC boundaries: EXIST.** `datasets/boundaries/in/pc/delim=2024/all.geojson` (+ `all.topojson`), 545 features. Feature properties: `state_ut_name`, `state_ut_code`, `ls_seat_name`, `ls_seat_code` (ECI numeric seat code, STRINGIFIED - requires int coercion on join), `unique_id` (e.g. `S07_5`). Join key = `ls_seat_code`.
- **Schema already supports PC/lok_sabha:** `datasets/schemas/election-events.schema.json` kind enum includes `lok_sabha`; `datasets/schemas/constituency.schema.json` has `pc_id` of form `<state>-PC-<eci_no>` and the AC->PC nesting FK. No schema MAJOR bump needed for `kind:"lok_sabha"`.
- **National loader does NOT exist.** `frontend/src/lib/view-models/state-overview.ts` `loadStateAcWinners` is per-state (`entity_id LIKE 'IN-' || state || '-AC-%'`). A cross-state `loadNationalPcWinners` must be authored (Lane B).
- **No `INDIA_PC` entry in `frontend/src/lib/maplibre/sources.ts`** (only `STATE_AC`). `BoundaryEntry` shape: `{ id, label, geojson_local_path?, geojson_url, join_property }`.

### 0.3 CONCURRENCY - other agents are mid-flight (CRITICAL)

A separate topojson/boundary migration is running across many worktrees RIGHT NOW. It is actively churning:

- `frontend/src/lib/maplibre/sources.ts` (boundary entry declarations + topojson format additions)
- `datasets/boundaries/in/pc/**` (geojson -> topojson conversion; `BOUNDARY_FORMAT` env switch)
- `frontend/e2e/boundary-benchmark.spec.ts` (perf benches tagged `@bench`)

**Rules to avoid collisions:**

1. **Only ONE row in this plan touches `sources.ts`** - PR-B4 - and it is **append-only** (add a single `INDIA_PC` export at the end; do NOT edit, reorder, or reformat `STATE_AC` or the topojson-loading path). Immediately before PR-B4, `git fetch origin && git rebase origin/main`. If `sources.ts` conflicts, take **theirs** wholesale and re-append the `INDIA_PC` block.
2. **Do NOT depend on the PC boundary file FORMAT.** Read whichever of `all.geojson` / `all.topojson` the existing `MapChoropleth` loader resolves; do not hardcode a format. Do not convert or move any file under `datasets/boundaries/`.
3. **Do NOT add boundary-heavy cases to `golden-path.spec.ts`.** New election e2e specs go in a dedicated file `frontend/e2e/elections-atlas.spec.ts` and, if perf-sensitive, are tagged `@elections` (not `@bench`).
4. **Lane A (backend) and Lane 0 (docs) do not touch boundary files at all** - they are collision-free by construction.
5. Before each PR: `git worktree add ../yen-gov-elec-<row> -b feat/elec-<row> origin/main`. Never branch from another worktree's branch. Never park a worktree on `main` (keeps gh-merge clean per repo lessons).

### 0.4 Data truth that shapes the whole IA (do not violate)

Indian election results have a **constituency grain** (AC for state assembly, PC for Lok Sabha). **Constituencies do NOT nest into villages or sub-districts.** The drill therefore stops at the constituency leaf; there is NO village/sub-district level for election results. The honest drill is:

`country (PC atlas) -> state -> district-cluster (a FILTER, not a route) -> constituency leaf`.

State assembly uses AC; national uses PC. The cartogram and choropleth are built **grain-agnostic** so the same components serve both. This was user-confirmed on 2026-05-31.

### 0.5 Closure condition

Plan complete when every row is DONE or COLLAPSED-with-rationale. On completion: distil durable findings to `docs/` per `docs/how-to/distill-a-plan.md`, append the "Plan complete" distillation map, `git mv` this file to `docs/archive/plans/`.

---

## Section 1 - Status Reckoner

Lane 0 (docs/decisions), Lane A (backend PC ingest), Lane B (frontend) run in PARALLEL. `||` marks rows that can start immediately (no in-plan dependency).

| Row | Lane | Title | Depends on | Status | PR | Escalation agent |
| --- | --- | --- | --- | --- | --- | --- |
| PR-0 | 0 | ADR + docs: drill IA, generic TileCartogram, AC/PC grain, filter URL grammar | none `||` | [x] DONE | - | Gregor (PASS-WITH-NITS; 5 edits applied) |
| PR-A1 | A | PC source recon + ingest handover-doc + pre-flight proposal | none `||` | [x] DONE | Max (handover + pre-flight exit 0 add_facet) |
| PR-A2 | A | PC identity + PcDimRow + envelope + pc-* indicators + concepts + schemas | PR-A1 | [ ] PENDING | Hans + Max |
| PR-A3 | A | PC parser + observations + rollups + CLI `ingest-eci-ls` | PR-A2 | [ ] PENDING | Gregor |
| PR-A4 | A | Run ingest: write PC parquet + dim_pcs + lok_sabha event row + validate | PR-A3 | [ ] PENDING | Max |
| PR-B1 | B | Tile-layout schema + grapher layouts + pilot S13-AC + national-PC layout | none `||` | [ ] PENDING | Jony |
| PR-B2 | B | Generic `<TileCartogram>` SVG component + layout loader + ChartShell wrap | PR-B1 | [ ] PENDING | Jony |
| PR-B3 | B | `ElectionMap` wrapper (Map\|Equal seats toggle) on StateElection (AC) | PR-B2 | [ ] PENDING | Jony |
| PR-B4 | B | National atlas route `/t/elections/:event` + INDIA_PC + loadNationalPcWinners | PR-B2; live data needs PR-A4 | [ ] PENDING | Gregor |
| PR-B5 | B | Cross-year E1: swing arrows on seat-composition bars | PR-B3 | [ ] PENDING | Jony |
| PR-B6 | B | Cross-year E2: snapping time-slider on map/cartogram | PR-B3 | [ ] PENDING | Jony |
| PR-B7 | B | Cross-year E3: opt-in 2-election sankey (capped) | PR-B3 | [ ] PENDING | Jony |
| PR-B8 | B | Filter rail F1/F2/F3 (party / margin band / colour-by) - state level | PR-B3 | [ ] PENDING | Gregor + Max |
| PR-B9 | B | Wire filters at national level | PR-B8; PR-B4; PR-A4 | [ ] PENDING | Gregor |

**Concurrency map:** at t0 three agents can start in parallel on **PR-0**, **PR-A1**, **PR-B1**. Lane A and Lane B never touch the same files. The only cross-lane data dependency is PR-B4/PR-B9 needing PR-A4's PC data for LIVE rendering - both ship "dark" (boundary renders, winners show a "results pending" state) before PR-A4 lands, then light up automatically.

---

## Lane 0 - Decisions and docs

### PR-0 - ADR + docs for drill IA, generic TileCartogram, grain split, filter grammar `||`

**Scope:** Pure docs/decision. No code, no data. Locks the contracts the other two lanes build against. Ship FIRST in its lane but does not block other lanes from starting.

**Files:**
- NEW `docs/architecture/decisions/00XX-elections-drill-ia-and-tile-cartogram.md` (allocate the next free ADR number via `Get-ChildItem docs/architecture/decisions/ | Sort-Object Name | Select-Object -Last 3`).
- EDIT `docs/concepts/schema-is-the-design-system.md` - add `TileCartogram` to the election renderer set; record "one card per measure" still holds; cartogram is election-mount-only in v1.
- EDIT `docs/architecture/frontend/map.md` - add the `Map | Equal seats` mode contract + `?view=hex` URL param + "Each tile = one seat" legend rule.
- EDIT `docs/architecture/data/elections-indicators.md` - add a "PC (Lok Sabha) results - pending Lane A" note + the planned `pc-*` indicator list (mirror of `ac-*`).

**ADR must record (these ARE the contracts other rows depend on - be unambiguous):**
1. **Drill IA:** entry `/t/elections/:event` (NEW national PC atlas) -> `/lab/:state/:event` (existing state surface) -> district as `?d=<district>` FILTER (not a route) -> `/s/:state/ac/:ac` leaf. Place page `/s/:state` remains the spine. NO village/sub-district level for results.
2. **Grain split:** national = PC grain, state = AC grain. Components are grain-agnostic ("unit" = a constituency of either kind).
3. **Generic TileCartogram, election-mount-only in v1:** one reusable SVG primitive fed by a layout dataset; NOT wired to welfare/denominator indicators in v1 (equal-sizing welfare data is misleading - Hans/Max). Tile layouts are FRONTEND-OWNED render data under `datasets/grapher/` per ADR-0045, NOT canonical election data.
4. **Toggle:** segmented `Map` / `Equal seats` (never the words "choropleth"/"cartogram"); default geographic at all levels; persists to URL `?view=hex`; legend carries "Each tile = one seat."
5. **Cross-year ship order:** seat-bars + swing arrows (default), then snapping time-slider (snaps to election years, no interpolation, no autoplay), then opt-in 2-election capped sankey.
6. **Filter URL grammar (the contract PR-B8/B9 implement):** `?party=<csv of party short codes>` , `?margin=<all|lt2|gt20>` , `?mode=<winner|margin|turnout|age>` , `?view=<geo|hex>` , `?d=<district>`. Filters are modifiers on a fully-populated default view, never preconditions. Full example: `/t/elections/2024-ls?party=bjp&margin=lt2&mode=margin&view=hex`.
7. **Do-not-build list (v1):** village/sub-district levels; full >2-election sankey; a second `/t/elections/country/state/...` URL spine; per-state hand-placed bespoke hex layouts; autoplay/interpolated transitions; demographic cross-tabs beyond "colour by".

**Escalation:** if the ADR's grain or URL-grammar choices feel under-specified, dispatch **Gregor** ("Is this filter URL grammar a clean, versionable contract? Does the AC/PC grain-agnostic unit model hold?") and apply the verdict.

**Acceptance gates (frugal - docs only):**
- [ ] G-docs: every new/edited doc has H1 + `Last Updated: 2026-05-31` + "See also" cross-links; ASCII-only (CLAUDE.md s5).
- [ ] No code/data/schema touched (so NO pytest/vitest/validate needed - mark them n/a in PR body).

---

## Lane A - Backend: Lok Sabha PC results ingest (mandatory; gates national view)

> This lane mirrors the existing AC ingest pipeline (Section 0.2) for Parliamentary Constituencies. It is file-collision-free with Lanes 0 and B. Treat the AC modules as line-by-line templates. Follow `TODO/_TEMPLATE-ingest-handover.md` discipline and the pre-flight-ingest gate (ADR-0046).

### PR-A1 - PC source recon + handover-doc + pre-flight proposal `||`

**Scope:** Recon + paperwork only. NO canonical writes. Resolves the "which raw source" ambiguity and produces the ingest contract the rest of Lane A executes against.

**Steps:**
1. Inspect the candidate raw sources in `datasets/ephemeral/` (CSV-only ingest contract - read CSV headers + sample rows with a `.tmp_probe_pc.py` stdlib-`csv` script; **the `.xls` files are NOT ingest inputs** - every source has a `.csv` sibling, so NO `xlrd`/pandas is added to `backend`):
   - `2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv` (ECI, **direct PC-level, postal-inclusive** - `General/Postal/Total` cols; banner rows 1-2, header row 3; 545 distinct PCs; primary 2024 source, NO aggregation).
   - `2024_india_loksabha_34-Details-Of-Assembly-Segment-Of-PC.csv` (AC->PC segment map, EVM-only - **crosswalk ONLY**, useful for the `pc_id` FK on `dim_acs`).
   - `All_States_GA.csv` (TCPD `Lok Sabha (GE) (AC Segment Wise)`; 259,078 rows; 1999-2019 only, NO 2024; PC-tagged segment rows). Use = AC->PC crosswalk + historical fallback (aggregate segments to PC only if the direct-PC TCPD CSV is unavailable). NOT state-assembly data.
2. **Verdict:** `...33-Constituency-Wise-Detailed-Result.csv` confirmed to yield PC-level winners directly (postal-inclusive, 545 PCs). Record it as the 2024 primary. The remaining open item is sourcing the TCPD direct-PC **CSV** for 1999-2019 (see escalation).

**HANS + MAX VERDICT (baked 2026-06-01; research-only, both dispatched before PR-A1 starts):**
   - **2024 source = ECI `#33` direct-PC `.csv`** (postal-inclusive: `General/Postal/Total` cols; 545 distinct PCs; banner rows 1-2 + header row 3; **NO `xlrd`/pandas - CSV-only**). The `#34-Details-Of-Assembly-Segment-Of-PC.csv` (61,736 rows; cols `State/UT Name, PC NO, PC NAME, TOTAL ELECTORS IN PC, AC NO, AC NAME, TOTAL ELECTORS IN AC, TOTAL VALID VOTES IN STATE, NOTA VOTES EVM IN AC, CANDIDATE NAME, PARTY, VOTES SECURED EVM`) is **EVM-only / postal-excluded, AC-segment grain** - same shape as `All_States_GA.csv`. **Use `#34` ONLY as the 2024 AC->PC crosswalk + segment fanout, NEVER for PC totals/winner.**
   - **2019 source = ECI `#33`-equivalent direct `.csv`** (acquire the 2019 ECI constituency-wise CSV, same shape as 2024). **1999-2014 = TCPD's direct PC-level GE release** (the non-segment sibling, CSV - ACQUIRE it; confirm URL+licence in handover s7). `All_States_GA.csv` is **fallback-only**, every PC total then tagged `segment_approximate = true`.
   - **DECISIVE: do NOT make any AC-segment file the canonical PC spine.** It structurally **drops the ~5-7 non-assembly-UT single-PC seats every year** (Chandigarh, Lakshadweep, A&N, DNH-DD, Ladakh post-2019) because those PCs have no underlying AC segments. ECI direct files include them. Per-year **PC-count assertion (543/545) is the ingest gate** that catches this instantly.
   - **Postal-ballot level-shift (invisible methodology break):** segment-sum(PC) = ECI-official(PC) - postal ballots. Mixing postal-inclusive 2024 with postal-excluded 1999-2019 silently shifts turnout/votes/margin. If a year uses segment data, its `votes-polled/turnout/margin/nota` MUST carry `segment_approximate` so the frontend discloses it.
   - **2008 delimitation = hard discontinuity.** 1999/2004 = pre-2008; 2009/2014/2019/2024 = 2008 delim. `PC_No` NOT comparable across the break. Entity id MUST carry a delim token: `IN-PC-<delim_year>-<pc_no>`. Add ONE `methodology_breaks.parquet` row for 2008. Never join a 2004 PC_No to a 2009 PC_No. NOTA is null (not zero) pre-2013. Telangana pre-2014 framed under AP (entity remap, not a hole).
   - **5 mandatory reconciliation checks (bake into handover s3):** (1) EVM-vs-total tie-out per candidate (residual = postal votes, assert >=0); (2) **winner-flip guard** - compute winner segment-sum vs direct-PC, count disagreements, flipped PCs take winner from direct source; (3) margin-safety band - flag PCs with margin_pct < ~1% as postal-untrustworthy; (4) NOTA reconciliation; (5) crosswalk integrity - `SUM(electors across AC segments) == TOTAL ELECTORS IN PC` (validates the `#34` mapping independent of votes).
   - **GRAIN-PREFIX FORK - RESOLVED (Gregor, 2026-06-01): Option B with concept-binding.** Mint `pc-*` indicator ids mirroring the live `ac-*` set. This is sanctioned, NOT debt-laden: the grain-prefix gate (`GRAIN_PREFIX_RE = ^(state|district|national)-` in `backend/yen_gov/preflight/predicates.py` + Tier-B `tier_b_indicator_id_no_grain_prefix`) matches ONLY `state-/district-/national-`; it NEVER matches `ac-`/`pc-`, which [ADR-0044](../docs/architecture/decisions/0044-grain-over-entity.md) explicitly preserves as fact-grain prefixes. **The earlier claim that `ac-*` "contradicts ADR-0044" and that post-PR-B9 enforcement force-unwinds both `ac-*` and `pc-*` is WITHDRAWN - it is factually wrong against the regex.** `tier_b_one_indicator_per_concept` ships dark and keys on `(concept_id, sorted entity_kinds)`; `ac` and `pc` are distinct entity_kinds so it never collides them. The only gate that fires is pre-flight concept-overlap/concept-FK (#1/#6).
     - **Binding requirement (makes B a strict subset of the OWID-pure end-state):** every `pc-*` row MUST FK to a row in `datasets/taxonomy/concepts.json`. For each measure that exists at BOTH grains (winner-party, winner-candidate, margin-pct, margin-votes, turnout-pct, nota-pct, votes-polled, total-electors, candidates-total), the `ac-*` and `pc-*` ids MUST share ONE `concept_id` whose `entity_kinds` lists both `ac` and `pc`. This satisfies pre-flight #6 and keeps #1 honest (adding a grain to an existing concept, not minting a duplicate). A future single-id collapse, if ever mandated, becomes a pure expand-migrate-contract rename over rows that already share identity - never a re-model.
     - **Rejected - Option A (de-prefix now):** breaking migration of live `election_results.parquet` + every consumer filtering `indicator_id='ac-winner-party-id'`, for zero enforcement benefit. MP and MLA seats are different offices on different boundaries, not one fact at two zooms - the OWID single-Variable rule does not apply.
     - **Rejected - third path (PC-neutral-now):** two live conventions force the frontend to special-case both, and the eventual `ac-*` de-prefix would collide with the neutral PC id. Uniform sanctioned prefixes beat a clean island beside a legacy continent.
     - **Run before authoring any `pc-*` row:** `python -m yen_gov check-overlap --concept "parliamentary constituency election winner" --unit "<u>" --entity_kind "pc"` then `pre-flight-ingest`. Expect the concept-FK path to pass via the SHARED `concept_id`, not `mint_new` of a fresh concept. Exit 2 = fix proposal (Holy Law #5, no override). Cite ADR-0044 + ADR-0045 + both gate reports in the handover.
   - **Enrichment (candidate-bio columns: Sex, MyNeta_education, TCPD_Prof_Main, Turncoat, Incumbent, No_Terms) = OUT OF SCOPE for PR-A1.** Different grain (candidate, not PC-result) + lower tier (affidavit/research-derived, silver-bronze). Queue as a later PC candidate sidecar mirroring the AC people sidecar; do NOT bloat the gold result rows.
   - **`update_period_days = 1825`** (5-yr LS cycle - the electoral horizon, NOT the TCPD/ECI publisher lag).

**GREGOR VERDICT (contract / integration / write-seam / schema; baked 2026-06-01, research-only):**
   - **WRITE SEAM - same family, same `state=` partition.** PC ObservationRows write into the EXISTING `datasets/elections/state=<key>/election_results.parquet` Hive partition set, NOT a sibling family. Discrimination is the Content-Based Router the corpus already uses: `entity_id` prefix (`IN-PC-...` vs `IN-<state>-AC-...`) + `indicator_id` (`pc-*` vs `ac-*`). Each PC row's `state` partition value = the PC's `state_code` (from the `#34` crosswalk / `dim_pcs`); every Indian PC lies within one state/UT so this is always defined. One logical fact-type ("election result") = one Canonical Data Model = one family + one reader path; a sibling family is premature partitioning. Additive - PC rows slot into existing shards, no layout migration, `deploy-site.yml` smoke checks unaffected. **Do NOT add a `grain=`/`scope=` partition dimension** - it would relocate every existing AC shard and break hardcoded reader/smoke paths for no pruning gain on a national query that wants everything.
   - **Read patterns:** per-state AC and per-state PC drill both prune to a single shard; the national PC atlas (`WHERE indicator_id='pc-winner-party-id' AND entity_id LIKE 'IN-PC-%'`) scans all shards BY DESIGN (a national query wants all states; DuckDB-WASM serves it via parallel Range reads over a thin PC slice).
   - **Two integration MUST-FIXES (carry into PR-A2/A3):** (1) **PC `entity_id` MUST be globally unique** - ECI `pc_no` is per-state (every state has a "PC 5"), so `IN-PC-<delim>-<pc_no>` alone COLLIDES across states and the national `LIKE 'IN-PC-%'` filter returns ambiguous rows. Carry the state: `IN-PC-<delim>-<state_code>-<pc_no>` (or a nationally-unique seat code). Hans+Max own the final shape, but global uniqueness is a HARD contract. (2) **Update `backend/yen_gov/coverage.py`** to discriminate AC vs PC rows by `entity_kind`/`indicator_id` so PC rows in the shared `state=` shards are not miscounted as AC coverage.
   - **CSV-ONLY SEAM.** Converting any `.xls`-only source to CSV stays a documented one-time prep step OUTSIDE the pipeline (handover s7), NOT an in-repo tool - every current source already has a CSV sibling, so an in-repo converter now is speculative complexity. IF a recurring `.xls`-only source later appears, add a version-pinned, tested converter under `tools/` (NEVER `backend/`; `tools/` must not import backend runtime per the layer rule) emitting CSV into `datasets/ephemeral/`. Pipeline input contract stays "CSV in ephemeral"; no `xlrd`/pandas in `backend`.
   - **Quirk-handling location:** banner-row skip (header row 3) + trailing-empty-column tolerance live in the SOURCE-SPECIFIC parser `backend/yen_gov/sources/eci/ls_constituencywise.py` (Message Translator for ECI #33), NOT a shared normalization filter - these are facts about source #33; a generic filter would wrongly imply every source has banner rows.
   - **Fail-fast source-shape contract (Holy Law #3 + boundary rule):** after skipping to the real header, the parser MUST assert the expected header set is present (e.g. `State Name, PC Name, Candidate Name, Party Name, General, Postal, Total, Valid Votes, Total Electors`) and RAISE with the missing-column names if any are absent. No silent coercion, no positional-column guessing. Add a Tier-A test feeding a header-shifted fixture asserting the parser raises.
   - **SCHEMA VERSIONING.** Adding `pc` to the catalogue `entity_kinds` enum is an ADDITIVE MINOR bump (`1.x -> 1.(x+1)`) per CLAUDE.md s11 + a new `x-changelog` entry in the same commit (nothing removed/renamed/narrowed = not major). `kind:"lok_sabha"` is already a valid value in `election-events.schema.json` - NO events-schema bump (adding the event ROW is data, not schema). `observation.schema.json` does NOT constrain `entity_kind` to an enum (only `derivation` is enumerated) - NO observation-schema bump expected; PR-A2 MUST grep-confirm before assuming it.
   - **ADR-0047 reader-compatibility (the one real concern):** DuckDB-WASM treats `entity_kind` as an opaque string and is unaffected, but the frontend grain-dispatch MUST handle `entity_kind='pc'` BEFORE PR-A4 writes any `pc` row (rule #3: reader ships before producer - the plan already sequences this via PR-B4 dark). PR-A2/A3 gate: audit every reader switching on `entity_kind` and confirm `pc` hits a graceful/default branch, not an exhaustiveness throw. ADR-0044 already removed `IndicatorChoropleth`'s `entity_kind==="state"` hard constraint - dispatch-by-grain is the model.
   - **Doc impact (PR-0):** record the Option-B concept-binding rule + same-family/`state=`-partition decision as the two load-bearing contracts in the PR-0 ADR; add short entries to `docs/architecture/data/canonical-store.md` (PC shares `elections` family + `state=` partition) and the elections-indicators doc (the `pc-*` set + shared-`concept_id` rule). The fail-fast parser contract goes in the ingest subsystem doc / handover s7. None of this reopens ADR-0044.
3. Write `TODO/20260531-ls-pc-ingest-handover.md` from `TODO/_TEMPLATE-ingest-handover.md`, filled completely: source, scope (concept = "parliamentary constituency election result"; entity grain = `pc`; time range), and the planned `pc-*` indicator list.
4. Author `proposal.json` + run `python -m yen_gov pre-flight-ingest --proposal-file ./proposal.json --report ./report.json`. The pc-* indicators are NEW concepts (no AC overlap because grain differs) - expect `mint_new`. Cite both paths in the handover-doc s3. Exit code 2 = fix proposal and re-run (no override per Holy Law #5).
5. Decide the `event_id` naming for the lok_sabha event (e.g. `LsGen2024`) and `period_label` convention consistent with how assembly events shape `period_label`. Record it in the handover-doc - PR-A3/A4 depend on it.

**CLOSED 2026-05-31 (commit pending on branch):** Recon ran via `.tmp_probe_pc.py` (stdlib csv, deleted post-recon). Corrected header detection: ECI #33 real header is csv.reader row index 2 (banner row 0 + group sub-header row 1 + header row 2; the "header row 3" framing was the splitlines view of an embedded-newline cell). Confirmed: 542 contested PCs (Surat PC-24 unopposed, excluded by ECI; 543 total), 8904 candidate rows, postal-inclusive (General/Postal/Total per candidate), per-PC totals repeat per row, NOTA is a row, single-PC non-assembly UTs present, 3 footer junk pseudo-rows to skip, and NO `PC No` column (sourced from #34 crosswalk on `(State, PC Name)`). Handover: [20260531-ls-pc-ingest-handover.md](20260531-ls-pc-ingest-handover.md). Pre-flight on representative `pc-votes-polled` -> verdict `add_facet` (concept overlap 1.0 with `votes-polled`), exit 0, all six checks pass -> [proposal](20260531-ls-pc-proposal.json) + [report](20260531-ls-pc-report.json). This confirms the Option B concept-binding path (bind pc-* to existing AC concepts by extending `entity_kinds`, NOT `mint_new`); the step-4 "expect mint_new" note predates the baked Option-B resolution and is superseded. event_id = `LsGen2024`, period_label = `2024`, entity_id = `IN-PC-2008-<state_code>-<pc_no>`.

**Escalation:** **Max + Hans + Gregor dispatched 2026-06-01; verdicts baked above.** Remaining open follow-up for handover s7: confirm the **TCPD direct PC-level LS results** file URL + licence for 1999-2019 (the postal-inclusive sibling of `All_States_GA.csv`); fallback if unavailable = ECI's own pre-2019 constituency-wise archives (keeps the whole 1999-2024 spine ECI-primary, sidesteps the segment hole). The grain-prefix fork is **RESOLVED to Option B with concept-binding** (Gregor verdict above) - no further sign-off blocks PR-A2.

**Acceptance gates (frugal):**
- [ ] G1 `python -m yen_gov validate --root .` OK (no data changed, but confirms repo clean).
- [ ] pre-flight-ingest report committed with exit 0/1 (not 2).
- [ ] No pytest/vitest (recon + docs only).

### PR-A2 - PC identity + dimension + indicator catalogue + schemas

**Scope:** The static contracts for PC data. No ingest run yet (that's PR-A4). Mirror the AC envelope/identity.

**Files:**
- EDIT `backend/yen_gov/canonical/adapters/eci/identity.py` - add `pc_entity_id(...)` mirroring `ac_entity_id`. PC is NATIONAL scope. **Gregor contract (resolved): `entity_id` MUST be globally unique - ECI `pc_no` is per-state, so carry the state: `pc_id = IN-PC-<delim_year>-<state_code>-<pc_no>`** (or a nationally-unique seat code). `IN-PC-<delim>-<pc_no>` alone collides across states and breaks the national `LIKE 'IN-PC-%'` filter. Add a `pc_state_code` carry-through for the `state_code` column on the dim (also = the `state=` partition value, Gregor write-seam verdict).
- EDIT `backend/yen_gov/canonical/envelope.py` - add `PcDimRow(pc_id, delim_year, pc_no, ls_seat_code, state_code, name, source_id)` and a `pc_dim_rows: list[PcDimRow]` field on `BatchEnvelope`.
- EDIT `datasets/taxonomy/indicators.json` - **Grain-prefix fork RESOLVED to Option B with concept-binding (Gregor + Hans + Max verdicts in PR-A1).** Add `pc-winner-party-id`, `pc-winner-candidate-id`, `pc-margin-pct`, `pc-margin-votes`, `pc-turnout-pct`, `pc-nota-pct`, `pc-votes-polled`, `pc-total-electors`, `pc-candidates-total` (mirror the AC set; family `elections`; declare `update_period_days: 1825` per guardrail #18). **Each `pc-*` measure that also exists at AC grain MUST share ONE `concept_id` with its `ac-*` sibling**, that concept's `entity_kinds` listing both `ac` and `pc` (the binding that makes Option B a strict subset of the OWID-pure end-state). Run `check-overlap` + `pre-flight-ingest` first - expect the concept-FK path to pass via the SHARED concept, NOT `mint_new` of a duplicate. NOTA indicators null (not zero) pre-2013; segment-sourced years carry `segment_approximate`.
- EDIT `datasets/taxonomy/concepts.json` - add/extend the concept row(s) the pc-* indicators FK to, declaring `(noun, unit_canonical, normalisation, entity_kinds:[ac, pc])` for measures shared with AC (Gregor concept-binding). Per pre-flight: extend an existing concept's `entity_kinds` to add `pc` rather than minting a duplicate concept where an AC sibling already exists.
- Bump any schema that enumerates entity_kinds or indicator families if required. **Gregor (resolved): adding `pc` to the catalogue `entity_kinds` enum is an ADDITIVE MINOR bump** (`1.x -> 1.(x+1)`) + new `x-changelog` entry same commit; NOT major. `kind:"lok_sabha"` is already valid in `election-events.schema.json` (NO events-schema bump). **Grep-confirm `observation.schema.json` does NOT enumerate `entity_kind`** (only `derivation` is enumerated) before assuming no observation-schema bump. Follow CLAUDE.md s11.

**Escalation:** Indicator/concept shape signed off by Hans + Max (PR-A1 verdicts). The contract/integration shape (write-seam, entity_id uniqueness, concept-binding, schema bump) is signed off by Gregor (PR-A1 verdicts). No open escalation - if the indicator units drift from the AC denominators during authoring, re-confirm with Hans.

**Acceptance gates (frugal - targeted):**
- [ ] G1 `python -m yen_gov validate --root .` OK.
- [ ] G2 `pytest -q backend/tests` filtered to the touched modules (envelope, identity, indicator-catalogue, concepts validators). Set `$env:PYTHONPATH="$PWD\backend"` first (multi-worktree venv-shadow rule). Do NOT run the full suite.
- [ ] Schema changelog bumped if any schema changed.

### PR-A3 - PC parser + observations + rollups + CLI command

**Scope:** The logic that turns the confirmed raw source into `pc-*` ObservationRows + PcDimRows. Mirror `observations.py` + `rollups.py`. Tested against a small committed fixture, NOT the real corpus (no-real-corpus-in-pytest rule).

**Files:**
- NEW `backend/yen_gov/sources/eci/ls_constituencywise.py` (or extend the existing parser if the CSV shape matches) - parse the confirmed PR-A1 **CSV** source (stdlib `csv`, skip 2 banner rows, header row 3, ignore trailing empty cols) into a `PcResultRaw` per PC. **No `xlrd`/pandas.** **Gregor fail-fast contract:** after skipping to the real header, ASSERT the expected header set is present (`State Name, PC Name, Candidate Name, Party Name, General, Postal, Total, Valid Votes, Total Electors`) and RAISE with the missing-column names if any absent - no silent coercion, no positional guessing. Add a Tier-A test feeding a header-shifted fixture asserting the parser raises.
- NEW `backend/yen_gov/canonical/adapters/eci/pc_observations.py` - `observations_from_pc(...)` emitting `pc-winner-party-id`, `pc-margin-pct`, `pc-turnout-pct`, etc., mirroring `observations_from_constituency`.
- EDIT `backend/yen_gov/canonical/adapters/eci/rollups.py` - if national/party rollups for LS are in scope, add them; otherwise note as deferred.
- EDIT `backend/yen_gov/coverage.py` - **Gregor must-fix:** discriminate AC vs PC rows by `entity_kind`/`indicator_id` so PC rows in the shared `state=` shards are not miscounted as AC coverage (or vice-versa).
- EDIT `backend/yen_gov/pipeline/canonical_eci_backfill.py` - add a PC slice builder.
- EDIT `backend/yen_gov/cli.py` - add `@app.command("ingest-eci-ls")` mirroring `ingest-eci-ae-panel`.
- NEW `backend/tests/test_pc_observations.py` + a tiny committed fixture (2-3 PCs) under the test fixtures dir. Tier-A: assert winner/margin/turnout values for the fixture.

**Escalation:** Write-seam **RESOLVED by Gregor (PR-A1)**: PC rows share the EXISTING `datasets/elections/state=<key>/election_results.parquet` family, disambiguated by `entity_id` prefix (`IN-PC-` vs `IN-...-AC-`) + `indicator_id` (`pc-*` vs `ac-*`); each PC row's `state` partition = its `state_code`. NOT a sibling family/partition; do NOT add a `grain=`/`scope=` dimension. No open escalation.

**Acceptance gates (frugal):**
- [ ] G2 `pytest -q backend/tests/test_pc_observations.py` green (+ any directly touched writer test). `$env:PYTHONPATH` set. Do NOT run full suite.
- [ ] G1 `python -m yen_gov validate --root .` OK.

### PR-A4 - Run the ingest: PC parquet + dim_pcs + lok_sabha event + validate

**Scope:** Execute `ingest-eci-ls` to WRITE canonical PC data, add the `lok_sabha` event row, validate. This is the row that lights up the national view.

**Steps:**
1. `python -m yen_gov ingest-eci-ls --root .` -> writes PC ObservationRows into `datasets/elections/election_results.parquet`, `dim_pcs.parquet`, UPSERTs `sources.parquet`.
2. Add the `kind:"lok_sabha"` event row to `datasets/taxonomy/election_events.json` using the PR-A1 `event_id`/`display`/`polled_on` convention (display format `"<scope> - Lok Sabha <YYYY>"` per the events schema description). `kind:"lok_sabha"` is already a valid enum value - no schema bump.
3. `python -m yen_gov validate --root .` - confirm provenance FKs (every PC obs row has `source_id`), entity_kind, schema versions.
4. Spot-check with a `.tmp_check_pc.py` DuckDB query: count PC winners (~543 expected for 2024), confirm join to `dim_pcs` + `dim_parties` resolves.

**Escalation:** dispatch **Max** if PC coverage is incomplete (missing seats / states) - record the gap honestly in the handover-doc and `election_events.json` `data_status` (`partial` vs `complete`); do not fabricate.

**Acceptance gates (frugal):**
- [ ] G1 `python -m yen_gov validate --root .` OK (this is the gate that matters - real data written).
- [ ] DuckDB spot-check: PC winner count in expected range; FK joins resolve.
- [ ] G2 only the writer/validator tests that exercise the new partition. No full suite.

---

## Lane B - Frontend: generic machinery (AC/state first; PC/national lights up after Lane A)

> This lane builds entirely on EXISTING AC data, so it does not wait for Lane A. Components are grain-agnostic; PR-B4/B9 ship "dark" for PC and auto-populate when PR-A4 lands. Touches `sources.ts` exactly once (PR-B4, append-only) - obey Section 0.3.

### PR-B1 - Tile-layout schema + grapher layouts + pilot layouts `||`

**Scope:** The frontend-owned tile-layout contract + data. No component yet. Can start at t0.

**Files:**
- NEW `datasets/schemas/grapher-election-tile-layout.schema.json` v1.0 (full s11 header: `$schema`, local `$id`, `title`, `description`, `x-version:"1.0"`, `x-changelog`). Row fields: `layout_kind` (`ac`|`pc`), `scope` (state_code like `S13`, or `national`), `delim_year`, `unit_id` (the `ac_id`/`pc_id` or its eci/ls number), `eci_no`, `q`, `r` (axial hex coords; optionally `x`,`y`), `label`, `source_id`, `layout_version`, `derivation_method` (e.g. `centroid-hexbin` | `hand-authored`).
- NEW `datasets/grapher/election_tile_layouts.json` (or partitioned under `datasets/grapher/election-tile-layouts/`) - frontend-owned per ADR-0045.
- Pilot data: **Maharashtra S13 AC layout** (288 ACs) + **national PC layout** (~543 PCs). Generate from boundary centroids via a `.tmp_gen_layout.py` hexbin pass, then PERSIST the coords (no browser-side layout compute - citizens see stable positions). The PC layout can be authored now from geometry alone (does not need PC RESULTS).
- NEW `frontend/src/contracts/election-tile-layout-coverage.test.ts` - assert exactly one tile per dim row for each shipped `(layout_kind, scope, delim_year)`. For the PC layout, assert coverage against the 545 boundary features (since `dim_pcs` may not exist yet); for the S13 AC layout, assert against `dim_acs` S13 rows. Write the test to read whichever source-of-truth exists.

**Escalation:** dispatch **Jony** ("Is a centroid-hexbin layout legible for S13/India, or do we need a coarse manual cleanup of overlaps?"). Apply verdict; if manual cleanup needed, hand-edit the persisted coords and set `derivation_method: hand-authored`.

**Acceptance gates (frugal):**
- [ ] G1 `python -m yen_gov validate --root .` OK (validates the new grapher file against its schema).
- [ ] G4 `bun run test` filtered to `election-tile-layout-coverage.test.ts` only.

### PR-B2 - Generic `<TileCartogram>` component + layout loader + ChartShell wrap

**Scope:** The reusable SVG primitive. Grain-agnostic. Mounted in the dev charts sandbox for verification (no production route yet).

**Files:**
- NEW `frontend/src/lib/charts/TileCartogram.svelte` - SVG hex grid (NOT maplibre). Props: `tiles: TileRow[]` (`unit_id`, `q`, `r`, `fill`, `opacity`, `label`, `tooltip_html`, `selected`), `legend`, `height`, `highlight_key`, `onSelect`, `onHover`. Reuse the existing party colour resolver + margin->opacity semantics + click-target behaviour from `StateAcMap.svelte`/`MapChoropleth.svelte` (import the shared helpers; do not duplicate).
- NEW `frontend/src/lib/view-models/election-tile-layout.ts` - loader that joins a winners array (`AcWinner[]` today; `PcWinner[]` later) + layout rows from `datasets/grapher/election_tile_layouts.json` into `TileRow[]`. Grain-agnostic on `unit_id`.
- Wrap render in existing `ChartShell` so download/copy-link/share come free (reuse `chart-shell/action-builders.ts` `buildCopyLinkActionSpec`, `buildViewDataActionSpec`).
- Mount a demo in `frontend/src/routes/DevChartsSandbox.svelte` (the existing `/dev/charts-sandbox` route) feeding S13 AC winners + the S13 layout.
- NEW `frontend/src/lib/charts/__tests__/tile-cartogram.test.ts` - join correctness, selection state, mode-label rendering, click parity with StateAcMap (one tile = one unit).

**Escalation:** dispatch **Jony** on tile sizing/label density if the sandbox render looks crowded.

**Acceptance gates (frugal):**
- [ ] G3 `bun run check` 0 errors.
- [ ] G4 `bun run test` filtered to `tile-cartogram.test.ts` + `election-tile-layout-coverage.test.ts`.
- [ ] G5 browser smoke (integrated Playwright, NOT remote): `/dev/charts-sandbox` renders the cartogram, no console `[error]`, no 404. Screenshot to confirm visual intent. Do not wait for any deploy.

### PR-B3 - `ElectionMap` wrapper with Map|Equal seats toggle (AC/state)

**Scope:** The geographic|cartogram toggle, mounted on the real state election page. Geographic arm = existing `StateAcMap`; seats arm = `TileCartogram`.

**Files:**
- NEW `frontend/src/lib/elections/ElectionMap.svelte` - segmented control `Map` | `Equal seats` (top-right, thumb-reachable). `Map` wraps `StateAcMap`; `Equal seats` wraps `TileCartogram` fed by the layout loader. Preserve the selected constituency across toggle. Persist mode to URL `?view=geo|hex` via the existing `frontend/src/lib/url.ts` grammar. Legend line "Each tile = one seat" on the hex arm.
- EDIT `frontend/src/routes/StateElection.svelte` - this is currently a thin permalink/card page (ADR-0023); mount `ElectionMap` to make it the real state election-result page. Keep the existing breadcrumb/CTAs; add the map+toggle as the primary surface. Feed it `loadStateAcWinners(event, state_code)`.
- NEW `frontend/e2e/elections-atlas.spec.ts` (dedicated spec per Section 0.3, tag `@elections`) - smoke `/s/maharashtra/elections/<event>`: both modes render, toggle persists to URL, selecting a unit navigates to `/s/maharashtra/ac/<ac>`.

**Escalation:** **Jony** on default mode + toggle affordance copy.

**Acceptance gates (frugal):**
- [ ] G3 `bun run check` 0 errors.
- [ ] G4 `bun run test` filtered to the touched view-model/component tests.
- [ ] G5 integrated Playwright `elections-atlas.spec.ts` green; manual browser smoke of `/s/maharashtra/elections/<event>` + one cross-route (`/s/maharashtra`) for no-regression. No remote deploy wait.

### PR-B4 - National atlas route + INDIA_PC + national PC loader (ships dark, lights up after PR-A4)

**Scope:** The one new route + the one `sources.ts` touch. Renders PC geography/cartogram nationally. If PC results (PR-A4) are not yet in the bundle, show a "results pending" empty state - the route still ships.

**Files:**
- EDIT `frontend/src/main.ts` - add route `/t/elections/:event` -> a new `frontend/src/routes/NationalElectionsAtlas.svelte`.
- NEW `frontend/src/routes/NationalElectionsAtlas.svelte` - national PC `ElectionMap` (Map arm = a national PC choropleth over `INDIA_PC`; Equal seats arm = the national PC `TileCartogram` from PR-B1). Tapping a state drills to `/lab/:state/:event` (or `/s/:state/elections/:event`). Seat-total bar across the top.
- EDIT `frontend/src/lib/maplibre/sources.ts` - **APPEND-ONLY** `export const INDIA_PC: BoundaryEntry = { id: "india-pc", label: "India - Parliamentary Constituencies (2024 delimitation)", geojson_local_path: "boundaries/in/pc/delim=2024/all.geojson", geojson_url: "<upstream>", join_property: "ls_seat_code" };`. Coerce `ls_seat_code` to int on join (it is stringified in the GeoJSON) - follow the existing numeric-coercion path in `MapChoropleth` (`keys_are_numeric`/`to-number`). **Rebase onto origin/main immediately before; on conflict take theirs + re-append (Section 0.3).**
- NEW `frontend/src/lib/view-models/national-elections.ts` - `loadNationalPcWinners(event)` mirroring `loadStateAcWinners` but cross-state: `WHERE indicator_id='pc-winner-party-id' AND entity_id LIKE 'IN-PC-%'`, joined to `dim_pcs` + `dim_parties`. Must degrade gracefully (empty -> "results pending") when PC data absent.
- EDIT `frontend/e2e/elections-atlas.spec.ts` - add `/t/elections/<event>` smoke (boundary renders; pending-state OR winners depending on data presence).

**Escalation:** dispatch **Gregor** on the national loader contract + the "dark until data" degradation shape. Apply verdict.

**Acceptance gates (frugal):**
- [ ] G3 `bun run check` 0 errors.
- [ ] G4 `bun run test` filtered to `national-elections` tests.
- [ ] G5 integrated Playwright: `/t/elections/<event>` renders PC boundary + either winners or pending-state; tap-state drills; no console error/404. No remote deploy wait.
- [ ] Verify `sources.ts` diff is a pure append (no edits to `STATE_AC` / topojson path) via `git diff`.

### PR-B5 - Cross-year E1: swing arrows on seat-composition bars

**Scope:** Add per-party swing arrows (delta vs previous election) to the EXISTING seat-composition trend. Cheapest cross-year signal; default-on.

**Files:**
- EDIT `frontend/src/lib/ElectionSeatsTrend.svelte` + `frontend/src/lib/charts/StackedTrendV2.svelte` (or its model) - compute per-party delta between consecutive events and render a small up/down arrow + number on each bar segment.
- EDIT the relevant `frontend/src/lib/view-models/election-seats-trend.ts` to expose deltas.
- Tests: extend the existing stacked-trend tests for the delta computation.

**Escalation:** **Jony** on arrow legibility.

**Acceptance gates:** G3 `bun run check`; G4 filtered vitest; G5 browser smoke of a state page showing the trend.

### PR-B6 - Cross-year E2: snapping time-slider on the map/cartogram

**Scope:** A slider that scrubs the constituency map/cartogram across consecutive SAME-GRAIN elections, recolouring tiles. SNAPS to election years - no interpolation, no autoplay.

**Files:**
- NEW `frontend/src/lib/elections/ElectionTimeSlider.svelte` - discrete stops = the available events for that state/grain (from `election-events.ts` `listEventsForState`). On change, reload winners for that event and recolour `ElectionMap`. Persist to URL (the event is already in the route; slider just changes it).
- EDIT `ElectionMap.svelte` / `StateElection.svelte` to host the slider.
- Tests: slider stop derivation (snaps to real events only), recolour on change.

**Escalation:** **Jony** ("snapping behaviour + no-autoplay confirmation").

**Acceptance gates:** G3; G4 filtered; G5 browser smoke - drag slider, confirm recolour + URL event change, no interpolation.

### PR-B7 - Cross-year E3: opt-in 2-election sankey (capped)

**Scope:** A labelled "Flow (beta)" opt-in view for EXACTLY two adjacent same-grain elections, top-6 parties + merged "Others". Reuse the existing `SwingSankey.svelte` GEOMETRY pattern (losers left / gainers right; NOT d3-sankey). Honesty note: seat deltas, not voter-panel tracking.

**Files:**
- NEW `frontend/src/lib/elections/SeatFlowSankey.svelte` (or adapt `SwingSankey.svelte`) - constrained to 2 events, top-6 + Others cap, with the provenance honesty banner via ChartShell.
- Wire an opt-in "Flow (beta)" toggle on the election page (collapsed by default).
- Tests: party-cap logic, 2-event guard (refuse >2), Others bucketing.

**Escalation:** **Jony** ("does the capped flow read honestly, or should it be deferred?"). If Jony says defer, COLLAPSE this row with rationale rather than ship an unreadable chart.

**Acceptance gates:** G3; G4 filtered; G5 browser smoke of the opt-in flow.

### PR-B8 - Filter rail F1/F2/F3 (party / margin band / colour-by) - state level

**Scope:** The indian_mlas-style filters, on the state constituency map. Left rail (desktop) / bottom sheet (mobile). Modifiers on a fully-populated default view; serialize to URL per the PR-0 grammar.

**Files:**
- NEW `frontend/src/lib/elections/ElectionFilterRail.svelte` - F1 party multi-select chips (colour+name) `?party=`; F2 margin band segmented `All`/`Close (<2 pts)`/`Landslide (>20 pts)` `?margin=`; F3 "Colour by" dropdown `Winner`/`Margin`/`Turnout`/`Age of winner` `?mode=`. One reset affordance (the active-filter count chip).
- EDIT `ElectionMap.svelte` - recolour the SAME choropleth/cartogram based on `mode`; dim non-matching units based on `party`/`margin`. NO bespoke per-filter widget.
- EDIT `frontend/src/lib/url.ts` - add the filter params to the URL grammar (typed).
- Reuse `frontend/src/lib/explore/presets.ts` margin/party query logic and `CandidateBio` (`age`/`sex`/`education`) for `mode=age` recolour.
- Tests: URL round-trip (params <-> state), recolour-by-mode, dim-by-filter.

**Escalation:** dispatch **Gregor** (URL grammar as a versionable contract) AND **Max** ("Does `dim_persons` age coverage support `mode=age` for all states, or must the option be hidden where coverage is absent?"). Apply both verdicts; if age coverage is partial, gate the `age` option per-state on coverage.

**Acceptance gates:** G3 `bun run check`; G4 filtered vitest (URL + recolour tests); G5 browser smoke - apply each filter on `/s/maharashtra/elections/<event>`, confirm URL reflects state and a shared URL reproduces the screen.

### PR-B9 - Wire filters at national level

**Scope:** Bring the PR-B8 filter rail to `/t/elections/:event` (PC grain). Needs PC data (PR-A4) to be meaningful.

**Files:**
- EDIT `frontend/src/routes/NationalElectionsAtlas.svelte` - mount `ElectionFilterRail`; recolour the national PC map/cartogram; `mode=age` uses PC-candidate bio coverage.
- EDIT `national-elections.ts` loader to accept filter params.
- Tests: national URL round-trip + recolour.

**Escalation:** **Gregor** on cross-state filter performance (all-India PC recolour must stay static-bundle-friendly - no server compute, Holy Law #1).

**Acceptance gates:** G3; G4 filtered; G5 browser smoke - filters on `/t/elections/<event>` with live PC data; shared URL reproduces screen.

---

## Section 2 - Cross-cutting notes for executing agents

- **Frugality:** never run a full pytest or full vitest suite for a row scoped to the other runtime. Backend rows run targeted `pytest` with `$env:PYTHONPATH="$PWD\backend"`. Frontend rows run `bun run check` + targeted `bun run test` + ONE integrated Playwright smoke. Never wait for GitHub Pages deploy.
- **Multi-worktree venv shadow (repo lesson):** always `$env:PYTHONPATH="$PWD\backend"` before pytest in a worker worktree, else you import stale master code.
- **2-commit-then-squash + clean F5 merge:** structural commit, then a `_pending_ -> #NNN` stamp commit, squash on merge. Never park a worktree on `main`.
- **No `[DEBUG]` left; no hardcoded taxonomy; provenance FK on every new obs row; docs updated in the same PR; lockfiles in sync if `package.json` touched.** (CLAUDE.md s9 DoD.)
- **If a row's contract turns out wrong mid-execution,** consult the named escalation agent, and if the fix changes THIS plan's contract, update this plan-doc's row + Status Reckoner in the same PR and note it - do not silently diverge.

## Section 3 - References

- [CLAUDE.md](../CLAUDE.md) Holy Laws #1 (static-first), #3 (contracts before logic), #5 (structural fixes), #9 (provenance), #10 (tests ship with feature).
- [ADR-0023](../docs/architecture/decisions/0023-election-event-identity-per-place.md) election event identity per place (lok_sabha kept separate from assembly).
- [ADR-0044](../docs/architecture/decisions/0044-grain-over-entity.md) grain over entity.
- [ADR-0045](../docs/architecture/decisions/0045-grapher-catalogue-split.md) grapher catalogue split (render data is frontend-owned).
- [ADR-0046](../docs/architecture/decisions/0046-pre-flight-ingest-gate-contract.md) pre-flight-ingest gate.
- [TODO/_TEMPLATE-ingest-handover.md](_TEMPLATE-ingest-handover.md) ingest discipline.
- [docs/architecture/data/elections-indicators.md](../docs/architecture/data/elections-indicators.md) AC indicator catalogue.
- [docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md) renderer doctrine.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) closure procedure.
