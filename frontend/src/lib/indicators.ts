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
   * Publisher release cadence (v4.1, ADR-0027). Separate from `time_grain`:
   * a Census frame has `time_grain: year` but `cadence: decennial`; an
   * ad-hoc emissions inventory has `time_grain: year` but `cadence:
   * ad_hoc`. Used by `deriveTemporalRange` to know when omitting the gap
   * count is the honest treatment (decennial/ad_hoc have no defined
   * inter-observation interval, so "gaps" framing is misleading).
   */
  cadence?: "annual" | "annual_fy" | "quarterly" | "monthly" | "decennial" | "ad_hoc" | (string & {});
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

  // -- v4.4 proto-ontology bootstrap (PR-T, row 1.10 of TODO/20260517-canonical-long-format-pivot.md).
  // Eight optional fields establishing the OWID-floor grounding metadata
  // Phase 4 SLM will consume. All optional; existing v4.3 artifacts remain valid.

  /**
   * v4.4 (Hans + Max, row 1.10): one-line citizen-readable description
   * (≤280 chars), Plain-Facts style. Used by the chart wrapper as the
   * legend caption (visible at page load, NOT behind tooltip/expander).
   * Falls back to `title` when absent. NULL-able at schema layer per OWID
   * `MetadataValidator` precedent; enforcement lives at the per-family
   * PR-template gate, not at the schema. NO auto-stub mechanism — a
   * tautological `{title} ({unit})` stub looks authoritative on a chart
   * legend but is factually empty (CLAUDE.md §5 + Rosling Single-perspective).
   */
  description_short?: string;

  /**
   * v4.4 (Hans + Max, row 1.10): multi-paragraph markdown methodology —
   * numerator / denominator / scope / known breaks. Distinct from
   * `description` (one-paragraph definition) and `methodology.definition`:
   * this field is the long-form scholarly write-up for indicators that
   * warrant it. Renderer surfaces it in the methodology drawer when present.
   */
  description_long?: string;

  /**
   * v4.4 (Hans + Max, row 1.10): tight glyph form of `unit` for use as a
   * chart Y-axis label where horizontal space is tight (e.g. `%` for
   * unit=`percent`, `₹cr` for unit=`INR crore`, `MW`, `t/yr`). Chart
   * wrapper falls back to the full `unit` string when absent.
   */
  short_unit?: string;

  /**
   * v4.4 (Hans + Max, row 1.10): one sentence naming the numerator and
   * denominator (or otherwise the derivation pipeline) when this indicator
   * is itself derived from one or more raw upstream indicators (e.g.
   * per-capita rates, growth rates, composites). Surfaced in the chart's
   * source card.
   */
  derivation_note?: string;

  /**
   * v4.4 (Hans + Max, row 1.10): catalogue-level FK array into
   * `taxonomy/sources.parquet`. Each item is a `source_id` per CLAUDE.md
   * §12. Distinct from per-observation `source_id` (which lives on every
   * observation row): this lists the catalogue-level sources that fed THIS
   * indicator's curation (methodology PDF, definition note, peer-reviewed
   * paper). Renderer surfaces these in the source card.
   */
  source_ref?: ReadonlyArray<string>;

  /**
   * v4.4 (Hans + Max, row 1.10): semantic period grain — what the time
   * stamp on each row MEANS at the publisher-intent layer. Distinct from
   * `time_grain` (resolution of the stamp) and `cadence` (release rhythm).
   * Used by the Phase 4 SLM grounding layer to refuse cross-grain
   * comparisons that look valid syntactically but are nonsensical
   * semantically (e.g. comparing an FY value to a CY value).
   */
  valid_period_grain?: "year" | "fiscal_year" | "election_date";

  /**
   * v4.4 (Hans + Max, row 1.10): semantic entity grain — the level at
   * which this indicator's values are methodologically valid. Distinct
   * from `entity_kind` (schema-shape of `entity_id`) and `min_grain`
   * (TS-only frontend hint): publisher-intent layer. Used as a hard rail
   * by the Phase 4 SLM dispatcher.
   */
  valid_entity_grain?: "country" | "state" | "district" | "ac" | "pc";

  /**
   * v4.4 (Hans + Max, row 1.10): governance-pyramid classification —
   * input (resource spent), output (immediate deliverable), or outcome
   * (citizen-life change). Critical for honest reading: 'MGNREGA
   * performance' means very different things depending on which box this
   * indicator sits in.
   */
  is_input_output_outcome?: "input" | "output" | "outcome";
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

// -- Temporal range derivation -----------------------------------------------
// TS mirror of backend/yen_gov/inventory/derive.py::derive_temporal_range.
// Shared-fixture parity test in indicators.test.ts asserts both sides agree
// on every case under datasets/_test/temporal-range-fixtures/cases.json.

export interface TemporalRange {
  min_time: string;
  max_time: string;
  min_period_label: string;
  max_period_label: string;
  observed_periods_within_range?: number;
  gap_count_within_range?: number;
  time_grain?: string;
  cadence?: string;
}

type _Shape = "date" | "year_month" | "year" | "other";

const _SHAPE_DATE = /^\d{4}-\d{2}-\d{2}$/;
const _SHAPE_YYYYMM = /^\d{4}-\d{2}$/;
const _SHAPE_YYYY = /^\d{4}$/;

function _detectShape(token: string): _Shape {
  const t = token.trim();
  if (_SHAPE_DATE.test(t)) return "date";
  if (_SHAPE_YYYYMM.test(t)) return "year_month";
  if (_SHAPE_YYYY.test(t)) return "year";
  return "other";
}

