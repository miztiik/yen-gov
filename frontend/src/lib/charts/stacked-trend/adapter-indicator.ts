import { applyGlobalUnion, buildCategories, type RollupConfig, type RollupInputBar } from "./rollup";
import { computeHeadline, type HeadlineContext, type HeadlineRule } from "./headline";
import {
  StackedTrendModel,
  type StackedTrendBar,
  type StackedTrendModel as StackedTrendModelT,
} from "./types";

/** Subset of indicator.json shape this adapter consumes — typed minimally
 * so we don't pull the full schema into runtime. */
export interface IndicatorDoc {
  $schema_version?: string;
  sources: Array<{ url: string; fetched_at: string; name?: string; authority?: string }>;
  indicator: {
    id: string;
    title: string;
    unit: string;
    value_kind: "count" | "rate" | "share" | "currency" | "index" | "duration" | "raw";
    direction?: "higher_is_better" | "lower_is_better" | "neutral";
    time_grain: string;
    entity_kind: string;
    attribution_geography?: string;
    comparability?: string;
    methodology_vintage?: string;
    series_breaks?: Array<{ at_time: string; kind: string; note: string }>;
    notes?: string;
    chart_type?: string;
    default_mode?: "percent" | "absolute";
    /** Indicator schema 1.4: composer-supplied facet value → human label. */
    facet_labels?: Record<string, string>;
  };
  rows: Array<{
    entity_id: string;
    time: string;
    value: number | null;
    facet?: string | null;
  }>;
}

export type AdapterMode =
  | { kind: "temporal"; entity_id: string; entity_label?: string }
  | { kind: "spatial"; time: string; entity_labels?: Record<string, string>; pin_entity_ids?: string[] };

export interface AdapterOptions {
  mode: AdapterMode;
  config: RollupConfig;
  dimension: string;
  category_labels?: Record<string, string>;
  headline_rule?: HeadlineRule;
  headline_text?: string;
  validate?: boolean;
}

const MAP_VALUE_KIND: Record<string, "count" | "currency" | "rate" | "share" | "raw"> = {
  count: "count",
  rate: "rate",
  share: "share",
  currency: "currency",
  index: "raw",
  duration: "raw",
  raw: "raw",
};

export function indicatorToStackedTrend(
  doc: IndicatorDoc,
  opts: AdapterOptions,
): StackedTrendModelT {
  const facetted = doc.rows.filter((r) => r.facet != null && r.value != null);

  const inputBars: RollupInputBar[] =
    opts.mode.kind === "temporal"
      ? buildTemporalBars(facetted, opts.mode.entity_id)
      : buildSpatialBars(facetted, opts.mode.time, opts.mode.entity_labels);

  const rolled = applyGlobalUnion(inputBars, opts.config);
  const categories = buildCategories(
    rolled.named_category_ids,
    opts.category_labels ?? {},
    rolled.other_present,
  );

  const value_kind = MAP_VALUE_KIND[doc.indicator.value_kind] ?? "raw";
  const headlineCtx: HeadlineContext = {
    entity_label:
      opts.mode.kind === "temporal"
        ? opts.mode.entity_label ?? opts.mode.entity_id
        : opts.mode.time,
    category_labels: opts.category_labels ?? {},
    value_kind,
    unit_label: doc.indicator.unit,
    direction: doc.indicator.direction,
  };

  const headlineRule: HeadlineRule = opts.headline_rule ?? "max_lifetime";
  const headline =
    opts.headline_text != null
      ? { rule: "designated" as const, text: opts.headline_text }
      : computeHeadline(headlineRule, rolled.bars, headlineCtx);

  const bars: StackedTrendBar[] = rolled.bars
    .slice()
    .sort((a, b) => a.order - b.order);

  const seriesBreaks =
    doc.indicator.series_breaks?.map((b) => ({
      at_period_id: b.at_time,
      kind: b.kind,
      note: b.note,
    })) ?? undefined;

  const model: StackedTrendModelT = StackedTrendModel.parse({
    unit: { id: doc.indicator.unit, label: doc.indicator.unit, value_kind },
    x_axis_label: opts.mode.kind === "temporal" ? "Time" : "State",
    bar_sort: opts.mode.kind === "spatial" && opts.mode.pin_entity_ids?.length
      ? "by_pinned_then_order"
      : "by_order_ascending",
    categories,
    bars,
    headline,
    honesty: {
      comparability: doc.indicator.comparability as never,
      attribution_geography: doc.indicator.attribution_geography as never,
      methodology_vintage: doc.indicator.methodology_vintage,
      series_breaks: seriesBreaks,
      notes: doc.indicator.notes,
    },
    sources: doc.sources,
    dimension: opts.dimension,
    default_mode: doc.indicator.default_mode ?? "percent",
  });

  if (opts.validate ?? true) {
    StackedTrendModel.parse(model);
  }
  return model;
}

function buildTemporalBars(
  rows: IndicatorDoc["rows"],
  entity_id: string,
): RollupInputBar[] {
  const filtered = rows.filter((r) => r.entity_id === entity_id);
  const byTime = new Map<string, IndicatorDoc["rows"]>();
  for (const r of filtered) {
    if (!byTime.has(r.time)) byTime.set(r.time, []);
    byTime.get(r.time)!.push(r);
  }
  const sortedTimes = [...byTime.keys()].sort();
  return sortedTimes.map((time, i) => ({
    period_id: time,
    period_label: time,
    order: i,
    segments: (byTime.get(time) ?? []).map((r) => ({
      category_id: r.facet as string,
      value: r.value,
      availability: r.value == null ? ("missing" as const) : ("present" as const),
    })),
  }));
}

function buildSpatialBars(
  rows: IndicatorDoc["rows"],
  time: string,
  entity_labels?: Record<string, string>,
): RollupInputBar[] {
  const filtered = rows.filter((r) => r.time === time);
  const byEntity = new Map<string, IndicatorDoc["rows"]>();
  for (const r of filtered) {
    if (!byEntity.has(r.entity_id)) byEntity.set(r.entity_id, []);
    byEntity.get(r.entity_id)!.push(r);
  }
  const totalFor = (eid: string) =>
    (byEntity.get(eid) ?? []).reduce((a, r) => a + (r.value ?? 0), 0);
  const sortedEntities = [...byEntity.keys()].sort(
    (a, b) => totalFor(b) - totalFor(a),
  );
  return sortedEntities.map((eid, i) => ({
    period_id: eid,
    period_label: entity_labels?.[eid] ?? eid,
    order: i,
    segments: (byEntity.get(eid) ?? []).map((r) => ({
      category_id: r.facet as string,
      value: r.value,
      availability: r.value == null ? ("missing" as const) : ("present" as const),
    })),
  }));
}
