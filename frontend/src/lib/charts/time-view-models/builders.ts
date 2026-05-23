// View-model builders for dumbbell_range and time_series_line
// chart candidates (Phase 1.6 final slice).
//
// Doctrine ties:
//
//   - Plan §1.6: builders for `dumbbell_range`, `time_series_line`.
//
//   - Plan rules honoured:
//
//       * "Nulls/missing values stay visible and sort last."
//       * "Direct labels should be part of the view-model where the
//         renderer needs stable label eligibility." → both builders
//         emit `show_endpoint_label` (dumbbell) and
//         `show_direct_end_label` (time-series) flags.
//
//   - R-08 BBA: pure builders; renderers feed domain rows + a
//     projection.
//
//   - CLAUDE.md §10: closed-union narrowed policies for each builder.

import { applySortPolicy, sortDirectionForPolicy } from "../sort-policy/helpers";
import { parseLeadingYear } from "../temporal-viewport/helpers";
import type { SortItem, SortOptions, SortPolicy } from "../sort-policy/types";

// ─── dumbbell_range ────────────────────────────────────────────────

/**
 * Sort policies a `dumbbell_range` view-model permits. The sort key
 * defaults to the LATEST endpoint's value; `value_*` policies use
 * that. `latest_change` uses `|latest - earliest|`.
 */
export type DumbbellRangePolicy =
  | "value_asc"
  | "value_desc"
  | "rank_best_first"
  | "pinned_then_value"
  | "latest_change"
  | "alphabetical";

export interface DumbbellRangeInput<T> {
  readonly rows: readonly T[];
  /**
   * Projects a row onto two endpoints. The renderer-supplied tuple is
   * `[earliest, latest]` — order matters for delta sign / direct labels.
   * Either endpoint may be null (= missing); both null = "no data" row.
   */
  readonly toEndpoints: (row: T) => {
    readonly id: string;
    readonly label: string;
    readonly pinned_rank?: number | null;
    readonly earliest: { readonly period_label: string; readonly value: number | null };
    readonly latest: { readonly period_label: string; readonly value: number | null };
  };
  readonly policy: DumbbellRangePolicy;
  readonly options?: SortOptions;
  /** Threshold for `show_endpoint_label` (default 0.05 of `max_abs_value`). */
  readonly label_threshold?: number;
}

export interface DumbbellEndpointVM {
  readonly period_label: string;
  readonly value: number | null;
  readonly is_missing: boolean;
  readonly show_endpoint_label: boolean;
}

export interface DumbbellRowVM<T> {
  readonly row: T;
  readonly id: string;
  readonly label: string;
  readonly earliest: DumbbellEndpointVM;
  readonly latest: DumbbellEndpointVM;
  /** `latest - earliest`; null when either endpoint is missing. */
  readonly delta: number | null;
  /** `Math.abs(delta)`; null when delta is null. */
  readonly abs_delta: number | null;
  /** "up" | "down" | "flat" | "missing". */
  readonly direction: "up" | "down" | "flat" | "missing";
  /** Whether to show a delta / gap label between the dots. */
  readonly show_delta_label: boolean;
  /** 1-based rank by the policy's sort key (latest value or |Δ|). */
  readonly rank: number | null;
  readonly is_pinned: boolean;
  readonly is_missing: boolean;
}

export interface DumbbellRangeViewModel<T> {
  readonly rows: readonly DumbbellRowVM<T>[];
  readonly policy: DumbbellRangePolicy;
  readonly direction: "asc" | "desc" | "neutral";
  /** Max absolute endpoint value across all rows (drives shared scale). */
  readonly max_abs_value: number;
  /** Max absolute delta across all rows. */
  readonly max_abs_delta: number;
  readonly present_count: number;
  readonly missing_count: number;
}

// ─── time_series_line ──────────────────────────────────────────────

/**
 * Sort policies a `time_series_line` view-model permits for the
 * SERIES axis (the lines themselves). The points inside each series
 * are always chronological.
 */
