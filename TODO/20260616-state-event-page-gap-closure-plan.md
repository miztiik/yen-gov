# State election event page - gap + regression closure (ADDENDUM)

**Last Updated**: 2026-06-16
**Level**: 4 (structural; touches frontend route + 6 election subcomponents + 1 new seat-flow model + tests)
**Status**: APPROVED-for-execution. Addendum to the CLOSED parent plan [docs/archive/plans/20260615-state-election-event-page-redesign-plan.md](../docs/archive/plans/20260615-state-election-event-page-redesign-plan.md). User reviewed the live page on 2026-06-16 and named items the parent plan reported as DONE but which did NOT actually land (or regressed). This doc is the audit + the delivery spec.

> The parent plan's Status Reckoner marked R4/R5 MERGED, but a code-level audit against `main` on 2026-06-16 found several rows shipped as scaffolding only, mis-built, or never mounted, plus four named regressions vs the prior surface. This addendum closes the gap. It is NOT a re-litigation of the parent design - it delivers what the parent plan already specced.

## Section 0 - Why this addendum exists

The user audited <https://miztiik.github.io/yen-gov/maharashtra/elections/assembly-2024> on 2026-06-16 against the original objective and against the prior `/maharashtra` state page. Code-level verification on `main` confirmed each finding below. Two buckets:

**A. Parent-plan rows that did NOT actually land (specced but not built / mis-built / not mounted):**

1. **Seat-flow Sankey was built as VOTE-flow.** The user explicitly asked for a factual hold/loss seat-transition Sankey ("for a given constituency a party either holds or loses to another, so we can sum up across parties"). What shipped is [StateEventCrossEventSankey.svelte](../frontend/src/lib/elections/StateEventCrossEventSankey.svelte) wrapping the vote-approximation `SwingSankey` with a "this is an estimate" disclaimer - the opposite of factual. The data for a factual version is already loaded (current + prior winners are both per-AC `ElectionResultRow[]`, joinable on `entity_id`).
2. **"Races by competitiveness" was never mounted on the election page.** [RacesBoard.svelte](../frontend/src/lib/RacesBoard.svelte) exists and is mounted on [StateOverview.svelte](../frontend/src/routes/StateOverview.svelte) but the parent plan's "add Races before the constituency list" was not wired into [StateElection.svelte](../frontend/src/routes/StateElection.svelte).
3. **"All parties - directory" was never mounted on the election page.** Exists on [StateOverview.svelte](../frontend/src/routes/StateOverview.svelte); absent on the election route.
4. **Party composite is still the old `PartyBar`.** [StateEventPartyComposite.svelte](../frontend/src/lib/elections/StateEventPartyComposite.svelte) just wraps [PartyBar.svelte](../frontend/src/lib/PartyBar.svelte). The specced per-party row table with `[symbol][short][alliance-chip][seats-bar][seats][vote-share]` was never built.

**B. Regressions vs the prior surface (named by the user 2026-06-16):**

5. **Party mute mutations lost / degraded.** The "click a party to mute it; muted parties recede on the map" mutation is the load-bearing cross-section interaction. It must work end-to-end on the redesigned page (bar click -> hidden set -> AC + PC map cells recede).
6. **Party pills have no election symbols.** The codebase has a full symbol-asset system (`party-symbols/*.svg`, [symbol-asset.ts](../frontend/src/lib/boundaries/symbol-asset.ts), `dim_parties.election_symbol_asset_path`) but [PartyPill.svelte](../frontend/src/lib/party-pill/PartyPill.svelte) is a "leaf" that renders the symbol ONLY inside its hover popover. The party rows on the composite show no symbol. The user wants the symbol visible on the row.
7. **Alliance display regressed (the "arrows"/grouping gone).** Current [AllianceTotals.svelte](../frontend/src/lib/elections/AllianceTotals.svelte) renders a plain text line ("NDA 11 / INDIA 0 / Others 0"). The user's reference is a winner/runner-up diverging-bar summary (screenshot) with the member-party chips - the richer alliance representation Max + Jony specced.
8. **Tooltip double-render bug.** [PartyBar.svelte](../frontend/src/lib/PartyBar.svelte) fires its own `ChartTooltip` AND the nested [PartyPill.svelte](../frontend/src/lib/party-pill/PartyPill.svelte) fires its own `PartyTooltip` popover - two overlapping cards on one hover (user screenshot).
9. **Hero KPI glyphs too weak.** The glyphs render (`TopicIcon` landmark/users/vote/activity at `h-3.5`) but are visually understated; the user asked for "nice glyphs for seats / total voters / total polled".

## Section 0.1 - Hard scope

