// StackedTrendV2 — zod model + types (structural only; zero render).
//
// Per docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md Phase 2.1a
// (R-09 split). This file ships ONLY the v2 contract: types + zod model +
// fixture. Behavioural change starts at Phase 2.3.
//
// Branch by Abstraction (R-08): v2 ships ALONGSIDE
// `frontend/src/lib/charts/stacked-trend/types.ts`. The v1 file is NOT
// modified, NOT deprecated, NOT removed. Caller migration is one PR per
// caller (≤3 callers per PR with their own Playwright assertion). v1 is
// deleted in a single final PR after the last caller migrates.
//
// What changes between v1 and v2:
//
//   1. `StackedTrendSource` (v1) carried `url` + `fetched_at` - both
//      retired by ADR-0032 v2.0. v2's `StackedTrendV2Source` post the
//      sources-simplification PR-1 (2026-06-11) carries the deduped
//      publisher pill shape (`label, vintage_summary, url, count`) from
//      `frontend/src/lib/sources/types.ts`. Adapter-time denormalisation
//      keeps the renderer DuckDB-free (joins + dedupeToPills happen in
//      the view-model, not the renderer).
//
//   2. Every other shape (`StackedTrendCategory`, `StackedTrendSegment`,
//      `StackedTrendBar`, `StackedTrendHonesty`, `StackedTrendHeadline`)
//      keeps v1 semantics verbatim — Phase 2 is a polish pass, not a
//      ground-up rewrite. Behavioural changes (segmented mode control,
//      pinned readout, inline labels, missing-hatch, motion, export)
//      live in subsequent commits per the Track-D D1–D9 sequence
//      (Section "Track D" of the plan).

import { z } from "zod";

// ---------- shared with v1 (verbatim semantics) ----------

export const StackedTrendV2Category = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  fill: z.string().regex(/^#[0-9a-f]{6}$/i).optional(),
  order: z.number().optional(),
});

export const StackedTrendV2Segment = z.object({
  category_id: z.string().min(1),
  value: z.number().nullable(),
  availability: z
    .enum(["present", "missing", "not_applicable"])
    .default("present"),
  availability_label: z.string().optional(),
  /**
   * PR-B5 swing signal: this category's change versus the SAME category in
   * the chronologically-previous bar (current.value − previous.value), in the
   * model's native unit (seats for `count`, share-fraction for `share`).
   * `null` when either endpoint is missing or this is the first bar. Computed
   * once in the migrate shim (`stackedTrendModelToV2`) so the renderer stays
   * pure. Optional so v2 fixtures and other adapters need not supply it.
   */
  delta: z.number().nullable().optional(),
});

export const StackedTrendV2Bar = z.object({
  period_id: z.string().min(1),
  period_label: z.string().min(1),
  order: z.number(),
  kind: z.string().optional(),
  segments: z.array(StackedTrendV2Segment),
  total: z.number().optional(),
});

export const StackedTrendV2SeriesBreak = z.object({
  at_period_id: z.string(),
  kind: z.string(),
  note: z.string(),
});

export const StackedTrendV2UnitChange = z.object({
  at_period_id: z.string(),
  from_unit: z.string(),
  to_unit: z.string(),
  note: z.string(),
});

export const StackedTrendV2Honesty = z
  .object({
    comparability: z
      .enum([
        // v1.5 4-level ladder (preferred - see frontend/src/lib/indicators.ts).
        "comparable_across_states_and_time",
        "comparable_across_states_snapshot_only",
        "comparable_within_state_over_time",
        "directional_only",
        // v1.0-v1.4 deprecated tokens (kept for back-compat).
        "comparable_across_states",
        "comparable_with_normalisation",
        "not_comparable_across_states",
      ])
      .optional(),
    attribution_geography: z
      .enum([
        "where_produced",
        "where_allocated",
        "where_consumed",
        "where_billed",
        "where_resident",
        "where_administered",
      ])
      .optional(),
    methodology_vintage: z.string().optional(),
    series_breaks: z.array(StackedTrendV2SeriesBreak).optional(),
    unit_changed_at: z.array(StackedTrendV2UnitChange).optional(),
    notes: z.string().optional(),
  })
  .optional();

export const StackedTrendV2Headline = z
  .object({
    rule: z.enum([
      "max_latest_with_streak",
      "designated",
      "max_lifetime",
      "none",
    ]),
    text: z.string(),
    so_what: z.string().optional(),
    highlight_category_id: z.string().optional(),
  })
  .optional();

// ---------- v2-only - publisher pills (5-col SourceRow -> dedupeToPills, 2026-06-11) ----------

/**
 * Adapter-denormalised publisher pill carried inline on every
 * StackedTrendV2 model. Shape mirrors the canonical `PublisherPill`
 * contract from `frontend/src/lib/sources/types.ts` post the
 * sources-simplification PR-1 (2026-06-11) - one pill per
 * (producer x series_family). Adapters resolve the rows from
 * `taxonomy.sources` (manifest-registered, R-28), dedupe via
 * `dedupeToPills`, and copy the deduped pills onto the model so the
 * renderer never touches DuckDB.
 *
 * What changed at the 2026-06-11 rip: the v2.0 ledger's 11-col
 * adapter-denormalised row (`license`, `confidence_tier`,
 * `is_issuing_authority`, `verification_method`, `citation_full`,
 * `notes`, `url_main`, plus identity triple + source_id) was retired
 * per inline ADR `citation-ledger-5col` in docs/concepts/data-provenance.md.
 * The renderer's export footer composes the citation line from
 * `label + vintage_summary` (one pill per producer x series_family).
 */
export const StackedTrendV2Source = z.object({
  label: z.string().min(1),
  vintage_summary: z.string(),
  url: z.string().nullable(),
  count: z.number().int().positive(),
});

// ---------- v2 model (root) ----------

export const StackedTrendV2Model = z.object({
  schema_version: z.literal("2.0"),
  unit: z.object({
    id: z.string(),
    label: z.string(),
    value_kind: z.enum(["count", "currency", "rate", "share", "raw"]),
  }),
  x_axis_label: z.string(),
  bar_sort: z
    .enum([
      "by_order_ascending",
      "by_total_descending",
      "by_pinned_then_order",
    ])
    .default("by_order_ascending"),
  categories: z.array(StackedTrendV2Category).min(1),
  bars: z.array(StackedTrendV2Bar).min(1),
  headline: StackedTrendV2Headline,
  honesty: StackedTrendV2Honesty,
  /** Citation-ledger publisher pills (post 2026-06-11). One pill per
   *  (producer x series_family) via `dedupeToPills` from $lib/sources. */
  sources: z.array(StackedTrendV2Source),
  dimension: z.string().min(1),
  default_mode: z.enum(["percent", "absolute"]).default("percent"),
});

export type StackedTrendV2Category = z.infer<typeof StackedTrendV2Category>;
export type StackedTrendV2Segment = z.infer<typeof StackedTrendV2Segment>;
export type StackedTrendV2Bar = z.infer<typeof StackedTrendV2Bar>;
export type StackedTrendV2Honesty = z.infer<typeof StackedTrendV2Honesty>;
export type StackedTrendV2Headline = z.infer<typeof StackedTrendV2Headline>;
export type StackedTrendV2Source = z.infer<typeof StackedTrendV2Source>;
export type StackedTrendV2Model = z.infer<typeof StackedTrendV2Model>;

export const OTHER_CATEGORY_ID_V2 = "__OTHER__";
export const OTHER_CATEGORY_FILL_V2 = "#9ca3af";
