// Vitest — CompositionBar pure helpers (no Svelte, no DOM).
//
// Covers the percent-share math, the tiny-segment lift, the projection
// geometry, the readout formatter, and the sum-check. Pinning the math
// here means the renderer can trust its `<rect>` coordinates and the
// vitest contract test in `types.test.ts` can lean on `projectSegments`
// for fixture verification.

import { describe, expect, it } from "vitest";

import {
  MIN_VISUAL_WIDTH_PCT,
  formatSegmentReadout,
  projectSegments,
  segmentsSumMatchesTotal,
  shareOfTotalPct,
  totalSegmentValue,
} from "./helpers";
import type {
  CompositionBarModel,
  CompositionBarSegment,
} from "./types";

function seg(
  id: string,
  value: number,
  extras: Partial<CompositionBarSegment> = {},
): CompositionBarSegment {
  return {
    id,
    label: extras.label ?? id,
    value,
    fill: extras.fill ?? "#94a3b8",
    swatch_role: extras.swatch_role ?? "party",
    is_tail: extras.is_tail ?? false,
  };
}

describe("totalSegmentValue", () => {
  it("returns 0 for an empty list", () => {
    expect(totalSegmentValue([])).toBe(0);
  });

  it("sums positive values", () => {
    expect(totalSegmentValue([seg("a", 50), seg("b", 30), seg("c", 20)])).toBe(
      100,
    );
  });

  it("handles a single segment", () => {
    expect(totalSegmentValue([seg("a", 182)])).toBe(182);
  });
});

describe("shareOfTotalPct", () => {
  it("returns zeros for empty input", () => {
    expect(shareOfTotalPct([])).toEqual([]);
  });

  it("returns zeros when total is zero", () => {
    expect(shareOfTotalPct([seg("a", 0), seg("b", 0)])).toEqual([0, 0]);
  });

  it("returns honest percentages summing to 100", () => {
    const shares = shareOfTotalPct([
      seg("a", 50),
      seg("b", 30),
      seg("c", 20),
    ]);
    expect(shares).toEqual([50, 30, 20]);
    expect(shares.reduce((a, b) => a + b, 0)).toBe(100);
  });

  it("handles a single-party-dominant case (Gujarat 2022 BJP)", () => {
    // 156 / 182 = 85.7142857%, 17 / 182 = 9.3406593%, etc.
    const shares = shareOfTotalPct([
      seg("BJP", 156),
      seg("INC", 17),
      seg("AAP", 5),
      seg("IND", 3),
      seg("OTHERS", 1),
    ]);
    expect(shares[0]).toBeCloseTo(85.714, 3);
    expect(shares[1]).toBeCloseTo(9.341, 3);
    expect(shares.reduce((a, b) => a + b, 0)).toBeCloseTo(100, 6);
  });
});

