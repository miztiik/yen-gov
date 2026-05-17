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

/**
 * Controlled vocabulary for `indicator.renderer_rules[]` (v1.5).
 * The schema validates the slug shape (`^[a-z][a-z0-9_]*$`) but does not
 * enumerate; this union is the live frontend-recognised set. Adding a new
 * slug requires: (a) extend this union, (b) update the consuming renderer
 * (e.g. `canShowRank` in indicator-card.ts), (c) document it in
 * docs/concepts/indicator-naming.md §6.
 *
 *  - `no_rank_table`        — suppress rank line on IndicatorCard + ranked-table view.
 *  - `no_growth_across_break` — refuse to compute YoY growth that spans a `series_break`.
 *  - `mask_be_in_long_view` — visually distinguish Budget-Estimate periods from Actuals.
 *  - `force_per_capita_choropleth` — block raw-magnitude choropleth for a not-comparable raw count.
 */
export type RendererRuleSlug =
  | "no_rank_table"
  | "no_growth_across_break"
  | "mask_be_in_long_view"
  | "force_per_capita_choropleth";

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
  // v1.1 (2026-05-11) — governance/honesty metadata. All optional.
  icon?: string;
  attribution_geography?:
    | "where_produced" | "where_allocated" | "where_consumed" | "where_billed"
    | "where_resident" | "where_administered";
  comparability?:
    // v1.5 4-level ladder (preferred — see indicator.schema.json + docs/concepts/indicator-naming.md §5).
    | "comparable_across_states_and_time"
    | "comparable_across_states_snapshot_only"
    | "comparable_within_state_over_time"
    | "directional_only"
    // v1.0–v1.4 tokens (deprecated; kept for back-compat per schema description).
    // Migration map: comparable_across_states → comparable_across_states_and_time;
    // not_comparable_across_states → directional_only;
    // comparable_with_normalisation → splits per-artifact into one of the 4 new tokens on next touch.
    | "comparable_across_states"
    | "comparable_with_normalisation"
    | "not_comparable_across_states";

  /**
   * Optional v1.5 (Hans) field. Slug-strings from a controlled vocabulary
   * (see docs/concepts/indicator-naming.md §6) that bind renderer
   * behaviour to the indicator's data shape. Schema enforces the slug
   * shape `^[a-z][a-z0-9_]*$`; the union below is the live vocabulary
   * the frontend recognises today. Unknown slugs validate but are
   * ignored by the renderer (forward-compat: new slugs land in the
   * schema/data before the renderer learns them).
   */
  renderer_rules?: ReadonlyArray<RendererRuleSlug | (string & {})>;
  funding_split?: {
    centre_pct: number;
    state_pct: number;
    other_pct?: number;
    source: string;
  };
  implementing_authority?: "state" | "centre" | "joint" | "local_body" | "parastatal";
  methodology_vintage?: string;
  series_breaks?: Array<{
    at_time: string;
    kind: "rebase" | "definition_change" | "frame_change" | "coverage_change";
    note: string;
  }>;
  /**
   * Lowest geographic grain at which this indicator is measurably valid
   * (Phase 3 c3 of TN-GRANULAR-GEO-PLAN). When undefined the drill-down is
   * unrestricted. PLFS / NFHS sample-based indicators set this to "state"
   * or "district" so the citizen cannot drill into a level the underlying
   * methodology does not support. Greyed crumbs in the breadcrumb surface
   * the floor in their tooltip ("this indicator is measured at district
   * level, not village"). The schema bump that makes this field part of
   * the on-disk indicator artifact is deferred to a follow-up commit; the
   * TS type accepts it now so the drill-down honours it as soon as a
   * producer starts emitting it.
   */
  min_grain?: "country" | "state" | "district" | "subdistrict" | "village";
  /**
   * v4.3 (Phase 1 step 4) optional registry of distinct measurable
   * quantities that share this indicator's (entity, time) axis. A composite
   * (e.g. `discom_health`) lists one entry per quantity; rows bind to a
   * sub_metric by setting `IndicatorRow.facet` to the sub_metric's `id`,
   * and may carry `IndicatorRow.unit` to override the indicator-level unit
   * (different sub_metrics typically have different units). When absent
   * (the common case), behaviour is unchanged from v4.2.
   */
  sub_metrics?: ReadonlyArray<IndicatorSubMetric>;
}

