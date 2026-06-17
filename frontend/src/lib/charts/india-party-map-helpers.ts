// Pure helpers for IndiaPartyMap.svelte and the sibling d3-geo
// choropleths. Extracted so vitest can exercise them in node-env
// without mounting the Svelte component (repo vitest doctrine:
// node-env, no jsdom canvas, no @testing-library/svelte mounts).
//
// Two concerns live here:
//   * `resolveStateClickAction` - decides WHICH path a polygon click
//     takes (the component owns the side effect).
//   * `computeIslandMarker` - locates the single far-flung island
//     (Lakshadweep) that collapses to sub-pixel at the national fit so
//     the component can paint a small clickable SQUARE at its centroid.

import { geoCentroid, type GeoPath, type GeoProjection } from "d3-geo";
import type {
  Feature,
  Geometry,
  GeoJsonProperties,
  MultiPolygon,
  Polygon,
  Position,
} from "geojson";

// -----------------------------------------------------------------
// Click-action resolver (PR-4c)
// -----------------------------------------------------------------
//
// IndiaPartyMap's per-feature click handler has two consumers as of
// PR-4c:
//   * Home (`/?theme=election`): no prop -> navigate to state hub
//     (`link.state(code)` -> `/<state>`). Default behaviour, unchanged.
//   * NationalElection (`/t/elections/<event>`): passes
//     `onSelect={(code) => navigate(link.stateElection(code, event))}`
//     so the click stays in the same event cohort
//     (`/<state>/elections/<event>`).
//
// The resolver below decides which path to take WITHOUT calling
// `navigate` itself (so the helpers module stays free of the
// Svelte-only `lib/url` import + side-effecting routing) and WITHOUT
// holding a closure over the prop function (so the test can read the
// decision off the returned discriminated union).
//
// The Svelte component owns the side effects:
//   * `kind === "callback"`     -> invoke the user-supplied callback
//   * `kind === "navigate-default"` -> call `navigate(link.state(code))`
//   * `kind === "noop"`         -> the boundary key has no ECI mapping
//                                  (data not loaded yet OR a stale
//                                  state that fell out of the
//                                  taxonomy)
//
// This split keeps the new prop surface unit-testable in the same
// node-env style as the rest of this module (no @testing-library/
// svelte mount, no jsdom canvas).

/** Discriminated result of resolving a click on a state polygon. */
export type StateClickAction =
  | { kind: "callback"; eciCode: string }
  | { kind: "navigate-default"; eciCode: string }
  | { kind: "noop" };

/**
 * Decide what should happen when the citizen clicks the polygon
 * with boundary-join key `key`.
 *
 * @param key                 The string-coerced join-key value the
 *                            click handler received (e.g. `"33"` for
 *                            Tamil Nadu's `State_LGD`).
 * @param keyToEci            Reverse lookup populated by the component
 *                            from the states taxonomy
 *                            (`boundary_join_key` -> `eci_code`).
 * @param hasCustomCallback   True when the consumer supplied an
 *                            `onSelect` prop. The component passes
 *                            this so the helper does not need to hold
 *                            a closure over the function reference.
 */
export function resolveStateClickAction(
  key: string,
  keyToEci: Record<string, string>,
  hasCustomCallback: boolean,
): StateClickAction {
  const code = keyToEci[key];
  if (!code) return { kind: "noop" };
  if (hasCustomCallback) return { kind: "callback", eciCode: code };
  return { kind: "navigate-default", eciCode: code };
}

// -----------------------------------------------------------------
// Island marker (Lakshadweep visibility)
// -----------------------------------------------------------------
//
// Lakshadweep is ~32 km^2 of land in the Arabian Sea, ~300 km off the
// mainland. At any honest national Mercator fit it projects to a ~2-3 px
// dot - below the threshold a citizen can see or tap. fitWidth alone
// cannot fix this (the island stays sub-pixel at every viewport width),
// so the national maps paint a small SQUARE at its centroid carrying the
// SAME fill + click + hover as the polygon. The marker is scoped BY NAME
// to the one far-flung island so mainland small areas (Delhi, Chandigarh)
// are never marked - they stay reachable by the zoom affordance.

/** Max projected dimension (px, national fit) below which the named
 *  island needs a square marker. Lakshadweep sits ~2-3 px; mainland
 *  states sit well above this, so the name scope is the real guard and
 *  this only suppresses the marker when the map is already zoomed onto
 *  the island (e.g. its own state page). */
export const ISLAND_MARKER_THRESHOLD_PX = 12;

/** One island-marker descriptor: the join-key value + projected centroid
 *  in the SAME viewBox units the polygons render into (painted inside the
 *  zoom group so it tracks the island on pan / zoom). */
export interface IslandMarker {
  /** Join-key value (string-coerced) the fill / click / hover read. */
  key: string;
  /** Projected centroid x in the map's viewBox. */
  cx: number;
  /** Projected centroid y in the map's viewBox. */
  cy: number;
}

/**
 * Largest projected span (px) of any SINGLE island polygon in `f`.
 *
 * For a scattered archipelago (Lakshadweep is a MultiPolygon of 4 islands
 * spread over ~280 km of sea) the whole-feature bounding box is dominated
 * by the empty water between islands - ~82 px tall at national fit - while
 * each island is ~1 px. Measuring the bbox makes `computeIslandMarker`
 * wrongly read the feature as "big enough to click directly" and suppress
 * the marker. Measuring the largest individual island (each `Polygon` of a
 * `MultiPolygon`, or the single `Polygon`) gives the size the citizen can
 * actually see and tap.
 *
 * For a single-polygon island this equals the whole-feature bbox span (no
 * behaviour change). On the island's own zoomed page every island is large,
 * so the marker is still correctly suppressed. Non-polygon geometries fall
 * back to the whole-feature bbox span.
 */
