// Typed view of `datasets/taxonomy/indicators.parquet` rows + Zod schema.
// Mirrors `datasets/schemas/indicator-catalogue.schema.json` v3.0 column-for-column.
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
// v2.0 (PR-B1 2026-05-26 grain-over-entity rip per ADR-0044): adds required
// `entity_kinds: EntityKind[]` + `default_entity_kind: EntityKind`. Drops
// `id_aliases` + `deprecated_in` -- per-PR rename scripts under
// `tools/migrate/` replace the one-release alias window.
//
// v3.0 (Deferral 2 of TODO/20260609-url-prefix-drop-phase0-plan.md, 2026-06-10):
// adds required `url_slug: string` (citizen-facing URL slug at the position-2
// URL segment /<state>/<url_slug>, single-segment kebab, max 60 chars) +
// optional `url_slug_history: string[]` (append-only, NO TTL, permanent
// redirect ledger per Max OWID precedent). Extends the runtime index with
// `bySlug` map + cross-row + cross-history collision throw at index-build
// time (so a rename PR that forgets to append to url_slug_history surfaces
// loudly instead of silently breaking shared bookmarks). Atomic ship per
// Gregor verdict i (born-mature contract; no strangler-fig).

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

// v2.0 (PR-B1 2026-05-26 grain-over-entity rip per ADR-0044). The closed
// enum of entity_kinds supported on the canonical catalogue. Widened beyond
// the geographic four {country,state,district,ac} to include {party,candidate}
// because election-class indicators (party-vote-share-pct, candidate-rank)
// carry party/candidate as the entity.
export const ENTITY_KIND_VALUES = [
  "country",
  "state",
  "district",
  "ac",
  "party",
  "candidate",
] as const;
export type EntityKind = (typeof ENTITY_KIND_VALUES)[number];

export const REVISION_TIER_VALUES = [
  "first_release",
  "revised",
  "final",
  "mixed",
] as const;
export type RevisionTier = (typeof REVISION_TIER_VALUES)[number];

// D30 kebab pattern (single segment, lowercase, <=60 chars). Mirrors
// `indicator-catalogue.schema.json::properties.indicators.items.properties.indicator_id.pattern`.
export const D30_KEBAB_PATTERN = /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/;

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
    // v2.0 (PR-B1 2026-05-26 grain-over-entity rip per ADR-0044). The entity
    // kinds this indicator can be observed at. Grain dispatches at READ time
    // from each observation row's `entity_kind` column; never encoded in
    // `indicator_id`. After Phase-B collapse pairs the same indicator_id can
    // carry e.g. [country, state, district].
    entity_kinds: z.array(z.enum(ENTITY_KIND_VALUES)).min(1),
    default_entity_kind: z.enum(ENTITY_KIND_VALUES),
    // v3.0 (Deferral 2 of TODO/20260609-url-prefix-drop-phase0-plan.md,
    // 2026-06-10). REQUIRED. Citizen-facing URL slug at the position-2 URL
    // segment (/<state>/<url_slug>); same single-segment kebab pattern as
    // indicator_id. Per Hans: this is the citizen-attribution field and
    // MUST be hand-authored at catalogue-row creation time. Uniqueness
    // enforced by `buildIndicatorCatalogueIndex` + Tier-B
    // `tier_b_indicator_url_slug_unique`; cross-namespace disjointness
    // enforced by the 5-way contract at
    // `frontend/src/contracts/url-namespace-disjointness.test.ts`.
    url_slug: z.string().regex(D30_KEBAB_PATTERN).max(60),
    // v3.0 (Deferral 2). OPTIONAL. Append-only ledger of previous url_slug
    // values for this indicator. Permanent, NO TTL -- per Max OWID precedent.
    // Rename rule: set new url_slug + APPEND old url_slug to this array in
    // the SAME commit. Route layer reads this array to issue 301 redirects
    // to the current url_slug forever. NEVER reuse an entry across
    // catalogue rows -- enforced at index-build time.
    url_slug_history: z
      .array(z.string().regex(D30_KEBAB_PATTERN).max(60))
      .optional(),
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
 * many ids as the user navigates).
 *
 * v2.0 (PR-B1 2026-05-26): the byAlias map was removed alongside
 * id_aliases; per-PR rename scripts under `tools/migrate/` rewrite stale
 * ids at observation level rather than carrying them as a runtime resolve
 * surface. Use `index.byId.get(id)` for lookups.
 *
 * v3.0 (Deferral 2 of TODO/20260609-url-prefix-drop-phase0-plan.md,
 * 2026-06-10): adds `bySlug` -- map from `url_slug` AND every
 * `url_slug_history[]` entry -> the canonical row. The route layer uses
 * this for forever-redirects: a citizen visiting `/<state>/<old-slug>`
 * lands on a row whose current `url_slug` is `<new-slug>`, and the route
 * issues a 301 to `/<state>/<new-slug>`. Cross-row collisions throw at
 * build time so a rename PR that forgets to append to `url_slug_history`
 * surfaces loudly instead of silently breaking shared bookmarks.
 */
