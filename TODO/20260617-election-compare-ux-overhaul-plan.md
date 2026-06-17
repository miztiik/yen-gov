# Election Compare + Year-Navigation UX Overhaul (Jony)

**Last Updated**: 2026-06-17

**Authority**: Jony + Citizen (UX) per CLAUDE.md section 0a. Touches `frontend/` only.
No data-shape, schema, or backend change. Correction Level 2-3 (frontend, behaviour
change, ships with tests).

**Load-bearing Holy Laws**: #1 static-first, #4 docs=memory, #5 structural-fixes-only,
#7 no-mocks, #10 tests-ship.

**Load-bearing docs**: [docs/concepts/citizen-first.md](../docs/concepts/citizen-first.md),
[docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md),
[docs/concepts/schema-is-the-design-system.md](../docs/concepts/schema-is-the-design-system.md).

**Domain rules honoured**: discrete pills never sliders (election surface);
"2027-ready not 1990-ready" (no arrows/chevrons, no native `<select>` as the primary
control); every party reference renders via `<PartyPill>`; pure-model extraction so
vitest (node-env, no jsdom) tests the math; English-only citizen chrome.

---

## 0. What the user reported (verbatim intent, neutral prose)

Four UX problems on the election surfaces, raised 2026-06-17:

1. **Year navigation does not scale.** The state/national event pages render one pill
   per election year (`SiblingEventsRail`). As elections grow to 10-15+, "keep adding a
   pill per year" stops making sense. Same scaling problem on the compare page.
2. **Comparison is hard-tied to one year.** The state event page only offers
   "Compare with {prior_year}" (the immediately-preceding same-body event). The compare
   page itself (`/compare/elections/...`) cannot change either side once you land on it.
   The user explicitly wants Jony to propose options BEYOND a 1990s dropdown before any
   dropdown is chosen.
3. **Compare-constituency table is hard to scan.** No string search over constituency
   names (234 rows for TN assembly). The sort affordance (a tiny up/down glyph that
   appears only on the active column) is not intuitive and not visible at rest.
4. **Compare hero cards are flat.** No glyphs. "Flips" and "Holds" are bare counts with
   no share-of-seats context. "New-party entries" is an abstract count - the citizen
   cannot see WHICH seats a new party won.

---

## 1. Jony framing

The election surface already made the right call once: the year strip is a discrete
tap-to-jump rail (Spotify Now-Playing / IG story-tray reference class), not a slider and
not a dropdown. That decision is sound and we keep it. The failure is not the rail
metaphor - it is that:

- the rail has no hierarchy or overflow affordance, so 15 equal chips read as noise;
- the COMPARE entry point is a single hardwired pill (prior-year only); and
- once on the compare page the citizen is trapped at one (from, to) pair.

The unifying Jony move: **build ONE reusable "year picker" popover primitive and reuse it
everywhere a year must be chosen** - compare-entry on the rail, and from/to swap on the
compare page. Do not grow a bespoke control per surface (schema-is-the-design-system).
A dropdown is the LAST option; the picker-popover with a year grid is the modern form of
the same affordance and is what we ship.

Removing-before-adding: the rail's flexibility problem is solved by REPLACING the single
"Compare with {prior_year}" pill with one "Compare" chip that opens the picker - not by
adding a second control.

---

## 2. Issue 1 - Year navigation that scales (nav) + un-tying compare (compare)

### 2a. Navigation rail (which year am I viewing)

The rail is `overflow-x-auto` + scroll-snap and already auto-centres the active chip, so
it technically survives 15 chips. The gap is hierarchy + overflow signalling. Options
(Jony proposes, recommends one):

- **Option A - Edge-fade + keep (RECOMMENDED).** Keep every chip; add a left/right
  gradient fade mask that appears only when the rail overflows, signalling "more years
  this way". Active chip stays centred. Zero new interaction; pure affordance. Scales
  cleanly to ~15. This is the smallest change that fixes the reported "noise".
- **Option B - Recent-N + "Earlier" disclosure.** Show the most recent N chips (e.g. 6)
  inline; collapse older ones behind one "Earlier" chip that expands the full rail (or
  opens the year-picker popover from 2b). Progressive disclosure - 90% of citizens want
  the last 2-3 elections. Better at 20+ but adds an interaction.
