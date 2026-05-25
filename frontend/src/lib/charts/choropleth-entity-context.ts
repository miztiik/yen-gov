// Grain-agnostic entity wiring for IndicatorChoropleth.
//
// One of the four "seams" needed to lift the choropleth from state-only
// to grain-dispatched (PR B.05). The component used to inline:
//   - the boundary entry (INDIA_STATES)
//   - the entity loader (loadStates)
//   - reverse maps eci_code ↔ boundary_join_key, eci_code → display
// Each of those is grain-specific. This helper returns the same
// information in a unified shape so the call site iterates and renders
// once, regardless of grain.
//
// State path is intentionally byte-identical at runtime: the helper
// wraps loadStates() and projects StateRow → EntityRow with no shape
// change to the underlying data (just renamed fields). District grain
// is added by PR B.05 C3 (Behaviour); this commit (C2 — Structural)
// only carves the seam and rewires the state branch to use it.
//
// Per Fowler verdict 2026-05-25 (yenask sprint, livestock B.05): when
// the component has clear seams already carved (`geoLevel` prop,
// `loadBoundary`, `joinKeyFor`), the right move is Extract Function +
// Replace Conditional with Strategy — not a redesign. Each strategy is
// a thin projection over the existing per-grain loader.

import {
  loadStates,
  type StateRow,
} from "../view-models/states";
import {
  loadAllDistrictEntities,
  type DistrictEntity,
} from "../view-models/districts";
import { INDIA_STATES, type BoundaryEntry } from "../maplibre/sources";

/** Grain currently supported by this helper (a subset of GeoLevel). */
export type ChoroplethGrain = "state" | "district";

/**
 * One row in the choropleth's entity table, grain-agnostic. The
 * component iterates these to build fills, tooltips, reverse maps, and
 * coverage counts — without branching on grain at every site.
 *
 * Field semantics:
 *   code              — canonical id used as the join token in indicator
 *                       rows. At state grain this is ECI (e.g. "S22").
 *                       At district grain this is the LGD-anchored entity
 *                       id (e.g. "IN-S22-D567").
 *   display_name      — citizen-display label (state shortform or
 *                       district name).
 *   boundary_join_key — string value that matches the boundary feature's
 *                       `BoundaryEntry.join_property`. For both grains
 *                       this is the LGD code coerced to string.
 *   parent_display_name — null at state grain; parent state's display
 *                       name at district grain (Jony UX constraint —
 *                       district tooltips MUST carry parent state name).
 */
export interface EntityRow {
  code: string;
  display_name: string;
  boundary_join_key: string;
  parent_display_name: string | null;
}

/**
 * Per-grain choropleth wiring. The boundary entry tells MapChoropleth
 * which polygon layer to render + which property carries the join key.
 * The loader fetches the canonical entity table for the grain. The
 * citizen-surface label names this grain in coverage captions etc.
 */
export interface EntityContext {
  grain: ChoroplethGrain;
  boundary_entry: BoundaryEntry;
  /** Returns a fresh array each call (callers should not mutate). */
  load_entities: () => Promise<EntityRow[]>;
  /** Singular noun used in coverage captions: "states/UTs" or "districts". */
  coverage_noun: string;
}

// District boundary entry (national LGD-keyed polygons). Mirrors
// INDIA_STATES; the file is shipped at boundaries/in/districts/all.geojson
// (PR #267, ramSeraph LGD lineage). Property `dist_lgd` is an INTEGER
// upstream; MapChoropleth's `to-number` coercion handles the
// string-key/int-property bridge so the same string-LGD join model used
// by the state layer carries over without change.
export const INDIA_DISTRICTS: BoundaryEntry = {
  id: "india-districts",
  label: "India — districts",
  geojson_local_path: "boundaries/in/districts/all.geojson",
  geojson_url: "",
  join_property: "dist_lgd",
  attribution: INDIA_STATES.attribution,
};

function projectStateRow(s: StateRow): EntityRow {
  return {
    code: s.eci_code,
    display_name: s.boundary_join_name,
    boundary_join_key: s.boundary_join_key,
    parent_display_name: null,
  };
}

function projectDistrictEntity(d: DistrictEntity): EntityRow {
  return {
    code: d.entity_id,
    display_name: d.display_name,
    boundary_join_key: d.boundary_join_key,
    parent_display_name: d.parent_state_name,
  };
}

/**
 * Resolve the grain to its choropleth wiring. Pure, cheap, safe to call
 * inside a `$derived`. The returned `load_entities` is a closure over the
 * cached view-model loaders (loadStates / loadAllDistrictEntities), so
 * repeated calls do not re-fetch the parquet.
 *
 * Adding a new grain (e.g. "constituency") is a 3-line change here +
 * a projection function — no IndicatorChoropleth.svelte edit.
 */
export function entityContextForGrain(grain: ChoroplethGrain): EntityContext {
  if (grain === "state") {
    return {
      grain,
      boundary_entry: INDIA_STATES,
      load_entities: async () => (await loadStates()).map(projectStateRow),
      coverage_noun: "states/UTs",
    };
  }
  return {
    grain,
    boundary_entry: INDIA_DISTRICTS,
    load_entities: async () => (await loadAllDistrictEntities()).map(projectDistrictEntity),
    coverage_noun: "districts",
  };
}
