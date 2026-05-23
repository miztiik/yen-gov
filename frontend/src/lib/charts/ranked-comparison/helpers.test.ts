import { describe, expect, it } from "vitest";

import {
  computeGapLine,
  computePeerBand,
  projectPeerBandMarker,
} from "./helpers";

const pct1 = (v: number): string => `${v.toFixed(1)}%`;

describe("computePeerBand", () => {
  it("median-only band collapses lower/upper to median", () => {
    const band = computePeerBand([1, 2, 3, 4, 5], "median");
    expect(band.kind).toBe("median");
    expect(band.median).toBe(3);
    expect(band.lower).toBe(3);
    expect(band.upper).toBe(3);
    expect(band.count).toBe(5);
  });

  it("IQR returns p25 / median / p75 with linear interp", () => {
    const band = computePeerBand([1, 2, 3, 4, 5, 6, 7, 8, 9], "iqr");
    expect(band.median).toBe(5);
    expect(band.lower).toBe(3);
    expect(band.upper).toBe(7);
    expect(band.count).toBe(9);
  });

  it("p10_p90 returns wider envelope than IQR", () => {
    const xs = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
    const iqr = computePeerBand(xs, "iqr");
    const wide = computePeerBand(xs, "p10_p90");
    expect((wide.upper ?? 0) - (wide.lower ?? 0))
      .toBeGreaterThan((iqr.upper ?? 0) - (iqr.lower ?? 0));
  });

  it("ignores nulls / undefined / NaN", () => {
    const band = computePeerBand(
      [null, 1, undefined, 2, NaN, 3, 4, 5],
      "iqr",
    );
    expect(band.count).toBe(5);
    expect(band.median).toBe(3);
  });

  it("empty input → all-null band, count 0", () => {
    const band = computePeerBand([null, undefined, NaN], "iqr");
    expect(band).toEqual({
      kind: "iqr",
      median: null,
      lower: null,
      upper: null,
      count: 0,
    });
  });

  it("single value collapses to itself", () => {
    const band = computePeerBand([42], "p10_p90");
    expect(band.median).toBe(42);
    expect(band.lower).toBe(42);
    expect(band.upper).toBe(42);
    expect(band.count).toBe(1);
  });
});

describe("projectPeerBandMarker", () => {
  it("projects median onto [0,1] relative to bar-area max", () => {
    const band = computePeerBand([10, 20, 30, 40, 50], "iqr");
    // median 30, lower 20, upper 40; bar max 100.
    const marker = projectPeerBandMarker(band, 100);
    expect(marker.median).toBe(30);
    expect(marker.median_pct_of_max).toBeCloseTo(0.3, 5);
    expect(marker.lower_pct_of_max).toBeCloseTo(0.2, 5);
    expect(marker.upper_pct_of_max).toBeCloseTo(0.4, 5);
    expect(marker.count).toBe(5);
  });

  it("clamps overflow to 1.0", () => {
    const band = computePeerBand([10, 200], "iqr");
    const marker = projectPeerBandMarker(band, 100);
    expect(marker.upper_pct_of_max).toBe(1);
  });

  it("treats max <= 0 as no scale → null pcts", () => {
    const band = computePeerBand([10, 20], "iqr");
    const marker = projectPeerBandMarker(band, 0);
    expect(marker.median_pct_of_max).toBeNull();
    expect(marker.lower_pct_of_max).toBeNull();
    expect(marker.upper_pct_of_max).toBeNull();
  });

  it("passes through null band edges", () => {
    const empty = computePeerBand([], "iqr");
    const marker = projectPeerBandMarker(empty, 100);
    expect(marker.median).toBeNull();
    expect(marker.median_pct_of_max).toBeNull();
    expect(marker.lower_pct_of_max).toBeNull();
    expect(marker.upper_pct_of_max).toBeNull();
    expect(marker.count).toBe(0);
  });
});