export type TimeSeriesLinePolicy =
  | "value_desc"
  | "value_asc"
  | "rank_best_first"
  | "pinned_then_value"
  | "latest_change"
  | "alphabetical";

export interface TimeSeriesLineInput<T> {
  readonly rows: readonly T[];
  /**
   * Projects a row onto a SERIES + a POINT. Multiple rows with the
   * same `series_id` get bucketed into one series.
   */
  readonly toPoint: (row: T) => {
    readonly series_id: string;
    readonly series_label: string;
    readonly series_pinned_rank?: number | null;
    readonly series_colour?: string;
    /** Period id — used for x-axis ordering via `parseLeadingYear`. */
    readonly period_id: string;
    /** Citizen-facing period label. */
    readonly period_label: string;
    readonly value: number | null;
  };
  /** Series sort policy. Points inside a series are always chronological. */
  readonly policy: TimeSeriesLinePolicy;
  readonly options?: SortOptions;
  /**
   * Visible window of period_ids (optional). When provided, points
   * outside the window are dropped FROM THE VIEW-MODEL (renderer
   * draws only the windowed points). Series with zero windowed
   * points still appear (as flat-line-with-no-data).
   */
  readonly visible_period_ids?: readonly string[];
  /**
   * When true (default), suppress lines across a series-break (a
   * null point between two present points). When false, the
   * renderer should bridge nulls with a dashed line.
   */
  readonly suppress_breaks?: boolean;
  /** Threshold for `show_direct_end_label` (default 0.05 of global max). */
  readonly label_threshold?: number;
}

export interface TimeSeriesPointVM {
  readonly period_id: string;
  readonly period_label: string;
  readonly year: number | null;
  readonly value: number | null;
  readonly is_missing: boolean;
  /** True when this point is the START of a series-break segment. */
  readonly is_break_start: boolean;
}

export interface TimeSeriesSeriesVM<T> {
  readonly series_id: string;
  readonly series_label: string;
  readonly series_colour?: string;
  /** Original rows in this series (in input order). */
  readonly source_rows: readonly T[];
  /** Points in chronological order (windowed if `visible_period_ids` set). */
  readonly points: readonly TimeSeriesPointVM[];
  /** Latest non-null value across the visible points; null if all missing. */
  readonly latest_value: number | null;
  /** Earliest non-null value across visible points. */
  readonly earliest_value: number | null;
  /** `|latest - earliest|` over the visible window; null when either side missing. */
  readonly abs_delta: number | null;
  /** Whether the renderer should print a direct end-of-line label. */
  readonly show_direct_end_label: boolean;
  readonly is_pinned: boolean;
  /** True when no visible points have a present value. */
  readonly is_missing: boolean;
  /** 1-based rank by latest_value (direction-aware), over series with present data. */
  readonly rank: number | null;
}

export interface TimeSeriesLineViewModel<T> {
  readonly series: readonly TimeSeriesSeriesVM<T>[];
  /** Global axis order — every period_id seen in `rows[*]`, deduped, chronological. */
  readonly period_axis: readonly { readonly period_id: string; readonly period_label: string; readonly year: number | null }[];
  readonly policy: TimeSeriesLinePolicy;
  readonly direction: "asc" | "desc" | "neutral";
  /** Max absolute value across all visible points (drives shared scale). */
  readonly max_abs_value: number;
  readonly suppress_breaks: boolean;
}

// ─── helpers ───────────────────────────────────────────────────────

function isMissingValue(v: number | null | undefined): boolean {
  return v === null || v === undefined || Number.isNaN(v);
}

// ─── public: buildDumbbellRangeViewModel ───────────────────────────

