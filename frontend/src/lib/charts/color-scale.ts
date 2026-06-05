// Shared color-scale helpers for the F2b renderer family (parent plan
// section 14.5 doctrine #5: "Shared ColorScale + Legend primitive
// serves both <Choropleth> and <Matrix>"). Pure module: no DOM, no
// Svelte. Exercised by `color-scale.test.ts` (node-env vitest).
//
// Doctrine ties:
//   - Reuses the existing OkLCh sequential ramp at `lib/indicators.ts`
//     (`sequentialSwatch` + `hueForDirection` + `SEQUENTIAL_RAMP_*`
//     constants) so the new d3-geo-based GeoChoropleth + Matrix render
//     with the SAME palette the existing maplibre-based
//     IndicatorChoropleth uses. One palette, two engines.
//   - Adds `d3-scale` for tick math (`scaleLinear`, `scaleQuantize`,
//     `scaleSqrt`) and `d3-format` for tick-label formatting. Both
//     are first-class runtime deps in `frontend/package.json` (added
//     by F2b.2; F4 set the precedent for promoting d3 sub-packages
//     from transitive `d3` devDep to first-class runtime dep so vite
//     tree-shakes them cleanly).
//   - Per parent plan section 14.3 C2: the binned intensity bar is
//     ALWAYS rectangular, ALWAYS carries numeric labels at the bins,
//     and exposes a value-tick marker for the hovered/selected entity
//     (Jony's bank-branch chart observation). The tick is a derived
//     state (caller-driven `value_tick` prop on `<ChoroplethLegend>`),
//     not a new data layer.

import { scaleLinear, scaleQuantize } from "d3-scale";
import { format } from "d3-format";
import {
  hueForDirection,
  sequentialSwatch,
  type Direction,
} from "../indicators";

/**
 * The binned color scale: maps any `value` in `[domain.min, domain.max]`
 * to one of `bins` discrete OkLCh swatches. Out-of-domain values clamp
 * to the nearest endpoint swatch (per parent plan honesty doctrine: a
 * citizen reads the colour as "more of the thing"; a clamped-to-max
 * outlier reads as "maximum", not as "blank").
 */
export interface BinnedSequentialScale {
  /** Resolve a value to its swatch hex. Out-of-domain clamps to ends. */
  colorForValue(value: number | null): string;
  /** The bin edges, length `bins + 1`. */
  bin_edges: readonly number[];
  /** One swatch hex per bin, length `bins`. */
  swatches: readonly string[];
  /** Pre-formatted tick labels, length `bins + 1`. */
  tick_labels: readonly string[];
  /** Position the legend value-tick at `(value - min) / (max - min)`
   *  in [0, 1]. Returns null when value is out-of-domain or null. */
  positionForValue(value: number | null): number | null;
}

export interface BinnedSequentialArgs {
  domain: { min: number; max: number };
  bins: number;
  direction: Direction;
  /** Citizen-readable tick formatter (e.g. d3-format ".2s" for SI). */
  format_tick?: string;
  /** Fallback hex for null / out-of-bounds. Defaults to slate-200. */
  fallback?: string;
}

const DEFAULT_FALLBACK = "#e2e8f0";

/**
 * Build a typed binned-sequential scale over `domain`. Bin count must
 * be >= 1; the scale silently collapses to one bin if `bins < 1`. A
 * degenerate domain (min == max) returns a one-bin scale whose single
 * swatch is the dark endpoint (so the citizen reads "all maximum"
 * rather than "all blank").
 */
