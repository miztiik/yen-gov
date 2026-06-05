# F2a.5 sub-sub-plan - CategoryBar mode="diverging" + composition-bar migration

**Last Updated**: 2026-06-05
**Parent sub-plan**: [TODO/20260605-f2a-categorybar-consolidation-subplan.md](20260605-f2a-categorybar-consolidation-subplan.md) sub-row F2a.5
**Grandparent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk F2a
**Status**: TODO (sub-sub-plan spawned 2026-06-05 after F2a.3+F2a.4 #782 closed)
**Authority**: Fowler (deletion safety + experiment-cookie smoke) / Jony (chart-ergonomics) / Gregor (composition-bar/ package fate) per CLAUDE.md section 0a

---

## Why this sub-sub-plan exists

Parent F2a.5 reads as one row in the F2a sub-plan ledger: "composition-bar -> CategoryBar mode='diverging' + production migration". My pre-implementation audit (PR #782 follow-on) discovered three substantive deviations from the F2a sub-plan's blast-radius assumption that warrant their own design framing:

1. **The blast radius is much smaller than the parent sub-plan claimed.** The parent listed `IndicatorChoropleth` (923 LOC) / `IndicatorRanked` (474 LOC) / `IndicatorSmallMultiples` (227 LOC) / `StackedTrendV2` (805 LOC) as composition-bar consumers. **None of them import `composition-bar/`.** The actual consumer surface is `frontend/src/lib/CompositionBar.svelte` (252 LOC; the renderer that wraps `composition-bar/helpers` + `composition-bar/types`) mounted at exactly ONE production site: `routes/StateOverview.svelte`. (`StackedTrendV2.svelte` is consumed by `ElectionSeatsTrend.svelte` + `StackedTrendArtifact.svelte`, neither of which is composition-bar-related.)

2. **The single production mount is experiment-gated.** The CompositionBar mount in `StateOverview.svelte` (line 781) is wrapped in `{#if composition_bar_in_treatment && composition_bar_loaded}` - the `composition-bar/experiment-definition.json` Phase 3.6(c) A/B rollout cookie. **Default §13 smoke on `/s/tamil-nadu` will NOT mount it**, so a naive smoke is a silent false-green. F2a.5b's §13 gate must set the experiment cookie before navigating.

3. **The composition-bar/ package is a real adapter library, not just a renderer's private VM.** 805 LOC across 9 files: adapter (506) + helpers (141) + types (125) + tests + fixtures + experiment-definition.json. The adapter consumes loaded DuckDB rows and produces the `CompositionBarModel` view-model (analogous to `bar-view-models/` for ranked and `multi-dim-view-models/` for stacked). **It SHOULD be lifted, not retired**, to a more general home (e.g. `lib/charts/diverging-view-models/` or kept at `lib/charts/composition-bar/` if the name still reads cleanly).

These three findings together push F2a.5 across the threshold for a sub-sub-plan per the parent F2a sub-plan's directive: "If F2a.5 grows beyond one PR... spawn a sub-sub-plan F2a.5 with per-consumer rows per parent section 24.5."

Per CLAUDE.md section 24.5 + the established U / B / F sub-plan pattern.

## Scope

In scope: the three surfaces above. Each is a separate PR with its own branch, its own gate, and its own §13 smoke.

Out of scope (deliberately deferred):
- Closure (F2a.6 in the parent sub-plan) — blocks on F2a.5.3 completing.

## Sub-row Execution Ledger

| Sub-row | Blocks on | Gate | PR# | Status |
| --- | --- | --- | --- | --- |
| F2a.5.1 Add `mode="diverging"` body to `CategoryBar.svelte` (lift body byte-identical from `frontend/src/lib/CompositionBar.svelte`; consume `CompositionBarModel` from `composition-bar/types`; ChartShell wrap moves INSIDE the diverging body because the model carries `label` + `subtitle` + `honesty_banners` + `caption_fptp` that the existing top-level wrap_in_shell mechanism doesn't surface). Update DevChartsSandbox with a synthetic `CompositionBarModel` demo. NO production-route touch. | - | vitest + sandbox-render-smoke on `/dev/charts-sandbox` | #784 | MERGED |
| F2a.5.2 Production migration: flip the `CompositionBar` import in `StateOverview.svelte` to use `CategoryBar mode="diverging"`. CompositionBar.svelte deleted (option b per recommendation; git rename detection preserves blame). Playwright `composition-bar-mount.spec.ts` selectors updated to `[data-component="category-bar"][data-mode="diverging"]`. §13 smoke uses `?yg_variant=treatment` URL override (auto-sets `yg_variant_chart-composition-bar-election-seats` cookie via bucket.ts readOverride) against `/s/karnataka` (in targeting list S05/S07/S29/S10; TN excluded). Cookie-name + override mechanism verified against `frontend/src/lib/experiments/bucket.ts` lines 222-244 before drafting smoke. | F2a.5.1 | section 13 in-browser smoke with `?yg_variant=treatment` override + svelte-check + vitest (CategoryBar tests still pass) | _pending_ | IN-FLIGHT |
| F2a.5.3 `composition-bar/` package decision: per the audit, this package is an adapter library worth keeping. Decide and act on one of: (a) KEEP at `lib/charts/composition-bar/` and rename the README to clarify "diverging-bar adapter package, consumed by CategoryBar mode='diverging'"; (b) RENAME the folder to `lib/charts/diverging-bar/` to align with the CategoryBar mode name; (c) split the renderer-orphan (anything that referenced the deleted CompositionBar.svelte) into a separate module. Recommend (a) - minimal churn, blame-history preserves, new README clarifies the contract. | F2a.5.2 | docs-review + svelte-check + vitest (adapter tests still pass) | _pending_ | TODO |

Parallel-safe groups: F2a.5 is SERIAL (each row depends on the previous one's API surface).

## Per-sub-row notes

### F2a.5.1 mode="diverging" body

Body lift surface:
- Source: `frontend/src/lib/CompositionBar.svelte` 252 LOC. The `<ChartShell>...</ChartShell>` block (~150 LOC) lifts verbatim into a `divergingBody` snippet inside `CategoryBar.svelte`.
- Helper: `projectSegments` from `lib/charts/composition-bar/helpers` (called inside the body to project segments onto the 0..100 axis with the tiny-segment lift).
- Type: `CompositionBarModel` from `lib/charts/composition-bar/types`. The discriminated-union `DivergingProps` flips from `unknown` to this concrete type.

ChartShell-wrap structural decision: the existing `wrap_in_shell` mechanism uses `chart_title` + `chart_subtitle` from props. The diverging mode's title/subtitle/banners/caption all live on the `model`. **Cleanest:** the diverging body always wraps itself in ChartShell internally (mirrors CompositionBar.svelte's structure); the top-level `wrap_in_shell` mechanism is bypassed for mode="diverging". Document this in the JSDoc on `wrap_in_shell`.

Sandbox demo: synthetic `CompositionBarModel` with 3-4 segments (e.g. fuel mix coal/gas/hydro/renewable with hex fills) so reviewers see the bar + legend + segment math render correctly.

### F2a.5.2 production migration

Touched files:
- `frontend/src/routes/StateOverview.svelte` line 37 (import flip) + line 781 (`<CompositionBar />` -> `<CategoryBar mode="diverging" />`)
- `frontend/src/lib/CompositionBar.svelte` (DELETE per recommendation b)

§13 cookie-setup recipe (mandatory in the PR body):

**Correction note (F2a.5.2 pre-flight audit, 2026-06-05):** the F2a.5 sub-sub-plan body originally proposed a `composition_bar=on` cookie recipe AND used `/s/tamil-nadu` as the smoke route. BOTH were wrong against the actual experiment machinery in `frontend/src/lib/experiments/bucket.ts`:

1. **Cookie name + value:** there is no `assignment_cookie` field in `experiment-definition.json`. The override mechanism (`bucket.ts:readOverride`) reads `?yg_variant=<variation_id>` from the URL on first hit and persists it to a per-experiment cookie `yg_variant_<experiment_id>` (where `experiment_id = "chart-composition-bar-election-seats"`). Variation ids are `"control"` and `"treatment"`.
2. **Targeting state:** `experiment-definition.json` `single-party-dominant-states.condition.state_code.$in = ["S05","S07","S29","S10"]`. Tamil Nadu is **S22** and is **explicitly excluded** per plan R-02 (alliance-led verdict; party-only chart misframes it). Hitting `/s/tamil-nadu` with `?yg_variant=treatment` would return `null` from `bucketForWithOverride` and NEVER mount the chart. **Karnataka (`/s/karnataka` = S10)** is the existing smoke state in `frontend/e2e/composition-bar-mount.spec.ts`; reuse it.

Correct §13 recipe:
```js
// URL-override path - one navigation, cookie auto-persisted by bucket.ts
await page.goto('http://localhost:5173/s/karnataka?yg_variant=treatment');
await page.waitForLoadState('networkidle');
// Verify the new mount renders:
//   [data-component='category-bar'][data-mode='diverging']
// Verify the old mount is GONE:
//   [data-component='composition-bar']
// Verify the SeatDonut sibling still renders (regression guard).
```

Golden-render: capture DOM HTML for the diverging mount BEFORE the migration (current main, with cookie set) and AFTER (this PR's branch). Diff must show ONLY the wrapper element change (composition-bar -> category-bar) + the new `data-mode="diverging"` attribute; segment count, fills, share percentages, legend labels, caption_fptp must match byte-identical.

### F2a.5.3 composition-bar/ package fate

Recommend KEEP at current path + README rewrite. The package's `assembleCompositionBar` adapter + `CAPTION_FPTP` constant + `loadCompositionBarElectionSeats` loader are real production logic; deleting them just to move files is gratuitous churn.

README rewrite explains:
- This package is the diverging-bar VM toolkit (analogous to `bar-view-models/`, `multi-dim-view-models/`, `time-view-models/`).
- The renderer that consumes it lives in `lib/charts/CategoryBar.svelte` mode="diverging".
- Adapter / helpers / types / fixtures are the stable contract surface; downstream callers (election-seats adapter, future fuel-mix adapter) import from the package barrel.

## Contract invariants (inherited from parent F2a sub-plan)

1. **Behaviour-preserving** at the citizen surface. §13 smoke + golden-render gate enforces.
2. **Strangler-fig topology** - each PR independently revertable.
3. **No new data-layer touches** - this is structural / renderer-engine only.
4. **Production routes get cookie-aware §13 smoke** - F2a.5.2 specifically. Default smoke is insufficient.
5. **No mocks at the renderer seam** - vitest stays on VM-shape contracts; DOM lives in Playwright / §13 smoke.

## Tracking

The parent F2a sub-plan row F2a.5 is `DEFERRED-TO-SUB-SUB-PLAN -> TODO/20260605-f2a-5-diverging-mode-subsubplan.md` in this PR. Sub-row status updates land inside each F2a.5.x PR per parent section 24.3.

## See also

- Parent sub-plan: [TODO/20260605-f2a-categorybar-consolidation-subplan.md](20260605-f2a-categorybar-consolidation-subplan.md) F2a.5 row
- Grandparent plan: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) sections 22.5 (Execution Ledger), 23.5 (file-level ripple corrections; **NB: parent's blast-radius bullet for F2a was inaccurate** - composition-bar/ consumers do NOT include the production trio IndicatorChoropleth/Ranked/SmallMultiples).
- Prior F2a sub-rows: F2a.1+F2a.2 = PR #781 (ranked), F2a.3+F2a.4 = PR #782 (stacked).
- Strangler-fig precedent: yen-gov PR #78 ([/memories/patterns.md](../../../memories/patterns.md) "Strangler-fig pre-stage").
