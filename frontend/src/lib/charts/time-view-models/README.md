# `charts/time-view-models/` — dumbbell + time-series builders (Phase 1.6)

Pure builders for the `dumbbell_range` and `time_series_line` chart
candidates from the plan vocabulary. Both adopt the closed-enum sort
policies from `../sort-policy/` and re-use `parseLeadingYear` from
`../temporal-viewport/` for chronological ordering — same primitive
as the temporal viewport brush.

## Contract

```ts
import {
  buildDumbbellRangeViewModel,
  buildTimeSeriesLineViewModel,
} from "$lib/charts/time-view-models";

// 1. Dumbbell: two endpoints per row (earliest, latest).
const gap = buildDumbbellRangeViewModel({
  rows: state_literacy,
  toEndpoints: (r) => ({
    id: r.code,
    label: r.name,
    earliest: { period_label: "2011", value: r.y2011 },
    latest:   { period_label: "2021", value: r.y2021 },
  }),
  policy: "latest_change",            // movers first
});

// 2. Time-series: many points per series (line per state, year on x).
const lines = buildTimeSeriesLineViewModel({
  rows: gsdp_long_format,
  toPoint: (r) => ({
    series_id: r.state_code,
    series_label: r.state_name,
    period_id: String(r.year),
    period_label: String(r.year),
    value: r.gsdp_inr_crore,
  }),
  policy: "value_desc",
  visible_period_ids: ["2019", "2020", "2021", "2022", "2023"],  // optional window
  suppress_breaks: true,                                          // null = visual gap
});
```

## Dumbbell output

| Field | Meaning |
|---|---|
| `earliest` / `latest` | endpoint VMs with `period_label`, `value`, `is_missing`, `show_endpoint_label` |
| `delta` | `latest - earliest`; null if either endpoint missing |
| `abs_delta` | `\|delta\|`; null when delta is null |
| `direction` | `"up"` / `"down"` / `"flat"` / `"missing"` |
| `show_delta_label` | label eligibility for the connecting line |
| `rank` | 1-based by policy's primary sort key |

## Time-series output

| Field | Meaning |
|---|---|
| `period_axis` | global chronological axis: `[{ period_id, period_label, year }, …]` |
| `series[].points` | chronological, optionally windowed via `visible_period_ids` |
| `series[].points[].is_break_start` | true at the first present point AND after any null |
| `series[].latest_value` / `earliest_value` / `abs_delta` | over the visible window |
| `series[].show_direct_end_label` | direct end-label eligibility |
| `series[].rank` | by latest_value, direction-aware |
| `suppress_breaks` | echoed from input so renderer can decide on null bridging |

## Doctrine

- **Plan §1.6** — builders for `dumbbell_range` + `time_series_line`.
- **Plan rule** — *"Nulls/missing values stay visible and sort last
  unless the projection explicitly filters them."* → dumbbell rows
  with all-null endpoints remain (rank null); series with zero
  windowed points remain.
- **Plan rule** — *"Direct labels should be part of the view-model
  where the renderer needs stable label eligibility."* →
  `show_endpoint_label` / `show_delta_label` / `show_direct_end_label`
  flags.
- **CLAUDE.md §10** — `DumbbellRangePolicy` and `TimeSeriesLinePolicy`
  are narrowed unions.
- **R-08 BBA** — pure builders; no renderer imports, no URL/global
  state. The temporal viewport brush (#147) and these builders share
  the same `parseLeadingYear` primitive for chronological ordering.
- **R-16** — final Phase 1.6 slice. Sorting/grouping helpers were
  shipped in #149 / #150 / #151.

## Properties

- Pure (row references preserved by identity).
- Stable (ties keep insertion order).
- Null-honest.
- Window-aware.
- Empty-array safe.
