# Elections off MapLibre + map UX polish + census_code_2011 enrichment

**Last Updated**: 2026-06-11
**Level**: 4 (PR-4 + PR-5 + PR-6 are structural; multi-file; cross-cutting renderer migration that retires a dependency)
**Authority spine**: Jony + Citizen (UX, scroll-zoom, +/-/home controls, Lakshadweep visibility), Fowler (deletion discipline for MapLibre + pmtiles), Hans + Max (census_code_2011 sidecar property on boundary topology), Gregor (renderer-seam contract during transition).
**Status**: READY-FOR-DISPATCH. Wave A (PR-alpha + PR-1 + PR-2 + PR-3) dispatches in 4 parallel sub-worktrees; PR-4 -> PR-5 sequential; PR-6 closes the deletion.

---

## Preamble - binding doctrine

This plan executes (i) the deferred d3-geo-everywhere ruling from [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) section 14.5, (ii) three orthogonal map-UX wins, and (iii) corrects two factual mistakes from the prior turn's investigation.

### User-corrected mistakes from preceding investigation (2026-06-11)

1. **"ToS / scraping" comment on Bharat Pashudhan - withdrawn.** It is a government public-data site (DAHD / NDLM) serving citizens. Public information served to citizens carries no scraping prohibition for a citizen-facing tool that exists for the same audience. The devtools-block dialog is UX friction, not a permission boundary. Their published topology is fair to research + reuse.
2. **"Bharat Pashudhan has no map" - wrong.** The user-provided 2026-06-11 screenshot proves a state-level India choropleth on `/keyStatistics?key=1&pageLabel=Pashu%20Aadhaar%20Issued`. My earlier sweep stopped at the landing page and got blocked by the SPA's devtools-detection dialog before the keyStatistics route hydrated. PR-alpha re-investigates properly and produces a receipt with the actual topology endpoint + reusability verdict.

### User mandate (intent in agent-authored neutral prose)

- Move elections off MapLibre to d3-geo - top priority (closes section 14.5).
- Disable `cooperativeGestures` so scroll-wheel zooms without Ctrl; add +/-/home button trio (IndiaVotes + Bharat Pashudhan parity).
- Enrich district topology with `census_code_2011` sidecar property so Census-2011-keyed datasets join without code.
- Rewrite stale [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md) which still names MapLibre as primary.
- Lakshadweep MUST be visible at national zoom (NOT auto-zoom callout per user). Render a minimum-size dot marker when the polygon collapses to sub-pixel.
- Chronic-red `parties-symbol-asset.test.ts` is being fixed by a parallel agent in worktree `yen-gov-party-symbol-fix` on branch `fix/party-symbol-assets-functional-contract` (SHA `14099746c`). OUT OF SCOPE for this plan - do NOT collide.

### Binding documents

- [CLAUDE.md](../CLAUDE.md) - Holy Laws #1 (static-first), #4 (docs = memory), #5 (structural fixes only), #8 (open source first); section 0a authority table; section 13 UI verification (mandatory for every frontend runtime change).
- [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) section 14.5 - the deferred d3-geo-everywhere ruling this plan executes (election surfaces are the only remaining MapLibre consumers).
- [docs/concepts/citizen-first.md](../docs/concepts/citizen-first.md) - citizen-experience supremacy over implementation novelty; Lakshadweep visibility is a citizen-trust requirement.
- [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md) - stale; PR-2 rewrites.

### Authority dispatch (CLAUDE.md section 0a)

| Question | Authority | Verdict baked in |
|---|---|---|
| Renderer for elections | Fowler + Gregor (section 14.5 already settled) | d3-geo SVG + d3-zoom. No new debate. |
| Scroll-zoom UX | Jony + Citizen | `cooperativeGestures: false` on MapLibre (interim PR-1) + remove altogether in PR-4/5. Add +/-/home button trio. |
| Lakshadweep visibility | Jony + Citizen | Render a minimum-size dot marker (~12-14 px radius) at the path centroid when path bbox is sub-threshold. NO auto-zoom callout (user mandate). |
| `census_code_2011` enrichment | Hans + Max (user pre-approved per 2026-06-11 message) | Additive sidecar property on `datasets/boundaries/in/districts/all.topojson`. Source: data-analytics.github.io map.json (Census 2011 districts, 641 features, `censuscode` + `st_cen_cd` keys). Post-2011 child districts inherit parent's Census code (multiple LGD -> same Census code is the correct semantic for "Census 2011 didn't know about this split"). |
| Drop maplibre-gl / pmtiles | Fowler | After PR-4 + PR-5 cover all consumers. PR-6 deletes `frontend/src/lib/maplibre/` + the two npm deps. |