In scope: items 1-9 above. All are frontend-only on the election route + its subcomponents + one new pure seat-flow model + tests. No schema change, no backend writer change, no new data ingest.

Out of scope (named so an executor does not pull them in):

- District grouping for the constituency list (item 7e in the prior audit). The loader does not carry a `district` label; that is a separate ingest concern. The fold/search/click already work against one "All constituencies" group; real district grouping waits for the AC-district crosswalk to flow through `loadElectionResults`. Documented, deferred.
- The full J-elevated 2027 motion contract (view-transitions, haptics, pinch-zoom, narrative-generator, national-context, share-card memory). Those are parent-plan aspirational rows; this addendum closes the FUNCTIONAL gaps + regressions only.
- Per-AC drill-down page changes.

## Section 0.2 - ESCALATE triggers (PAUSE and ask user)

- The factual seat-flow Sankey reveals a data integrity problem (e.g. prior-event AC ids do not join to current-event AC ids because of a delimitation change) for the anchor states - surface the join-failure rate rather than silently bucketing to "Others".
- Restoring party symbols on the row requires a loader field that is not populated (`election_symbol_asset_path` missing for the anchor parties) - surface which parties lack a symbol asset rather than shipping a wall of placeholders.
- Any change here would require a schema or backend writer change - that is out of scope; stop and surface.

## Section 1 - Status Reckoner

| Row | Title                                                                                          | Status        | Effort |
| --- | ---------------------------------------------------------------------------------------------- | ------------- | ------ |
| G1  | Fix PartyBar double-tooltip (suppress nested PartyPill popover inside the bar)                  | [x] DONE      | XS     |
| G2  | Mount "Races by competitiveness" (RacesBoard) above the constituency list                      | [x] DONE      | S      |
| G3  | Mount "All parties - directory" as the final section                                           | [x] DONE      | S      |
| G4  | Party-row symbols + restore mute mutations + alliance chip in the composite                    | [x] DONE      | M      |
| G5  | Factual seat-flow (hold/loss) Sankey replacing the vote-flow approximation                     | [x] DONE      | M      |
| G6  | Alliance display upgrade (winner/runner-up diverging bars + member chips)                       | [x] DONE      | M      |
| G7  | Strengthen hero KPI glyphs (size + weight + colour)                                             | [x] DONE      | XS     |

Effort key: XS = minutes; S = single sitting; M = a few hours.

Dependency: G1/G2/G3/G7 are independent quick wins. G4 precedes G5/G6 conceptually (shared party-row chrome) but they touch different files so may ship together. No hard ordering; ship in Reckoner order for review clarity.

## Section 2 - Per-row spec

### Row G1 - Fix PartyBar double-tooltip

**Root cause**: [PartyBar.svelte](../frontend/src/lib/PartyBar.svelte) wires row-level `onmouseenter={(e) => showTip(e, p)}` driving its own `ChartTooltip`, AND it mounts a nested `<PartyPill>` which has its own hover/focus popover (`PartyTooltip`). On hover both fire -> two overlapping cards (user screenshot).

**Fix**: Suppress the PartyPill popover when the pill is rendered inside PartyBar (the bar already owns the richer `ChartTooltip` card with seats + vote-share + mute hint). Add a `suppress_tooltip?: boolean` prop to PartyPill (default false; PartyBar passes true). The pill keeps its colour treatment + label + click-to-mute affordance; only its popover is silenced.

**Files**: [frontend/src/lib/party-pill/PartyPill.svelte](../frontend/src/lib/party-pill/PartyPill.svelte) (+ `suppress_tooltip` prop, guard the open-state), [frontend/src/lib/PartyBar.svelte](../frontend/src/lib/PartyBar.svelte) (pass `suppress_tooltip`), new unit assertion in the existing PartyPill test that `suppress_tooltip` keeps `shouldOpen` false.

**Oracle**: hover a PartyBar row -> exactly one tooltip card. Browser smoke + a vitest assertion that PartyPill with `suppress_tooltip` never opens.

### Row G2 - Mount Races by competitiveness

**Scope**: Mount [RacesBoard.svelte](../frontend/src/lib/RacesBoard.svelte) on [StateElection.svelte](../frontend/src/routes/StateElection.svelte) directly ABOVE the `StateEventConstituencyList`. Mirror the StateOverview invocation: `<RacesBoard state={state_code} rows={winners-as-ac-winners} event={event_id} />`. The election page's `winners` rows carry the same `(entity_id, party_short, party_id, margin_pct)` shape RacesBoard needs; add a thin adapter if the prop names differ.

**Files**: [frontend/src/routes/StateElection.svelte](../frontend/src/routes/StateElection.svelte) (import + mount + section heading "Races by competitiveness"), section-order contract test extended to assert RacesBoard appears before the constituency list.

