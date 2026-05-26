import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  fetchGrapherIndicatorCatalogue,
  fetchGrapherTopicCatalogue,
  lookupIndicatorRender,
  lookupTopicRender,
  _resetGrapherCachesForTests,
} from "./catalogue";

const BASE = "/data";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

let fetchSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
  _resetGrapherCachesForTests();
  fetchSpy = vi.fn();
  globalThis.fetch = fetchSpy as unknown as typeof fetch;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchGrapherIndicatorCatalogue", () => {
  it("requests the indicator render catalogue path", async () => {
    const envelope = {
      $schema: "../schemas/grapher-indicator-render.schema.json",
      $schema_version: "1.0",
      indicators: [
        {
          indicator_id: "environment/state_no2_annual_mean_ug_m3",
          chart_type: "choropleth",
        },
        {
          indicator_id: "district-pashu-aadhaar-count-total",
          renderer_rules: ["no_rank_table"],
        },
      ],
    };
    fetchSpy.mockResolvedValueOnce(jsonResponse(envelope));
    const cat = await fetchGrapherIndicatorCatalogue();
    expect(fetchSpy).toHaveBeenCalledWith(`${BASE}/grapher/indicator_render.json`);
    expect(cat.indicators.length).toBe(2);
  });

  it("throws on fetch failure", async () => {
    fetchSpy.mockResolvedValueOnce(
      new Response("nope", { status: 404, statusText: "Not Found" }),
    );
    await expect(fetchGrapherIndicatorCatalogue()).rejects.toThrow(/indicator_render\.json/);
  });
});

describe("fetchGrapherTopicCatalogue", () => {
  it("requests the topic render catalogue path", async () => {
    const envelope = {
      $schema: "../schemas/grapher-topic-render.schema.json",
      $schema_version: "1.0",
      topics: [
        {
          topic_id: "energy",
          indicator_id: "energy/state_electricity_generation_by_source_gwh",
          chart_type: "ranked",
          dimension: "power_source",
        },
      ],
    };
    fetchSpy.mockResolvedValueOnce(jsonResponse(envelope));
    const cat = await fetchGrapherTopicCatalogue();
    expect(fetchSpy).toHaveBeenCalledWith(`${BASE}/grapher/topic_render.json`);
    expect(cat.topics.length).toBe(1);
  });
});

describe("lookupIndicatorRender", () => {
  it("returns the row for a known indicator", () => {
    const cat = {
      $schema: "x",
      $schema_version: "1.0",
      indicators: [
        { indicator_id: "a", chart_type: "ranked" as const },
        { indicator_id: "b", renderer_rules: ["no_rank_table"] },
      ],
    };
    expect(lookupIndicatorRender(cat, "b")?.renderer_rules).toEqual([
      "no_rank_table",
    ]);
  });

  it("returns null for unknown indicator", () => {
    const cat = { $schema: "x", $schema_version: "1.0", indicators: [] };
    expect(lookupIndicatorRender(cat, "missing")).toBeNull();
  });
});

describe("lookupTopicRender", () => {
  it("matches by (topic_id, indicator_id) pair", () => {
    const cat = {
      $schema: "x",
      $schema_version: "1.0",
      topics: [
        {
          topic_id: "energy",
          indicator_id: "x",
          chart_type: "ranked" as const,
          dimension: "power_source",
        },
        {
          topic_id: "economy",
          indicator_id: "x",
          chart_type: "stacked-trend" as const,
        },
      ],
    };
    expect(lookupTopicRender(cat, "energy", "x")?.dimension).toBe("power_source");
    expect(lookupTopicRender(cat, "economy", "x")?.chart_type).toBe("stacked-trend");
    expect(lookupTopicRender(cat, "energy", "missing")).toBeNull();
  });
});
