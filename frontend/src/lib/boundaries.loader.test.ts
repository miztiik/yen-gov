// Loader unit tests for the topojson-first / geojson-fallback contract
// (docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md P2.3). Mocks
// `fetch` per the CLAUDE.md Holy Law #7 loader-test carve-out so we can
// exercise topo-OK, topo-404, topo-parse-error, and topo-decode-error
// branches deterministically without touching the on-disk corpus.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { loadBoundaryFromPath, loadBoundaryData, boundaryRelPaths } from "./boundaries";

// Three-feature tiny GeoJSON used as the fallback payload.
const TINY_GEOJSON = {
  type: "FeatureCollection",
  features: [
    { type: "Feature", properties: { State_LGD: 33 }, geometry: { type: "Point", coordinates: [0, 0] } },
    { type: "Feature", properties: { State_LGD: 7 }, geometry: { type: "Point", coordinates: [1, 1] } },
    { type: "Feature", properties: { State_LGD: 22 }, geometry: { type: "Point", coordinates: [2, 2] } },
  ],
};

// Minimal valid TopoJSON wrapping the same three points. Hand-built; the
// loader uses topojson-client#feature() to decode, so any shape with
// `type: "Topology"` + `objects.<name>` + arcs (empty arcs OK for
// points) works.
const TINY_TOPOJSON = {
  type: "Topology",
  arcs: [],
  objects: {
    tiny: {
      type: "GeometryCollection",
      geometries: [
        { type: "Point", properties: { State_LGD: 33 }, coordinates: [0, 0] },
        { type: "Point", properties: { State_LGD: 7 }, coordinates: [1, 1] },
        { type: "Point", properties: { State_LGD: 22 }, coordinates: [2, 2] },
      ],
    },
  },
};

function mockFetch(impl: (url: string) => Promise<Response>): void {
  vi.stubGlobal("fetch", vi.fn(impl as any));
}

beforeEach(() => {
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("boundaryRelPaths", () => {
  it("returns sibling .topojson + .geojson paths", () => {
    expect(boundaryRelPaths("state")).toEqual({
      topo: "states/all.topojson",
      geo: "states/all.geojson",
    });
    expect(boundaryRelPaths("country")).toEqual({
      topo: "country/all.topojson",
      geo: "country/all.geojson",
    });
    expect(boundaryRelPaths("district")).toEqual({
      topo: "districts/all.topojson",
      geo: "districts/all.geojson",
    });
  });
});

describe("loadBoundaryFromPath - topojson-first / geojson-fallback", () => {
  it("returns format=topojson when topo sibling fetches and decodes", async () => {
    mockFetch(async url => {
      if (url.endsWith(".topojson")) {
        return new Response(JSON.stringify(TINY_TOPOJSON), { status: 200 });
      }
      throw new Error("geojson should not have been fetched");
    });
    const { fc, format } = await loadBoundaryFromPath("states/all.geojson", "state");
    expect(format).toBe("topojson");
    expect(fc).not.toBeNull();
    expect(fc!.features).toHaveLength(3);
    expect(fc!.features[0].properties.State_LGD).toBe(33);
  });

  it("falls back to geojson on topojson 404 (no warn for the common case)", async () => {
    mockFetch(async url => {
      if (url.endsWith(".topojson")) return new Response("not found", { status: 404 });
      return new Response(JSON.stringify(TINY_GEOJSON), { status: 200 });
    });
    const warnSpy = vi.spyOn(console, "warn");
    const { fc, format } = await loadBoundaryFromPath("states/all.geojson", "state");
    expect(format).toBe("geojson");
    expect(fc).not.toBeNull();
    expect(fc!.features).toHaveLength(3);
    // 404 is the common-case "no topojson yet"; loader should NOT noise the
    // console with a fallback warning for this branch.
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it("falls back to geojson on topojson HTTP 500 and warns", async () => {
    mockFetch(async url => {
      if (url.endsWith(".topojson")) return new Response("boom", { status: 500 });
      return new Response(JSON.stringify(TINY_GEOJSON), { status: 200 });
    });
    const warnSpy = vi.spyOn(console, "warn");
    const { fc, format } = await loadBoundaryFromPath("states/all.geojson", "state");
    expect(format).toBe("geojson");
    expect(fc!.features).toHaveLength(3);
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy.mock.calls[0][0]).toMatch(/\[fallback\].*topojson:state.*500/);
  });

  it("falls back to geojson on topojson parse error and warns", async () => {
    mockFetch(async url => {
      if (url.endsWith(".topojson")) {
        return new Response("not json {", { status: 200 });
      }
      return new Response(JSON.stringify(TINY_GEOJSON), { status: 200 });
    });
    const warnSpy = vi.spyOn(console, "warn");
    const { fc, format } = await loadBoundaryFromPath("states/all.geojson", "state");
    expect(format).toBe("geojson");
    expect(fc!.features).toHaveLength(3);
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy.mock.calls[0][0]).toMatch(/\[fallback\].*topojson:state/);
  });

  it("returns format=null + fc=null when both siblings fail", async () => {
    mockFetch(async () => new Response("nope", { status: 404 }));
    const { fc, format } = await loadBoundaryFromPath("states/all.geojson", "state");
    expect(format).toBeNull();
    expect(fc).toBeNull();
  });

  it("returns format=null when both topo and geo network-error", async () => {
    mockFetch(async () => {
      throw new Error("offline");
    });
    const { fc, format } = await loadBoundaryFromPath("states/all.geojson", "state");
    expect(format).toBeNull();
    expect(fc).toBeNull();
  });
});

describe("loadBoundaryData - public entry point + district filter", () => {
  it("delegates to loadBoundaryFromPath and returns the FC for state level", async () => {
    mockFetch(async url => {
      if (url.endsWith(".topojson")) return new Response(JSON.stringify(TINY_TOPOJSON), { status: 200 });
      throw new Error("geojson should not have been fetched");
    });
    const fc = await loadBoundaryData("state");
    expect(fc).not.toBeNull();
    expect(fc!.features).toHaveLength(3);
  });

  it("filters district FC by stateLgd post-load", async () => {
    const districtPayload = {
      type: "FeatureCollection",
      features: [
        { type: "Feature", properties: { state_lgd: 33, dist_lgd: 1 }, geometry: { type: "Point", coordinates: [0, 0] } },
        { type: "Feature", properties: { state_lgd: 7, dist_lgd: 2 }, geometry: { type: "Point", coordinates: [1, 1] } },
        { type: "Feature", properties: { state_lgd: 33, dist_lgd: 3 }, geometry: { type: "Point", coordinates: [2, 2] } },
      ],
    };
    mockFetch(async url => {
      if (url.endsWith(".topojson")) return new Response("nope", { status: 404 });
      return new Response(JSON.stringify(districtPayload), { status: 200 });
    });
    const fc = await loadBoundaryData("district", undefined, "33");
    expect(fc).not.toBeNull();
    expect(fc!.features).toHaveLength(2);
    expect(fc!.features.every(f => Number(f.properties?.state_lgd) === 33)).toBe(true);
  });
});