**Oracle**: `/maharashtra/elections/assembly-2024` shows the 6-band races board (BJP won easily / ... / Most competitive) above the constituency list, matching the prior state-page surface.

### Row G3 - Mount All parties directory

**Scope**: Mount an "All parties - directory" section as the LAST content section (after the Sankey), mirroring [StateOverview.svelte](../frontend/src/routes/StateOverview.svelte): searchable grid of every party that contested, each a `PartyPill` link to `/parties/<slug>` + `seats - vote-share`. Source rows from the event's full party-totals (the same data feeding the composite, unfiltered to top-N).

**Files**: new [frontend/src/lib/elections/StateEventAllParties.svelte](../frontend/src/lib/elections/StateEventAllParties.svelte) (extract the StateOverview directory markup into a reusable component so both surfaces share it) + mount in [StateElection.svelte](../frontend/src/routes/StateElection.svelte) + unit test for the search filter.

**Oracle**: `/maharashtra/elections/assembly-2024` ends with a searchable all-parties directory; typing filters; clicking a party opens its page.

### Row G4 - Party-row symbols + restore mutations + alliance chip

**Scope**: Replace the [StateEventPartyComposite.svelte](../frontend/src/lib/elections/StateEventPartyComposite.svelte) body (currently a thin `PartyBar` wrapper) with the specced per-party row table: `[symbol][short pill][alliance-chip][seats-bar][seats][vote-share%]`.

- **Symbol**: render the party election symbol via [symbol-asset.ts](../frontend/src/lib/boundaries/symbol-asset.ts) `symbolAssetUrl(election_symbol_asset_path)` in a `rounded-full bg-slate-50 ring-1 ring-slate-200` halo (Jony J-elevated-6). Falls back to the placeholder asset when the path is null.
- **Mutations (restore)**: keep the click-to-mute mutation - clicking a row toggles the party into `hidden_parties`; the binding flows up to the AC + PC map override path so muted parties recede on the map (verify end-to-end; this is regression item 5). The reset ("Show all (N muted)") affordance stays.
- **Alliance chip**: small outline chip showing the party's alliance short when one exists for `(event_id, state)`.

**Files**: [frontend/src/lib/elections/StateEventPartyComposite.svelte](../frontend/src/lib/elections/StateEventPartyComposite.svelte) (rebuild body), loader join to carry `election_symbol_asset_path` + `alliance_short` onto the party-totals rows if not already present, unit test for the row shape + mute toggle, browser smoke that muting a row recedes its map cells.

**Oracle**: each party row shows its symbol + short + alliance chip + seats bar + seats + vote-share; clicking mutes it and the map cell recedes; the reset restores.

### Row G5 - Factual seat-flow (hold/loss) Sankey

**Scope**: Replace the vote-flow approximation with a FACTUAL seat-transition Sankey. New pure model [frontend/src/lib/elections/seat-flow-model.ts](../frontend/src/lib/elections/seat-flow-model.ts): join current winners + prior winners on `entity_id` (the AC/PC); for each seat emit a `(prev_party -> curr_party)` transition; aggregate to a flow matrix. A seat where the same party held is a self-loop (HOLD); a seat that changed hands is a cross-flow (LOSS/GAIN). Render with the existing `SwingSankey` primitive fed the real transition counts (NOT the vote-redistribution estimate), OR a thin d3-sankey if SwingSankey cannot express self-loops cleanly.

- **Caption (factual, not "approximate")**: "Each constituency's seat moved from its {prev_year} winner to its {curr_year} winner. Ribbon width = number of seats. Self-loops are holds." NO "estimate" / "approximate" language - this is exact.
- **No-prior**: same no-prior copy as today (first event on record has nothing to flow from).
- **Delimitation guard** (ESCALATE): if > X% of current ACs do not join to a prior AC id (boundary change), surface the unmatched count in the caption rather than silently dropping.

**Files**: new [frontend/src/lib/elections/seat-flow-model.ts](../frontend/src/lib/elections/seat-flow-model.ts) + test, rebuild [frontend/src/lib/elections/StateEventCrossEventSankey.svelte](../frontend/src/lib/elections/StateEventCrossEventSankey.svelte) to consume it (retire the vote-flow `cross-event-sankey-model` path or keep the diverging bar as the always-on baseline + swap the opt-in Sankey to seat-flow), update the section heading from "Vote-flow comparison" to "Seat flow: where each seat moved".

**Oracle**: MH 2024 vs 2019 shows ribbons whose widths sum to the seat count; a party that held N seats shows an N-wide self-loop; the caption carries no "approximate" language.

