// `feasibleAt()` - pure-function source of truth for the chart-switcher
// picker (plan section 16.3a, 16.2, 21.9; chart-index.md section 2).
//
// Given a data shape + grain context, returns the ordered list of
// `ChartType` values that are encodings-of-honesty-and-feasibility for
// THIS shape. The frontend picker then intersects this list with the
// authored `chart_types[]` from the grapher catalogue; the intersection
// is what the switcher offers, in catalogue order, with
// `chart_types[0]` pre-selected.
//
// Why it is here (not inline):
//   - The chart-drift gate at `chart-index.drift.test.ts` proves the
//     ChartType union <-> chart-index.md section 1 rows <-> THIS
//     function's branches are 1:1, and that `ranked` is in every branch
//     (the guaranteed terminal fallback per plan section 23.5). With
//     `feasibleAt` inline in a route file, that gate could not assert.
//   - The function is referenced by chart-index.md as the contract that
//     the matrix's prose form implements. One pure file, no I/O, easy
//     to test.
//
// Invariants enforced here + asserted by tests:
//   1. The returned array is NEVER empty (guarantee: `ranked` is in
//      every branch). The citizen never sees a blank card.
//   2. When `geometryAvailable === false`, both `choropleth` and
//      `choropleth-symbol` are silently REMOVED before the array is
//      returned (a citizen is never offered a map that cannot draw).
//   3. The ORDER of the returned array is the doctrine-recommended
//      preference order from chart-index.md section 2; the picker
//      preserves it as switcher-segment order when the catalogue's
//      `chart_types[]` is absent.
//
// See also:
//   - docs/reference/chart-index.md (the section-2 matrix this implements)
//   - frontend/src/lib/grapher/catalogue.ts (the ChartType union)
//   - frontend/src/lib/grapher/chart-index.drift.test.ts (the gate)

import type { ChartType } from "./catalogue";

/**
 * Closed enumeration of data shapes after the query. Each shape maps
 * to one branch of the matrix (chart-index.md section 2, one row).
 *
 * Names follow the matrix prose verbatim so a reviewer can grep both
 * directions: doc shape -> shape literal here, and back.
 */
export type DataShape =
  | "one-measure-over-geo-one-slice"
  | "one-measure-over-geo-many-slices"
  | "one-measure-named-series-over-time"
  | "two-measures-joined-per-entity"
  | "one-measure-split-by-facet"
  | "part-to-whole-precise-compare"
  | "magnitude-clusters-shallow-hierarchy"
  | "start-end-pair-per-entity"
  | "one-measure-over-geo-glyph-honest";

/** Grain at which the page is rendering; controls geometry feasibility. */
export type Grain = "country" | "state" | "district" | "sub-district";

/** Input to `feasibleAt()`. Pure data; no DOM, no fetch. */
export interface FeasibleAtInput {
  /** The data shape after the query (one of the 9 matrix rows). */
  dataShape: DataShape;
  /** The page's rendered grain; used by the geometry gate. */
  grain: Grain;
  /**
   * Whether geometry exists at the rendered grain. When false, BOTH
   * `choropleth` and `choropleth-symbol` are removed from the result
   * (a citizen is never offered a map that cannot draw, per plan
   * section 16.2). For `state`/`district` grains this is typically
   * `true`; for `sub-district` it is `false` until village/ward
   * geometry lands.
   */
  geometryAvailable: boolean;
  /** Whether the data carries a `facet` axis (sex, fuel, sector, etc.). */
  hasFacet: boolean;
  /** Whether the data carries a time axis (`time` column present + cardinality >= 2). */
  hasTimeAxis: boolean;
}

/**
 * Map data shape -> feasible encodings, BEFORE the geometry gate. Each
 * row of the inner literal corresponds to one row of chart-index.md
 * section 2. Order matters: it is the doctrine-recommended preference
 * order used when the catalogue's `chart_types[]` is absent.
 *
 * RANKED MUST APPEAR IN EVERY ROW (guaranteed terminal fallback per
 * plan section 23.5; asserted by `feasibleAt.test.ts` and by
 * `chart-index.drift.test.ts`).
 */
const MATRIX_BY_SHAPE: Readonly<Record<DataShape, readonly ChartType[]>> = {
  "one-measure-over-geo-one-slice": ["choropleth", "ranked"] as const,
  "one-measure-over-geo-many-slices": [
    "matrix",
    "line",
    "choropleth",
    "ranked",
  ] as const,
  "one-measure-named-series-over-time": [
    "line",
    "matrix",
    "ranked",
  ] as const,
  "two-measures-joined-per-entity": ["scatter", "ranked"] as const,
  "one-measure-split-by-facet": ["diverging", "ranked"] as const,
  "part-to-whole-precise-compare": [
    "treemap",
    "stacked",
    "ranked",
  ] as const,
  "magnitude-clusters-shallow-hierarchy": [
    "circle-pack",
    "treemap",
    "ranked",
  ] as const,
  "start-end-pair-per-entity": [
    "dumbbell-dot",
    "dumbbell-arrow",
    "ranked",
  ] as const,
  "one-measure-over-geo-glyph-honest": [
    "choropleth-symbol",
    "ranked",
  ] as const,
};

/**
 * Return the ordered list of feasible chart types for the given data
 * shape + grain + geometry context.
 *
 * Guarantees (locked by tests):
 *   - Result is non-empty (`ranked` is in every branch).
 *   - `choropleth` + `choropleth-symbol` are stripped when
 *     `geometryAvailable === false`.
 *   - Order is the doctrine preference order from chart-index.md
 *     section 2.
 *
 * Intentionally ignores `grain`, `hasFacet`, and `hasTimeAxis` in the
 * base mapping - those are encoded in `dataShape` by the caller (the
 * query has already collapsed time + facet into a shape literal). The
 * params are kept on the signature so future shape refinements (e.g.
 * sub-grain feasibility) can be added without changing every call site.
 */
export function feasibleAt(input: FeasibleAtInput): ChartType[] {
  const base = MATRIX_BY_SHAPE[input.dataShape];
  if (input.geometryAvailable) {
    return [...base];
  }
  // Silently remove map encodings when the rendered grain has no geometry.
  return base.filter(
    (t) => t !== "choropleth" && t !== "choropleth-symbol",
  );
}

/**
 * Intersect a feasible list (from `feasibleAt`) with the catalogue's
 * authored `chart_types[]`, preserving catalogue order so the picker
 * shows the citizen-authored sequence rather than the matrix order.
 *
 * When the catalogue list is empty or undefined, the feasible list is
 * returned as-is.
 *
 * When the intersection has exactly ONE member, callers SHOULD render
 * NO switcher (a one-option control is chrome that failed the deletion
 * test, per plan section 16.3a). When the intersection is empty (no
 * authored type is feasible at this grain), callers SHOULD fall back to
 * the feasible list's first member (`ranked` is always present, so this
 * is never a blank card).
 */
export function intersectWithCatalogue(
  feasible: readonly ChartType[],
  cataloguedOrder: readonly ChartType[] | undefined,
): ChartType[] {
  if (!cataloguedOrder || cataloguedOrder.length === 0) {
    return [...feasible];
  }
  const feasibleSet = new Set(feasible);
  return cataloguedOrder.filter((t) => feasibleSet.has(t));
}
