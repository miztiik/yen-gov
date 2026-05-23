import { describe, expect, it } from "vitest";

import {
  buildDumbbellRangeViewModel,
  buildTimeSeriesLineViewModel,
} from "./builders";

// ─── dumbbell_range ────────────────────────────────────────────────

describe("buildDumbbellRangeViewModel — basics", () => {
  interface StateGap {
    readonly code: string;
    readonly name: string;
    readonly y2011: number | null;
    readonly y2021: number | null;
  }
  const ROWS: StateGap[] = [
    { code: "KL", name: "Kerala", y2011: 89, y2021: 94 },
    { code: "BR", name: "Bihar", y2011: 47, y2021: 62 },
    { code: "RJ", name: "Rajasthan", y2011: 55, y2021: 65 },
    { code: "ZZ", name: "All-null", y2011: null, y2021: null },
    { code: "MM", name: "Missing-end", y2011: 50, y2021: null },
  ];

  const toEndpoints = (r: StateGap) => ({
    id: r.code,
    label: r.name,
    earliest: { period_label: "2011", value: r.y2011 },
    latest: { period_label: "2021", value: r.y2021 },
  });

  it("sorts by latest value (value_desc); missing latest sorts last", () => {
    const vm = buildDumbbellRangeViewModel({
      rows: ROWS,
      toEndpoints,
      policy: "value_desc",
    });
    // Latest: KL 94, RJ 65, BR 62, then nulls.
    expect(vm.rows.slice(0, 3).map((r) => r.id)).toEqual(["KL", "RJ", "BR"]);
    expect(vm.rows[0].rank).toBe(1);
    expect(vm.rows[3].rank).toBeNull();
    expect(vm.rows[4].rank).toBeNull();
    expect(vm.max_abs_value).toBe(94);
    expect(vm.max_abs_delta).toBe(15); // BR: 62-47
    expect(vm.present_count).toBe(4);
    expect(vm.missing_count).toBe(1); // ZZ
  });

  it("delta + direction reflect endpoint relationship", () => {
    const vm = buildDumbbellRangeViewModel({
      rows: ROWS,
      toEndpoints,
      policy: "value_desc",
    });
    const kl = vm.rows.find((r) => r.id === "KL")!;
    expect(kl.delta).toBe(5);
    expect(kl.direction).toBe("up");
    const zz = vm.rows.find((r) => r.id === "ZZ")!;
    expect(zz.delta).toBeNull();
    expect(zz.direction).toBe("missing");
    const mm = vm.rows.find((r) => r.id === "MM")!;
    expect(mm.delta).toBeNull();
    expect(mm.direction).toBe("missing");
  });

  it("flat direction when latest == earliest", () => {
    const vm = buildDumbbellRangeViewModel({
      rows: [{ code: "x", name: "x", y2011: 50, y2021: 50 } as StateGap],
      toEndpoints,
      policy: "value_desc",
    });
    expect(vm.rows[0].direction).toBe("flat");
    expect(vm.rows[0].delta).toBe(0);
  });

  it("down direction when latest < earliest", () => {
    const vm = buildDumbbellRangeViewModel({
      rows: [{ code: "x", name: "x", y2011: 100, y2021: 80 } as StateGap],
      toEndpoints,
      policy: "value_desc",
    });
    expect(vm.rows[0].direction).toBe("down");
    expect(vm.rows[0].delta).toBe(-20);
    expect(vm.rows[0].abs_delta).toBe(20);
  });

  it("latest_change policy sorts by |Δ| desc", () => {
    const vm = buildDumbbellRangeViewModel({
      rows: ROWS,
      toEndpoints,
      policy: "latest_change",
    });
    // |Δ|: BR 15, RJ 10, KL 5, others null.
    expect(vm.rows.slice(0, 3).map((r) => r.id)).toEqual(["BR", "RJ", "KL"]);
  });

  it("show_endpoint_label honours threshold", () => {
    const vm = buildDumbbellRangeViewModel({
      rows: [
        { code: "big", name: "big", y2011: 100, y2021: 110 } as StateGap,
        { code: "tiny", name: "tiny", y2011: 2, y2021: 3 } as StateGap,
      ],
      toEndpoints,
      policy: "value_desc",
    });
    const big = vm.rows.find((r) => r.id === "big")!;
    const tiny = vm.rows.find((r) => r.id === "tiny")!;
    expect(big.earliest.show_endpoint_label).toBe(true);
    expect(big.latest.show_endpoint_label).toBe(true);
    // tiny endpoints (2, 3) vs max 110 → 2/110 < 0.05, 3/110 < 0.05.
    expect(tiny.earliest.show_endpoint_label).toBe(false);
    expect(tiny.latest.show_endpoint_label).toBe(false);
  });

  it("show_delta_label suppresses tiny deltas", () => {
    const vm = buildDumbbellRangeViewModel({
      rows: [
        { code: "big", name: "big", y2011: 100, y2021: 200 } as StateGap, // Δ=100
        { code: "tiny", name: "tiny", y2011: 50, y2021: 51 } as StateGap, // Δ=1
      ],
      toEndpoints,
      policy: "value_desc",
    });
    const tiny = vm.rows.find((r) => r.id === "tiny")!;
    expect(tiny.show_delta_label).toBe(false); // 1/100 = 0.01 < 0.05
    expect(vm.rows.find((r) => r.id === "big")!.show_delta_label).toBe(true);
  });

  it("pinned_then_value pins explicitly", () => {
    const vm = buildDumbbellRangeViewModel({
      rows: ROWS,
      toEndpoints: (r) => ({
        ...toEndpoints(r),
        pinned_rank: r.code === "BR" ? 0 : null,
      }),
      policy: "pinned_then_value",
    });
    expect(vm.rows[0].id).toBe("BR");
    expect(vm.rows[0].is_pinned).toBe(true);
  });

  it("preserves original row reference (identity)", () => {
    const vm = buildDumbbellRangeViewModel({
      rows: ROWS,
      toEndpoints,
      policy: "value_desc",
    });
    expect(vm.rows[0].row).toBe(ROWS[0]); // Kerala
  });

  it("empty input → empty view-model", () => {
    const vm = buildDumbbellRangeViewModel<StateGap>({
      rows: [],
      toEndpoints,
      policy: "value_desc",
    });
    expect(vm.rows).toEqual([]);
    expect(vm.max_abs_value).toBe(0);
    expect(vm.max_abs_delta).toBe(0);
  });
});

