// Parity test — grapher catalogue MUST carry identical render values to
// every legacy site that today owns those values, so PR-A3c can delete
// the legacy fields without changing behavior.
//
// Locks the seed of `datasets/grapher/{indicator_render,topic_render}.json`
// produced in PR-A3a against drift relative to:
//   - `datasets/taxonomy/topics.json`   (chart_type, dimension on artifact refs)
//   - canonical-backed rank-incompatible descriptors (renderer_rules now live here)
//
// Test direction is INCLUSIVE: every legacy row MUST have a matching
// grapher row with identical values. The grapher catalogue MAY carry
// additional rows (it was seeded broader than the live legacy surface to
// cover indicators not yet routed through the canonical allowlist).
//
// See:
//   - docs/architecture/decisions/0045-grapher-catalogue-split.md
//   - docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md PR-A3b

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { CANONICAL_BACKED_INDICATORS } from "../canonical/indicator-allowlist";
import type { GrapherIndicatorCatalogue, GrapherTopicCatalogue } from "./catalogue";

const REPO_ROOT = resolve(__dirname, "..", "..", "..", "..");

function loadJson<T>(rel: string): T {
  return JSON.parse(readFileSync(resolve(REPO_ROOT, rel), "utf-8")) as T;
}

interface LegacyTopicArtifact {
  kind: string;
  id: string;
  chart_type?: string;
  dimension?: string;
}

const RANK_SUPPRESSING_COMPARABILITY = new Set<string>([
  "directional_only",
  "comparable_within_state_over_time",
  "not_comparable_across_states",
]);

function effectiveIndicatorRenderId(
  desc: (typeof CANONICAL_BACKED_INDICATORS)[number],
): string {
  return desc.kind === "single"
    ? desc.canonical_indicator_id
    : desc.canonical_parent_indicator_id;
}
interface LegacyTopic {
  id: string;
  artifacts: LegacyTopicArtifact[];
}
interface LegacyTopicCatalogue {
  topics: LegacyTopic[];
}

describe("grapher catalogue parity (PR-A3b)", () => {
  const grapherIndicators = loadJson<GrapherIndicatorCatalogue>(
    "datasets/grapher/indicator_render.json",
  );
  const grapherTopics = loadJson<GrapherTopicCatalogue>(
    "datasets/grapher/topic_render.json",
  );
  const legacyTopics = loadJson<LegacyTopicCatalogue>(
    "datasets/taxonomy/topics.json",
  );

  const indicatorIdx = new Map(
    grapherIndicators.indicators.map((r) => [r.indicator_id, r]),
  );
  const topicIdx = new Map(
    grapherTopics.topics.map((r) => [`${r.topic_id}::${r.indicator_id}`, r]),
  );

  describe("topic-artifact chart_type / dimension", () => {
    // Post PR-A3c: chart_type + dimension have been stripped from
    // datasets/taxonomy/topics.json (canonical topic catalogue v2.0).
    // The render hints now live solely in datasets/grapher/topic_render.json,
    // applied at fetch time by applyGrapherOverlay (PR-A3b). With no
    // legacy-side values remaining there is nothing to cross-check;
    // this block stays as a sentinel so a future regression that
    // re-introduces chart_type/dimension into the canonical catalogue
    // would surface here as a failing assertion against the grapher row.
    it("legacy topics.json carries no chart_type / dimension (PR-A3c)", () => {
      for (const t of legacyTopics.topics) {
        for (const a of t.artifacts) {
          expect(a.chart_type, `${t.id}::${a.id} chart_type`).toBeUndefined();
          expect(a.dimension, `${t.id}::${a.id} dimension`).toBeUndefined();
        }
      }
    });
    for (const t of legacyTopics.topics) {
      for (const a of t.artifacts) {
        if (a.kind !== "indicator") continue;
        if (a.chart_type == null && a.dimension == null) continue;
        it(`${t.id}::${a.id} matches grapher topic_render`, () => {
          const g = topicIdx.get(`${t.id}::${a.id}`);
          expect(g, `missing grapher row for ${t.id}::${a.id}`).toBeDefined();
          if (a.chart_type != null) {
            expect(g!.chart_type).toBe(a.chart_type);
          }
          if (a.dimension != null) {
            expect(g!.dimension).toBe(a.dimension);
          }
        });
      }
    }
  });

  describe("indicator renderer_rules", () => {
    const rankSuppressedIds = new Set(
      CANONICAL_BACKED_INDICATORS
        .filter((desc) =>
          RANK_SUPPRESSING_COMPARABILITY.has(desc.meta.comparability ?? ""),
        )
        .map(effectiveIndicatorRenderId),
    );

    for (const id of rankSuppressedIds) {
      it(`${id} renderer_rules match grapher indicator_render`, () => {
        const g = indicatorIdx.get(id);
        expect(g, `missing grapher row for ${id}`).toBeDefined();
        expect(g!.renderer_rules ?? []).toContain("no_rank_table");
      });
    }
  });
});
