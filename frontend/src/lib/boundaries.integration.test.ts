// Integration tests for the loader. fetch is mocked (the loader's contract
// IS the fetch boundary — Holy Law #7 carve-out). Index manifest reads
// + per-district file fetches are exercised end-to-end through the public
// loadBoundary surface.
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  loadBoundary,
  fetchVillagesIndex,
  _resetCachesForTesting,
} from "./boundaries";

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

const INDEX_FIXTURE = {
  $schema: "https://yen-gov.github.io/schemas/boundary.villages_index.schema.json",
  $schema_version: "2.0",
  sources: [{ url: "https://example/x.7z", fetched_at: "2026-05-15T00:00:00Z" }],
  state_lgd: "33",
  district_lgd_codes: ["568", "603"],
  generated_at: "2026-05-15T00:00:00Z",
};

describe("loadBoundary — composition", () => {
  it("country resolves to india-soi.geojson", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(FC(1)));
    const out = await loadBoundary("country");
    expect(fetchSpy).toHaveBeenCalledWith(`${BASE}/boundaries/in/geojson/india-soi.geojson`);
    expect(out?.features.length).toBe(1);
  });

  it("subdistrict for TN composes the per-state file path", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(FC(300)));
    const out = await loadBoundary("subdistrict", undefined, "33");
    expect(fetchSpy).toHaveBeenCalledWith(
      `${BASE}/boundaries/in/geojson/S22-subdistricts.geojson`,
    );
    expect(out?.features.length).toBe(300);
  });

  it("village for present district fetches the index then the shard", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(INDEX_FIXTURE));
    fetchSpy.mockResolvedValueOnce(jsonResponse(FC(42)));
    const out = await loadBoundary("village", "603", "33");
    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      `${BASE}/boundaries/in/geojson/S22-villages-index.json`,
    );
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      `${BASE}/boundaries/in/geojson/S22-villages-603.geojson`,
    );
    expect(out?.features.length).toBe(42);
  });

  it("village for an absent district returns null without probing the shard URL", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(INDEX_FIXTURE));
    const out = await loadBoundary("village", "999", "33");
    expect(out).toBeNull();
    // Only the index was fetched — the shard URL was NOT probed (Fowler v4 nit 1).
    expect(fetchSpy).toHaveBeenCalledTimes(1);
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

  it("missing index manifest collapses any village query for that state to null", async () => {
    fetchSpy.mockResolvedValueOnce(new Response("nope", { status: 404 }));
    const out = await loadBoundary("village", "603", "33");
    expect(out).toBeNull();
    // Only the index probe — never the shard.
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });
});

describe("fetchVillagesIndex caching", () => {
  it("calls fetch only once for repeated queries to the same state", async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(INDEX_FIXTURE));
    const first = await fetchVillagesIndex("33");
    const second = await fetchVillagesIndex("33");
    expect(first).toEqual(second);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("returns null synchronously for a state with no per-state shard set", async () => {
    const out = await fetchVillagesIndex("99");
    expect(out).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