- **Option C - Native dropdown.** The 1990s fallback. Rejected as the PRIMARY control;
  only acceptable as the year-grid INSIDE the picker popover (Option B's expansion target).

**Recommendation**: ship **Option A** now (cheap, no new interaction). Option B is the
escalation path if event counts cross ~20; documented but not built yet.

### 2b. Compare picker primitive + un-tying compare (RECOMMENDED, both surfaces)

Build a small reusable popover `YearComparePicker` (button -> popover with a year grid of
the same-body sibling events, winner-colour underline per year, current year disabled).
Reuse it in two places:

- **On the rail**: replace the hardwired "Compare with {prior_year}" pill with a single
  "Compare" chip. Tap -> picker lists every OTHER same-body year -> pick any -> navigate
  to `/compare/elections/<state>/<picked>/<current>`. Citizen can now compare 2024 vs any
  prior year, not just 2019.
- **On the compare page**: the header's two static "From: X" / "To: Y" badges become two
  picker buttons (From / To). Pick either side -> `navigate()` to the new compare URL.
  This directly kills "comparison is hard-tied to one year" on the compare surface itself.

One component, two mounts. The picker is the modern dropdown - a year GRID popover, not a
native select - so the user's "propose options before a massive dropdown" is satisfied:
we never ship a massive dropdown.

---

## 3. Issue 2 - Compare-constituency table: search + discoverable sort

`CompareElections.svelte` table today: column-header `<button>` with a tiny triangle that
renders ONLY on the active sort column; no search.

Fixes (both easy, frontend-only):

- **Search box.** A compact text input in the table toolbar (next to the filter chips and
  the "N of M rows" count). Live case-insensitive substring filter that matches
  **constituency name AND party** (both the From and To winner - short code e.g. "DMK"
  and full party name). A citizen asking "show me all AIADMK seats" or "where did the
  DMK lose" is answered by the same box. Clears with an x. Composes with the existing
  All/Flips/Holds filter and with sort.
  - Note: matching party means the filter model needs the full party name, not only the
    `party_short` already on the row. Source it from the party registry the page already
    loads for `<PartyPill>`; if the full name is not readily available on the compare
    row, match `party_short` (always present) + `entity_name` and treat full-name match
    as an additive nicety, not a blocker.
- **Discoverable sort affordance.** Make the affordance visible AT REST, not only after
  interaction (core Jony rule):
  - every sortable header shows a faint neutral up-down chevron glyph by default, sized
    **slightly smaller** than the current active-only triangle (a light, unobtrusive
    hint - not a heavy arrow);
  - the active column shows a solid filled arrow (up/down), same small size, + bold label;
  - cursor + hover state confirm the header is interactive;
  - a small "Sorted by {column}" caption is optional (decide at build).

### 3a. Result-count + party-dot summary (mirror the state-page list)

The state event page's constituency list already shows a result count + a winner-party
dot-strip (the screenshot's top-right "3 [dots]"); the source pattern lives in
`StateEventConstituencyList.svelte` (`dot_strip: string[]` of up to 6 winner-colour hex).
The compare table should carry the SAME affordance, with its meaning anchored to the
compare surface:

- **Rule (Jony)**: the dots = the distinct **To-winner parties present in the current
  filtered + searched rows**, ordered by frequency (most seats first), capped at ~6 with
  a "+k" overflow, alongside the existing "N of M rows" count.
- **Why To-winner (not a fixed "holds-by-party")**: tying the dots to a single metric
  (e.g. holds-by-party) is distracting - it buries flips, the more interesting story on
  a compare page. Anchoring to the To-winner column makes the dots SELF-ADAPT to the
  active filter: with Holds active they read as "parties holding", with Flips active as
  "parties that flipped to", with All as the overall winner palette. One rule, correct
  under every filter.
- **Colour source**: resolve each To-winner `party_id` via `getPartyColor(party_id, row)`
  (`frontend/src/lib/colors/resolver.ts`) - the same 3-tier resolver PartyPill uses;
  anchor + fallback always yield a deterministic hex, brand tier uses the parties.csv row
  when available. Never hand-pick a hue.
- Orphan rows (Boundary changed / New seat) have no stable To-party in both events; they
  are excluded from the dot tally the same way they are excluded from the flip/hold KPIs.

Difficulty: trivial. Pure template + one model helper for the filter (kept in a `*.ts`
model so vitest tests the predicate without jsdom).

---

## 4. Issue 3 - Compare hero cards: glyphs + composition % + new-party discoverability

### 4a. Glyphs (easy)

`StateEventHero` already has the exact pattern: a `TopicIcon` in a tinted rounded square
next to each KPI label. Mirror it onto the four `CompareElections` KPI cards:

| Card | Icon | Status |
| --- | --- | --- |
| Total seats | `landmark` | exists |
| Flips | `arrow-left-right` (or `repeat`) | MUST ADD svg to `frontend/public/icons/` |
| Holds | `shield` | exists |
| New-party entries | `flag` | exists |

Icons are a build-time registry walking `frontend/public/icons/*.svg` (silent-miss if
absent). Flips needs a new Lucide SVG dropped into `public/icons/` (allowed per platform
plan 21.10). Keep `aria-hidden` (a11y is a CLAUDE.md Non-Goal; icons are decorative).

### 4b. Composition % on Flips / Holds (easy)

Show flips and holds as a share of total comparable seats, computed live:
`flips/total_seats`, `holds/total_seats`. E.g. "163 / 70% of seats" and "71 / 30%".
This is the meaningful "change %" for a single (from, to) pair.

> RESOLVED 2026-06-17: ship reading (a) composition % in PR4 now. Reading (b) - the
> flip-TREND ("has flipping increased this election vs the previous election") - is a
> VALID citizen + Hans question and is prepared as PR5 (section 5). PR4 ships only (a).

### 4c. New-party-entry discoverability (easy)

The KPI already computes `new_entries` (to-winner party that won zero seats in `from`).
Expose it so the citizen can SEE the seats:

- add a 4th filter chip "New parties" alongside All / Flips / Holds that filters the
  table to those constituencies;
- tag those rows in the Change column with a distinct badge, e.g.
  "New entry -> {party}", so they stand out when "All" is selected.

The per-row predicate already exists in the KPI loop; lift it to a row flag.

---

## 5. PR breakdown

Four frontend-only PRs, each ships with tests (vitest pure-model + any contract test) and
section-13 browser verification. Order is independent except PR1 introduces the picker
primitive that PR1 itself consumes; PRs 2-4 do not depend on PR1.

### PR1 - Year-compare picker primitive + compare-anywhere
- New `frontend/src/lib/elections/YearComparePicker.svelte` (thin) +
  `year-compare-picker-model.ts` (pure: given sibling events + current event_id, emit the
  selectable year list with winner-colour + disabled-current flag) + model test.
- Rewire `SiblingEventsRail`: replace the single "Compare with {prior_year}" pill with a
  "Compare" chip that opens the picker; keep the nav chips unchanged.
- Rewire `CompareElections` header: From / To badges become picker buttons that
  `navigate()` to the recomputed `link.compareElections(state, from, to)` URL.
- Update `sibling-events-rail-model.ts` to expose all sibling years to the picker (it
  already builds the full sorted list; surface it instead of only `prior_year`).
- Tests: model unit tests (selectable list, current disabled, href construction);
  update `sibling-events-rail-model.test.ts`; e2e: land on a compare page, swap the From
  year, assert URL + table change.
- Section 13: browser-verify rail "Compare" popover + compare-page From/To swap on a
  state with many events (e.g. Tamil Nadu assembly).

### PR2 - Nav-rail overflow affordance (Option A)
- Add the edge-fade mask to `SiblingEventsRail` (CSS-only; appears on overflow).
- Keep active-chip auto-centre. No model change.
- Test: a contract/DOM-light assertion is hard for CSS masks; rely on section-13
  screenshot verification on a >=12-event state + a small vitest snapshot of the rail
  class wiring if cheap.

### PR3 - Compare table: search box + discoverable sort + result party-dots
- Add search input to `CompareElections` toolbar; filter helper in a new
  `compare-table-filter.ts` pure model + test (substring over constituency name AND party
  short/full + filter-chip + sort compose).
- Default neutral sort glyph (slightly smaller) on every sortable header; solid arrow on
  active column.
- Add the result-count + To-winner party-dot summary (section 3a): a pure
  `compare-dot-summary.ts` (given the filtered rows + a colour resolver, emit the ordered
  distinct-party hex list capped at 6 + overflow count) + model test; the Svelte toolbar
  renders the dots next to "N of M rows".
- Tests: model unit tests for the combined filter/sort + the dot-summary ordering/cap;
  e2e: type in search (constituency AND party), assert row count drops; click an inactive
  header, assert reorder; assert the dot cluster reflects the filtered To-winner palette.

### PR4 - Compare hero cards: glyphs + composition % + new-party filter & badge
- Add `arrow-left-right.svg` (Lucide) to `frontend/public/icons/`.
- Mirror the `StateEventHero` icon-chip pattern onto the four `CompareElections` KPI cards.
- Compute + render composition % on Flips and Holds (reading 4a; ship (a) now; the
  flip-trend variant ships separately in PR5).
- Add "New parties" filter chip + per-row "New entry -> {party}" badge; lift the existing
  `new_entries` predicate to a row flag.
- Tests: extend the KPI/derivation model with the row-level new-party flag + composition
  %; assert the icon registry includes `arrow-left-right`; e2e: select "New parties",
  assert only new-entry rows remain.

### PR5 - Flip-trend delta ("is volatility rising?")

Answers the user's reading (b): on a compare page showing From=N-1, To=N, surface whether
flipping went UP or DOWN versus the PREVIOUS transition (N-2 -> N-1). Both Citizen ("how
many seats flipped this year, and is that more than last time?") and Hans (electoral
volatility trend) get their answer.

**Validity (Hans + Citizen)**: valid and meaningful. The one caveat is comparability -
the seat set shifts across delimitation breaks, so the trend is computed on COMPARABLE
seats (constituencies present in all three events; orphans excluded, same rule the current
compare table already applies). Surface the caveat in a tooltip when the prior
transition's comparable-seat base differs materially.

**Difficulty: moderate, frontend-only, no new data.** Building blocks all exist:
- load ONE extra event - the same-body event immediately BEFORE `from` (the rail model
  already knows the full sorted sibling list, so "event before from" is a lookup);
- reuse `projectAsWinnersByEntity` + the existing winner-join to count flips for the
  prior transition (N-2 -> N-1) exactly as the page counts flips for (N-1 -> N);
- delta = flips(this) - flips(prior); render as a delta pill on the Flips KPI card
  (mirrors the StateEventHero turnout-delta pill: "+12 vs 2014" with trending-up/down
  glyph, emerald/rose tint);
- first-transition pin: when no event before `from` exists, OMIT the pill entirely
  (never render "0" or em-dash), same as the turnout-delta collapse.

**Scope guard**: PR5 reports flips(prior) vs flips(this) as a COUNT delta on comparable
seats. It does NOT introduce a new persisted metric or aggregate surface (no Hans
schema/data work); it is a third client-side projection over already-loaded winner data.
A standalone multi-election volatility series, if ever wanted, is a separate
Hans-territory proposal.

- New: extend `CompareElections` to resolve + load the pre-`from` event; a pure
  `flip-trend-model.ts` (given three winner sets, emit flips_this / flips_prior / delta /
  comparable_base) + model test.
- Tests: model unit tests (delta math, orphan exclusion, first-transition null); e2e on a
  3+-event state (TN assembly) asserting the Flips card shows the trend pill; assert the
  pill is absent on the earliest available transition.

---

## 6. Decision points for the user (resolve before PR4; PR1-PR3 can proceed)

1. **Nav rail**: RESOLVED - ship Option A (edge-fade, keep all chips). Option B (recent-N
   + Earlier) deferred until event counts approach ~20.
2. **"Change % from previous years"** (section 4b): RESOLVED - PR4 ships (a) composition %;
   PR5 ships (b) the flip-trend delta.
3. **Search scope** (section 3): RESOLVED - search matches constituency name AND party.
4. **Sort glyph** (section 3): RESOLVED - smaller default chevron, visible at rest.
5. **Compare picker scope**: RESOLVED - both mounts. The compare page DOES get the year
   picker (From/To swap) so the citizen can compare any two elections without leaving the
   page; the rail gets the "Compare" chip. Same `YearComparePicker` component, both surfaces.

No schema, data, or backend change in any PR. All four honour: discrete pills, no native
dropdown as primary control, PartyPill for party refs, pure-model extraction, ASCII-only,
section-13 browser verification, full suite green at merge.
