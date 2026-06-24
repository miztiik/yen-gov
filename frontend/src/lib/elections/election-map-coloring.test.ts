import { describe, expect, it } from "vitest";
import {
  MARGIN_CAP_PP,
  MARGIN_FILL_OPACITY,
  MARGIN_PENDING_FILL,
  WINNER_FILL_OPACITY,
  MIN_MARGIN_BANDS,
  MAX_MARGIN_BANDS,
  circularHueDistance,
  computeMarginBands,
  deconflictPalette,
  marginBandIndex,
  marginBandLegendStops,
  marginLegendStops,
  marginShade,
  marginShadeBanded,
  resolveWinnerBaseColours,
  type PaletteEntry,
} from "./election-map-coloring";

/** Perceived luminance proxy (sum of channels) - higher = lighter. */
function lum(hex: string): number {
  const h = hex.replace("#", "");
  return (
    parseInt(h.slice(0, 2), 16) +
    parseInt(h.slice(2, 4), 16) +
    parseInt(h.slice(4, 6), 16)
  );
}
function hue(hex: string): number {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b),
    min = Math.min(r, g, b),
    d = max - min;
  if (d < 1e-6) return 0;
  let x: number;
  if (max === r) x = ((g - b) / d) % 6;
  else if (max === g) x = (b - r) / d + 2;
  else x = (r - g) / d + 4;
  x *= 60;
  return x < 0 ? x + 360 : x;
}

const BJP = "#ea580c"; // anchor saffron
const INC = "#1d4ed8"; // anchor blue

