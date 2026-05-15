// Pure dispatch from a catalogue artifact to the render kind that
// `TopicLanding.svelte` (and any future topic-style page) should use.
//
// Why this exists as a separate module:
//   - Today the dispatch is a single chart_type === "stacked-trend" branch
//     embedded in TopicLanding's template. Phase 4 introduces a second
//     condition (country-entity dispatch to the StackedTrend "national"
//     variant). Two conditions inline is the smell the Refactoring book
//     calls "Replace Conditional with Polymorphism" — at our scale, a
//     pure dispatch table is sufficient.
//   - Tidy First (Beck): the seam lands in its own commit with a unit test,
//     before any new dispatch case is added. C3 (the behavioural step)
//     extends `RenderKind` without re-touching TopicLanding's branch shape.
//
// What this module is NOT:
//   - Not a generic UI router. The catalogue is small and closed; an enum
//     of render kinds is honest about that.
//   - Not async. Today everything dispatch needs lives on the catalogue
//     artifact. If C3 needs entity_kind, the structural decision is to
//     mirror it onto the catalogue artifact (same pattern chart_type
//     already follows) — keeping dispatch sync.

import type { CatalogueArtifact } from "./catalogue";

/**
 * Closed enumeration of how a topic-page section should render an artifact.
 *
 * - `stacked-trend`: spatial-mode stacked-trend (one entity per row, faceted
 *   by `dimension`) — used today for state × power-source capacity.
 * - `trio`: the default renderer triple (choropleth + ranked + small
 *   multiples) for state-entity scalar series.
 */
export type RenderKind = "stacked-trend" | "trio";

/**
 * Decide which render kind a catalogue artifact maps to.
 *
 * Pure: same inputs always produce the same output. No I/O, no DOM.
 */
export function renderKindForArtifact(artifact: CatalogueArtifact): RenderKind {
  if (artifact.chart_type === "stacked-trend") return "stacked-trend";
  return "trio";
}
