# Sort policy and view-model builders (Phase 1.6)

**Last Updated**: 2026-05-25

Foundation for every generic renderer in the [`charts/`](.) family. Defines the closed-enum sort policy plus the three builder modules (bar, multi-dim, time) that lock sort/project/dimension choices before a renderer ever receives data.

## What it is

### Sort policy

- [`frontend/src/lib/charts/sort-policy/types.ts`](../../../../frontend/src/lib/charts/sort-policy/types.ts) — closed-union `SortPolicy` of 8 values: `value_asc`, `value_desc`, `axis_order`, `chronological`, `pinned_then_value`, `rank_best_first`, `latest_change`, `alphabetical`. Plus `SortItem`, `SortOptions`.
- [`frontend/src/lib/charts/sort-policy/helpers.ts`](../../../../frontend/src/lib/charts/sort-policy/helpers.ts) — `applySortPolicy(items, policy, options?)` pure, stable, null-honest comparator switch. `sortDirectionForPolicy(policy)` returns `"asc" | "desc" | "neutral"`. `KNOWN_SORT_POLICIES` is the source-of-truth array.

### View-model builders

- [`frontend/src/lib/charts/bar-view-models/builders.ts`](../../../../frontend/src/lib/charts/bar-view-models/builders.ts) — `buildRankedBarViewModel`, `buildOrderedCategoryBarViewModel`.
- [`frontend/src/lib/charts/multi-dim-view-models/builders.ts`](../../../../frontend/src/lib/charts/multi-dim-view-models/builders.ts) — `buildHorizontalGroupedBarViewModel`, `buildFacetPanelGridViewModel`.
- [`frontend/src/lib/charts/time-view-models/builders.ts`](../../../../frontend/src/lib/charts/time-view-models/builders.ts) — `buildDumbbellRangeViewModel`, `buildTimeSeriesLineViewModel`.

Each builder takes raw rows + a `policy` + per-builder options; returns a typed view-model that the matching renderer consumes verbatim.

## Doctrinal rules

- **CLOSED enum, three-place lock** (CLAUDE.md §10). `SortPolicy` union + `KNOWN_SORT_POLICIES` array + `applySortPolicy` switch with a `never` branch. Adding a value requires editing all three, or TypeScript fails the build. The switch's `never` branch is the structural guard.
- **Builder is the contract, not the renderer.** View-model builder output carries `rank`, `order`, `period_axis`, `sort_value` fields alongside values; renderers MUST NOT re-sort. If a renderer needs a different order, that is a builder change, not a renderer change.
- **Nulls and missing values sort LAST** in numeric / chronological / alphabetical policies. Plan quote: *"Nulls/missing values stay visible and sort last unless the projection explicitly filters them."* No silent drops.
- **`chronological` re-uses `parseLeadingYear`** from the [temporal viewport](temporal-viewport.md) module. The brush math and the chronological sort math agree by construction.
- **No silent filters in builders.** All-null rows and all-missing series remain in the output with `rank: null` (visible, sortable last). Filtering is the caller's job, not the builder's.
- **`OrderedCategoryBarPolicy` is narrower** (`axis_order` | `alphabetical` only) — value-sort is structurally forbidden for axis-ordered categories. See [`generic-renderers.md`](generic-renderers.md).

## Test surface

- [`sort-policy/helpers.test.ts`](../../../../frontend/src/lib/charts/sort-policy/helpers.test.ts) — 31 vitest cases (purity, stability, nulls-last, axis-order with missing, chronological unparseable, pinned_then_value, rank_best_first both directions, latest_change, alphabetical).
- [`bar-view-models/builders.test.ts`](../../../../frontend/src/lib/charts/bar-view-models/builders.test.ts), [`multi-dim-view-models/builders.test.ts`](../../../../frontend/src/lib/charts/multi-dim-view-models/builders.test.ts), [`time-view-models/builders.test.ts`](../../../../frontend/src/lib/charts/time-view-models/builders.test.ts) — per-builder coverage (21+ cases per file).

## See also

- [`generic-renderers.md`](generic-renderers.md) — the renderers that consume these builders.
- [`temporal-viewport.md`](temporal-viewport.md) — shared `parseLeadingYear` helper.
- [`overview.md`](../overview.md) — visualization catalog (renderer ↔ builder mapping in the renderer table).

## Historical citations

Distils `.commit-msg-37.txt`–`.commit-msg-40.txt` and `.pr-body-37.md`–`.pr-body-40.md` (deleted on distillation). PR-149 = sort-policy foundation; PRs 150/151/152 = bar / multi-dim / time builder modules.