---

## Scope-change ledger

| Row | Date | Intent | signoff |
|---|---|---|---|
| (none) | - | - | - |

---

## Section 1 - Status Reckoner

| Row | Title | Status | PR | Effort |
|---|---|---|---|---|
| PR-alpha | Pashu Aadhaar re-investigation receipt (research-only; corrects last turn's wrong claim) | `[ ] PENDING` | - | XS (~20 min) |
| PR-1 (B) | MapChoropleth: `cooperativeGestures=false` + add +/-/home zoom controls | `[ ] PENDING` | - | S (~1h) |
| PR-2 (E) | Rewrite `docs/architecture/frontend/map.md` - d3-geo primary, MapLibre deprecated | `[ ] PENDING` | - | XS (~30 min) |
| PR-3 (F) | Enrich `datasets/boundaries/in/districts/all.topojson` with `census_code_2011` sidecar property | `[ ] PENDING` | - | M (~2h) |
| PR-4 (D-1 + A) | `IndiaMap.svelte` -> d3-geo SVG with pan/zoom/home + Lakshadweep dot marker | `[ ] PENDING` | - | M (~3h) |
| PR-5 (D-2) | `StateAcMap.svelte` -> d3-geo SVG with pan/zoom + AC highlight + drill-down | `[ ] PENDING` | - | M (~3h) |
| PR-6 (D-3) | Drop `maplibre-gl` + `pmtiles` deps; delete `frontend/src/lib/maplibre/` | `[ ] PENDING` | - | XS (~30 min) |

### Wave shape

- **Wave A** (parallel-safe, file-disjoint): PR-alpha (browser-only research, no worktree) + PR-1 (`MapChoropleth.svelte` only) + PR-2 (`map.md` only) + PR-3 (backend tools + topology + schema; zero frontend touches). 4 parallel sub-worktrees.
- **Wave B** (sequential; both touch election renderers): PR-4 -> PR-5.
- **Wave C** (after Wave B): PR-6 (mechanical deletion).

---

## Section 2 - Per-row spec

### PR-alpha - Pashu Aadhaar re-investigation receipt

**Scope.** Research-only. No code. Re-open `https://bharatpashudhan.ndlm.co.in/keyStatistics?key=1&pageLabel=Pashu%20Aadhaar%20Issued` properly (last turn stopped at the landing page; the keyStatistics route is where the map renders). Wait for full SPA hydration. Dismiss the devtools-block dialog if it appears (Playwright `click_element` on the "Ok" button - it does not actually block research, just shows a modal). Then probe:

- Renderer used: d3 / leaflet / maplibre / hand-rolled SVG / canvas. (`window.L`, `window.maplibregl`, `window.d3`, `.leaflet-container`, `.maplibregl-map`, etc.)
- Topology file URL via `performance.getEntriesByType('resource')` filter on `*.json` / `*.geojson` / `*.topojson`.
- Topology shape: feature count, property keys, Lakshadweep / Ladakh / Telangana presence, vintage indicator.
- Verdict: reuse-as-is / merge-with-ours / keep-ours-and-borrow-property.

**Files touched.** Zero. PR body IS the receipt.

**Acceptance gate.** PR body answers all 4 probe questions with concrete evidence (URLs, snippet of feature properties, screenshot of map area).

**Oracle.** A successful `page.evaluate(async () => fetch(<topology URL>))` returning a parseable JSON with `Lakshadweep` in features.

**Effort.** XS (~20 min by Explore subagent).

---

### PR-1 (B) - Scroll/zoom UX polish on MapChoropleth

**Scope.** Single component edit + 3 UI buttons. Interim fix for live users while PR-4/PR-5 ship the structural migration.

**Files touched.**

- `frontend/src/lib/maplibre/MapChoropleth.svelte`:
  - Line ~552 `cooperativeGestures: true` -> `cooperativeGestures: false`.
  - Update the inline comment at lines 546-551 to record the verdict change with date and cross-link to this plan.
  - Add 3 absolutely-positioned `<button>` elements over the map container: `+` (zoom in: `map.zoomIn()`), `-` (zoom out: `map.zoomOut()`), `home`/`⌂` (reset: `map.fitBounds(initialBounds)` or `map.flyTo(initialCenter, initialZoom)`). Style with Tailwind: small white circular buttons stacked vertically, bottom-right corner, slate-200 border, hover slate-100.

**Acceptance gates.**

1. svelte-check: 0 new errors vs baseline.
2. vitest unchanged.
3. build green.
4. Browser smoke per CLAUDE.md section 13:
   - Open a route mounting `MapChoropleth` (state election page, e.g. `/maharashtra/elections/general-2024` or whatever maps onto NationalElection.svelte today).
   - Hover map, send `page.mouse.wheel(0, -100)`; assert map zoom level INCREASES (no Ctrl required).
   - Click `+` button; assert zoom increases. Click `home` button; assert returns to initial view.
   - Console errors: 0 new.

**Oracle.** Playwright assertion that wheel-scroll over the map changes `map.getZoom()` (not the page scroll position).

**Effort.** S (~1h). One Svelte file edit + 1 Playwright test addition.

---

### PR-2 (E) - Doc rewrite for map.md

**Scope.** Rewrite [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md) so "Library" section names d3-geo SVG as the primary renderer for ALL choropleths (welfare + election), citing section 14.5 of the umbrella plan. Note MapLibre as DEPRECATED - retained only until PR-6 lands. Keep the boundary-pipeline + sources-resolver sections (those are still correct). Update the component descriptor table to reflect the actual current files (post-PR-4 + PR-5 component names; record in present-progressive form).

**Files touched.** [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md) only.

**Acceptance gates.**

1. ASCII-only per CLAUDE.md section 5 (use `-`, `->`, `>=`, etc.).
2. Cross-links resolve (Test-Path each relative path before commit).
3. `git grep -i "Library: MapLibre GL JS" docs/architecture/frontend/map.md` returns 0 (the old primary-library line is gone) AND `git grep -i "d3-geo" docs/architecture/frontend/map.md` returns >= 2 (new primary-renderer section + components table reference).

**Oracle.** The "Library" section reads as a single coherent ruling: d3-geo primary, MapLibre deprecated, section 14.5 cited.

**Effort.** XS (~30 min).

---

### PR-3 (F) - census_code_2011 enrichment

**Scope.** Add Census-2011 district codes as a sidecar property on every feature in `datasets/boundaries/in/districts/all.topojson`. Source: the Census 2011 topology at `https://data-analytics.github.io/Choropleth_India_Map/map.json` (641 features carrying `censuscode` + `st_cen_cd` + `st_nm` + `district` properties). Join key: normalized `(state_name, district_name)` against our LGD districts. Where Census 2011 does not know about post-2011 bifurcations (Telangana 2014, Ladakh 2019, Tamil Nadu Mayiladuthurai 2020, etc.), the new LGD child districts inherit the parent's `census_code_2011` value - multiple LGD -> same Census code is the correct semantic for "Census 2011 was published before this split" and supports lossless join-back to any Census-2011 indicator.

**Files touched.**

- `tools/boundaries/enrich_census_code_2011.py` (NEW) - standalone Python script (no `backend/` import per `tools/` rule). Downloads map.json (or reads it from a cached local snapshot under `datasets/_ops/`), normalizes names via lower-case + strip-punct + space-strip, joins by `(state_norm, district_norm)` against the on-disk districts topology, writes `datasets/boundaries/in/districts/census_code_2011.json` as `{ "<dist_lgd>": <census_code> }` AND a `coverage.json` reporting % matched + unmatched districts.
- `tools/boundaries/build.py` or `tools/topojson/convert_layer.py` (whichever currently emits `districts/all.topojson`) - merge the sidecar map: when emitting each feature, look up `census_code_2011 = sidecar.get(str(feature.properties.dist_lgd))` and set `feature.properties.census_code_2011 = code or null`.
- `datasets/schemas/boundary-layers.schema.json` (or whichever schema covers district feature properties) - additive minor bump: `census_code_2011: integer | null`. New changelog entry in same commit.
- `datasets/boundaries/in/districts/all.topojson` - regenerate with the new property.
- `frontend/src/contracts/boundaries-conform.test.ts` - add assertion: >= 600 / 785 district features carry a non-null `census_code_2011` (95%+ coverage; post-2011-bifurcation slack is the residual).

**Acceptance gates.**

1. Tier-A backend pytest: no new failures.
2. boundaries-conform.test.ts Tier-A: new census_code_2011 coverage assertion passes.
3. Manual spot-check: load topology in Node, find Tamil Nadu's Chennai district by `dist_lgd`, assert `census_code_2011 == 603` (Census 2011 known value).

**Oracle.** `(features with non-null census_code_2011) / (total features) >= 0.95`. Coverage report committed at `datasets/_ops/census-code-2011-coverage.json` enumerates the residual unmatched districts (all should be post-2011 bifurcations).

**Effort.** M (~2h).

---

### PR-4 (D-1 + A) - IndiaMap to d3-geo with pan/zoom/home + Lakshadweep visibility

**Scope.** Replace `frontend/src/lib/maplibre/IndiaMap.svelte` with a d3-geo SVG implementation. Create new component `frontend/src/lib/charts/IndiaPartyMap.svelte` (NOT inside `maplibre/`). Preserve EVERY feature the current component has, plus add what the user-named comparison sites have:

**Must preserve (current functionality):**

- Per-state fill from the leading-party palette via `loadIndiaLeadingParties` loader (unchanged signature).
- Hover tooltip: state name + top-3 party seats + event id (HTML overlay positioned at the mouse).
- Click state polygon -> `navigate(link.state(eci_code))`.

**Must add (user-named gaps):**

- Pan/zoom via `d3.zoom().on("zoom", e => g.attr("transform", e.transform))`. Scroll-wheel zooms WITHOUT Ctrl. Touch drag pans. Pinch zooms.
- Absolute-positioned button trio over the SVG: `+` / `-` / `home`. Wire to `svg.transition().call(zoom.scaleBy, 1.5)` / `0.667` / `zoom.transform, identity`.
- Lakshadweep + Chandigarh + Daman & Diu / Puducherry / A&N (any UT whose polygon bbox < 14px in either dimension at the chosen viewBox) get a SECOND render pass: `<circle r=7>` at the path's `geoCentroid()` projected coordinate, with the SAME fill + the SAME tooltip + the SAME click handler. This is the "small-shape marker overlay" - NO auto-zoom callout per user mandate. The circle is the citizen's clickable target when the polygon is sub-pixel.

**Files touched.**

- `frontend/src/lib/charts/IndiaPartyMap.svelte` (NEW) - the d3-geo replacement. Re-uses `GeoChoropleth.svelte`'s projection scaffolding pattern where helpful but is a standalone component (election-mode has hover tooltips + party palette which welfare-mode does not).
- `frontend/src/routes/Home.svelte` - one-line swap: `import IndiaMap from "../lib/maplibre/IndiaMap.svelte"` -> `import IndiaPartyMap from "../lib/charts/IndiaPartyMap.svelte"` and the tag swap.
- `frontend/src/lib/charts/IndiaPartyMap.test.ts` (NEW) - assert (a) 36 paths rendered for 36 states, (b) sub-threshold paths get a circle marker, (c) Lakshadweep circle present + clickable + correct color, (d) pan/zoom state transitions: `zoom.scaleBy(svg.node(), 2)` doubles the zoom level state.
- `frontend/src/lib/maplibre/IndiaMap.svelte` - **NOT deleted** in this PR (PR-6 deletes); kept on disk so any other consumer still works during the transition.

**Acceptance gates.**

1. svelte-check 0 new errors.
2. New IndiaPartyMap.test.ts passes (~6-8 vitest cases).
3. vitest full: no regression.
4. build green.
5. Browser smoke per CLAUDE.md section 13:
   - Open Home `/?theme=election` -> the new `IndiaPartyMap` renders 36 states.
   - Sweep the bottom-left ocean area as in the last investigation; assert >= 1 "Lakshadweep" tooltip hit (current MapLibre live map returns 0; THIS IS THE LOAD-BEARING ORACLE).
   - Hover any mainland state -> tooltip with party totals.
   - `page.mouse.wheel(0, -200)` over map -> SVG zoom transform increases.
   - Click `+` button -> zooms in.
   - Click `home` button -> returns to initial bounds.
   - Click any state polygon (e.g. Tamil Nadu) -> navigates to `/tamil-nadu`.
   - Console errors: 0 new.
6. Screenshot for the PR body: Lakshadweep dot visible at default zoom.

**Oracle.** Playwright sweep returns >= 1 "Lakshadweep" tooltip hit (vs 0 on current live MapLibre map). This proves the visibility fix landed.

**Effort.** M (~3h). The largest single PR in this plan.

**Note.** This PR also corrects the prior plan's wrong "DELIVERED" Lakshadweep claim. Reference [docs/archive/plans/20260611-home-page-citizen-experience-plan.md](../docs/archive/plans/20260611-home-page-citizen-experience-plan.md) PR-0 receipt - the receipt's "DELIVERED 2026-06" verdict was technically true (topojson contains Lakshadweep + renders without geometry-null errors) but failed the citizen-visibility test. PR-4 here is the actual citizen-visibility fix.

---

### PR-5 (D-2) - StateAcMap to d3-geo with pan/zoom + highlight

**Scope.** Same pattern as PR-4 but for the AC-level state map. Replace `frontend/src/lib/maplibre/StateAcMap.svelte` -> `frontend/src/lib/charts/StateAcMapD3.svelte`. Preserve AC drill-down highlight (focused AC at full opacity, others at 18%, focused AC outlined slate-900 2.5 px), margin-based opacity per AC, click-to-drilldown navigation. Same pan/zoom/home controls as PR-4.

**Files touched.**

- `frontend/src/lib/charts/StateAcMapD3.svelte` (NEW).
- `frontend/src/routes/NationalElection.svelte` - swap import (MapChoropleth -> probably IndiaPartyMap for the national surface; or check if NationalElection uses StateAcMap separately).
- Any other route that imports StateAcMap (grep + swap; expected: state election pages).
- `frontend/src/lib/charts/StateAcMapD3.test.ts` (NEW).

**Acceptance gates.** Same DoD shape as PR-4 but exercised on TN AC map (234 ACs):

1. All 234 ACs render with correct party-coloured fills.
2. Clicking an AC drills down to constituency page.
3. `highlight_eci_no` prop dims all others.
4. Scroll-wheel zooms without Ctrl.
5. Buttons work.
6. Console errors 0.

**Oracle.** Playwright opens TN AC map; clicks AC ECI 1; asserts navigation to constituency page AND the highlighted-mode mini-map on the constituency page paints AC 1 at full opacity + others at 18%.

**Effort.** M (~3h).

---

### PR-6 (D-3) - MapLibre deletion

**Scope.** After PR-4 + PR-5 land:

- `frontend/package.json` - remove `maplibre-gl: ^4.7.1` and `pmtiles: ^3.2.1` from `dependencies`. Regenerate `bun.lock` in same commit (CLAUDE.md section 9 DoD).
- Delete `frontend/src/lib/maplibre/` directory entirely (after grep confirms zero remaining imports).
- Update any stale doc cross-link still pointing into `frontend/src/lib/maplibre/`.

**Files touched.** Many deletes; 1 package.json edit; 1 bun.lock regen.

**Acceptance gates.**

1. `git grep -i "maplibre\|pmtiles" frontend/src` returns 0 hits.
2. `bun install --frozen-lockfile` succeeds with the regenerated lock.
3. `bun run build` green; `dist/assets/maplibre-*.js` absent.
4. svelte-check 0 new errors.
5. Bundle size dropped by ~230 KB gzipped (the maplibre chunk).

**Oracle.** Build dist directory: no `maplibre-*` chunk file present.

**Effort.** XS (~30 min).

---

## Section 3 - Closure ritual

After PR-6 merges:

1. Append `## Plan complete` stanza with per-row distillation pointers.
2. `git mv TODO/20260611-elections-off-maplibre-and-map-ux-plan.md docs/archive/plans/`.
3. Retarget all `../` links to `../../../` (same shape as the prior plan's closure).
4. Distill durable doctrine into [docs/architecture/frontend/map.md](../docs/architecture/frontend/map.md) (PR-2 already rewrites the foundation; closure adds the post-PR-4/5/6 component descriptors).
5. Update [docs/archive/plans/20260611-home-page-citizen-experience-plan.md](../docs/archive/plans/20260611-home-page-citizen-experience-plan.md) with a "Correction note: PR-4 of the 2026-06-11 follow-on plan is the actual Lakshadweep citizen-visibility fix; the prior PR-0 receipt's 'DELIVERED' verdict was geometry-only and failed the citizen-visibility test."

---

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it" / "ship runSubagent", execute as the ORCHESTRATOR:

1. **Orchestrator + subagent-PR topology.** Main agent owns the Status Reckoner; each row dispatches to a stateless `runSubagent` brief embedding row scope, files, gates, oracle. Use the DEFAULT agent for implementation rows (file edits + terminal + git). Use the `Explore` agent ONLY for PR-alpha (research). Persona agents (Fowler / Hans / Max / Jony / Citizen / Gregor) are ADVISOR-only - never dispatch them for implementation work (per user-memory `Fowler-persona subagent has no edit/terminal tools`).
2. **One row = one PR = one branch.** Master parks on `scratch-master-parking-2026-06-10` so no worktree owns `main` (clean `gh pr merge`). Author per [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md): 2-commit-then-squash, 5-gate DoD, mandatory browser smoke (`open_browser_page` + `read_page` + `screenshot_page`) for every frontend runtime change per CLAUDE.md section 13.
3. **Ship loop, non-stop.** Merge each row as gates green; sync master; teardown worktree. Pre-existing chronic-red items (the parallel agent's parties-symbol-asset work; 14 baseline svelte-check errors; 3 baseline 404s) are NOT gating - document the baseline, do not block.
4. **Tests ship with the row.** No new mocks unless asked.
5. **Manage context via offload.** Push research / audits into Explore subagents.
6. **Post-merge hygiene.** `gh pr merge --squash --admin --delete-branch`; cosmetic `'main' is already used by worktree` warning is expected - manually `git push origin --delete <branch>` after. Prune `: gone` local branches.
7. **Stop only at a real boundary.** STOP-AND-SURFACE per CLAUDE.md section 10 when a user-named source/instruction would be silently downgraded.
8. **Wave A parallelism.** PR-alpha + PR-1 + PR-2 + PR-3 dispatch in 4 PARALLEL `runSubagent` calls (file-disjoint; each gets its own sub-worktree except PR-alpha which is browser-only).
9. **Wave B sequential.** PR-4 -> PR-5 sequential because both transition election surfaces (PR-4 swaps Home; PR-5 swaps state pages); shared mental model + a single Playwright spec coverage.
10. **PARALLEL-AGENT AWARENESS.** Worktree `yen-gov-party-symbol-fix` is owned by another agent. Do not touch the chronic-red `parties-symbol-asset.test.ts` or `frontend/public/party-symbols/*.svg` in any of this plan's PRs. The master worktree currently shows an unrelated `M frontend/public/party-symbols/unverified.svg` modification - that is also other-agent WIP; never `git add .` / `-A`.

---

## See also

- [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) - section 14.5 deferred ruling this plan executes.
- [docs/archive/plans/20260611-home-page-citizen-experience-plan.md](../docs/archive/plans/20260611-home-page-citizen-experience-plan.md) - prior plan; PR-0 Lakshadweep receipt is corrected by PR-4 here.
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - 5-gate DoD.
- [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md) - closure ritual.
- [docs/concepts/citizen-first.md](../docs/concepts/citizen-first.md) - citizen-visibility supremacy.
- [CLAUDE.md](../CLAUDE.md) - engineering contract.
