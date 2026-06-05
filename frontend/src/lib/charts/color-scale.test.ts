// F2b.2 vitest unit for `color-scale.ts`. Node-env (no jsdom) per
// CLAUDE.md section 14 + /memories/lessons.md.
//
// Covers:
//   - binnedSequential partition correctness (bin count, edge spacing)
//   - clamping behaviour (out-of-domain values -> nearest endpoint)
//   - degenerate domain handling (min == max -> one-bin scale)
//   - tick-label formatting via d3-format
//   - shouldRenderValueTick predicate truth table
//   - positionForValue domain math
//   - sqrtAreaScale honest area encoding (4x value -> 2x size, not 4x)

import { describe, expect, test } from "vitest";
import {
  binnedSequential,
  positionForValue,
  shouldRenderValueTick,
  sqrtAreaScale,
} from "./color-scale";

describe("binnedSequential", () => {
  test("5-bin scale over [0, 100] yields 6 edges at 0/20/40/60/80/100", () => {
    const scale = binnedSequential({
      domain: { min: 0, max: 100 },
      bins: 5,
      direction: "higher_is_better",
    });
    expect(scale.bin_edges).toEqual([0, 20, 40, 60, 80, 100]);
    expect(scale.swatches.length).toBe(5);
    expect(scale.tick_labels.length).toBe(6);
  });

  test("colorForValue maps mid-domain values to mid-band swatch", () => {
    const scale = binnedSequential({
      domain: { min: 0, max: 100 },
      bins: 5,
      direction: "higher_is_better",
    });
    // Bin 2 (the middle of 5 bins, range [40, 60])
    expect(scale.colorForValue(50)).toBe(scale.swatches[2]);
  });

  test("colorForValue clamps below-min to first-bin swatch", () => {
    const scale = binnedSequential({
      domain: { min: 0, max: 100 },
      bins: 5,
      direction: "higher_is_better",
    });
    expect(scale.colorForValue(-50)).toBe(scale.swatches[0]);
  });

  test("colorForValue clamps above-max to last-bin swatch", () => {
    const scale = binnedSequential({
      domain: { min: 0, max: 100 },
      bins: 5,
      direction: "higher_is_better",
    });
    expect(scale.colorForValue(200)).toBe(scale.swatches[4]);
  });

  test("colorForValue returns fallback hex for null", () => {
    const scale = binnedSequential({
      domain: { min: 0, max: 100 },
      bins: 5,
      direction: "higher_is_better",
      fallback: "#abcdef",
    });
    expect(scale.colorForValue(null)).toBe("#abcdef");
  });

  test("colorForValue returns fallback for NaN", () => {
    const scale = binnedSequential({
      domain: { min: 0, max: 100 },
      bins: 5,
      direction: "higher_is_better",
    });
    expect(scale.colorForValue(NaN)).toBe("#e2e8f0");
  });

  test("degenerate domain (min == max) returns one-bin dark-end scale", () => {
    const scale = binnedSequential({
      domain: { min: 42, max: 42 },
      bins: 5,
      direction: "neutral",
    });
    expect(scale.swatches.length).toBe(1);
    expect(scale.bin_edges).toEqual([42, 42]);
    // Any value EXCEPT 42 is out-of-domain and renders fallback.
    expect(scale.colorForValue(42)).toBe(scale.swatches[0]);
    expect(scale.colorForValue(41)).toBe("#e2e8f0");
  });

  test("bins < 1 collapses silently to one bin", () => {
    const scale = binnedSequential({
      domain: { min: 0, max: 100 },
      bins: 0,
      direction: "higher_is_better",
    });
    expect(scale.swatches.length).toBe(1);
  });

  test("tick_labels use d3-format SI by default", () => {
    const scale = binnedSequential({
      domain: { min: 0, max: 10_000 },
      bins: 2,
      direction: "neutral",
    });
    // d3-format ".2s" -> SI-suffixed (e.g. "5.0k" for 5000).
    expect(scale.tick_labels).toEqual(["0.0", "5.0k", "10k"]);
  });

  test("tick_labels honour caller's format string", () => {
    const scale = binnedSequential({
      domain: { min: 0, max: 1 },
      bins: 2,
      direction: "higher_is_better",
      format_tick: ".0%",
    });
    expect(scale.tick_labels).toEqual(["0%", "50%", "100%"]);
  });
});

