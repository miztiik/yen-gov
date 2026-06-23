// Typed boundary loader. Single entry point for any map component that
// needs an LGD-keyed FeatureCollection — replaces the per-component
// fetch('/boundary.json') pattern. Phase 2 of TODO/TN-GRANULAR-GEO-PLAN.md.
//
// The loader is a pure path resolver wrapped around a fetcher. It does NOT
// know about choropleth values, color scales, or click handlers — it only
// answers "given (level, parent district lgd, state lgd), where is the
// GeoJSON and what property carries the join key?".
//
// Drill levels (post-T.0d Hive layout per ADR-0031 Amendment 2026-05-22):
//   country      → datasets/boundaries/in/country/all.geojson
//                  (silhouette only; no per-feature join key)
//   state        → datasets/boundaries/in/states/all.geojson
//                  (ramSeraph LGD-keyed lineage post-D.0; joins on
//                  State_LGD integer per BharatMaps. Pre-D.0 the layer
//                  was DataMeet/maps and joined on ST_NM English name
//                  — see TODO/20260524-boundary-coverage-expansion-plan.md.)
//   district     → datasets/boundaries/in/districts/all.geojson
//                  (LGD-keyed; joins on dist_lgd integer)
//   subdistrict  → datasets/boundaries/in/subdistricts/state=<lgd_slug>/all.geojson
//                  (one shard per state; joins on subdt_lgd integer)
//   village      → datasets/boundaries/in/villages/state=<lgd_slug>/district=<lgd>/all.geojson
//                  (one shard PER DISTRICT; joins on vil_lgd integer)
//   postal       → datasets/boundaries/in/postal/state=<lgd_slug>/all.geojson
//                  (search-only; joins on pincode 6-digit string. Unkeyed
//                   pincode polygons sit in postal/scope=unkeyed/all.geojson
//                   and are not resolved by this state-scoped helper.)
//
// The per-district village split is the contract that lets a single
// district click pull ~10–600 KB instead of the full TN villages bundle
// (~200 MB raw, ~50 MB at coord_precision=4). Which shards exist is
// now sourced from `datasets/data/entities/boundary_layer.csv`
// (X1a-fu2-E 2026-06-07; was a parquet under datasets/boundaries/ pre-rip)
// — the per-state `villages-index.json` manifest was retired in T.0d
// (replaced by the ledger; ADR-0031 Amendment). Missing-shard handling:
// 404-as-null (a one-time HTTP probe per missing district, browser-cached). The previous index
// manifest was a premature optimisation: it cost a separate JSON fetch
// AND a class of state-sync bugs (manifest says X exists but file
// doesn't, or vice versa). The parquet ledger is the single source of
// truth.
//
// Why not import.meta.glob over the per-district files: datasets/ is
// served at runtime via the dev-server middleware + Pages, not bundled
// into the SPA. Vite's import.meta.glob would not see datasets/ even if
// it could; runtime fetch is the right primitive for "load when clicked".
//
// 404-as-null contract: every loadBoundary call that hits a missing file
// resolves to null rather than throwing. Callers (the choropleth) degrade
// gracefully — show a toast, keep the parent layer visible — instead of
// crashing the page. The same contract as resolveSource() in maplibre/sources.ts.

import { feature as topojsonFeature } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import { DATA_BASE } from "./paths";

export type GeoLevel = "country" | "state" | "district" | "subdistrict" | "village" | "postal";

export interface BoundaryFeature {
  type: "Feature";
  properties: Record<string, unknown>;
  geometry: Record<string, unknown>;
}

export interface BoundaryFeatureCollection {
  type: "FeatureCollection";
  features: BoundaryFeature[];
}

/** Per-level property name on each Feature that carries the join key. */
const JOIN_KEYS: Record<GeoLevel, string | null> = {
  country: null,
  state: "State_LGD",
  district: "dist_lgd",
  subdistrict: "subdt_lgd",
  village: "vil_lgd",
  postal: "pincode",
};

