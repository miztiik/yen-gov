// Lakshadweep callout helpers (Phase 3 of TODO/TN-GRANULAR-GEO-PLAN, Jony
// edit §c). The Lakshadweep islands are sub-pixel at national zoom on a
// choropleth — visible only as the smallest dot in the Arabian Sea — so
// citizens routinely lose track of them. Standard practice in Indian
// cartography is an inset showing the islands at exaggerated scale, with
// a labelled border (NOT a connecting line — a line would imply
// geographic continuity that isn't there; the labelled border carries
// the meaning).
//
// This module is a pure SVG generator. It does NOT mount a second
// maplibre instance (memory cost) — instead it extracts Lakshadweep's
// geometry once from the india-states FC the parent map already loads,
// projects it equirectangular into a small SVG viewbox, and the
// component renders that <path>.
//
// Why equirectangular and not Web Mercator: the inset is ~80×80 px
// covering 4° of latitude near the equator; the projection difference
// between equirectangular and Mercator over that span is fractions of a
// pixel. Equirectangular avoids pulling in a projection library.
//
// Visibility gating (when the inset shows / hides) is the component's
// responsibility, not this module's. This module just answers two
// questions: "given an FC, what is Lakshadweep's geometry?" and "given a
// geometry and a viewbox, what is the SVG path d= attribute?".

import type { BoundaryFeatureCollection } from "./boundaries";

/** State name as it appears in india-states.geojson's `ST_NM` property. */
const ST_NM = "Lakshadweep";

/**
 * Extract Lakshadweep's geometry from an india-states-shaped
 * FeatureCollection. Returns null when no feature with `ST_NM` ===
 * "Lakshadweep" is present (e.g. a partial test fixture, a future FC
 * that omits union territories).
 *
 * Pure: no I/O.
 */
export function extractLakshadweepGeometry(
  fc: BoundaryFeatureCollection | null | undefined,
): { type: string; coordinates: unknown } | null {
  if (!fc || !Array.isArray(fc.features)) return null;
  for (const f of fc.features) {
    if (f?.properties?.ST_NM === ST_NM && f?.geometry) {
      return f.geometry as { type: string; coordinates: unknown };
    }
  }
  return null;
}

export interface ViewBox {
  width: number;
  height: number;
  /** Padding inside the viewbox (in viewbox units). */
  padding: number;
}

/**
 * Compute the bounding box of a GeoJSON geometry's coordinates by walking
 * every position. Pure: no I/O.
 *
 * Returns null when the geometry has no positions (degenerate input).
 */
export function geometryBbox(
  geometry: { coordinates?: unknown } | null | undefined,
): { minX: number; minY: number; maxX: number; maxY: number } | null {
  if (!geometry || !geometry.coordinates) return null;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  function visit(c: any): void {
    if (typeof c[0] === "number" && typeof c[1] === "number") {
      if (c[0] < minX) minX = c[0];
      if (c[1] < minY) minY = c[1];
      if (c[0] > maxX) maxX = c[0];
      if (c[1] > maxY) maxY = c[1];
      return;
    }
    for (const child of c) visit(child);
  }
  visit(geometry.coordinates);
  if (!Number.isFinite(minX)) return null;
  return { minX, minY, maxX, maxY };
}

/**
 * Render a GeoJSON Polygon / MultiPolygon geometry as an SVG path `d=`
 * string fitted to the given viewbox. Equirectangular projection
 * (lng→x, lat→y); aspect ratio is preserved (the geometry is centred
 * within the viewbox if the bbox aspect differs from the viewbox).
 *
 * Y is flipped because SVG y grows downward while latitude grows
 * upward; without the flip Lakshadweep renders upside-down.
 *
 * Returns "" for null / empty geometry — callers can render the inset
 * conditionally on a non-empty result.
 */
export function geometryToSvgPath(
  geometry: { type?: string; coordinates?: unknown } | null | undefined,
  viewbox: ViewBox,
): string {
  if (!geometry || !geometry.coordinates) return "";
  const bbox = geometryBbox(geometry);
  if (!bbox) return "";

  const inner_w = Math.max(1, viewbox.width - 2 * viewbox.padding);
  const inner_h = Math.max(1, viewbox.height - 2 * viewbox.padding);
  const span_x = Math.max(1e-9, bbox.maxX - bbox.minX);
  const span_y = Math.max(1e-9, bbox.maxY - bbox.minY);
  const scale = Math.min(inner_w / span_x, inner_h / span_y);
  // Centre offset (px) so smaller-axis dimension is centred in viewbox.
  const used_w = span_x * scale;
  const used_h = span_y * scale;
  const off_x = viewbox.padding + (inner_w - used_w) / 2;
  const off_y = viewbox.padding + (inner_h - used_h) / 2;

  function project(lng: number, lat: number): [number, number] {
    const x = off_x + (lng - bbox!.minX) * scale;
    // Flip Y: max-lat maps to off_y, min-lat maps to off_y + used_h.
    const y = off_y + (bbox!.maxY - lat) * scale;
    return [x, y];
  }

  const segments: string[] = [];

  function emitRing(ring: any[]): void {
    if (!ring.length) return;
    const [x0, y0] = project(ring[0][0], ring[0][1]);
    segments.push(`M${x0.toFixed(2)} ${y0.toFixed(2)}`);
    for (let i = 1; i < ring.length; i++) {
      const [x, y] = project(ring[i][0], ring[i][1]);
      segments.push(`L${x.toFixed(2)} ${y.toFixed(2)}`);
    }
    segments.push("Z");
  }

  function emitPolygon(rings: any[]): void {
    for (const ring of rings) emitRing(ring);
  }

  const t = geometry.type;
  const c = geometry.coordinates as any;
  if (t === "Polygon") {
    emitPolygon(c);
  } else if (t === "MultiPolygon") {
    for (const polygon of c) emitPolygon(polygon);
  } else {
    return "";
  }

  return segments.join(" ");
}