describe("projectSegments — geometry", () => {
  it("returns an empty list when all values are zero", () => {
    expect(projectSegments([seg("a", 0), seg("b", 0)])).toEqual([]);
  });

  it("filters out zero-value segments before projecting", () => {
    const out = projectSegments([seg("a", 0), seg("b", 60), seg("c", 40)]);
    expect(out.map(p => p.id)).toEqual(["b", "c"]);
  });

  it("lays segments left-to-right with cumulative x_pct", () => {
    const out = projectSegments([
      seg("a", 50),
      seg("b", 30),
      seg("c", 20),
    ]);
    expect(out.map(p => p.x_pct)).toEqual([0, 50, 80]);
    expect(out.map(p => p.width_pct)).toEqual([50, 30, 20]);
    expect(out.map(p => p.share_pct)).toEqual([50, 30, 20]);
  });

  it("propagates id / label / fill / swatch_role / is_tail / value through", () => {
    const out = projectSegments([
      seg("BJP", 156, { label: "BJP", fill: "#ffb236", swatch_role: "party" }),
      seg("OTHERS", 1, {
        label: "Others",
        fill: "#94a3b8",
        swatch_role: "others",
        is_tail: true,
      }),
    ]);
    expect(out[0]).toMatchObject({
      id: "BJP",
      label: "BJP",
      fill: "#ffb236",
      swatch_role: "party",
      is_tail: false,
      value: 156,
    });
    expect(out[1]).toMatchObject({
      id: "OTHERS",
      label: "Others",
      fill: "#94a3b8",
      swatch_role: "others",
      is_tail: true,
      value: 1,
    });
  });

  it("lifts a sub-threshold segment to MIN_VISUAL_WIDTH_PCT", () => {
    // 0.4% segment would be invisible at 320 px chart width — lift it.
    // 99.6 / 0.4 ratio approximated with 996 vs 4 values.
    const out = projectSegments([seg("big", 996), seg("tiny", 4)]);
    const tiny = out.find(p => p.id === "tiny")!;
    expect(tiny.width_pct).toBe(MIN_VISUAL_WIDTH_PCT);
    // Honest share remains correct in the readout-facing field.
    expect(tiny.share_pct).toBeCloseTo(0.4, 3);
  });

  it("subtracts the borrowed width from the largest segment", () => {
    // 99.6% big vs 0.4% tiny → after lift, big = 99.6 - 0.2 = 99.4%,
    // tiny lifts from 0.4 → 0.6, borrowed = 0.2.
    const out = projectSegments([seg("big", 996), seg("tiny", 4)]);
    const big = out.find(p => p.id === "big")!;
    expect(big.width_pct).toBeCloseTo(99.4, 6);
  });

  it("keeps total width at 100 after the lift", () => {
    const out = projectSegments([seg("big", 996), seg("tiny", 4)]);
    const sum = out.reduce((a, p) => a + p.width_pct, 0);
    expect(sum).toBeCloseTo(100, 6);
  });

  it("leaves non-tiny segments untouched", () => {
    // None of these is below the threshold; nothing should be lifted.
    const out = projectSegments([
      seg("a", 50),
      seg("b", 30),
      seg("c", 20),
    ]);
    expect(out.map(p => p.width_pct)).toEqual([50, 30, 20]);
  });

  it("handles a single-party-dominant case with a visible-but-small tail", () => {
    // Gujarat 2022 BJP 156 + INC 17 + AAP 5 + IND 3 + Others 1.
    // Honest shares: 85.7, 9.3, 2.7, 1.6, 0.5 — tail 0.5% lifts to 0.6.
    const out = projectSegments([
      seg("BJP", 156),
      seg("INC", 17),
      seg("AAP", 5),
      seg("IND", 3),
      seg("OTHERS", 1, { is_tail: true }),
    ]);
    expect(out).toHaveLength(5);
    const others = out.find(p => p.id === "OTHERS")!;
    expect(others.is_tail).toBe(true);
    expect(others.width_pct).toBeGreaterThanOrEqual(MIN_VISUAL_WIDTH_PCT);
    const sum = out.reduce((a, p) => a + p.width_pct, 0);
    expect(sum).toBeCloseTo(100, 6);
  });
});

describe("formatSegmentReadout", () => {
  it("formats label + value + unit + share", () => {
    expect(
      formatSegmentReadout(seg("BJP", 156, { label: "BJP" }), 85.714, "seats"),
    ).toBe("BJP — 156 seats (85.7%)");
  });

  it("rounds share to 1 decimal place", () => {
    expect(
      formatSegmentReadout(seg("X", 10, { label: "X" }), 33.3333, "MW"),
    ).toBe("X — 10 MW (33.3%)");
  });

  it("handles a zero-share row gracefully", () => {
    expect(formatSegmentReadout(seg("Z", 0, { label: "Z" }), 0, "seats")).toBe(
      "Z — 0 seats (0.0%)",
    );
  });
});

describe("segmentsSumMatchesTotal", () => {
  function model(
    segments: CompositionBarSegment[],
    total_value: number,
  ): CompositionBarModel {
    return {
      schema_version: "1.0",
      label: "Test",
      subtitle: null,
      total_value,
      total_unit: "seats",
      segments,
      honesty_banners: [],
      dimension: "party",
      caption_fptp: null,
    };
  }

  it("returns true when segments sum exactly to total_value", () => {
    expect(
      segmentsSumMatchesTotal(
        model([seg("a", 100), seg("b", 82)], 182),
      ),
    ).toBe(true);
  });

  it("returns false when segments do not sum to total_value", () => {
    expect(
      segmentsSumMatchesTotal(
        model([seg("a", 100), seg("b", 50)], 182),
      ),
    ).toBe(false);
  });

  it("tolerates a small rounding gap within the default tolerance", () => {
    expect(
      segmentsSumMatchesTotal(
        model([seg("a", 100.3), seg("b", 81.5)], 182),
      ),
    ).toBe(true);
  });

  it("respects a caller-supplied tolerance", () => {
    expect(
      segmentsSumMatchesTotal(
        model([seg("a", 100), seg("b", 80)], 182),
        2,
      ),
    ).toBe(true);
    expect(
      segmentsSumMatchesTotal(
        model([seg("a", 100), seg("b", 80)], 182),
        1,
      ),
    ).toBe(false);
  });
});
