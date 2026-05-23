// View-model builders for multi-dimension chart candidates:
// `horizontal_grouped_bar` and `facet_panel_grid`.
//
// Doctrine ties:
//
//   - Plan §1.6: builders for `horizontal_grouped_bar`,
//     `facet_panel_grid`. Plan rules:
//
//       * "Shared-scale decisions for faceted panels must be explicit
//         in the view-model."
//       * "Nulls/missing values stay visible and sort last unless the
//         projection explicitly filters them."
//       * "Direct labels should be part of the view-model where the
//         renderer needs stable label eligibility."
//
//   - R-08 BBA: builders are PURE; renderers feed domain rows + a
//     `toCells(row)` projection.
//
//   - CLAUDE.md §10: `GroupedBarPolicy` and `FacetPanelPolicy` are
//     NARROWED subsets of `SortPolicy`.

import { applySortPolicy, sortDirectionForPolicy } from "../sort-policy/helpers";
import type { SortItem, SortOptions, SortPolicy } from "../sort-policy/types";

// ─── narrowed policy unions ────────────────────────────────────────

/**
 * Sort policies a `horizontal_grouped_bar` view-model permits. Each
 * ROW (entity) has one bar per group key; `total_value` / `max_cell_value`
 * / etc. drive the row sort.
 *
 * Excludes `axis_order` and `chronological` (the GROUP axis carries
 * those concerns; row order is value-driven).
 */
export type GroupedBarPolicy =
  | "value_asc"
  | "value_desc"
  | "rank_best_first"
  | "pinned_then_value"
  | "alphabetical";

/**
 * Sort policies a `facet_panel_grid` view-model permits. Each PANEL
 * is one facet (e.g. one state); the rows inside a panel are
 * value-sorted; the panels themselves are sorted by their aggregate.
 */
export type FacetPanelPolicy =
  | "value_asc"
  | "value_desc"
  | "rank_best_first"
  | "axis_order"
  | "alphabetical";

/**
 * Aggregation used to reduce a row's cells into a single sort key
 * (for grouped bars) or a panel's rows into a single panel-level
 * value (for facet grids).
 *
 *   - `sum`  — total across cells (default for grouped bars).
 *   - `max`  — largest cell value.
 *   - `mean` — arithmetic mean over PRESENT cells.
 *   - `pick_group` — use the value of a single nominated group key
 *                   (e.g. "rank rows by 2024 value").
 */
export type CellAggregator =
  | { readonly kind: "sum" }
  | { readonly kind: "max" }
  | { readonly kind: "mean" }
  | { readonly kind: "pick_group"; readonly group_id: string };

// ─── cell shape ─────────────────────────────────────────────────────

/**
 * One cell in a grouped/faceted row. The renderer-supplied
 * `toCells(row)` returns an array of these.
 */
export interface BarCell {
  /** The group key (party / fuel / year / etc.). Must be unique within a row. */
  readonly group_id: string;
  /** Citizen-facing label for the group. */
  readonly group_label: string;
  /** Value for this cell. `null` = missing (stays visible). */
  readonly value: number | null;
  /** Optional fill colour the renderer should use. */
  readonly colour?: string;
}

// ─── grouped bar input/output ──────────────────────────────────────

export interface GroupedBarInput<T> {
  /** Domain rows in their natural order. */
  readonly rows: readonly T[];
  /** Project a row onto its label keys + cells. */
  readonly toRow: (row: T) => {
    readonly id: string;
    readonly label: string;
    readonly pinned_rank?: number | null;
    readonly cells: readonly BarCell[];
  };
  /** Sort policy for ROWS (entity order). */
  readonly policy: GroupedBarPolicy;
  /** Aggregation used to reduce cells → row sort key. Default `{ kind: "sum" }`. */
  readonly aggregator?: CellAggregator;
  /** Options for the underlying sort policy. */
  readonly options?: SortOptions;
  /** Label eligibility threshold relative to `max_cell_value`. Default 0.05. */
  readonly label_threshold?: number;
  /**
   * Optional explicit GROUP order. When provided, every row's cells
   * are re-ordered to match (missing groups in a row get filled with
   * a null-value cell so the grid stays rectangular).
   *
   * If omitted, the natural order is the first time each `group_id`
   * appears across `rows[i].cells[*]`.
   */
  readonly group_order?: readonly string[];
}

