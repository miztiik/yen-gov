// Integration tests for the loader. fetch is mocked (the loader's contract
// IS the fetch boundary - Holy Law #7 carve-out). Post-T.0d (ADR-0031
// Amendment) URLs use the Hive layout under `boundaries/in/<kind>/...`
// and the per-state villages-index manifest is gone (replaced by
// `data/entities/boundary_layer.csv`, the X1a-fu2-E CSV-form ledger).
// Missing village shards now resolve to null via the 404-as-null branch.
//
// Post the 2026-06-16 map-geometry rip the loader is FORMAT-AWARE: only the
// country layer probes `.topojson` first (the sole surviving topojson);
// every other layer fetches `.geojson` DIRECTLY. These tests pin the
// non-country geojson-direct path (1 fetch per layer, no topojson probe);
// `mockGeoPayload` still returns 404 for any `.topojson` URL so the
// country fallback case stays covered too.
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { loadBoundary, _resetCachesForTesting } from "./boundaries";

const BASE = "/data";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

let fetchSpy: ReturnType<typeof vi.fn>;

/**
 * Route a single .geojson payload via the topo-first / geo-fallback
 * contract: any `.topojson` URL returns 404; the matching `.geojson`
 * URL returns the supplied body. Other URLs throw (caller test bug).
 */
function mockGeoPayload(body: unknown, status = 200): void {
  fetchSpy.mockImplementation(async (url: string) => {
    if (url.endsWith(".topojson")) return new Response("nope", { status: 404 });
    if (url.endsWith(".geojson")) return jsonResponse(body, status);
    throw new Error(`unexpected fetch URL in test: ${url}`);
  });
}

beforeEach(() => {
  fetchSpy = vi.fn();
  globalThis.fetch = fetchSpy as unknown as typeof fetch;
  _resetCachesForTesting();
});

afterEach(() => {
  vi.restoreAllMocks();
});

const FC = (n: number) => ({
  type: "FeatureCollection",
  features: Array.from({ length: n }, (_, i) => ({
    type: "Feature",
    properties: { i },
    geometry: { type: "Point", coordinates: [80, 13] },
  })),
});

describe("loadBoundary - composition (Hive paths)", () => {
  it("country resolves to country/all.geojson", async () => {
    mockGeoPayload(FC(1));
    const out = await loadBoundary("country");
    expect(fetchSpy).toHaveBeenCalledWith(`${BASE}/boundaries/in/country/all.geojson`);
    expect(out?.features.length).toBe(1);
  });

  it("state resolves to states/all.geojson", async () => {
    mockGeoPayload(FC(36));
    const out = await loadBoundary("state");
    expect(fetchSpy).toHaveBeenCalledWith(`${BASE}/boundaries/in/states/all.geojson`);
    expect(out?.features.length).toBe(36);
  });

  it("district resolves to districts/all.geojson", async () => {
    mockGeoPayload(FC(766));
    const out = await loadBoundary("district");
    expect(fetchSpy).toHaveBeenCalledWith(`${BASE}/boundaries/in/districts/all.geojson`);
    expect(out?.features.length).toBe(766);
  });

  it("subdistrict for TN composes the per-state Hive shard path", async () => {
    mockGeoPayload(FC(300));
    const out = await loadBoundary("subdistrict", undefined, "33");
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/boundaries/in/subdistricts/state=tamil-nadu/all.geojson`,
    );
    expect(out?.features.length).toBe(300);
  });

  it("village for present district fetches the per-district Hive shard (geojson-direct)", async () => {
    mockGeoPayload(FC(42));
    const out = await loadBoundary("village", "603", "33");
    // Post map-geometry rip: non-country layers fetch geojson directly
    // (1 fetch, no topojson probe).
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/boundaries/in/villages/state=tamil-nadu/district=603/all.geojson`,
    );
    expect(out?.features.length).toBe(42);
  });

  it("village for an absent district returns null (single geojson 404)", async () => {
    fetchSpy.mockImplementation(async () => new Response("nope", { status: 404 }));
    const out = await loadBoundary("village", "999", "33");
    expect(out).toBeNull();
    // 1 fetch: geojson only (no topojson probe for non-country layers).
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/boundaries/in/villages/state=tamil-nadu/district=999/all.geojson`,
    );
  });
});

describe("loadBoundary - graceful degradation", () => {
  it("404 on both siblings returns null, not throw", async () => {
    fetchSpy.mockImplementation(async () => new Response("nope", { status: 404 }));
    const out = await loadBoundary("district");
    expect(out).toBeNull();
  });

  it("network error on both siblings returns null, not throw", async () => {
    fetchSpy.mockImplementation(async () => {
      throw new Error("offline");
    });
    const out = await loadBoundary("state");
    expect(out).toBeNull();
  });
});

describe("loadBoundary - district-level filter", () => {
  it("trims national districts file to the requested state", async () => {
    const national = {
      type: "FeatureCollection" as const,
      features: [
        { type: "Feature" as const, properties: { dist_lgd: 603, state_lgd: 33 }, geometry: { type: "Point", coordinates: [80, 13] } },
        { type: "Feature" as const, properties: { dist_lgd: 555, state_lgd: 33 }, geometry: { type: "Point", coordinates: [80, 13] } },
        { type: "Feature" as const, properties: { dist_lgd: 11, state_lgd: 24 }, geometry: { type: "Point", coordinates: [72, 23] } },
      ],
    };
    mockGeoPayload(national);
    const out = await loadBoundary("district", undefined, "33");
    expect(out?.features.length).toBe(2);
    expect(out?.features.every(f => Number(f.properties?.state_lgd) === 33)).toBe(true);
  });
});
