// State silhouette loader (parent plan section 25.4 E3).
//
// Shared by `StateAcMap.svelte` (district choropleth, maplibre) and
// `ElectionMap.svelte` (which feeds `TileCartogram.svelte`'s hex
// silhouette layer). Returns the one state Feature drawn behind /
// above the per-state map so the citizen instantly recognises which
// state they are looking at.
//
// Doctrine ties:
//   - parent plan section 25.4: "both pull the outline from the SAME
//     boundary geometry the choropleth already loads (the active
//     node's state feature)". The shared canonical state-boundary
//     corpus is `datasets/boundaries/in/states/all.geojson` (the
//     `.topojson` sibling was retired in the 2026-06-16 map-geometry
//     rip; the d3 choropleths read the `states` object of the combined
//     `country/all.topojson`). Reusing the same
//     seam keeps the single-state silhouette feature derived from
//     the canonical corpus - no new bespoke geometry file, no new
//     loader, no new dep.
//   - CLAUDE.md section 12 ADR-0050: state identity crosswalk lives
//     on `taxonomy.entities` via `view-models/states.ts`
//     (`loadStates()`). The silhouette feature is keyed on the
//     `State_LGD` numeric property; we map the caller's ECI code
//     (e.g. "S22") to the LGD code (e.g. "33") via
//     `boundary_join_key`.
//
// Cache scope: per-page-load. The 36-row crosswalk + state geojson
// don't change inside a session, and a citizen browsing multiple
// states would otherwise re-decode the topojson on each visit. The
// cache is a `Map<eci_code, Feature | null>`; null is cached so a
// missing state doesn't re-probe on every render.

import type { Feature, Geometry } from "geojson";

import { loadBoundaryFromPath } from "./boundaries";
import { loadStates } from "./view-models/states";

/** Feature.properties shape for `states/all.geojson` per the ramSeraph LGD_States lineage. */
export interface StateSilhouetteProps {
  [name: string]: unknown;
  State_LGD?: number;
  STNAME?: string;
  Remarks?: string;
}

export type StateSilhouetteFeature = Feature<Geometry, StateSilhouetteProps>;

const cache = new Map<string, StateSilhouetteFeature | null>();
let inFlight: Promise<void> | null = null;

/**
 * Returns the one state Feature for `state_code` (ECI form, e.g.
 * "S22"). Resolves to `null` when (a) the ECI -> LGD crosswalk has no
 * entry, (b) the boundary corpus is missing the state, or (c) the
 * fetch fails. Callers should fall through to "no silhouette drawn"
 * in any null case - the underlying map remains usable.
 *
 * Calls more than one consumer in the same page-load share the
 * cached result; the first call loads + decodes the topojson, every
 * subsequent call returns synchronously from the in-memory map.
 */
export async function loadStateSilhouette(
  state_code: string,
): Promise<StateSilhouetteFeature | null> {
  if (cache.has(state_code)) return cache.get(state_code) ?? null;
  // Serialise in-flight loads so two parallel callers don't both
  // decode the topojson into separate FeatureCollection instances.
  if (inFlight) await inFlight;
  if (cache.has(state_code)) return cache.get(state_code) ?? null;
  let resolveFlight!: () => void;
  inFlight = new Promise<void>((res) => {
    resolveFlight = res;
  });
  try {
    const feature = await loadStateSilhouetteUncached(state_code);
    cache.set(state_code, feature);
    return feature;
  } finally {
    resolveFlight();
    inFlight = null;
  }
}

async function loadStateSilhouetteUncached(
  state_code: string,
): Promise<StateSilhouetteFeature | null> {
  const states = await loadStates();
  const row = states.find((s) => s.eci_code === state_code);
  if (!row || !row.boundary_join_key) return null;
  const lgd = Number(row.boundary_join_key);
  if (!Number.isFinite(lgd)) return null;
  const { fc } = await loadBoundaryFromPath(
    "states/all.geojson",
    `state-silhouette-${state_code.toLowerCase()}`,
  );
  if (!fc) return null;
  const hit = fc.features.find((f) => {
    const props = (f.properties ?? {}) as StateSilhouetteProps;
    return typeof props.State_LGD === "number" && props.State_LGD === lgd;
  });
  return (hit as StateSilhouetteFeature | undefined) ?? null;
}

/** Test-only: clear the module cache so each test starts fresh. */
export function __resetForTests(): void {
  cache.clear();
  inFlight = null;
}
