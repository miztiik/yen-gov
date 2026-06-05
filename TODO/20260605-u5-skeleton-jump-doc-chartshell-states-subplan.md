# U5 sub-plan - Skeleton + IndicatorJump + IndicatorDoc route + ChartShell error/empty/loading slots

**Last Updated**: 2026-06-05
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk U5
**Status**: IN-FLIGHT (spawned 2026-06-05; first sub-row IN-FLIGHT alongside spawn PR)
**Authority**: Jony (loading-state craft + jump-strip metaphor + doc page IA) / Gregor (URL grammar contract for `/docs/indicator/:topic/:id`) / Citizen (mobile ~360px jump strip comprehension + the trust banner on the doc page) per CLAUDE.md section 0a

---

## Why this exists

Parent chunk U5 reads as one row in the parent Execution Ledger but expands into four distinct deliverables plus a closure: (a) `Skeleton.svelte` (generic loading primitive) + `ChartShell` error/empty/loading slots folded into the EXISTING shell per parent section 23.5; (b) `url.indicatorDoc(id)` builder + `/docs/indicator/:topic/:id` route + ONE generic `IndicatorDoc.svelte` reading catalogue + render hints + provenance (never hand-authored per indicator) per parent section 20.12; (c) `IndicatorJump.svelte` (sticky theme-chip jump strip with scroll-spy + type-to-filter, mobile-first ~360px) per parent section 20.12 + integration into `StateOverview` (the state route); (d) closure (distil into `docs/architecture/frontend/design-system.md` per-component-migration U5 row; flip the parent U5 ledger row -> MERGED; archive this sub-plan under `docs/archive/plans/`).

