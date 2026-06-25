# Election Constituency-List Redesign + AC->PC Backfill Plan

**Last Updated**: 2026-06-25
**Level**: 4 (structural; crosses `frontend/` + `backend/`/`datasets/`; rip-and-replace of the shared constituency-list renderer plus a data backfill)
**Supersedes UI of**: [TODO/20260622-election-constituency-grouping-plan.md](20260622-election-constituency-grouping-plan.md) (Row 2/3 grouping; this plan rips its flex layout and replaces it with a CSS subgrid).

---

## Section 0 - Operating contract

### 0.0 Why this plan exists

The "Constituencies by state" list on the national general-election page (`/t/elections/general-2024`) and the shared state-event list confuse citizens and break visually. Verified failures (citations are to the live code):

1. **Right-rail bars do not align.** [NationalElection.svelte](../frontend/src/routes/NationalElection.svelte#L1586) state rail is a `flex ... justify-between` with a `min-w-[60px] flex-1` bar + a `shrink-0` variable-width label, so a wider label (`BJP 17/28`) shoves its bar left and no column ever forms. This is the user's #1 issue ("make sure things align").
2. **Two unlabelled numbers** on a PC header (e.g. Bhongir `INC 45.0%` + `15.9%`) read as ambiguous; the Citizen guesses the margin is turnout or runner-up share.
3. **`-> District` arrow** ([StateEventConstituencyList.svelte](../frontend/src/lib/elections/StateEventConstituencyList.svelte#L424)) reads as "navigate to", not "sits in".
4. **The "All constituencies" bucket** ([constituency-list-tokens.ts](../frontend/src/lib/elections/constituency-list-tokens.ts#L362) `groupKeyOf` fallback) is the set of Assembly seats with no parent Parliament seat; it renders an all-dashes `<table>` and, because `buildGroups` sorts groups by `localeCompare`, sorts as "All..." and WEDGES second (after "Adilabad", before "Bhongir") in Telangana, breaking reading order. It reads as a bug.
5. **State separation + hover** are a single hairline + faint `hover:bg-slate-50`.
6. **Mobile** hides the share (`hidden sm:inline`) leaving a bare margin that misreads as vote share.

Underneath #4 is a real data gap: 382 live-delim (2008) Assembly seats across 26 states have a NULL `parent` Parliament seat (Delhi 70/70 = 100%, Andhra Pradesh 120/293 = 41%, Telangana 10/119). The user directed: fix the data (Phase 0), and make the UI honest + aligned + 2026-modern.

### 0.1 Locked design (user-ratified 2026-06-25, after two Citizen + Jony debate rounds)

Authority for these calls: UX = Jony + Citizen (CLAUDE.md section 0a); data shape = Hans + Max; the user ratified each below.

| # | Decision | Ruling |
|---|----------|--------|
| D1 | Layout | **Option E - margin-bar** on a shared CSS subgrid. The margin BAR (length = magnitude, hue = RdYlBu band) is the datum; a wall of red stubs (Mahbubnagar +0.36) jumps out before a number is read. No density toggle (Option F dropped). |
| D2 | Alignment engine | ONE 6-track `grid-cols-subgrid` ruler shared by the state rail, the PC header, and the AC leaf. Only the NAME cell indents by depth; result columns never shift. This is the fix for failure #1 and the core requirement. |
| D3 | Typed tokens | Share ALWAYS carries `%` (`45.0%`); margin is signed + unitless (`+15.9`) against its colour bar. A `%` is always a share, a `+n` by a bar is always a lead - so the two numbers stay UNLABELLED per row (too many rows for labels) yet unambiguous. Plus ONE one-time column hint pinned at the top of the whole list. |
| D4 | Mobile | Show BOTH typed tokens (`45.0%` and `+15.9`) on the PC header even < 640px; the district reflows to a second line under the AC name. (Reverses today's bug that hid the share.) |
| D5 | Pending bucket | The unlinked-AC bucket becomes a group titled **"Parliament seat pending"**, sorted LAST (never wedged mid-list), its leaves show muted **"data pending"** in the context cell, and it NEVER renders dashed result columns. Nothing is hidden (the user: "we cannot hide AC that is part of PC"). |
| D6 | District label | `(map-pin) Ranga Reddy` in the shared context column (track 3) on desktop; reflows to a second line under the AC name on mobile. No "in" word (the pin means "at this place"). Replaces the `-> District` arrow. |
| D7 | AC hyperlink | The whole AC leaf is an `<a href>`; a muted trailing `arrow-up-right` glyph (NOT chevron-right, which is the expand twisty) signals "tap to go deeper", brightening on row hover. Destination = the AC's own page via the existing `link.ac(state_slug, ac_name)` (the only drill-down that exists today). A future "focus AC inside its PC group" route is OUT OF SCOPE (noted, not built). |
| D8 | State rail | Explicit + aligned: `Telangana   17 Parliament seats   BJP 8 of 17   [seat bar]`. "17 Parliament seats" (not bare "17 seats"); "BJP 8 of 17" (not "BJP 8/17"). |
| D9 | State separation | Heavier divider between states + a tinted (`bg-slate-50`) open panel. (Card-border option rejected by user.) |
| D10 | Vocabulary | "Parliament seat" (PC) / "Assembly seat" (AC) / "District". PC/AC abbreviations appear ONLY in the one-time top hint where they are introduced paired - never as per-row tags. |
| D11 | Scope | The ONE shared [StateEventConstituencyList.svelte](../frontend/src/lib/elections/StateEventConstituencyList.svelte) keeps serving BOTH assembly mode (state pages, per-AC result table) AND PC mode (national). Shared fixes (subgrid, hover, separation, tokens) apply to both; mode-specific fixes (pending bucket, district leaf, AC jump glyph) apply where relevant. |
| D12 | Data gap | Phase 0 backfills the 382 NULL `parent` links sourced from the ECI 2008 Delimitation Order / indiavotes (LGD's snapshot lacks `parent_pc_lgd_code` for these, so LGD alone cannot fill them - confirmed). Residual unmappable ACs stay NULL and degrade to D5 "data pending". The UI (Phase 1) and the backfill (Phase 0) are INDEPENDENT and run in parallel. |
| D13 | Strategy | Rip-and-replace. No strangler-fig, no feature flag, no parallel old/new path. The flex `justify-between` blocks are deleted and replaced by the subgrid in one component row. |

### 0.2 The locked render (ASCII ground truth for the executor)

Glyphs: `^>` = `arrow-up-right` (jump) - `(pin)` = `map-pin` - `|####----|` = RdYlBu margin bar.

Desktop (Telangana expanded, Bhongir expanded; `|` = subgrid track boundary, not rendered):
```
       | tw | name                       | context           | pty  | share | margin + bar     |
state  | v  | Telangana                  | 17 Parliament seats| BJP | 8 of 17| [#######........] |
PC hdr | v  |   Bhongir                  | 7 Assembly seats  | INC  | 45.0% | +15.9 |####----|  |
leaf   |    |     Ibrahimpatnam     ^>   | (pin) Ranga Reddy |      |       |                  |
leaf   |    |     Nakrekal [SC]     ^>   | (pin) Nalgonda    |      |       |                  |
leaf   |    |     Jangoan           ^>   | (pin) Jangoan     |      |       |                  |
PC hdr | >  |   Mahbubnagar              | 7 Assembly seats  | BJP  | 41.8% | +0.36 |#.......|  |  <- red stub
PC hdr | >  |   Hyderabad                | 7 Assembly seats  |AIMIM | 61.4% | +31.4 |########|  |
...    |    |   (12 more Parliament seats)                                                     |
pend   | >  |   Parliament seat pending  | 10 Assembly seats |      |       | data pending     |  <- sorted LAST
leaf   |    |     Nizamabad Urban   ^>   | District pending  |      |       |                  |
```

Narrow mobile (< 640px): context wraps under the name; PC header keeps BOTH tokens.
```
v Bhongir   Parliament seat
    7 Assembly seats        INC  45.0%  +15.9 |####--|
  Ibrahimpatnam                          ^>
    (pin) Ranga Reddy
  Nizamabad Urban                        ^>
    District pending
```

The 6 tracks (defined ONCE on the parent; every row is `grid grid-cols-subgrid col-span-full items-center`):

| # | track | width | align | state rail | PC header | AC leaf |
|---|-------|-------|-------|------------|-----------|---------|
| 1 | twist | `1.25rem` | center | chevron | chevron (indent 1) | connector (indent 2) |
| 2 | name | `minmax(0,1fr)` | left | "Telangana" | "Bhongir" + badge | AC name + badge + `^>` glyph |
| 3 | context | `minmax(0,max-content)` | left, muted | "17 Parliament seats" | "7 Assembly seats" | "(pin) Ranga Reddy" / "data pending" |
| 4 | party | `max-content` | left | BJP chip | INC chip | (empty) |
| 5 | share | `max-content` | right, tabular | "8 of 17" | "45.0%" | (empty) |
| 6 | margin+bar | `max-content` | right, tabular | seat bar (spans 5-6) | "+15.9" + RdYlBu bar | (empty) |

The grid-template string is exported ONCE from the token module (Row R2) as `GRID_COLS` and consumed by BOTH the component (R3) and the national rail (R4) so the two grids share one ruler across the embed boundary.

### 0.3 Real-data ground truth (for browser verification)

Telangana 2024 PC winners (name / winner / share% / margin pp): Mahbubnagar BJP 41.8 / 0.36 (RED); Medak BJP 34.11 / 2.84; Zahirabad INC 42.83 / 3.74; Secunderabad BJP 45.37 / 4.79; Adilabad[ST] BJP 46.43 / 7.41; Nagarkurnool INC 38.29 / 7.77; Nizamabad BJP 48.19 / 8.89; Chevella BJP 48.53 / 10.36; Peddapalle INC 43.65 / 12.06; Bhongir INC 45.04 / 15.9; Karimnagar BJP 44.75 / 17.22; Warangal INC 46.15 / 17.49; Malkajgiri BJP 51.6 / 20.38; Hyderabad AIMIM 61.44 / 31.38; Mahabubabad INC 55.6 / 31.68; Khammam INC 61.63 / 37.6; Nalgonda INC 60.79 / 43.4 (deep BLUE). State rail: BJP 8 of 17.

Bhongir's 7 Assembly seats + district: Ibrahimpatnam -> Ranga Reddy; Munugode -> Nalgonda; Bhongir -> Yadadri Bhuvanagiri; Nakrekal[SC] -> Nalgonda; Thungathurthy[SC] -> Suryapet; Alair -> Yadadri Bhuvanagiri; Jangoan -> Jangoan.

The unlinked-AC gap (live 2008 delim; `parent IS NULL`), top states: delhi 70/70, andhra-pradesh 120/293, west-bengal 40/295, uttar-pradesh 26/403, maharashtra 22/289, karnataka 16/224, rajasthan 13/200, jammu-and-kashmir 13/90, telangana 10/119, mizoram 8/40; national total = 382 across 26 states. Telangana's 10: Nizamabad (Urban), Dharmapuri[SC], Tandur, Goshamahal, Charminar, Yakutpura, Secunderabad Cantt.[SC], Achampet[SC], Warangal West, Warangal East.

### 0.4 Scope fences + ESCALATE triggers

- IN SCOPE: the shared list renderer, the national state rail, the icon glyphs, the token logic, the pending-bucket behaviour, the 382-AC `parent` backfill, the tests + browser verification for all of it.
- OUT OF SCOPE: a new "AC-focused-inside-its-PC" route (D7 fallback is the existing AC page); any schema change to `electoral.csv` (the `parent` column already exists - this is a data backfill, not a contract change); a11y/ARIA (CLAUDE.md section 0 Non-Goal); the maps; the assembly-mode RESULT semantics (only its LAYOUT moves to the subgrid).
- ESCALATE (stop + ask) ONLY when: (a) Phase-0 sourcing - the ECI/indiavotes AC->PC composition for the 382 cannot be obtained or cross-checked cleanly for a state (surface the residual with a count, do not fabricate a mapping); (b) any row would require deleting or mutating existing election-results VALUES (not just `parent`); (c) a schema major bump is implied; (d) an audit chain exceeds depth 3. Otherwise AUTO.

---

## Section 1 - Status Reckoner

Rows are PRs. Phase 0 (data) and Phase 1 (UI) are INDEPENDENT and run concurrently. Within Phase 1, R1+R2 are parallel prerequisites for R3; R4 follows R3; R5 verifies all.

| Row | Title | Phase / Wave | Depends on | Status | PR | Effort |
|-----|-------|--------------|------------|--------|----|--------|
| R1 | Add `arrow-up-right` + `map-pin` icon glyphs | P1 / A | - | [ ] PENDING | - | S |
| R2 | Token module: typed tokens + margin-bar + pending grouping + `GRID_COLS` | P1 / A | - | [ ] PENDING | - | M |
| R3 | Rip + replace the shared list renderer to the subgrid (Option E) | P1 / B | R1, R2 | [ ] PENDING | - | L |
| R4 | National state rail + one-time top hint on the shared `GRID_COLS` | P1 / C | R2, R3 | [ ] PENDING | - | M |
| R5 | Browser-verify + e2e smoke + alignment proof | P1 / D | R3, R4, P0b | [ ] PENDING | - | M |
| P0a | Source + commit the 382-AC -> PC backfill crosswalk | P0 / A | - | [ ] PENDING | - | L |
| P0b | Wire crosswalk into the seed writer + regenerate `electoral.csv` | P0 / B | P0a | [ ] PENDING | - | M |

**Concurrency model (no idle time; NEVER waits on remote CI or gh merges).** Two independent lanes run concurrently - the UI lane (R1, R2 -> R3 -> R4 -> R5) and the DATA lane (P0a -> P0b) - each in its OWN git worktree. Dispatch {R1, R2, P0a} at once. A dependent row branches off its parent's LOCAL branch tip (stacked), so R3 starts the instant R1+R2 pass LOCAL gates - it does NOT wait for their PRs to merge remotely. Each finished row pushes, opens a PR, and is set to auto-merge so remote CI + the squash-merge happen in the background while the orchestrator immediately advances to the next unblocked row. When a parent PR finally merges, the open child branches are rebased onto origin/main (mechanical; the rows touch disjoint files). The only synchronization point is a true data dependency - never a CI run, never a merge round-trip.

---

## Section 2 - R1: icon glyphs

- **Scope**: add two Lucide (ISC-licensed) SVGs so `TopicIcon name="arrow-up-right"` and `name="map-pin"` render (today both are silent-misses).
- **Files**: `frontend/public/icons/arrow-up-right.svg`, `frontend/public/icons/map-pin.svg`, `frontend/public/icons/LICENCES.md` (one inventory row each + bump the "N glyphs" count), `frontend/src/lib/TopicIcon.test.ts` (add both names, in alphabetical position, to the pinned `registeredIconNames()` array).
- **Gotcha (from /memories)**: the build-time `iconRegistryPlugin` parses each SVG through `frontend/src/lib/icons/allowlist.ts`; `ALLOWED_ATTRS` does NOT include `rect` `width`/`height`/`rx`. `map-pin` is path+circle (safe); if any source uses `<rect>` convert it to a rounded-rect `<path>`. Keep inner paths byte-identical otherwise.
- **Gates**: `bun run build` (validates SVG bytes via the registry) + `bun run test` (TopicIcon.test.ts name-list gate) green.
- **Oracle**: `registeredIconNames()` returns the exact sorted array INCLUDING `arrow-up-right` + `map-pin`, and `bun run build` passes the SVG allowlist for both.

## Section 3 - R2: token module (typed tokens + margin-bar + pending grouping + shared grid)

- **Scope**: extend [constituency-list-tokens.ts](../frontend/src/lib/elections/constituency-list-tokens.ts) (pure logic, no Svelte) with everything the renderer needs, so R3 stays a thin renderer.
- **Add**:
  1. `fmtShare(n) -> "45.0%" | "-"` and `fmtMarginSigned(n) -> "+15.9" | "-0.4" | "-"` (typed-token formatters; share keeps `%`, margin keeps sign, no `%`).
  2. `marginBarSegment(margin)` -> `{ pct: 0..100, hex }` where `pct` encodes magnitude on a fixed scale (e.g. clamp `min(|margin|, 50)/50*100`) and `hex` = the existing `marginBand` colour. The BAR is the datum (D1).
  3. Pending grouping: a `PENDING_GROUP = "Parliament seat pending"` constant; `buildGroups` (PC mode) routes leaves whose `pc_group == null` into `PENDING_GROUP` (instead of today's `"All constituencies"` fallback) AND sorts that group LAST regardless of `localeCompare` (D5). Keep the assembly-mode `district`/`"All constituencies"` fallback UNCHANGED (D11 - assembly pages still group by district).
  4. `export const GRID_COLS = "grid-cols-[1.25rem_minmax(0,1fr)_minmax(0,max-content)_max-content_max-content_max-content]"` - the single ruler consumed by R3 + R4 (D2).
- **Files**: `constituency-list-tokens.ts`; tests `frontend/src/lib/elections/StateEventConstituencyList.test.ts` + `frontend/src/lib/elections/national-constituency-list.test.ts` (these test the token module - extend the oracle here, no corpus iteration per CLAUDE.md section 10).
- **Gates**: `bun run test` (vitest) green; the token tests are the oracle.
- **Oracle**: unit tests assert (a) `fmtShare(45.04)=="45.0%"`, `fmtMarginSigned(15.9)=="+15.9"`, `fmtMarginSigned(-0.36)=="-0.4"`; (b) `marginBarSegment(0.36).hex` is the nail-biter red and its `pct` < `marginBarSegment(15.9).pct`; (c) `buildGroups` with a null-`pc_group` leaf places it in a group keyed `"Parliament seat pending"` that is the LAST element of the returned array even when another group sorts after it alphabetically; (d) assembly-mode grouping (no `group_headers`) is byte-for-byte unchanged (regression test).

## Section 4 - R3: rip + replace the renderer (Option E subgrid)

- **Scope**: DELETE the `flex ... justify-between` PC header, the `-> {district}` leaf span, and the assembly `<table>` LAYOUT in [StateEventConstituencyList.svelte](../frontend/src/lib/elections/StateEventConstituencyList.svelte); replace with the 6-track `grid-cols-subgrid` (D2) carrying Option E. No old path left behind (D13).
- **Build**:
  - Parent `<ul>` sets `class={`grid ${GRID_COLS} ...`}`; every row (`<li>`/PC header `<button>`/AC leaf) is `grid grid-cols-subgrid col-span-full items-center`.
  - PC header row: twist chevron (track1) - name + `ReservationBadge` (track2) - "N Assembly seats" (track3) - party chip (track4) - `fmtShare` (track5) - `fmtMarginSigned` + the `marginBarSegment` bar (track6). Both share+margin visible on mobile (D4).
  - AC leaf row: now an `<a href={r.href}>` (whole-row link, D7) with `group` - name + badge + trailing muted `arrow-up-right` glyph that brightens on `group-hover` (track2) - `(map-pin) {district}` muted, or muted `"data pending"` / `"District pending"` when null (track3, D6) - tracks 4-6 empty. The context cell uses `max-sm:col-start-2 max-sm:row-start-2` to reflow under the name on mobile (D4/D6).
  - Pending group: renders the SAME header shape, title "Parliament seat pending", context "N Assembly seats", tracks 5-6 show muted "data pending" (NEVER a dashed table, D5). Its leaves render exactly like normal AC leaves with "District pending" where missing. Nothing dropped (bijection).
  - Assembly mode (no `group_headers`): the SAME subgrid; the per-AC winner chip + `fmtShare` + `fmtMarginSigned`+bar fill tracks 4-6 on the LEAF (where PC mode leaves them empty). Keep `eci_no` as a quiet prefix inside track2 when present. The dashed-`<table>` is gone for BOTH modes (D11).
  - Hover/separation: leaves `hover:bg-slate-50`; the open panel is tinted `bg-slate-50` (D9 - the national embed owns the heavier state divider in R4).
- **Files**: `StateEventConstituencyList.svelte`; `frontend/src/lib/elections/StateEventConstituencyList.test.ts` (structural assertions).
- **Gates**: `bun run test` green; section 13 browser-verify deferred to R5 but smoke one state page here.
- **Oracle**: a contract test asserting (a) EVERY rendered row carries `grid-cols-subgrid` (no `justify-between` survives - grep the compiled markup); (b) a PC-mode AC leaf is an `<a href>` containing the `arrow-up-right` glyph and the `map-pin` district cell; (c) a null-district leaf renders "District pending" and NO dashed result cells; (d) bijection - rows rendered == leaves in == nothing dropped; (e) assembly mode still renders a per-AC winner chip on the leaf. Browser (one state page) shows the share + margin columns sharing a single x.

## Section 5 - R4: national state rail + one-time top hint

- **Scope**: move the [NationalElection.svelte](../frontend/src/routes/NationalElection.svelte#L1563) state-row rail onto the shared `GRID_COLS` so the state rail's columns align with the nested PC/AC rows; make it explicit (D8); add the one-time top hint (D3/D10).
- **Build**:
  - State row `<button>` becomes `grid grid-cols-subgrid col-span-full` under a parent `<ul class={`grid ${GRID_COLS}`}>`: chevron (track1) - state name (track2) - "17 Parliament seats" (track3) - leading-party chip (track4) - "8 of 17" (track5) - the seat-dominance bar spanning tracks 5-6 (D8). DELETE the `max-w-[55%] flex-1` floating rail (failure #1).
  - Heavier divider between state rows + tinted open panel (D9).
  - One-time hint pinned at the top of the list (reuse/extend the existing [MarginLegend.svelte](../frontend/src/lib/elections/MarginLegend.svelte)): a single line "Parliament seats hold Assembly seats, grouped by District." + the existing RdYlBu margin legend. Introduces "PC"/"AC" paired ONCE here, nowhere per-row (D10).
  - Confirm the embedded `StateEventConstituencyList` (mounted in the state panel) inherits/repeats the SAME `GRID_COLS` so columns line up across the embed (right-anchored result columns + matching horizontal padding origin).
- **Files**: `NationalElection.svelte`; `MarginLegend.svelte` (hint line); `frontend/src/lib/elections/national-constituency-list.test.ts` (rail tokens); the route's existing testids preserved.
- **Gates**: `bun run test` green.
- **Oracle**: test asserts the state rail emits "17 Parliament seats" + "8 of 17" (not "17 seats"/"8/17") and uses `grid-cols-subgrid`; browser on `/t/elections/general-2024` Telangana shows the state-rail bar, the PC `+15.9` bar, and the share column all left/right-aligned to the same x down the list (the original-bug proof).

## Section 6 - R5: browser-verify + e2e + alignment proof

- **Scope**: section 13 UI verification across the surfaces + an e2e smoke; capture the alignment proof.
- **Surfaces**: `/t/elections/general-2024` -> expand Telangana (PC groups + Bhongir's 7 ACs with pins + the "Parliament seat pending" group LAST with its 10 ACs), Delhi (the 70/70 all-pending case - must render gracefully, never a dashed table), Andhra Pradesh (120 pending + real PC groups interleaved correctly, pending LAST); plus one state ASSEMBLY event page (e.g. `/maharashtra/elections/assembly-2019`) to prove D11 (assembly mode still shows per-AC results on the same subgrid).
- **Checks**: (a) new copy/structure renders; (b) no new `[error]` console events; (c) no new 404; (d) screenshot proving the share/margin/bar columns share an x across state rail + PC + AC; (e) mobile viewport shows BOTH tokens + the district on a second line.
- **Files**: `frontend/e2e/*.spec.ts` (extend the elections smoke; use `waitUntil:"load"` + a fixed `waitForTimeout` per /memories - `networkidle` never fires for DuckDB-WASM; for the live-animating map pages prefer a DOM-click bypass).
- **Gates**: `bun run test` + `bun run build` + the targeted Playwright spec green; browser smoke per section 13.
- **Oracle**: the screenshot/measurement shows column alignment holds on Telangana AND Delhi (all-pending) AND a state assembly page; zero new console errors on all four routes.

## Section 7 - P0a: source + commit the 382-AC -> PC backfill crosswalk

- **Scope**: produce a committed, source-cited crosswalk mapping each of the 382 NULL-`parent` Assembly seats (live 2008 delim) to its parent Parliament seat, sourced from the ECI 2008 Delimitation Order (de jure PC->AC composition) cross-checked against indiavotes (D12). LGD cannot fill these (its snapshot lacks `parent_pc_lgd_code` for them - confirmed at [electoral_csv_from_snapshot.py](../backend/yen_gov/canonical/seed/electoral_csv_from_snapshot.py#L142)).
- **Build**: a new committed artifact (e.g. `datasets/data/entities/ac_pc_backfill.csv`) with columns `ac_entity_id, parent_pc_entity_id, parent_pc_lgd_code, match_method, source_id` + a `source.csv` provenance row (Holy Law #9; build `source_id` via `derive_source_id`). The local ingest/build script MAY fetch indiavotes (CLAUDE.md D1: LOCAL pipeline only; production/CI never fetch). Residual ACs that cannot be mapped with confidence are LISTED (not guessed) and stay NULL -> D5 "data pending".
- **ESCALATE**: if a state's composition cannot be obtained/cross-checked cleanly, surface the residual count for that state and proceed with the rest - do NOT fabricate a mapping (section 0.4 trigger a).
- **Files**: the crosswalk CSV + its `source.csv` row + the build tool under `backend/` or `tools/` + a Tier-A/B note; docs under `docs/architecture/data/` if a new artifact class.
- **Gates**: `pytest -q` green; the crosswalk validates (FK targets resolve: every `ac_entity_id` exists in electoral.csv as an `entity_kind='ac'` with delim 2008 and NULL parent today; every `parent_pc_entity_id` exists as a PC).
- **Oracle**: the crosswalk covers >= the agreed share of 382 (target: all states where ECI/indiavotes composition is obtainable), every row carries a `source_id`, and the residual-unmapped list is committed with a count; no row maps an AC that already had a non-NULL parent.

## Section 8 - P0b: wire the crosswalk into the seed writer + regenerate

- **Scope**: consume the P0a crosswalk in the seed writer so `parent` is populated for the backfilled ACs; regenerate `electoral.csv`; confirm the unlinked count drops from 382 to the documented residual.
- **Build**: in [electoral_csv_from_snapshot.py](../backend/yen_gov/canonical/seed/electoral_csv_from_snapshot.py#L142), after the LGD `parent_pc_lgd_code` resolution, fall back to the P0a crosswalk for ACs still NULL (LGD-first, crosswalk-second, NULL-last for residual). Regenerate `datasets/data/entities/electoral.csv`. No other column may churn.
- **Files**: the seed writer + the regenerated `electoral.csv` + the writer's test under `backend/tests/`.
- **Gates**: `pytest -q` green incl. a new writer test; Tier-B `python -m yen_gov validate --root .` clean for the touched files.
- **Oracle**: a query proves `COUNT(parent IS NULL) for entity_kind='ac' AND delim_year=2008` == the documented residual (down from 382), and `git diff` on `electoral.csv` touches ONLY the `parent` column of the backfilled AC rows (no name/eci_no/reservation churn). After P0b + R3/R4 merge, the Telangana "Parliament seat pending" bucket shrinks (or empties) live.

---

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on.
2. **One row = one PR = one branch, in its OWN worktree.** Park master on a `scratch-master-parking` branch so no worktree owns `main` (clean gh-merge). Give each concurrently-running row its own `git worktree` off the right base (origin/main for wave-A rows; the parent's branch tip for stacked rows) so parallel subagents NEVER share a working tree - a shared worktree causes lost/misplaced commits and branch-switches under a sibling. Author per `docs/how-to/ship-a-pr.md`: 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change.
3. **Ship loop - non-stop, NEVER blocking on remote CI or merges.** Keep multiple PRs in flight on separate branches/worktrees and never sit idle waiting for CI to go green or for `gh` to finish a merge. The moment a row's LOCAL gates pass (run vitest/build/pytest locally), push the branch, open its PR, and set it to auto-merge (`gh pr merge --auto --squash --delete-branch`) so remote CI + the merge complete ASYNCHRONOUSLY in the background; the orchestrator IMMEDIATELY starts the next unblocked row. For a DEPENDENT row do NOT wait for the parent's PR to merge - branch it off the parent's local branch tip (stacked: R3 on R1+R2, R4 on R3, P0b on P0a, R5 on R3+R4+P0b). When a parent PR merges, rebase the open child branches onto the new origin/main (mechanical; the rows touch disjoint files). The only synchronization point is a true data dependency, never a CI run or a merge round-trip. Pre-existing unrelated test failures are not gating - document the baseline, do not block.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked.
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (CLAUDE.md section 0a) in debate, not parallel review; bake the single written verdict into the row and proceed. (The section 0.1 table already pre-resolves the known calls.)
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into subagents so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (section 0.4), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3. Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt (the command + its zero result). Archive the plan-doc with a per-row distillation map per `docs/how-to/distill-a-plan.md`.

---

## Appendix - decision provenance + file inventory

- Persona debate: Citizen + Jony, two rounds (2026-06-25). Jony round 1 options A/B/C rejected by user; round 2 options D/E/F/G -> user chose E + strict subgrid alignment. All section 0.1 rulings user-ratified.
- Load-bearing source files: `frontend/src/lib/elections/constituency-list-tokens.ts`, `frontend/src/lib/elections/StateEventConstituencyList.svelte`, `frontend/src/routes/NationalElection.svelte`, `frontend/src/lib/elections/constituency-district-loader.ts`, `frontend/src/lib/links.ts`, `frontend/src/lib/elections/MarginLegend.svelte`, `frontend/src/lib/TopicIcon.svelte`, `frontend/public/icons/`, `backend/yen_gov/canonical/seed/electoral_csv_from_snapshot.py`, `datasets/data/entities/{electoral.csv, lgd/constituencies.csv, ac_crosswalk.csv, electoral_district_membership.csv}`.
- Holy Laws load-bearing: #1 static-first (the AC link is client routing; any indiavotes fetch is LOCAL-only per D1), #3 contracts (the `GRID_COLS` + token contract; no schema change), #5 structural (rip-and-replace, no flag), #9 provenance (the P0a crosswalk carries `source_id`), #10 tests ship with the row.
