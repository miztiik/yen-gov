import { describe, it, expect } from "vitest";
import { indicatorToStackedTrend, type IndicatorDoc } from "./adapter-indicator";

// Synthetic IndicatorDoc fixture mirroring the legacy energy composer artifact
// (`datasets/indicators/in/energy/installed_capacity_by_source_mw.json`) that
// this test originally read from disk. PR 7b retires that composer + shard
// (per TODO/20260522-phase-2-p1-energy-pivot.md C5/PR-7b); the adapter
// contract still exists and is still exercised by stacked-trend-v2/migrate.ts,
// so the test stays in place with an inline fixture that satisfies the same
// behaviour shape:
//   * 25 entities × 5 power_source facets at "2026-03" → spatial bars > 20.
//   * Entity "S22" (Tamil Nadu) has 3 periods (2024-03, 2025-03, 2026-03)
//     → temporal mode yields >= 1 bar.
//   * Honesty fields carry the CEA + "nameplate" markers the old composer
//     emitted, so honesty-flow assertions stay meaningful.
//   * `sources[0].url` is an https CEA URL, so provenance propagation assertion
//     stays meaningful.
function buildFixture(): IndicatorDoc {
  const entities = Array.from({ length: 25 }, (_, i) => `S${String(i + 1).padStart(2, "0")}`);
  const facets = ["coal", "gas", "hydro", "nuclear", "renewable"];
  const baseValues: Record<string, number> = {
    coal: 12000,
    gas: 3000,
    hydro: 5000,
    nuclear: 1000,
    renewable: 8000,
  };
  const rows: IndicatorDoc["rows"] = [];
  for (const entity_id of entities) {
    for (const facet of facets) {
      rows.push({
        entity_id,
        time: "2026-03",
        value: baseValues[facet] + entity_id.charCodeAt(2),
        facet,
      });
    }
  }
  for (const time of ["2024-03", "2025-03"]) {
    for (const facet of facets) {
      rows.push({
        entity_id: "S22",
        time,
        value: baseValues[facet] + 22,
        facet,
      });
    }
  }
  return {
    $schema_version: "1.4",
    sources: [
      {
        url: "https://cea.nic.in/installed-capacity-report/",
        fetched_at: "2026-03-15T00:00:00Z",
        name: "Installed Capacity Report",
        authority: "Central Electricity Authority (CEA)",
      },
    ],
    indicator: {
      id: "test-energy-installed-capacity-mw",
      title: "Installed capacity by power source (MW)",
      unit: "MW",
      value_kind: "count",
      direction: "neutral",
      time_grain: "monthly",
      entity_kind: "state",
      attribution_geography: "where_produced",
      comparability: "comparable_with_normalisation",
      methodology_vintage: "CEA Installed Capacity 2026-03",
      notes: "Reports nameplate capacity by power source per state-month.",
      chart_type: "stacked-trend",
      default_mode: "percent",
    },
    rows,
  };
}

const realDoc = buildFixture();

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
