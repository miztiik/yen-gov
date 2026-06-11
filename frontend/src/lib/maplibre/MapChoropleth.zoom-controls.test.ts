// Pure-helper tests for MapChoropleth's +/-/home zoom-control overlay.
//
// Per the repo vitest doctrine (node-env, no jsdom canvas, no
// @testing-library/svelte mounts - Skeleton + IndicatorJump + tap-to-pin
// + map-highlight-utils precedent), the rendered overlay shape (three
// circular buttons, aria-labels, Tailwind classes, position over the
// map container) is covered by the CLAUDE.md section 13 browser smoke
// captured in this PR's body. This file covers every dispatch branch
// of the three click-handler helpers against a stub map.
//
// No mocking of `maplibre-gl` is needed - the helpers operate on a
// narrow `ZoomableMap` surface that names only the three methods we
// touch, so vi.fn() suffices.
//
// PR-1 of TODO/20260611-elections-off-maplibre-and-map-ux-plan.md.

import { describe, expect, it, vi } from "vitest";

import {
  homeViewOnMap,
  type ZoomableMap,
  zoomInOnMap,
  zoomOutOnMap,
} from "./zoom-controls";

function stubMap(): ZoomableMap & {
  zoomIn: ReturnType<typeof vi.fn>;
  zoomOut: ReturnType<typeof vi.fn>;
  flyTo: ReturnType<typeof vi.fn>;
} {
  return {
    zoomIn: vi.fn(),
    zoomOut: vi.fn(),
    flyTo: vi.fn(),
  };
}

describe("zoomInOnMap", () => {
  it("invokes map.zoomIn exactly once", () => {
    const map = stubMap();
    zoomInOnMap(map);
    expect(map.zoomIn).toHaveBeenCalledTimes(1);
    expect(map.zoomOut).not.toHaveBeenCalled();
    expect(map.flyTo).not.toHaveBeenCalled();
  });

  it("is a no-op when map is null", () => {
    expect(() => zoomInOnMap(null)).not.toThrow();
  });

  it("is a no-op when map is undefined", () => {
    expect(() => zoomInOnMap(undefined)).not.toThrow();
  });
});

describe("zoomOutOnMap", () => {
  it("invokes map.zoomOut exactly once", () => {
    const map = stubMap();
    zoomOutOnMap(map);
    expect(map.zoomOut).toHaveBeenCalledTimes(1);
    expect(map.zoomIn).not.toHaveBeenCalled();
    expect(map.flyTo).not.toHaveBeenCalled();
  });

  it("is a no-op when map is null", () => {
    expect(() => zoomOutOnMap(null)).not.toThrow();
  });

  it("is a no-op when map is undefined", () => {
    expect(() => zoomOutOnMap(undefined)).not.toThrow();
  });
});

describe("homeViewOnMap", () => {
  it("calls map.flyTo with the captured centre + zoom + 400ms duration", () => {
    const map = stubMap();
    homeViewOnMap(map, [80, 22], 4.25);
    expect(map.flyTo).toHaveBeenCalledTimes(1);
    expect(map.flyTo).toHaveBeenCalledWith({
      center: [80, 22],
      zoom: 4.25,
      duration: 400,
    });
    expect(map.zoomIn).not.toHaveBeenCalled();
    expect(map.zoomOut).not.toHaveBeenCalled();
  });

  it("is a no-op when map is null (regardless of captured state)", () => {
    expect(() => homeViewOnMap(null, [80, 22], 4)).not.toThrow();
  });

  it("is a no-op when initial_center is null (idle has not fired yet)", () => {
    const map = stubMap();
    homeViewOnMap(map, null, 4);
    expect(map.flyTo).not.toHaveBeenCalled();
  });

  it("is a no-op when initial_zoom is null (idle has not fired yet)", () => {
    const map = stubMap();
    homeViewOnMap(map, [80, 22], null);
    expect(map.flyTo).not.toHaveBeenCalled();
  });

  it("preserves a zoom value of 0 (falsy but valid)", () => {
    // Guard against `if (!initial_zoom)` regressions - zoom 0 is a
    // legitimate maplibre zoom value (world-view) and must NOT be
    // treated as "not captured yet". The helper's null check uses
    // `=== null` for exactly this reason.
    const map = stubMap();
    homeViewOnMap(map, [0, 0], 0);
    expect(map.flyTo).toHaveBeenCalledTimes(1);
    expect(map.flyTo).toHaveBeenCalledWith({
      center: [0, 0],
      zoom: 0,
      duration: 400,
    });
  });
});
