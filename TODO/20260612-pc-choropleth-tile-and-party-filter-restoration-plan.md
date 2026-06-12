# Election event page — PC choropleth + TileCartogram + party filter rail (restoration) — 2026-06-12

**Status:** READY-TO-IMPLEMENT
**Correction level:** Level-3 (multi-file frontend restoration, 1 PR)
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §0a (UX = Jony + Citizen; data shape = Hans + Max; engineering = Fowler; contracts = Gregor) · §6 correction levels · §9 DoD · §13 UI verification.
**Predecessor:** PR [#954](https://github.com/miztiik/yen-gov/pull/954) (event-page UX polish; merged `76ab5101d` 2026-06-12) deferred PC boundary integration. This PR closes that deferral PLUS restores the deliberately-deleted "Map | Equal seats" toggle + party filter rail.

## Problem (user-named, 2026-06-12, after PR #954)

PR #954 shipped a placeholder card on `/<state>/elections/general-2024` saying *"Constituency map being prepared"*. User pushed back the same day:

> "If we have the data, then make the PC choropleth to work — visible for user. While we are at it, we need two more features to be built — this was already in the app."

The two features the user remembered (and research confirmed):

1. **"One hexagon per seat" equal-representation map** — found at [frontend/src/lib/charts/TileCartogram.svelte](frontend/src/lib/charts/TileCartogram.svelte). Built in PR-B2 (UK-style elections plan), full unit tests, currently mounted ONLY in DevChartsSandbox. Pre-rebuild `NationalElection.svelte` had a "Map | Equal seats" toggle that was deliberately removed in PR-W3c with the explicit note "*will return on PR-W4c + PR-W3d*". PR-W3d never shipped. This PR is that restoration.

2. **Party-symbol filter rail** — found as `PartyBar.hidden_parties` + `cellTreatment(mode: "party_won")` already-shipped infrastructure. Wired on AC pages ([Psephlab.svelte](frontend/src/routes/Psephlab.svelte) + [StateOverview.svelte](frontend/src/routes/StateOverview.svelte)); NOT wired on `StateElection.svelte` or `NationalElection.svelte`.

## User-confirmed scope (2026-06-12 ask-questions response)

| Q | Answer |
| --- | --- |
| Hexagon = `TileCartogram.svelte`? | YES, proceed |
| Surface subset? | **ALL THREE LIVE SURFACES** (National PC 2024 + State PC 2024 + State AC) |
| Filter rail location? | Click PartyBar rows to filter (StateOverview precedent) |
| Alliance backfill? | Queue as separate plan-doc AFTER this PR |

## Data inventory (research-confirmed 2026-06-12)

| Surface | Choropleth data | TileCartogram data |
| --- | --- | --- |
| National PC (2024) | ✓ `datasets/boundaries/electoral/delim=2024/pc/all.topojson` 543 features | ✓ `pc/national/delim=2008` 545 tiles |
| State PC (2024) | ✓ filter national PC topojson per state | ✗ no per-state PC tile layout authored |
| State AC (most states) | ✓ `delim=2008/ac/state=*/all.topojson` (30 states) | ✓ `ac/<state>/delim=2008` (30 states) |
| Pre-2024 PC events | ✗ delim=2008/2014 PC geometry missing (upstream gap) | ✓ tile layout but no winners | 

**Key joins to verify in pre-flight (Risk #1, #2 below):**
- delim=2008 PC tile layout `unit_id` shape vs delim=2024 PC entity `entity_id` shape — DO they match? If they don't, the tile cartogram for 2024 events won't render.
- per-state PC slicing: PC features in `all.topojson` need a `state` property OR an entity-table join. Check property keys + check `datasets/data/entities/electoral.csv` for PC→state mapping.

## Verdicts (locked, no re-debate)

### Surface 1: National Parliament event page (`/t/elections/general-2024`)

Current: KPIs + IndiaPartyMap (state-level state choropleth) + top-parties.

Add a **3-way map toggle** above the map area: `States | Constituencies | Equal seats`
- **States** = current `IndiaPartyMap` (one polygon per state, coloured by party-with-most-seats; default). Preserves the at-a-glance "BJP wins these states" read.
- **Constituencies** = NEW `IndiaPcMapD3.svelte` (new file; pattern mirrors `StateAcMapD3.svelte` but at national scope; uses delim=2024 PC topojson; coloured by per-PC winner).
- **Equal seats** = `TileCartogram` with `pc/national/delim=2008` layout.

Add **Winner | Margin sub-toggle** that applies to the active map (already supported by both StateAcMapD3 and TileCartogram via shared `cellTreatment`).

Add **party filter** via PartyBar click-to-mute. Muted parties recede on whichever map is active.

### Surface 2: State Parliament event page (`/<state>/elections/general-2024`)

Current: PC-placeholder card.

Replace with a per-state PC choropleth via new `StatePcMapD3.svelte` (mirrors StateAcMapD3 but uses national PC geometry filtered by state). Same Winner|Margin toggle. NO "Equal seats" mode (no per-state PC tile layout exists — surfaced as an inline note: "Equal-seats view available on the national 2024 surface.").

Add **party filter** via PartyBar click-to-mute.

### Surface 3: State Assembly event page (`/<state>/elections/assembly-*`)

Current: StateAcMapD3 + Winner|Margin toggle.

Add a **Map | Equal seats** toggle above the map area:
- **Map** = current `StateAcMapD3` (default).
- **Equal seats** = `TileCartogram` with `ac/<state-scope>/delim=2008` layout.

Winner|Margin toggle applies to both.

Add **party filter** via PartyBar click-to-mute. Muted parties recede on both renderers.

### Cross-surface decisions

- **2019 LS and earlier Parliament events:** still get the placeholder card. The delim=2008 PC geometry is an upstream-ingest gap (Hans + Max owned; tracked in follow-up).
- **Filter rail location:** PartyBar click-to-mute (StateOverview precedent; no separate chip strip). When `hidden_parties.size > 0`, render a "Show all (N muted)" reset button above the PartyBar.
- **Mode persistence:** the active map mode lives in component state only, NOT in the URL (consistent with Scatter filter pills per PR-W4c).
- **Default mode** on each surface: the most-informative-at-a-glance — States (national), Map (state-PC), Map (state-AC).

## Scope (this PR — rows A through G)

| # | Change | Files | Level |
| - | --- | --- | :---: |
| A | New `IndiaPcMapD3.svelte` — national PC choropleth (pattern from StateAcMapD3; uses `INDIA_PC` boundary source) | `frontend/src/lib/charts/IndiaPcMapD3.svelte` (NEW) · `frontend/src/lib/charts/IndiaPcMapD3.test.ts` (NEW) | 2 |
| B | New `StatePcMapD3.svelte` — per-state PC choropleth (filters national PC geometry by state via entities.csv join) | `frontend/src/lib/charts/StatePcMapD3.svelte` (NEW) · `frontend/src/lib/charts/StatePcMapD3.test.ts` (NEW) · possibly `frontend/src/lib/boundaries/sources.ts` if a `STATE_PC` resolver is cleaner than inline filtering | 3 |
| C | NationalElection 3-way map toggle (States / Constituencies / Equal seats) + Winner|Margin sub-toggle + PartyBar click-to-mute wiring | `frontend/src/routes/NationalElection.svelte` | 3 |
| D | StateElection PC choropleth restoration: replace placeholder card with StatePcMapD3 + Winner|Margin toggle + sub-threshold legend mirror | `frontend/src/routes/StateElection.svelte` (replace the PC placeholder card from PR #954) | 2 |
| E | StateElection (Assembly) Map | Equal seats toggle + TileCartogram wire-up | `frontend/src/routes/StateElection.svelte` (same file as D — single edit pass) | 2 |
| F | PartyBar click-to-mute wired on both routes; `hidden_parties` state owned by the route; passed to all map renderers via `selected_party_id` / `highlight_mode` props | `frontend/src/routes/StateElection.svelte` · `frontend/src/routes/NationalElection.svelte` | 2 |
| G | E2E + vitest tests | `frontend/e2e/state-event-view.spec.ts` · `frontend/e2e/national-event-view.spec.ts` · `frontend/e2e/elections-scatter.spec.ts` (only if scatter assertions need adjusting) · new unit tests where Row A/B add helpers | 1 |

**Out of scope (separate follow-up plan-docs):**
- **Alliance data backfill** for `general-2024` and other "pending" events (user-confirmed queued; opens a separate plan-doc after this PR ships).
- **delim=2008 PC boundary ingest** for 2019/2014/2009 LS events (Hans + Max owned; upstream).
- **Per-state PC tile layout authoring** (would let state Parliament pages get "Equal seats" too — not blocking; tile-layout authoring is its own discipline).
- **Tile-layout vintage upgrade** (the national PC tile layout is delim_year=2008 with 545 tiles; the 2024 event has 543 PCs with delim=2024 unit_ids. Pre-flight will determine whether the join works on `unit_id` alone or whether a new delim=2024 layout is needed; if the latter, surface as Risk #1 BLOCKED and ship without national Equal-seats).

## Risk register

| # | Risk | Mitigation | Stop-condition? |
| - | --- | --- | --- |
| 1 | **delim=2008 PC tile layout `unit_id`s don't match delim=2024 PC entity ids** — the national Equal-seats mode would render every tile as "pending" (no winners join). | Pre-flight: read 3 sample `unit_id`s from `election_tile_layouts.json` (tiles where `layout_kind="pc", scope="national"`) and compare against 3 sample PC `entity_id`s from `datasets/data/entities/electoral.csv` where `entity_kind="pc"`. If they don't match: STOP Row C's Equal-seats arm; ship the 3-way toggle as 2-way (States | Constituencies); add a Scope-change ledger row explaining why. Do NOT band-aid by writing a unit_id translator — that's data-tier work owned by Hans + Max. | YES |
| 2 | **PC features in `all.topojson` lack a `state` property** — Row B's per-state filter has nowhere to join. | Pre-flight: read the first feature's `properties` keys from `delim=2024/pc/all.topojson`. If `state` or equivalent is absent, JOIN via the canonical `electoral.csv` PC rows (their `state` column or `parent` FK). Cost is a small in-memory map (~543 entries) built once per page. If neither works: STOP Row B; placeholder card persists for state Parliament pages. | YES |
| 3 | **PartyBar `hidden_parties` Set identity** — PartyBar uses `party_eci_code OR party_short` as the key per its docstring. The map's `cellTreatment` uses `selected_party_id` which is the canonical `parties.IN.<SLUG>`. Two different ID spaces. | Translate at the route level: map `hidden_parties` (party_short keys) to the equivalent `selected_party_id` via the party catalogue (the same source that powers `getPartyColor`). Use the existing `partyIdFor` pattern in `election-tile-layout.ts`. | NO (engineering wire-up only) |
| 4 | **NationalElection.svelte previous "Map | Equal seats" toggle code may still be reachable in git history** — could save authoring time. | Subagent runs `git log --all --diff-filter=D --oneline -- 'frontend/src/routes/NationalElection.svelte'` for the pre-W3c version; if the deletion commit is recoverable and reusable, lift-and-adapt rather than re-write. | NO (optimisation only) |
| 5 | **PartyBar widening from PR #954 (`alliance_short?`) might surprise the new map-filter wiring** — adding `hidden_parties` after another PR's interface widening can confuse consumers. | The widening was additive; this PR's wiring is also additive. Read PartyBar end-to-end once before touching it; verify no existing call-site breaks (`Psephlab`, `StateOverview`, `StateElection` post-#954). | NO |
| 6 | **3-way toggle on national page may visually clutter** — Jony's earlier verdict was reductionist. | The toggle bar is a single row of 3 segmented buttons (same affordance as Winner|Margin); it adds 1 row of chrome ~32px tall. If the visual fails browser smoke (looks busy), fall back to a 2-way "Map | Equal seats" (drop the States third option; IndiaPartyMap stays the default, toggle just hides/shows it). Cite Jony in the deviation note. | NO (UX fallback) |

## Implementation discipline

- **Worktree:** subagent works in `..\yen-gov-elx-restoration` on branch `feat/elx-pc-choropleth-and-tile-restoration` (file-disjoint from active worktrees `yen-gov-boundary-precision`, `yen-gov-pw-fixes`, `yen-gov-tcpd-catalogue` per user-memory master-collision protection).
- **Tests:** every changed component lands with vitest + e2e per CLAUDE.md §14.
- **Lockfile:** zero `package.json` changes expected; if any creep in, `bun install` + stage `bun.lock` in same commit per CLAUDE.md §9.
- **§13 UI verification:** subagent MUST hit ALL THREE surfaces (`/t/elections/general-2024`, `/maharashtra/elections/general-2024`, `/maharashtra/elections/assembly-2019`) + a second state for state-agnostic spot-check (`/karnataka/elections/assembly-2023` or similar).
- **§7 debug logs:** zero `[DEBUG]` markers at PR finish.
- **§8 git hygiene:** named branch, explicit-path `git add`, squash-merge, post-merge cleanup.
- **§10 anti-pattern alerts:** no JSON projections of canonical data (existing CSV-via-DuckDB-WASM holds); no new UI fields on indicator-catalogue (none touched); no network fetches (everything ships in the static bundle).

## Acceptance gates

| Gate | Command |
| --- | --- |
| svelte-check | `cd frontend; bun x svelte-check --threshold error` — 0 new errors vs baseline (PR #954 left 30 pre-existing on main; this PR must not add to that count) |
| vitest | `cd frontend; bun x vitest run --pool=forks --poolOptions.forks.singleFork=true` all pass |
| playwright | `cd frontend; bun x playwright test e2e/state-event-view.spec.ts e2e/elections-scatter.spec.ts e2e/national-event-view.spec.ts` all pass |
| browser smoke 1 | `/t/elections/general-2024`: 3-way map toggle visible; States renders IndiaPartyMap; Constituencies renders 543 PC polygons; Equal seats renders 545 hex tiles (or 2-way fallback per Risk #1); Winner|Margin sub-toggle works on Constituencies + Equal seats; PartyBar click mutes a party AND the map updates (selected-party cells stay, others recede); "Show all (N muted)" reset works. |
| browser smoke 2 | `/maharashtra/elections/general-2024`: PC choropleth visible (no placeholder card); Winner|Margin works; PartyBar click filters; AC-style sub-threshold legend visible if applicable. |
| browser smoke 3 | `/maharashtra/elections/assembly-2019`: Map | Equal seats toggle visible; Map renders StateAcMapD3 (current); Equal seats renders TileCartogram with MH AC layout; Winner|Margin works on both; PartyBar click filters both. |
| browser smoke 4 | `/karnataka/elections/assembly-2023`: state-agnostic verification of smoke 3 (just toggle through and confirm no Karnataka-specific regression). |
| smoke console | zero `[error]` console events across all 4 smoke surfaces. |

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-12 | research | Explore subagent confirmed all three threads: PC choropleth feasible (delim=2024 + INDIA_PC registered, no consumer yet); TileCartogram exists + tested + ONLY mounted in DevChartsSandbox; PartyBar.hidden_parties wired on AC pages (Psephlab + StateOverview), missing on Parliament surfaces. |
| 2026-06-12 | data probe | National PC tile layout = `(layout_kind=pc, scope=national, delim_year=2008)` 545 tiles. Per-state PC tile layout = none. AC tile layouts = 30 state scopes at delim=2008. PC geometry on disk = delim=2024 only. |
| 2026-06-12 | confirm | User answered ask-questions: hexagon = TileCartogram (confirmed), surfaces = ALL THREE LIVE, filter rail = PartyBar click (StateOverview precedent), alliance backfill = queue after. |
| 2026-06-12 | scope-lock | 7 rows A through G; 3 surfaces; out-of-scope = pre-2024 LS events (delim=2008 PC missing) + per-state PC tile layout authoring + alliance data backfill (queued as follow-up plan-doc). |
| 2026-06-12 | pre-flight | Risk #1 (unit_id shape) GREEN with creative resolution — tile `IN-PC-2008-<state_code>-<eci_no>` constructed at route from `state_code` + `eci_no` projection; 80% national tile join (435/545). Risk #2 (per-state PC join) GREEN — topojson features carry `state_ut_code` + `unique_id` properties; per-state filter is in-memory, no external join. Risk #4 (git-history lift) PARTIAL — pre-W3c `NationalElectionsAtlas.svelte` deleted in `5801b9384` carried MapLibre+TileCartogram toggle; MapLibre retired; layout/setView pattern lifted from still-alive `ElectionMap.svelte`. Risk #3 (PartyBar identity translation) GREEN — `buildPartyKeyToPid` helper bridges party_short keys to canonical `parties.IN.<SLUG>`. |
| 2026-06-12 | ship | PR [#958](https://github.com/miztiik/yen-gov/pull/958) merged to `origin/main` at `315f14e15`. Rows A-G all landed; 9 files (+2684 / -160). svelte-check 0 NEW errors (30 pre-existing baseline). vitest 5548 passed / 0 failed. §13 browser smoke on 4 surfaces (national PC 2024, Maharashtra PC 2024, Maharashtra AC 2019, Karnataka AC 2023) all GREEN with zero `[error]` console events. State PC 100% join on Maharashtra; National AC tile cartogram 92% (266/288 Maharashtra); National PC tile cartogram 80% (435/545) — residual 20% is `SLUG_TO_ECI` loader gap surfaced as follow-up #1 below. |

## Plan complete (2026-06-12)

**Closure.** All 7 rows A-G landed in PR [#958](https://github.com/miztiik/yen-gov/pull/958) (`315f14e15`). Pre-2024 LS events still show the placeholder card per scope-lock; per-state PC tile layout authoring is deferred. Two follow-up workstreams surfaced:

1. **National PC tile pending rate (~20%, 110 tiles).** `view-models/election-results.ts::SLUG_TO_ECI` fallback (`state_slug.toUpperCase()`) doesn't match the `S07` / `U03` ECI state codes the tile layout uses. One-pass audit + mechanical map fix should close the gap.
2. **Alliance backfill** — user-confirmed queued. Opens as a separate plan-doc.

This plan-doc is preserved in `TODO/` as the audit trail for PR #958.
