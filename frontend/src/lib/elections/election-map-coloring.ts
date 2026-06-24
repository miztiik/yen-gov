// election-map-coloring - the SINGLE source of truth for "Margin" mode colour
// on every election map surface.
//
// Doctrine (user decision 2026-06-22, overriding the earlier party-agnostic
// ramp): Margin mode shades WITHIN the winning party's own colour. A seat keeps
// its party hue; the DEPTH of that hue encodes the winning margin - pale = won
// by a whisker (knife-edge), deep/saturated = safe seat (landslide). So the
// citizen reads who-won AND how-safe from one fill.
//
// Two pieces:
//   1. `marginShade(partyHex, margin_pp)` - ramps a resolved party colour from
//      a pale tint (knife-edge) to its full hue (landslide), in gamma-correct
//      linear-sRGB space so the lightening stays clean. The pale end is BOUNDED
//      (never near-white) so the hue - and thus the party - stays identifiable
//      even on the closest races.
//   2. `resolveWinnerBaseColours(winners)` - resolves the per-party base colour
//      for the set of winners present, ranked by seats won, and de-conflicts
//      COLLISIONS: if a decorative (fallback-tier) minor party's hue clashes
//      with a higher-ranked party already placed (or lands in an anchor's
//      reserved band), the LOWER-ranked party is nudged to a free hue. Iconic
//      anchor colours (BJP saffron, INC blue, ...) and editorial brand colours
//      are IDENTITY and are NEVER mutated (resolver contract); only the
//      decorative fallback tier yields.
//
// ALL FOUR surfaces - national map, national equal-seats, assembly map,
// assembly equal-seats (plus the state-PC map/hex) - shade via `marginShade`
// off the same `resolveWinnerBaseColours` palette, so the colour is identical
// and there is zero drift.
//
// Decision + rationale: docs/architecture/frontend/colours.md.

import {
  getPartyColor,
  ANCHOR_RESERVED_HUE_RANGES,
  type PartyRowForResolver,
} from "../colors/resolver";

// ---------------------------------------------------------------------------
// Tunables
// ---------------------------------------------------------------------------

/** Margin (pp) at/above which a win reads as a "safe seat" - the full-hue deep
 *  end of the ramp. Mirrors the [0, 30]pp window the winner-mode opacity ramp
 *  and `map-highlight-utils.marginOpacity` use, so every surface tells the same
 *  close-vs-walkover story. */
export const MARGIN_CAP_PP = 30;

/** Fill for a unit whose winning margin is unknown / results pending. A calm
 *  slate-200 that is deliberately NOT a party tint, so "no data" can never be
 *  mistaken for a pale knife-edge win. */
export const MARGIN_PENDING_FILL = "#e2e8f0"; // slate-200

/** Constant fill-opacity for Margin mode. The margin magnitude is carried
 *  entirely by the fill's depth, so opacity stays high + FLAT - no second
 *  (opacity) ramp that would double-fade close races into the white page. */
export const MARGIN_FILL_OPACITY = 0.92;

/** Constant fill-opacity for Winner mode. Flat + near-solid so every seat reads
 *  at its winning party's FULL strength ("who won"), with the close-vs-safe
 *  texture reserved for Margin mode. Matches the doctrine in
 *  docs/architecture/frontend/colours.md (Winner = full strength). */
export const WINNER_FILL_OPACITY = 0.95;

/** Margin mode classes seats into competitiveness BANDS sized per election
 *  (quantile classing), not a fixed pp cap: each band holds a roughly equal
 *  share of this event's seats, so every depth always appears and the close-
 *  vs-safe contrast is always legible. Band count is clamped to [MIN, MAX]. */
export const MIN_MARGIN_BANDS = 4;
export const MAX_MARGIN_BANDS = 8;
/** Target seats per band; the band count is sized ~floor(seats / this),
 *  clamped to [MIN_MARGIN_BANDS, MAX_MARGIN_BANDS]. */
export const MARGIN_BAND_TARGET_SEATS = 8;

/** Lightness (HSL, 0..1) at a knife-edge win - a single pale level shared by
 *  every party so "how close" reads consistently across hues. The full-margin
 *  end uses the party colour's own lightness. */
const MARGIN_SHADE_PALE_L = 0.86;

/** Fraction of the party colour's own saturation kept at a knife-edge win.
 *  Below 1 so the pale end is a gentle tint, but high enough that the hue -
 *  and thus the party - stays unmistakable (and two similar hues stay apart). */
const MARGIN_SHADE_PALE_S_FRAC = 0.5;

