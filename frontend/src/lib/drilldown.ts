// Drill-down state machine for IndicatorChoropleth (Phase 3 c3 of
// TODO/TN-GRANULAR-GEO-PLAN.md). Pure module — no DOM, no fetch — so the
// orchestration is unit-testable without mounting Svelte/maplibre.
//
// Behavioural goals (plan §Phase 3):
//   - Click on a state polygon when level === "state" advances to the
//     chosen state's districts (zoom-and-replace, NOT stacked).
//   - Click on a district advances to subdistricts; click on a subdistrict
//     advances to villages.
//   - Breadcrumb stack tracks the path; clicking a crumb returns to that
//     level (and re-clicking the active crumb is a recentre — Jony edit #1).
//   - The indicator's `min_grain` (state|district|subdistrict|village)
//     gates how deep the drill can go. Crumbs deeper than min_grain are
//     greyed and tooltip names the lowest-valid grain (Jony edit #4).
//
// State-LGD vs ECI: the boundaries loader takes LGD numeric codes
// ("33"), not ECI codes ("S22"). At v0 of this drill-down, only TN
// (LGD "33" / ECI "S22") has per-state subdistrict + village shards,
// so we hard-map at the click site. Multi-state deep drills are a
// follow-up (the loader's STATE_LGD_TO_ECI table is the single point of
// extension).

import type { GeoLevel, BoundaryFeature } from "./boundaries";
import { centroidOf } from "./boundaries";

export interface BreadcrumbCrumb {
  /** Geographic level this crumb represents. */
  level: GeoLevel;
  /** Display label (e.g. "Tamil Nadu", "Coimbatore"). */
  label: string;
  /**
   * Join-key value for the polygon at this level. For `state` this is the
   * state name (`ST_NM`); for deeper levels it's the LGD numeric code as
   * string. Null for the implicit "India" root crumb.
   */
  key: string | null;
  /** Centroid for the SVG glyph render (lng, lat). Null when unknown. */
  centroid: [number, number] | null;
}

export interface DrillState {
  /** Current rendered level. */
  level: GeoLevel;
  /** LGD code of the parent district (when level === "village"). */
  parentDistrictLgd?: string;
  /** LGD code of the state being drilled into (when deeper than country). */
  stateLgd?: string;
  /** Stack from root → current level. Always begins with the India crumb. */
  breadcrumbStack: BreadcrumbCrumb[];
}

const LEVEL_RANK: Record<GeoLevel, number> = {
  country: 0,
  state: 1,
  district: 2,
  subdistrict: 3,
  village: 4,
};

const RANK_TO_LEVEL: GeoLevel[] = ["country", "state", "district", "subdistrict", "village"];

const LEVEL_LABEL: Record<GeoLevel, string> = {
  country: "country",
  state: "state",
  district: "district",
  subdistrict: "subdistrict",
  village: "village",
};

/** Initial drill state for an indicator that opens at `geoLevel`. */
export function initialDrillState(geoLevel: GeoLevel = "state"): DrillState {
  return {
    level: geoLevel,
    breadcrumbStack: [
      { level: "country", label: "India", key: null, centroid: null },
    ],
  };
}

/** Next deeper level, or null if already at village. */
export function nextLevel(level: GeoLevel): GeoLevel | null {
  const r = LEVEL_RANK[level];
  if (r >= LEVEL_RANK.village) return null;
  return RANK_TO_LEVEL[r + 1];
}

/**
 * Returns the gating verdict for a candidate level given the indicator's
 * declared min_grain. When `min_grain` is undefined every level is allowed
 * (back-compat: existing artifacts pre-date the field).
 */
export function isLevelEnabled(
  candidate: GeoLevel,
  min_grain: GeoLevel | undefined,
): boolean {
  if (!min_grain) return true;
  return LEVEL_RANK[candidate] <= LEVEL_RANK[min_grain];
}

/**
 * Tooltip text for a greyed (min_grain-blocked) crumb. Names the lowest
 * valid grain so the citizen knows the floor without a second tap
 * (Jony edit #4 / plan §Phase 3 goal #5).
 */
export function blockedCrumbTooltip(min_grain: GeoLevel): string {
  return `this indicator is measured at ${LEVEL_LABEL[min_grain]} level, not ${LEVEL_LABEL[nextLevel(min_grain) ?? min_grain]}`;
}