Per CLAUDE.md correction-level discipline (>= 4 files structural -> propose breakdown first) and parent plan section 24.5, the right shape is a thin parent row + this sub-plan. Precedents: U1 (4 sub-rows, PRs #714 / #716 / #718 / #720), U2 (4 sub-rows, PRs #739 / #742 / #745 / #747), B1 (7 sub-rows, PRs #629-#670), B2a (8 emits + closure, PRs #673-#688). The kickoff prompt explicitly named the same 4-way split ("U5a: Skeleton + ChartShell error/empty/loading slots; U5b: url.indicatorDoc + /docs/indicator/:id route + IndicatorDoc.svelte; U5c: IndicatorJump.svelte + integration into state route; U5d: closure").

---

## Scope

### In scope (this sub-plan)

1. `frontend/src/lib/Skeleton.svelte` (NEW) - generic loading skeleton primitive. Props: `width`, `height`, `rounded`, `cls`. Calm shimmer animation that respects `prefers-reduced-motion` (collapses to a soft pulse). Sized via props or via the parent's layout (the default `width: 100%; height: 4rem;` is a sensible card-sized default). Reads from existing tokens (`--surface-sunken`, `--line`, `--r-md`, `--dur`).
2. `frontend/src/lib/Skeleton.test.ts` (NEW) - vitest unit covering the size-style helper (`skeletonStyle({width, height}) -> "width: ...; height: ...;"`). No DOM render (vitest is node-env per `/memories/lessons.md`); the module-scope export pattern from `GeoBreadcrumb.svelte`'s `computeCrumbs` is the template.
3. `frontend/src/lib/charts/ChartShell.svelte` (EDIT) - add 4 new state branches in the body section (per parent section 23.5: "Error/empty states fold into the existing `ChartShell` (U5), no new component"):
   - `state: "loading"` -> renders `<Skeleton />` in the body
   - `state: "error"` -> renders `<p>Data unavailable</p>` + an optional `source_line` slot (the caller supplies the source line for the citizen to know which publisher failed)
   - `state: "empty"` -> renders a small inline SVG diagonal-stripe hatch swatch + `<p>No data for this selection.</p>` (the no-data visual language already used in `OrderedCategoryBar.ocb__hatch` + `HorizontalGroupedBar.hgb__cell-hatch` + `FacetPanelGrid.fpg__hatch`; we inline a small pattern in ChartShell rather than minting a new shared `HatchPattern.svelte` for one caller)
   - `state: "data"` (default) -> renders the `children` snippet as today
   
   The header (title + subtitle + toolbar + honesty banners) and footer (sources + actions) render UNCHANGED across all 4 states - the chrome stays consistent, only the body content shifts (the central UX point of the rational chart-viz doctrine in parent section 21.9).

4. `frontend/src/lib/charts/chart-shell/state.ts` (NEW) - pure module-scope helpers consumed by the new ChartShell state branches:
   - `type ChartShellState = "loading" | "error" | "empty" | "data"`
   - `DEFAULT_ERROR_MESSAGE = "Data unavailable"`
   - `DEFAULT_EMPTY_MESSAGE = "No data for this selection."`
   - `resolveChartShellState(state: ChartShellState | null | undefined): ChartShellState` -> defaults to `"data"`; the canonical place a renderer's null state is normalised so the shell never branches on undefined.
5. `frontend/src/lib/charts/chart-shell/state.test.ts` (NEW) - vitest unit covering the state resolver + the default-message constants (~6 cases, mirrors the `actions.test.ts` shape).
6. `frontend/src/lib/charts/chart-shell/index.ts` (EDIT) - re-export the new state helpers + the `ChartShellState` type.
7. `frontend/src/lib/url.ts` (EDIT) - add `url.indicatorDoc(indicatorId)` builder:
   ```ts
   indicatorDoc(indicatorId: string): string {
     return withBase(`/docs/indicator/${indicatorId}`);
   },
   ```
   The `indicatorId` is the catalogue's natural `<topic>/<id>` form (e.g. `fiscal/outstanding_debt_pct_gsdp`); no URL-encoding needed because both segments are kebab-snake slug chars. Documented in the JSDoc.
8. `frontend/src/lib/url.test.ts` (EDIT) - add ~3 round-trip assertions for `url.indicatorDoc`:
   - `url.indicatorDoc("fiscal/outstanding_debt_pct_gsdp")` -> `/docs/indicator/fiscal/outstanding_debt_pct_gsdp`
   - URL prefix `/docs/indicator/` is stable
   - never URL-encodes the slash (it is a path separator, not an opaque token)
9. `frontend/src/main.ts` (EDIT) - register `/docs/indicator/:topic/:id` route binding to `IndicatorDoc.svelte`:
   ```ts
   {
     pattern: "/docs/indicator/:topic/:id",
     component: IndicatorDoc,
     parse: ({ topic, id }) => ({ indicator_id: `${topic}/${id}` }),
   },
   ```
   4-segment pattern, distinct from every existing route (`/docs` literal + 2 indicator-id segments); order not load-bearing.
10. `frontend/src/routes/IndicatorDoc.svelte` (NEW) - the ONE generic indicator-documentation route per parent section 20.12. Reads the catalogue (`fetchTopicCatalogue()`), the indicator render hints (`fetchGrapherIndicatorCatalogue()`), and the indicator artifact (`fetchIndicator()` via `indicatorPathForArtifact()`). Renders: title + description (one-paragraph), methodology / definition + base-year notes, source (4 fields per parent section 7: `owner`, `title`, `vintage`, `url` - bend the legacy `SourceRef[]` shape into the 4-field display until the B2a/B2b cutover lands `entities/source.csv`), cadence + staleness (via `indicator.cadence` for the cadence text; the `update_period_days` field from parent section 20.10 / variables.csv is not yet emitted, so the section is "soon" with a TODO marker per the kickoff prompt's BLOCKED carve-out), caveats (`methodology.known_caveats[]` if present, else `indicator.notes`), download (a direct static link to the indicator file: `<a href={path} download>`).
11. `frontend/src/routes/IndicatorDoc.test.ts` (NEW) - vitest unit covering the pure formatter helpers (citizen-readable cadence label, source-line projection from `SourceRef[]` -> `{owner, title, vintage, url}`). No route-mount test (no jsdom).
12. `frontend/src/lib/IndicatorJump.svelte` (NEW) - sticky theme-chip jump strip per parent section 20.12. Props: `groups: ReadonlyArray<{ id: string; label: string; icon?: string }>` (one chip per topic / section); `current?: string` (the active id, controlled by the parent via scroll-spy). Renders: a horizontally-scrollable row of pill chips with active highlight + a thin type-to-filter input above. Scroll-spy is via a pure helper that maps `scrollY` + section-offsets -> active id (the helper is the testable surface; the actual `IntersectionObserver` wiring lives in the Svelte `$effect`). Mobile-first ~360px: chips wrap or scroll horizontally; the filter input is full-width above the chip row.
13. `frontend/src/lib/IndicatorJump.test.ts` (NEW) - vitest unit covering:
    - `filterGroups(groups, query) -> filtered groups` (case-insensitive substring match on `label`; empty query -> all groups)
    - `activeIdForOffsets(scrollY, offsets) -> id | null` (returns the id whose offset is the largest one <= scrollY; null when no group's offset is <= scrollY)
14. `frontend/src/routes/StateOverview.svelte` (EDIT) - mount `<IndicatorJump groups={...} current={...} />` at the top of the indicator sections block (above the `{#each indicator_topics as topic}` loop). The `groups` derive from `indicator_topics` (id, title, icon). Scroll-spy `current` updates via an `IntersectionObserver` on each topic section's wrapper element. Mounts on top of the existing layout - no other layout shift.
15. `docs/architecture/frontend/design-system.md` (EDIT, U5d only) - flip the per-component-migration U5 row from `TODO` to `MERGED #N`; add a brief distillation paragraph for the loading/error/empty surfaces + the doc-page IA + the jump-strip metaphor.
16. `TODO/20260603-data-and-charting-platform-reset-plan.md` (EDIT) - flip U5 row from `TODO` to `DEFERRED-TO-SUBPLAN` in the spawn PR; stamp PR#s for U5a..U5d as each lands; flip to `MERGED` at U5d closure.
17. `git mv TODO/20260605-u5-skeleton-jump-doc-chartshell-states-subplan.md docs/archive/plans/20260605-u5-skeleton-jump-doc-chartshell-states-subplan.md` at U5d closure.

### Out of scope (other parent chunks)

- **U4**: chart switcher (`SegmentedControl` + `ChartShell` toolbar + `feasibleAt()` + grapher JSON migration). MERGED #748 + #750.
- **B***, **F***, **X1a/b**, **YA**: backend + data cutover (independent). U5 is pure frontend chrome.
- **The data layer for `update_period_days`** (parent section 20.10): the new column lands on `variables.csv` in B2a, which is part of the B-track. U5's `IndicatorDoc.svelte` carries a TODO marker for the cadence + staleness section (`update_period_days`-driven banner) per the kickoff carve-out; the marker becomes a real banner once B2a/B2b emit the column.
- **The 4-field provenance display from `entities/source.csv`** (parent section 7): same shape - the source line on `IndicatorDoc` uses `SourceRef[]` (the legacy `{url, fetched_at}` shape with `owner` / `title` / `vintage` extracted from sibling metadata where available) until B2a lands the canonical CSV; then F1/X1a re-points the read path. The TODO marker is the cutover seam.
- **Sibling-jump popover on the jump strip** (the trailing `v` from `GeoBreadcrumb` U2b - parent section 20.12 references "scroll-spy, IDP grid metaphor"): the jump strip ships with scroll-spy + type-to-filter only. A peer / sibling popover is not in parent section 20.12's scope for the jump strip - that affordance lives on the breadcrumb (deferred there in U2b too).
- **The (i) link from ChartShell title to `/docs/indicator/<id>`** mentioned in parent section 21.8: the URL builder + route + page ship in U5b; the `(i)` glyph on the ChartShell title is the JOB OF every renderer that has an indicator id to link to, and is added in the renderer-by-renderer migration that follows U5d (NOT scope of U5b). The route is reachable by direct URL today; the `(i)` link on each chart is the per-renderer migration step.
- **Theme-drawer integration of IndicatorJump** (parent section 20.12: "reused by state page + theme drawer"): U5c integrates ONLY into the state route. The theme-drawer surface does not exist yet (U2 shipped the left-drawer chrome but no theme grid inside it); when the drawer's theme grid lifts in a later sub-plan, that sub-plan REUSES the `IndicatorJump` component shipped here. No duplication.

---

## Sub-row Execution Ledger

| Sub-row | Blocks on | Parallel-OK with | Gate | PR# | Status |
| --- | --- | --- | --- | --- | --- |
| U5-spawn (this file + parent ledger flip to DEFERRED-TO-SUBPLAN; U5a flipped IN-FLIGHT inline) | - | - | docs-review | #751 | MERGED |
| U5a Skeleton + ChartShell error/empty/loading slots + state helpers + tests | U5-spawn | U5b, U5c | build+vitest(skeleton, chart-shell-state) | #752 | MERGED |
| U5b url.indicatorDoc + `/docs/indicator/:topic/:id` route + IndicatorDoc.svelte + tests | U5-spawn | U5a, U5c | build+vitest(url, indicator-doc)+in-browser smoke (`/docs/indicator/fiscal/outstanding_debt_pct_gsdp`) | #755 | MERGED |
| U5c IndicatorJump.svelte + StateOverview integration + tests | U5-spawn | U5a, U5b | build+vitest(indicator-jump)+in-browser smoke (`/s/tamil-nadu`) | #757 | MERGED |
| U5d closure (distil into design-system.md U5 row; flip parent U5 ledger; archive this sub-plan) | U5a, U5b, U5c | - | docs-review | _pending_ | IN-FLIGHT |

U5a, U5b, U5c are all parallel-OK with each other (Skeleton + IndicatorDoc + IndicatorJump touch disjoint files; ChartShell.svelte edits are only in U5a; url.ts + main.ts edits are only in U5b; StateOverview.svelte edits are only in U5c). U5d is closure.

---

## Per-sub-row notes

### U5a Skeleton + ChartShell error/empty/loading slots + state helpers + tests

**Files (~6, ~250 LOC including tests):**

- `frontend/src/lib/Skeleton.svelte` (NEW, ~50 LOC): single presentation leaf with a `<script lang="ts" module>` block exporting `skeletonStyle({ width?, height? })` (returns the inline-style string) so vitest can cover the size resolution without mounting. Props: `width = "100%"`, `height = "4rem"`, `rounded = true`, `cls = ""`. The shimmer is a CSS `@keyframes` animation that respects `prefers-reduced-motion`:
  ```css
  .yen-skeleton {
    background: var(--surface-sunken);
    border-radius: var(--r-md);
    position: relative;
    overflow: hidden;
  }
  .yen-skeleton::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.6), transparent);
    transform: translateX(-100%);
    animation: yen-shimmer var(--dur, 200ms) cubic-bezier(0.4,0,0.2,1) infinite;
    animation-duration: 1500ms;
  }
  @keyframes yen-shimmer { 100% { transform: translateX(100%); } }
  @media (prefers-reduced-motion: reduce) {
    .yen-skeleton::after { animation: none; }
    .yen-skeleton { opacity: 0.7; }
  }
  ```

- `frontend/src/lib/Skeleton.test.ts` (NEW, ~30 LOC): import `skeletonStyle` from the module block; 3 cases (default props, custom width/height, omitted dims).

- `frontend/src/lib/charts/chart-shell/state.ts` (NEW, ~40 LOC): pure module with `ChartShellState` type + `DEFAULT_ERROR_MESSAGE` + `DEFAULT_EMPTY_MESSAGE` + `resolveChartShellState()`.

- `frontend/src/lib/charts/chart-shell/state.test.ts` (NEW, ~50 LOC): ~6 cases (resolveChartShellState defaults to "data" for null / undefined / empty-string-coerced cases; passes through valid states; default messages are non-empty strings).

- `frontend/src/lib/charts/chart-shell/index.ts` (EDIT, +3 LOC): re-export the new state helpers.

- `frontend/src/lib/charts/ChartShell.svelte` (EDIT, ~+60 LOC): import the new state helpers + Skeleton; add `state?: ChartShellState` + `error_message?: string | null` + `source_line?: string | null` props; replace the body block with a state-discriminated render. Header + footer are UNCHANGED so the chrome stays consistent in every state. Inline the diagonal-stripe SVG pattern for the empty state (using `--ink-muted` + `--surface-sunken`).

**Gate**: build + vitest (`Skeleton.test.ts` + `state.test.ts` pass) + svelte-check.

**Risk**: low. Skeleton is a leaf; ChartShell edits are purely additive (no caller passes `state` today, so every existing ChartShell consumer keeps rendering its `children` block unchanged because the default state is `"data"`).

### U5b url.indicatorDoc + `/docs/indicator/:topic/:id` route + IndicatorDoc.svelte + tests

**Files (~5, ~300 LOC including tests):**

- `frontend/src/lib/url.ts` (EDIT, +12 LOC): new `indicatorDoc(indicatorId)` builder + JSDoc. The slash inside `indicatorId` is preserved (not URL-encoded) because the catalogue keys natively use `<topic>/<id>` as a 2-segment slug pair; the router pattern `/docs/indicator/:topic/:id` matches against that 2-segment form.

- `frontend/src/lib/url.test.ts` (EDIT, +20 LOC): 3 new assertions covering the round-trip + slash-preservation invariant + base-URL prefix.

- `frontend/src/main.ts` (EDIT, +8 LOC): register the new route + import `IndicatorDoc`.

- `frontend/src/routes/IndicatorDoc.svelte` (NEW, ~180 LOC): the ONE generic route. Reads:
  - `fetchTopicCatalogue()` to resolve the indicator id to its catalogue artifact (so the page knows the topic title + the catalogue-level display label).
  - `fetchGrapherIndicatorCatalogue()` for `chart_type` + `renderer_rules` (surfaced under "How this is shown").
  - `fetchIndicator(indicatorPathForArtifact({ kind: "indicator", id: indicator_id }))` for the artifact body (title, description, methodology, sources, license, coverage).
  
  Renders:
  - `<ChartShell>` with `state="loading"` until both fetches resolve; `state="error"` on fetch failure; `state="data"` once loaded (the doc page uses the same loading + error chrome the chart cards use - one consistency contract).
  - Title (`indicator.title`).
  - Description (`indicator.description` if present, else `indicator.description_short`).
  - Methodology block: `methodology.definition` + each `methodology_breaks[]` row + `methodology.known_caveats[]`.
  - Sources block (4-field projection): each `sources[]` row rendered as `owner | title | vintage | url` where `owner` is heuristically derived from `methodology.publisher` (fall back to `-`), `title` from `methodology.publisher_methodology_url`'s domain (fall back to the URL), `vintage` from `methodology_vintage` or `sources[].fetched_at`, `url` from `sources[].url`. A `<p class="text-xs text-slate-500"><strong>Provenance display will switch to <code>entities/source.csv</code> 4-field shape once chunk B2a lands (parent plan section 7).</strong></p>` TODO marker is rendered to surface the cutover honestly.
  - Cadence + staleness: prints `indicator.cadence` if present (e.g. "annual_fy"); the staleness banner driven by `update_period_days` is a `// TODO: lift update_period_days from variables.csv once B2a lands (parent plan section 20.10)` marker - no banner ships in U5b.
  - Download link: a direct static link `<a href={indicator_path} download>Download JSON</a>` so a citizen / researcher can grab the source file.

- `frontend/src/routes/IndicatorDoc.test.ts` (NEW, ~80 LOC): vitest unit covering the pure helpers exported from the route's `<script module>` block:
  - `projectToFourFieldSource(SourceRef, methodology) -> { owner, title, vintage, url }` - the source-projection helper.
  - `cadenceLabel(cadence) -> citizen-readable string` (e.g. `"annual_fy"` -> `"Annual (financial year)"`).

**Gate**: build + vitest + svelte-check + in-browser smoke on `/docs/indicator/fiscal/outstanding_debt_pct_gsdp`.

**Risk**: low-medium. The route is new (no existing callers); the source-projection is a clean leaf helper; the only seam is the `IndicatorDoc.svelte` -> `fetchIndicator()` path (well-trodden).

### U5c IndicatorJump.svelte + StateOverview integration + tests

**Files (~4, ~280 LOC including tests):**

- `frontend/src/lib/IndicatorJump.svelte` (NEW, ~140 LOC): module-scope `<script lang="ts" module>` exporting `filterGroups()` + `activeIdForOffsets()` so vitest covers the logic without mounting. The Svelte component wires:
  - a text `<input>` filter at the top (bound to a local `$state` query)
  - a horizontally-scrollable chip row (one chip per remaining group)
  - an `IntersectionObserver` (created in `$effect`, torn down on unmount) on each section element identified by the parent's `<section data-jump-id="<id>">` markup
  - `current` is passed in as a `$bindable` so the parent can also drive it (e.g. on initial mount); the `IntersectionObserver` mutates it as the user scrolls.
  - Tap on a chip scrolls smoothly to the matching `data-jump-id` section.
  
  Mobile-first: chips wrap or scroll horizontally with `overflow-x-auto`; the filter input is full-width above the chip row.

- `frontend/src/lib/IndicatorJump.test.ts` (NEW, ~80 LOC): vitest unit covering:
  - `filterGroups(groups, query)`: empty query -> all groups; case-insensitive match on label; substring (not prefix); returns empty array on no match.
  - `activeIdForOffsets(scrollY, offsets)`: returns the id whose offset is the largest <= scrollY; null when scrollY < every offset; ties broken by FIRST occurrence (stable).

- `frontend/src/routes/StateOverview.svelte` (EDIT, ~+20 LOC): import `IndicatorJump`; derive `groups` from `indicator_topics` (id, title, icon); mount `<IndicatorJump groups={groups} bind:current={active_topic_id} />` immediately above the `{#each indicator_topics as topic}` block; add `data-jump-id={topic.id}` to each `<section>` wrapper inside the each block so the IntersectionObserver knows what to watch.

**Gate**: build + vitest (`IndicatorJump.test.ts` passes) + svelte-check + in-browser smoke on `/s/tamil-nadu` (confirm: jump strip renders above the indicator sections; tap a chip scrolls smoothly; filter input narrows the chip set).

**Risk**: low. New leaf primitive; integration is one mount + one `data-jump-id` attribute per existing section.

### U5d closure (distil into design-system.md; flip parent ledger; archive sub-plan)

**Files (~3, ~80 LOC):**

- `docs/architecture/frontend/design-system.md` (EDIT, ~+30 LOC):
  - In the Per-component migration table, flip U5 row from `TODO` to `MERGED #<U5a>+#<U5b>+#<U5c>`.
  - Add a sub-section `### U5 - Skeleton + IndicatorJump + IndicatorDoc + ChartShell states (PRs #N / #N / #N)` distilling the 4 surfaces in one paragraph: loading state via shimmer Skeleton (tokens: `--surface-sunken`, `--r-md`, `--dur`); error / empty states folded into ChartShell so chrome stays consistent; one generic `IndicatorDoc.svelte` route reading catalogue + render + provenance (never hand-authored per indicator); sticky `IndicatorJump` strip with scroll-spy + filter (mobile-first ~360px).

- `TODO/20260603-data-and-charting-platform-reset-plan.md` (EDIT, ~+2 LOC):
  - Flip U5 row from `DEFERRED-TO-SUBPLAN` to `MERGED` and stamp PR# (the U5d PR #).
  - Add the same `(sub-plan archived at ...; four sub-rows ...; distilled into ...)` footnote U2/U1 use.

- `git mv TODO/20260605-u5-skeleton-jump-doc-chartshell-states-subplan.md docs/archive/plans/20260605-u5-skeleton-jump-doc-chartshell-states-subplan.md`.

- Within the moved file: rewrite outbound paths (parent plan reference: `(20260603-...)` -> `(../../../TODO/20260603-...)`; CLAUDE.md if cited: `(../CLAUDE.md)` -> `(../../../CLAUDE.md)`; sibling archived sub-plans + docs paths). Per `/memories/lessons.md` U2d closure rule: grep `\]\(([^)]+\.md)\)` on the moved file, categorise destinations by depth-change, rewrite in one batch.

- Append a `## Sub-plan complete (YYYY-MM-DD)` block immediately BEFORE the See-also section (per `/memories/lessons.md`: order matters) with per-row PR distillation map (Row | PR | Distilled output | Note). Plus a 1-paragraph pointer to `/memories/lessons.md` naming the lesson topics captured during U5a/b/c sessions.

**Gate**: docs-review (no code).

**Risk**: trivial. Doc-only closure PR.

---

## Gates catalogue (operational definitions)

- `build` = `bun run build` in `frontend/` exits 0, no warnings.
- `vitest(<file>)` = `bun run test <file>` exits 0, all cases pass.
- `svelte-check` = `bun run check` exits 0, no errors.
- `in-browser smoke` = `bun --cwd frontend run dev` then `open_browser_page` + `read_page` per CLAUDE.md section 13 on the named route; confirm no NEW `[error]` console events vs main, no new 404s, the new surface renders as designed.

---

## See also

- [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) sections 20.12 (IndicatorJump + IndicatorDoc bullets), 22.2 (U5 row), 23.5 (error/empty fold-into-ChartShell), 22.3 (per-chunk DoD).
- [docs/architecture/frontend/design-system.md](../docs/architecture/frontend/design-system.md) - the token home U5 components consume from; the per-component-migration table U5d flips.
- [docs/archive/plans/20260604-u1-tokens-fonts-subplan.md](../docs/archive/plans/20260604-u1-tokens-fonts-subplan.md) - precedent for the 4-sub-row-then-closure shape (U1).
- [docs/archive/plans/20260605-u2-breadcrumb-drawer-district-subplan.md](../docs/archive/plans/20260605-u2-breadcrumb-drawer-district-subplan.md) - precedent for the 4-sub-row-then-closure shape (U2) + the module-scope helper pattern (`computeCrumbs` is the testable surface).
- [CLAUDE.md](../CLAUDE.md) sections 6 (correction levels - this sub-plan is the Level-2/3 escalation of parent chunk U5), 13 (UI verification), 14 (test coverage policy).