describe("marginShade", () => {
  it("returns the FULL party hue at a landslide (margin >= cap)", () => {
    expect(marginShade(BJP, MARGIN_CAP_PP)).toBe(BJP);
    expect(marginShade(BJP, 80)).toBe(BJP); // clamped at the cap
    expect(marginShade(INC, 30)).toBe(INC);
  });

  it("a knife-edge win is a pale tint of the SAME hue (not white, not grey)", () => {
    const pale = marginShade(BJP, 0);
    expect(pale).toMatch(/^#[0-9a-f]{6}$/);
    expect(lum(pale)).toBeGreaterThan(lum(BJP)); // lighter than full hue
    expect(pale).not.toBe("#ffffff");
    // hue preserved within a few degrees (still recognisably saffron)
    expect(circularHueDistance(hue(pale), hue(BJP))).toBeLessThan(12);
  });

  it("ramps monotonically darker toward the party hue as the margin grows", () => {
    const knife = marginShade(INC, 0);
    const mid = marginShade(INC, 15);
    const land = marginShade(INC, 30);
    expect(new Set([knife, mid, land]).size).toBe(3);
    expect(lum(knife)).toBeGreaterThan(lum(mid));
    expect(lum(mid)).toBeGreaterThan(lum(land));
    expect(land).toBe(INC);
  });

  it("keeps the party hue stable across the whole ramp", () => {
    for (let m = 0; m <= 30; m += 5) {
      expect(circularHueDistance(hue(marginShade(INC, m)), hue(INC))).toBeLessThan(12);
    }
  });

  it("treats margin as a magnitude (sign does not matter)", () => {
    expect(marginShade(BJP, -4)).toBe(marginShade(BJP, 4));
    expect(marginShade(BJP, -30)).toBe(marginShade(BJP, 30));
  });

  it("returns the off-ramp pending slate for null / undefined / NaN margin", () => {
    expect(marginShade(BJP, null)).toBe(MARGIN_PENDING_FILL);
    expect(marginShade(BJP, undefined)).toBe(MARGIN_PENDING_FILL);
    expect(marginShade(BJP, Number.NaN)).toBe(MARGIN_PENDING_FILL);
  });

  it("guards a degenerate party hex -> pending, never #NaNNaNNaN / black", () => {
    expect(marginShade("", 10)).toBe(MARGIN_PENDING_FILL);
    expect(marginShade("var(--party-neutral)", 10)).toBe(MARGIN_PENDING_FILL);
    expect(marginShade("oklch(0.6 0.1 240)", 10)).toBe(MARGIN_PENDING_FILL);
    for (let m = 0; m <= 60; m += 3) {
      const f = marginShade(BJP, m);
      expect(f).toMatch(/^#[0-9a-f]{6}$/);
      expect(f).not.toBe("#000000");
    }
  });

  it("normalises a 3-digit shorthand hex at the deep end", () => {
    expect(marginShade("#f00", 30)).toBe("#ff0000");
  });

  it("keeps a sane flat opacity constant", () => {
    expect(MARGIN_FILL_OPACITY).toBeGreaterThan(0.8);
    expect(MARGIN_FILL_OPACITY).toBeLessThanOrEqual(1);
  });
});

describe("deconflictPalette", () => {
  const anchor = (id: string, hex: string): PaletteEntry => ({
    party_id: id,
    hex,
    source: "anchor",
  });
  const fallback = (id: string, hex: string): PaletteEntry => ({
    party_id: id,
    hex,
    source: "fallback",
  });

  it("never mutates identity (anchor / brand) colours", () => {
    const out = deconflictPalette([
      anchor("BJP", BJP),
      anchor("INC", INC),
      { party_id: "X", hex: "#7a3cc4", source: "brand" },
    ]);
    expect(out.get("BJP")).toBe(BJP);
    expect(out.get("INC")).toBe(INC);
    expect(out.get("X")).toBe("#7a3cc4");
  });

  it("does NOT move two identity reds even when they collide (identity wins)", () => {
    const out = deconflictPalette([
      anchor("DMK", "#dc2626"),
      anchor("CPI", "#b91c1c"),
    ]);
    expect(out.get("DMK")).toBe("#dc2626");
    expect(out.get("CPI")).toBe("#b91c1c");
  });

  it("nudges a LOWER-ranked fallback party off a colliding higher-ranked hue", () => {
    // both teal-ish (~175 deg); the second (lower-ranked) is fallback and yields
    const teal = "#15b8a6";
    const out = deconflictPalette([
      anchor("BIG", teal),
      fallback("small", teal),
    ]);
    expect(out.get("BIG")).toBe(teal); // identity, fixed
    const moved = out.get("small")!;
    expect(moved).not.toBe(teal);
    expect(circularHueDistance(hue(moved), hue(teal))).toBeGreaterThanOrEqual(20);
  });

  it("nudges a fallback party OUT of an anchor's reserved hue band", () => {
    // ~33 deg sits in the saffron reserved band [25,45]; a fallback there must move
    const out = deconflictPalette([fallback("minor", "#e2902a")]);
    const moved = out.get("minor")!;
    const h = hue(moved);
    const inSaffron = h >= 25 && h <= 45;
    expect(inSaffron).toBe(false);
  });

  it("leaves a lone non-colliding fallback untouched", () => {
    const out = deconflictPalette([fallback("solo", "#06b6d4")]); // cyan ~191, free band
    expect(out.get("solo")).toBe("#06b6d4");
  });
});

describe("resolveWinnerBaseColours", () => {
  it("resolves anchored winners to their iconic colours", () => {
    const base = resolveWinnerBaseColours([
      { party_id: "parties.IN.BJP" },
      { party_id: "parties.IN.INC" },
    ]);
    expect(base.get("parties.IN.BJP")).toBe(BJP);
    expect(base.get("parties.IN.INC")).toBe(INC);
  });

  it("ranks by seats so the bigger party keeps first pick (deterministic)", () => {
    // one INC seat, three BJP seats -> BJP ranked first; both anchored so both
    // keep their colour regardless, but the call must be stable + complete
    const base = resolveWinnerBaseColours([
      { party_id: "parties.IN.INC" },
      { party_id: "parties.IN.BJP" },
      { party_id: "parties.IN.BJP" },
      { party_id: "parties.IN.BJP" },
    ]);
    expect(base.size).toBe(2);
    expect(base.get("parties.IN.BJP")).toBe(BJP);
    expect(base.get("parties.IN.INC")).toBe(INC);
  });

  it("honours a high-confidence brand colour as identity", () => {
    const base = resolveWinnerBaseColours([
      {
        party_id: "parties.IN.SOMEREG",
        brand_colour_hex: "#0ea5e9",
        brand_colour_confidence: "high",
      },
    ]);
    expect(base.get("parties.IN.SOMEREG")).toBe("#0ea5e9");
  });
});

describe("marginLegendStops", () => {
  it("returns four labelled competitiveness bands plus a pending row", () => {
    const stops = marginLegendStops();
    expect(stops).toHaveLength(5);
    for (const s of stops) {
      expect(s.label.length).toBeGreaterThan(0);
      expect(s.hex).toMatch(/^#[0-9a-f]{6}$/);
    }
    expect(stops.filter((s) => s.pending)).toHaveLength(1);
    expect(stops[4].pending).toBe(true);
    expect(stops[4].hex).toBe(MARGIN_PENDING_FILL);
  });

  it("orders the four demonstrative bands light -> dark", () => {
    const ramp = marginLegendStops().filter((s) => !s.pending);
    for (let i = 1; i < ramp.length; i++) {
      expect(lum(ramp[i - 1].hex)).toBeGreaterThan(lum(ramp[i].hex));
    }
  });
});

describe("computeMarginBands", () => {
  it("returns no bands for an all-empty / null margin set", () => {
    expect(computeMarginBands([]).nBands).toBe(0);
    expect(computeMarginBands([null, undefined, Number.NaN]).nBands).toBe(0);
  });

  it("clamps the band count to [MIN, MAX] sized by seat count", () => {
    // 234 seats -> floor(234/8)=29 -> clamped to MAX
    const many = computeMarginBands(
      Array.from({ length: 234 }, (_, i) => i * 0.3 + 1),
    );
    expect(many.nBands).toBe(MAX_MARGIN_BANDS);
    // 40 seats -> floor(40/8)=5 bands
    const mid = computeMarginBands(Array.from({ length: 40 }, (_, i) => i + 1));
    expect(mid.nBands).toBe(5);
    // 12 seats -> floor(12/8)=1 -> raised to MIN
    const few = computeMarginBands(Array.from({ length: 12 }, (_, i) => i + 1));
    expect(few.nBands).toBe(MIN_MARGIN_BANDS);
  });

  it("emits ascending upper edges ending at the max margin", () => {
    const b = computeMarginBands([1, 2, 3, 4, 5, 6, 7, 8, 40]);
    expect(b.upperEdges.length).toBe(b.nBands);
    for (let i = 1; i < b.upperEdges.length; i++) {
      expect(b.upperEdges[i]).toBeGreaterThan(b.upperEdges[i - 1]);
    }
    expect(b.upperEdges[b.upperEdges.length - 1]).toBe(40);
  });

  it("treats margins as magnitudes (sign ignored)", () => {
    expect(computeMarginBands([-1, -2, -3, -40])).toEqual(
      computeMarginBands([1, 2, 3, 40]),
    );
  });

  it("merges tied quantile edges so every band is reachable", () => {
    // all-identical margins collapse to a single reachable band
    const b = computeMarginBands(Array.from({ length: 20 }, () => 5));
    expect(b.nBands).toBe(1);
    expect(b.upperEdges).toEqual([5]);
  });
});

describe("marginShadeBanded", () => {
  // 5 bands over margins 1..40
  const bands = computeMarginBands(Array.from({ length: 40 }, (_, i) => i + 1));

  it("returns the FULL party hue for a top-band (safest) seat", () => {
    expect(marginShadeBanded(BJP, 40, bands)).toBe(BJP);
  });

  it("paled the SAME hue for a closest-band seat (not white / grey)", () => {
    const pale = marginShadeBanded(BJP, 1, bands);
    expect(lum(pale)).toBeGreaterThan(lum(BJP));
    expect(circularHueDistance(hue(pale), hue(BJP))).toBeLessThan(12);
  });

  it("steps monotonically darker from the closest to the safest band", () => {
    const shades = [1, 9, 17, 25, 40].map((m) => marginShadeBanded(INC, m, bands));
    expect(new Set(shades).size).toBe(bands.nBands);
    for (let i = 1; i < shades.length; i++) {
      expect(lum(shades[i])).toBeLessThan(lum(shades[i - 1]));
    }
  });

  it("is RELATIVE to the election (same margin, different distributions)", () => {
    const tight = computeMarginBands(
      Array.from({ length: 40 }, (_, i) => i * 0.2 + 0.1),
    ); // 0.1..7.9
    const wide = computeMarginBands(
      Array.from({ length: 40 }, (_, i) => i + 1),
    ); // 1..40
    // a 7pp seat is "safe" (deep) in the tight election, "close" (pale) in the wide one
    expect(lum(marginShadeBanded(BJP, 7, tight))).toBeLessThan(
      lum(marginShadeBanded(BJP, 7, wide)),
    );
  });

  it("returns the pending slate for null margin, bad hex, or no bands", () => {
    expect(marginShadeBanded(BJP, null, bands)).toBe(MARGIN_PENDING_FILL);
    expect(marginShadeBanded("", 10, bands)).toBe(MARGIN_PENDING_FILL);
    expect(marginShadeBanded(BJP, 10, computeMarginBands([]))).toBe(
      MARGIN_PENDING_FILL,
    );
  });
});

describe("marginBandIndex", () => {
  const bands = computeMarginBands([1, 2, 3, 4, 5, 6, 7, 8]); // 4 bands

  it("maps a margin to 0 (closest) .. nBands-1 (safest)", () => {
    expect(marginBandIndex(0.5, bands)).toBe(0);
    expect(marginBandIndex(100, bands)).toBe(bands.nBands - 1);
  });
});

describe("marginBandLegendStops", () => {
  it("emits one labelled swatch per band (light -> dark) plus a pending row", () => {
    const bands = computeMarginBands(
      Array.from({ length: 40 }, (_, i) => i + 1),
    );
    const stops = marginBandLegendStops(bands);
    expect(stops).toHaveLength(bands.nBands + 1);
    const ramp = stops.filter((s) => !s.pending);
    expect(ramp).toHaveLength(bands.nBands);
    for (let i = 1; i < ramp.length; i++) {
      expect(lum(ramp[i - 1].hex)).toBeGreaterThan(lum(ramp[i].hex));
    }
    expect(stops[stops.length - 1].pending).toBe(true);
    // every band label carries a pp range (house rule: colour never the only signal)
    for (const s of ramp) expect(s.label).toMatch(/pp/);
  });

  it("collapses to just the pending row when there are no bands", () => {
    const stops = marginBandLegendStops(computeMarginBands([]));
    expect(stops).toHaveLength(1);
    expect(stops[0].pending).toBe(true);
  });
});

describe("WINNER_FILL_OPACITY", () => {
  it("is a flat, near-solid constant for Winner mode", () => {
    expect(WINNER_FILL_OPACITY).toBeGreaterThan(0.8);
    expect(WINNER_FILL_OPACITY).toBeLessThanOrEqual(1);
  });
});