function largestIslandSpanPx(
  f: Feature<Geometry, GeoJsonProperties>,
  path: GeoPath,
): number {
  const geom = f.geometry;
  if (geom.type !== "Polygon" && geom.type !== "MultiPolygon") {
    const b = path.bounds(f);
    const span = Math.max(b[1][0] - b[0][0], b[1][1] - b[0][1]);
    return Number.isFinite(span) ? span : 0;
  }
  const polygons: Position[][][] =
    geom.type === "MultiPolygon"
      ? (geom as MultiPolygon).coordinates
      : [(geom as Polygon).coordinates];
  let max_span = 0;
  for (const rings of polygons) {
    const single: Feature<Polygon, GeoJsonProperties> = {
      type: "Feature",
      properties: {},
      geometry: { type: "Polygon", coordinates: rings },
    };
    let b: ReturnType<GeoPath["bounds"]>;
    try {
      b = path.bounds(single);
    } catch {
      continue;
    }
    const span = Math.max(b[1][0] - b[0][0], b[1][1] - b[0][1]);
    if (Number.isFinite(span) && span > max_span) max_span = span;
  }
  return max_span;
}

/**
 * Locate the single named far-flung island (Lakshadweep) and return a
 * square-marker descriptor for it, or null when it is absent, already
 * large enough to click directly (map zoomed onto it), or not
 * projectable. Scoped by `name_pattern` so ONLY that island is marked.
 *
 * @param features      Feature list (typically `collection.features`).
 * @param projection    The projection driving `path`.
 * @param path          The geoPath built on `projection`.
 * @param feature_key   Extractor for the join-key value (fill / click).
 * @param feature_name  Extractor for the human name matched against
 *                      `name_pattern` (e.g. `STNAME` / `ls_seat_name`).
 * @param name_pattern  Case-insensitive matcher selecting the island.
 * @param threshold_px  Suppress the marker when the largest single island's
 *                      projected span is at or above this (the island fills
 *                      the viewport).
 */
export function computeIslandMarker<P extends GeoJsonProperties>(
  features: readonly Feature<Geometry, P>[],
  projection: GeoProjection,
  path: GeoPath,
  feature_key: (f: Feature<Geometry, P>) => string | number | null | undefined,
  feature_name: (f: Feature<Geometry, P>) => string | null | undefined,
  name_pattern: RegExp,
  threshold_px: number = ISLAND_MARKER_THRESHOLD_PX,
): IslandMarker | null {
  for (const f of features) {
    const name = feature_name(f);
    if (!name || !name_pattern.test(name)) continue;
    const key = feature_key(f);
    if (key == null) continue;
    let b: ReturnType<GeoPath["bounds"]>;
    try {
      b = path.bounds(f as Feature<Geometry, GeoJsonProperties>);
    } catch {
      continue;
    }
    if (
      !Number.isFinite(b[0][0]) ||
      !Number.isFinite(b[0][1]) ||
      !Number.isFinite(b[1][0]) ||
      !Number.isFinite(b[1][1])
    ) {
      continue;
    }
    const span = largestIslandSpanPx(
      f as Feature<Geometry, GeoJsonProperties>,
      path,
    );
    if (span >= threshold_px) continue; // largest island big enough to click directly
    const [lng, lat] = geoCentroid(f as Feature<Geometry, GeoJsonProperties>);
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) continue;
    const projected = projection([lng, lat]);
    if (
      !projected ||
      !Number.isFinite(projected[0]) ||
      !Number.isFinite(projected[1])
    ) {
      continue;
    }
    return { key: String(key), cx: projected[0], cy: projected[1] };
  }
  return null;
}

// -----------------------------------------------------------------
// No-data detection (no-data dot-grid + "No data" chip)
// -----------------------------------------------------------------
//
// The national party map paints every state that has a loaded winner
// with its leading-party colour; states with no loaded winner (e.g.
// Jammu & Kashmir, Ladakh) fall through to the no-data dot-grid fill -
// the same idiom the welfare choropleth (GeoChoropleth) uses, so the
// two home themes (Winning party / welfare indicator) show "no data"
// the same way. The "No data" legend chip is gated on this predicate so
// a fully-covered cohort stays chip-free.

/**
 * True when at least one rendered feature has no entry in `fills` - i.e.
 * the map paints at least one state with the no-data dot-grid. A feature
 * whose join-key value is null/undefined also counts (no key -> no
 * possible fill match), mirroring the component's
 * `key ? fillForKey(key) : NO_DATA_FILL` branch.
 *
 * Pure so vitest can exercise it in node-env without mounting the Svelte
 * component (same doctrine as the other helpers in this module).
 *
 * @param features      Feature list (typically `collection.features`).
 * @param fills         Join-key -> colour map the component derived from
 *                      the loader; a key absent from this map paints the
 *                      no-data dot-grid.
 * @param feature_key   Extractor for the join-key value (the same one the
 *                      fill / click / hover handlers use).
 */
export function hasNoDataFeature<P extends GeoJsonProperties>(
  features: readonly Feature<Geometry, P>[],
  fills: Record<string, string>,
  feature_key: (f: Feature<Geometry, P>) => string | number | null | undefined,
): boolean {
  for (const f of features) {
    const raw = feature_key(f);
    const key = raw == null ? null : String(raw);
    if (key == null || fills[key] == null) return true;
  }
  return false;
}
