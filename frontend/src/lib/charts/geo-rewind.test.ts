import { describe, it, expect } from "vitest";
import type { Feature, FeatureCollection, Geometry, Position } from "geojson";
import {
  ringSignedArea,
  rewindFeatureForD3,
  rewindCollectionForD3,
} from "./geo-rewind";

// A unit square. In lon/lat space (y-up) this ordering goes
// (0,0)->(1,0)->(1,1)->(0,1)->close = COUNTER-CLOCKWISE (RFC 7946 exterior).
const CCW_SQUARE: Position[] = [
  [0, 0],
  [1, 0],
  [1, 1],
  [0, 1],
  [0, 0],
];
// The reverse winding = CLOCKWISE (d3-geo exterior convention).
const CW_SQUARE: Position[] = [...CCW_SQUARE].slice().reverse();

function poly(rings: Position[][]): Feature<Geometry> {
  return {
    type: "Feature",
    properties: {},
    geometry: { type: "Polygon", coordinates: rings },
  };
}

describe("ringSignedArea", () => {
  it("is negative for a counter-clockwise (RFC 7946) ring", () => {
    expect(ringSignedArea(CCW_SQUARE)).toBeLessThan(0);
  });
  it("is positive for a clockwise (d3-geo) ring", () => {
    expect(ringSignedArea(CW_SQUARE)).toBeGreaterThan(0);
  });
  it("returns 0 for a degenerate ring", () => {
    expect(ringSignedArea([[0, 0], [1, 1]])).toBe(0);
  });
});

describe("rewindFeatureForD3", () => {
  it("flips a CCW exterior ring to clockwise (d3-geo wants CW exteriors)", () => {
    const out = rewindFeatureForD3(poly([CCW_SQUARE]));
    const ext = (out.geometry as { coordinates: Position[][] }).coordinates[0];
    expect(ringSignedArea(ext)).toBeGreaterThan(0);
  });

  it("leaves an already-clockwise exterior ring untouched (idempotent)", () => {
    const input = poly([CW_SQUARE]);
    const out = rewindFeatureForD3(input);
    const ext = (out.geometry as { coordinates: Position[][] }).coordinates[0];
    // unchanged reference for a ring that needs no rewind
    expect(ext).toBe(CW_SQUARE);
  });

  it("makes holes counter-clockwise while the exterior stays clockwise", () => {
    // exterior CCW (needs flip -> CW); hole CW (needs flip -> CCW)
    const out = rewindFeatureForD3(poly([CCW_SQUARE, CW_SQUARE]));
    const rings = (out.geometry as { coordinates: Position[][] }).coordinates;
    expect(ringSignedArea(rings[0])).toBeGreaterThan(0); // exterior clockwise
    expect(ringSignedArea(rings[1])).toBeLessThan(0); // hole counter-clockwise
  });

  it("rewinds every polygon of a MultiPolygon", () => {
    const f: Feature<Geometry> = {
      type: "Feature",
      properties: {},
      geometry: { type: "MultiPolygon", coordinates: [[CCW_SQUARE], [CCW_SQUARE]] },
    };
    const out = rewindFeatureForD3(f);
    const polys = (out.geometry as { coordinates: Position[][][] }).coordinates;
    for (const p of polys) expect(ringSignedArea(p[0])).toBeGreaterThan(0);
  });

  it("passes non-areal geometries through unchanged", () => {
    const f: Feature<Geometry> = {
      type: "Feature",
      properties: {},
      geometry: { type: "Point", coordinates: [1, 2] },
    };
    expect(rewindFeatureForD3(f)).toBe(f);
  });

  it("is idempotent: a second pass changes nothing", () => {
    const once = rewindFeatureForD3(poly([CCW_SQUARE]));
    const twice = rewindFeatureForD3(once);
    const a = (once.geometry as { coordinates: Position[][] }).coordinates[0];
    const b = (twice.geometry as { coordinates: Position[][] }).coordinates[0];
    expect(b).toEqual(a);
  });
});

describe("rewindCollectionForD3", () => {
  it("rewinds all features and preserves the collection envelope", () => {
    const fc: FeatureCollection<Geometry> = {
      type: "FeatureCollection",
      features: [poly([CCW_SQUARE]), poly([CCW_SQUARE])],
    };
    const out = rewindCollectionForD3(fc);
    expect(out.type).toBe("FeatureCollection");
    expect(out.features).toHaveLength(2);
    for (const f of out.features) {
      const ext = (f.geometry as { coordinates: Position[][] }).coordinates[0];
      expect(ringSignedArea(ext)).toBeGreaterThan(0);
    }
  });
});