export interface DrillClick {
  /** Join-key value of the clicked feature (`ST_NM` string for state level,
   *  LGD code string for deeper levels). */
  key: string | number;
  /** Display label for the breadcrumb (typically same as `key` for state-
   *  level / a name property for LGD levels). */
  label: string;
  /** Raw GeoJSON feature for centroid extraction (optional — when null the
   *  breadcrumb glyph falls back to a generic dot). */
  feature?: BoundaryFeature | null;
  /** When the current level is `state`, this is the LGD code for the
   *  clicked state (looked up from STATE_NAME_TO_ECI / its LGD inverse).
   *  Required when advancing into district level for a specific state. */
  stateLgd?: string;
}

/**
 * Compute the next drill state after a polygon click. Returns the same
 * state object (referentially equal) when the click should be a no-op
 * (e.g. already at village level, or the indicator's min_grain blocks
 * advancement). Pure: no fetch, no DOM.
 */
export function drillTo(
  state: DrillState,
  click: DrillClick,
  min_grain: GeoLevel | undefined,
): DrillState {
  const nl = nextLevel(state.level);
  if (!nl) return state;
  if (!isLevelEnabled(nl, min_grain)) return state;

  const centroid = click.feature ? centroidOf(click.feature.geometry) : null;
  const key_str = String(click.key);
  const crumb: BreadcrumbCrumb = {
    level: state.level,
    label: click.label,
    key: key_str,
    centroid,
  };

  // Clicking on a state polygon: stateLgd must be supplied (caller resolves
  // ECI → LGD via the maplibre/sources tables). For deeper levels the LGD
  // code IS the click key.
  let nextStateLgd = state.stateLgd;
  let nextParent = state.parentDistrictLgd;
  if (state.level === "state") {
    nextStateLgd = click.stateLgd;
  }
  if (state.level === "district") {
    nextParent = key_str;
  }

  return {
    level: nl,
    stateLgd: nextStateLgd,
    parentDistrictLgd: nextParent,
    breadcrumbStack: [...state.breadcrumbStack, crumb],
  };
}

/**
 * Return-to-crumb. crumbIndex 0 = root India crumb (resets to country/state
 * default); higher indices return to that crumb's level. Re-clicking the
 * active crumb (crumbIndex === stack.length) is treated as a recentre
 * signal (Jony edit #1) — caller observes the returned state's
 * `recentreSignal` flag.
 */
export function goBack(state: DrillState, crumbIndex: number): DrillState {
  // Re-click the active crumb (one past the stack tail) → recentre, no
  // level change.
  if (crumbIndex >= state.breadcrumbStack.length) {
    return state;
  }
  const trimmed = state.breadcrumbStack.slice(0, crumbIndex + 1);
  const tail = trimmed[trimmed.length - 1];
  // Determine what level we land on AFTER popping. Going back to the
  // India crumb resets to the indicator's default (state).
  let nextLvl: GeoLevel;
  if (tail.level === "country") {
    nextLvl = "state";
  } else {
    // Crumb at `state` → land on `state` (we restore the parent of the
    // current level — except the country crumb, which represents "before
    // any drill happened").
    nextLvl = tail.level;
  }
  // Pop parent / state context that no longer applies.
  let nextStateLgd = state.stateLgd;
  let nextParent = state.parentDistrictLgd;
  if (LEVEL_RANK[nextLvl] < LEVEL_RANK.village) nextParent = undefined;
  if (LEVEL_RANK[nextLvl] <= LEVEL_RANK.state) nextStateLgd = undefined;
  return {
    level: nextLvl,
    parentDistrictLgd: nextParent,
    stateLgd: nextStateLgd,
    // The clicked crumb stays in the stack as a return-to landmark; deeper
    // crumbs are popped. We trim back to crumbIndex (inclusive) but do NOT
    // include a synthetic leaf for the new current level (the new current
    // level renders without a crumb until the user drills again).
    breadcrumbStack: trimmed,
  };
}

/**
 * Compose the (level, parentDistrictLgd, stateLgd) tuple to pass to
 * `loadBoundary`. Pure projector — keeps the call site at the choropleth
 * trivial.
 */
export function loadBoundaryArgs(
  state: DrillState,
): [GeoLevel, string | undefined, string | undefined] {
  return [state.level, state.parentDistrictLgd, state.stateLgd];
}
