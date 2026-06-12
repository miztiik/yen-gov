# Election event page UX polish — 2026-06-12

**Status:** READY-TO-IMPLEMENT
**Correction level:** Level-3 (multi-file frontend rework, 1 PR)
**Authority cites:** [CLAUDE.md](../CLAUDE.md) §0a (UX = Jony + Citizen; data shape = Hans + Max; engineering = Fowler; contracts = Gregor) · §6 correction levels · §9 DoD · §13 UI verification.
**Surface:** `/<state-slug>/elections/<event-slug>` (Svelte 5 route `frontend/src/routes/StateElection.svelte`) + `/t/elections/<event-slug>` (national equivalent) + the shared `Scatter.svelte` primitive.

## Problem (user-named, 2026-06-12)

Reviewing the live page <https://miztiik.github.io/yen-gov/maharashtra/elections/general-2024> exposed six UX gaps on the election event surface. State-agnostic; same code path renders all 36 state/UTs × N events.

1. **Parliament events show no constituency map.** Assembly event renders a per-AC choropleth; Parliament event renders nothing (PC boundaries gated out at `body === "ac"`).
2. **Scatter "Turnout vs winning margin" is ugly.** Circles too big → blob; Y-axis 0..100 wastes 65% canvas; SC/ST footnote claims data unpopulated when it is now populated (3819 GEN / 524 SC / 390 ST as of 2026-06-12); body filter chips visible on a single-body fixed-event page; chart renders at SVG width=720 inside a `max-w-6xl` (1152px) parent so it floats narrow.
3. **"Event slug general-2024"** header text is developer metadata, not citizen-facing.
4. **"Top parties by seats"** bar only encodes seats. Need vote-share + seats together; a chart with that shape already exists at `frontend/src/lib/PartyBar.svelte`.
5. **Party/alliance representation.** Parties show only short codes (BJP, SHSU…). Need alliance affiliation surfaced.
6. **District-wise map circles are unexplained.** The Assembly map overlays circular markers for ACs whose bounding box is < 14 px (urban dense ACs). Citizens have no legend telling them what the circles mean.

## Verdicts (persona debate, 2026-06-12)

### Scatter circle-size encoding (Issue 2, sub-question "what data to pack into radius")

Three candidates surfaced by Citizen + Max:

| # | Candidate | Story | Pre-req | Decision |
| - | --- | --- | --- | --- |
| 1 | `sqrt(electors)` (status quo) | "Structural civic weight" | none | reject — structural fact, not result fact |
| 2 | `sqrt(votes_polled)` | "Civic decision weight cast in THIS event" | none (already projected) | runner-up |
| 3 | **`sqrt(margin_votes)`** | "How decisively was this seat won — 3k votes vs 4 lakh" | additive SQL projection (~3 lines) on `election-results.ts` | **CHOSEN** |

Citizen + Max both ranked (3) as the strongest pairing with Y=margin%: "close in % AND in absolute votes is a different story from close in % but lakhs apart." Cost is one column projection on both SQL arms.

### Scatter visual spec (Jony verdict, baked into PR)

1. `MAX_R = 10` (was 22); keep `MIN_R = 2`; keep `scaleSqrt` (OWID Rosling area-proportional).
2. Remove resting white stroke; `fill-opacity = 0.55` (was 0.7); on hover `stroke = slate-900 1.5px`, `fill-opacity = 1.0`.
3. **Dynamic Y**: `y_max = max(40, ceil(1.1 × max_margin / 10) × 10)`; capped at 100. Fixed-0 lower (Rosling axiom: never break zero baseline on a ratio chart). **X stays fixed 0..100** (turnout is a universal participation rate; price of cross-event comparability).
4. **Full width**: drop hard `width=720` default; use `bind:clientWidth` on a wrapper `<div>`, pass to component.
5. **Body chip**: NEW prop `lock_body?: boolean`; when true (state-event surfaces always; national surfaces when constraining), the Body row hides.
6. **Footnotes**: delete stale reservation note entirely; move honesty caption into an `(i)` info-icon next to the chart title, default-hidden (icon only renders when multi-event scope crosses the 2009 delim boundary — state-event surface never does).
7. **Chip rail wrap**: `flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-6 sm:gap-y-2`.

### Other verdicts

