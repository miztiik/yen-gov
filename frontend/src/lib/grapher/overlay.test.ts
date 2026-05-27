// Unit test for `applyGrapherOverlay` — the seam that sources topic-artifact
// `chart_type` / `dimension` from the grapher catalogue at fetch time, per
// PR-A3b of docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md.

import { describe, it, expect } from "vitest";
import { applyGrapherOverlay } from "./overlay";
import type { TopicCatalogue } from "../catalogue";
import type { GrapherTopicCatalogue } from "./catalogue";

function makeTopicCat(): TopicCatalogue {
  return {
    $schema: "x",
    $schema_version: "1.2",
    sources: [],
    topics: [
      {
        id: "energy",
        title: "Energy",
        list: "concurrent",
        summary: "",
        artifacts: [
          {
            kind: "indicator",
            id: "energy/state_x_gwh",
            chart_type: "ranked",
            dimension: "power_source",
          },
          {
            kind: "indicator",
            id: "energy/state_y_pct",
            // no canonical chart_type — relies on grapher to supply
          },
          {
            kind: "election",
            id: "AcGen2026",
          },
        ],
      },
    ],
  };
}

function makeGrapherTopicCat(
  overrides: Array<{ topic_id: string; indicator_id: string; chart_type?: string; dimension?: string }>,
): GrapherTopicCatalogue {
  return {
    $schema: "x",
    $schema_version: "1.0",
    topics: overrides.map((o) => ({
      topic_id: o.topic_id,
      indicator_id: o.indicator_id,
      chart_type: (o.chart_type ?? null) as never,
      dimension: o.dimension ?? null,
    })),
  };
}

describe("applyGrapherOverlay (PR-A3b)", () => {
  it("sources chart_type + dimension from grapher when present", () => {
    const out = applyGrapherOverlay(
      makeTopicCat(),
      makeGrapherTopicCat([
        { topic_id: "energy", indicator_id: "energy/state_x_gwh", chart_type: "ranked", dimension: "power_source" },
        { topic_id: "energy", indicator_id: "energy/state_y_pct", chart_type: "stacked-trend", dimension: "billing_basis" },
      ]),
    );
    const arts = out.topics[0].artifacts;
    expect(arts[0].chart_type).toBe("ranked");
    expect(arts[0].dimension).toBe("power_source");
    expect(arts[1].chart_type).toBe("stacked-trend");
    expect(arts[1].dimension).toBe("billing_basis");
  });

  it("falls back to canonical value when grapher has no row", () => {
    const out = applyGrapherOverlay(makeTopicCat(), makeGrapherTopicCat([]));
    expect(out.topics[0].artifacts[0].chart_type).toBe("ranked");
    expect(out.topics[0].artifacts[0].dimension).toBe("power_source");
  });

  it("leaves non-indicator artifacts untouched", () => {
    const out = applyGrapherOverlay(
      makeTopicCat(),
      makeGrapherTopicCat([
        { topic_id: "energy", indicator_id: "AcGen2026", chart_type: "ranked" },
      ]),
    );
    expect(out.topics[0].artifacts[2].kind).toBe("election");
    expect((out.topics[0].artifacts[2] as { chart_type?: string }).chart_type).toBeUndefined();
  });

  it("returns a new catalogue (no input mutation)", () => {
    const cat = makeTopicCat();
    const before = JSON.stringify(cat);
    applyGrapherOverlay(
      cat,
      makeGrapherTopicCat([
        { topic_id: "energy", indicator_id: "energy/state_x_gwh", chart_type: "choropleth" },
      ]),
    );
    expect(JSON.stringify(cat)).toBe(before);
  });
});
