# `charts/bar-view-models/` — single-dimension bar builders (Phase 1.6)

Pure builders for the `ranked_bar` and `ordered_category_bar` chart
candidates from `TODO/20260518-frontend-charting-modernisation-plan.md`.
Both take a renderer-agnostic `rows + toItem(row)` projection and
return a view-model ready for a Svelte renderer.

## Contract

```ts
import {
  buildRankedBarViewModel,
  buildOrderedCategoryBarViewModel,
} from "$lib/charts/bar-view-models";

const ranked = buildRankedBarViewModel({
  rows: state_rows,
  toItem: (r) => ({ id: r.code, label: r.name, value: r.literacy_pct }),
  policy: "value_desc",                              // narrowed enum
});

const cats = buildOrderedCategoryBarViewModel({
  rows: economic_class_rows,
  toItem: (r) => ({ id: r.id, label: r.label, order: r.order, value: r.value }),
  policy: "axis_order",                              // axis_order | alphabetical
});
```

## Returned view-model

Both builders return the same row shape:

| Field | Meaning |
|---|---|
| `row` | The original domain row, untouched. |
| `sort_key` | The `SortItem` the builder used internally. |
| `rank` | 1-based rank over rows with a present value; `null` for missing. |
| `is_pinned` | `sort_key.pinned_rank` is a number (>= 0). |
| `is_missing` | `value` is `null` / `undefined` / `NaN`. |
| `is_max` | `Math.abs(value)` equals the global max. |
| `show_value_label` | `Math.abs(value)` >= `max_abs_value * label_threshold` (default 0.05). |

Plus top-level: `policy`, `direction`, `max_abs_value`, `present_count`,
`missing_count`.

## Doctrine

- **Plan §1.6**: builders for `ranked_bar` and `ordered_category_bar`
  candidates.
- **Plan rule** — *"Nulls/missing values stay visible and sort last
  unless the projection explicitly filters them."* → missing rows
  remain in the view-model as the last entries, with `rank: null`.
- **Plan rule** — *"Direct labels should be part of the view-model
  where the renderer needs stable label eligibility."* →
  `show_value_label` flag is computed here, not in the renderer.
- **CLAUDE.md §10 closed enums**: `RankedBarPolicy` and
  `OrderedCategoryBarPolicy` are narrowed subsets of `SortPolicy`.
  Policies that don't make sense for a single-dimension bar (e.g.
  `axis_order` on a ranked bar, or `chronological` on either) are
  excluded at the type level.
- **R-08 BBA**: pure functions; no renderer imports, no URL/global
  state. Renderers feed their domain rows + a projection.
- **R-16**: this is one slice (single-dimension bars). Other Phase
  1.6 candidates (`horizontal_grouped_bar`, `facet_panel_grid`,
  `dumbbell_range`, `time_series_line`) ship in subsequent PRs.

## Properties

- Pure: input arrays never mutated; row references preserved via
  identity (===).
- Stable: ties keep their original insertion order.
- Null-honest: missing rows are still in the view-model; renderers
  draw a "no data" indicator.
- Empty-array safe.
