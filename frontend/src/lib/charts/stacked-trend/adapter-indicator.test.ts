import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { indicatorToStackedTrend, type IndicatorDoc } from "./adapter-indicator";

const repoRoot = resolve(__dirname, "../../../../..");
const docPath = resolve(
  repoRoot,
  "datasets/indicators/in/energy/installed_capacity_by_source_mw.json",
);
const realDoc = JSON.parse(readFileSync(docPath, "utf-8")) as IndicatorDoc;

describe("indicatorToStackedTrend — spatial mode (energy fixture)", () => {
  it("produces a valid model from the real composed energy artifact", () => {
    const model = indicatorToStackedTrend(realDoc, {
      mode: { kind: "spatial", time: "2026-03" },
      config: { coverage_ceiling: 0.95, max_named_categories: 8 },
      dimension: "power_source",
      category_labels: {
        coal: "Coal",
        gas: "Gas",
        hydro: "Hydro",
        nuclear: "Nuclear",
        renewable: "Renewable",
        other_thermal: "Other thermal",
      },
    });
    expect(model.bars.length).toBeGreaterThan(20);
    expect(model.categories.length).toBeGreaterThan(0);
    expect(model.dimension).toBe("power_source");
    expect(model.default_mode).toBe("percent");
  });

  it("flows honesty fields through from indicator metadata", () => {
    const model = indicatorToStackedTrend(realDoc, {
      mode: { kind: "spatial", time: "2026-03" },
      config: { coverage_ceiling: 0.95, max_named_categories: 8 },
      dimension: "power_source",
    });
    expect(model.honesty?.attribution_geography).toBe("where_produced");
    expect(model.honesty?.comparability).toBe("comparable_with_normalisation");
    expect(model.honesty?.methodology_vintage).toContain("CEA");
    expect(model.honesty?.notes).toContain("nameplate");
  });

  it("propagates sources from upstream artifact (CLAUDE.md §12)", () => {
    const model = indicatorToStackedTrend(realDoc, {
      mode: { kind: "spatial", time: "2026-03" },
      config: { coverage_ceiling: 0.95, max_named_categories: 8 },
      dimension: "power_source",
    });
    expect(model.sources.length).toBeGreaterThan(0);
    expect(model.sources[0].url).toMatch(/^https:\/\//);
  });

  it("temporal mode bars by time for one entity", () => {
    const model = indicatorToStackedTrend(realDoc, {
      mode: { kind: "temporal", entity_id: "S22", entity_label: "Tamil Nadu" },
      config: { coverage_ceiling: 0.95, max_named_categories: 8 },
      dimension: "power_source",
    });
    expect(model.bars.length).toBeGreaterThanOrEqual(1);
    expect(model.bars.every((b) => b.period_id.startsWith("2"))).toBe(true);
  });
});

describe("indicatorToStackedTrend — designated headline override", () => {
  it("uses headline_text when supplied", () => {
    const model = indicatorToStackedTrend(realDoc, {
      mode: { kind: "spatial", time: "2026-03" },
      config: { coverage_ceiling: 0.95, max_named_categories: 8 },
      dimension: "power_source",
      headline_text: "Test headline",
    });
    expect(model.headline?.rule).toBe("designated");
    expect(model.headline?.text).toBe("Test headline");
  });
});