export interface GroupedBarCellVM extends BarCell {
  readonly is_missing: boolean;
  readonly show_value_label: boolean;
}

export interface GroupedBarRowVM<T> {
  readonly row: T;
  readonly id: string;
  readonly label: string;
  readonly cells: readonly GroupedBarCellVM[];
  /** Aggregated value used to sort this row. */
  readonly sort_value: number | null;
  /** 1-based rank by `sort_value` over rows with a non-null `sort_value`. */
  readonly rank: number | null;
  readonly is_pinned: boolean;
  readonly is_missing: boolean;
}

export interface GroupedBarViewModel<T> {
  /** Rows in render order. */
  readonly rows: readonly GroupedBarRowVM<T>[];
  /** Group order (left→right or top→bottom in the panel). */
  readonly group_order: readonly { readonly id: string; readonly label: string }[];
  readonly policy: GroupedBarPolicy;
  readonly direction: "asc" | "desc" | "neutral";
  /** Max ABSOLUTE cell value across the whole grid (drives shared scale). */
  readonly max_cell_value: number;
  readonly present_count: number;
  readonly missing_count: number;
}

// ─── facet panel input/output ──────────────────────────────────────

export interface FacetPanelInput<T> {
  /** Domain rows (one per panel-row, across panels). */
  readonly rows: readonly T[];
  /** Project a row to its panel id + value. */
  readonly toPanelRow: (row: T) => {
    readonly panel_id: string;
    readonly panel_label: string;
    readonly panel_order?: number;
    readonly id: string;
    readonly label: string;
    readonly pinned_rank?: number | null;
    readonly value: number | null;
  };
  /** Sort policy for ROWS within each panel. */
  readonly row_policy: GroupedBarPolicy;
  /** Sort policy for PANELS themselves. */
  readonly panel_policy: FacetPanelPolicy;
  /** Aggregator used to derive a panel-level value from its rows. Default `sum`. */
  readonly panel_aggregator?: CellAggregator;
  readonly options?: SortOptions;
  readonly label_threshold?: number;
  /**
   * Shared-scale decision (per plan rule). When `true` (default),
   * every panel uses the GLOBAL `max_abs_value`. When `false`, each
   * panel uses its OWN max. Renderers must honour the
   * per-panel `max_abs_value` accordingly.
   */
  readonly shared_scale?: boolean;
}

export interface FacetPanelRowVM<T> {
  readonly row: T;
  readonly id: string;
  readonly label: string;
  readonly value: number | null;
  readonly rank: number | null;
  readonly is_pinned: boolean;
  readonly is_missing: boolean;
  readonly is_max_in_panel: boolean;
  readonly show_value_label: boolean;
}

export interface FacetPanelVM<T> {
  readonly panel_id: string;
  readonly panel_label: string;
  readonly rows: readonly FacetPanelRowVM<T>[];
  /** Panel-level aggregated value (drives panel order). */
  readonly panel_value: number | null;
  /** Max ABSOLUTE value within this panel. */
  readonly max_abs_value: number;
  readonly present_count: number;
  readonly missing_count: number;
}

export interface FacetPanelGridViewModel<T> {
  readonly panels: readonly FacetPanelVM<T>[];
  readonly row_policy: GroupedBarPolicy;
  readonly panel_policy: FacetPanelPolicy;
  readonly shared_scale: boolean;
  /** Global max — only meaningful when `shared_scale` is true. */
  readonly global_max_abs_value: number;
}

// ─── shared internals ──────────────────────────────────────────────

function isMissingValue(v: number | null | undefined): boolean {
  return v === null || v === undefined || Number.isNaN(v);
}

