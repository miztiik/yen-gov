// View-model builders for single-dimension bar candidates: `ranked_bar`
// and `ordered_category_bar` (per the renderer enum vocabulary in
// `TODO/20260518-frontend-charting-modernisation-plan.md`).
//
// Doctrine ties:
//
//   - Plan §1.6: "Add helpers that build view-models for `ranked_bar`,
//     `ordered_category_bar`, `horizontal_grouped_bar`,
//     `facet_panel_grid`, `dumbbell_range`, and `time_series_line`
//     candidates."
//
//   - Plan rule: "Nulls/missing values stay visible and sort last
//     unless the projection explicitly filters them." → builders
//     preserve null-valued rows; renderers display "no data" for them.
//
//   - Plan rule: "Direct labels should be part of the view-model where
//     the renderer needs stable label eligibility." → builders emit a
//     `show_value_label` flag per row based on a magnitude threshold.
//
//   - R-08 BBA: builders are PURE; they don't import from a renderer
//     and they don't read URL/global state. Renderers pass their
//     domain shape + a `toItem` projection.
//
//   - CLAUDE.md §10 closed enums: `RankedBarPolicy` is a NARROWED
//     subset of `SortPolicy` — only sort policies that make sense for
//     a single-dimension bar are listed. `OrderedCategoryBarPolicy`
//     is even narrower (axis_order + alphabetical only).

import { applySortPolicy, sortDirectionForPolicy } from "../sort-policy/helpers";
import type { SortItem, SortOptions, SortPolicy } from "../sort-policy/types";

// ─── narrowed policy unions ────────────────────────────────────────

/**
 * The sort policies a `ranked_bar` view-model permits. Excludes
 * `axis_order` (categorical-only) and `chronological` (time-series-only).
 */
export type RankedBarPolicy =
  | "value_asc"
  | "value_desc"
  | "rank_best_first"
  | "pinned_then_value"
  | "latest_change"
  | "alphabetical";

/**
 * The sort policies an `ordered_category_bar` view-model permits. By
 * definition this projection respects the source's axis order; only
 * `axis_order` and `alphabetical` fallback are accepted.
 */
export type OrderedCategoryBarPolicy = "axis_order" | "alphabetical";

// ─── input contracts ───────────────────────────────────────────────

/**
 * Generic input contract — the renderer supplies its domain rows and a
 * projection function. The builder never reads the row's fields
 * directly, so this stays renderer-agnostic.
 */
export interface RankedBarInput<T> {
  /** The domain rows in their natural (caller-supplied) order. */
  readonly rows: readonly T[];
  /** Project a row onto a `SortItem` for sorting. Must be pure. */
  readonly toItem: (row: T) => SortItem;
  /** The requested sort policy. */
  readonly policy: RankedBarPolicy;
  /** Optional sort options (e.g. `best_is_high` for `rank_best_first`). */
  readonly options?: SortOptions;
  /**
   * Optional label-eligibility threshold. A row's `show_value_label`
   * is `true` when its `Math.abs(value)` ≥ `max_abs_value * threshold`.
   * Default 0.05 (label rows ≥ 5 % of the biggest bar).
   */
  readonly label_threshold?: number;
}

export interface OrderedCategoryBarInput<T> {
  readonly rows: readonly T[];
  readonly toItem: (row: T) => SortItem;
  readonly policy: OrderedCategoryBarPolicy;
  readonly label_threshold?: number;
}

// ─── output view-models ────────────────────────────────────────────

/**
 * One row in the rendered bar list. `row` is the ORIGINAL domain row
 * (untouched), and the helper fields are projections the renderer
 * can use without re-deriving them.
 */
export interface RankedBarRowVM<T> {
  /** The original domain row, untouched. */
  readonly row: T;
  /** The projection result (id, label, value, etc.). */
  readonly sort_key: SortItem;
  /** 1-based rank over rows with a present value; `null` for missing. */
  readonly rank: number | null;
  /** True when `sort_key.pinned_rank` is a number (>= 0). */
  readonly is_pinned: boolean;
  /** True when `value` is null / undefined / NaN. */
  readonly is_missing: boolean;
  /** True when `value` is the maximum absolute value in the visible set. */
  readonly is_max: boolean;
  /** Label eligibility: bar is "big enough" to carry an end label. */
  readonly show_value_label: boolean;
}