export function buildDumbbellRangeViewModel<T>(
  input: DumbbellRangeInput<T>,
): DumbbellRangeViewModel<T> {
  const threshold = input.label_threshold ?? 0.05;
  const options = input.options ?? {};

  const projected = input.rows.map((row, index) => {
    const p = input.toEndpoints(row);
    const e_missing = isMissingValue(p.earliest.value);
    const l_missing = isMissingValue(p.latest.value);
    const delta
      = !e_missing && !l_missing
        ? (p.latest.value as number) - (p.earliest.value as number)
        : null;
    return {
      index,
      row,
      proj: p,
      e_missing,
      l_missing,
      delta,
    };
  });

  // Global max-abs across BOTH endpoints.
  let max_abs_value = 0;
  let max_abs_delta = 0;
  for (const r of projected) {
    if (!r.e_missing) {
      const a = Math.abs(r.proj.earliest.value as number);
      if (a > max_abs_value) max_abs_value = a;
    }
    if (!r.l_missing) {
      const a = Math.abs(r.proj.latest.value as number);
      if (a > max_abs_value) max_abs_value = a;
    }
    if (r.delta !== null) {
      const ad = Math.abs(r.delta);
      if (ad > max_abs_delta) max_abs_delta = ad;
    }
  }

  // Build SortItems based on the policy's needs.
  const sort_items: SortItem[] = projected.map((r) => {
    // latest value is the primary sort key for value-based policies.
    // latest_change uses [earliest, latest] for |Δ|.
    return {
      id: r.proj.id,
      label: r.proj.label,
      value: r.proj.latest.value,
      pinned_rank: r.proj.pinned_rank,
      latest_two: [r.proj.earliest.value, r.proj.latest.value],
    };
  });
  const sorted_items = applySortPolicy(sort_items, input.policy as SortPolicy, options);
  const by_id = new Map<string, (typeof projected)[number]>();
  for (const r of projected) by_id.set(r.proj.id, r);
  const sorted = sorted_items.map((it) => by_id.get(it.id) as (typeof projected)[number]);

  // Rank over rows whose primary key is not missing.
  const rank_dir = sortDirectionForPolicy(input.policy as SortPolicy, options);
  const present_rows = sorted.filter((r) => !r.l_missing);
  const cmp = (a: (typeof projected)[number], b: (typeof projected)[number]): number => {
    const av = a.proj.latest.value as number;
    const bv = b.proj.latest.value as number;
    return rank_dir === "asc" ? av - bv : bv - av;
  };
  const ranked = present_rows.slice().sort(cmp);
  const rank_by_index = new Map<number, number>();
  ranked.forEach((r, i) => rank_by_index.set(r.index, i + 1));

  let present_count = 0;
  let missing_count = 0;
  const rows: DumbbellRowVM<T>[] = sorted.map((r) => {
    const row_missing = r.e_missing && r.l_missing;
    if (row_missing) missing_count += 1;
    else present_count += 1;

    const e_abs = r.e_missing ? 0 : Math.abs(r.proj.earliest.value as number);
    const l_abs = r.l_missing ? 0 : Math.abs(r.proj.latest.value as number);
    const e_show_label
      = !r.e_missing && max_abs_value > 0 && e_abs >= max_abs_value * threshold;
    const l_show_label
      = !r.l_missing && max_abs_value > 0 && l_abs >= max_abs_value * threshold;

    let direction: DumbbellRowVM<T>["direction"];
    if (r.delta === null) direction = "missing";
    else if (r.delta > 0) direction = "up";
    else if (r.delta < 0) direction = "down";
    else direction = "flat";

    // delta label visible when delta is non-trivial vs max_abs_delta.
    const show_delta_label
      = r.delta !== null
        && max_abs_delta > 0
        && Math.abs(r.delta) >= max_abs_delta * threshold;

    return {
      row: r.row,
      id: r.proj.id,
      label: r.proj.label,
      earliest: {
        period_label: r.proj.earliest.period_label,
        value: r.proj.earliest.value,
        is_missing: r.e_missing,
        show_endpoint_label: e_show_label,
      },
      latest: {
        period_label: r.proj.latest.period_label,
        value: r.proj.latest.value,
        is_missing: r.l_missing,
        show_endpoint_label: l_show_label,
      },
      delta: r.delta,
      abs_delta: r.delta === null ? null : Math.abs(r.delta),
      direction,
      show_delta_label,
      rank: rank_by_index.get(r.index) ?? null,
      is_pinned: typeof r.proj.pinned_rank === "number" && r.proj.pinned_rank >= 0,
      is_missing: row_missing,
    };
  });

  return {
    rows,
    policy: input.policy,
    direction: sortDirectionForPolicy(input.policy as SortPolicy, options),
    max_abs_value,
    max_abs_delta,
    present_count,
    missing_count,
  };
}

