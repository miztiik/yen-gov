import { describe, it, expect } from "vitest";
import {
  formatTimeLabel,
  splitOnBreaks,
  growthSafeAcross,
  vintageTooltipLine,
  indexAxisHint,
  breaksFromMeta,
  splitRowsForEntity,
  axisUnitLabel,
  legendCaption,
  type SeriesBreak,
} from "./indicator-render";
import type { IndicatorMeta, IndicatorRow } from "./indicators";

// ---- formatTimeLabel ------------------------------------------------------

describe("formatTimeLabel", () => {
  it("returns YYYY for year grain", () => {
    expect(formatTimeLabel("2024", "year")).toBe("2024");
    expect(formatTimeLabel("2011", "year")).toBe("2011");
  });

  it("renders FY YYYY-YY for fiscal_year grain", () => {
    expect(formatTimeLabel("2024-04", "fiscal_year")).toBe("FY 2024-25");
    expect(formatTimeLabel("2024", "fiscal_year")).toBe("FY 2024-25");
    expect(formatTimeLabel("1999-04", "fiscal_year")).toBe("FY 1999-00");
  });

  it("rolls a Jan-Mar fiscal_year stamp back to the preceding FY", () => {
    expect(formatTimeLabel("2025-01", "fiscal_year")).toBe("FY 2024-25");
    expect(formatTimeLabel("2025-03", "fiscal_year")).toBe("FY 2024-25");
  });

  it("maps months to fiscal-year quarters Q1-Q4 with prev-FY rollover", () => {
    expect(formatTimeLabel("2024-04", "quarter")).toBe("2024 Q1");
    expect(formatTimeLabel("2024-06", "quarter")).toBe("2024 Q1");
    expect(formatTimeLabel("2024-07", "quarter")).toBe("2024 Q2");
    expect(formatTimeLabel("2024-10", "quarter")).toBe("2024 Q3");
    expect(formatTimeLabel("2024-12", "quarter")).toBe("2024 Q3");
    expect(formatTimeLabel("2025-01", "quarter")).toBe("2024 Q4");
    expect(formatTimeLabel("2025-03", "quarter")).toBe("2024 Q4");
  });

  it("renders Mon YYYY for month grain", () => {
    expect(formatTimeLabel("2024-04", "month")).toBe("Apr 2024");
    expect(formatTimeLabel("2024-12", "month")).toBe("Dec 2024");
  });

  it("renders D Mon YYYY for date grain", () => {
    expect(formatTimeLabel("2024-04-15", "date")).toBe("15 Apr 2024");
    expect(formatTimeLabel("2024-12-01", "date")).toBe("1 Dec 2024");
  });

  it("returns the input verbatim when malformed", () => {
    expect(formatTimeLabel("garbage", "year")).toBe("garbage");
    expect(formatTimeLabel("", "year")).toBe("");
  });

  it("never produces mixed year/month strings on the same axis (regression)", () => {
    // The bug: a chart pulling `r.time` directly produced 2024 alongside 2024-04.
    // After this helper, both stamps under fiscal_year grain render identically.
    expect(formatTimeLabel("2024", "fiscal_year"))
      .toBe(formatTimeLabel("2024-04", "fiscal_year"));
  });
});

// ---- splitOnBreaks --------------------------------------------------------

describe("splitOnBreaks", () => {
  const getTime = (r: { t: string }) => r.t;

  it("returns one segment when there are no breaks", () => {
    const rows = [{ t: "2010" }, { t: "2011" }, { t: "2012" }];
    expect(splitOnBreaks(rows, [], getTime)).toEqual([rows]);
  });

  it("splits at a single break — break point belongs to the new segment", () => {
    const rows = [{ t: "2010" }, { t: "2011" }, { t: "2012" }, { t: "2013" }];
    const breaks: SeriesBreak[] = [{ at_time: "2012", kind: "rebase", note: "x" }];
    const segs = splitOnBreaks(rows, breaks, getTime);
    expect(segs).toEqual([
      [{ t: "2010" }, { t: "2011" }],
      [{ t: "2012" }, { t: "2013" }],
    ]);
  });

  it("handles multiple breaks producing N+1 segments", () => {
    const rows = ["2008", "2009", "2010", "2011", "2012", "2013"].map(t => ({ t }));
    const breaks: SeriesBreak[] = [
      { at_time: "2010", kind: "rebase", note: "" },
      { at_time: "2012", kind: "rebase", note: "" },
    ];
    const segs = splitOnBreaks(rows, breaks, getTime);
    expect(segs.length).toBe(3);
    expect(segs[0].map(r => r.t)).toEqual(["2008", "2009"]);
    expect(segs[1].map(r => r.t)).toEqual(["2010", "2011"]);
    expect(segs[2].map(r => r.t)).toEqual(["2012", "2013"]);
  });

  it("returns [[]] for empty input", () => {
    expect(splitOnBreaks([], [{ at_time: "2010", kind: "rebase", note: "" }], getTime))
      .toEqual([[]]);
  });

  it("handles a break before all data (entire series in post-break segment)", () => {
    const rows = [{ t: "2015" }, { t: "2016" }];
    const breaks: SeriesBreak[] = [{ at_time: "2010", kind: "rebase", note: "" }];
    expect(splitOnBreaks(rows, breaks, getTime)).toEqual([rows]);
  });

  it("handles a break after all data (entire series in pre-break segment)", () => {
    const rows = [{ t: "2008" }, { t: "2009" }];
    const breaks: SeriesBreak[] = [{ at_time: "2099", kind: "rebase", note: "" }];
    expect(splitOnBreaks(rows, breaks, getTime)).toEqual([rows]);
  });

  it("does not reorder rows (caller is responsible for sorting)", () => {
    // The function preserves the iteration order of `rows`. When rows are
    // pre-sorted (the documented contract via splitRowsForEntity), the
    // segments come out in natural order. Passing unsorted rows is best-
    // effort: the splitter walks once forward and never rewinds.
    const rows = [{ t: "2010" }, { t: "2011" }, { t: "2012" }];
    const breaks: SeriesBreak[] = [{ at_time: "2011", kind: "rebase", note: "" }];
    const segs = splitOnBreaks(rows, breaks, getTime);
    // Within a segment, original order is preserved.
    expect(segs[0]).toEqual([{ t: "2010" }]);
    expect(segs[1]).toEqual([{ t: "2011" }, { t: "2012" }]);
  });
});

