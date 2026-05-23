// Typed view of `datasets/taxonomy/indicators.parquet` rows + Zod schema.
// Mirrors `datasets/schemas/indicator-catalogue.schema.json` v1.1 column-for-column.
//
// SEPARATE from `frontend/src/lib/indicators.ts`. That file's `IndicatorMeta`
// mirrors the LEGACY per-shard `indicator.schema.json` v1.5 which describes
// `datasets/indicators/in/<topic>/<id>.json` artifacts. THIS file mirrors the
// NEW canonical catalogue (one row per indicator, lives at
// `datasets/taxonomy/indicators.parquet`). The legacy per-shard JSON retires
// family-by-family via the P.* canonical-pivot PRs; the catalogue is the
// forward path.
//
// Pure module: no DOM, no Svelte, no DuckDB. Exercised directly by vitest.
//
// v1.1 (T.3 2026-05-22) adds `id_aliases?: string[]` + `deprecated_in?: string`
// for one-release back-compat dereferencing. The 60-day expiry window on
// `deprecated_in` is enforced server-side by Tier-B
// (`backend/yen_gov/validate.py::tier_b_indicator_alias_window`); the
// frontend dereferencer in this module honours the field as published.

import { z } from "zod";

// ---------------------------------------------------------------------------
// Controlled vocabularies (mirrored from indicator-catalogue.schema.json v1.1).
// Keep in lockstep with the JSON Schema -- pair them at the same commit.
// ---------------------------------------------------------------------------

export const CADENCE_VALUES = [
  "annual_fy",
  "annual_cy",
  "quarterly_fy",
  "quarterly_cy",
  "monthly_fy",
  "monthly_cy",
  "weekly",
  "daily",
  "decennial",
  "ad_hoc",
] as const;
export type Cadence = (typeof CADENCE_VALUES)[number];

export const PILLAR_VALUES = ["people", "money", "infrastructure", "politics"] as const;
export type Pillar = (typeof PILLAR_VALUES)[number];

export const VALUE_KIND_VALUES = [
  "absolute",
  "rate",
  "ratio",
  "count",
  "index",
  "percentage",
  "currency",
] as const;
export type ValueKindCat = (typeof VALUE_KIND_VALUES)[number];

export const DIRECTION_VALUES = [
  "higher_is_better",
  "lower_is_better",
  "neutral",
] as const;
export type DirectionCat = (typeof DIRECTION_VALUES)[number];

export const ATTRIBUTION_GEOGRAPHY_VALUES = [
  "where_produced",
  "where_allocated",
  "where_consumed",
  "where_billed",
  "where_resident",
  "where_administered",
] as const;
export type AttributionGeography = (typeof ATTRIBUTION_GEOGRAPHY_VALUES)[number];

export const COMPARABILITY_VALUES = [
  "comparable_across_states_and_time",
  "comparable_across_states_snapshot_only",
  "comparable_within_state_over_time",
  "directional_only",
] as const;
export type Comparability = (typeof COMPARABILITY_VALUES)[number];

export const IMPLEMENTING_AUTHORITY_VALUES = [
  "state",
  "centre",
  "joint",
  "local_body",
  "parastatal",
  "private",
  "unspecified",
] as const;
export type ImplementingAuthority = (typeof IMPLEMENTING_AUTHORITY_VALUES)[number];

export const REVISION_TIER_VALUES = [
  "first_release",
  "revised",
  "final",
  "mixed",
] as const;
export type RevisionTier = (typeof REVISION_TIER_VALUES)[number];

// D30 kebab pattern (single segment, lowercase, ≤60 chars). Mirrors
// `indicator-catalogue.schema.json::properties.indicators.items.properties.indicator_id.pattern`.
export const D30_KEBAB_PATTERN = /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/;

// Legacy folded-shard id form: `<topic_slug>/<snake_case_id>` (pre-canonical-pivot
// shape e.g. `fiscal/outstanding_debt_pct_gsdp`). Mirrors the v1.1
// `id_aliases.items.pattern` exactly (alternation: D30 OR slash-form).
export const LEGACY_SLASH_FORM_PATTERN = /^[a-z][a-z0-9_]*\/[a-z][a-z0-9_]*$/;