// ─── public: buildTimeSeriesLineViewModel ──────────────────────────

export function buildTimeSeriesLineViewModel<T>(
  input: TimeSeriesLineInput<T>,
): TimeSeriesLineViewModel<T> {
  const threshold = input.label_threshold ?? 0.05;
  const options = input.options ?? {};
  const suppress_breaks = input.suppress_breaks ?? true;
  const visible_set = input.visible_period_ids
    ? new Set(input.visible_period_ids)
    : null;

  // 1. Bucket points by series_id; record the series metadata at first sight.
  interface SeriesBucket {
    series_id: string;
    series_label: string;
    series_colour?: string;
    series_pinned_rank?: number | null;
    source_rows: T[];
    points: Array<{
      period_id: string;
      period_label: string;
      year: number | null;
      value: number | null;
    }>;
  }
  const buckets = new Map<string, SeriesBucket>();
  const period_seen = new Map<
    string,
    { period_label: string; year: number | null }
  >();

  for (const row of input.rows) {
    const p = input.toPoint(row);
    let bucket = buckets.get(p.series_id);
    if (!bucket) {
      bucket = {
        series_id: p.series_id,
        series_label: p.series_label,
        series_colour: p.series_colour,
        series_pinned_rank: p.series_pinned_rank,
        source_rows: [],
        points: [],
      };
      buckets.set(p.series_id, bucket);
    }
    bucket.source_rows.push(row);
    const year = parseLeadingYear(p.period_id);
    bucket.points.push({
      period_id: p.period_id,
      period_label: p.period_label,
      year,
      value: p.value,
    });
    if (!period_seen.has(p.period_id)) {
      period_seen.set(p.period_id, { period_label: p.period_label, year });
    }
  }

  // 2. Build the global period axis (chronological).
  const period_axis = Array.from(period_seen.entries())
    .map(([period_id, meta]) => ({ period_id, ...meta }))
    .sort((a, b) => {
      const ay = a.year;
      const by = b.year;
      const a_missing = ay === null;
      const b_missing = by === null;
      if (a_missing && b_missing) {
        if (a.period_id < b.period_id) return -1;
        if (a.period_id > b.period_id) return 1;
        return 0;
      }
      if (a_missing) return 1;
      if (b_missing) return -1;
      if (ay === by) {
        if (a.period_id < b.period_id) return -1;
        if (a.period_id > b.period_id) return 1;
        return 0;
      }
      return (ay as number) - (by as number);
    });

  // 3. For each bucket: sort points chronologically, apply window,
  //    mark break starts.
  let max_abs_value = 0;
  const series_intermediate = Array.from(buckets.values()).map((b) => {
    const sorted_points = b.points.slice().sort((p1, p2) => {
      const y1 = p1.year;
      const y2 = p2.year;
      const m1 = y1 === null;
      const m2 = y2 === null;
      if (m1 && m2) {
        if (p1.period_id < p2.period_id) return -1;
        if (p1.period_id > p2.period_id) return 1;
        return 0;
      }
      if (m1) return 1;
      if (m2) return -1;
      if (y1 === y2) {
        if (p1.period_id < p2.period_id) return -1;
        if (p1.period_id > p2.period_id) return 1;
        return 0;
      }
      return (y1 as number) - (y2 as number);
    });
    const windowed = visible_set
      ? sorted_points.filter((p) => visible_set.has(p.period_id))
      : sorted_points;

    // Mark break starts: a present point that follows a missing point
    // (or is the first point) starts a new visual segment.
    const point_vms: TimeSeriesPointVM[] = windowed.map((p, i) => {
      const is_missing = isMissingValue(p.value);
      if (!is_missing) {
        const abs = Math.abs(p.value as number);
        if (abs > max_abs_value) max_abs_value = abs;
      }
      let is_break_start = false;
      if (!is_missing) {
        const prev = windowed[i - 1];
        if (!prev || isMissingValue(prev.value)) is_break_start = true;
      }
      return { ...p, is_missing, is_break_start };
    });

    let earliest_value: number | null = null;
    let latest_value: number | null = null;
    for (const p of point_vms) {
      if (!p.is_missing) {
        if (earliest_value === null) earliest_value = p.value;
        latest_value = p.value;
      }
    }
    const abs_delta
      = earliest_value !== null && latest_value !== null
        ? Math.abs(latest_value - earliest_value)
        : null;

    return {
      bucket: b,
      point_vms,
      earliest_value,
      latest_value,
      abs_delta,
    };
  });

  // 4. Sort series by policy.
  const sort_items: SortItem[] = series_intermediate.map((s) => ({
    id: s.bucket.series_id,
    label: s.bucket.series_label,
    value: s.latest_value,
    pinned_rank: s.bucket.series_pinned_rank,
    latest_two: [s.earliest_value, s.latest_value],
  }));
  const sorted_items = applySortPolicy(sort_items, input.policy as SortPolicy, options);
  const by_id = new Map<string, (typeof series_intermediate)[number]>();
  for (const s of series_intermediate) by_id.set(s.bucket.series_id, s);
  const sorted = sorted_items.map(
    (it) => by_id.get(it.id) as (typeof series_intermediate)[number],
  );

  // 5. Rank by latest_value (direction-aware) over series with present data.
  const rank_dir = sortDirectionForPolicy(input.policy as SortPolicy, options);
  const present = sorted.filter((s) => s.latest_value !== null);
  const cmp = (
    a: (typeof series_intermediate)[number],
    b: (typeof series_intermediate)[number],
  ): number => {
    const av = a.latest_value as number;
    const bv = b.latest_value as number;
    return rank_dir === "asc" ? av - bv : bv - av;
  };
  const ranked = present.slice().sort(cmp);
  const rank_by_id = new Map<string, number>();
  ranked.forEach((s, i) => rank_by_id.set(s.bucket.series_id, i + 1));

  // 6. Emit VMs.
  const out_series: TimeSeriesSeriesVM<T>[] = sorted.map((s) => {
    const is_missing = s.latest_value === null;
    const show_direct_end_label
      = !is_missing
        && max_abs_value > 0
        && Math.abs(s.latest_value as number) >= max_abs_value * threshold;
    return {
      series_id: s.bucket.series_id,
      series_label: s.bucket.series_label,
      series_colour: s.bucket.series_colour,
      source_rows: s.bucket.source_rows,
      points: s.point_vms,
      latest_value: s.latest_value,
      earliest_value: s.earliest_value,
      abs_delta: s.abs_delta,
      show_direct_end_label,
      is_pinned:
        typeof s.bucket.series_pinned_rank === "number"
        && s.bucket.series_pinned_rank >= 0,
      is_missing,
      rank: rank_by_id.get(s.bucket.series_id) ?? null,
    };
  });

  return {
    series: out_series,
    period_axis,
    policy: input.policy,
    direction: sortDirectionForPolicy(input.policy as SortPolicy, options),
    max_abs_value,
    suppress_breaks,
  };
}

// `suppress_breaks` is honoured by the RENDERER — the view-model
// emits `is_break_start` per point so the renderer can decide whether
// to draw a line segment up to this point or start a new path.
