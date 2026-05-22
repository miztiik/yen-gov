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
//                  (datameet/maps lineage; joins on ST_NM English name)
//   district     → datasets/boundaries/in/districts/all.geojson
//                  (LGD-keyed; joins on dist_lgd integer)
//   subdistrict  → datasets/boundaries/in/subdistricts/state=in_<lc>/all.geojson
//                  (one shard per state; joins on subdt_lgd integer)
//   village      → datasets/boundaries/in/villages/state=in_<lc>/district=<lgd>/all.geojson
//                  (one shard PER DISTRICT; joins on vil_lgd integer)
//   postal       → datasets/boundaries/in/postal/IN-pincodes-<city>.geojson
//                  (search-only; Chennai metro under TN today; joins on
//                   pincode 6-digit string. Phase 4 §160 — structural
//                   surface lands ahead of the data file and the Phase 3
//                   search-affordance consumer.)
//
// The per-district village split is the contract that lets a single
// district click pull ~10–600 KB instead of the full TN villages bundle
// (~200 MB raw, ~50 MB at coord_precision=4). Which shards exist is
// now sourced from `datasets/boundaries/boundary_layers.parquet`
// (queryable via DuckDB-WASM) — the per-state `villages-index.json`
// manifest was retired in T.0d (replaced by the parquet ledger;
// ADR-0031 Amendment). Missing-shard handling: 404-as-null (a one-time
// HTTP probe per missing district, browser-cached). The previous index
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
  state: "ST_NM",
  district: "dist_lgd",
  subdistrict: "subdt_lgd",
  village: "vil_lgd",
  postal: "pincode",
};

/** Tamil Nadu LGD state code (string, as upstream features carry). */
const TN_STATE_LGD = "33";

/**
 * LGD state code → ECI state code. Used to derive the partition slug
 * `in_<lc>` from the LGD code in incoming requests. Pre-T.0d this was
 * STATE_LGD_TO_ECI; the export name is preserved so downstream callers
 * keep working.
 */
const STATE_LGD_TO_ECI: Record<string, string> = {
  "33": "S22",
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
      const eci = STATE_LGD_TO_ECI[stateLgd];
      if (!eci) throw new Error(`no per-state subdistricts file for stateLgd=${stateLgd}`);
      return `subdistricts/state=in_${eci.toLowerCase()}/all.geojson`;
    }
    case "village": {
      if (!stateLgd) throw new Error("village requires stateLgd");
      if (!parentDistrictLgd) throw new Error("village requires parentDistrictLgd");
      const eci = STATE_LGD_TO_ECI[stateLgd];
      if (!eci) throw new Error(`no per-state village files for stateLgd=${stateLgd}`);
      return `villages/state=in_${eci.toLowerCase()}/district=${parentDistrictLgd}/all.geojson`;
    }
    case "postal": {
      // Phase 4 §160 of TODO/TN-GRANULAR-GEO-PLAN.md. Pincode polygons are
      // a search-only layer (Jony edit §d) and currently exist only for
      // Chennai metro under TN. Returns the same Chennai file regardless
      // of `parentDistrictLgd` (kept in the signature for shape-symmetry
      // with `village`); the consumer searches by `pincode` property.
      // Postal stays under `postal/` (no Hive sub-tree yet) because there
      // is only one shard today; promote to `postal/state=in_s22/all.geojson`
      // when a second state pincode layer ships.
      if (!stateLgd) throw new Error("postal requires stateLgd");
      if (stateLgd !== TN_STATE_LGD) {
        throw new Error(`no postal boundaries for stateLgd=${stateLgd}`);
      }
      return "postal/IN-pincodes-chennai.geojson";
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

/** Per-level join-key property name (or null at country level — silhouette only). */
export function joinKeyFor(level: GeoLevel): string | null {
  return JOIN_KEYS[level];
}

/** Test-only — retained as a no-op for caller compatibility. */
export function _resetCachesForTesting(): void {
  // No internal caches after T.0d — villages-index reader was retired.
  // Kept as a stub so existing test setup code (resetting between cases)
  // doesn't break.
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
 * Load the FeatureCollection for the requested level. Returns null when
 * the file is absent (the graceful-degradation contract). Throws only on
 * caller-input bugs (see boundaryRelPath).
 *
 * For village queries: existence is no longer pre-checked against a
 * separate index manifest — the loader fetches the Hive-partitioned shard
 * directly and resolves to null on 404. Trade-off: one HTTP probe per
 * missing district click (browser-cached after first 404), in exchange
 * for elimination of the index/file state-sync bug class. The single
 * source of truth for which shards exist is
 * `datasets/boundaries/boundary_layers.parquet` (queryable via
 * DuckDB-WASM by any consumer that needs the full inventory).
 */
export async function loadBoundary(
  level: GeoLevel,
  parentDistrictLgd?: string,
  stateLgd?: string,
): Promise<BoundaryFeatureCollection | null> {
  const relpath = boundaryRelPath(level, parentDistrictLgd, stateLgd);
  const url = `${DATA_BASE}/boundaries/in/${relpath}`;
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    const fc = (await r.json()) as BoundaryFeatureCollection;
    // District-level filter: districts/all.geojson is national. When the
    // caller supplies a stateLgd (drill-down picked a specific state), trim
    // to that state's districts before returning so the choropleth doesn't
    // paint 766 districts for what was a state-scoped click. Property
    // upstream is numeric `state_lgd`; the caller passes the LGD as string,
    // so coerce on the property side. Phase 4 d4 of TN-GRANULAR-GEO-PLAN.
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
  } catch {
    return null;
  }
}