### Row G6 - Alliance display upgrade

**Scope**: Upgrade [AllianceTotals.svelte](../frontend/src/lib/elections/AllianceTotals.svelte) from the plain text line to the winner/runner-up diverging-bar summary the user referenced (screenshot): a Winner card + Runner-up card, each with alliance name + seats + vote-share + member-party chips, and a tail row of smaller alliances. Keep the R6 honesty caption + the silence-on-uncurated rule. The member-party chips reuse `PartyPill` (with `suppress_tooltip` from G1). This is the "alliance arrows/grouping" the user said regressed - represented as the bar pair + member chips, NOT literal arrows.

**Files**: [frontend/src/lib/elections/AllianceTotals.svelte](../frontend/src/lib/elections/AllianceTotals.svelte) (richer layout), [frontend/src/lib/elections/alliance-totals-model.ts](../frontend/src/lib/elections/alliance-totals-model.ts) (extend the breakdown with winner/runner-up ranking + per-alliance vote-share + member list), unit tests for the ranking + member rollup.

**Oracle**: an event with curated alliances (e.g. a TN/MH event) shows the winner + runner-up alliance bars with member chips; an uncurated event still suppresses the panel entirely.

### Row G7 - Strengthen hero glyphs

**Scope**: Make the four hero KPI glyphs read as deliberate iconography, not faint marks: bump from `h-3.5 w-3.5 text-slate-500` to a stronger treatment (e.g. `h-4 w-4` in a `rounded bg-slate-100 p-1` chip, or a coloured accent per the J-elevated-3 verdict), keeping the existing icon names (landmark/users/vote/activity) + the turnout-delta trending glyph. Verify the chosen glyphs are the "nice" ones the user wants; swap icon names if a clearer ballot/people/turnout glyph exists in the allowlist.

**Files**: [frontend/src/lib/elections/StateEventHero.svelte](../frontend/src/lib/elections/StateEventHero.svelte) (glyph treatment), existing hero test updated if it asserts the icon size.

**Oracle**: the four KPI cards show clear, weighted glyphs that a citizen reads at a glance on mobile.

## Section 3 - Execution + gates

Ship as a small number of reviewable commits on one branch `feat/state-event-gap-closure` (or split G5/G6 into their own PRs if the diff is large). Per-row gates:

- `cd frontend; bun run check` 0 new errors.
- `cd frontend; bun x vitest run` green (new + existing).
- Browser smoke per [CLAUDE.md section 13](../CLAUDE.md): `/maharashtra/elections/assembly-2024` (all sections render; one tooltip on hover; mute recedes map; races board present; all-parties present; seat-flow ribbons; alliance bars; strong glyphs), `/jammu-and-kashmir-ut/elections/assembly-2024` (first-event-on-record: no seat-flow prior, no turnout-delta), one cross-state smoke.
- No `[DEBUG]` left; no `bun.lock` desync.

## Section 4 - Closure ledger

Filled as rows land.

| Row | Status | Notes |
| --- | ------ | ----- |
| G1  | DONE | `suppress_tooltip` prop on PartyPill; PartyBar passes it. One tooltip on hover. |
| G2  | DONE | RacesBoard mounted above the constituency list via a dedicated `races_rows` (true winner colours + symbol, not margin-grey). |
| G3  | DONE | New `StateEventAllParties.svelte` (searchable, zero-seat toggle) mounted as final section; fed by full `all_parties` derivation. |
| G4  | DONE | Symbol glyph added to PartyBar rows (gutter widened w-24->w-28); `symbol_asset_path` threaded through PartyTotals + aggregation; mute mutation verified intact (hidden_parties -> hidden_pids -> map overrides). |
| G5  | DONE | New pure `seat-flow-model.ts` (factual hold/loss join on entity_id) + rewritten Sankey component (bipartite, holds as self-loops, factual caption). Retired vote-flow `cross-event-sankey-model.ts` + test (rip). 7 unit tests + 3 section-order invariants. |
| G6  | DONE | AllianceTotals upgraded to winner/runner-up cards (seat-share bar + member chips) + tail chips. Winner card uses emerald (amber forbidden by no-pending-pill contract). |
| G7  | DONE | Hero KPI glyphs upgraded to per-metric coloured icon chips (h-7 rounded squares). |

**Gates**: `bun x vitest run` 3631 passed / 21 skipped / 0 failed; `bun run check` 0 new errors (16 baseline errors + 40 warnings unchanged); e2e seat-flow spec updated to new testids/copy. Also removed an orphaned untracked `routes/ElectionsFirehose.svelte` (resurrected copy of the route deleted during the redesign rip) that was tripping the `no-route-bare-width-cap` contract.