export const ALIAS_PATTERN =
  /^([a-z][a-z0-9]*(-[a-z0-9]+)*|[a-z][a-z0-9_]*\/[a-z][a-z0-9_]*)$/;

// ISO calendar date `YYYY-MM-DD`. Lexicographic-sortable; no semver math.
export const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

// ---------------------------------------------------------------------------
// Funding-split nested struct.
// ---------------------------------------------------------------------------

export const FundingSplitSchema = z
  .object({
    centre_pct: z.number().min(0).max(100),
    state_pct: z.number().min(0).max(100),
    other_pct: z.number().min(0).max(100).optional(),
    source: z.string().min(1),
  })
  .strict();
export type FundingSplit = z.infer<typeof FundingSplitSchema>;

// ---------------------------------------------------------------------------
// Canonical catalogue row (v1.1).
// Field order mirrors `indicator-catalogue.schema.json` properties order for
// review-diff clarity.
// ---------------------------------------------------------------------------

export const IndicatorCatalogueRowSchema = z
  .object({
    indicator_id: z.string().regex(D30_KEBAB_PATTERN).max(60),
    label_short: z.string().min(1).max(60),
    label_long: z.string().min(1),
    description_short: z.string().min(10),
    description_long: z.string().optional(),
    unit: z.string().min(1),
    cadence: z.enum(CADENCE_VALUES),
    default_period_seq_for_cadence: z.number().int().optional(),
    family: z.string().regex(/^[a-z][a-z0-9_]*$/),
    pillar: z.enum(PILLAR_VALUES),
    topic_tags: z.array(z.string().regex(/^[a-z][a-z0-9_]*$/)).default([]),
    value_kind: z.enum(VALUE_KIND_VALUES),
    direction: z.enum(DIRECTION_VALUES),
    denominator: z.string().nullable().optional(),
    attribution_geography: z.enum(ATTRIBUTION_GEOGRAPHY_VALUES),
    comparability: z.enum(COMPARABILITY_VALUES),
    implementing_authority: z.enum(IMPLEMENTING_AUTHORITY_VALUES).nullable().optional(),
    funding_split: FundingSplitSchema.nullable().optional(),
    methodology_vintage: z.string().nullable().optional(),
    revision_tier: z.enum(REVISION_TIER_VALUES).nullable().optional(),
    excluded_notes: z.array(z.string()).default([]),
    parent_indicator_id: z.string().regex(D30_KEBAB_PATTERN).max(60).nullable().optional(),
    dimension_values: z.record(z.string(), z.string()).nullable().optional(),
    methodology_version: z.string().nullable().optional(),
    methodology_break_ids: z.array(z.string()).default([]),
    source_id: z.string().nullable().optional(),
    coverage_states_count: z.number().int().min(0).optional(),
    coverage_year_min: z.number().int().optional(),
    coverage_year_max: z.number().int().optional(),
    coverage_density: z.number().min(0).max(1).optional(),
    renderer_rules: z.array(z.string().regex(/^[a-z][a-z0-9_]*$/)).default([]),
    // v1.1 (T.3 2026-05-22) -- one-release back-compat. Each alias is EITHER
    // D30 kebab (rename history) OR legacy `<topic>/<snake_case_id>` (pre-pivot
    // folded-shard form). When non-empty, `deprecated_in` MUST be set in the
    // same row (server-side semantic-pairing rule; see
    // `backend/yen_gov/canonical/indicators_seed.py`).
    id_aliases: z.array(z.string().regex(ALIAS_PATTERN).max(80)).default([]),
    // ISO calendar date the alias chain was introduced. Tier-B
    // `tier_b_indicator_alias_window` rejects rows whose deprecated_in is
    // older than 60 days (one-release window per Gregor lock 2026-05-22).
    deprecated_in: z.string().regex(ISO_DATE_PATTERN).nullable().optional(),
  })
  .strict();
