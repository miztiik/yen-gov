// Typed view + helpers for indicator artifacts under datasets/indicators/.
// Mirrors datasets/schemas/indicator.schema.json (v1.0).
//
// Pure module: no DOM, no Svelte. Exercised directly by vitest.

import { DATA_BASE } from "./paths";
import { oklchToHex } from "./colors/oklch";

// -- Schema-shaped types ------------------------------------------------------

export interface IndicatorSource {
  url: string;
  fetched_at: string;
  name?: string;
  authority?: string;
}

export interface IndicatorLicense {
  id: string;
  name: string;
  url: string | null;
  redistributable: boolean | null;
}

export interface IndicatorCoverage {
  spatial: string;
  temporal: string;
  admin_level: string | null;
}

export type EntityKind =
  | "country" | "state" | "district" | "subdistrict"
  | "constituency" | "city" | "ward";

export type TimeGrain =
  | "year" | "fiscal_year" | "quarter" | "month" | "date";

export type ValueKind =
  | "count" | "rate" | "share" | "currency" | "index" | "duration" | "raw";

export type Direction =
  | "higher_is_better" | "lower_is_better" | "neutral";

export type ScaleHint =
  | "linear" | "log" | "quantile" | "symlog";

export interface IndicatorMeta {
  id: string;
  title: string;
  description?: string;
  entity_kind: EntityKind;
  time_grain: TimeGrain;
  value_kind: ValueKind;
  direction: Direction;
  scale_hint?: ScaleHint;
  unit: string;
  denominator?: string | null;
  notes?: string;
}

export interface IndicatorRow {
  entity_id: string;
  time: string;
  value: number | null;
  facet?: string | null;
}

export interface IndicatorArtifact {
  $schema: string;
  $schema_version: string;
  sources: IndicatorSource[];
  license: IndicatorLicense;
  coverage: IndicatorCoverage;
  indicator: IndicatorMeta;
  rows: IndicatorRow[];
}

// -- Fetcher ------------------------------------------------------------------

export async function fetchIndicator(path: string): Promise<IndicatorArtifact> {
  // `path` is the relative POSIX path under DATA_BASE, e.g.
  // "/indicators/in/energy/installed_mw_by_state.json".
  const res = await fetch(`${DATA_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`fetch ${path} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as IndicatorArtifact;
}

// -- Pure helpers (vitest-tested) --------------------------------------------

/** Sorted unique time values in the artifact's rows. Ascending lexicographic
 *  — works for YYYY, YYYY-MM, YYYY-MM-DD per the schema's time pattern. */
export function uniqueTimes(rows: readonly IndicatorRow[]): string[] {
  const seen = new Set<string>();
  for (const r of rows) seen.add(r.time);
  return [...seen].sort();
}

/** Sum of `value` over all rows matching `time`, grouped by entity_id.
 *  Null values are ignored (per schema: null = "not available"). When no
 *  non-null row exists for an entity at this time, the entity is omitted. */
export function rollupByEntity(
  rows: readonly IndicatorRow[],
  time: string,
): Map<string, number> {
  const out = new Map<string, number>();
  for (const r of rows) {
    if (r.time !== time) continue;
    if (r.value == null) continue;
    out.set(r.entity_id, (out.get(r.entity_id) ?? 0) + r.value);
  }
  return out;
}

/** Per-entity facet breakdown for a given time. Used by tooltips. */
export function facetsByEntity(
  rows: readonly IndicatorRow[],
  time: string,
): Map<string, Array<{ facet: string; value: number }>> {
  const out = new Map<string, Array<{ facet: string; value: number }>>();
  for (const r of rows) {
    if (r.time !== time) continue;
    if (r.value == null) continue;
    const f = r.facet ?? "";
    const arr = out.get(r.entity_id) ?? [];
    arr.push({ facet: f, value: r.value });
    out.set(r.entity_id, arr);
  }
  for (const arr of out.values()) arr.sort((a, b) => b.value - a.value);
  return out;
}

/** Pick a base hue (degrees) for the sequential ramp from the indicator's
 *  direction. `higher_is_better` -> teal/green; `lower_is_better` -> red;
 *  `neutral` -> blue. Dark always means "high value" regardless of direction
 *  (the citizen reading colour intensity reads "more of the thing"). */
export function hueForDirection(d: Direction): number {
  switch (d) {
    case "higher_is_better": return 160;
    case "lower_is_better":  return 25;
    case "neutral":          return 250;
  }
}

/** Normalise `value` to 0..1 using a linear, log, or symlog scale.
 *  `quantile` is treated as `linear` here (the chart can pre-rank values
 *  if it wants true quantile bucketing). Returns null when value is null
 *  or the domain is degenerate. */
export function normalise(
  value: number | null,
  min: number,
  max: number,
  scale: ScaleHint = "linear",
): number | null {
  if (value == null || !Number.isFinite(value)) return null;
  if (!(max > min)) return 0.5; // single-point domain
  if (scale === "log") {
    // log requires positive values; if min <= 0, fall back to linear.
    if (min > 0 && value > 0) {
      return (Math.log(value) - Math.log(min)) / (Math.log(max) - Math.log(min));
    }
  }
  if (scale === "symlog") {
    const sym = (x: number) => Math.sign(x) * Math.log1p(Math.abs(x));
    return (sym(value) - sym(min)) / (sym(max) - sym(min));
  }
  return (value - min) / (max - min);
}

/** Sequential OkLCh ramp swatch: light (high L, low C) at t=0 -> dark
 *  (low L, moderate C) at t=1, all at the same hue. */
export function sequentialSwatch(t: number, hue: number): string {
  const clamped = Math.max(0, Math.min(1, t));
  const l = 0.94 - 0.50 * clamped; // 0.94 .. 0.44
  const c = 0.04 + 0.13 * clamped; // 0.04 .. 0.17
  return oklchToHex({ l, c, h: hue });
}

/** End-to-end fill resolver. Returns hex `#rrggbb` or a fallback grey when
 *  the value is null/missing. */
export function fillForValue(
  value: number | null,
  min: number,
  max: number,
  direction: Direction,
  scale: ScaleHint = "linear",
  fallback = "#e2e8f0",
): string {
  const t = normalise(value, min, max, scale);
  if (t == null) return fallback;
  return sequentialSwatch(t, hueForDirection(direction));
}

/** Number formatter selected by `value_kind` + `unit`. Citizen-readable
 *  (1,234 not 1234; short SI suffixes for big numbers). */
export function formatValue(
  value: number | null,
  meta: Pick<IndicatorMeta, "value_kind" | "unit">,
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const { value_kind, unit } = meta;
  if (value_kind === "share") {
    // share can be stored as 0..1 OR as a percentage 0..100 with unit "%".
    const pct = unit.includes("%") || unit === "%" || value > 1 ? value : value * 100;
    return `${pct.toFixed(1)}%`;
  }
  if (value_kind === "currency") {
    return `${formatCompact(value)} ${unit}`;
  }
  if (value_kind === "rate" || value_kind === "index" || value_kind === "duration") {
    return `${formatCompact(value)} ${unit}`.trim();
  }
  if (value_kind === "count") {
    return `${Math.round(value).toLocaleString("en-IN")} ${unit}`.trim();
  }
  // raw + unknown
  return `${formatCompact(value)} ${unit}`.trim();
}

/** Short SI-style compact formatter: 1234 -> "1.2k", 12_345_678 -> "12.3M". */
export function formatCompact(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(value / 1e3).toFixed(1)}k`;
  if (abs >= 10) return value.toFixed(0);
  return value.toFixed(2);
}