function _expectedPeriodCount(args: {
  min_time: string;
  max_time: string;
  shape: _Shape;
  time_grain: string;
}): number | null {
  const { min_time, max_time, shape, time_grain } = args;
  if (min_time === max_time) return 1;
  if (shape === "year") return Number(max_time) - Number(min_time) + 1;
  if (shape === "year_month") {
    const miny = Number(min_time.slice(0, 4));
    const minm = Number(min_time.slice(5, 7));
    const maxy = Number(max_time.slice(0, 4));
    const maxm = Number(max_time.slice(5, 7));
    const total_months = (maxy * 12 + maxm) - (miny * 12 + minm) + 1;
    if (time_grain === "month") return total_months;
    if (time_grain === "fiscal_year") return (maxy - miny) + 1;
    if (time_grain === "quarter") {
      if (total_months % 3 !== 0 && (total_months - 1) % 3 !== 0) return null;
      return Math.floor((total_months - 1) / 3) + 1;
    }
    return null;
  }
  return null;
}

const _UNDEFINED_CADENCE: ReadonlySet<string> = new Set(["decennial", "ad_hoc"]);

/**
 * Derive observed temporal-range fields from an indicator's rows + header.
 *
 * Mirrors `derive_temporal_range` in `backend/yen_gov/inventory/derive.py`.
 * Returns `null` when rows is empty or no row carries a `time` field.
 * Throws when rows[].time tokens span more than one detected shape — that
 * is an adapter bug (CLAUDE.md §10 fail-loud) and silent-omit would
 * overload the null signal.
 */
export function deriveTemporalRange(
  rows: readonly IndicatorRow[],
  indicator: Pick<IndicatorMeta, "id" | "time_grain" | "cadence">,
): TemporalRange | null {
  if (!rows || rows.length === 0) return null;
  const grain = String(indicator?.time_grain ?? "");
  const cadence = indicator?.cadence ? String(indicator.cadence) : "";
  const ind_id = String(indicator?.id ?? "<unknown>");

  const times: string[] = [];
  const label_for: Record<string, string> = {};
  for (const row of rows) {
    if (!row || row.time === undefined || row.time === null) continue;
    const t = String(row.time);
    times.push(t);
    if (!(t in label_for)) {
      const lbl = (row as IndicatorRow & { period_label?: string }).period_label;
      label_for[t] = String(lbl ?? t);
    }
  }
  if (times.length === 0) return null;

  const distinct_times = Array.from(new Set(times)).sort();
  const shapes = new Set(distinct_times.map(_detectShape));
  if (shapes.size > 1) {
    const sample = distinct_times.slice(0, 5);
    throw new Error(
      `indicator ${ind_id}: heterogeneous rows[].time vocabulary: ` +
        `shapes=${JSON.stringify([...shapes].sort())}, sample_tokens=${JSON.stringify(sample)}`,
    );
  }
  const [shape] = [...shapes] as [_Shape];

  const min_time = distinct_times[0];
  const max_time = distinct_times[distinct_times.length - 1];

  const out: TemporalRange = {
    min_time,
    max_time,
    min_period_label: label_for[min_time],
    max_period_label: label_for[max_time],
  };
  if (grain) out.time_grain = grain;
  if (cadence) out.cadence = cadence;

  if (cadence && _UNDEFINED_CADENCE.has(cadence)) return out;

  out.observed_periods_within_range = distinct_times.length;

  const expected = _expectedPeriodCount({ min_time, max_time, shape, time_grain: grain });
  if (expected !== null && grain !== "date") {
    const gap = expected - distinct_times.length;
    if (gap < 0) {
      throw new Error(
        `indicator ${ind_id}: observed periods (${distinct_times.length}) ` +
          `exceed expected (${expected}) at grain=${JSON.stringify(grain)}, shape=${JSON.stringify(shape)}; ` +
          `check cadence assumptions`,
      );
    }
    out.gap_count_within_range = gap;
  }

  return out;
}

/**
 * Citizen-readable cadence word. Prefers the publisher's declared
 * `cadence` over the per-row `time_grain` (a Census artifact's grain
 * is `year` but its cadence is `decennial` — the citizen should read
 * "every 10 years", not "annual").
 */
export function cadenceWord(
  cadence: string | undefined,
  time_grain: string | undefined,
): string {
  switch (cadence) {
    case "annual": return "annual";
    case "annual_fy": return "annual (fiscal year)";
    case "quarterly": return "quarterly";
    case "monthly": return "monthly";
    case "decennial": return "every 10 years";
    case "ad_hoc": return "irregular updates";
  }
  switch (time_grain) {
    case "year": return "annual";
    case "fiscal_year": return "annual (fiscal year)";
    case "quarter": return "quarterly";
    case "month": return "monthly";
    case "date": return "";
  }
  return "";
}

/**
 * Build the temporal caption string rendered under each IndicatorChoropleth.
 * Multi-period: "2018 → 2022 · annual". Single-period: "As of 2024 · annual".
 * When `cadenceWord` returns empty (date snapshot with no cadence), the
 * cadence segment is dropped.
 */
export function buildTemporalCaption(range: TemporalRange): string {
  const word = cadenceWord(range.cadence, range.time_grain);
  const single = range.min_period_label === range.max_period_label;
  const body = single
    ? `As of ${range.min_period_label}`
    : `${range.min_period_label} \u2192 ${range.max_period_label}`;
  return word ? `${body} \u00b7 ${word}` : body;
}
