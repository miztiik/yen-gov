// Pure helpers for the MapChoropleth +/-/home zoom-control overlay.
//
// Extracted so vitest can exercise the three click-handler dispatches
// against a stub map without mounting the Svelte component (repo
// vitest doctrine: node-env, no jsdom canvas, no @testing-library/
// svelte mounts - Skeleton + IndicatorJump + tap-to-pin precedent).
// The rendered overlay shape (3 circular buttons, aria-labels, Tailwind
// positioning) is covered by the CLAUDE.md section 13 browser smoke
// captured in this PR's body.
//
// Helpers are typed loosely (the `ZoomableMap` surface only names the
// three methods we touch) to match the MapChoropleth instance-script
// convention - the underlying maplibre-gl types do not need to leak
// into every consumer or test file.
//
// PR-1 of TODO/20260611-elections-off-maplibre-and-map-ux-plan.md
// (Jony + Citizen authority; interim citizen-experience fix while
// PR-4 / PR-5 ship the structural d3-geo migration).

/**
 * Minimal map surface the +/-/home overlay touches. Mirrors the
 * three maplibre-gl `Map` methods we dispatch to - kept narrow so
 * tests can pass a `vi.fn()` triple without reconstructing the whole
 * maplibre type hierarchy.
 */
export interface ZoomableMap {
  zoomIn: () => void;
  zoomOut: () => void;
  flyTo: (opts: {
    center: [number, number];
    zoom: number;
    duration?: number;
  }) => void;
}

/** Step the map up by one maplibre zoom step. No-op if no map yet. */
export function zoomInOnMap(map: ZoomableMap | null | undefined): void {
  if (!map) return;
  map.zoomIn();
}

/** Step the map down by one maplibre zoom step. No-op if no map yet. */
export function zoomOutOnMap(map: ZoomableMap | null | undefined): void {
  if (!map) return;
  map.zoomOut();
}

/**
 * Fly the map back to the centre + zoom captured on the first `idle`
 * event after mount (the post-fit-to-data framing the citizen first
 * saw). 400ms flyTo matches the IndiaVotes / Bharat Pashudhan parity
 * the row spec asked for. No-op when either captured value is null -
 * the initial idle has not fired yet (e.g. user clicked Reset during
 * the cold-boot frame before the GeoJSON resolved).
 */
export function homeViewOnMap(
  map: ZoomableMap | null | undefined,
  initial_center: [number, number] | null,
  initial_zoom: number | null,
): void {
  if (!map) return;
  if (!initial_center || initial_zoom === null) return;
  map.flyTo({
    center: initial_center,
    zoom: initial_zoom,
    duration: 400,
  });
}
