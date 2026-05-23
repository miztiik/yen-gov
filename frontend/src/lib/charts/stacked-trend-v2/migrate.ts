// StackedTrend v1 → v2 migration adapter (Track-D D10 shim).
//
// Phase 2 of TODO/20260518-frontend-charting-modernisation-plan.md is
// shipping the v2 component (StackedTrendV2.svelte) alongside v1
// (StackedTrend.svelte) under R-08 Branch by Abstraction. The Track-D
// D10..D13 sequence migrates callers one at a time.
//
// This adapter is the **per-caller bridge**: it takes a v1
// StackedTrendModel + a separately-resolved SourceV2Row[] from the
// view-model (which now JOINs taxonomy.sources directly) and returns a
// fully-typed StackedTrendV2Model the v2 renderer can consume.
//
// Why the v1 model's own `sources` are dropped on the floor:
//
//   v1 StackedTrendSource = { url, fetched_at }
//
// is the retired v1.0 contract. ADR-0032 P.0e removed both fields from
// the citation ledger; they live in `.runtime/<adapter>/<source_id>.json`
// sidecars now. The v1 fields cannot be losslessly upgraded — `url` may
// or may not equal `url_main` and `fetched_at` is forbidden in citizen
// chrome (R-24). The right place to source the v2 ledger row is the
// view-model query that already JOINs `taxonomy.sources` by `source_id`
// — adapter consumers pass that row[] directly to this function.
//
// Everything else in the v1 model maps **verbatim** to v2 (Phase 2 is
// polish, not a rewrite — the categories / bars / honesty / headline /
// unit / dimension / default_mode all carry the same semantics).

import type { StackedTrendModel } from "../stacked-trend/types";
import type { StackedTrendV2Model, StackedTrendV2Source } from "./types";

/**
 * Bridge a v1 StackedTrendModel into a v2 StackedTrendV2Model.
 *
 * @param model      v1 model emitted by an existing adapter
 *                   (electionsToStackedTrend, indicatorToStackedTrend, …).
 * @param sourcesV2  v2.0 ledger rows resolved by the view-model from
 *                   `taxonomy.sources`. MUST already be the v2.0 shape
 *                   (11 fields; no `fetched_at`, no `url`). The view-model
 *                   is the only place that knows the data-source `source_id`s
 *                   the adapter aggregated over.
 *
 * @returns A StackedTrendV2Model with `schema_version: "2.0"` stamped on
 *          and the v1 `sources` replaced by the v2 ledger rows. Every
 *          other field is reference-copied — the v1 model is not mutated.
 *
 * Pure / sync / zero side-effects. Safe to call inside `$derived.by()`.
 */
export function stackedTrendModelToV2(
  model: StackedTrendModel,
  sourcesV2: readonly StackedTrendV2Source[],
): StackedTrendV2Model {
  return {
    schema_version: "2.0",
    unit: model.unit,
    x_axis_label: model.x_axis_label,
    bar_sort: model.bar_sort,
    categories: model.categories,
    bars: model.bars,
    headline: model.headline,
    honesty: model.honesty,
    sources: [...sourcesV2],
    dimension: model.dimension,
    default_mode: model.default_mode,
  };
}