export interface RankedBarViewModel<T> {
  /** Rows in the order the renderer should draw them. */
  readonly rows: readonly RankedBarRowVM<T>[];
  /** Echo of the requested policy. */
  readonly policy: RankedBarPolicy;
  /** Arrow direction for the policy. */
  readonly direction: "asc" | "desc" | "neutral";
  /** Maximum absolute value across rows that have a value (>= 0). */
  readonly max_abs_value: number;
  /** Count of rows where `value` is present. */
  readonly present_count: number;
  /** Count of rows where `value` is missing. */
  readonly missing_count: number;
}

export interface OrderedCategoryBarViewModel<T> {
  readonly rows: readonly RankedBarRowVM<T>[];
  readonly policy: OrderedCategoryBarPolicy;
  readonly direction: "asc" | "desc" | "neutral";
  readonly max_abs_value: number;
  readonly present_count: number;
  readonly missing_count: number;
}

// ─── shared internals ──────────────────────────────────────────────

function isMissingValue(v: number | null | undefined): boolean {
  return v === null || v === undefined || Number.isNaN(v);
}

interface PairWithIndex {
  readonly index: number;
  readonly row_ref: unknown;
  readonly item: SortItem;
}

/**
 * Common projection-and-sort path shared by both builders. Keeps the
 * original row reference attached so the public builders can re-pair
 * after sorting.
 */
function projectAndSort<T>(
  rows: readonly T[],
  toItem: (row: T) => SortItem,
  policy: SortPolicy,
  options: SortOptions,
): PairWithIndex[] {
  const pairs: PairWithIndex[] = rows.map((row, index) => ({
    index,
    row_ref: row,
    item: toItem(row),
  }));
  // applySortPolicy sorts SortItems; we sort the pairs ourselves
  // using the same comparator semantics via a re-application:
  // because applySortPolicy is stable, sorting the projected items
  // and then re-pairing by index gives the same order.
  const sorted_items = applySortPolicy(
    pairs.map((p) => p.item),
    policy,
    options,
  );
  // Re-pair: sorted_items came from pairs[].item references, so we
  // can match on identity (===). This preserves the original row_ref.
  const by_item = new Map<SortItem, PairWithIndex>();
  for (const p of pairs) by_item.set(p.item, p);
  return sorted_items.map((it) => by_item.get(it) as PairWithIndex);
}

function summarise(items: readonly SortItem[]): {
  max_abs_value: number;
  present_count: number;
  missing_count: number;
} {
  let max_abs_value = 0;
  let present_count = 0;
  let missing_count = 0;
  for (const it of items) {
    if (isMissingValue(it.value)) {
      missing_count += 1;
      continue;
    }
    present_count += 1;
    const abs = Math.abs(it.value as number);
    if (abs > max_abs_value) max_abs_value = abs;
  }
  return { max_abs_value, present_count, missing_count };
}

function assignRanks(
  sorted: PairWithIndex[],
  policy: RankedBarPolicy,
  options: SortOptions,
): Map<number, number> {
  // Rank only over rows with a present value. Ranks reflect the
  // policy's preferred direction (best = rank 1):
  //   - value_desc / rank_best_first(best_is_high=true) / latest_change → desc
  //   - value_asc / rank_best_first(best_is_high=false) → asc
  //   - pinned_then_value / alphabetical → desc by value (sensible default)
  const direction = sortDirectionForPolicy(policy, options);
  // Build a value-only sorted list to derive 1..N ranks.
  const present = sorted.filter((p) => !isMissingValue(p.item.value));
  // Direction may be "neutral" for alphabetical/pinned — we still need
  // a ranking convention, so default to desc value for those.
  const cmp = (a: PairWithIndex, b: PairWithIndex): number => {
    const av = a.item.value as number;
    const bv = b.item.value as number;
    return direction === "asc" ? av - bv : bv - av;
  };
  const ranked = present.slice().sort(cmp);
  const rank_by_index = new Map<number, number>();
  ranked.forEach((p, i) => rank_by_index.set(p.index, i + 1));
  return rank_by_index;
}

