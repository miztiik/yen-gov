// Diagonal-hatch fill pattern for "no data" polygons (Phase 4 d1, pulled
// forward from Phase 3 c3 deferral in TODO/TN-GRANULAR-GEO-PLAN.md).
//
// Why a hatch and not a flat colour: the citizen review flagged that a
// flat slate-200 fill on a "no data" polygon reads as "this region has the
// minimum value", indistinguishable from the lowest choropleth bucket.
// A diagonal hatch reads unambiguously as "different kind of empty" — a
// well-known cartographic convention for missing-data overlays.
//
// Generated as raw RGBA pixels so MapChoropleth can `map.addImage(...)`
// without bundling an extra PNG. Pure module → unit-testable without
// mounting maplibre or hitting a canvas.

export interface HatchPattern {
  width: number;
  height: number;
  /** RGBA bytes, length = width * height * 4. */
  data: Uint8ClampedArray;
}

/**
 * Build an N×N RGBA tile of diagonal hatch lines. Background is fully
 * transparent so the underlying base layer (slate-50 background) shows
 * through; the stripe pixels are slate-400 at full opacity.
 *
 * The pattern repeats every `size` pixels both axes; maplibre's
 * fill-pattern repeats it across the polygon. `stripe_width` is the
 * line thickness; `gap` is the transparent space between stripes.
 *
 * Pure: no DOM, no canvas. Vitest covers it directly.
 */
export function diagonalHatch(opts: {
  size?: number;
  stripe_width?: number;
  /** RGBA stripe colour. Default slate-400 (#94a3b8). */
  stripe_rgba?: [number, number, number, number];
} = {}): HatchPattern {
  const size = opts.size ?? 8;
  const sw = opts.stripe_width ?? 2;
  const [r, g, b, a] = opts.stripe_rgba ?? [148, 163, 184, 255];
  const data = new Uint8ClampedArray(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      // A diagonal stripe at 45° hits pixels where (x+y) mod size lies
      // within [0, sw). Wrap-around at the tile edge keeps the pattern
      // seamless when maplibre tiles it.
      const along = (x + y) % size;
      const on = along < sw;
      const i = (y * size + x) * 4;
      if (on) {
        data[i] = r;
        data[i + 1] = g;
        data[i + 2] = b;
        data[i + 3] = a;
      } else {
        data[i] = 0;
        data[i + 1] = 0;
        data[i + 2] = 0;
        data[i + 3] = 0;
      }
    }
  }
  return { width: size, height: size, data };
}
