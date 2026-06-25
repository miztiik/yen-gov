// Pure hex-cartogram geometry (extracted from TileCartogram.svelte, plan Row 6).
//
// The component is a pure SVG hex grid: one pointy-top hexagon per tile,
// positioned by axial coords (q,r). The coordinate math lives here as plain
// functions so it is node-testable (vitest runs node-env, no jsdom) and so
// the `S` radius knob can be proven to change the emitted viewBox without a
// DOM render. The component imports these and renders the result.
//
// On-screen hex size is governed by the container `height` (the SVG viewBox
// auto-fits via preserveAspectRatio); `S` only sets the intrinsic coordinate
// scale. Both are component props (plan R-I #2).

/** Axial grid coordinate for one tile. */
export interface AxialCoord {
  q: number;
  r: number;
}

/** Inclusive axial extent of a tile set. */
export interface TileBounds {
  minQ: number;
  maxQ: number;
  minR: number;
  maxR: number;
}

/** Hex layout metrics derived from the centre-to-corner radius `S`. */
export interface HexMetrics {
  /** Centre-to-corner hex radius (pointy-top). */
  S: number;
  /** Flat width = sqrt(3) * S. */
  HEX_W: number;
  /** Vertical centre-to-centre row spacing = 1.5 * S. */
  ROW_H: number;
  /** Outer padding = S. */
  PAD: number;
  /** In-hex 2-letter code font size = 0.78 * S. */
  codeFont: number;
}

/** Default centre-to-corner hex radius. Only sets the intrinsic coordinate
 *  scale; raising the container `height` is what visibly enlarges the hexes
 *  (the viewBox auto-fits). */
export const DEFAULT_HEX_RADIUS = 10;

export function hexMetrics(S: number): HexMetrics {
  return {
    S,
    HEX_W: Math.sqrt(3) * S,
    ROW_H: 1.5 * S,
    PAD: S,
    codeFont: S * 0.78,
  };
}

export function tileBounds(tiles: readonly AxialCoord[]): TileBounds {
  if (tiles.length === 0) return { minQ: 0, maxQ: 0, minR: 0, maxR: 0 };
  let minQ = Infinity,
    maxQ = -Infinity,
    minR = Infinity,
    maxR = -Infinity;
  for (const t of tiles) {
    if (t.q < minQ) minQ = t.q;
    if (t.q > maxQ) maxQ = t.q;
    if (t.r < minR) minR = t.r;
    if (t.r > maxR) maxR = t.r;
  }
  return { minQ, maxQ, minR, maxR };
}

/** Cartogram extent in viewBox units for a given bounds + metrics. Linear in
 *  `S`, so doubling the radius doubles the extent. */
export function cartogramSize(
  bounds: TileBounds,
  m: HexMetrics,
): { w: number; h: number } {
  const cols = bounds.maxQ - bounds.minQ + 1;
  const rows = bounds.maxR - bounds.minR + 1;
  const w = m.PAD * 2 + cols * m.HEX_W + m.HEX_W / 2;
  const h = m.PAD * 2 + (rows - 1) * m.ROW_H + 2 * m.S;
  return { w, h };
}

/** SVG `viewBox` string (origin at 0,0) for a given bounds + metrics. */
export function cartogramViewBox(bounds: TileBounds, m: HexMetrics): string {
  const { w, h } = cartogramSize(bounds, m);
  return `0 0 ${w.toFixed(1)} ${h.toFixed(1)}`;
}

/** Pixel centre of the hex at axial (q,r) within the laid-out grid. */
export function hexCenter(
  m: HexMetrics,
  bounds: TileBounds,
  q: number,
  r: number,
): { cx: number; cy: number } {
  const col = q - bounds.minQ;
  const row = r - bounds.minR;
  const offset = (row & 1) === 1 ? m.HEX_W / 2 : 0;
  const cx = m.PAD + col * m.HEX_W + offset + m.HEX_W / 2;
  const cy = m.PAD + row * m.ROW_H + m.S;
  return { cx, cy };
}

/** Pointy-top hexagon vertices (vertex at top) as an SVG `points` string. */
export function hexPoints(m: HexMetrics, cx: number, cy: number): string {
  const pts: string[] = [];
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 180) * (60 * i - 90);
    pts.push(
      `${(cx + m.S * Math.cos(a)).toFixed(2)},${(cy + m.S * Math.sin(a)).toFixed(2)}`,
    );
  }
  return pts.join(" ");
}