export type IndicatorCatalogueRow = z.infer<typeof IndicatorCatalogueRowSchema>;

// ---------------------------------------------------------------------------
// Indexing + dereferencing.
// ---------------------------------------------------------------------------

/**
 * Lookup index over a catalogue array. Built once, reused across many
 * resolve calls (typical scenario: load the catalogue from
 * `indicators.parquet` via DuckDB-WASM, build the index, then dereference
 * many slugs as the user navigates).
 */
export interface IndicatorCatalogueIndex {
  /** Map from canonical `indicator_id` -> row. */
  readonly byId: ReadonlyMap<string, IndicatorCatalogueRow>;
  /** Map from each alias string (D30 OR legacy slash-form) -> the row whose
   * `id_aliases[]` contains it. Aliases collide-detect at build time. */
  readonly byAlias: ReadonlyMap<string, IndicatorCatalogueRow>;
}

/**
 * Build a lookup index. Throws on alias collisions (two rows claim the same
 * legacy slug) and on alias-equals-canonical-id collisions (a row's alias
 * shadows another row's `indicator_id`). Both are operator authoring bugs
 * that would lead to silent wrong-row dereferences at runtime.
 */
export function buildIndicatorCatalogueIndex(
  rows: readonly IndicatorCatalogueRow[],
): IndicatorCatalogueIndex {
  const byId = new Map<string, IndicatorCatalogueRow>();
  const byAlias = new Map<string, IndicatorCatalogueRow>();
  for (const row of rows) {
    if (byId.has(row.indicator_id)) {
      throw new Error(
        `indicator_id collision: ${row.indicator_id!} appears in two catalogue rows`,
      );
    }
    byId.set(row.indicator_id, row);
  }
  for (const row of rows) {
    for (const alias of row.id_aliases ?? []) {
      if (byId.has(alias)) {
        throw new Error(
          `alias collision: ${alias} is a canonical indicator_id; ` +
            `cannot also be an alias of ${row.indicator_id}`,
        );
      }
      const prior = byAlias.get(alias);
      if (prior && prior.indicator_id !== row.indicator_id) {
        throw new Error(
          `alias collision: ${alias} aliased to both ${prior.indicator_id} ` +
            `and ${row.indicator_id}`,
        );
      }
      byAlias.set(alias, row);
    }
  }
  return { byId, byAlias };
}

/**
 * Dereference a slug (URL param, query string, or DuckDB column value) to
 * the canonical catalogue row.
 *
 * Resolution order:
 *  1. Exact canonical `indicator_id` match.
 *  2. Alias match (legacy slash-form OR D30 rename history).
 *  3. null when the slug is unknown.
 *
 * The slug-as-canonical case wins over the slug-as-alias case (an alias
 * cannot shadow a live canonical id; `buildIndicatorCatalogueIndex` rejects
 * authoring patterns that would create the collision).
 */
export function resolveIndicatorId(
  slug: string,
  index: IndicatorCatalogueIndex,
): IndicatorCatalogueRow | null {
  if (!slug) return null;
  const canonical = index.byId.get(slug);
  if (canonical) return canonical;
  const aliased = index.byAlias.get(slug);
  if (aliased) return aliased;
  return null;
}

/**
 * Same as `resolveIndicatorId` but returns only the canonical
 * `indicator_id` string (handy for redirect handlers / DuckDB query
 * rewrites that don't need the full row).
 */
export function resolveCanonicalIndicatorId(
  slug: string,
  index: IndicatorCatalogueIndex,
): string | null {
  const row = resolveIndicatorId(slug, index);
  return row ? row.indicator_id : null;
}

/**
 * Returns true when the input slug resolved via the alias path (vs the
 * canonical path). Callers use this to decide whether to issue a 301-style
 * redirect or just continue silently. Cheap: one map lookup.
 */
export function isAliasSlug(slug: string, index: IndicatorCatalogueIndex): boolean {
  if (!slug) return false;
  if (index.byId.has(slug)) return false;
  return index.byAlias.has(slug);
}