// TODO(C.4): add a VILLAGE_BOUNDARY_BY_DISTRICT registry in
// frontend/src/lib/maplibre/sources.ts mirroring PANCHAYAT_BOUNDARY_BY_DISTRICT
// when the first village-grain citizen indicator lands (e.g. MGNREGA
// person-days, micro-watershed, PMGSY road length). 659 shards exist on
// disk (645 LGD + 14 J&K Bhuvan) but no citizen-facing surface consumes
// them yet. Tracked in docs/archive/plans/20260530-boundary-plan-followups.md Category
// 3 (BLOCKED on indicator demand); marker shipped via Row 4.1.


/**
 * LGD state code → ECI state code. Display-only since ADR-0050; partition
 * paths use the LGD-name slug map below.
 */
const STATE_LGD_TO_ECI: Record<string, string> = {
  "33": "S22",
};

/**
 * LGD state code → LGD-name slug (per ADR-0050). Used as the partition-key
 * value for the `state=<slug>/...` Hive layout. Source of truth:
 * `datasets/taxonomy/lgd_states.json` (PR #555). Only LGD codes that have
 * an active partition under `datasets/boundaries/` need an entry here.
 */
const STATE_LGD_TO_SLUG: Record<string, string> = {
  "33": "tamil-nadu",
};

/**
 * Resolve the relative path under `boundaries/in/` for a given level +
 * scope. Pure: no I/O.
 *
 * Throws when the inputs do not satisfy the contract — these are caller
 * bugs (e.g. asking for villages without naming a district) and should
 * surface in tests, not silently return a bogus path. Missing FILES on
 * disk are different from missing INPUTS; that's the 404-as-null branch
 * in loadBoundary.
 */
export function boundaryRelPath(
  level: GeoLevel,
  parentDistrictLgd?: string,
  stateLgd?: string,
): string {
  switch (level) {
    case "country":
      return "country/all.geojson";
    case "state":
      return "states/all.geojson";
    case "district":
      return "districts/all.geojson";
    case "subdistrict": {
      if (!stateLgd) throw new Error("subdistrict requires stateLgd");
      const slug = STATE_LGD_TO_SLUG[stateLgd];
      if (!slug) throw new Error(`no LGD slug mapping for stateLgd=${stateLgd}`);
      return `subdistricts/state=${slug}/all.geojson`;
    }
    case "village": {
      if (!stateLgd) throw new Error("village requires stateLgd");
      if (!parentDistrictLgd) throw new Error("village requires parentDistrictLgd");
      const slug = STATE_LGD_TO_SLUG[stateLgd];
      if (!slug) throw new Error(`no LGD slug mapping for stateLgd=${stateLgd}`);
      return `villages/state=${slug}/district=${parentDistrictLgd}/all.geojson`;
    }
    case "postal": {
      if (!stateLgd) throw new Error("postal requires stateLgd");
      const slug = STATE_LGD_TO_SLUG[stateLgd];
      if (!slug) throw new Error(`no LGD slug mapping for stateLgd=${stateLgd}`);
      return `postal/state=${slug}/all.geojson`;
    }
  }
}

/**
 * @deprecated Use `boundaryRelPath` (post-T.0d Hive layout). Retained
 * as a thin alias for one release so callers that stored the symbol can
 * migrate. Returns the same string boundaryRelPath returns.
 */
export function boundaryBasename(
  level: GeoLevel,
  parentDistrictLgd?: string,
  stateLgd?: string,
): string {
  return boundaryRelPath(level, parentDistrictLgd, stateLgd);
}

/**
 * Sibling-path pair for the topojson-first / geojson-fallback contract
 * (docs/archive/plans/20260531-geojson-to-topojson-migration-plan.md P2.3). Returns
 * both candidate relative paths for the same logical layer; the loader
 * tries `topo` first and falls back to `geo`. Pure: no I/O.
 *
 * Until P5.4 retires geojson siblings, every boundary partition has a
 * `.geojson` on disk; only some have a `.topojson` sibling yet (Phase
 * 1 ships states; Phase 3/4 cascades remaining layers).
 */
