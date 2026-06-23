// Unit tests for the session geometry-JSON cache (perf plan Row 3b).
// Mocks `fetch` per the Holy Law #7 loader-test carve-out.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchGeometryJson, __resetGeometryCacheForTests } from "./geometry-cache";

function mockFetch(impl: (url: string) => Promise<Response>): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  vi.stubGlobal("fetch", vi.fn(impl as any));
}

beforeEach(() => {
  __resetGeometryCacheForTests();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("fetchGeometryJson - session cache (perf plan Row 3b)", () => {
  it("fetches a URL once and serves repeat calls from the cache", async () => {
    const urls: string[] = [];
    mockFetch(async url => {
      urls.push(url);
      return new Response(JSON.stringify({ type: "FeatureCollection", features: [] }), {
        status: 200,
      });
    });
    const a = await fetchGeometryJson("/data/x/all.geojson");
    const b = await fetchGeometryJson("/data/x/all.geojson");
    // One network fetch total; the second call is served from cache.
    expect(urls).toHaveLength(1);
    expect(b).toBe(a); // same cached resolved value
  });

  it("dedupes concurrent in-flight calls for the same URL", async () => {
    const urls: string[] = [];
    mockFetch(async url => {
      urls.push(url);
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    });
    const [a, b] = await Promise.all([
      fetchGeometryJson("/data/y.geojson"),
      fetchGeometryJson("/data/y.geojson"),
    ]);
    expect(urls).toHaveLength(1);
    expect(a).toEqual(b);
  });

  it("throws on a non-OK response and evicts so a retry re-fetches", async () => {
    let calls = 0;
    mockFetch(async () => {
      calls += 1;
      return calls === 1
        ? new Response("nope", { status: 404 })
        : new Response(JSON.stringify({ recovered: true }), { status: 200 });
    });
    await expect(fetchGeometryJson("/data/z.geojson")).rejects.toThrow(
      /geometry fetch failed: 404/,
    );
    // The rejected promise is evicted -> the next mount can re-fetch.
    const ok = await fetchGeometryJson("/data/z.geojson");
    expect(ok).toEqual({ recovered: true });
    expect(calls).toBe(2);
  });

  it("keys the cache on URL (distinct URLs fetch separately)", async () => {
    const urls: string[] = [];
    mockFetch(async url => {
      urls.push(url);
      return new Response(JSON.stringify({ url }), { status: 200 });
    });
    await fetchGeometryJson("/data/a.geojson");
    await fetchGeometryJson("/data/b.geojson");
    expect(urls).toEqual(["/data/a.geojson", "/data/b.geojson"]);
  });
});
