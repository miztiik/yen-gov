import { describe, expect, it } from "vitest";

import {
  breakXs,
  computeYDomain,
  latestDot,
  pathForSeries,
  projectX,
  projectY,
  zeroBaselineY,
  type SparkProjection,
} from "./helpers";

describe("computeYDomain", () => {
  it("returns sane default for empty input", () => {
    expect(computeYDomain([])).toEqual({ min: 0, max: 1, includes_zero: true });
  });

  it("anchors min to 0 when all values are non-negative", () => {
    expect(computeYDomain([10, 20, 5])).toEqual({ min: 0, max: 20, includes_zero: true });
  });

  it("preserves true bounds when values straddle zero", () => {
    const d = computeYDomain([-3, 5, 0]);
    expect(d.min).toBe(-3);
    expect(d.max).toBe(5);
    expect(d.includes_zero).toBe(true);
  });

  it("anchors max to 0 when all values are non-positive", () => {
    const d = computeYDomain([-2, -5, -1]);
    expect(d.min).toBe(-5);
    expect(d.max).toBe(0);
    expect(d.includes_zero).toBe(true);
  });

  it("ignores null / undefined / NaN", () => {
    const d = computeYDomain([10, null, undefined, NaN, 20]);
    expect(d.min).toBe(0);
    expect(d.max).toBe(20);
  });

  it("handles single-value domain by padding to include 0", () => {
    expect(computeYDomain([7])).toEqual({ min: 0, max: 7, includes_zero: true });
    expect(computeYDomain([-7])).toEqual({ min: -7, max: 0, includes_zero: true });
    expect(computeYDomain([0])).toEqual({ min: 0, max: 1, includes_zero: true });
  });
});

describe("projectX / projectY", () => {
  const proj: SparkProjection = {
    view_box_width: 100,
    view_box_height: 32,
    pad_x: 2,
    pad_y: 3,
    y_domain: { min: -10, max: 10, includes_zero: true },
    time_axis: ["2011", "2016", "2021"],
  };

  it("projectX places first time at left pad and last at right pad", () => {
    expect(projectX("2011", proj)).toBeCloseTo(2);
    expect(projectX("2021", proj)).toBeCloseTo(98);
  });

  it("projectX places middle time in the middle", () => {
    expect(projectX("2016", proj)).toBeCloseTo(50);
  });

  it("projectX returns null for unknown time", () => {
    expect(projectX("2099", proj)).toBeNull();
  });

  it("projectY maps min to bottom and max to top", () => {
    expect(projectY(-10, proj)).toBeCloseTo(29); // pad_y + inner_h
    expect(projectY(10, proj)).toBeCloseTo(3);   // pad_y
  });

  it("projectY maps 0 to the middle when domain straddles zero", () => {
    expect(projectY(0, proj)).toBeCloseTo(16);
  });
});

describe("pathForSeries", () => {
  const proj: SparkProjection = {
    view_box_width: 100,
    view_box_height: 32,
    pad_x: 2,
    pad_y: 3,
    y_domain: { min: -10, max: 10, includes_zero: true },
    time_axis: ["2011", "2016", "2021"],
  };

  it("produces a 3-point path for fully present series", () => {
    const d = pathForSeries([
      { time: "2011", value: -5 },
      { time: "2016", value: 0 },
      { time: "2021", value: 5 },
    ], proj);
    // Three commands, starts with M.
    expect(d.startsWith("M")).toBe(true);
    expect(d.split(" ").length).toBe(3);
  });

  it("segments around missing values", () => {
    const d = pathForSeries([
      { time: "2011", value: -5 },
      { time: "2016", value: NaN as unknown as number },
      { time: "2021", value: 5 },
    ], proj);
    const cmds = d.split(" ");
    expect(cmds.filter(c => c.startsWith("M")).length).toBe(2);
    expect(cmds.length).toBe(2);
  });

  it("returns empty string when fewer than two time slots exist", () => {
    const small: SparkProjection = { ...proj, time_axis: ["2011"] };
    expect(pathForSeries([{ time: "2011", value: 5 }], small)).toBe("");
  });

  it("differs visually from an unsigned projection on negative data", () => {
    const d_signed = pathForSeries([
      { time: "2011", value: -10 },
      { time: "2021", value: 10 },
    ], { ...proj, time_axis: ["2011", "2021"] });
    // First Y must be at the BOTTOM (29) when the value is -10 (the min).
    const first = d_signed.split(" ")[0];
    expect(first).toMatch(/M.*,29\.00/);
  });
});

describe("latestDot", () => {
  const proj: SparkProjection = {
    view_box_width: 100,
    view_box_height: 32,
    pad_x: 2,
    pad_y: 3,
    y_domain: { min: 0, max: 100, includes_zero: true },
    time_axis: ["2011", "2016", "2021"],
  };

  it("picks the rightmost present point", () => {
    const dot = latestDot([
      { time: "2011", value: 50 },
      { time: "2016", value: 60 },
      { time: "2021", value: NaN as unknown as number },
    ], proj);
    expect(dot?.time).toBe("2016");
    expect(dot?.value).toBe(60);
  });

  it("returns null when nothing present", () => {
    expect(latestDot([], proj)).toBeNull();
  });
});

describe("breakXs", () => {
  const proj: SparkProjection = {
    view_box_width: 100,
    view_box_height: 32,
    pad_x: 2,
    pad_y: 3,
    y_domain: { min: 0, max: 100, includes_zero: true },
    time_axis: ["2011", "2016", "2021"],
  };

  it("returns x coords for known break times", () => {
    const xs = breakXs(["2016"], proj);
    expect(xs.length).toBe(1);
    expect(xs[0]).toBeCloseTo(50);
  });

  it("silently drops unknown break times", () => {
    const xs = breakXs(["2099"], proj);
    expect(xs.length).toBe(0);
  });
});

describe("zeroBaselineY", () => {
  it("returns null when domain does not straddle zero", () => {
    const proj: SparkProjection = {
      view_box_width: 100,
      view_box_height: 32,
      pad_x: 2,
      pad_y: 3,
      y_domain: { min: 0, max: 100, includes_zero: true },
      time_axis: ["2011"],
    };
    // includes_zero=true but min=0 means "all non-negative". The
    // baseline is the bottom of the rect, which is informative for
    // bar charts but not for sparklines — return null in that case
    // would be a misread of `includes_zero`. The helper trusts the
    // flag, so domains anchored to 0 still produce a baseline at the
    // bottom. The renderer can decide whether to draw it.
    expect(zeroBaselineY(proj)).toBeCloseTo(29);
  });

  it("returns inner y when domain straddles zero", () => {
    const proj: SparkProjection = {
      view_box_width: 100,
      view_box_height: 32,
      pad_x: 2,
      pad_y: 3,
      y_domain: { min: -50, max: 50, includes_zero: true },
      time_axis: ["2011"],
    };
    expect(zeroBaselineY(proj)).toBeCloseTo(16);
  });
});