export function boundaryRelPaths(
  level: GeoLevel,
  parentDistrictLgd?: string,
  stateLgd?: string,
): { topo: string; geo: string } {
  const geo = boundaryRelPath(level, parentDistrictLgd, stateLgd);
  // Swap the `.geojson` extension for `.topojson`. Both extensions are
  // 7 chars; the partition path itself is unchanged.
  const topo = geo.replace(/\.geojson$/, ".topojson");
  return { topo, geo };
}

/** Per-level join-key property name (or null at country level — silhouette only). */
export function joinKeyFor(level: GeoLevel): string | null {
  return JOIN_KEYS[level];
}

/** Test-only — retained as a no-op for caller compatibility. */
export function _resetCachesForTesting(): void {
  // Row 3: clear the session boundary-geometry cache so module-level state
  // does not leak across vitest `it()` blocks. (The T.0d villages-index
  // reader cache was retired; the boundary geometry cache is the only
  // internal cache now.)
  boundaryCache.clear();
}

/**
 * Compute a coarse centroid for a GeoJSON geometry. Pure: no I/O. Used by
 * the drill-down breadcrumb glyph (Phase 3 c3 of TN-GRANULAR-GEO-PLAN).
 *
 * Algorithm: arithmetic mean of every coordinate pair the geometry visits.
 * NOT a proper polygon-area centroid (which requires shoelace integration);
 * this is the cheapest "where roughly is this thing" we can compute without
 * pulling in @turf/centroid (~30 KB) for a 14 px glyph. The breadcrumb is
 * a positional cue, not a geometric assertion — coarse is fine.
 *
 * Returns null when the geometry is missing or has no positions.
 */
export function centroidOf(
  geometry: { coordinates?: unknown } | null | undefined,
): [number, number] | null {
  if (!geometry || !geometry.coordinates) return null;
  let sx = 0;
  let sy = 0;
  let n = 0;
  function visit(c: any): void {
    if (typeof c[0] === "number" && typeof c[1] === "number") {
      sx += c[0];
      sy += c[1];
      n += 1;
      return;
    }
    for (const child of c) visit(child);
  }
  visit(geometry.coordinates);
  if (n === 0) return null;
  return [sx / n, sy / n];
}

/** State-LGD → ECI code (exported for callers that need to bridge the two). */
export const STATE_LGD_TO_ECI_PUBLIC: Record<string, string> = STATE_LGD_TO_ECI;

/**
 * Predicate: does `baseGeoRelPath` have a real `.topojson` sibling on
 * disk worth probing? After the 2026-06-16 map-geometry rip (decision
 * D4) the ONLY `.topojson` `loadBoundaryFromPath` serves is the combined
 * country file `country/all.topojson` (two named objects: `states` +
 * `districts`). The national AC topojson (`electoral/delim=2024/ac/
 * all.topojson`, Row 3) is fetched + decoded inline by StateAcMapD3, NOT
 * through this loader, so it is intentionally absent here. Every other
 * layer ships `.geojson` only, so the loader fetches geojson DIRECTLY
 * instead of wasting an HTTP round-trip on a `.topojson` that no longer
 * exists. Pure: no I/O.
 */
export function pathHasTopojson(baseGeoRelPath: string): boolean {
  return baseGeoRelPath === "country/all.geojson";
}

// Session-scoped boundary-geometry cache (perf plan Row 3). The fetched +
// decoded result for a given (baseGeoRelPath, objectName) is immutable
// within a session: the boundary corpus changes only on deploy, and a
// deploy changes the bundle hash and forces a full page reload (a fresh
// module instance), so the cached promise has a ZERO staleness window by
// construction - structural, not a TTL band-aid (CLAUDE.md Holy Law #5).
// Without it, navigating state -> back -> state re-downloads 0.5-10 MB of
// geometry on every map mount (the router full-remounts every component).
// A null result is cached too, so a genuinely absent file is not
// re-probed on every mount (the 404-as-null contract). Mirrors the
// Map + promise pattern proven in state-silhouette.ts.
const boundaryCache = new Map<
  string,
  Promise<{ fc: BoundaryFeatureCollection | null; format: "topojson" | "geojson" | null }>
