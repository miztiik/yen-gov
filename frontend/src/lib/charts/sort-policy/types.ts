// Sort policies — closed-enum type contract for Phase 1.6 chart
// view-model sorting helpers.
//
// Per `docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md` Phase 1.6:
// "Move chart sorting/grouping decisions out of Svelte templates and
// into tested view-model helpers."
//
// Doctrine ties:
//
//   - CLAUDE.md §10 (closed enums): `SortPolicy` is a closed string
//     union. Adding a value requires editing this file, the
//     `KNOWN_SORT_POLICIES` array in `./helpers.ts`, AND the plan task
//     list in lockstep — the same three-place rule that guards
//     `ChartShellAction`, `TemporalPreset`, etc.
//
//   - R-12 ("citizen-readable controls"): every policy is keyed by a
//     verb a citizen could read off a settings menu (descending vs
//     ascending vs chronological, etc.) — no internal-only modes like
//     "raw_score_then_alphabetical".
//
// Scope:
//
//   - This module defines TYPES + a SortItem<T> contract; the actual
//     sort implementations live in `./helpers.ts`.
//
//   - Per-renderer view-model builders (`buildRankedBarViewModel`,
//     `buildOrderedCategoryBarViewModel`, etc.) ship in separate PRs
//     per R-16 — this PR is the foundation slice.

/**
 * The set of sort policies a chart view-model can request.
 *
 *   - `value_asc` — numeric, lowest first. Nulls / missing stay
 *     visible and sort LAST (per plan: "Nulls/missing values stay
 *     visible and sort last unless the projection explicitly filters
 *     them.").
 *   - `value_desc` — numeric, highest first. Nulls last (same).
 *   - `axis_order` — preserves the caller-supplied `order` integer.
 *     Used by categorical axes (economic class, age band, fuel mix)
 *     where the natural order is semantic, not numeric.
 *   - `chronological` — by period_id ascending. Stale ids that don't
 *     parse to a year sort LAST (after the parseable ones).
 *   - `pinned_then_value` — pinned ids (home / compare in
 *     IndicatorRanked) first in pin order; remainder by value_desc.
 *   - `rank_best_first` — for indicators where "best" is unambiguous
 *     (high or low), sort the best end first. The sort uses the
 *     caller-supplied `best_is_high` flag.
 *   - `latest_change` — by absolute delta between the two latest
 *     period values (descending magnitude). Used for "movers" lists.
 *   - `alphabetical` — by `label` ascending, case-insensitive.
 */
export type SortPolicy =
  | "value_asc"
  | "value_desc"
  | "axis_order"
  | "chronological"
  | "pinned_then_value"
  | "rank_best_first"
  | "latest_change"
  | "alphabetical";

/**
 * The canonical row shape every sort helper consumes. Renderers project
 * their domain shapes (bar, segment, dumbbell endpoint, etc.) onto
 * `SortItem` via a `key`/`label`/`value` mapping function at the
 * view-model boundary — so the sort helpers stay free of renderer
 * knowledge.
 *
 * Fields:
 *
 *   - `id`         — stable identifier (party_code, age_band id,
 *                    period_id, etc.). Must be unique within the
 *                    input array.
 *   - `label`      — citizen-facing string for `alphabetical` sort.
 *   - `value`      — primary numeric value for `value_*` and
 *                    `rank_best_first`. `null` is honest "missing" —
 *                    sorts LAST in numeric policies.
 *   - `order`      — integer key for `axis_order`. Missing → treated
 *                    as the largest order (sorts last).
 *   - `period_id`  — for `chronological`. The helper extracts a year
 *                    via `parseLeadingYear` (same primitive as the
 *                    temporal viewport); unparseable ids sort LAST.
 *   - `pinned_rank`— for `pinned_then_value`. Lower rank = pinned
 *                    earlier. `null` (or missing) means "not pinned".
 *   - `latest_two` — for `latest_change`. Optional tuple
 *                    `[previous, latest]` of two numbers OR null
 *                    entries (a present-then-missing series has zero
 *                    delta and sorts LAST).
 */
export interface SortItem {
  readonly id: string;
  readonly label: string;
  readonly value?: number | null;
  readonly order?: number;
  readonly period_id?: string;
  readonly pinned_rank?: number | null;
  readonly latest_two?: readonly [number | null, number | null];
}

/**
 * Caller-supplied flags consumed by certain policies. Pass-through
 * record: only the policies that need them read their fields, the
 * rest ignore extras.
 *
 *   - `best_is_high` — required by `rank_best_first`. `true` for
 *     "higher is better" indicators (literacy rate, GSDP per capita),
 *     `false` for "lower is better" (IMR, NPL ratio). Defaults to
 *     `true` if omitted.
 */
export interface SortOptions {
  readonly best_is_high?: boolean;
}