describe("computeGapLine", () => {
  it("home above compare, higher_is_better → verdict better", () => {
    const line = computeGapLine({
      home_name: "Tamil Nadu",
      home_value: 82.3,
      compare_name: "Karnataka",
      compare_value: 75.6,
      direction: "higher_is_better",
      format_gap: pct1,
    });
    expect(line.direction).toBe("above");
    expect(line.verdict).toBe("better");
    expect(line.abs_gap).toBeCloseTo(6.7, 5);
    expect(line.formatted_gap).toBe("6.7%");
    expect(line.wording).toBe("Tamil Nadu is 6.7% above Karnataka.");
  });

  it("home above compare, lower_is_better → verdict worse", () => {
    const line = computeGapLine({
      home_name: "TN",
      home_value: 30,
      compare_name: "KA",
      compare_value: 20,
      direction: "lower_is_better",
      format_gap: pct1,
    });
    expect(line.direction).toBe("above");
    expect(line.verdict).toBe("worse");
    expect(line.wording).toBe("TN is 10.0% above KA.");
  });

  it("home below compare, higher_is_better → verdict worse", () => {
    const line = computeGapLine({
      home_name: "TN",
      home_value: 60,
      compare_name: "KA",
      compare_value: 75,
      direction: "higher_is_better",
      format_gap: pct1,
    });
    expect(line.direction).toBe("below");
    expect(line.verdict).toBe("worse");
    expect(line.wording).toBe("TN is 15.0% below KA.");
  });

  it("home below compare, lower_is_better → verdict better", () => {
    const line = computeGapLine({
      home_name: "TN",
      home_value: 12,
      compare_name: "KA",
      compare_value: 20,
      direction: "lower_is_better",
      format_gap: pct1,
    });
    expect(line.direction).toBe("below");
    expect(line.verdict).toBe("better");
    expect(line.wording).toBe("TN is 8.0% below KA.");
  });

  it("equal values → verdict equal, matching wording", () => {
    const line = computeGapLine({
      home_name: "TN",
      home_value: 40,
      compare_name: "KA",
      compare_value: 40,
      direction: "higher_is_better",
      format_gap: pct1,
    });
    expect(line.direction).toBe("equal");
    expect(line.verdict).toBe("equal");
    expect(line.abs_gap).toBe(0);
    expect(line.wording).toBe("TN matches KA.");
  });

  it("neutral direction never claims better/worse", () => {
    const line = computeGapLine({
      home_name: "TN",
      home_value: 80,
      compare_name: "KA",
      compare_value: 60,
      direction: "neutral",
      format_gap: pct1,
    });
    expect(line.direction).toBe("above");
    expect(line.verdict).toBe("neutral");
  });

  it("missing home → direction & verdict missing", () => {
    const line = computeGapLine({
      home_name: "TN",
      home_value: null,
      compare_name: "KA",
      compare_value: 50,
      direction: "higher_is_better",
      format_gap: pct1,
    });
    expect(line.direction).toBe("missing");
    expect(line.verdict).toBe("missing");
    expect(line.gap).toBeNull();
    expect(line.abs_gap).toBeNull();
    expect(line.formatted_gap).toBe("");
    expect(line.wording).toBe("No data to compare TN with KA.");
  });

  it("missing compare → direction & verdict missing", () => {
    const line = computeGapLine({
      home_name: "TN",
      home_value: 50,
      compare_name: "KA",
      compare_value: null,
      direction: "lower_is_better",
      format_gap: pct1,
    });
    expect(line.direction).toBe("missing");
    expect(line.verdict).toBe("missing");
  });

  it("NaN values handled as missing", () => {
    const line = computeGapLine({
      home_name: "TN",
      home_value: Number.NaN,
      compare_name: "KA",
      compare_value: 50,
      direction: "higher_is_better",
      format_gap: pct1,
    });
    expect(line.direction).toBe("missing");
  });

  it("wording never asserts better/worse — only above/below/matches", () => {
    const cases = [
      {
        home_name: "A",
        home_value: 10,
        compare_name: "B",
        compare_value: 5,
        direction: "higher_is_better" as const,
        format_gap: pct1,
      },
      {
        home_name: "A",
        home_value: 5,
        compare_name: "B",
        compare_value: 10,
        direction: "lower_is_better" as const,
        format_gap: pct1,
      },
    ];
    for (const c of cases) {
      const line = computeGapLine(c);
      expect(line.wording).not.toMatch(/better|worse/i);
    }
  });
});