export interface IndicatorCatalogueIndex {
  /** Map from canonical `indicator_id` -> row. */
  readonly byId: ReadonlyMap<string, IndicatorCatalogueRow>;
  /**
   * Map from `url_slug` AND every `url_slug_history[]` entry -> row.
   * Lookups by current OR historical slug both land on the same canonical
   * row; the caller checks `row.url_slug` to decide whether to render
   * (current slug) or 301-redirect (historical slug). v3.0.
   */
  readonly bySlug: ReadonlyMap<string, IndicatorCatalogueRow>;
}

/**
 * Build a lookup index. Throws on:
 *   - duplicate `indicator_id` (operator authoring bug that would lead to
 *     silent wrong-row dereferences at runtime),
 *   - duplicate `url_slug` across rows, OR `url_slug` of one row
 *     colliding with `url_slug_history[]` of any other row -- both shapes
 *     would silently break the forever-redirect ledger (v3.0).
 */
export function buildIndicatorCatalogueIndex(
  rows: readonly IndicatorCatalogueRow[],
): IndicatorCatalogueIndex {
  const byId = new Map<string, IndicatorCatalogueRow>();
  const bySlug = new Map<string, IndicatorCatalogueRow>();
  for (const row of rows) {
    if (byId.has(row.indicator_id)) {
      throw new Error(
        `indicator_id collision: ${row.indicator_id!} appears in two catalogue rows`,
      );
    }
    byId.set(row.indicator_id, row);

    // v3.0: register the current url_slug + every historical slug. A
    // collision means either two indicators claim the same citizen-facing
    // slug (current) OR an indicator's old slug was reused for a different
    // row's current/historical slug -- both break shared bookmarks.
    const slugs: string[] = [row.url_slug, ...(row.url_slug_history ?? [])];
    for (const slug of slugs) {
      if (bySlug.has(slug) && bySlug.get(slug) !== row) {
        throw new Error(
          `url_slug collision: ${slug!} appears in two catalogue rows ` +
            `(${bySlug.get(slug)!.indicator_id} and ${row.indicator_id}). ` +
            `url_slug + url_slug_history entries must be globally unique ` +
            `across the catalogue -- never reuse a retired slug for a ` +
            `different indicator.`,
        );
      }
      bySlug.set(slug, row);
    }
  }
  return { byId, bySlug };
}

/**
 * Dereference an `indicator_id` to the canonical catalogue row.
 * Returns null when the id is unknown.
 */
export function resolveIndicatorId(
  id: string,
  index: IndicatorCatalogueIndex,
): IndicatorCatalogueRow | null {
  if (!id) return null;
  return index.byId.get(id) ?? null;
}

/**
 * Dereference a `url_slug` (current OR historical) to the canonical
 * catalogue row. Returns null when the slug is unknown.
 *
 * v3.0 (Deferral 2 of TODO/20260609-url-prefix-drop-phase0-plan.md,
 * 2026-06-10). The route layer at the position-2 URL segment
 * (/<state>/<slug>) calls this and:
 *   - renders the indicator when `row.url_slug === slug` (current),
 *   - issues a 301 redirect to `row.url_slug` when the slug appears in
 *     `row.url_slug_history` (historical, forever-redirect ledger).
 */
export function resolveBySlug(
  slug: string,
  index: IndicatorCatalogueIndex,
): IndicatorCatalogueRow | null {
  if (!slug) return null;
  return index.bySlug.get(slug) ?? null;
}
