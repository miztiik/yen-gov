# Home-page citizen-experience rebuild: full-bleed map, topic-grid front door, winning-party copy, indicator-rotated default theme

**Last Updated**: 2026-06-11
**Level**: 3 (3-4 frontend files + 2 doc files; cross-cutting because Home is the canonical landing surface and the theme/copy seam is shared with state pages)
**Authority spine**: Jony + Citizen (UX, URL grammar, copy), Hans + Max (default-theme indicator selection + "winning party" wording), Fowler (deletion discipline for the dead "Available / Other states" lists, retired strings). Gregor not in scope (no schema bump, no contract). Andre not in scope (no LLM surface). Backend/python not touched.
**Status**: READY-FOR-DISPATCH. Wave A (PR-0 receipts) can run immediately; Wave B (PR-1) ships ahead of Waves C + D because copy is independent. Waves C and D are file-disjoint and may run in parallel sub-worktrees per user-memory `Autonomous 16-PR plan orchestration` doctrine.

---

## Preamble - binding doctrine the plan cannot re-litigate

This plan is the engineering response to one user-named pain surfaced 2026-06-11:

> "The home page is showing all the states. Reduce the load. Or reimagine: describe what this app is and give them options. Reduce the long list of states. 'leading party' should be 'winning party'. Find out if Lakshadweep was delivered. There is empty space on the left rail / right - use the full space and reflow on mobile. The choropleth on the home page should colour based on some indicator (probably random) instead of just elections."