// ─── public builders ───────────────────────────────────────────────

/**
 * Build a ranked-bar view-model from a generic input. Pure.
 *
 *   - Preserves nulls (they show as "no data" rows at the bottom).
 *   - Computes 1-based rank over present rows only.
 *   - Flags `is_max` and `show_value_label` per row.
 *   - Returns a new object; input is never mutated.
 */
export function buildRankedBarViewModel<T>(
  input: RankedBarInput<T>,
): RankedBarViewModel<T> {
  const threshold = input.label_threshold ?? 0.05;
  const options = input.options ?? {};
  const sorted = projectAndSort(input.rows, input.toItem, input.policy, options);
  const items = sorted.map((p) => p.item);
  const { max_abs_value, present_count, missing_count } = summarise(items);
  const rank_by_index = assignRanks(sorted, input.policy, options);
  const rows: RankedBarRowVM<T>[] = sorted.map((p) => {
    const item = p.item;
    const is_missing = isMissingValue(item.value);
    const abs = is_missing ? 0 : Math.abs(item.value as number);
    const is_max = !is_missing && max_abs_value > 0 && abs === max_abs_value;
    const show_value_label
      = !is_missing && max_abs_value > 0 && abs >= max_abs_value * threshold;
    return {
      row: p.row_ref as T,
      sort_key: item,
      rank: rank_by_index.get(p.index) ?? null,
      is_pinned: typeof item.pinned_rank === "number" && item.pinned_rank >= 0,
      is_missing,
      is_max,
      show_value_label,
    };
  });
  return {
    rows,
    policy: input.policy,
    direction: sortDirectionForPolicy(input.policy, options),
    max_abs_value,
    present_count,
    missing_count,
  };
}

/**
 * Build an ordered-category-bar view-model. Pure.
 *
 * Same shape as `RankedBarViewModel<T>` except the policy union is
 * narrower (`axis_order` | `alphabetical`). Rank assignment uses
 * "desc by value" as a stable default — the renderer typically does
 * NOT show ranks on a categorical bar (the axis IS the order), but
 * the field is present for consistency.
 */
export function buildOrderedCategoryBarViewModel<T>(
  input: OrderedCategoryBarInput<T>,
): OrderedCategoryBarViewModel<T> {
  const threshold = input.label_threshold ?? 0.05;
  const sorted = projectAndSort(input.rows, input.toItem, input.policy, {});
  const items = sorted.map((p) => p.item);
  const { max_abs_value, present_count, missing_count } = summarise(items);
  // For categorical, "rank" is a value-desc projection — useful when a
  // renderer wants to badge the leading bar without losing axis order.
  const rank_by_index = new Map<number, number>();
  const present = sorted.filter((p) => !isMissingValue(p.item.value));
  present
    .slice()
    .sort(
      (a, b) => (b.item.value as number) - (a.item.value as number),
    )
    .forEach((p, i) => rank_by_index.set(p.index, i + 1));
  const rows: RankedBarRowVM<T>[] = sorted.map((p) => {
    const item = p.item;
    const is_missing = isMissingValue(item.value);
    const abs = is_missing ? 0 : Math.abs(item.value as number);
    const is_max = !is_missing && max_abs_value > 0 && abs === max_abs_value;
    const show_value_label
      = !is_missing && max_abs_value > 0 && abs >= max_abs_value * threshold;
    return {
      row: p.row_ref as T,
      sort_key: item,
      rank: rank_by_index.get(p.index) ?? null,
      is_pinned: typeof item.pinned_rank === "number" && item.pinned_rank >= 0,
      is_missing,
      is_max,
      show_value_label,
    };
  });
  return {
    rows,
    policy: input.policy,
    direction: sortDirectionForPolicy(input.policy, {}),
    max_abs_value,
    present_count,
    missing_count,
  };
}
