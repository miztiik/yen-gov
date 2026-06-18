# State-event election page polish (seat-flow, ordering, races, arc) - execution-ready plan

**Last Updated**: 2026-06-18
**Level**: 3 (cross-cutting frontend UI; 1-3 files per row; no schema / data-model / runtime change)

Surface under work: `/<state>/elections/<event>` rendered by
[frontend/src/routes/StateElection.svelte](frontend/src/routes/StateElection.svelte).
Worked example the requests came from: `http://localhost:5173/kerala/elections/general-2024`
(`body === "pc"`, 20 Lok Sabha seats).

Preamble reads (mandatory before any row): this plan, plus the two parent
plans whose contracts it amends -
[TODO/20260615-state-election-event-page-redesign-plan.md](TODO/20260615-state-election-event-page-redesign-plan.md)
(R4 IA contract) and
[TODO/20260616-state-event-page-gap-closure-plan.md](TODO/20260616-state-event-page-gap-closure-plan.md)
(G2 RacesBoard / G3 AllParties / G5 factual seat-flow). URL grammar is locked at
[docs/architecture/frontend/url-grammar.md](docs/architecture/frontend/url-grammar.md);
no row may alter it.

---

## Section 0 - Operating contract

### Why this plan exists

Eight citizen-facing polish requests were raised against the state-event page
(2026-06-18). They are all UX-layer changes (Jony + Citizen own this surface per
[CLAUDE.md](CLAUDE.md) section 0a). None touch the canonical store, schemas,
provenance, or the URL grammar. Grouped into four reviewable PR-rows below.

### Hard-coded scope (do NOT exceed)

- ONLY the state-event page surface and its directly-mounted section components.
- No change to the canonical CSV store, schemas, `manifest.json`, or any
  backend module.
- No change to the URL grammar or the `link.*` builder contract (Row 2 only
  *consumes* the existing `link.pc()` builder).