- **Issue 1 (PC map gap):** The `delim=2024` country PC file exists per `datasets/boundaries/electoral/README.md`. PC boundary integration (per-state filter + new STATE_PC loader + `body === "pc"` arm in StateElection) is Level-3 by itself; scoped OUT of this PR. **This PR ships a placeholder card** that explicitly tells citizens "Constituency map not available yet for Parliament events; see [follow-up plan]." Hans+Max own the follow-up work.
- **Issue 3 (event slug):** delete line 521 `<span class="text-slate-500">Event slug <code ...>{params.event}</code></span>`. `params.event` is still load-bearing for URL construction (constituency table links + Compare CTA) — only the visual text is removed.
- **Issue 4 (top parties):** Replace inline `<ol>` bar with `<PartyBar>`. Extend `PartyTotal` interface with `vote_share_pct?: number | null`; aggregate `vote_share_pct` per party from the existing W2b loader rows (sum of winner shares is NOT the right encoding — instead aggregate ALL rows per party by summing `votes_polled` and dividing by event-total `total_valid_votes`; this gives the correct party vote-share). Pass `total_seats = kpis.total_seats` to PartyBar.
- **Issue 5 (alliance):** Alliance lookup is already loaded by `AllianceTotals` via `loadAlliances(event)`. Refactor: hoist the `loadAlliances` call into StateElection's `$effect`; decorate each `PartyTotal` row with `alliance_short?: string | null`; PartyBar displays it as a slate-400 tag after the party short. **AllianceTotals continues to render its own panel unchanged.** When `alliance_short` is null (data pending — current state for general-2024), no tag renders.
- **Issue 6 (map circles legend):** Add a one-line legend below the StateAcMapD3 in StateElection.svelte: "Circles mark dense urban constituencies too small to render as polygons at this zoom." No code change in the map component itself.

## Scope (this PR)

| # | Change | Files | Level |
| - | --- | --- | :---: |
| A | Scatter visual rework (7-point Jony spec + dynamic Y + `lock_body` prop + footnote rewrite + responsive width) | `frontend/src/lib/charts/Scatter.svelte` · `frontend/src/lib/charts/scatter-model.ts` (if domain helpers move there) · `frontend/src/lib/charts/scatter-model.test.ts` | 2 |
| B | `margin_votes` SQL projection on W2b loader (both NATIONAL-PC + STATE-AC arms) + `ScatterDatum.margin_votes` field + radius encoding swap (electors → margin_votes) | `frontend/src/lib/view-models/election-results.ts` · `frontend/src/lib/charts/scatter-model.ts` · `frontend/src/lib/view-models/election-results.test.ts` | 2 |
| C | Event slug header text delete + map sub-threshold legend add + PC map placeholder card | `frontend/src/routes/StateElection.svelte` | 1 |
| D | Top-parties bar → PartyBar swap + vote_share aggregation + alliance decoration | `frontend/src/routes/StateElection.svelte` · `frontend/src/lib/PartyBar.svelte` (interface widen for alliance tag — additive) | 3 |
| E | NationalElection mirror: pass `lock_body` to Scatter (so the body chip hides when a national-event already implies body); event slug header text delete (if present); same responsive width | `frontend/src/routes/NationalElection.svelte` | 1 |
| F | E2E tests update | `frontend/e2e/state-event-view.spec.ts` · `frontend/e2e/elections-scatter.spec.ts` · `frontend/e2e/national-event-view.spec.ts` | 1 |

**Out of scope (follow-up plan-doc):**
- PC boundary integration for Parliament events (uses delim=2024 country file; per-state filter; new `STATE_PC` loader; `body === "pc"` arm in StateElection map conditional).
- Alliance data backfill for general-2024 and other "pending" events (Hans-owned upstream gap; touches `psephlab` data tier, not frontend).
- District-wise map rendered for Parliament events (Issue 1 partial; cosmetic legend only ships this PR).

## Implementation discipline