/** Two hues closer than this (degrees) read as "the same colour" at a glance;
 *  the de-conflictor treats that as a collision. */
const HUE_COLLISION_SEP_DEG = 22;

// ---------------------------------------------------------------------------
// Low-level colour helpers (sRGB <-> linear, hex, HSL, hue)
// ---------------------------------------------------------------------------

/** Parse `#rgb` / `#rrggbb` to `[r,g,b]` 0..255, or null when unparseable
 *  (empty string, CSS var, `oklch(...)`, ...). */
function hexToRgb(hex: string): [number, number, number] | null {
  if (typeof hex !== "string") return null;
  let h = hex.trim().replace(/^#/, "");
  if (/^[0-9a-fA-F]{3}$/.test(h)) {
    h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  }
  if (!/^[0-9a-fA-F]{6}$/.test(h)) return null;
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}

function clamp255(n: number): number {
  return Math.max(0, Math.min(255, Math.round(n)));
}

function rgbToHex(r: number, g: number, b: number): string {
  const c = (n: number) => clamp255(n).toString(16).padStart(2, "0");
  return `#${c(r)}${c(g)}${c(b)}`;
}

/** Hue in [0,360) for an `[r,g,b]`, or null for an achromatic (grey) colour -
 *  greys carry no hue and so can never "collide". */
function rgbToHue([r, g, b]: [number, number, number]): number | null {
  const rn = r / 255,
    gn = g / 255,
    bn = b / 255;
  const max = Math.max(rn, gn, bn),
    min = Math.min(rn, gn, bn);
  const d = max - min;
  if (d < 1e-6) return null;
  let h: number;
  if (max === rn) h = ((gn - bn) / d) % 6;
  else if (max === gn) h = (bn - rn) / d + 2;
  else h = (rn - gn) / d + 4;
  h *= 60;
  return h < 0 ? h + 360 : h;
}

function rgbToHsl([r, g, b]: [number, number, number]): {
  h: number;
  s: number;
  l: number;
} {
  const rn = r / 255,
    gn = g / 255,
    bn = b / 255;
  const max = Math.max(rn, gn, bn),
    min = Math.min(rn, gn, bn);
  const l = (max + min) / 2;
  const d = max - min;
  if (d < 1e-6) return { h: 0, s: 0, l };
  const s = d / (1 - Math.abs(2 * l - 1));
  let h: number;
  if (max === rn) h = ((gn - bn) / d) % 6;
  else if (max === gn) h = (bn - rn) / d + 2;
  else h = (rn - gn) / d + 4;
  h = h * 60;
  if (h < 0) h += 360;
  return { h, s, l };
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const hp = (((h % 360) + 360) % 360) / 60;
  const x = c * (1 - Math.abs((hp % 2) - 1));
  let r = 0,
    g = 0,
    b = 0;
  if (hp < 1) [r, g, b] = [c, x, 0];
  else if (hp < 2) [r, g, b] = [x, c, 0];
  else if (hp < 3) [r, g, b] = [0, c, x];
  else if (hp < 4) [r, g, b] = [0, x, c];
  else if (hp < 5) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  const m = l - c / 2;
  return [(r + m) * 255, (g + m) * 255, (b + m) * 255];
}

/** Circular distance between two hues, 0..180. */
export function circularHueDistance(a: number, b: number): number {
  const d = Math.abs(a - b) % 360;
  return Math.min(d, 360 - d);
}

function hueInReserved(
  h: number,
  ranges: ReadonlyArray<readonly [number, number]>,
): boolean {
  for (const [lo, hi] of ranges) {
    if (lo <= hi ? h >= lo && h <= hi : h >= lo || h <= hi) return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// 1. Party-hue depth ramp
// ---------------------------------------------------------------------------

/**
 * Margin-shaded fill for ONE seat: the winning party's hue, lightened toward a
 * pale tint in inverse proportion to the margin. Knife-edge -> a pale (but
 * still identifiable) tint of the party hue; landslide -> the full party hue.
 * The ramp is computed in HSL with the HUE HELD EXACTLY CONSTANT (only
 * lightness + saturation move), so a pale BJP seat stays unmistakably saffron
 * and a pale INC seat stays unmistakably blue.
 *
 * `margin_pct` is treated as a magnitude (|signed|). Returns
 * `MARGIN_PENDING_FILL` when the margin is null/undefined/NaN or the party hex
 * cannot be parsed - guarding against both `#NaNNaNNaN` and an accidental black.
 */
/**
 * Shade a party RGB toward the pale knife-edge tint at ramp position `t` in
 * [0,1]: 0 = palest (knife-edge), 1 = the full party hue (safe). Hue is held
 * EXACTLY constant; only lightness + saturation move. Shared by the continuous
 * `marginShade`, the banded `marginShadeBanded`, and the legend.
 */
function shadeRgbAtT(rgb: [number, number, number], t: number): string {
  if (t >= 1) return rgbToHex(rgb[0], rgb[1], rgb[2]);
  const tt = Math.max(0, t);
  const { h, s, l } = rgbToHsl(rgb);
  const lt = l * tt + MARGIN_SHADE_PALE_L * (1 - tt);
  const st = s * (MARGIN_SHADE_PALE_S_FRAC + (1 - MARGIN_SHADE_PALE_S_FRAC) * tt);
  const [r, g, b] = hslToRgb(h, st, lt);
  return rgbToHex(r, g, b);
}

/** Ramp position for band `index` of `nBands`: 0 (closest band) -> palest,
 *  nBands-1 (safest band) -> full hue. */
function bandT(index: number, nBands: number): number {
  return nBands > 1 ? index / (nBands - 1) : 1;
}

export function marginShade(
  partyHex: string,
  margin_pct: number | null | undefined,
): string {
  if (margin_pct == null || !Number.isFinite(margin_pct)) {
    return MARGIN_PENDING_FILL;
  }
  const rgb = hexToRgb(partyHex);
  if (!rgb) return MARGIN_PENDING_FILL;
  return shadeRgbAtT(
    rgb,
    Math.min(MARGIN_CAP_PP, Math.abs(margin_pct)) / MARGIN_CAP_PP,
  );
}

// ---------------------------------------------------------------------------
// 1b. Per-election margin BANDS (quantile classing)
// ---------------------------------------------------------------------------

/** A set of competitiveness bands derived from one election's winning margins.
 *  `upperEdges` is ascending; a seat falls in the first band whose upper edge
 *  is >= its |margin|. `nBands === 0` means no seat had a known margin. */
export interface MarginBands {
  nBands: number;
  /** Ascending upper-edge |margin| (pp) per band; length === nBands. */
  upperEdges: number[];
}

/** No-band sentinel (every seat renders the pending fill). */
export const EMPTY_MARGIN_BANDS: MarginBands = { nBands: 0, upperEdges: [] };

/**
 * Classify one election's winning margins into quantile bands (equal share of
 * seats per band) so Margin mode always uses the full pale->deep range and the
 * close-vs-safe contrast stays legible regardless of how the margins cluster.
 *
 * Band count is `clamp(MIN, MAX, floor(validSeats / MARGIN_BAND_TARGET_SEATS))`
 * (and never more than the number of distinct margins). Quantile edges that
 * collapse on ties are merged, so a returned band is always reachable.
 *
 * The shading is therefore RELATIVE to this election (the deepest band = its
 * safest seats, not a fixed pp); that is the correct reading for a single-
 * election map. Pure + deterministic.
 */
export function computeMarginBands(
  margins: readonly (number | null | undefined)[],
): MarginBands {
  const vals = margins
    .filter((m): m is number => m != null && Number.isFinite(m))
    .map((m) => Math.abs(m))
    .sort((a, b) => a - b);
  const n = vals.length;
  if (n === 0) return EMPTY_MARGIN_BANDS;

  let nBands = Math.max(
    MIN_MARGIN_BANDS,
    Math.min(MAX_MARGIN_BANDS, Math.floor(n / MARGIN_BAND_TARGET_SEATS)),
  );
  nBands = Math.min(nBands, n);

  const quantile = (p: number): number => {
    const idx = p * (n - 1);
    const lo = Math.floor(idx);
    const hi = Math.ceil(idx);
    return lo === hi ? vals[lo] : vals[lo] + (vals[hi] - vals[lo]) * (idx - lo);
  };

  const upperEdges: number[] = [];
  for (let i = 1; i <= nBands; i++) {
    const edge = i === nBands ? vals[n - 1] : quantile(i / nBands);
    // Merge ties so each band has a strictly larger upper edge (a collapsed
    // edge would create an unreachable zero-width band).
    if (upperEdges.length === 0 || edge > upperEdges[upperEdges.length - 1]) {
      upperEdges.push(edge);
    }
  }
  return { nBands: upperEdges.length, upperEdges };
}

/** Band index (0 = closest .. nBands-1 = safest) for a seat's margin. */
export function marginBandIndex(
  margin_pct: number,
  bands: MarginBands,
): number {
  const m = Math.abs(margin_pct);
  for (let i = 0; i < bands.nBands; i++) {
    if (m <= bands.upperEdges[i]) return i;
  }
  return bands.nBands - 1;
}

/**
 * Banded margin fill for ONE seat: the winning party's hue at the lightness of
 * its competitiveness BAND (pale = closest band, full hue = safest band). The
 * per-election band edges come from `computeMarginBands`. Returns
 * `MARGIN_PENDING_FILL` for a null/NaN margin, an unparseable hex, or when
 * there are no bands.
 */
export function marginShadeBanded(
  partyHex: string,
  margin_pct: number | null | undefined,
  bands: MarginBands,
): string {
  if (margin_pct == null || !Number.isFinite(margin_pct) || bands.nBands === 0) {
    return MARGIN_PENDING_FILL;
  }
  const rgb = hexToRgb(partyHex);
  if (!rgb) return MARGIN_PENDING_FILL;
  return shadeRgbAtT(
    rgb,
    bandT(marginBandIndex(margin_pct, bands), bands.nBands),
  );
}

// ---------------------------------------------------------------------------
// 2. Seat-ranked palette with fallback-collision de-confliction
// ---------------------------------------------------------------------------

/** A resolved party entry the de-conflictor reasons over. `source` decides
 *  whether the colour is IDENTITY (anchor / brand - never moved) or DECORATION
 *  (fallback - may be nudged when it collides). */
export interface PaletteEntry {
  party_id: string;
  hex: string;
  source: "anchor" | "brand" | "fallback";
}

/**
 * Resolve final base colours for a set of party entries, given in PRIORITY
 * order (highest seats/votes first). Walks the list once:
 *  - anchor / brand entries keep their colour verbatim (identity), and their
 *    hue is recorded as "taken".
 *  - a fallback entry whose hue clashes with an already-taken hue (within
 *    `HUE_COLLISION_SEP_DEG`) OR sits inside an anchor's reserved band is
 *    rotated to the nearest free hue (keeping its own saturation/lightness),
 *    so the LOWER-ranked party is the one that yields. If nothing is free it
 *    keeps its original colour (graceful).
 *
 * Pure + deterministic; unit-tested directly with crafted colliding entries.
 */
export function deconflictPalette(
  rankedEntries: readonly PaletteEntry[],
): Map<string, string> {
  const out = new Map<string, string>();
  const used: number[] = [];

  const clashes = (h: number) =>
    used.some((u) => circularHueDistance(h, u) < HUE_COLLISION_SEP_DEG);

  for (const e of rankedEntries) {
    if (out.has(e.party_id)) continue;
    const rgb = hexToRgb(e.hex);
    let hex = rgb ? rgbToHex(rgb[0], rgb[1], rgb[2]) : e.hex;
    let hue = rgb ? rgbToHue(rgb) : null;

    const needsMove =
      e.source === "fallback" &&
      hue != null &&
      rgb != null &&
      (clashes(hue) || hueInReserved(hue, ANCHOR_RESERVED_HUE_RANGES));

    if (needsMove && rgb != null && hue != null) {
      const { s, l } = rgbToHsl(rgb);
      if (s > 0.05) {
        for (let step = 13; step < 360; step += 13) {
          const cand = (hue + step) % 360;
          if (
            !clashes(cand) &&
            !hueInReserved(cand, ANCHOR_RESERVED_HUE_RANGES)
          ) {
            const [r, g, b] = hslToRgb(cand, s, l);
            hex = rgbToHex(r, g, b);
            hue = cand;
            break;
          }
        }
      }
    }

    if (hue != null) used.push(hue);
    out.set(e.party_id, hex);
  }
  return out;
}

/** Minimal winner shape `resolveWinnerBaseColours` reads - one row per WON
 *  seat (so seats-per-party is just an occurrence count). */
export interface WinnerForPalette {
  party_id: string;
  brand_colour_hex?: string | null;
  brand_colour_confidence?: "high" | "medium" | "low" | null;
}

/**
 * Resolve the de-conflicted base colour for every winning party in `winners`,
 * ranked by seats won (desc; ties broken by party_id for determinism). Returns
 * `party_id -> #rrggbb`. Pair with `marginShade` to paint each seat:
 *
 *   const base = resolveWinnerBaseColours(winners);
 *   const fill = marginShade(base.get(row.party_id) ?? FALLBACK, row.margin_pct);
 */
export function resolveWinnerBaseColours(
  winners: readonly WinnerForPalette[],
): Map<string, string> {
  const seats = new Map<string, number>();
  const rowFor = new Map<string, PartyRowForResolver | null>();
  for (const w of winners) {
    seats.set(w.party_id, (seats.get(w.party_id) ?? 0) + 1);
    if (!rowFor.has(w.party_id)) {
      rowFor.set(
        w.party_id,
        w.brand_colour_hex
          ? {
              party_id: w.party_id,
              brand_colour: {
                hex: w.brand_colour_hex,
                confidence: w.brand_colour_confidence ?? "medium",
              },
            }
          : null,
      );
    }
  }

  const rankedPids = [...seats.keys()].sort((a, b) => {
    const d = (seats.get(b) ?? 0) - (seats.get(a) ?? 0);
    return d !== 0 ? d : a < b ? -1 : a > b ? 1 : 0;
  });

  const entries: PaletteEntry[] = rankedPids.map((pid) => {
    const resolved = getPartyColor(pid, rowFor.get(pid) ?? null);
    return { party_id: pid, hex: resolved.hex, source: resolved.source };
  });

  return deconflictPalette(entries);
}

// ---------------------------------------------------------------------------
// 3. Legend
// ---------------------------------------------------------------------------

/** Demonstrative neutral base for the legend's depth ramp. Slate-600 - clearly
 *  NOT a party colour, so the legend can show the pale->deep axis without
 *  implying any party owns it (the map's real seats use party hues). */
const LEGEND_DEMO_HEX = "#475569"; // slate-600

/** One labelled stop on the Margin-mode legend strip. Colour is ALWAYS paired
 *  with a pp label (house rule: colour is never the only signal). */
export interface MarginLegendStop {
  /** Citizen-readable band, e.g. "Knife-edge <5pp". */
  label: string;
  /** Demonstrative swatch (neutral base shaded at the band midpoint). */
  hex: string;
  /** True for the "results pending / no data" row (off-ramp slate). */
  pending?: boolean;
}

/** Ordered legend stops for the Margin-mode strip: four competitiveness bands
 *  (pale -> deep) demonstrated on a neutral base, plus a distinct "Results
 *  pending" row. The map's real seats carry their winning party's hue at the
 *  same depths. Used as the fallback when no per-election bands are supplied;
 *  the live maps pass `marginBandLegendStops(bands)` instead. */
export function marginLegendStops(): MarginLegendStop[] {
  return [
    { label: "Knife-edge <5pp", hex: marginShade(LEGEND_DEMO_HEX, 2.5) },
    { label: "Close 5-10pp", hex: marginShade(LEGEND_DEMO_HEX, 7.5) },
    { label: "Clear 10-20pp", hex: marginShade(LEGEND_DEMO_HEX, 15) },
    { label: "Safe 20pp+", hex: marginShade(LEGEND_DEMO_HEX, 25) },
    { label: "Results pending", hex: MARGIN_PENDING_FILL, pending: true },
  ];
}

/** Round a pp value for a citizen-readable band label (trims a trailing .0). */
function fmtPp(x: number): string {
  const r = Math.round(x * 10) / 10;
  return Number.isInteger(r) ? String(r) : r.toFixed(1);
}

/**
 * Data-driven legend stops for the per-election quantile bands: one swatch per
 * band (pale -> deep on the neutral demo base) labelled with the band's real pp
 * range, plus the "Results pending" row. Used whenever the map renders banded
 * Margin fills so the legend's depths match the seats exactly (only the HUE is
 * demonstrative). Collapses to just the pending row when there are no bands.
 */
export function marginBandLegendStops(bands: MarginBands): MarginLegendStop[] {
  if (bands.nBands === 0) {
    return [
      { label: "Results pending", hex: MARGIN_PENDING_FILL, pending: true },
    ];
  }
  const rgb = hexToRgb(LEGEND_DEMO_HEX);
  const stops: MarginLegendStop[] = [];
  for (let i = 0; i < bands.nBands; i++) {
    const lo = i === 0 ? 0 : bands.upperEdges[i - 1];
    const hi = bands.upperEdges[i];
    const label =
      i === bands.nBands - 1
        ? `${fmtPp(lo)}pp+`
        : i === 0
          ? `<${fmtPp(hi)}pp`
          : `${fmtPp(lo)}-${fmtPp(hi)}pp`;
    const hex = rgb
      ? shadeRgbAtT(rgb, bandT(i, bands.nBands))
      : MARGIN_PENDING_FILL;
    stops.push({ label, hex });
  }
  stops.push({
    label: "Results pending",
    hex: MARGIN_PENDING_FILL,
    pending: true,
  });
  return stops;
}
