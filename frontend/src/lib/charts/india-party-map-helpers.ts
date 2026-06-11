// Pure helpers for IndiaPartyMap.svelte's sub-threshold marker
// overlay (PR-4 of TODO/20260611-elections-off-maplibre-and-map-ux-
// plan.md). Extracted so vitest can exercise them against the real
// states/all.topojson without mounting the Svelte component (repo
// vitest doctrine: node-env, no jsdom canvas, no @testing-library/
// svelte mounts).
//
// The svelte component (sibling) reads `SUB_THRESHOLD_PX` +
// `computeSubThresholdMarkers` to drive the second-pass <circle> render
// that gives the citizen a clickable target for states whose polygon
// collapses to sub-pixel at the national-fit Mercator projection.
//
// Lakshadweep is the named priority (4 atolls totalling ~32 km^2 of
// land on a 3300 km tall country); at the chosen 640x480 viewBox its
// path bounds are ~0.14 x 0.15 px. The 14 px threshold is calibrated
// to catch Lakshadweep + Chandigarh + Delhi + Goa from
// `datasets/boundaries/in/states/all.topojson` without flagging any
// mainland state. See PR-4 plan-doc row for the full rationale.

import { geoCentroid, type GeoPath, type GeoProjection } from "d3-geo";
import type { Feature, Geometry, GeoJsonProperties } from "geojson";

/**
 * Max-dimension threshold (in projected px) below which a state's
 * polygon needs a `<circle>` marker to remain citizen-clickable.
 * Calibrated against the 640x480 national-fit Mercator projection.
 */
export const SUB_THRESHOLD_PX = 14;

/** One sub-threshold marker descriptor (key + projected centroid). */
export interface MarkerOverlay {
  /** Join-key value (string-coerced) used by fills/tooltips/click handler. */
  key: string;
  /** Projected x in the same viewBox the polygon paths render into. */
  cx: number;
  /** Projected y in the same viewBox the polygon paths render into. */
  cy: number;
}

/** Width + height in projected px of a feature's path bounds. Null
 *  when bounds are non-finite (collapsed projection, empty geometry)
 *  OR when d3-geo's `path.bounds(...)` throws synchronously on a
 *  malformed ring (PR-5 hit this on per-state AC GeoJSONs for TN /
 *  Maharashtra / WB / Puducherry where a small subset of features
 *  have an empty `ring[0]`; the safer surface is to skip the marker
 *  rather than crash the whole reactive flush). */
export function pathSpan(
  feature: Feature<Geometry, GeoJsonProperties>,
  path: GeoPath,
): { width: number; height: number } | null {
  let b: ReturnType<GeoPath["bounds"]>;
  try {
    b = path.bounds(feature);
  } catch {
    return null;
  }
  if (
    !Number.isFinite(b[0][0]) ||
    !Number.isFinite(b[0][1]) ||
    !Number.isFinite(b[1][0]) ||
    !Number.isFinite(b[1][1])
  ) {
    return null;
  }
  return { width: b[1][0] - b[0][0], height: b[1][1] - b[0][1] };
}

/** True when the longer side of `span` is shorter than `threshold_px`. */
export function isSubThreshold(
  span: { width: number; height: number },
  threshold_px: number = SUB_THRESHOLD_PX,
): boolean {
  return Math.max(span.width, span.height) < threshold_px;
}

/** Project a feature's geographic centroid through `projection`. Null
 *  when the centroid or its projection is non-finite. */
export function projectedCentroid(
  feature: Feature<Geometry, GeoJsonProperties>,
  projection: GeoProjection,
): [number, number] | null {
  const [lng, lat] = geoCentroid(feature);
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return null;
  const projected = projection([lng, lat]);
  if (!projected) return null;
  if (!Number.isFinite(projected[0]) || !Number.isFinite(projected[1])) {
    return null;
  }
  return [projected[0], projected[1]];
}

/**
 * Compute the list of sub-threshold marker overlays for a feature
 * collection. Iterates every feature, runs the path-bounds + centroid
 * pipeline, and emits one MarkerOverlay per sub-threshold feature that
 * has a non-null join key and a projectable centroid. Skips features
 * the projection cannot represent (no error, no marker).
 *
 * @param features        Feature list (typically `collection.features`).
 * @param projection      The projection that drives `path`.
 * @param path            The geoPath built on `projection`.
 * @param feature_key     Extractor for the join-key value used by fills /
 *                        tooltips / click handler. Return null/undefined
 *                        to skip the feature.
 * @param threshold_px    Override the default 14 px threshold for tests.
 */
export function computeSubThresholdMarkers<P extends GeoJsonProperties>(
  features: readonly Feature<Geometry, P>[],
  projection: GeoProjection,
  path: GeoPath,
  feature_key: (f: Feature<Geometry, P>) => string | number | null | undefined,
  threshold_px: number = SUB_THRESHOLD_PX,
): MarkerOverlay[] {
  const out: MarkerOverlay[] = [];
  for (const f of features) {
    const key = feature_key(f);
    if (key == null) continue;
    const span = pathSpan(f as Feature<Geometry, GeoJsonProperties>, path);
    if (!span) continue;
    if (!isSubThreshold(span, threshold_px)) continue;
    const c = projectedCentroid(
      f as Feature<Geometry, GeoJsonProperties>,
      projection,
    );
    if (!c) continue;
    out.push({ key: String(key), cx: c[0], cy: c[1] });
  }
  return out;
}

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

/** Discriminated result of resolving a click on a state polygon /
 *  sub-threshold marker. */
export type StateClickAction =
  | { kind: "callback"; eciCode: string }
  | { kind: "navigate-default"; eciCode: string }
  | { kind: "noop" };

/**
 * Decide what should happen when the citizen clicks the polygon /
 * marker with boundary-join key `key`.
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
