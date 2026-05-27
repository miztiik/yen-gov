// Overlay grapher catalogue render hints onto a topic catalogue.
//
// Per ADR-0045 + PR-A3b of docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md,
// the canonical topic catalogue's `chart_type` and `dimension` fields are
// being migrated to live in `datasets/grapher/topic_render.json`. PR-A3a
// shipped the grapher catalogue additively (zero deletions); A3b makes the
// frontend READ the grapher catalogue as the source of truth, with the
// legacy canonical fields kept as a transitional fallback until A3c
// physically deletes them from `topic-catalogue.schema.json` v2.0.
//
// Strategy: overlay at the FETCH SEAM. `fetchTopicCatalogue()` calls
// `applyGrapherOverlay()` before returning, so every downstream reader
// (TopicLanding.svelte, topic-dispatch.ts, StackedTrendArtifact.svelte)
// automatically sees grapher values without any per-call-site change. This
// keeps the migration single-seam and makes A3c a pure deletion.
//
// Invariant (locked by grapher/catalogue.parity.test.ts): for every
// (topic_id, indicator_id) pair the legacy catalogue carries a chart_type
// or dimension for, the grapher catalogue carries the IDENTICAL values.

import type { TopicCatalogue, CatalogueArtifact } from "../catalogue";
import type { GrapherTopicCatalogue, TopicRender } from "./catalogue";

/** Index a grapher topic catalogue by `(topic_id, indicator_id)` for O(1) lookup. */
function indexGrapherTopics(
  cat: GrapherTopicCatalogue,
): Map<string, TopicRender> {
  const m = new Map<string, TopicRender>();
  for (const r of cat.topics) {
    m.set(`${r.topic_id}::${r.indicator_id}`, r);
  }
  return m;
}

/**
 * Return a NEW topic catalogue with each indicator-kind artifact's
 * `chart_type` / `dimension` sourced from the grapher catalogue when
 * present. The legacy canonical value is the fallback (and is identical
 * to the grapher value when both exist, per parity test). Pure: no I/O.
 */
export function applyGrapherOverlay(
  topicCat: TopicCatalogue,
  grapherTopicCat: GrapherTopicCatalogue,
): TopicCatalogue {
  const idx = indexGrapherTopics(grapherTopicCat);
  return {
    ...topicCat,
    topics: topicCat.topics.map((t) => ({
      ...t,
      artifacts: t.artifacts.map((a): CatalogueArtifact => {
        if (a.kind !== "indicator") return a;
        const g = idx.get(`${t.id}::${a.id}`);
        if (!g) return a;
        return {
          ...a,
          chart_type: (g.chart_type ?? a.chart_type) as
            | "choropleth"
            | "ranked"
            | "stacked-trend"
            | undefined,
          dimension: g.dimension ?? a.dimension,
        };
      }),
    })),
  };
}