/** v4.3 sub_metric registry entry. See `IndicatorMeta.sub_metrics`. */
export interface IndicatorSubMetric {
  id: string;
  label: string;
  unit: string;
  value_kind?: ValueKind;
  direction?: Direction;
  description?: string;
}

export interface IndicatorRow {
  entity_id: string;
  time: string;
  value: number | null;
  facet?: string | null;
  /** v1.6+: optional adapter-owned citizen label for the period token.
   *  When present, frontend prefers this over re-deriving from `time`. */
  period_label?: string | null;
  /** v4.3+ (Phase 1 step 4): optional row-level override of
   *  `IndicatorMeta.unit`. Takes precedence for THIS row's formatter
   *  selection. Required for composites whose sub_metrics carry
   *  heterogeneous units; absent for single-unit indicators. */
  unit?: string | null;
}

// -- Folded blocks (schema v2.0) ---------------------------------------------

/** Period frequency enum, mirrors indicator.schema.json
 *  `series_spec.expected_periods[].frequency`. */
export type PeriodFrequency =
  | "annual_fy"
  | "annual_cy"
  | "quarterly_fy"
  | "quarterly_cy"
  | "monthly"
  | "weekly"
  | "daily"
  | "decennial"
  | "ad_hoc";

/** A period token. Historically appeared in `series_spec.expected_periods[]`
 *  and `collection_inventory.observed_periods[]`; in v4.0+ those surfaces
 *  were lifted out of the indicator artifact per ADR-0026, so this type is
 *  now only used by the completeness index consumers. */
export interface PeriodToken {
  key: string;
  label: string;
  frequency: PeriodFrequency;
}

/** v4.0+: series_spec is reduced to a single human-authored description.
 *  Expected geographies / expected periods now live in the completeness
 *  index, not in the per-indicator artifact. */
export interface SeriesSpec {
  description: string;
}

export interface MethodologyBreak {
  from: string;
  note: string;
}

export interface IndicatorMethodology {
  definition: string;
  publisher: string;
  publisher_methodology_url?: string | null;
  documentation_status: "stub" | "partial" | "authored";
  methodology_breaks: MethodologyBreak[];
  known_caveats: string[];
  notes: string[];
  related_indicators?: string[];
  editor_note_md?: string;
  policy_context?: string[];
  chart_defaults?: Record<string, unknown>;
}

export interface IndicatorArtifact {
  $schema: string;
  $schema_version: string;
  sources: IndicatorSource[];
  license: IndicatorLicense;
  coverage: IndicatorCoverage;
  indicator: IndicatorMeta;
  rows: IndicatorRow[];
  /** Required since schema v2.0; optional in TS only so v1.5/v1.6
   *  test fixtures still type-check. */
  series_spec?: SeriesSpec;
  methodology?: IndicatorMethodology;
  /** Reserved for the divergence subsystem; always `null` today. */
  divergence?: null;
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

/** For each entity, return its (time, value) series sorted ascending in
 *  time. Multiple rows at the same (entity, time) are summed (mirrors
 *  rollupByEntity's null-skip semantics). Used by the small-multiples
 *  primitive to draw one mini sparkline per state. */
export function seriesByEntity(
  rows: readonly IndicatorRow[],
): Map<string, Array<{ time: string; value: number }>> {
  const buckets = new Map<string, Map<string, number>>();
  for (const r of rows) {
    if (r.value == null) continue;
    let inner = buckets.get(r.entity_id);
    if (!inner) {
      inner = new Map<string, number>();
      buckets.set(r.entity_id, inner);
    }
    inner.set(r.time, (inner.get(r.time) ?? 0) + r.value);
  }
  const out = new Map<string, Array<{ time: string; value: number }>>();
  for (const [entity, inner] of buckets) {
    const arr = [...inner.entries()]
      .map(([time, value]) => ({ time, value }))
      .sort((a, b) => a.time.localeCompare(b.time));
    out.set(entity, arr);
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