describe("shouldRenderValueTick", () => {
  const domain = { min: 0, max: 100 };

  test("returns true for in-domain value", () => {
    expect(shouldRenderValueTick(domain, 50)).toBe(true);
  });

  test("returns true at domain boundaries", () => {
    expect(shouldRenderValueTick(domain, 0)).toBe(true);
    expect(shouldRenderValueTick(domain, 100)).toBe(true);
  });

  test("returns false for null / undefined", () => {
    expect(shouldRenderValueTick(domain, null)).toBe(false);
    expect(shouldRenderValueTick(domain, undefined)).toBe(false);
  });

  test("returns false for below-min / above-max", () => {
    expect(shouldRenderValueTick(domain, -1)).toBe(false);
    expect(shouldRenderValueTick(domain, 101)).toBe(false);
  });

  test("returns false for NaN", () => {
    expect(shouldRenderValueTick(domain, NaN)).toBe(false);
  });

  test("returns false for degenerate domain", () => {
    expect(shouldRenderValueTick({ min: 42, max: 42 }, 42)).toBe(false);
  });
});

describe("positionForValue", () => {
  const domain = { min: 0, max: 100 };

  test("midpoint is 0.5", () => {
    expect(positionForValue(domain, 50)).toBe(0.5);
  });

  test("min endpoint is 0", () => {
    expect(positionForValue(domain, 0)).toBe(0);
  });

  test("max endpoint is 1", () => {
    expect(positionForValue(domain, 100)).toBe(1);
  });

  test("out-of-domain returns null", () => {
    expect(positionForValue(domain, -1)).toBeNull();
    expect(positionForValue(domain, 101)).toBeNull();
  });

  test("NaN returns null", () => {
    expect(positionForValue(domain, NaN)).toBeNull();
  });

  test("degenerate domain returns null", () => {
    expect(positionForValue({ min: 42, max: 42 }, 42)).toBeNull();
  });
});

describe("sqrtAreaScale (honesty rule)", () => {
  // Sqrt area scale: 4x value -> 2x size, not 4x size.
  // This is the load-bearing honesty contract from parent plan
  // section 15.1 for Treemap + CirclePack + GeoChoropleth{symbol}.

  test("zero value -> range_min_px", () => {
    const scale = sqrtAreaScale({
      max_value: 100,
      range_min_px: 4,
      range_max_px: 40,
    });
    expect(scale(0)).toBe(4);
  });

  test("max value -> range_max_px", () => {
    const scale = sqrtAreaScale({
      max_value: 100,
      range_min_px: 4,
      range_max_px: 40,
    });
    expect(scale(100)).toBe(40);
  });

  test("4x value -> 2x scaled size (HONESTY)", () => {
    const scale = sqrtAreaScale({
      max_value: 100,
      range_min_px: 0,
      range_max_px: 10,
    });
    // sqrt(25) / sqrt(100) = 5/10 = 0.5, so 25 -> 5 px (0.5 of range)
    // sqrt(100) / sqrt(100) = 1.0, so 100 -> 10 px (1.0 of range)
    // Ratio: 4x value (25 -> 100) gives 2x size (5 -> 10). HONEST.
    expect(scale(25)).toBe(5);
    expect(scale(100)).toBe(10);
  });

  test("null / negative values clamp to range_min_px", () => {
    const scale = sqrtAreaScale({
      max_value: 100,
      range_min_px: 4,
      range_max_px: 40,
    });
    expect(scale(null)).toBe(4);
    expect(scale(-5)).toBe(4);
  });

  test("above-max-value clamps to range_max_px", () => {
    const scale = sqrtAreaScale({
      max_value: 100,
      range_min_px: 4,
      range_max_px: 40,
    });
    expect(scale(200)).toBe(40);
  });
});
