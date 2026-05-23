import { describe, expect, it } from "vitest";

import {
  buildTimeSeriesLineViewModel,
  type TimeSeriesLineViewModel,
} from "./time-view-models";

// Renderer contract for TimeSeriesLine.svelte. Component-level DOM
// assertions are deferred to Playwright (vitest = node-env, no jsdom).

interface PointRow {
  series_id: string;
  series_label: string;
  pinned?: boolean;
  colour?: string;
  period_id: string;
  period_label: string;
  value: number | null;
}

const FIXTURE: readonly PointRow[] = [
  // KA
  { series_id: "KA", series_label: "Karnataka", period_id: "2011", period_label: "2011", value: 50 },
  { series_id: "KA", series_label: "Karnataka", period_id: "2016", period_label: "2016", value: 60 },
  { series_id: "KA", series_label: "Karnataka", period_id: "2021", period_label: "2021", value: 75 },
  // TN — pinned
  { series_id: "TN", series_label: "Tamil Nadu", pinned: true, period_id: "2011", period_label: "2011", value: 55 },
  { series_id: "TN", series_label: "Tamil Nadu", pinned: true, period_id: "2016", period_label: "2016", value: null }, // break
  { series_id: "TN", series_label: "Tamil Nadu", pinned: true, period_id: "2021", period_label: "2021", value: 70 },
  // KL — all missing
  { series_id: "KL", series_label: "Kerala", period_id: "2011", period_label: "2011", value: null },
  { series_id: "KL", series_label: "Kerala", period_id: "2016", period_label: "2016", value: null },
  { series_id: "KL", series_label: "Kerala", period_id: "2021", period_label: "2021", value: null },
];

function buildVM(policy: "value_desc" | "pinned_then_value" | "latest_change" = "value_desc", suppress_breaks = true): TimeSeriesLineViewModel<PointRow> {
  return buildTimeSeriesLineViewModel({
    rows: FIXTURE,
    toPoint: r => ({
      series_id: r.series_id,
      series_label: r.series_label,
      series_pinned_rank: r.pinned ? 0 : null,
      series_colour: r.colour,
      period_id: r.period_id,
      period_label: r.period_label,
      value: r.value,
    }),
    policy,
    suppress_breaks,
  });
}

describe("TimeSeriesLine renderer contract", () => {
  const vm = buildVM("value_desc");

  it("dedupes the period axis chronologically", () => {
    expect(vm.period_axis.map(p => p.period_id)).toEqual(["2011", "2016", "2021"]);
  });

  it("emits one series per unique series_id", () => {
    expect(vm.series.length).toBe(3);
    expect(vm.series.map(s => s.series_id).sort()).toEqual(["KA", "KL", "TN"]);
  });

  it("flags a fully missing series", () => {
    const kl = vm.series.find(s => s.series_id === "KL")!;
    expect(kl.is_missing).toBe(true);
    expect(kl.latest_value).toBeNull();
  });

  it("marks a break-start point when a present point follows a missing one", () => {
    const tn = vm.series.find(s => s.series_id === "TN")!;
    const idx = tn.points.findIndex(p => p.period_id === "2021");
    expect(tn.points[idx].is_break_start).toBe(true);
  });

  it("pinned_then_value puts TN first", () => {
    const sorted = buildVM("pinned_then_value");
    expect(sorted.series[0].series_id).toBe("TN");
    expect(sorted.series[0].is_pinned).toBe(true);
  });

  it("max_abs_value tracks the largest visible point", () => {
    expect(vm.max_abs_value).toBe(75); // KA 2021
  });

  it("suppress_breaks echoes through", () => {
    const bridged = buildVM("value_desc", false);
    expect(bridged.suppress_breaks).toBe(false);
    const suppressed = buildVM("value_desc", true);
    expect(suppressed.suppress_breaks).toBe(true);
  });
});
