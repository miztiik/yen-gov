// Grapher catalogue loader (frontend-owned render hints).
//
// Per ADR-0045, visualization choice (chart_type, default_mode, renderer_rules,
// facet_labels, per-topic dimension) is a frontend concern and lives outside
// the canonical data schemas. This module loads `datasets/grapher/*.json` and
// exposes typed lookup helpers.
//
// U4 (2026-06-05): widened `ChartType` from 3 to 12 base-set members so the
// union is 1:1 with docs/reference/chart-index.md section 1, the doc the
// chart-drift gate (section 22.6 of the rip plan) asserts against. Added
// `chart_types?: ChartType[]` to IndicatorRender + TopicRender; the singular
// `chart_type` field is retained as a DEPRECATED alias kept readable per
// ADR-0047 (reader-before-writer) until F2a / F2b consolidate the renderer
// set. `DEPRECATED_CHART_TYPE_ALIASES` + `normalizeChartType()` map the one
// legacy literal (`stacked-trend`) onto the closest base-set member (`line`).
//
// See also:
//   - datasets/grapher/AGENTS.md
//   - docs/architecture/decisions/0045-grapher-catalogue-split.md
//   - docs/reference/chart-index.md (the 12-member ChartType contract)
//   - frontend/src/lib/grapher/chart-index.drift.test.ts (the drift gate)
//   - frontend/src/lib/grapher/feasibleAt.ts (the U4 pure-function picker source)

import { DATA_BASE } from "../paths";

/**
 * Canonical ChartType set (1:1 with docs/reference/chart-index.md section 1).
 *
 * Twelve base-set members; the optional `Radar` (section-1 row 13) stays out
 * of the union until the >= 2-indicator rule (chart-index section 5) is met
 * for it. The drift gate enforces this 1:1 mapping plus the matrix-coverage
 * rule that every section-2 matrix row lists `ranked` as a feasible encoding
 * (the guaranteed terminal fallback per plan section 23.5).
 */
export type ChartType =
  | "choropleth"
  | "choropleth-symbol"
  | "matrix"
  | "ranked"
  | "stacked"
  | "diverging"
  | "line"
  | "scatter"
  | "dumbbell-dot"
  | "dumbbell-arrow"
  | "treemap"
  | "circle-pack";

/**
 * DEPRECATED legacy chart-type literals retained for back-compat READING
 * only. New writes (in `datasets/grapher/*.json` and ingest emitters) MUST
 * use one of the `ChartType` members above. Removed after F2a / F2b
 * consolidate the renderer set; reader-before-writer per ADR-0047.
 */
export type DeprecatedChartType = "stacked-trend";

/** Any value the reader may encounter while JSON migration is in flight. */
export type AnyChartType = ChartType | DeprecatedChartType;

/**
 * Map of deprecated chart-type literals to their closest base-set
 * equivalent. Consulted by `normalizeChartType()` so callers can pass
 * `AnyChartType` and receive a guaranteed `ChartType`.
 *
 * `stacked-trend` is currently realised by `StackedTrendV2.svelte` (a
 * stacked area over time, used by TopicLanding cards under
 * `chart_type: "stacked-trend"`). It will be subsumed by F2a/F2b's
 * `bar-stacked` + `TimeControl` composition; in the meantime it aliases
 * to `line` because the matrix row "one measure, 1-3 named series over
 * time" is the closest base-set shape that preserves the
 * facet-over-time intent. The renderer itself stays valid; this is a
 * type-system convenience for feasibleAt() callers, not a runtime swap.
 */
export const DEPRECATED_CHART_TYPE_ALIASES: Readonly<
  Record<DeprecatedChartType, ChartType>
> = Object.freeze({
  "stacked-trend": "line",
});

/** Coerce any historically-valid chart-type literal to a current `ChartType`. */
export function normalizeChartType(t: AnyChartType): ChartType {
  const alias = (
    DEPRECATED_CHART_TYPE_ALIASES as Record<string, ChartType>
  )[t];
  return alias ?? (t as ChartType);
}

