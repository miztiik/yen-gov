// Unit tests for the Lakshadweep callout helpers. Pure module — no I/O.
import { describe, it, expect } from "vitest";
import {
  extractLakshadweepGeometry,
  geometryBbox,
  geometryToSvgPath,
} from "./lakshadweep";

describe("extractLakshadweepGeometry", () => {
  it("returns the matching feature's geometry", () => {
    const fc = {
      type: "FeatureCollection" as const,
      features: [
        {
          type: "Feature" as const,
          properties: { ST_NM: "Tamil Nadu" },
          geometry: { type: "Polygon", coordinates: [[[80, 13], [80, 14], [81, 14], [80, 13]]] },
        },
        {
          type: "Feature" as const,
          properties: { ST_NM: "Lakshadweep" },
          geometry: { type: "Polygon", coordinates: [[[72, 10], [72, 11], [73, 11], [72, 10]]] },
        },
      ],
    };
    const g = extractLakshadweepGeometry(fc as any);
    expect(g?.type).toBe("Polygon");
  });

  it("returns null when no Lakshadweep feature is present", () => {
    const fc = {
      type: "FeatureCollection" as const,
      features: [
        {
          type: "Feature" as const,
          properties: { ST_NM: "Tamil Nadu" },
          geometry: { type: "Polygon", coordinates: [[[80, 13], [80, 14], [81, 14], [80, 13]]] },
        },
      ],
    };
    expect(extractLakshadweepGeometry(fc as any)).toBeNull();
  });

  it("returns null for null / empty input", () => {
    expect(extractLakshadweepGeometry(null)).toBeNull();
    expect(extractLakshadweepGeometry(undefined)).toBeNull();
    expect(
      extractLakshadweepGeometry({ type: "FeatureCollection", features: [] } as any),
    ).toBeNull();
  });
});

describe("geometryBbox", () => {
  it("computes bbox of a simple polygon", () => {
    const g = { type: "Polygon", coordinates: [[[0, 0], [10, 0], [10, 5], [0, 5], [0, 0]]] };
    expect(geometryBbox(g)).toEqual({ minX: 0, minY: 0, maxX: 10, maxY: 5 });
  });

  it("walks MultiPolygon", () => {
    const g = {
      type: "MultiPolygon",
      coordinates: [
        [[[0, 0], [1, 0], [1, 1], [0, 0]]],
        [[[5, 5], [6, 5], [6, 6], [5, 5]]],
      ],
    };
    expect(geometryBbox(g)).toEqual({ minX: 0, minY: 0, maxX: 6, maxY: 6 });
  });

  it("returns null for empty / null input", () => {
    expect(geometryBbox(null)).toBeNull();
    expect(geometryBbox({})).toBeNull();
    expect(geometryBbox({ coordinates: [] })).toBeNull();
  });
});

describe("geometryToSvgPath", () => {
  const vb = { width: 80, height: 80, padding: 4 };

  it("emits a closed path for a Polygon", () => {
    const g = { type: "Polygon", coordinates: [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]] };
    const d = geometryToSvgPath(g, vb);
    expect(d.startsWith("M")).toBe(true);
    expect(d).toContain("Z");
    // Five vertices → one M + four L + one Z (the last vertex equals the
    // first so we still emit it; consumers don't mind).
    const moves = d.match(/M/g)?.length ?? 0;
    const lines = d.match(/L/g)?.length ?? 0;
    expect(moves).toBe(1);
    expect(lines).toBe(4);
  });

  it("emits multiple sub-paths for a MultiPolygon", () => {
    const g = {
      type: "MultiPolygon",
      coordinates: [
        [[[0, 0], [1, 0], [1, 1], [0, 0]]],
        [[[5, 5], [6, 5], [6, 6], [5, 5]]],
      ],
    };
    const d = geometryToSvgPath(g, vb);
    const moves = d.match(/M/g)?.length ?? 0;
    expect(moves).toBe(2);
  });

  it("flips Y so northern-most lat maps to lowest pixel", () => {
    // A square from lat 0 → 10. Northern-most lat (10) should land near
    // top of viewbox (small y); southern-most (0) near bottom (large y).
    const g = { type: "Polygon", coordinates: [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]] };
    const d = geometryToSvgPath(g, vb);
    // First emitted point is (lng=0, lat=0): south-west corner. Y should
    // be near the bottom of the viewbox (~ height - padding).
    const m = /^M([0-9.]+) ([0-9.]+)/.exec(d)!;
    const y0 = Number(m[2]);
    expect(y0).toBeGreaterThan(vb.height / 2);
  });

  it("returns empty string for unsupported / null geometry", () => {
    expect(geometryToSvgPath(null, vb)).toBe("");
    expect(geometryToSvgPath({ type: "Point", coordinates: [0, 0] }, vb)).toBe("");
  });

  it("centres geometry within the viewbox when bbox aspect differs", () => {
    // A wide-and-short bbox (10×1) inside a square viewbox should be
    // centred vertically — the path should not touch top/bottom edges.
    const g = { type: "Polygon", coordinates: [[[0, 0], [10, 0], [10, 1], [0, 1], [0, 0]]] };
    const d = geometryToSvgPath(g, vb);
    const ys: number[] = [];
    const re = /[ML]([0-9.]+) ([0-9.]+)/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(d)) !== null) ys.push(Number(m[2]));
    const min_y = Math.min(...ys);
    const max_y = Math.max(...ys);
    // Both edges should be well inside the viewbox padding zone.
    expect(min_y).toBeGreaterThan(vb.padding);
    expect(max_y).toBeLessThan(vb.height - vb.padding);
  });
});