- No new data fetch, no new mart, no JSON projection (Holy Law #1, #10).

### ESCALATE triggers (STOP-AND-SURFACE per CLAUDE.md section 10)

Stop and ask the user ONLY when:

1. A Jony design call (Row 3 arc-sizing approach, Row 4 canonical heading
   treatment) cannot converge with the Citizen lens after debate -
   persona-conflict-unresolved.
2. A reorder in Row 2 would require *removing* a section the user did not ask to
   move, or would collide with the R4 IA contract test
   ([frontend/src/lib/elections/StateElection.section-order.test.ts](frontend/src/lib/elections/StateElection.section-order.test.ts))
   in a way that cannot be satisfied by updating the test to the new
   user-ratified order.
3. Any row is discovered to need a schema / URL-grammar change (it should not;
   if it does, that is Level-5 and pauses).

Everything else is in-scope autonomous work - do not pause.

### Strategy + persona rulings baked in

- **Authority**: Jony + Citizen (UX) own every row; Fowler owns the RacesBoard
  link-seam shape in Row 2 (engineering craft). Named inline per CLAUDE.md
  section 0a.
- **Jony ruling, Row 1 coupling**: same-line labels (request A) is a
  *prerequisite* for a shorter chart (request B). Shrinking chart height shrinks
  each seat-band; the current two-line stacked label (party name on one
  baseline, seat count 12px below) collides harder when bands are shorter.
  Single-line labels MUST land in the same PR as the height change. Verdict:
  bundle A + B + C into one atomic Sankey PR.
- **Jony ruling, Row 4 root cause**: the user reported the "Seat flow" heading is
  "not highlighted like constituency". Investigation shows the Seat-flow heading
  and the Constituencies-list heading use the *identical* class
  (`text-sm font-medium text-slate-700`); they are already the same. The
  sections that actually read as "highlighted" are **Races by competitiveness**
  and **All parties - directory**, which use a card wrapper
  (`rounded border border-slate-200 bg-white p-4`) plus an uppercase label
  heading (`text-sm font-semibold uppercase tracking-wide text-slate-500`). The
  real defect is that the page mixes two section-heading treatments. Verdict:
  Row 4 harmonises to ONE canonical treatment so every section reads
  consistently; the Seat-flow section is elevated to the prominent treatment.
- **Citizen lens, Row 2 ordering**: the user-ratified tail order is
  `Scatter -> Seat flow -> All parties -> Races by competitiveness -> Constituency`.
  User instruction supersedes any agent narrative preference (CLAUDE.md 0a). The
  existing G2/G3 literal assertions stay green under this order, but their intent
  comments go stale - update them.

---

## Section 1 - Status Reckoner

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| 1 | Seat-flow Sankey: single-line labels + wider/shorter + always-on (A,B,C) | [x] DONE | [#1138](https://github.com/miztiik/yen-gov/pull/1138) | M |
| 2 | Section reorder + Races-by-competitiveness for parliament (D,E,H) | [x] DONE | [#1139](https://github.com/miztiik/yen-gov/pull/1139) | M |
| 3 | ParliamentArc dynamic compact sizing for small chambers (G) | [x] DONE | [#1140](https://github.com/miztiik/yen-gov/pull/1140) | M |
| 4 | Section-heading harmonisation (F) | [x] DONE | [#1145](https://github.com/miztiik/yen-gov/pull/1145) | S-M |

Closure (2026-06-18): all 4 rows shipped via the orchestrator + subagent-PR
topology in an isolated `yen-gov-se-polish` worktree (the main repo was occupied
by a parallel agent). Per-row distillation: Row 1 collapsed the band labels to a
single `<tspan>` baseline + landscape `760x300` viewBox + removed the toggle
(oracle `StateEventCrossEventSankey.shape.test.ts`). Row 2 reordered the tail and
relaxed the Races gate to admit PC, with a Fowler `hrefFor` seam on RacesBoard
(`link.pc` for parliament). Row 3 extracted `parliament-arc-geometry.ts` (pure,
since no @testing-library/svelte) and scaled radii by
`clamp(sqrt(total_seats/140),0.3,1)` so small chambers are compact while TN-234
stays byte-identical. Row 4 harmonised all 10 section `<h2>` to
`text-sm font-semibold text-slate-800`; the Section-13 computed-style smoke
caught a 9th section (`AllianceTotals`, a shared component) the source audit
missed, fixed via an optional `headingClass` prop that keeps NationalElection
byte-identical. Durable lessons in repo memory `yen-gov-ship-and-state-event.md`.

Phasing / dependency: Row 4 re-touches files owned by Row 1
(`StateEventCrossEventSankey.svelte`) and Row 2 (`StateElection.svelte`), so Row
4 ships LAST. Rows 1, 2, 3 are mutually independent (disjoint files) and may ship
in any order; the ship loop runs them serially regardless.

Request -> Row map: A,B,C -> Row 1; D,E,H -> Row 2; G -> Row 3; F -> Row 4.

---

## Section 2 - Row 1: Seat-flow Sankey readability + shape + always-on

Requests A (squished seat numbers on one line), B (wider, less tall), C (remove
the "Hide seat flow" toggle).

### Scope

In [frontend/src/lib/elections/StateEventCrossEventSankey.svelte](frontend/src/lib/elections/StateEventCrossEventSankey.svelte):

1. **A - single-line band labels.** Today each band draws TWO `<text>` nodes: the
   party label at `y = b.y + b.h/2`, the seat count at `y = b.y + b.h/2 + 12`
   (font-size 9, slate-500). Collapse to ONE baseline: party name then the seat
   count as a muted suffix on the same line (e.g. `INC 15` with the count in a
   lighter weight/colour via a `<tspan>` so it stays one `<text>` element). Left
   column stays `text-anchor="end"`, right column `text-anchor="start"`; both
   read `name count`.
2. **B - wider, shorter.** The chart height is NOT set directly: the SVG is
   `viewBox="0 0 {W} {H}"` (currently `W=620`, `H=380`) with
   `class="h-auto w-full"`, so rendered height = container-width x (H/W) =
   container-width x 0.61. Lower the aspect ratio so the same column renders a
   shorter chart. Jony to pick exact values; target landscape ratio
   `W/H >= 2.2` (e.g. `W=760`, `H=300`). Keep `PAD_Y`, `COL_W`, `LEFT_X`,
   `RIGHT_X` consistent with the new `W`.
3. **C - remove the toggle.** Delete the `expanded` state, the
   `<button data-testid="state-event-seat-flow-toggle">` ("Hide seat flow" /
   "Show seat flow"), and the `{#if expanded}` gate; the diagram renders
   unconditionally (it is shown by default already - the toggle is pure chrome).

### Files touched

- [frontend/src/lib/elections/StateEventCrossEventSankey.svelte](frontend/src/lib/elections/StateEventCrossEventSankey.svelte) (component).
- [frontend/e2e/state-event-view.spec.ts](frontend/e2e/state-event-view.spec.ts) - remove/replace the two assertions that drive `state-event-seat-flow-toggle` (lines ~416, ~476); the diagram is now always present, so assert the diagram testid is visible without a toggle click.
- New/updated vitest contract test (oracle below).

### Jony tuning note (resolve in-row, no user pause)

Very thin 1-seat bands can still crowd their single-line label vertically when
adjacent bands are close. Acceptable mitigations, Jony's choice: a minimum
label-slot gap, or suppress the numeric count on sub-threshold bands (name only),
or a faint leader offset. Do NOT reintroduce two-line stacking.

### Acceptance gates

- `bun --cwd=frontend run test` green; `bun --cwd=frontend run build` green.
- e2e `state-event-view.spec.ts` green with the toggle assertions retired.
- Section 13 browser smoke on `/kerala/elections/general-2024`: labels read on
  one line, chart is visibly wider-than-tall, no toggle button, no new console
  `[error]` / `404`.

### ONE load-bearing oracle

A vitest source-contract test on `StateEventCrossEventSankey.svelte` asserting all
three at once: (a) the file contains NO `state-event-seat-flow-toggle` testid and
NO `Hide seat flow` / `Show seat flow` string; (b) the parsed `W` and `H`
constants satisfy `W / H >= 2.2` (landscape); (c) the band-count `<text>` no
longer uses the `+ 12` vertical offset (single-line proof). Re-injecting any of
the three flips the test RED in <10ms.

---

## Section 3 - Row 2: Section reorder + Races-by-competitiveness for parliament

Requests D (seat flow above constituency), E (all-parties above constituency),
H (Races-by-competitiveness for parliament, placed between all-parties and
constituency).

### Scope

1. **Reorder the template tail** in
   [frontend/src/routes/StateElection.svelte](frontend/src/routes/StateElection.svelte)
   from the current
   `Scatter -> [Races ac-only] -> Constituency -> Seat flow -> All parties`
   to the user-ratified
   `Scatter -> Seat flow -> All parties -> Races -> Constituency`.
   Mechanical move of the `<StateEventCrossEventSankey>`, `<StateEventAllParties>`,
   the Races `<section>`, and `<StateEventConstituencyList>` blocks; no prop
   changes.
2. **Enable Races for parliament (request H - assessed EASY-MEDIUM).** The
   `races_rows` derivation is gated `body !== "ac" ? []` (StateElection.svelte
   ~line 491); relax to also admit `body === "pc"`. Every field it maps
   (`eci_no`, `entity_name`, `margin_pct`, `turnout_pct`, `winner_age`,
   `winner_candidate_name`, `symbol_asset_path`, `brand_colour_hex`) is already
   present on PC winner rows. Relax the template gate
   `{#if body === "ac" && ...}` to `{#if (body === "ac" || body === "pc") && ...}`.
3. **PC link seam in RacesBoard (Fowler ruling).** [frontend/src/lib/RacesBoard.svelte](frontend/src/lib/RacesBoard.svelte)
   line ~250 hardcodes `href={link.ac(state_code, r.name, event)}`. For
   parliament it must use `link.pc(...)` (exists at
   [frontend/src/lib/links.ts](frontend/src/lib/links.ts#L245); note the arg
   order differs: `link.ac(state, name, event)` vs
   `link.pc(state, event, slug)`, and `link.pc` expects an already-slugged PC
   name). Fowler verdict: pass an explicit `hrefFor: (row) => string` callback
   prop from `StateElection.svelte` (which knows `body`) rather than threading a
   `body` discriminator into RacesBoard - keeps RacesBoard presentational and
   body-agnostic. Default the prop to the current `link.ac` behaviour so the
   `/<state>` overview call site is unchanged.

### Files touched

- [frontend/src/routes/StateElection.svelte](frontend/src/routes/StateElection.svelte) (reorder + races gate + hrefFor wiring).
- [frontend/src/lib/RacesBoard.svelte](frontend/src/lib/RacesBoard.svelte) (optional `hrefFor` prop with `link.ac` default).
- [frontend/src/lib/elections/StateElection.section-order.test.ts](frontend/src/lib/elections/StateElection.section-order.test.ts) (new order asserts; refresh G2/G3 intent comments).
- [frontend/e2e/state-event-view.spec.ts](frontend/e2e/state-event-view.spec.ts) (assert RacesBoard present on a `general-*` event + new visual order).

### Acceptance gates

- Existing G2 (`RacesBoard` before constituency list) and G3 (`AllParties` after
  Sankey) literal assertions stay green under the new order; their stale intent
  comments are refreshed.
- `/<state>` overview RacesBoard links still resolve to AC pages (default prop
  path unchanged) - re-run the StateOverview tests.
- Section 13 browser smoke on `/kerala/elections/general-2024`: order is
  Seat flow -> All parties -> Races -> Constituency; Races rows link to PC
  seat pages (`/kerala/elections/general-2024/<pc-slug>`), not AC pages.

### ONE load-bearing oracle

Extend `StateElection.section-order.test.ts` with a single new test asserting the
template index order `Sankey < AllParties < RacesBoard < ConstituencyList` AND
that the Races mount gate string admits `pc` (i.e. the template contains
`body === "ac" || body === "pc"` adjacent to the `state-event-races-board`
testid). Reverting either the reorder or the gate flips it RED.

---

## Section 4 - Row 3: ParliamentArc dynamic compact sizing

Request G ("Seats won" semicircle is sparse; size dynamically instead of always
using the default full width).

### Root cause (verified)

[frontend/src/lib/ParliamentArc.svelte](frontend/src/lib/ParliamentArc.svelte)
fixes `W=720`, `H=380`, `r_inner=140`, `r_outer=340` as constants and renders
`class="w-full h-auto"`. A 20-seat chamber (Kerala LS) therefore draws the SAME
full-width semicircle as a 234-seat chamber (Tamil Nadu AC), just with fewer,
larger dots - hence the sparse, stretched look. `dot_radius` already scales with
spacing, but the arc *footprint* does not scale with seat count.

### Scope (Jony rules the approach - resolve in-row via debate, no user pause)

Make the arc footprint scale with `total_seats` so small chambers render a
compact semicircle. Three candidate approaches for Jony + Citizen to converge on:

- **Option A (cap rendered width)**: keep the geometry, wrap the SVG in a
  container whose `max-width` scales with `total_seats` (e.g. clamp between a
  small-chamber min and the current full width), centred. Lowest-risk; leaves the
  234-dot reconciliation math untouched.
- **Option B (scale radii)**: derive `r_outer` / `r_inner` (and the `rows`
  heuristic floor) from `total_seats` so few-seat arcs use a smaller radius and
  sit compact inside the viewBox. Higher fidelity, but must preserve the E5
  invariant gate the 234-dot layout depends on.
- **Option C (derive viewBox W)**: compute `W` from `total_seats` (clamped) so
  the aspect ratio itself tightens for small chambers; pair with a CSS
  `max-width`.

Jony default recommendation absent stronger Citizen signal: **Option A** (cap +
centre) - it is the smallest, most reversible change and cannot regress the
large-chamber layout. Document the chosen option inline in the component.

### Files touched

- [frontend/src/lib/ParliamentArc.svelte](frontend/src/lib/ParliamentArc.svelte).
- The ParliamentArc invariant/unit test (the 234-dot reconciliation gate) - keep
  green; add the small-chamber compactness assertion.

### Acceptance gates

- The existing 234-dot reconciliation invariant stays green (no regression at TN
  scale).
- `bun --cwd=frontend run test` + build green.
- Section 13 smoke: `/kerala/elections/general-2024` "Seats won" arc reads
  compact (dots closer together, arc not stretched edge-to-edge);
  `/tamil-nadu/elections/assembly-2021` (234 seats) unchanged.

### ONE load-bearing oracle

A vitest asserting the rendered horizontal dot-span (max dot `x` - min dot `x`,
or the effective arc width) for `total_seats = 20` is materially smaller than for
`total_seats = 234` - e.g. `span(20) <= 0.7 * span(234)`. Today both are ~equal
(full width); the row is correct only when the small chamber is provably
compacter. The large-chamber span and the 234-dot count must be unchanged.

---

## Section 5 - Row 4: Section-heading harmonisation

Request F (the "Seat flow" section title is not highlighted like the prominent
sections).

### Root cause (verified)

The election page mixes two section-heading treatments:

- **Plain** (`text-sm font-medium text-slate-700`, bare `<section>`): the map
  ("Constituencies"), "Top parties by seats", "Seats won", the constituency list
  ("Constituencies (N)"), and "Seat flow: where each seat moved". The Seat-flow
  heading is byte-identical to the Constituencies-list heading today.
- **Card label** (`text-sm font-semibold uppercase tracking-wide text-slate-500`
  inside `rounded border border-slate-200 bg-white p-4`): "Races by
  competitiveness" and "All parties - directory".

So the Seat-flow heading is not actually different from "Constituencies"; the
visible "highlight" the user perceives belongs to the card sections.

### Scope (Jony rules the canonical treatment - resolve in-row, no user pause)

Pick ONE canonical section-heading treatment for the state-event page and apply
it so every top-level section reads consistently, with the Seat-flow section
elevated to the prominent treatment. Jony default: adopt the card-label
treatment (the Races / All-parties style) as the canonical "section divider" for
the secondary analytical sections (Seat flow, Seats won, and any other plain
ones that should read as peers), OR, if Citizen finds the all-caps label too
heavy for every section, standardise on a single slightly-stronger plain heading
(e.g. `text-sm font-semibold text-slate-800`) applied uniformly. Converge to ONE
verdict; do not leave two styles.

### Files touched (depends on Jony verdict; superset)

- [frontend/src/lib/elections/StateEventCrossEventSankey.svelte](frontend/src/lib/elections/StateEventCrossEventSankey.svelte) (Seat-flow heading - minimum).
- [frontend/src/routes/StateElection.svelte](frontend/src/routes/StateElection.svelte) ("Seats won" inline heading).
- Other bare-heading section components as needed for consistency
  (`StateEventMap.svelte`, `StateEventPartyComposite.svelte`,
  `StateEventConstituencyList.svelte`) - only if the verdict is page-wide.
- A vitest heading-consistency contract test (oracle below).

### Acceptance gates

- `bun --cwd=frontend run test` + build green.
- Section 13 smoke on `/kerala/elections/general-2024`: the Seat-flow heading is
  visually prominent and consistent with the chosen canonical treatment; no
  section is left in the orphaned old style.

### ONE load-bearing oracle

A vitest contract test asserting every top-level state-event section `<h2>`
resolves to the SINGLE canonical heading class string (read each section
component's source / the route template). Two distinct heading-class strings in
the set flips it RED - proving the page no longer mixes treatments.

---

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

## See also

- [CLAUDE.md](CLAUDE.md) - authority table (section 0a), correction levels (section 6), anti-patterns (section 10), UI verification (section 13).
- [TODO/20260615-state-election-event-page-redesign-plan.md](TODO/20260615-state-election-event-page-redesign-plan.md) - R4 IA contract this surface inherits.
- [TODO/20260616-state-event-page-gap-closure-plan.md](TODO/20260616-state-event-page-gap-closure-plan.md) - G2/G3/G5 contracts amended by Row 2.
- [docs/architecture/frontend/url-grammar.md](docs/architecture/frontend/url-grammar.md) - locked URL grammar (Row 2 consumes `link.pc`).
- [docs/how-to/ship-a-pr.md](docs/how-to/ship-a-pr.md) - the PR lifecycle the EXECUTION BLOCK references.
