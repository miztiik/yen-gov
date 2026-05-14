import { z } from "zod";

export const StackedTrendCategory = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  fill: z.string().regex(/^#[0-9a-f]{6}$/i).optional(),
  order: z.number().optional(),
});

export const StackedTrendSegment = z.object({
  category_id: z.string().min(1),
  value: z.number().nullable(),
  availability: z.enum(["present", "missing", "not_applicable"]).default("present"),
  availability_label: z.string().optional(),
});

export const StackedTrendBar = z.object({
  period_id: z.string().min(1),
  period_label: z.string().min(1),
  order: z.number(),
  kind: z.string().optional(),
  segments: z.array(StackedTrendSegment),
  total: z.number().optional(),
});

export const StackedTrendSeriesBreak = z.object({
  at_period_id: z.string(),
  kind: z.string(),
  note: z.string(),
});

export const StackedTrendUnitChange = z.object({
  at_period_id: z.string(),
  from_unit: z.string(),
  to_unit: z.string(),
  note: z.string(),
});

export const StackedTrendHonesty = z.object({
  comparability: z.enum([
    "comparable_across_states",
    "comparable_with_normalisation",
    "not_comparable_across_states",
  ]).optional(),
  attribution_geography: z.enum([
    "where_produced",
    "where_consumed",
    "where_billed",
    "where_resident",
    "where_administered",
  ]).optional(),
  methodology_vintage: z.string().optional(),
  series_breaks: z.array(StackedTrendSeriesBreak).optional(),
  unit_changed_at: z.array(StackedTrendUnitChange).optional(),
  notes: z.string().optional(),
}).optional();

export const StackedTrendHeadline = z.object({
  rule: z.enum(["max_latest_with_streak", "designated", "max_lifetime", "none"]),
  text: z.string(),
  so_what: z.string().optional(),
  highlight_category_id: z.string().optional(),
}).optional();

export const StackedTrendSource = z.object({
  url: z.string().url(),
  fetched_at: z.string(),
  name: z.string().optional(),
  authority: z.string().optional(),
});

export const StackedTrendModel = z.object({
  unit: z.object({
    id: z.string(),
    label: z.string(),
    value_kind: z.enum(["count", "currency", "rate", "share", "raw"]),
  }),
  x_axis_label: z.string(),
  bar_sort: z.enum([
    "by_order_ascending",
    "by_total_descending",
    "by_pinned_then_order",
  ]).default("by_order_ascending"),
  categories: z.array(StackedTrendCategory).min(1),
  bars: z.array(StackedTrendBar).min(1),
  headline: StackedTrendHeadline,
  honesty: StackedTrendHonesty,
  sources: z.array(StackedTrendSource),
  dimension: z.string().min(1),
  default_mode: z.enum(["percent", "absolute"]).default("percent"),
});

export type StackedTrendCategory = z.infer<typeof StackedTrendCategory>;
export type StackedTrendSegment = z.infer<typeof StackedTrendSegment>;
export type StackedTrendBar = z.infer<typeof StackedTrendBar>;
export type StackedTrendHonesty = z.infer<typeof StackedTrendHonesty>;
export type StackedTrendHeadline = z.infer<typeof StackedTrendHeadline>;
export type StackedTrendSource = z.infer<typeof StackedTrendSource>;
export type StackedTrendModel = z.infer<typeof StackedTrendModel>;

export const OTHER_CATEGORY_ID = "__OTHER__";
export const OTHER_CATEGORY_FILL = "#9ca3af";
