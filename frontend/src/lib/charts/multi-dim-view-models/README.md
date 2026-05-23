# `charts/multi-dim-view-models/` — grouped + faceted builders (Phase 1.6)

Pure builders for the `horizontal_grouped_bar` and `facet_panel_grid`
chart candidates from the plan vocabulary. Both adopt the closed-enum
sort policies from `../sort-policy/`.

## Contract

```ts
import {
  buildHorizontalGroupedBarViewModel,
  buildFacetPanelGridViewModel,
} from "$lib/charts/multi-dim-view-models";

const grouped = buildHorizontalGroupedBarViewModel({
  rows: party_results,
  toRow: (r) => ({
    id: r.party,
    label: r.party,
    cells: [
      { group_id: "y2019", group_label: "2019", value: r.y2019 },
      { group_id: "y2024", group_label: "2024", value: r.y2024 },
    ],
  }),
  policy: "value_desc",                              // row sort
  aggregator: { kind: "sum" },                        // cells → row sort key
});

const grid = buildFacetPanelGridViewModel({
  rows: state_indicator_rows,
  toPanelRow: (r) => ({
    panel_id: r.state_code,
    panel_label: r.state_name,
    id: `${r.state_code}-${r.cat}`,
    label: r.cat_label,
    value: r.value,
  }),
  row_policy: "value_desc",
  panel_policy: "value_desc",
  shared_scale: true,                                 // global vs per-panel max
});
```

## Doctrine

- **Plan §1.6** — builders for `horizontal_grouped_bar` and
  `facet_panel_grid`.
- **Plan rule** — *"Shared-scale decisions for faceted panels must
  be explicit in the view-model."* → `shared_scale` is a required
  decision (default `true`) that drives `show_value_label` and is
  echoed on the output via `FacetPanelGridViewModel.shared_scale` +
  `global_max_abs_value`.
- **Plan rule** — *"Nulls/missing values stay visible and sort last
  unless the projection explicitly filters them."* → both rectangular
  rows (grouped) and entire panels with all-null values remain in
  the view-model.
- **Plan rule** — *"Direct labels should be part of the view-model
  where the renderer needs stable label eligibility."* →
  `show_value_label` flag per cell / row.
- **CLAUDE.md §10 closed enums** — `GroupedBarPolicy`,
  `FacetPanelPolicy`, `CellAggregator` are narrowed unions.
- **R-08 BBA** — pure builders; no renderer imports, no URL/global
  state.
- **R-16** — multi-dimension slice. The remaining Phase 1.6
  candidates (`dumbbell_range`, `time_series_line`) ship in
  subsequent PRs.

## Aggregator vocabulary

| Kind | Behaviour | Common use |
|---|---|---|
| `{ kind: "sum" }` | sum of present cells; null if all missing | "total seats over years" |
| `{ kind: "max" }` | max present cell | "best election year" |
| `{ kind: "mean" }` | arithmetic mean of present cells | "average over the strip" |
| `{ kind: "pick_group", group_id }` | value of a single nominated group | "rank parties by 2024 value" |

## Properties

- Pure: row references preserved by identity.
- Stable: ties keep insertion order.
- Null-honest: missing cells remain (grid is rectangular).
- Shared-scale honest: `FacetPanelGridViewModel` always echoes
  `shared_scale` + `global_max_abs_value` so renderers don't
  re-derive them.
- Empty-array safe.
