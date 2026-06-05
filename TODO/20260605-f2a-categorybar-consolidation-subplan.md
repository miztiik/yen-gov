# F2a sub-plan - CategoryBar consolidation

**Last Updated**: 2026-06-05
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk F2a
**Status**: IN-FLIGHT (spawned 2026-06-05 after F3 #779 + F1.2 #778 unblocked the F-track session)
**Authority**: Fowler (deletion safety + strangler-fig topology) / Jony (chart-ergonomics) per CLAUDE.md section 0a

---

## Why this exists

Parent chunk F2a reads as one row in the parent Execution Ledger (22.5) - "CategoryBar merge (structural)". But the actual delivery is **SIX distinct surfaces** that each need their own diff + gate (strangler-fig per [/memories/patterns.md](../../../memories/patterns.md) PR #78 doctrine):

1. **`CategoryBar.svelte` core component**: a new single renderer accepting `mode={"ranked" | "stacked" | "diverging"}`. Pure Svelte; consumes the existing view-model shapes (`OrderedCategoryBarViewModel`, `GroupedBarViewModel`, `CompositionBarModel`) via a discriminated-union prop.
2. **`OrderedCategoryBar` migration -> `CategoryBar mode="ranked"`**: the V2 orphan renderer (196 LOC) imported ONLY by `routes/DevChartsSandbox.svelte`. The sandbox is updated, not preserved.
3. **`HorizontalGroupedBar` migration -> `CategoryBar mode="stacked"` OR a closely-related variant**: the V2 orphan renderer (289 LOC) imported ONLY by `routes/DevChartsSandbox.svelte`. Sandbox is updated.
4. **`composition-bar/` package migration -> `CategoryBar mode="diverging"`**: ~1900 LOC across 9 files (`adapter-elections-seats.ts` 506 LOC + `helpers.ts` 141 LOC + `types.ts` 125 LOC + tests + fixtures + README + `index.ts`). The production trio (`IndicatorChoropleth` 923 LOC / `IndicatorRanked` 474 LOC / `IndicatorSmallMultiples` 227 LOC) + `CompositionBar` mount in `StateOverview` via `topic-dispatch.ts` + `StackedTrendV2` (805 LOC) all consume this. Migration is per-consumer, golden-render gated.
5. **Delete the orphans + `composition-bar/`**: only after every caller is migrated. `git rm` + allowlist scrub + the test-disposition table.
6. **Closure**: distil the seam shape into [docs/architecture/frontend/chart-architecture.md](../docs/architecture/frontend/chart-architecture.md) (or equivalent), flip parent ledger F2a row to MERGED, archive this sub-plan to `docs/archive/plans/`.

Per CLAUDE.md correction-level discipline (>=4 files structural -> propose breakdown first; >=5 = core design) and parent plan section 24.5 sub-plan spawning rule, this is sub-plan territory.

Same pattern as the U1 / U2 / U5 / B1 / B2a / B2b / B2b.4 / B2b.5 / F1 sub-plans.

This sub-plan is the merge-queue authority for F2a. The parent ledger row stays `DEFERRED-TO-SUBPLAN` until F2a.6 (closure) merges, at which point parent flips to `MERGED` with the closure PR# stamped.

## Scope

In scope: the six surfaces above. Each is a separate PR with its own branch, its own gate, and its own §13 in-browser smoke (where it touches a citizen route).

Out of scope (deliberately deferred to other chunks):

- **F2b new renderers** (GeoChoropleth, Matrix, Treemap, CirclePack, C2/C3/C5 primitives): its own sub-plan candidate per parent §23.5 and the session brief.
- **X1a reader flip** + **X1b parquet delete**: parallel-OK with F2a per user override of the `Blocks on X1b` edge ("FRONTEND chart engine work - data layer agnostic; they ship cleanly even while X cutover is pending").
- **B3 / B4 producer + fetch deletions**: independent.

## Sub-row Execution Ledger

| Sub-row | Blocks on | Gate | PR# | Status |
| --- | --- | --- | --- | --- |
| F2a.1 `CategoryBar.svelte` shell + `mode="ranked"` parity (consumes `OrderedCategoryBarViewModel`; behaviour byte-identical to `OrderedCategoryBar.svelte` for the ranked path) | - | vitest + golden-render against the sandbox `ocb` section | _pending_ | TODO |
| F2a.2 `OrderedCategoryBar` -> `CategoryBar mode="ranked"`: flip the `DevChartsSandbox.svelte` import + props; delete `OrderedCategoryBar.svelte` (orphan after this PR; no production consumers) | F2a.1 | sandbox-render-smoke (`/dev/charts-sandbox`) + svelte-check | _pending_ | TODO |
| F2a.3 Add `mode="stacked"` to `CategoryBar`: consume the existing `GroupedBarViewModel` shape (or a small adapter); behaviour byte-identical to `HorizontalGroupedBar.svelte` | F2a.2 | vitest + golden-render against the sandbox `hgb` section | _pending_ | TODO |
| F2a.4 `HorizontalGroupedBar` -> `CategoryBar mode="stacked"`: flip the `DevChartsSandbox.svelte` import + props; delete `HorizontalGroupedBar.svelte` | F2a.3 | sandbox-render-smoke + svelte-check | _pending_ | TODO |
| F2a.5 Add `mode="diverging"` to `CategoryBar`: consume the existing `CompositionBarModel` (adapt or thin-wrap). Migrate the `CompositionBar` mount in `StateOverview` via `topic-dispatch.ts`; verify the production trio renders unchanged; verify `StackedTrendV2` (elections) renders unchanged; delete `composition-bar/` package | F2a.4 | section 13 in-browser smoke on (a) `/s/<state>` mounting `CompositionBar`, (b) one election view with `StackedTrendV2`, (c) one /t/<topic> with `IndicatorChoropleth` / `IndicatorRanked` / `IndicatorSmallMultiples`; svelte-check; build | _pending_ | TODO |
| F2a.6 closure (flip parent F2a row to MERGED; distil the seam shape into the right [docs/architecture/frontend/](../docs/architecture/frontend/) home; archive this sub-plan) | F2a.5 | docs-review | _pending_ | TODO |

Parallel-safe groups: F2a is intentionally SERIAL because each row depends on the previous one's API surface. Two-PR fast-paths exist (e.g. F2a.1+F2a.2 can land in one PR if `OrderedCategoryBar` is deleted in the same diff as `CategoryBar`'s creation) but the default is one row per PR for reviewability.

If F2a.5 (the production migration) grows beyond one PR (4+ consumers x non-trivial render-smoke + svelte-check + golden-render fixtures), spawn a sub-sub-plan `TODO/<YYYYMMDD>-f2a-5-categorybar-prod-migration-subsubplan.md` with per-consumer rows per parent §24.5.

## Per-sub-row notes

### F2a.1 CategoryBar shell + ranked mode

NEW: `frontend/src/lib/charts/CategoryBar.svelte` (~250 LOC). Discriminated-union prop:

```ts
type CategoryBarProps =
  | { mode: "ranked"; view_model: OrderedCategoryBarViewModel<T>; ... }
  | { mode: "stacked"; view_model: GroupedBarViewModel<T>; ... }
  | { mode: "diverging"; view_model: CompositionBarModel; ... };
```

Only the `mode="ranked"` branch implemented in F2a.1; the other two delegate to TODO branches that throw at runtime (Svelte's `assertNever`-style narrowing keeps the type-checker honest). Tests: golden-render comparison against `OrderedCategoryBar.svelte` for a fixed view-model fixture.

Doctrine: this is a TYPE-LEVEL consolidation. The underlying SVG-drawing code can be lifted ~as-is from `OrderedCategoryBar.svelte` into the `mode="ranked"` branch. The mode flag is the discriminator; renderer-internal helpers (axis, scale, sort) stay shared.

### F2a.2 OrderedCategoryBar -> CategoryBar mode="ranked"

`DevChartsSandbox.svelte` flip + delete `OrderedCategoryBar.svelte`. Per parent §23.5: "The sandbox is updated or deleted, not preserved." `bar-view-models/builders.ts` STAYS (it provides `buildOrderedCategoryBarViewModel`; the renderer consumes it through the new component name). `builders.test.ts` stays.

`§13 sandbox-render-smoke`: navigate to `/dev/charts-sandbox`, confirm the `ocb` section's bars match the F2a.1 golden render.

### F2a.3 CategoryBar mode="stacked"

Extend the discriminated union. Lift the SVG-drawing code from `HorizontalGroupedBar.svelte` into the `mode="stacked"` branch of `CategoryBar.svelte`. Reuse the existing `legendColour` helper (currently exported from `HorizontalGroupedBar.svelte`).

If the `mode="stacked"` rendering is genuinely different enough to warrant a distinct mode label (e.g. `mode="grouped"`), rename — the discriminated-union shape is the design seam, not the literal flag value.

### F2a.4 HorizontalGroupedBar -> CategoryBar mode="stacked"

Same shape as F2a.2: sandbox flip + renderer delete. `multi-dim-view-models/builders.ts` STAYS.

### F2a.5 composition-bar -> CategoryBar mode="diverging" + production migration

LARGEST sub-row. The `composition-bar/` package has multiple concerns:

- **Renderer surface** (consumed by `CompositionBar.svelte` mount): lift into `CategoryBar mode="diverging"`.
- **Adapter** (`adapter-elections-seats.ts`, 506 LOC; consumed by `StackedTrendV2.svelte` and the StateOverview mount): the adapter logic (loaded-rows -> diverging-bar-model) is INDEPENDENT of the renderer. **Lift the adapter to its own home** (`frontend/src/lib/charts/diverging-bar/` or `lib/charts/category-bar/diverging-adapter/`) when deleting `composition-bar/`. Do NOT lose adapter logic.
- **Helpers** + **types**: lift along with the adapter; consolidate naming with `CategoryBar`'s diverging-mode contract.
- **Tests + fixtures + README**: rewrite in the new home; the README distillation is the seam doc.

Production consumer matrix (golden-render gate for each):

| Consumer | LOC | Mount point | Smoke route |
| --- | --- | --- | --- |
| `IndicatorChoropleth.svelte` | 923 | `/t/<topic>` topic pages via `topic-dispatch.ts` | `/t/energy`, `/t/elections` |
| `IndicatorRanked.svelte` | 474 | same | same |
| `IndicatorSmallMultiples.svelte` | 227 | same | same |
| `CompositionBar` mount in `StateOverview.svelte` | direct mount | `/s/<state>` | `/s/tamil-nadu` |
| `StackedTrendV2.svelte` | 805 | election views via `topic-dispatch.ts` | election-experience routes |

Per parent §23.5: "the V2 orphan renderers are imported ONLY by DevChartsSandbox... The real migration target is the production trio." F2a.5 honours this: the production migration is the actual work; F2a.1-F2a.4 are the warm-up.

`§13 in-browser smoke` (3+ routes minimum): verify (a) the diverging bars render pixel-identical-or-better, (b) party colours preserved via `getPartyColor`/`resolvePartyPalette`, (c) source-line in `ChartShell` footer unchanged, (d) 0 new console errors, (e) 0 failed requests.

### F2a.6 closure

- Distil the `CategoryBar` discriminated-union pattern into [docs/architecture/frontend/chart-architecture.md](../docs/architecture/frontend/chart-architecture.md) (or create if absent) section "Consolidated bar renderers".
- Flip the parent F2a ledger row to MERGED in this same PR; stamp the closure PR#.
- Archive this sub-plan to `docs/archive/plans/20260605-f2a-categorybar-consolidation-subplan.md` with a "Plan complete" block per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).
- Confirm: F2b (new renderers) may now build on `CategoryBar`'s discriminated-union pattern; F3 (national reference line) ships independently per [PR #779](../pull/779).

## Contract invariants (inherited from parent 21.7 / 21.8 / 21.9 / 23.5)

1. **Behaviour-preserving.** Every consumer renders pixel-identical-or-better after migration. Golden-render gate per `golden-render` row in parent §22.6 gates catalogue.
2. **No new data-layer touches.** F2a is structural; data flow (CSV/Parquet/JSON) is unchanged. Per session brief: "F2a/F2b/F3/F4 are FRONTEND chart engine work - data layer agnostic".
3. **Strangler-fig topology.** Each PR is independently revertable. The orphan `OrderedCategoryBar` / `HorizontalGroupedBar` survive in-tree until their migrate-then-delete PR.
4. **§13 smoke is the safety net.** Every PR touching a citizen-visible mount runs `/s/<state>`, `/t/<topic>`, or `/dev/charts-sandbox` smoke per CLAUDE.md section 13.
5. **No mocks at the renderer seam.** Component tests use real view-model fixtures (Holy Law #7).

## Tracking

The parent Execution Ledger row F2a is `DEFERRED-TO-SUBPLAN -> TODO/20260605-f2a-categorybar-consolidation-subplan.md` in the SAME PR that lands this sub-plan. Sub-row status updates land inside each F2a.x PR per 24.3.

## See also

- Parent plan: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) sections 23.5 (file-level ripple corrections; production blast radius), 22.6 (gates catalogue: `golden-render`), 24.5 (sub-plan spawning).
- Sibling F-track sub-plans: [TODO/20260605-f1-csv-loaders-and-oracle-rewrite-subplan.md](20260605-f1-csv-loaders-and-oracle-rewrite-subplan.md) F1.2 = #778; F3 reference-line shipped as #779.
- Strangler-fig precedent: yen-gov PR #78 ([/memories/patterns.md](../../../memories/patterns.md) "Strangler-fig pre-stage").
- Frontend allowlist seam precedent: PR #171 ([/memories/patterns.md](../../../memories/patterns.md) "Per-indicator frontend allowlist seam").
