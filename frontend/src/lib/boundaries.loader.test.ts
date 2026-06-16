// Loader unit tests for the format-aware contract (Row 2 of the
// 2026-06-16 map-geometry rip): the country layer is topojson-first with
// geojson fallback + object-by-name decode; every other layer fetches
// geojson DIRECTLY (no topojson probe). Mocks `fetch` per the CLAUDE.md
// Holy Law #7 loader-test carve-out so we can exercise the country
// topo-OK / topo-404 / topo-500 / topo-parse-error branches AND the
// non-country geojson-direct branch deterministically, without touching
// the on-disk corpus.

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

// Minimal country-shaped topojson with TWO named objects (states +
// districts) to exercise the object-by-name decode. `states` carries
// State_LGD; `districts` carries dist_lgd.
const TINY_COUNTRY_TOPOJSON = {
  type: "Topology",
  arcs: [],
  objects: {
    states: {
      type: "GeometryCollection",
      geometries: [
        { type: "Point", properties: { State_LGD: 33 }, coordinates: [0, 0] },
        { type: "Point", properties: { State_LGD: 7 }, coordinates: [1, 1] },
      ],
    },
    districts: {
      type: "GeometryCollection",
      geometries: [
        { type: "Point", properties: { dist_lgd: 1 }, coordinates: [0, 0] },
        { type: "Point", properties: { dist_lgd: 2 }, coordinates: [1, 1] },
        { type: "Point", properties: { dist_lgd: 3 }, coordinates: [2, 2] },
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

describe("loadBoundaryFromPath - format-aware (country=topojson, else geojson-direct)", () => {
  it("country: returns format=topojson when the topo sibling decodes", async () => {
    mockFetch(async url => {
      if (url.endsWith(".topojson")) {
        return new Response(JSON.stringify(TINY_TOPOJSON), { status: 200 });
      }
      throw new Error("geojson should not have been fetched");
    });
    const { fc, format } = await loadBoundaryFromPath("country/all.geojson", "country");
    expect(format).toBe("topojson");
    expect(fc).not.toBeNull();
    expect(fc!.features).toHaveLength(3);
    expect(fc!.features[0].properties.State_LGD).toBe(33);
  });

  it("country: decodes the caller-named object (object-by-name)", async () => {
    mockFetch(async url => {
      if (url.endsWith(".topojson")) {
        return new Response(JSON.stringify(TINY_COUNTRY_TOPOJSON), { status: 200 });
      }
      throw new Error("geojson should not have been fetched");
    });
    const states = await loadBoundaryFromPath("country/all.geojson", "country", "states");
    expect(states.format).toBe("topojson");
    expect(states.fc!.features).toHaveLength(2);
    expect(states.fc!.features[0].properties.State_LGD).toBe(33);

    const districts = await loadBoundaryFromPath("country/all.geojson", "country", "districts");
    expect(districts.fc!.features).toHaveLength(3);
    expect(districts.fc!.features[0].properties.dist_lgd).toBe(1);
  });

  it("country: unknown object name falls back to the first object", async () => {
    mockFetch(async url => {
      if (url.endsWith(".topojson")) {
        return new Response(JSON.stringify(TINY_COUNTRY_TOPOJSON), { status: 200 });
      }
      throw new Error("geojson should not have been fetched");
    });
    const { fc } = await loadBoundaryFromPath("country/all.geojson", "country", "nope");
    // objectKeys[0] === "states" (declared first), so 2 features.
    expect(fc!.features).toHaveLength(2);
  });

  it("country: falls back to geojson on topo 404 (no warn for the common case)", async () => {
    mockFetch(async url => {
      if (url.endsWith(".topojson")) return new Response("not found", { status: 404 });
      return new Response(JSON.stringify(TINY_GEOJSON), { status: 200 });
    });
    const warnSpy = vi.spyOn(console, "warn");
    const { fc, format } = await loadBoundaryFromPath("country/all.geojson", "country");
    expect(format).toBe("geojson");
    expect(fc!.features).toHaveLength(3);
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it("country: falls back to geojson on topo HTTP 500 and warns", async () => {
    mockFetch(async url => {
      if (url.endsWith(".topojson")) return new Response("boom", { status: 500 });
      return new Response(JSON.stringify(TINY_GEOJSON), { status: 200 });
    });
    const warnSpy = vi.spyOn(console, "warn");
    const { fc, format } = await loadBoundaryFromPath("country/all.geojson", "country");
    expect(format).toBe("geojson");
    expect(fc!.features).toHaveLength(3);
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy.mock.calls[0][0]).toMatch(/\[fallback\].*topojson:country.*500/);
  });

  it("country: falls back to geojson on topo parse error and warns", async () => {
    mockFetch(async url => {
      if (url.endsWith(".topojson")) {
        return new Response("not json {", { status: 200 });
      }
      return new Response(JSON.stringify(TINY_GEOJSON), { status: 200 });
    });
    const warnSpy = vi.spyOn(console, "warn");
    const { fc, format } = await loadBoundaryFromPath("country/all.geojson", "country");
    expect(format).toBe("geojson");
    expect(fc!.features).toHaveLength(3);
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy.mock.calls[0][0]).toMatch(/\[fallback\].*topojson:country/);
  });

  it("non-country: fetches geojson DIRECTLY without probing topojson", async () => {
    const fetchedUrls: string[] = [];
    mockFetch(async url => {
      fetchedUrls.push(url);
      if (url.endsWith(".topojson")) {
        throw new Error("topojson must not be probed for a non-country layer");
      }
      return new Response(JSON.stringify(TINY_GEOJSON), { status: 200 });
    });
    const { fc, format } = await loadBoundaryFromPath("states/all.geojson", "state");
    expect(format).toBe("geojson");
    expect(fc!.features).toHaveLength(3);
    // Exactly one fetch, and it is the geojson (no topojson round-trip).
    expect(fetchedUrls).toHaveLength(1);
    expect(fetchedUrls[0].endsWith("states/all.geojson")).toBe(true);
  });

  it("non-country: returns null on geojson 404 (single fetch, no topo probe)", async () => {
    const fetchedUrls: string[] = [];
    mockFetch(async url => {
      fetchedUrls.push(url);
      return new Response("nope", { status: 404 });
    });
    const { fc, format } = await loadBoundaryFromPath(
      "villages/state=tamil-nadu/district=603/all.geojson",
      "village",
    );
    expect(format).toBeNull();
    expect(fc).toBeNull();
    expect(fetchedUrls).toHaveLength(1);
    expect(fetchedUrls[0].endsWith(".geojson")).toBe(true);
  });

  it("country: returns format=null + fc=null when both siblings fail", async () => {
    mockFetch(async () => new Response("nope", { status: 404 }));
    const { fc, format } = await loadBoundaryFromPath("country/all.geojson", "country");
    expect(format).toBeNull();
    expect(fc).toBeNull();
  });

  it("country: returns format=null when both topo and geo network-error", async () => {
    mockFetch(async () => {
      throw new Error("offline");
    });
    const { fc, format } = await loadBoundaryFromPath("country/all.geojson", "country");
    expect(format).toBeNull();
    expect(fc).toBeNull();
  });
});

describe("loadBoundaryData - public entry point + district filter", () => {
  it("delegates to loadBoundaryFromPath and returns the FC for state level (geojson-direct)", async () => {
    mockFetch(async url => {
      if (url.endsWith(".topojson")) {
        throw new Error("topojson must not be probed for the state layer");
      }
      return new Response(JSON.stringify(TINY_GEOJSON), { status: 200 });
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