/**
 * Resolve the on-load default chart type for a render-hint row.
 *
 * Precedence:
 *   1. `chart_types[0]` (the U4 plural; what new writes carry)
 *   2. `chart_type` (the deprecated singular; what pre-U4 JSON carried)
 *   3. `null` (no hint; caller falls through to feasibleAt() default)
 *
 * The returned value is always normalised to a current `ChartType` (no
 * deprecated literal leaks past this seam).
 */
export function resolveDefaultChartType(row: {
  chart_types?: readonly AnyChartType[] | null;
  chart_type?: AnyChartType | null;
}): ChartType | null {
  const t = row.chart_types?.[0] ?? row.chart_type ?? null;
  return t == null ? null : normalizeChartType(t);
}

export type DefaultMode = "absolute" | "percent";

export interface IndicatorRender {
  indicator_id: string;
  /**
   * DEPRECATED singular chart-type hint. Reader keeps this field readable
   * per ADR-0047 until F2a / F2b consolidate the renderer set; new writes
   * use `chart_types`. When both are present, `chart_types[0]` wins.
   */
  chart_type?: AnyChartType | null;
  /** Ordered list of feasible chart types (catalogue v1.1 / U4). `chart_types[0]`
   *  is the on-load default; the rest are switcher segments. */
  chart_types?: AnyChartType[];
  default_mode?: DefaultMode | null;
  renderer_rules?: string[];
  facet_labels?: Record<string, string> | null;
}

export interface TopicRender {
  topic_id: string;
  indicator_id: string;
  /** DEPRECATED singular per-topic chart-type override. See IndicatorRender.chart_type. */
  chart_type?: AnyChartType | null;
  /** Ordered list of feasible chart types (catalogue v1.1 / U4). */
  chart_types?: AnyChartType[];
  dimension?: string | null;
}

export interface GrapherIndicatorCatalogue {
  $schema: string;
  $schema_version: string;
  indicators: IndicatorRender[];
}

export interface GrapherTopicCatalogue {
  $schema: string;
  $schema_version: string;
  topics: TopicRender[];
}

let _indicatorCache: Promise<GrapherIndicatorCatalogue> | null = null;
let _topicCache: Promise<GrapherTopicCatalogue> | null = null;

/** Fetch the grapher indicator render catalogue. Cached for the page lifetime. */
export function fetchGrapherIndicatorCatalogue(): Promise<GrapherIndicatorCatalogue> {
  if (_indicatorCache) return _indicatorCache;
  _indicatorCache = (async () => {
    const res = await fetch(`${DATA_BASE}/grapher/indicator_render.json`);
    if (!res.ok) {
      throw new Error(
        `fetch /grapher/indicator_render.json failed: ${res.status} ${res.statusText}`,
      );
    }
    return (await res.json()) as GrapherIndicatorCatalogue;
  })();
  return _indicatorCache;
}

/** Fetch the grapher topic render catalogue. Cached for the page lifetime. */
export function fetchGrapherTopicCatalogue(): Promise<GrapherTopicCatalogue> {
  if (_topicCache) return _topicCache;
  _topicCache = (async () => {
    const res = await fetch(`${DATA_BASE}/grapher/topic_render.json`);
    if (!res.ok) {
      throw new Error(
        `fetch /grapher/topic_render.json failed: ${res.status} ${res.statusText}`,
      );
    }
    return (await res.json()) as GrapherTopicCatalogue;
  })();
  return _topicCache;
}

/** Lookup render hints for an indicator. Returns null if no row. */
export function lookupIndicatorRender(
  cat: GrapherIndicatorCatalogue,
  indicator_id: string,
): IndicatorRender | null {
  return cat.indicators.find((r) => r.indicator_id === indicator_id) ?? null;
}

/** Lookup per-topic per-indicator render override. Returns null if no row. */
export function lookupTopicRender(
  cat: GrapherTopicCatalogue,
  topic_id: string,
  indicator_id: string,
): TopicRender | null {
  return (
    cat.topics.find(
      (r) => r.topic_id === topic_id && r.indicator_id === indicator_id,
    ) ?? null
  );
}

/**
 * Reset the in-module caches. Test-only.
 */
export function _resetGrapherCachesForTests(): void {
  _indicatorCache = null;
  _topicCache = null;
}