>();

/**
 * Public boundary loader - session-cached wrapper around
 * `loadBoundaryFromPathUncached`. The cache key is
 * `(baseGeoRelPath, objectName)` because `objectName` selects which named
 * object is decoded from the (shared) country topojson, so two object
 * names off the same file are distinct results. `label` is perf-mark-only
 * and is intentionally NOT part of the key. The wrapped impl never
 * rejects (it returns `{ fc: null }` on any failure), but the `.catch`
 * eviction keeps an unexpected throw from pinning the cache.
 */
export function loadBoundaryFromPath(
  baseGeoRelPath: string,
  label: string,
  objectName?: string,
): Promise<{ fc: BoundaryFeatureCollection | null; format: "topojson" | "geojson" | null }> {
  const key = `${baseGeoRelPath}|${objectName ?? ""}`;
  const cached = boundaryCache.get(key);
  if (cached) return cached;
  const p = loadBoundaryFromPathUncached(baseGeoRelPath, label, objectName);
  boundaryCache.set(key, p);
  p.catch(() => {
    boundaryCache.delete(key);
  });
  return p;
}

/**
 * Fetch one boundary partition by its base relative path.
 *
 * Format-aware contract (post 2026-06-16 map-geometry rip): only the
 * country layer (`country/all.geojson`, per `pathHasTopojson`) has a
 * `.topojson` sibling, so only it is probed `.topojson`-first and falls
 * back to `.geojson` on any failure (404, JSON parse error, topojson
 * decode error). Every other base path fetches `.geojson` DIRECTLY (no
 * wasted topojson probe). Returns the parsed FeatureCollection plus a
 * `format` marker indicating which sibling won, or `{ fc: null, format:
 * null }` when the file is absent (the 404-as-null contract).
 *
 * Object-by-name: the country topojson carries MULTIPLE named objects,
 * so `objectName` selects which one to decode (e.g. `"states"` or
 * `"districts"`). When `objectName` is omitted or absent from the
 * topology, the first object name is decoded (the single-object case for
 * any other future topojson). Ignored on the geojson path.
 *
 * `[fallback]` console.warn logs the reason whenever the country topo
 * branch loses for a non-404 reason. Perf-marks (VITE_BENCH=1) wrap the
 * winning fetch+parse so the bench harness can attribute the cost
 * per-layer.
 *
 * `baseGeoRelPath` is the `.geojson` sibling path relative to the
 * `boundaries/in/` root (matches what `boundaryRelPath` returns, e.g.
 * `"states/all.geojson"`). `label` is a stable short identifier
 * surfaced in perf-mark names and fallback warnings (typically the
 * GeoLevel string).
 */
