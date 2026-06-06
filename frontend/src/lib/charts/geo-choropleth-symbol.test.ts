// F2b.7 vitest unit for the symbol-mode helpers consumed by
// GeoChoropleth. Node-env (no jsdom) - we cover the pure math:
//   - sqrtAreaScale (re-exported from color-scale.ts) honesty
//   - geoCentroid call signature smoke (returns [lng, lat])
//
// The DOM rendering of the symbol mode is exercised by section-13
// in-browser smoke per CLAUDE.md sec 13.

import { describe, expect, test } from "vitest";
import { sqrtAreaScale } from "./color-scale";
import { geoCentroid } from "d3-geo";
import type { Feature, Polygon } from "geojson";

describe("sqrtAreaScale (F2b.7 symbol-mode HONESTY)", () => {
  test("4x value gives 2x radius (sqrt honesty)", () => {
    const scale = sqrtAreaScale({
      max_value: 400,
      range_min_px: 0,
      range_max_px: 40,
    });
    const r100 = scale(100);
    const r400 = scale(400);
    // 4x value -> 2x radius. sqrt(100)/sqrt(400) = 10/20 = 0.5.
    expect(r400 / r100).toBeCloseTo(2.0, 3);
  });

  test("null/zero/negative -> min radius", () => {
    const scale = sqrtAreaScale({
      max_value: 100,
      range_min_px: 6,
      range_max_px: 36,
    });
    expect(scale(null)).toBe(6);
    expect(scale(0)).toBe(6);
    expect(scale(-1)).toBe(6);
  });

  test("at-max value -> range_max_px", () => {
    const scale = sqrtAreaScale({
      max_value: 100,
      range_min_px: 6,
      range_max_px: 36,
    });
    expect(scale(100)).toBeCloseTo(36, 1);
  });

  test("custom range maps correctly", () => {
    const scale = sqrtAreaScale({
      max_value: 100,
      range_min_px: 0,
      range_max_px: 100,
    });
    // sqrt(25)/sqrt(100) = 5/10 = 0.5 -> 50px
    expect(scale(25)).toBeCloseTo(50, 1);
  });
});

describe("geoCentroid (F2b.7 symbol-mode positioning)", () => {
  test("returns [lng, lat] pair for a simple polygon", () => {
    // d3-geo expects exterior rings in counter-clockwise order;
    // clockwise rings are interpreted as the antipodal complement,
    // so the centroid lands on the other side of the globe (real
    // gotcha when copy-pasting GeoJSON from different sources).
    const square: Feature<Polygon> = {
      type: "Feature",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [0, 0],
            [0, 10],
            [10, 10],
            [10, 0],
            [0, 0],
          ],
        ],
      },
    };
    const centroid = geoCentroid(square);
    expect(centroid).toHaveLength(2);
    expect(Number.isFinite(centroid[0])).toBe(true);
    expect(Number.isFinite(centroid[1])).toBe(true);
    // For a small near-equatorial CCW square the centroid is roughly
    // in the middle (5, 5) - spherical math drifts slightly but
    // stays close enough for a smoke assertion.
    expect(centroid[0]).toBeGreaterThan(4);
    expect(centroid[0]).toBeLessThan(6);
    expect(centroid[1]).toBeGreaterThan(4);
    expect(centroid[1]).toBeLessThan(6);
  });

  test("handles a degenerate (zero-area) ring without throwing", () => {
    const degen: Feature<Polygon> = {
      type: "Feature",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [5, 5],
            [5, 5],
            [5, 5],
            [5, 5],
          ],
        ],
      },
    };
    // Even when d3-geo can't compute a proper centroid, the call
    // must not throw. NaN is an acceptable return; the renderer
    // skips features with non-finite centroids.
    expect(() => geoCentroid(degen)).not.toThrow();
  });
});