Five concerns. The plan splits them into five PR-rows on file-disjoint surfaces so each row is reviewable in isolation. PR-0 retires the Lakshadweep concern with a no-op receipt (work was already delivered by PR #788 + PR #455 - confirmed below). The other four rows are the actual engineering work.

Binding documents (read these before any PR):

- [CLAUDE.md](../CLAUDE.md) - engineering contract; section 0a authority table; section 6 correction levels; section 8 git hygiene; section 13 UI verification (mandatory for any frontend runtime change); section 0 a11y non-goal.
- [docs/concepts/citizen-first.md](../docs/concepts/citizen-first.md) - question-first ordering; Citizen bookends every loop.
- [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md) - The One Rule; OWID-precedent breaks ties on UX questions.
- [docs/architecture/frontend/overview.md](../docs/architecture/frontend/overview.md) - "Default landing is the Citizen path: India choropleth at `#/`" - this plan modifies that landing.
- [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md) - choropleth + theme dispatch reference.
- [TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md](IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md) - section "Deferred to follow-on PRs" item #3 explicitly mandates "Default Home map theme -> NOT elections. A featured social-welfare or coverage indicator. User-mandated doctrine." This plan closes that deferred item.

Prior persona rulings that bind this plan (do not re-debate):

- **Hans + Max (data shape, 2026-05-26 to 2026-06-10)**: the canonical indicator catalogue at `datasets/taxonomy/indicators.json` and the per-CSV variable header `datasets/data/variables.csv` already say "Winning party" (3 rows, ids `ac-winner-party-id`, `pc-winner-party-id`, `winning-party-id`). The UI string "leading party" is a stale frontend literal that lags the taxonomy. No data-shape question; this is a frontend copy sweep.
- **Jony + Citizen (UX, 2026-05-13 IA-RESET P5 close)**: "elections are one of many indicators; social welfare should be the first-class citizen." Recorded in ADR-0022 doctrine and `docs/concepts/schema-is-the-design-system.md`. Default home theme has been documented to be non-elections since 2026-05-13; landing slipped to "P5 follow-on" and never shipped. PR-2 ships it.
- **Fowler (engineering craft, 2026-06-10)**: deletion-first. The current `available` + `stub` sections on Home enumerate all 36 states (alphabetical) AND fall back to a "no data" pile that is dead code today (every state has data via the 20 wired national indicators - `has_national_indicator` is always TRUE). Delete both sections; the LeftRail `StatePill` is already the canonical state picker.

---

## Scope-change ledger

Per [CLAUDE.md section 10](../CLAUDE.md), any agent that proposes to silently downgrade a user-named source, instruction, or recommended-default MUST add a row here before merging the row's PR. Capture INTENT in neutral prose; never paste user chat verbatim.

| Row | Date | Intent (what changed, why, what it overrode) | signoff |
|---|---|---|---|
| (none) | - | No scope changes yet. | - |

---

## Section 0 - Operating contract

### 0.1 Strategy (one sentence)

Make the Home page lean (kill the dead state lists), full-bleed (no 192px desktop gutter), citizen-first (greeting + topic grid above the map), correctly-worded ("winning party" everywhere the UI says "leading party"), and non-election by default (rotate among curated national indicators on first paint; keep the election theme as one explicit picker option).

### 0.2 Hard-coded scope

**IN scope**:
- `frontend/src/routes/Home.svelte` (the landing surface)
- `frontend/src/lib/home-theme.ts` + its `.test.ts` (default-theme logic + copy constants)
- `frontend/src/routes/ElectionsFirehose.svelte` (1 table header)
- `frontend/src/routes/NationalElection.svelte` (1 visible heading)
- `frontend/e2e/golden-path.spec.ts` (1 regex assertion to keep e2e green)
- `docs/architecture/frontend/overview.md` (4 doc-copy lines)
- `docs/architecture/frontend/map.md` (1 doc-copy line)
- `docs/concepts/citizen-first.md` cross-link only (no body change)

**OUT of scope** (each is its own future plan-doc if needed):
- Backend python, schema, taxonomy, parties.csv, election-quality work (in-flight per #897-#915; do NOT collide).
- Per-state pages (`/s/<state>`) layout - this plan is Home-only.
- `LeftRail.svelte` / `StatePill.svelte` - already canonical for state navigation; reuse as-is, no edit.
- HomeElectionsRail (PR-W4d #892, shipped 2026-06-10) - KEEP as-is; it is the right hook for the elections-curious citizen.
- New chart types or renderers - PR-3 reuses `IndicatorChoropleth` (height knob already exists).
- New indicator ingest - PR-2 picks from the 20 already-wired national indicators (no new data work).
- The 3 backend test strings `ac-leading-party-id` / `pc-leading-party-id` / `state-leading-party-id` in `backend/tests/test_party_id_fk_closure.py` - those are legacy indicator-id literals that may already be dead; sweep is a backend concern, not frontend copy. File a follow-on if Tier-A still references them after PR-1 lands.

### 0.3 ESCALATE triggers (do NOT proceed without user sign-off)

- **Level-5 schema/data-shape change**: this plan touches NONE. If a row reveals a needed schema bump (e.g. catalogue v1.3 to mark `default_home_theme`), STOP and surface; do not bump silently.
- **STOP-AND-SURFACE on user-named-source downgrade** ([CLAUDE.md section 10](../CLAUDE.md)): the user named "Lakshadweep" explicitly. PR-0 verifies it was already delivered; if PR-0 discovers Lakshadweep is NOT actually rendering on Home for any reason (broken JOIN, missing election event, etc.), STOP and surface - do NOT silently rescope.
- **STOP if the indicator-rotation pool collapses** (PR-2): if `nationalIndicators(catalogue).length < 3` at run time, fall back to election theme silently AND surface a one-line warning in the plan-doc closure - do not invent a non-catalogue default.
- **STOP at any persona conflict** (PR-3): if Jony's full-bleed verdict collides with a Citizen complaint that the map "loses its frame," dispatch a debate row; do not pick one and proceed.

### 0.4 Deciding-authority dispatch (per [CLAUDE.md section 0a](../CLAUDE.md))

| Question | Authority | Verdict baked in this plan |
|---|---|---|
| Should "leading party" become "winning party"? | Hans + Max | YES. The canonical taxonomy already says "Winning party" (`datasets/taxonomy/indicators.json` lines 240/575/1040, `datasets/data/variables.csv` rows 14/139/175). UI is the lagger. |
| Should "ruling party" or "majority party" be considered instead? | Hans | NO. "Ruling party" conflates the elected-legislature winner with the executive coalition (which may include allies post-election). "Majority party" is misleading in fragmented results (TN 2026: TVK led with 108 seats but no majority at 117). The canonical taxonomy's "Winning party" = the party with the most seats won, which is what the map and tooltips actually depict. |
| Default Home theme: election or indicator? | Hans + Jony (UX) | NON-ELECTION. Closes IA-RESET P5 deferred item #3. Election stays in the picker as an explicit choice. |
| Indicator-rotation strategy: random / sticky / deterministic? | Jony + Citizen | DETERMINISTIC-BY-DAY (day-of-year mod N over the curated pool). User said "probably random" - deterministic-by-day is the OWID-precedent shape (Our World in Data picks a "chart of the day" on the home tile; shareable URLs stay stable within a day; refresh does not whiplash). Election theme survives as `?theme=election`. Sticky bookmark via `?theme=indicator/<id>`. |
| Indicator-pool selection (which subset of the 20 wired national indicators?) | Hans + Max | CURATED-5 in v0, expand later. The pool is `outstanding_debt_pct_gsdp` (fiscal flagship), `gdp_inr_crore` (economy headline), `cpi_inflation_pct` (prices headline), `india_ghg_emissions_mtco2e_by_sector` (environment), `pashu_aadhaar_count_cattle` (agriculture, citizen-near). One per topic family; OWID-style "topic-coverage" rotation. Curation lives as a `CURATED_DEFAULT_THEMES` constant in `home-theme.ts` with a doc comment naming the authority; expansion is a 1-row edit. |
| Full-bleed map vs capped map? | Jony | FULL-BLEED on the map section only. Container `max-w-screen-2xl mx-auto p-6` stays for the topic grid + rail + footer; the map breaks out via a nested `<section class="-mx-6">` shim (negative margin equals the container padding). Mobile (< md): no break-out; map stays inline. |
| Replace the "Available" states list entirely or trim it? | Fowler + Jony | REPLACE with a 6-card topic-grid front door. The flat list of 36 alphabetical states is noise (a) the map already shows them, (b) the LeftRail StatePill is the canonical picker, (c) the topic grid surfaces the actual product proposition ("Indian civic data by topic"). The "Other states (no data yet)" branch is dead code today (`has_national_indicator` is always TRUE) - delete. |
| Where does the topic grid get its data? | Hans + Max | From `fetchTopicCatalogue()` (already loaded on Home). Use existing `CatalogueTopic[]` with `featured: true` filter, plus a final "Elections" tile that links to `/t/elections` (Elections is its own first-class section group per ADR-0022, not a topic with `featured` flag). 6 cards: 5 featured topics + Elections. |
| Per-row PR shape (one row = one PR = one branch)? | Fowler | YES. Five rows, five PRs, five squash-merges. Master parks on `scratch-master-parking-2026-06-10`; sub-worktrees per parallel-friendly row (D and C are file-disjoint). |

### 0.5 What "done" means for this plan

All 5 PR-rows merged to `main` with a green 5-gate DoD ([docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md)), the Home page rendering verifiably (a) without the alphabetical states list, (b) with a topic-grid front door, (c) with a non-election default theme that rotates by day, (d) with "winning party" wherever it previously said "leading party", and (e) full-bleed map on desktop / responsive on mobile. Closure follows [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md): durable doctrine lifted into `docs/architecture/frontend/overview.md` + `docs/architecture/frontend/map.md`; plan-doc archived under `docs/archive/plans/`.

---

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner (section 1) and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on. Use the `Jony` agent for layout / copy / theme rulings inside subagent debates; the `Fowler` agent for deletion-discipline calls; `Hans` + `Max` for any data-shape question that surfaces mid-row.
2. **One row = one PR = one branch.** Park master on `scratch-master-parking-2026-06-10` so no worktree owns `main` (clean `gh pr merge`). Author per [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md): 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify (`open_browser_page` + `read_page` + `screenshot_page`) for every frontend runtime change per [CLAUDE.md section 13](../CLAUDE.md). PR-0 is a doc-only / receipts row; skip the browser smoke for PR-0 only.
3. **Ship loop, non-stop.** Keep PRs in flight; never idle. As soon as one row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next row. Pre-existing unrelated test failures (the chronic backend `pipeline-pytest` red on main, the chronic frontend `citizen-site-e2e` red noted in user-memory 2026-06-10) are not gating - document the baseline, do not block. The cosmetic `'main' is already used by worktree` warning from `gh pr merge` when any worktree holds `main` is expected per user-memory CLAUDE.md section 8 - the manual `git push origin --delete <branch>` follow-up is mandatory, not optional.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked. PR-1 updates the existing `home-theme.test.ts` (3 string assertions) + the existing `golden-path.spec.ts` regex (1 line). PR-2 adds 4-6 new vitest cases for the day-of-year rotation logic. PR-3 adds 2-3 vitest cases for the topic-grid filter + 1 Playwright assertion that the alphabetical states list is GONE. PR-4 is doc-only (no tests).
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call mid-flight, run the authority personas in DEBATE (not parallel review); bake the single written verdict into the row commit message + into the plan-doc Scope-change ledger if it deviates from section 0.4. Do not parallelise debate.
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into `Explore` subagents (`runSubagent` agentName="Explore") so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch (`git push origin --delete <branch>` if `gh pr merge --delete-branch` failed cosmetically), prune `: gone` local branches (`git fetch --prune` then `git branch -vv | grep ': gone' | awk '{print $1}' | xargs -n1 git branch -D`), remove `.tmp_*`, distill durable lessons (PR-2 rotation logic and PR-3 layout shim are the candidates).
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger from section 0.3 fires, an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per [CLAUDE.md section 10](../CLAUDE.md)), or an audit chain exceeds depth 3 (the loop is lossy - escalate with Path A/B/C options, do not ship a 4th audit). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. PR-0 is a no-op row and carries a receipt (the PR #788 + PR #455 merge SHAs cited inline + the on-disk Lakshadweep CSV path). Archive the plan-doc with a per-row distillation map per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md). Lift the day-of-year rotation rule, the curated-5 indicator pool, and the full-bleed shim into `docs/architecture/frontend/map.md` and `docs/architecture/frontend/overview.md` respectively.

---

## Section 1 - Status Reckoner

PR-rows. Status starts `[ ] PENDING`, flips to `[x] DONE` with the merged PR number.

| Row | Title | Status | PR | Effort | Depends on |
|---|---|---|---|---|---|
| PR-0 | Lakshadweep delivery receipt + close-out (audit-only, no code) | `[x] DONE` (Lakshadweep oracle 5/5 green; orchestrator-authored bootstrap) | (this PR) | XS (~30 min) | (none) |
| PR-1 | Wording sweep: "leading party" -> "winning party" (frontend + e2e + docs) | `[ ] PENDING` | - | S (~1h) | (none) |
| PR-2 | Default Home theme: deterministic day-of-year rotation over curated-5 indicators | `[ ] PENDING` | - | M (~2h) | PR-1 (avoid copy-collision in `home-theme.ts`) |
| PR-3 | Home layout rebuild: full-bleed map + topic-grid front door + delete "Available" / "Other states" sections | `[ ] PENDING` | - | M (~2h) | PR-1 (Home.svelte string drift); file-disjoint vs PR-2 inner logic; can run in parallel sub-worktree after PR-1 merges |
| PR-4 | Doc lift: distill the deterministic-rotation rule + curated-5 pool + full-bleed shim into `docs/architecture/frontend/` | `[ ] PENDING` | - | XS (~30 min) | PR-2 + PR-3 merged |

**Wave shape**:
- **Wave A** (parallel-safe, no deps): PR-0 + PR-1 dispatch immediately. PR-0 is doc/receipt-only; PR-1 is a narrow copy sweep.
- **Wave B** (PR-1 merged): PR-2 + PR-3 dispatch in two parallel sub-worktrees. They are file-disjoint (PR-2 = `home-theme.ts` + tests + tiny `Home.svelte` import; PR-3 = `Home.svelte` layout + topic-grid + state-list deletion).
- **Wave C** (PR-2 + PR-3 merged): PR-4 ships docs.

---

## Section 2 - Per-row spec

### Row PR-0: Lakshadweep delivery receipt + close-out

**Scope.** Audit-only PR that confirms the user's Lakshadweep concern is closed by prior merged work. No code change. The PR body is a 1-screen receipt with the 2 merge SHAs, the on-disk CSV path, and the test file that locks the contract. This is the canonical place future agents will find the answer when the user re-asks. The PR-body itself stays as the durable record (a `docs/` file is NOT warranted - this is a receipt, not doctrine).

**Files touched**: ZERO code. Add ONE line to this plan-doc's Status Reckoner with the merge SHA.

**Acceptance gates**:
1. PR body cites PR #788 (topojson `keep-shapes` fix; smoke at `frontend/src/contracts/topojson-island-render.test.ts`) and PR #455 (boundary-rip-and-replace D.1.A; retired `frontend/src/lib/lakshadweep.ts` extractor + chip-strip).
2. PR body cites the on-disk election CSV at `datasets/data/datapoints/electoral/lakshadweep_election_results.csv`, the LGD entry `lgd_district_id=553` slug `lakshadweep-district`, and the `state=lakshadweep` election partition.
3. PR body includes a 1-line `Set-Location` + `Test-Path` proof from a fresh checkout that the CSV is present at HEAD.
4. The receipt explicitly closes the question "find out if that plan has been delivered or not" with: **YES, DELIVERED 2026-06.**

**Oracle (the one load-bearing check)**: 

```
git -C <repo> log --oneline --all -- frontend/src/contracts/topojson-island-render.test.ts | head -1
```

must return a SHA that traces to a merged PR (#788), AND

```
Test-Path datasets/data/datapoints/electoral/lakshadweep_election_results.csv
```

must return `True`. If either fails, ESCALATE (Lakshadweep is NOT delivered; rescope this plan to include the data ingest).

**Effort**: XS. Author the PR body, run the two oracle commands, paste output. No browser smoke (doc-only PR, [CLAUDE.md section 13](../CLAUDE.md) carve-out).

#### PR-0 receipt - executed 2026-06-11 (orchestrator)

Bootstrap PR: combines plan-doc commit + Lakshadweep delivery audit. Per the multi-PR pattern in user-memory `Autonomous 16-PR plan orchestration`, the orchestrator authors the bootstrap row directly; PR-1 through PR-4 dispatch to stateless subagents.

**Oracle output** (run from `C:\Users\kumarsnaveen\Downloads\NawiN\personal\gitrepos\yen-gov` at SHA `741925321`):

| # | Check | Result |
|---|---|---|
| 1 | `Test-Path frontend/src/contracts/topojson-island-render.test.ts` | `True` |
| 2 | `Test-Path datasets/data/datapoints/electoral/lakshadweep_election_results.csv` | `True` |
| 3 | CSV row count | `144` rows; header `entity_id,year,period_label,period_seq,indicator_id,value_numeric,value_text,source_id,derivation` |
| 4 | `git log --oneline -- frontend/src/contracts/topojson-island-render.test.ts` | `a018c75ed F4 d3-geo + topojson island-render smoke (section 21.11 frozen requirement a) (#788)` |
| 5 | `frontend/src/lib/lakshadweep.ts` retired? | `False` (file absent - retired per D.1.A in PR #455) |
| 5 | `frontend/src/lib/lakshadweep.test.ts` retired? | `False` (file absent) |
| 5 | `frontend/src/lib/UnmappedRegionChips.svelte` retired? | `False` (file absent) |

**Verdict: DELIVERED 2026-06.** Lakshadweep renders at true geographic position on the Home India choropleth and on every other map surface (via `boundaries/in/{states,districts}/all.topojson` with `keep-shapes` mapshaper flag). Election data on disk: 144 long-format rows under [datasets/data/datapoints/electoral/lakshadweep_election_results.csv](../datasets/data/datapoints/electoral/lakshadweep_election_results.csv). The 4 island geographies (Lakshadweep state + Lakshadweep district `lgd_district_id=553` + Andaman & Nicobar + Daman & Diu islands) are locked by the smoke test at [frontend/src/contracts/topojson-island-render.test.ts](../frontend/src/contracts/topojson-island-render.test.ts) (14 assertions: 4 islands x [present + area + bounds + projected-path] + 1 corpus-shape).

**Delivering PRs**:
- **PR #788** (merged 2026-06-04 via SHA `a018c75ed`) - topojson island-render smoke + `keep-shapes` mapshaper fix; closed the user-named requirement "Lakshadweep + A&N must actually draw from `all.topojson`" attached to [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) row F4.
- **PR #455** (boundary-rip-and-replace D.1.A, see [docs/archive/plans/20260529-boundary-rip-and-replace-plan.md](../docs/archive/plans/20260529-boundary-rip-and-replace-plan.md)) - retired the per-state `lakshadweep.ts` polygon extractor + the chip-strip subsystem + ADR-0029 + the Playwright chip assertions. All UTs now render at true geographic location.

**Closing the user question** ("can you find out if that plan has been delivered or not?"): **YES.** No follow-on engineering needed. PR-0 ships as the durable receipt; future agents grep this file to find the answer.

---

### Row PR-1: Wording sweep "leading party" -> "winning party"

**Scope.** Replace user-visible "leading party" / "Leading party" strings with "winning party" / "Winning party" across the frontend. Citizen-facing copy only. Code comments and internal identifiers untouched (per implementation-discipline rule: do not refactor what is not asked).

**Files touched** (exhaustive list - if grep finds anything new, ESCALATE):

1. `frontend/src/lib/home-theme.ts` lines 44-45:
   - `ELECTION_LABEL = "Leading party"` -> `ELECTION_LABEL = "Winning party"`
   - `ELECTION_CAPTION = "leading party by state"` -> `ELECTION_CAPTION = "winning party by state"`
2. `frontend/src/lib/home-theme.test.ts` (3 string assertions):
   - The "returns 'leading party by state' for election" test name + the `.toBe("leading party by state")` literal flip to "winning party by state".
3. `frontend/src/routes/ElectionsFirehose.svelte` line 530 (visible table header):
   - `<th class="px-3 py-2">Leading party</th>` -> `<th class="px-3 py-2">Winning party</th>`
   - Lines 19 + 296 are code comments; leave alone per implementation-discipline rule.
4. `frontend/src/routes/NationalElection.svelte` line 466 (visible heading):
   - `Leading party by state` -> `Winning party by state`
   - Line 180 is a code comment; leave alone.
5. `frontend/e2e/golden-path.spec.ts` line 37 (regex assertion):
   - `name: /leading party by state/i` -> `name: /winning party by state/i`
6. `docs/architecture/frontend/overview.md` lines 31, 104:
   - Line 31: `"showing the leading party and a link"` -> `"showing the winning party and a link"`
   - Line 104: `"party hue per leading-party tally"` -> `"party hue per winning-party tally"`
   - Line 370 mentions "leading party has cleared half the chamber" - leave alone; that is about MAJORITY signalling, semantically distinct from winner-of-most-seats. Do NOT touch.
7. `docs/architecture/frontend/map.md` line 115:
   - `"colors each by leading party"` -> `"colors each by winning party"`

**Out of scope for PR-1** (file in PR-4 follow-up or separate plan):
- `backend/tests/test_party_id_fk_closure.py` lines 231-237 reference legacy ids `ac-leading-party-id` / `pc-leading-party-id` / `state-leading-party-id`. These are LEGACY indicator-id literals; the canonical taxonomy now uses `*-winner-party-id`. Verify whether the legacy ids are still emitted anywhere (grep `datasets/data/variables.csv` shows only the `*-winner-party-id` form). If dead, retire the fixture array in a separate Tier-A test row.
- `Home.svelte` line 29 inline comment - code comment, untouched per implementation-discipline rule.
- `IndiaMap.svelte` opening block comment - code comment, untouched.

**Acceptance gates**:
1. `cd frontend && bun test home-theme` green.
2. `cd frontend && bun run check` clean (svelte-check 0 errors).
3. `cd frontend && bun run build` clean.
4. Browser smoke per [CLAUDE.md section 13](../CLAUDE.md): `open_browser_page http://localhost:5173/` -> caption above the map reads "India - winning party by state". Console errors 0. Failed requests 0.
5. Browser smoke 2: `/t/elections/<latest-event>` -> ElectionsFirehose table header reads "Winning party".
6. `git grep -i "leading party" frontend/src docs/architecture` returns ONLY: (a) the `frontend/src/routes/NationalElection.svelte` line 180 comment if not edited, (b) the `home-theme.ts` line 4 file-header comment if not edited, (c) the `overview.md` line 370 MAJORITY-signalling sentence (explicitly out-of-scope per file list above). Any other hit ESCALATES.

**Oracle (the one load-bearing check)**: a fresh frontend build + the Playwright `golden-path.spec.ts` run end-to-end against `npm run dev` MUST be green; the spec asserts the new wording.

**Effort**: S. 7 files, ~14 line edits, 1 test flip, 1 Playwright assertion flip.

---

### Row PR-2: Default Home theme - deterministic day-of-year rotation over curated-5 indicators

**Scope.** Land the IA-RESET P5 deferred item #3: stop defaulting Home to the election theme. Default to one of 5 curated national-scope indicators, rotated by day-of-year so the same date yields the same default theme across all visitors (shareable, debuggable, not whiplash-y on refresh). Election theme survives as the explicit `?theme=election` choice.

**Files touched**:

1. `frontend/src/lib/home-theme.ts`:
   - Add `const CURATED_DEFAULT_THEMES: readonly { id: string; topic_id: string }[]` - 5 entries (one per topic family, see section 0.4 verdict). Doc comment names Hans + Max as the authority and points to the catalogue rows that back each id.
   - Rewrite `defaultHomeTheme(catalogue)` body: if catalogue is null OR fewer than 3 of the curated 5 are present in the catalogue's national-scope indicators, fall back to `{ kind: "election" }`. Otherwise compute `idx = dayOfYear(now) % availableCount` and return `{ kind: "indicator", id: <curated_id_at_idx> }`. `dayOfYear` is a pure helper inside the file.
   - Keep the current file-header comment but update the "Default = { kind: 'election' }" sentence to describe the new behaviour. The "When/if a live event lands, hook the default-theme logic here" hook stays (future work).
2. `frontend/src/lib/home-theme.test.ts`:
   - Update the existing `defaultHomeTheme is election today` test to assert the new rotation behaviour. Add fixture catalogue with all 5 curated indicators present; assert the function returns `{ kind: "indicator", id: <one-of-five> }` AND the same day-of-year deterministically returns the same id (call twice on a frozen `Date`; assert equality).
   - Add 3 new cases: (a) catalogue null -> election fallback, (b) only 2 of 5 curated indicators present -> election fallback, (c) day-of-year rotation cycles through all 5 over a year (sample at day 1, day 100, day 250, day 365; assert at least 3 distinct ids appear).
3. `frontend/src/routes/Home.svelte`:
   - One-line semantic change: `theme = state<HomeTheme>({ kind: "election" })` (line 53) -> initialize as `null` and let the `sync_theme_from_url()` -> `defaultHomeTheme(catalogue)` chain set it once the catalogue loads. This avoids a 200ms flash of "leading party / Winning party" before the rotation kicks in. Guard the `{#if theme}` so the map section shows a skeleton during the catalogue-load window (reuse the existing `home-elections-rail-loading` skeleton pattern).
   - No layout change in this PR (that is PR-3).

**Acceptance gates**:
1. `cd frontend && bun test home-theme` green; new 4+ cases visible in the test output.
2. `cd frontend && bun run check` clean.
3. `cd frontend && bun run build` clean.
4. Browser smoke: `open_browser_page http://localhost:5173/` -> caption reads the curated indicator title for today's day-of-year (e.g. "India - Outstanding liabilities (% of GSDP)"), NOT "winning party by state". Console errors 0.
5. Browser smoke 2: `open_browser_page http://localhost:5173/?theme=election` -> election theme renders; caption reads "India - winning party by state" (the PR-1 wording).
6. Browser smoke 3: `open_browser_page http://localhost:5173/?theme=indicator/fiscal/outstanding_debt_pct_gsdp` -> sticky bookmark still works.
7. The theme picker `<select>` dropdown still lists all 21 themes (Election + 20 national indicators) grouped by topic.

**Oracle (the one load-bearing check)**: in vitest, freeze `Date` at two distinct days 100 days apart; assert `defaultHomeTheme(catalogue)` returns different `{ kind: "indicator", id }` shapes AND that re-calling on the same frozen day returns IDENTICAL output. This is the determinism contract.

**Effort**: M. ~80-line `home-theme.ts` edit; ~40-line test addition; 5-line `Home.svelte` skeleton-guard tweak.

---

### Row PR-3: Home layout rebuild - full-bleed map + topic-grid front door + delete state lists

**Scope.** Replace the "Available" + "Other states (no data yet)" sections with a topic-grid front door. Break the map out of the `max-w-screen-2xl` cap on desktop. Make mobile a single column (Tailwind responsive). Keep the HomeElectionsRail (PR-W4d #892) and the existing header.

**Files touched**:

1. `frontend/src/routes/Home.svelte`:
   - **Delete** the two `<section>` blocks for `available` states and `stub` states (the entire `{#if error} ... {:else if !states} ... {:else} ... {/if}` block at the bottom). With it, delete the `fetchStates`, `loadStates`, `available`, `stub`, `has_national_indicator`, `fallback_codes`, `states`, `states_taxonomy`, `error` reactivity. The map's per-state colouring is loaded internally by `IndiaMap.svelte` via its own `loadStates()` call (line 47 of `IndiaMap.svelte`); Home.svelte no longer needs them.
   - **Add** a `<section>` for the topic-grid front door, placed BETWEEN the header and the map. 6 cards (5 featured topics + Elections), rendered as a CSS grid `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3`. Each card: topic icon (if present), topic title (e.g. "Money & debt"), 1-line summary, `<a href={url.topic(topic.id)}>` link. Elections card hard-codes title="Elections", summary="Assembly + parliament results, party-by-party", href=`/t/elections`.
   - **Wrap** the map section in a desktop-only break-out shim: change `<section class="bg-white rounded-lg shadow-sm p-4 space-y-3">` to `<section class="bg-white rounded-lg shadow-sm p-4 space-y-3 md:-mx-6 lg:-mx-12">` (negative margin equals the container `p-6` on md and grows on lg). Verify the map's MapLibre / `IndicatorChoropleth` canvas re-flows to the new width via window resize observer (both already do).
   - **Refine** the header copy. Replace the current `<p>Indian civic data - fiscal capacity, energy, elections, and more, compared across states. Click a state to drill in.</p>` with a 2-sentence version that names the topic axis (per Citizen verdict: the home page must answer "what is this app?" in <10 seconds): "Open data on India's socio-economic and electoral landscape, organised by topic and compared across states. Pick a topic below, or open the map for state-by-state comparison." Keep the "What is this?" link to `/about`.
   - **Keep** HomeElectionsRail mounted BELOW the map (current position).

**Acceptance gates**:
1. `cd frontend && bun test` full vitest green.
2. `cd frontend && bun run check` clean.
3. `cd frontend && bun run build` clean.
4. Browser smoke 1 desktop (`open_browser_page http://localhost:5173/` at default viewport): (a) topic-grid renders 6 cards, (b) map section visually extends edge-to-edge OR at least beyond the topic-grid cap, (c) NO alphabetical states list anywhere on the page, (d) HomeElectionsRail still mounted below the map. Console errors 0.
5. Browser smoke 2 mobile (resize browser to 375px or use mobile emulation): (a) topic-grid stacks single-column, (b) map section flows inline (no negative margin overflow / horizontal scrollbar), (c) HomeElectionsRail single-column.
6. Playwright `golden-path.spec.ts` update: any assertion that depended on the "Available" / "Other states" headings or list items must be retired in the same PR. Replace with a positive assertion that the topic-grid renders 6 cards.
7. Visual regression: 1 desktop + 1 mobile screenshot pasted in the PR body (per [CLAUDE.md section 13](../CLAUDE.md) layout-sensitive carve-out).

**Oracle (the one load-bearing check)**: the Playwright assertion that counts topic-grid cards must equal exactly 6, AND a `page.locator("h2:has-text('Available')")` MUST be absent (`.count() === 0`). This locks the delete + the new structure simultaneously.

**Effort**: M. ~80-line `Home.svelte` net delete + ~60-line topic-grid addition; ~10-line Playwright spec update.

**Parallelism note**: PR-3 touches `Home.svelte` (top half). PR-2 also touches `Home.svelte` (the `theme` initialisation - bottom half of `<script>`). They are NOT file-disjoint. Run sequentially: PR-2 first, then PR-3. If a sub-worktree runs PR-3 in parallel, rebase against PR-2 merge before pushing; conflict surface is the `<script>` block.

---

### Row PR-4: Doc lift - distill the rotation rule + curated-5 pool + full-bleed shim

**Scope.** Pure doc PR. Lift the durable doctrine from PR-2 and PR-3 into the right `docs/` homes per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md). Plan-doc closure follows next session as a separate move-to-archive PR (not bundled here).

**Files touched**:

1. `docs/architecture/frontend/map.md`: add a "Default Home theme" subsection (1-2 paragraphs) describing the deterministic day-of-year rotation over the curated-5 national-scope indicators, the election-theme fallback path (catalogue null OR <3 curated present), and the sticky-bookmark `?theme=indicator/<id>` contract. Name Hans + Max as the curation authority; cross-link to `frontend/src/lib/home-theme.ts` CURATED_DEFAULT_THEMES.
2. `docs/architecture/frontend/overview.md`: update the "Default landing is the Citizen path" paragraph (line ~31) to describe the topic-grid front door + the full-bleed map + the absence of the old "Available" / "Other states" lists. Cross-link to `frontend/src/routes/Home.svelte`.
3. `docs/concepts/citizen-first.md` (no body change): add ONE "See also" cross-link to this plan-doc's archived path so the next agent finds the rationale.

**Acceptance gates**:
1. Markdown lints clean (ASCII-only per CLAUDE.md section 5; `-`, `->`, `>=`).
2. Cross-links resolve (no 404s in `docs/` build if one runs).
3. `git diff --stat` shows the 3 docs files and ONLY the 3 docs files.

**Oracle**: `grep -r "Available states" docs/architecture/frontend/` returns ZERO matches AFTER the PR lands (doc-text/old reality drift check).

**Effort**: XS. ~30 minutes.

---

## Section 3 - Post-merge closure ritual

After PR-4 merges:

1. **Archive plan-doc**: `git mv TODO/20260611-home-page-citizen-experience-plan.md docs/archive/plans/` in a closure PR. Append a "Closure" stanza enumerating PR-0 through PR-4 with their merge SHAs + a 1-line distillation pointer for each (PR-1 = "winning-party copy lift, no doctrine drift"; PR-2 = "rotation rule lifted to `frontend/map.md`"; PR-3 = "topic-grid + full-bleed lifted to `frontend/overview.md`"; PR-4 = "doc lift; this PR"; PR-0 = "Lakshadweep delivery receipt"). Update [docs/reference/decision-index.md](../docs/reference/decision-index.md) if any ADR-class decision was minted (none expected for this plan).
2. **Lessons memory**: if any of the rows surfaced a recurring agent trap, append to `/memories/lessons.md` per user-memory `lessons.md` discipline. Candidates: the `home-theme.ts` "deterministic-by-day rotation" pattern (reusable for state-page heroes), the `md:-mx-6` full-bleed shim (reusable for any cap-bound full-width section).
3. **Branch cleanup**: `git fetch --prune origin`; delete any `: gone` local tracking branches. Verify `git worktree list` shows no orphan worktrees for this plan's PRs.
4. **Browser final sweep**: `open_browser_page http://localhost:5173/` on the freshly-merged main; pass-or-fail screenshot in the closure PR body.

---

## Section 4 - What we are NOT doing in this plan (so the next plan-author sees the boundary)

- **No new indicator ingest.** PR-2 picks from the 20 already-wired national indicators; if Hans + Max want to expand the curated-5 pool to (say) education or health when those land, the expansion is a 1-line edit to `CURATED_DEFAULT_THEMES`. Net-new ingest follows its own plan-doc shape.
- **No state-page (`/s/<state>`) layout work.** This plan is Home-only. The state-page "hero composed only from featured catalogue entries" rule (IA-RESET P2 deferred item #4) is its own follow-on.
- **No election-quality / parties.csv / parity collisions.** PRs #897-#915 are pure backend; this plan is pure frontend. Zero overlap.
- **No accessibility / ARIA / WCAG work.** Project non-goal per [CLAUDE.md section 0](../CLAUDE.md). PR-3's topic-grid uses semantic `<a href>` per default; do not add `aria-*` attributes.
- **No a11y a11y descope re-debate.** Closed since 2026-05-12.
- **No router / URL grammar change.** The `?theme=` slot stays exactly as in IA-RESET P5; default value computed (PR-2) instead of literal.
- **No new dependencies.** PR-3 reuses Tailwind's existing grid classes; PR-2's `dayOfYear` is a 4-line pure helper. No `bun add` calls.

---

## See also

- [TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md](IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md) - the umbrella IA reset; this plan closes its P5 deferred item #3 and retires its alphabetical-states-list scaffolding.
- [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) - the umbrella Level-5 platform reset; PR #788 row F4 is the Lakshadweep receipt PR-0 cites.
- [TODO/20260610-electoral-data-quality-and-party-catalogue-plan.md](20260610-electoral-data-quality-and-party-catalogue-plan.md) - in-flight backend electoral-quality plan; this plan is DISJOINT from it (frontend-only).
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - the 5-gate Definition-of-Done every PR-row honours.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) - the closure ritual PR-4 + the archive-PR follow.
- [docs/how-to/handle-scope-change.md](../docs/how-to/handle-scope-change.md) - STOP-AND-SURFACE for the Lakshadweep ESCALATE trigger.
- [docs/architecture/frontend/overview.md](../docs/architecture/frontend/overview.md) - lifted into by PR-4.
- [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md) - lifted into by PR-4.
- [docs/concepts/citizen-first.md](../docs/concepts/citizen-first.md) - the question-first doctrine that drives section 0.4 verdicts.
- [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md) - The One Rule; OWID-precedent broke the rotation-strategy tie (deterministic-by-day over pure-random or sticky-default).
- [CLAUDE.md](../CLAUDE.md) - engineering contract; Holy Laws + section 0a + section 6 + section 8 + section 13.