// ─── time_series_line ──────────────────────────────────────────────

describe("buildTimeSeriesLineViewModel — basics", () => {
  interface RawPoint {
    readonly series: string;
    readonly year: number;
    readonly v: number | null;
  }
  const ROWS: RawPoint[] = [
    { series: "Kerala", year: 2011, v: 89 },
    { series: "Kerala", year: 2016, v: 91 },
    { series: "Kerala", year: 2021, v: 94 },
    { series: "Bihar", year: 2011, v: 47 },
    { series: "Bihar", year: 2016, v: 55 },
    { series: "Bihar", year: 2021, v: 62 },
  ];
  const toPoint = (r: RawPoint) => ({
    series_id: r.series,
    series_label: r.series,
    period_id: String(r.year),
    period_label: String(r.year),
    value: r.v,
  });

  it("buckets points by series; chronological axis", () => {
    const vm = buildTimeSeriesLineViewModel({
      rows: ROWS,
      toPoint,
      policy: "value_desc",
    });
    expect(vm.period_axis.map((p) => p.period_id)).toEqual(["2011", "2016", "2021"]);
    expect(vm.series.map((s) => s.series_id)).toEqual(["Kerala", "Bihar"]);
    expect(vm.series[0].points.map((p) => p.period_id)).toEqual([
      "2011",
      "2016",
      "2021",
    ]);
    expect(vm.max_abs_value).toBe(94);
    expect(vm.suppress_breaks).toBe(true);
  });

  it("computes earliest / latest / abs_delta per series", () => {
    const vm = buildTimeSeriesLineViewModel({
      rows: ROWS,
      toPoint,
      policy: "value_desc",
    });
    const kl = vm.series.find((s) => s.series_id === "Kerala")!;
    expect(kl.earliest_value).toBe(89);
    expect(kl.latest_value).toBe(94);
    expect(kl.abs_delta).toBe(5);
    expect(kl.rank).toBe(1);
  });

  it("visible_period_ids windows the points but keeps series", () => {
    const vm = buildTimeSeriesLineViewModel({
      rows: ROWS,
      toPoint,
      policy: "value_desc",
      visible_period_ids: ["2016", "2021"],
    });
    expect(vm.series[0].points.map((p) => p.period_id)).toEqual(["2016", "2021"]);
    expect(vm.series[0].latest_value).toBe(94);
    expect(vm.series[0].earliest_value).toBe(91);
    expect(vm.series[0].abs_delta).toBe(3);
  });

  it("series with zero windowed points still appears", () => {
    const vm = buildTimeSeriesLineViewModel({
      rows: ROWS,
      toPoint,
      policy: "value_desc",
      visible_period_ids: ["1900"], // matches nothing
    });
    expect(vm.series.length).toBe(2);
    expect(vm.series[0].points).toEqual([]);
    expect(vm.series[0].is_missing).toBe(true);
    expect(vm.series[0].rank).toBeNull();
  });

  it("marks break starts after a null point", () => {
    const rows: RawPoint[] = [
      { series: "Patchy", year: 2011, v: 10 },
      { series: "Patchy", year: 2016, v: null },
      { series: "Patchy", year: 2021, v: 30 },
    ];
    const vm = buildTimeSeriesLineViewModel({
      rows,
      toPoint,
      policy: "value_desc",
    });
    const s = vm.series[0];
    expect(s.points[0].is_break_start).toBe(true); // first present
    expect(s.points[1].is_break_start).toBe(false); // null
    expect(s.points[2].is_break_start).toBe(true); // after null
  });

  it("suppress_breaks=false is echoed on the output", () => {
    const vm = buildTimeSeriesLineViewModel({
      rows: ROWS,
      toPoint,
      policy: "value_desc",
      suppress_breaks: false,
    });
    expect(vm.suppress_breaks).toBe(false);
  });

  it("pinned_then_value pins the series", () => {
    const vm = buildTimeSeriesLineViewModel({
      rows: ROWS,
      toPoint: (r) => ({
        ...toPoint(r),
        series_pinned_rank: r.series === "Bihar" ? 0 : null,
      }),
      policy: "pinned_then_value",
    });
    expect(vm.series[0].series_id).toBe("Bihar");
    expect(vm.series[0].is_pinned).toBe(true);
  });

  it("show_direct_end_label honours threshold + missing", () => {
    const rows: RawPoint[] = [
      { series: "big", year: 2020, v: 100 },
      { series: "tiny", year: 2020, v: 3 },
      { series: "ghost", year: 2020, v: null },
    ];
    const vm = buildTimeSeriesLineViewModel({
      rows,
      toPoint,
      policy: "value_desc",
    });
    const labels = Object.fromEntries(
      vm.series.map((s) => [s.series_id, s.show_direct_end_label]),
    );
    expect(labels.big).toBe(true);
    expect(labels.tiny).toBe(false); // 3/100 < 0.05
    expect(labels.ghost).toBe(false);
  });

  it("rank_best_first with best_is_high=false ranks low first", () => {
    const vm = buildTimeSeriesLineViewModel({
      rows: ROWS,
      toPoint,
      policy: "rank_best_first",
      options: { best_is_high: false },
    });
    // Latest: KL 94, BR 62. best=low → BR rank 1.
    expect(vm.series[0].series_id).toBe("Bihar");
    expect(vm.series[0].rank).toBe(1);
  });

  it("source_rows preserved per series in input order", () => {
    const vm = buildTimeSeriesLineViewModel({
      rows: ROWS,
      toPoint,
      policy: "value_desc",
    });
    const kl = vm.series.find((s) => s.series_id === "Kerala")!;
    expect(kl.source_rows.length).toBe(3);
    expect(kl.source_rows[0]).toBe(ROWS[0]);
    expect(kl.source_rows[2]).toBe(ROWS[2]);
  });

  it("empty input → empty view-model", () => {
    const vm = buildTimeSeriesLineViewModel<RawPoint>({
      rows: [],
      toPoint,
      policy: "value_desc",
    });
    expect(vm.series).toEqual([]);
    expect(vm.period_axis).toEqual([]);
    expect(vm.max_abs_value).toBe(0);
  });
});
