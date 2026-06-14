// PR-4 vitest for `DualAxisBarLine.svelte`.
//
// Per project doctrine (`@testing-library/svelte` is NOT installed):
// pure helpers are extracted to the `<script module>` block so vitest
// can pin the contract without mounting Svelte. The Svelte template
// is covered by the e2e spec (`frontend/e2e/party-detail.spec.ts`)
// and the CLAUDE.md section 13 in-browser smoke.

import { describe, expect, it } from "vitest";
import {
  buildScales,
  pickLabelStride,
  yearFromPeriodLabel,
} from "./DualAxisBarLine.svelte";

// --- buildScales ----------------------------------------------------------

describe("buildScales", () => {
  it("returns the bar period_labels in input order in the x_domain", () => {
    const bars = [
      { period_label: "AcGenJan1989", value: 24 },
      { period_label: "AcGenFeb1991", value: 2 },
      { period_label: "AcGenFeb1996", value: 173 },
    ];
    const line = [
      { period_label: "AcGenJan1989", value: 14.4 },
      { period_label: "AcGenFeb1991", value: 22.5 },
      { period_label: "AcGenFeb1996", value: 42.1 },
    ];
    const out = buildScales(bars, line);
    expect(out.x_domain).toEqual([
      "AcGenJan1989",
      "AcGenFeb1991",
      "AcGenFeb1996",
    ]);
  });

  it("merges in line-only period_labels at the end of the x_domain", () => {
    const bars = [{ period_label: "AcGenJan1989", value: 24 }];
    const line = [
      { period_label: "AcGenJan1989", value: 14.4 },
      { period_label: "AcGenFeb1991", value: 22.5 },
    ];
    const out = buildScales(bars, line);
    expect(out.x_domain).toEqual(["AcGenJan1989", "AcGenFeb1991"]);
  });

  it("floors left_y_max + right_y_max at 1 so a zero-only series renders a visible axis", () => {
    const out = buildScales(
      [{ period_label: "AcGenFeb1991", value: 0 }],
      [{ period_label: "AcGenFeb1991", value: 0 }],
    );
    expect(out.left_y_max).toBe(1);
    expect(out.right_y_max).toBe(1);
  });

  it("computes the max across all bar values, ignoring non-finite entries", () => {
    const out = buildScales(
      [
        { period_label: "a", value: 12 },
        { period_label: "b", value: NaN },
        { period_label: "c", value: 99 },
      ],
      [],
    );
    expect(out.left_y_max).toBe(99);
  });

  it("returns an empty x_domain for an empty input pair", () => {
    const out = buildScales([], []);
    expect(out.x_domain).toEqual([]);
    expect(out.left_y_max).toBe(1);
    expect(out.right_y_max).toBe(1);
  });
});

// --- pickLabelStride ------------------------------------------------------

describe("pickLabelStride", () => {
  it("returns the mobile stride when the viewport is < 640px", () => {
    expect(pickLabelStride(360, 14, 4)).toBe(4);
    expect(pickLabelStride(639, 6, 3)).toBe(3);
  });

  it("returns stride 1 above 640px when the year count is <= 12", () => {
    expect(pickLabelStride(900, 5, 4)).toBe(1);
    expect(pickLabelStride(900, 12, 4)).toBe(1);
  });

  it("returns stride 2 above 640px when the year count is > 12 (label density rule)", () => {
    expect(pickLabelStride(900, 13, 4)).toBe(2);
    expect(pickLabelStride(1280, 20, 4)).toBe(2);
  });

  it("returns 1 for an empty year list (defensive)", () => {
    expect(pickLabelStride(900, 0, 4)).toBe(1);
  });

  it("clamps a zero / negative mobile_stride up to 1", () => {
    expect(pickLabelStride(360, 14, 0)).toBe(1);
    expect(pickLabelStride(360, 14, -3)).toBe(1);
  });
});

// --- yearFromPeriodLabel --------------------------------------------------

describe("yearFromPeriodLabel", () => {
  it("extracts the 4-digit trailing year from an ECI event id", () => {
    expect(yearFromPeriodLabel("AcGenApr2021")).toBe("2021");
    expect(yearFromPeriodLabel("LsGenMay2024")).toBe("2024");
    expect(yearFromPeriodLabel("AcByeOct1971")).toBe("1971");
  });

  it("falls back to the raw input when no year suffix matches", () => {
    expect(yearFromPeriodLabel("not-an-event-id")).toBe("not-an-event-id");
    expect(yearFromPeriodLabel("")).toBe("");
  });
});
