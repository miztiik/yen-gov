// Integration tests for the loader. fetch is mocked (the loader's contract
// IS the fetch boundary — Holy Law #7 carve-out). Post-T.0d (ADR-0031
// Amendment) URLs use the Hive layout under `boundaries/in/<kind>/...`
// and the per-state villages-index manifest is gone (replaced by
// `boundaries/boundary_layers.parquet` queryable via DuckDB-WASM).
// Missing village shards now resolve to null via the 404-as-null branch.
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

describe("loadBoundary — composition (Hive paths)", () => {
  it("country resolves to country/all.geojson", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(FC(1)));
    const out = await loadBoundary("country");
    expect(fetchSpy).toHaveBeenCalledWith(`${BASE}/boundaries/in/country/all.geojson`);
    expect(out?.features.length).toBe(1);
  });

  it("state resolves to states/all.geojson", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(FC(36)));
    const out = await loadBoundary("state");
    expect(fetchSpy).toHaveBeenCalledWith(`${BASE}/boundaries/in/states/all.geojson`);
    expect(out?.features.length).toBe(36);
  });

  it("district resolves to districts/all.geojson", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(FC(766)));
    const out = await loadBoundary("district");
    expect(fetchSpy).toHaveBeenCalledWith(`${BASE}/boundaries/in/districts/all.geojson`);
    expect(out?.features.length).toBe(766);
  });

  it("subdistrict for TN composes the per-state Hive shard path", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(FC(300)));
    const out = await loadBoundary("subdistrict", undefined, "33");
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/boundaries/in/subdistricts/state=in_s22/all.geojson`,
    );
    expect(out?.features.length).toBe(300);
  });

  it("village for present district fetches the per-district Hive shard", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(FC(42)));
    const out = await loadBoundary("village", "603", "33");
    // Post-T.0d: no index probe; one direct fetch to the partitioned shard.
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/boundaries/in/villages/state=in_s22/district=603/all.geojson`,
    );
    expect(out?.features.length).toBe(42);
  });

  it("village for an absent district returns null via 404-as-null", async () => {
    fetchSpy.mockResolvedValueOnce(new Response("nope", { status: 404 }));
    const out = await loadBoundary("village", "999", "33");
    expect(out).toBeNull();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/boundaries/in/villages/state=in_s22/district=999/all.geojson`,
    );
  });
});

describe("loadBoundary — graceful degradation", () => {
  it("404 on an existing-spec path returns null, not throw", async () => {
    fetchSpy.mockResolvedValueOnce(new Response("nope", { status: 404 }));
    const out = await loadBoundary("district");
    expect(out).toBeNull();
  });

  it("network error returns null, not throw", async () => {
    fetchSpy.mockRejectedValueOnce(new Error("offline"));
    const out = await loadBoundary("state");
    expect(out).toBeNull();
  });
});

describe("loadBoundary — district-level filter", () => {
  it("trims national districts file to the requested state", async () => {
    const national = {
      type: "FeatureCollection" as const,
      features: [
        { type: "Feature" as const, properties: { dist_lgd: 603, state_lgd: 33 }, geometry: { type: "Point", coordinates: [80, 13] } },
        { type: "Feature" as const, properties: { dist_lgd: 555, state_lgd: 33 }, geometry: { type: "Point", coordinates: [80, 13] } },
        { type: "Feature" as const, properties: { dist_lgd: 11, state_lgd: 24 }, geometry: { type: "Point", coordinates: [72, 23] } },
      ],
    };
    fetchSpy.mockResolvedValueOnce(jsonResponse(national));
    const out = await loadBoundary("district", undefined, "33");
    expect(out?.features.length).toBe(2);
    expect(out?.features.every(f => Number(f.properties?.state_lgd) === 33)).toBe(true);
  });
});