export function binnedSequential(
  args: BinnedSequentialArgs,
): BinnedSequentialScale {
  const bins = Math.max(1, Math.floor(args.bins));
  const { min, max } = args.domain;
  const fallback = args.fallback ?? DEFAULT_FALLBACK;
  const hue = hueForDirection(args.direction);
  const fmt = format(args.format_tick ?? ".2s");

  // Edge case: degenerate domain. Render every cell at the dark end.
  if (!(max > min)) {
    const swatch = sequentialSwatch(1, hue);
    return Object.freeze({
      bin_edges: Object.freeze([min, min]) as readonly number[],
      swatches: Object.freeze([swatch]) as readonly string[],
      tick_labels: Object.freeze([fmt(min), fmt(min)]) as readonly string[],
      colorForValue(value: number | null): string {
        if (value == null || !Number.isFinite(value)) return fallback;
        // In a degenerate domain only `value == min` is in-domain;
        // any other finite value is out-of-vocabulary and reads as
        // fallback (citizen-honest: "this value is not on the legend").
        if (value !== min) return fallback;
        return swatch;
      },
      positionForValue(value: number | null): number | null {
        if (value == null || !Number.isFinite(value)) return null;
        if (value !== min) return null;
        return 0;
      },
    });
  }

  // Standard partition. d3-scale.scaleQuantize maps `domain -> N
  // discrete bins`; we recover the bin index from its output then
  // re-evaluate the OkLCh ramp at the bin's CENTRE so the swatch reads
  // as the middle of the band (parent plan section 14.3 C2: "binned
  // intensity bar"; bin centre is the citizen-honest swatch).
  const quantizer = scaleQuantize<number>().domain([min, max]).range(
    Array.from({ length: bins }, (_, i) => i),
  );
  const swatches = Array.from({ length: bins }, (_, i) => {
    const t = (i + 0.5) / bins; // bin centre in [0, 1]
    return sequentialSwatch(t, hue);
  });
  const bin_edges = Array.from({ length: bins + 1 }, (_, i) => {
    return min + (i / bins) * (max - min);
  });
  const tick_labels = bin_edges.map(fmt);

  return Object.freeze({
    bin_edges: Object.freeze(bin_edges) as readonly number[],
    swatches: Object.freeze(swatches) as readonly string[],
    tick_labels: Object.freeze(tick_labels) as readonly string[],
    colorForValue(value: number | null): string {
      if (value == null || !Number.isFinite(value)) return fallback;
      // Clamp out-of-domain values to the nearest endpoint bin
      // (citizen-honest per parent plan 14.5 doctrine).
      if (value <= min) return swatches[0];
      if (value >= max) return swatches[bins - 1];
      const idx = quantizer(value);
      // quantizer returns undefined only when value is NaN, which we
      // ruled out above. Defensive fallback to the last bin keeps the
      // function total.
      return swatches[idx ?? bins - 1];
    },
    positionForValue(value: number | null): number | null {
      if (value == null || !Number.isFinite(value)) return null;
      if (value < min || value > max) return null;
      return (value - min) / (max - min);
    },
  });
}

/**
 * Predicate used by the legend value-tick: render the tick only when
 * the supplied value is non-null AND falls within the scale's domain.
 * Pure boolean function so the test surface is tiny.
 */
export function shouldRenderValueTick(
  domain: { min: number; max: number },
  value_tick: number | null | undefined,
): boolean {
  if (value_tick == null || !Number.isFinite(value_tick)) return false;
  if (!(domain.max > domain.min)) return false;
  return value_tick >= domain.min && value_tick <= domain.max;
}

/**
 * Map a value to its [0, 1] position on the legend bar. Returns null
 * for null / NaN / out-of-domain values (caller hides the tick).
 *
 * This is `scale.positionForValue` lifted to a standalone function so
 * callers that have only a domain (no scale) can position a tick.
 */
export function positionForValue(
  domain: { min: number; max: number },
  value: number,
): number | null {
  if (!Number.isFinite(value)) return null;
  if (!(domain.max > domain.min)) return null;
  if (value < domain.min || value > domain.max) return null;
  return (value - domain.min) / (domain.max - domain.min);
}

/**
 * Build a sqrt-area scale (parent plan section 15.1 honesty rule:
 * Treemap + CirclePack + GeoChoropleth{symbol} all encode magnitude
 * by AREA via sqrt). `scaleSqrt().domain([0, max])` returns a SIDE
 * length; the caller squares it to get area if it wants area directly,
 * or applies it to a circle/rect radius for visual sizing.
 *
 * Returns a function `(value: number | null) => number` clamped to
 * [range_min, range_max].
 */
export function sqrtAreaScale(args: {
  max_value: number;
  range_min_px: number;
  range_max_px: number;
}): (value: number | null) => number {
  const scale = scaleLinear()
    .domain([0, Math.sqrt(Math.max(0, args.max_value))])
    .range([args.range_min_px, args.range_max_px])
    .clamp(true);
  return (value: number | null): number => {
    if (value == null || !Number.isFinite(value) || value <= 0) {
      return args.range_min_px;
    }
    return scale(Math.sqrt(value));
  };
}
