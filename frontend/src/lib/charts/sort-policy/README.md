# `charts/sort-policy/` — view-model sort helpers (Phase 1.6)

Pure helpers that apply a closed-enum `SortPolicy` to an array of
`SortItem` rows. Renderers project their domain shapes (parties,
indicator rows, dumbbell endpoints, time periods) onto `SortItem`
via a `key`/`label`/`value` mapping at the view-model boundary,
then call `applySortPolicy(items, policy, options?)`.

## Contract

```ts
import { applySortPolicy } from "$lib/charts/sort-policy";

const sorted = applySortPolicy(rows, "value_desc");           // numeric, nulls last
const ranked = applySortPolicy(rows, "rank_best_first", {     // direction-aware
  best_is_high: false,                                        //   (IMR, NPL)
});
const axis   = applySortPolicy(rows, "axis_order");           // economic class etc.
const chrono = applySortPolicy(rows, "chronological");        // period_id → year
const pinned = applySortPolicy(rows, "pinned_then_value");    // home/compare first
const movers = applySortPolicy(rows, "latest_change");        // |Δ| desc
const alpha  = applySortPolicy(rows, "alphabetical");         // label asc
```

## Doctrine

- **CLAUDE.md §10 — closed enums.** `SortPolicy` is a closed string
  union in `./types.ts`; the switch in `./helpers.ts` uses a `never`
  branch so adding a value without an arm fails type-checking. The
  `KNOWN_SORT_POLICIES` frozen array is the third place — keep all
  three in lockstep.
- **R-12 — citizen-readable controls.** Every policy is keyed by a
  verb a citizen could read off a settings menu. No internal-only
  modes like "raw_score_then_alphabetical".
- **R-16 — three-PR split.** This is the foundation slice (helpers
  only). Per-renderer view-model builders ship in subsequent PRs.
- **Plan rule.** Nulls / missing values STAY VISIBLE and SORT LAST
  in numeric policies — they're never silently dropped.

## Properties

- Pure: input arrays are never mutated; every call returns a new array.
- Stable: ties preserve insertion order (relies on ECMAScript 2019
  stable `Array.prototype.sort`).
- Null-honest: `null` / `undefined` / `NaN` values sort LAST in
  numeric, chronological, and alphabetical policies.
- Empty-array safe: returns `[]` for every policy.

## Renderer guidance

When wiring a renderer:

1. Project your domain shape onto `SortItem` (id, label, value,
   plus the optional keys the policy needs: `order`,
   `period_id`, `pinned_rank`, `latest_two`).
2. Call `applySortPolicy(items, policy, options)`.
3. Render in the returned order. If you also show a direction arrow,
   use `sortDirectionForPolicy(policy, options)`.