- **Worktree:** subagent works in `../yen-gov-elx-polish` on branch `feat/elx-event-page-polish` (file-disjoint from active boundary-precision + pw-fixes worktrees per user-memory master-collision protection pattern).
- **Tests:** every changed component lands with vitest + e2e per CLAUDE.md §14 (Unit + Contract + E2E tiers).
- **Lockfile:** zero `package.json` changes expected; if any creep in, `bun install` + stage `bun.lock` in same commit per CLAUDE.md §9.
- **§13 UI verification:** subagent MUST hit BOTH `/maharashtra/elections/general-2024` (Parliament; no map; scatter visible) AND `/maharashtra/elections/assembly-2019` (Assembly; map visible; scatter visible) on dev server BEFORE marking done.
- **Doctrine:** no UI fields on `indicator-catalogue.schema.json` (election-event-row schema is separate; this PR doesn't touch the indicator catalogue). No JSON projections of canonical data (already CSV via DuckDB-WASM). Path rules unchanged.
- **§7 debug logs:** zero `[DEBUG]` markers at PR finish.
- **§8 git hygiene:** named branch, explicit-path `git add`, squash-merge, post-merge cleanup.

## Acceptance gates

Before marking ready-to-merge the subagent must report:

| Gate | Command |
| --- | --- |
| svelte-check | `cd frontend; bun x svelte-check --threshold error` returns 0 errors |
| vitest | `cd frontend; bun x vitest run --pool=forks --poolOptions.forks.singleFork=true` all pass |
| playwright (changed specs only) | `cd frontend; bun x playwright test e2e/state-event-view.spec.ts e2e/elections-scatter.spec.ts e2e/national-event-view.spec.ts` all pass |
| backend pytest | not applicable (no backend changes) |
| browser smoke A | navigate to `/maharashtra/elections/general-2024`: scatter spans full width, dynamic Y caps near 40%, no "Event slug" text in header, top-parties bar shows vote-share + seats; sub-threshold-marker legend NOT visible (no map); PC placeholder card present |
| browser smoke B | navigate to `/maharashtra/elections/assembly-2019`: scatter same as above; AC map present with the new legend below |
| browser smoke C | navigate to `/karnataka/elections/assembly-2023`: scatter + map both render with same shape (state-agnostic check) |
| smoke console | zero `[error]` console events on any of the three smoke surfaces |

## Risk register

- **Risk:** PartyBar's existing consumers break if interface widens for `alliance_short`. Mitigation: add `alliance_short?` as OPTIONAL field on PartyTotals; existing call-sites pass `null`/`undefined`; PartyBar renders the tag only when truthy.
- **Risk:** margin_votes column may not exist in the source SQL views. Mitigation: subagent verifies the table schemas during pre-flight (read `frontend/src/lib/canonical/sql/election_results.sql` or the SQL string in `election-results.ts`) and surfaces the projection seam in plain terms; if the column is absent at the data tier, subagent stops and reports.
- **Risk:** Dynamic Y-axis with a 40% floor may make a near-sweep state event look flat. Mitigation: caption auto-includes "y-axis adapted to data range" when y_max < 100 so analysts know not to compare across events at sight.

## Ledger

| Date | Row | Notes |
| --- | --- | --- |
| 2026-06-12 | research | Explore subagent mapped full topology; minor research error (claimed scatter not mounted on StateElection; verified at line 760+); cleared |
| 2026-06-12 | data probe | reservation column populated as of 2026-06-12 (GEN 3819 / SC 524 / ST 390); footnote is stale |
| 2026-06-12 | debate | Citizen + Max + Jony each returned crisp verdicts; converged on dynamic Y + smaller circles + hide body chip + delete reservation note + full width; circle-size encoding voted to `sqrt(margin_votes)` |
| 2026-06-12 | scope-lock | PC boundary integration (Issue 1) DEFERRED to follow-up; placeholder card ships this PR; alliance backfill (Issue 5 upstream) DEFERRED to Hans-owned plan |
| 2026-06-12 | ship | PR [#954](https://github.com/miztiik/yen-gov/pull/954) merged to `origin/main` at `76ab5101d`. Rows A-F all landed. 15 files, +611 / -148. svelte-check 0 new errors (30 pre-existing baseline). vitest 5548 passed / 0 failed. playwright 8/8 passed (state-event-view + elections-scatter + national-event-view). §13 browser smoke on 3 surfaces (MH Parliament, MH Assembly, KA Assembly) all green with zero console errors. Pre-flight verified `margin_votes` is contract-declared in both summary.csv schemas (KA-2023 BADAMI = 9725) — no compute-from-vote_share band-aid needed. |

## Plan complete (2026-06-12)

**Closure.** All 6 user-named issues addressed in PR [#954](https://github.com/miztiik/yen-gov/pull/954) (`76ab5101d`). Follow-up scope explicitly carried forward, NOT band-aided:

1. **PC boundary integration for Parliament events** — `delim=2024` country PC topojson exists on disk per `datasets/boundaries/electoral/README.md`. Need per-state filter + new STATE_PC loader + `body === "pc"` arm in StateElection map conditional. Hans+Max owned. Tracked here, not yet a separate plan-doc.
2. **Alliance data backfill for general-2024 and other "pending" events** — upstream `psephlab` data-tier gap. AllianceTotals shows "Alliance data pending for this event" message. Once data lands, PartyBar's `alliance_short` tag renders with zero code change (additive interface already shipped). Hans owned.

This plan-doc is preserved in `TODO/` as the audit trail for PR #954. A future maintenance PR may relocate it under `docs/archive/plans/` per `docs/how-to/distill-a-plan.md` when convenient.
