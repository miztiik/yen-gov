// CompositionBar — view-model contract.
//
// Per `TODO/20260518-frontend-charting-modernisation-plan.md` Phase 3.6
// — single-entity, single-period horizontal 100%-stacked bar. Generic;
// NOT election-specific. Domain bindings (party seats, fuel mix, age
// bands, …) live in adapters; the renderer takes a typed view-model.
//
// Doctrine ties:
//
//   - R-08 Branch by Abstraction. v1 of the renderer ships ALONGSIDE
//     SeatDonut / ParliamentArc / AcStackedBar. Per-route mounts
//     happen in dedicated PRs (Phase 3.6 (c) mount lane).
//
//   - R-16 Three-PR split. (a) renderer (this PR) → (b) adapter +
//     experiment definition → (c) mount + Playwright. Each ships
//     independently reviewable.
//
//   - R-24 / R-28. The footer slot delegates to SourceListV2 via
//     ChartShell; no fetch telemetry, no parquet path literal.
//
//   - "Tail handling: when the upstream adapter emits an `others`
//     segment, it renders as a visible swatch in the bar with its own
//     label; the renderer never collapses tail to a footnote." — plan
//     line 1310. The model carries the `others` segment as one row
//     among the segments array.
//
//   - "Fill: segment fills are passed in by the adapter; renderer
//     never knows about parties, power sources, or age bands." —
//     plan line 1311. Therefore `fill` is required on every segment;
//     resolution belongs to the adapter (which calls `categoryColour`
//     or `partyColour`).
//
//   - "Forbidden: do NOT add a `variant: "donut" | "pie" | "sunburst"`
//     prop. The whole point of this renderer is that it is NOT a
//     radial composition chart." — plan line 1313. No variant prop
//     here; the only knob is segment data.

import { z } from "zod";

/**
 * One bar segment. The adapter resolves the `fill` (typically via
 * `categoryColour` / `partyColour`) and decides whether this segment
 * is the tail aggregate (`is_tail: true` for an `others`-style row).
 * The renderer treats every segment the same way visually — the
 * tail is just one more swatch with its own label.
 *
 * `swatch_role` is an adapter-supplied semantic tag (e.g. `"party"`,
 * `"nota"`, `"others"`, `"fuel-type"`) the renderer surfaces via
 * `data-swatch-role` on the segment rect so Playwright (and curators
 * inspecting the DOM) can identify a segment without parsing labels.
 */
export const CompositionBarSegment = z.object({
  /** Stable code: party_eci_code, fuel_type_id, age_band_id, … */
  id: z.string().min(1),
  /** Citizen-readable display label. Adapter localises. */
  label: z.string().min(1),
  /** The raw value the segment contributes. Non-negative. Zero is
   *  allowed (renderer omits zero-width swatches). */
  value: z.number().nonnegative(),
  /** Adapter-resolved hex colour. Required so the renderer never
   *  reaches into the colour subsystem. */
  fill: z.string().regex(/^#[0-9a-f]{6}$/i),
  /** Adapter-supplied semantic role. Exposed as `data-swatch-role` on
   *  the rect — Playwright uses it to identify segments. */
  swatch_role: z.string().min(1),
  /** True iff this segment is the tail aggregate (e.g. an `others`
   *  row that rolls up the long tail of small-share segments). The
   *  renderer treats it the same as any other segment; the flag is
   *  carried for downstream tooling (legend grouping, summary copy)
   *  not for visual styling. */
  is_tail: z.boolean().default(false),
});

/**
 * Inline honesty disclosure carried at the chart-shell level. Mirrors
 * `ChartShellHonestyBanner` so the adapter can build it once and
 * propagate to the shell via `<CompositionBar>` → `<ChartShell>`.
 */
export const CompositionBarHonestyBanner = z.object({
  kind: z.enum([
    "comparability",
    "series_break",
    "unit_change",
    "vintage",
    "missing_data",
    "note",
  ]),
  text: z.string().min(1),
});

/**
 * Root view-model. The adapter emits one of these per chart render;
 * the renderer never aggregates, sorts, or computes percentages from
 * raw rows.
 *
 *   - `label`       — entity + period heading (e.g. "Gujarat — 2022
 *                     Assembly").
 *   - `subtitle`    — optional one-liner (e.g. "All 182 seats; FPTP
 *                     winners only").
 *   - `total_value` — denominator the renderer shows in the centre /
 *                     header (e.g. 182 seats).
 *   - `total_unit`  — citizen-readable unit (e.g. "seats", "MW", "%").
 *   - `segments`    — ordered list. Adapter decides sort policy and
 *                     tail placement (typically biggest first, tail
 *                     last).
 *   - `honesty_banners` — propagated to ChartShell.
 *   - `dimension`   — adapter-supplied dimension id ("party",
 *                     "fuel_type", …) exposed as `data-dimension` for
 *                     downstream selectors / tests.
 *   - `caption_fptp` — optional FPTP framing footnote (elections
 *                     adapter only; per plan line 1320 the elections
 *                     adapter reuses the StackedTrend wording).
 */
export const CompositionBarModel = z.object({
  schema_version: z.literal("1.0"),
  label: z.string().min(1),
  subtitle: z.string().nullable().default(null),
  total_value: z.number().positive(),
  total_unit: z.string().min(1),
  segments: z.array(CompositionBarSegment).min(1),
  honesty_banners: z.array(CompositionBarHonestyBanner).default([]),
  dimension: z.string().min(1),
  caption_fptp: z.string().nullable().default(null),
});

export type CompositionBarSegment = z.infer<typeof CompositionBarSegment>;
export type CompositionBarHonestyBanner = z.infer<
  typeof CompositionBarHonestyBanner
>;
export type CompositionBarModel = z.infer<typeof CompositionBarModel>;
