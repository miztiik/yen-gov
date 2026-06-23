// Session-scoped raw geometry-JSON cache (perf plan Row 3b).
//
// The d3 map components (StateAcMapD3, StatePcMapD3, IndiaPcMapD3,
// IndiaPartyMap, GeoChoropleth) each fetch a geometry file (topojson /
// geojson, 0.5-10 MB) on mount and then decode it (topojson object
// selection, d3 winding rewind). The custom router full-remounts every
// component on navigation, so revisiting a map used to re-download the
// whole geometry file every time. This caches the fetched + parsed JSON
// keyed by URL so a given geometry file is fetched ONCE per session; the
// decode stays in each component (it differs per layer).
//
// Immutable per deploy: the boundary corpus changes only on deploy, and a
// deploy changes the bundle hash and forces a full page reload (a fresh
// module instance), so the cached promise has a ZERO staleness window by
// construction - structural, not a TTL band-aid (CLAUDE.md Holy Law #5).
//
// Error contract: throws on a non-OK HTTP status so each component's
// existing handling fires unchanged (the per-mount `try/catch` sets
// `load_error`; StateAcMapD3's helper propagates to its caller's catch).
// The rejected promise is EVICTED so a transient failure can be retried
// on the next mount instead of pinning a permanent failure. Mirrors the
// memoisation idiom in duckdb.ts (manifestPromise) and boundaries.ts.

const cache = new Map<string, Promise<unknown>>();

/**
 * Fetch + JSON-parse a geometry file, cached by URL for the session.
 * Returns the parsed JSON (a topojson `Topology` or a geojson
 * `FeatureCollection`); the caller casts + decodes. Throws on a non-OK
 * response.
 */
export function fetchGeometryJson(url: string): Promise<unknown> {
  const hit = cache.get(url);
  if (hit) return hit;
  const p = (async () => {
    const r = await fetch(url);
    if (!r.ok) {
      throw new Error(`geometry fetch failed: ${r.status} ${url}`);
    }
    return (await r.json()) as unknown;
  })();
  cache.set(url, p);
  p.catch(() => {
    cache.delete(url);
  });
  return p;
}

/**
 * Test-only hook: clear the session geometry cache so module-level state
 * does not leak across vitest `it()` blocks. NOT for production use.
 */
export function __resetGeometryCacheForTests(): void {
  cache.clear();
}