function aggregate(
  cells: readonly { readonly group_id: string; readonly value: number | null }[],
  agg: CellAggregator,
): number | null {
  switch (agg.kind) {
    case "sum": {
      let total = 0;
      let any_present = false;
      for (const c of cells) {
        if (!isMissingValue(c.value)) {
          total += c.value as number;
          any_present = true;
        }
      }
      return any_present ? total : null;
    }
    case "max": {
      let m: number | null = null;
      for (const c of cells) {
        if (!isMissingValue(c.value)) {
          const v = c.value as number;
          if (m === null || v > m) m = v;
        }
      }
      return m;
    }
    case "mean": {
      let total = 0;
      let count = 0;
      for (const c of cells) {
        if (!isMissingValue(c.value)) {
          total += c.value as number;
          count += 1;
        }
      }
      return count > 0 ? total / count : null;
    }
    case "pick_group": {
      const hit = cells.find((c) => c.group_id === agg.group_id);
      return hit && !isMissingValue(hit.value) ? (hit.value as number) : null;
    }
    default: {
      const exhaustive: never = agg;
      throw new Error(`Unknown aggregator: ${(exhaustive as { kind: string }).kind}`);
    }
  }
}

// ─── public: buildHorizontalGroupedBarViewModel ────────────────────

export function buildHorizontalGroupedBarViewModel<T>(
  input: GroupedBarInput<T>,
): GroupedBarViewModel<T> {
  const aggregator = input.aggregator ?? { kind: "sum" };
  const threshold = input.label_threshold ?? 0.05;
  const options = input.options ?? {};

  // 1. Project rows.
  const projected = input.rows.map((row, index) => ({
    index,
    row,
    proj: input.toRow(row),
  }));

  // 2. Resolve group order (explicit or first-seen).
  const group_order: { id: string; label: string }[] = [];
  const seen = new Set<string>();
  if (input.group_order) {
    // Build label index from projected cells.
    const label_by_id = new Map<string, string>();
    for (const p of projected) {
      for (const c of p.proj.cells) {
        if (!label_by_id.has(c.group_id)) label_by_id.set(c.group_id, c.group_label);
      }
    }
    for (const gid of input.group_order) {
      if (seen.has(gid)) continue;
      seen.add(gid);
      group_order.push({ id: gid, label: label_by_id.get(gid) ?? gid });
    }
  } else {
    for (const p of projected) {
      for (const c of p.proj.cells) {
        if (seen.has(c.group_id)) continue;
        seen.add(c.group_id);
        group_order.push({ id: c.group_id, label: c.group_label });
      }
    }
  }

  // 3. Rectangularise + compute sort_value + max_cell_value.
  let max_cell_value = 0;
  let present_count = 0;
  let missing_count = 0;
  const rect = projected.map((p) => {
    const by_group = new Map<string, BarCell>();
    for (const c of p.proj.cells) by_group.set(c.group_id, c);
    const cells: BarCell[] = group_order.map((g) => {
      const hit = by_group.get(g.id);
      if (hit) return hit;
      // Fill missing cell so the grid stays rectangular.
      return { group_id: g.id, group_label: g.label, value: null };
    });
    for (const c of cells) {
      if (isMissingValue(c.value)) {
        missing_count += 1;
      } else {
        present_count += 1;
        const abs = Math.abs(c.value as number);
        if (abs > max_cell_value) max_cell_value = abs;
      }
    }
    const sort_value = aggregate(cells, aggregator);
    return { ...p, cells, sort_value };
  });

  // 4. Sort rows.
  const sort_items: SortItem[] = rect.map((r) => ({
    id: r.proj.id,
    label: r.proj.label,
    value: r.sort_value,
    pinned_rank: r.proj.pinned_rank,
  }));
  const sorted_items = applySortPolicy(sort_items, input.policy as SortPolicy, options);
  // Re-pair by id (id is unique per row by contract).
  const by_id = new Map<string, (typeof rect)[number]>();
  for (const r of rect) by_id.set(r.proj.id, r);
  const sorted = sorted_items.map((it) => by_id.get(it.id) as (typeof rect)[number]);

  // 5. Rank over rows with non-null sort_value.
  const rank_dir = sortDirectionForPolicy(input.policy as SortPolicy, options);
  const present_rows = sorted.filter((r) => !isMissingValue(r.sort_value));
  const cmp = (a: (typeof rect)[number], b: (typeof rect)[number]): number => {
    const av = a.sort_value as number;
    const bv = b.sort_value as number;
    return rank_dir === "asc" ? av - bv : bv - av;
  };
  const ranked = present_rows.slice().sort(cmp);
  const rank_by_index = new Map<number, number>();
  ranked.forEach((r, i) => rank_by_index.set(r.index, i + 1));

  // 6. Emit view-model.
  const out_rows: GroupedBarRowVM<T>[] = sorted.map((r) => {
    const is_row_missing = isMissingValue(r.sort_value);
    return {
      row: r.row,
      id: r.proj.id,
      label: r.proj.label,
      cells: r.cells.map((c) => {
        const cell_missing = isMissingValue(c.value);
        const abs = cell_missing ? 0 : Math.abs(c.value as number);
        const show_value_label
          = !cell_missing && max_cell_value > 0 && abs >= max_cell_value * threshold;
        return { ...c, is_missing: cell_missing, show_value_label };
      }),
      sort_value: r.sort_value,
      rank: rank_by_index.get(r.index) ?? null,
      is_pinned:
        typeof r.proj.pinned_rank === "number" && r.proj.pinned_rank >= 0,
      is_missing: is_row_missing,
    };
  });

  return {
    rows: out_rows,
    group_order: group_order.map((g) => ({ id: g.id, label: g.label })),
    policy: input.policy,
    direction: sortDirectionForPolicy(input.policy as SortPolicy, options),
    max_cell_value,
    present_count,
    missing_count,
  };
}