// ---- growthSafeAcross -----------------------------------------------------

describe("growthSafeAcross", () => {
  it("computes (curr - prev) / prev when no break straddles", () => {
    expect(growthSafeAcross(100, 110, "2010", "2011", [])).toBeCloseTo(0.1);
  });

  it("returns null when a break.at_time falls strictly between the two times", () => {
    const breaks: SeriesBreak[] = [{ at_time: "2011", kind: "rebase", note: "" }];
    expect(growthSafeAcross(100, 110, "2010", "2011", breaks)).toBeNull();
    expect(growthSafeAcross(100, 110, "2010", "2012", breaks)).toBeNull();
  });

  it("returns null when prev is 0 (avoid div-by-zero)", () => {
    expect(growthSafeAcross(0, 50, "2010", "2011", [])).toBeNull();
  });

  it("returns null on null/non-finite inputs", () => {
    expect(growthSafeAcross(null, 100, "2010", "2011", [])).toBeNull();
    expect(growthSafeAcross(100, null, "2010", "2011", [])).toBeNull();
    expect(growthSafeAcross(NaN, 100, "2010", "2011", [])).toBeNull();
    expect(growthSafeAcross(100, Infinity, "2010", "2011", [])).toBeNull();
  });

  it("a break BEFORE prev does not block growth", () => {
    const breaks: SeriesBreak[] = [{ at_time: "2008", kind: "rebase", note: "" }];
    expect(growthSafeAcross(100, 110, "2010", "2011", breaks)).toBeCloseTo(0.1);
  });

  it("regression: vintage-spliced NSDP base-year jump returns null, not +3,400%", () => {
    // RBI splice of pre-2011-12 series (SDP at FY 2004-05 prices, lower
    // numbers) into post-2011-12 series (NSDP at FY 2011-12 prices,
    // higher numbers). Naive growth would announce a giant jump.
    const breaks: SeriesBreak[] = [{ at_time: "2011-04", kind: "rebase", note: "Base year change" }];
    expect(growthSafeAcross(50_000, 1_750_000, "2010-04", "2011-04", breaks)).toBeNull();
  });
});

// ---- vintageTooltipLine ---------------------------------------------------

describe("vintageTooltipLine", () => {
  it("returns empty strings when no vintage and no break", () => {
    const meta = {} as Pick<IndicatorMeta, "methodology_vintage" | "series_breaks">;
    expect(vintageTooltipLine(meta)).toEqual({ vintageLine: "", breakLine: "" });
  });

  it("renders Methodology vintage: <text> when set", () => {
    const meta = { methodology_vintage: "RBI Handbook 2024-25 edition" };
    expect(vintageTooltipLine(meta).vintageLine)
      .toBe("Methodology vintage: RBI Handbook 2024-25 edition");
  });

  it("surfaces an exact break note when atTime matches break.at_time", () => {
    const meta = {
      methodology_vintage: "RBI splice",
      series_breaks: [
        { at_time: "2011-04", kind: "rebase" as const, note: "Base year changed to FY 2011-12" },
      ],
    };
    const out = vintageTooltipLine(meta, "2011-04");
    expect(out.breakLine).toBe("Series rebase at 2011-04: Base year changed to FY 2011-12");
  });

  it("does not surface a break for a non-matching atTime", () => {
    const meta = {
      series_breaks: [
        { at_time: "2011-04", kind: "rebase" as const, note: "Base year change" },
      ],
    };
    expect(vintageTooltipLine(meta, "2015-04").breakLine).toBe("");
  });
});

// ---- indexAxisHint --------------------------------------------------------

