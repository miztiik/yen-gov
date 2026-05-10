// OkLCh perceptual colour palette generation.
//
// Pure module: no DOM, no Svelte, no localStorage. Imported by party-colour.ts
// and exercised directly by vitest.
//
// OkLCh is a perceptually uniform colour space (https://bottosson.github.io/posts/oklab/).
// Picking palette swatches at fixed lightness and chroma with evenly-spaced
// hues gives visually-distinct swatches, unlike picking HSL hex values which
// vary wildly in perceived brightness.

/** A point in OkLCh space. */
export interface OkLCh {
  /** Lightness, 0..1 (0 = black, 1 = white). Typical UI range 0.40 - 0.75. */
  l: number;
  /** Chroma, 0..~0.4. Higher = more saturated. */
  c: number;
  /** Hue, 0..360 degrees. */
  h: number;
}

/** Convert an OkLCh point to a `#rrggbb` hex string. Clamps out-of-gamut. */
export function oklchToHex(p: OkLCh): string {
  // OkLCh -> OkLab
  const hRad = (p.h * Math.PI) / 180;
  const a = p.c * Math.cos(hRad);
  const b = p.c * Math.sin(hRad);
  // OkLab -> linear sRGB (Bottosson coefficients)
  const l_ = p.l + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = p.l - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = p.l - 0.0894841775 * a - 1.291485548 * b;
  const lc = l_ * l_ * l_;
  const mc = m_ * m_ * m_;
  const sc = s_ * s_ * s_;
  const r = +4.0767416621 * lc - 3.3077115913 * mc + 0.2309699292 * sc;
  const g = -1.2684380046 * lc + 2.6097574011 * mc - 0.3413193965 * sc;
  const b2 = -0.0041960863 * lc - 0.7034186147 * mc + 1.707614701 * sc;
  // linear -> sRGB
  const toSrgb = (x: number) => {
    if (x <= 0.0031308) return 12.92 * x;
    return 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
  };
  const clamp = (x: number) => Math.max(0, Math.min(1, x));
  const R = Math.round(clamp(toSrgb(r)) * 255);
  const G = Math.round(clamp(toSrgb(g)) * 255);
  const B = Math.round(clamp(toSrgb(b2)) * 255);
  const hex = (n: number) => n.toString(16).padStart(2, "0");
  return `#${hex(R)}${hex(G)}${hex(B)}`;
}

/** Inputs for `generateOkLChPalette`. */
export interface PaletteSpec {
  /** Number of hue slots evenly spaced over [0, 360). Typical 18-36. */
  hueSlots: number;
  /**
   * Optional hue ranges (in degrees) to skip. Use this to reserve bands for
   * anchor colours (saffron 25-40°, Congress-blue 250-270°, party-red 0-15°)
   * so algorithmic assignments don't clash perceptually with anchors.
   */
  reservedHueRanges?: Array<[number, number]>;
  /**
   * Lightness bands. Each band repeats the full hue circle, giving N×K total
   * swatches. Typical: `[0.55, 0.42]` for one mid and one darker pass.
   */
  lightnessBands: number[];
  /** Chroma; same across the whole palette so swatches feel uniform. */
  chroma: number;
}

/** Whether a hue lies inside any reserved range (inclusive endpoints). */
function isReserved(hue: number, ranges?: Array<[number, number]>): boolean {
  if (!ranges) return false;
  for (const [lo, hi] of ranges) {
    if (lo <= hi) {
      if (hue >= lo && hue <= hi) return true;
    } else {
      // Wraparound range, e.g. [350, 10].
      if (hue >= lo || hue <= hi) return true;
    }
  }
  return false;
}

/**
 * Build a deterministic palette of OkLCh swatches.
 *
 * The order is band-major, hue-minor: all hue slots at band[0] first, then
 * all hue slots at band[1], etc. This keeps the most-saturated tier first so
 * the algorithm gives the brighter swatches before falling back to darker.
 */
export function generateOkLChPalette(spec: PaletteSpec): OkLCh[] {
  const out: OkLCh[] = [];
  for (const l of spec.lightnessBands) {
    for (let i = 0; i < spec.hueSlots; i++) {
      const h = (i * 360) / spec.hueSlots;
      if (isReserved(h, spec.reservedHueRanges)) continue;
      out.push({ l, c: spec.chroma, h });
    }
  }
  return out;
}

/**
 * Cheap, stable string hash (djb2-ish). Returned value is a non-negative int.
 * Same input always produces the same output across JS engines.
 */
export function stringHash(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}