// ─── public: buildFacetPanelGridViewModel ──────────────────────────

export function buildFacetPanelGridViewModel<T>(
  input: FacetPanelInput<T>,
): FacetPanelGridViewModel<T> {
  const panel_aggregator = input.panel_aggregator ?? { kind: "sum" };
  const threshold = input.label_threshold ?? 0.05;
  const options = input.options ?? {};
  const shared_scale = input.shared_scale ?? true;

  // 1. Project + bucket by panel_id.
  interface PanelBucket {
    panel_id: string;
    panel_label: string;
    panel_order?: number;
    rows: Array<{
      index: number;
      row: T;
      id: string;
      label: string;
      pinned_rank?: number | null;
      value: number | null;
    }>;
  }
  const buckets = new Map<string, PanelBucket>();
  input.rows.forEach((row, index) => {
    const p = input.toPanelRow(row);
    let bucket = buckets.get(p.panel_id);
    if (!bucket) {
      bucket = {
        panel_id: p.panel_id,
        panel_label: p.panel_label,
        panel_order: p.panel_order,
        rows: [],
      };
      buckets.set(p.panel_id, bucket);
    }
    bucket.rows.push({
      index,
      row,
      id: p.id,
      label: p.label,
      pinned_rank: p.pinned_rank,
      value: p.value,
    });
  });

  // 2. For each bucket: sort rows + compute panel_value + max_abs_value.
  const panel_vms: FacetPanelVM<T>[] = [];
  let global_max_abs_value = 0;
  for (const bucket of buckets.values()) {
    const cells = bucket.rows.map((r) => ({ group_id: r.id, value: r.value }));
    const panel_value = aggregate(cells, panel_aggregator);

    let panel_max = 0;
    let panel_present = 0;
    let panel_missing = 0;
    for (const r of bucket.rows) {
      if (isMissingValue(r.value)) {
        panel_missing += 1;
      } else {
        panel_present += 1;
        const abs = Math.abs(r.value as number);
        if (abs > panel_max) panel_max = abs;
      }
    }
    if (panel_max > global_max_abs_value) global_max_abs_value = panel_max;

    // Row sort within panel.
    const row_items: SortItem[] = bucket.rows.map((r) => ({
      id: r.id,
      label: r.label,
      value: r.value,
      pinned_rank: r.pinned_rank,
    }));
    const sorted_row_items = applySortPolicy(
      row_items,
      input.row_policy as SortPolicy,
      options,
    );
    const by_id = new Map<string, (typeof bucket.rows)[number]>();
    for (const r of bucket.rows) by_id.set(r.id, r);
    const sorted_rows = sorted_row_items.map(
      (it) => by_id.get(it.id) as (typeof bucket.rows)[number],
    );

    // Row ranks within panel (by value, direction-aware).
    const row_dir = sortDirectionForPolicy(input.row_policy as SortPolicy, options);
    const present_rows = sorted_rows.filter((r) => !isMissingValue(r.value));
    const cmp = (
      a: (typeof bucket.rows)[number],
      b: (typeof bucket.rows)[number],
    ): number => {
      const av = a.value as number;
      const bv = b.value as number;
      return row_dir === "asc" ? av - bv : bv - av;
    };
    const ranked = present_rows.slice().sort(cmp);
    const rank_by_id = new Map<string, number>();
    ranked.forEach((r, i) => rank_by_id.set(r.id, i + 1));

    // Build row VMs. `is_max_in_panel` and `show_value_label` use the
    // panel-local max when `shared_scale === false`, else global.
    const scale_max = shared_scale ? global_max_abs_value : panel_max;
    const out_rows: FacetPanelRowVM<T>[] = sorted_rows.map((r) => {
      const is_missing = isMissingValue(r.value);
      const abs = is_missing ? 0 : Math.abs(r.value as number);
      const is_max_in_panel = !is_missing && panel_max > 0 && abs === panel_max;
      const show_value_label
        = !is_missing && scale_max > 0 && abs >= scale_max * threshold;
      return {
        row: r.row,
        id: r.id,
        label: r.label,
        value: r.value,
        rank: rank_by_id.get(r.id) ?? null,
        is_pinned: typeof r.pinned_rank === "number" && r.pinned_rank >= 0,
        is_missing,
        is_max_in_panel,
        show_value_label,
      };
    });
    panel_vms.push({
      panel_id: bucket.panel_id,
      panel_label: bucket.panel_label,
      rows: out_rows,
      panel_value,
      max_abs_value: panel_max,
      present_count: panel_present,
      missing_count: panel_missing,
    });
  }

  // 3. Recompute show_value_label / rank for shared_scale=true now that
  //    global_max_abs_value is final (we did one pass — but global was
  //    finalised by the end of the loop, and we used it via `scale_max`
  //    AFTER the bucket's own scan, so for shared_scale we'd need a
  //    second pass IF any later panel raised the global max. Do that
  //    second pass now to keep the contract honest.)
  if (shared_scale) {
    for (const panel of panel_vms) {
      // re-emit rows with the now-final global_max_abs_value
      const rebuilt: FacetPanelRowVM<T>[] = panel.rows.map((r) => {
        const is_missing = r.is_missing;
        const abs = is_missing ? 0 : Math.abs(r.value as number);
        const show_value_label
          = !is_missing
            && global_max_abs_value > 0
            && abs >= global_max_abs_value * threshold;
        return { ...r, show_value_label };
      });
      // Mutate readonly via cast — the panel object was just built here.
      (panel as unknown as { rows: FacetPanelRowVM<T>[] }).rows = rebuilt;
    }
  }

  // 4. Sort panels.
  const panel_items: SortItem[] = panel_vms.map((p) => {
    // Build an item that supports both order- and value-based policies.
    // The bucket carries the optional `panel_order` from the first row
    // that mentioned this panel.
    const panel_order = buckets.get(p.panel_id)?.panel_order;
    return {
      id: p.panel_id,
      label: p.panel_label,
      value: p.panel_value,
      order: panel_order,
    };
  });
  const sorted_panel_items = applySortPolicy(
    panel_items,
    input.panel_policy as SortPolicy,
    options,
  );
  const panel_by_id = new Map<string, FacetPanelVM<T>>();
  for (const p of panel_vms) panel_by_id.set(p.panel_id, p);
  const sorted_panels = sorted_panel_items.map(
    (it) => panel_by_id.get(it.id) as FacetPanelVM<T>,
  );

  return {
    panels: sorted_panels,
    row_policy: input.row_policy,
    panel_policy: input.panel_policy,
    shared_scale,
    global_max_abs_value,
  };
}