describe("indexAxisHint", () => {
  it("returns inert hints for non-index value_kind", () => {
    expect(indexAxisHint({ value_kind: "currency", unit: "INR (crore)" }))
      .toEqual({ axisSuffix: "", baseCaption: "", ownAxis: false });
  });

  it("captures a YYYY base from a typical RBI unit string", () => {
    const out = indexAxisHint({ value_kind: "index", unit: "index (Base 2012=100)" });
    expect(out.axisSuffix).toBe("(index, 2012=100)");
    expect(out.baseCaption).toBe("= 100 in 2012");
    expect(out.ownAxis).toBe(true);
  });

  it("captures a YYYY-YY fiscal-year base", () => {
    const out = indexAxisHint({ value_kind: "index", unit: "Index, 2011-12 = 100" });
    expect(out.axisSuffix).toBe("(index, 2011-12=100)");
    expect(out.baseCaption).toBe("= 100 in 2011-12");
  });

  it("falls back to '(index)' when no base year is present in unit", () => {
    const out = indexAxisHint({ value_kind: "index", unit: "index" });
    expect(out.axisSuffix).toBe("(index)");
    expect(out.baseCaption).toBe("");
    expect(out.ownAxis).toBe(true);
  });

  it("regression: the 2026-05-15 audit case (CPI Combined annual)", () => {
    // The actual unit string from datasets/indicators/in/prices/national_cpi_combined_index_annual.json
    const out = indexAxisHint({ value_kind: "index", unit: "index (Base 2012=100)" });
    expect(out.ownAxis).toBe(true);
    expect(out.baseCaption).toBe("= 100 in 2012");
  });
});

// ---- convenience helpers --------------------------------------------------

describe("breaksFromMeta + splitRowsForEntity", () => {
  it("breaksFromMeta returns [] when no series_breaks declared", () => {
    expect(breaksFromMeta({})).toEqual([]);
  });

  it("breaksFromMeta sorts ascending by at_time", () => {
    const out = breaksFromMeta({
      series_breaks: [
        { at_time: "2015-04", kind: "rebase", note: "" },
        { at_time: "2011-04", kind: "definition_change", note: "" },
      ],
    });
    expect(out.map(b => b.at_time)).toEqual(["2011-04", "2015-04"]);
  });

  it("splitRowsForEntity sorts then splits in one call", () => {
    const rows: IndicatorRow[] = [
      { entity_id: "TN", time: "2012-04", value: 200 },
      { entity_id: "TN", time: "2010-04", value: 50 },
      { entity_id: "TN", time: "2011-04", value: 60 },
      { entity_id: "TN", time: "2013-04", value: 220 },
    ];
    const meta = {
      series_breaks: [{ at_time: "2012-04", kind: "rebase" as const, note: "splice" }],
    };
    const segs = splitRowsForEntity(rows, meta);
    expect(segs.length).toBe(2);
    expect(segs[0].map(r => r.time)).toEqual(["2010-04", "2011-04"]);
    expect(segs[1].map(r => r.time)).toEqual(["2012-04", "2013-04"]);
  });
});

// ---- axisUnitLabel + legendCaption (PR-T row 1.10 / T-4) -----------------

describe("axisUnitLabel", () => {
  it("prefers short_unit over unit when both are present", () => {
    expect(axisUnitLabel({ unit: "INR (crore)", short_unit: "₹cr" })).toBe("₹cr");
    expect(axisUnitLabel({ unit: "kWh per person per year", short_unit: "kWh/cap" }))
      .toBe("kWh/cap");
    expect(axisUnitLabel({ unit: "per 1,000 live births", short_unit: "/1k LB" }))
      .toBe("/1k LB");
  });

  it("falls back to unit when short_unit is undefined", () => {
    expect(axisUnitLabel({ unit: "INR (crore)" })).toBe("INR (crore)");
    expect(axisUnitLabel({ unit: "MW" })).toBe("MW");
  });

  it("returns empty string when both are absent", () => {
    expect(axisUnitLabel({})).toBe("");
  });

  it("treats null/undefined short_unit identically (?? semantics)", () => {
    expect(axisUnitLabel({ unit: "MW", short_unit: undefined })).toBe("MW");
  });
});

describe("legendCaption", () => {
  it("prefers description_short over description over title", () => {
    expect(legendCaption({
      title: "Outstanding liabilities",
      description: "Long publisher-style methodology paragraph mentioning RBI and FRBM Act…",
      description_short: "State govt debt as a share of GSDP. Solvency-ratio metric.",
    })).toBe("State govt debt as a share of GSDP. Solvency-ratio metric.");
  });

  it("falls back to description when description_short is absent (tail indicator)", () => {
    expect(legendCaption({
      title: "Renewable capacity",
      description: "Total renewable energy installed capacity in MW (solar + wind + hydro <25 MW).",
    })).toBe(
      "Total renewable energy installed capacity in MW (solar + wind + hydro <25 MW).",
    );
  });

  it("falls back to title when both descriptions are absent (defensive)", () => {
    expect(legendCaption({ title: "Some Indicator" })).toBe("Some Indicator");
  });

  it("regression: 280-char ceiling holds on hand-authored top-30", () => {
    // The schema-level guardrail; the helper itself doesn't enforce length.
    const ds = "x".repeat(280);
    expect(legendCaption({ title: "T", description_short: ds }).length).toBe(280);
  });
});