async function loadBoundaryFromPathUncached(
  baseGeoRelPath: string,
  label: string,
  objectName?: string,
): Promise<{ fc: BoundaryFeatureCollection | null; format: "topojson" | "geojson" | null }> {
  const geoUrl = `${DATA_BASE}/boundaries/in/${baseGeoRelPath}`;
  const benchEnabled = import.meta.env.VITE_BENCH === "1";
  const markStart = benchEnabled ? `boundary-fetch-start:${label}` : "";
  const markEnd = benchEnabled ? `boundary-source-added:${label}` : "";
  if (benchEnabled) performance.mark(markStart);

  const finish = (format: "topojson" | "geojson" | null): void => {
    if (!benchEnabled) return;
    performance.mark(markEnd);
    try {
      performance.measure(`boundary-load:${label}`, markStart, markEnd);
    } catch {
      // measure() can throw if the marks were cleared mid-flight; ignore.
    }
    if (format) {
      try {
        performance.measure(
          `boundary-load:${label}:${format}`,
          markStart,
          markEnd,
        );
      } catch {
        // ignore measure errors; the unprefixed measure above is the
        // load-bearing signal for the bench harness.
      }
    }
  };

  // 1. Try topojson first - ONLY for the country layer, the sole
  //    `.topojson` on disk post-rip. Non-country base paths skip
  //    straight to geojson (no wasted HTTP probe).
  if (pathHasTopojson(baseGeoRelPath)) {
    const topoRel = baseGeoRelPath.replace(/\.geojson$/, ".topojson");
    const topoUrl = `${DATA_BASE}/boundaries/in/${topoRel}`;
    try {
      const r = await fetch(topoUrl);
      if (r.ok) {
        const topo = (await r.json()) as Topology;
        const objectKeys = Object.keys(topo.objects ?? {});
        if (objectKeys.length === 0) {
          throw new Error("topojson has no objects");
        }
        // Decode the caller-named object when present (the country file
        // carries TWO objects - `states` + `districts` - so objectKeys[0]
        // is ambiguous); otherwise decode the first (single-object case).
        const objectKey =
          objectName && topo.objects[objectName] ? objectName : objectKeys[0];
        const decoded = topojsonFeature(
          topo,
          topo.objects[objectKey] as GeometryCollection,
        );
        const fc =
          decoded.type === "FeatureCollection"
            ? (decoded as unknown as BoundaryFeatureCollection)
            : ({
                type: "FeatureCollection",
                features: [decoded as unknown as BoundaryFeature],
              } as BoundaryFeatureCollection);
        finish("topojson");
        return { fc, format: "topojson" };
      }
      // Non-OK is the common 404 case. Fall through to geojson.
      if (r.status !== 404) {
        // eslint-disable-next-line no-console
        console.warn(
          `[fallback] topojson:${label} HTTP ${r.status}; falling back to geojson`,
        );
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn(`[fallback] topojson:${label} ${String(err)}; falling back to geojson`);
    }
  }

  // 2. Fall back to (or, for non-country layers, go straight to) geojson.
  try {
    const r = await fetch(geoUrl);
    if (!r.ok) {
      finish(null);
      return { fc: null, format: null };
    }
    const fc = (await r.json()) as BoundaryFeatureCollection;
    finish("geojson");
    return { fc, format: "geojson" };
  } catch {
    finish(null);
    return { fc: null, format: null };
  }
}

/**
 * Public sibling of `loadBoundary` exposing the topojson-first /
 * geojson-fallback contract. Replaces direct `boundaryRelPath()` +
 * `fetch()` patterns at any call site that should pick up the wire-size
 * win from the topojson encoding (per P2.3).
 *
 * The legacy `loadBoundary()` below now delegates to this function, so
 * callers can migrate at their own pace; both signatures share the same
 * resolution + fallback behaviour.
 */
export async function loadBoundaryData(
  level: GeoLevel,
  parentDistrictLgd?: string,
  stateLgd?: string,
): Promise<BoundaryFeatureCollection | null> {
  const relpath = boundaryRelPath(level, parentDistrictLgd, stateLgd);
  const { fc } = await loadBoundaryFromPath(relpath, level);
  if (!fc) return null;
  if (level === "district" && stateLgd) {
    const wanted = Number(stateLgd);
    if (Number.isFinite(wanted)) {
      return {
        ...fc,
        features: fc.features.filter(f => Number(f.properties?.state_lgd) === wanted),
      };
    }
  }
  return fc;
}

/**
 * Load the FeatureCollection for the requested level. Returns null when
 * the file is absent (the graceful-degradation contract). Throws only on
 * caller-input bugs (see boundaryRelPath).
 *
 * Post-2026-05-31 (P2.3) this function delegates to `loadBoundaryData`,
 * which adds the topojson-first / geojson-fallback resolution. Behaviour
 * is unchanged for any partition that lacks a `.topojson` sibling (the
 * loader silently falls through to the existing geojson path).
 */
export async function loadBoundary(
  level: GeoLevel,
  parentDistrictLgd?: string,
  stateLgd?: string,
): Promise<BoundaryFeatureCollection | null> {
  return loadBoundaryData(level, parentDistrictLgd, stateLgd);
}
