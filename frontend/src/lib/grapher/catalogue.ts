// Grapher catalogue loader (frontend-owned render hints).
//
// Per ADR-0045, visualization choice (chart_type, default_mode, renderer_rules,
// facet_labels, per-topic dimension) is a frontend concern and lives outside
// the canonical data schemas. This module loads `datasets/grapher/*.json` and
// exposes typed lookup helpers.
//
// See also:
//   - datasets/grapher/AGENTS.md
//   - docs/architecture/decisions/0045-grapher-catalogue-split.md

import { DATA_BASE } from "../paths";

export type ChartType = "stacked-trend" | "ranked" | "choropleth";
export type DefaultMode = "absolute" | "percent";

export interface IndicatorRender {
  indicator_id: string;
  chart_type?: ChartType | null;
  default_mode?: DefaultMode | null;
  renderer_rules?: string[];
  facet_labels?: Record<string, string> | null;
}

export interface TopicRender {
  topic_id: string;
  indicator_id: string;
  chart_type?: ChartType | null;
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
