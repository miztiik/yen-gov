// Pure helpers for the parent-plan-25.5 highlight modes shared by
// StateAcMap (maplibre choropleth) and TileCartogram (SVG hex
// cartogram). ONE legend component (MapHighlightLegend.svelte) drives
// BOTH map surfaces; both surfaces call `cellTreatment` per row so the
// per-cell fill / opacity / stroke is computed identically.
//
// E4 doctrine (parent plan section 25.5):
//   - Mode A ("margin", default): fill = winner colour; opacity ramps
//     0.35..0.95 over the [0, 30] pp margin window via `marginOpacity`.
//   - Mode B ("party_won"): pick ONE party via legend pill. Cells WON
//     by that party (with margin >= `min_margin`) get the party
//     colour at full opacity. Non-matching cells RECEDE to
//     `var(--party-neutral)` at low opacity + the existing hairline
//     internal border carries the cell outline.
//
// Pure, deterministic, node-friendly - every branch is unit-tested
// in the sibling `.test.ts`. Component-level shape assertions live in
// the Playwright e2e spec (per repo vitest doctrine, frontend vitest
// is node-env with no DOM, no @testing-library/svelte).

export type HighlightMode = "margin" | "party_won";

/** Stepped slider domain for the party_won mode sub-filter (percentage
 *  points). "0" means no filter (every win by the selected party stays
 *  fully filled). 10/20/30 progressively recede narrower wins. */
export const MIN_MARGIN_STEPS = [0, 10, 20, 30] as const;
export type MinMargin = (typeof MIN_MARGIN_STEPS)[number];

/** Recede opacity for non-matching cells in party_won mode. Mid of the
 *  ~0.15-0.2 band the spec calls for. */
export const RECEDE_OPACITY = 0.18;

/** Fallback neutral hex when the live `--party-neutral` token cannot
 *  be read (SSR / no DOM). Matches the literal in app-tokens.css. */
export const NEUTRAL_HEX_FALLBACK = "#cbd5e1"; // slate-300

/**
 * Margin-ramp opacity formula from the E4 spec.
 *
 * `opacity = 0.35 + clamp(|margin|, 0, 30) / 30 * 0.6`
 *
 * Saturates at 0.95 once the margin is 30pp or more; floors at 0.35
 * for knife-edge wins so a 0pp result still reads, never disappears.
 * `margin_pct` is treated as |signed|; a -5pp margin is treated the
 * same as +5pp (the winner is still the winner).
 */
export function marginOpacity(margin_pct: number | null | undefined): number {
  const m = Math.max(0, Math.min(30, Math.abs(margin_pct ?? 0)));
  return 0.35 + (m / 30) * 0.6;
}

/** The current shared highlight state driven by MapHighlightLegend. */
export interface HighlightState {
  mode: HighlightMode;
  selected_party_id: string | null;
  min_margin: MinMargin;
}

/** Reasonable starting state for any consumer that has not persisted
 *  anything: margin mode, no party, no margin filter. */
export const DEFAULT_HIGHLIGHT_STATE: HighlightState = {
  mode: "margin",
  selected_party_id: null,
  min_margin: 0,
};

/** Computed per-cell paint triple. */
export interface CellTreatment {
  /** Fill colour as a hex string (or any maplibre / SVG accepted value). */
  fill: string;
  /** Opacity in [0, 1]. */
  opacity: number;
  /**
   * When set, the cell carries this hairline stroke; the recede style
   * uses the neutral token so its outline stays the same calm grey as
   * the fill. `null` = no stroke override (the rendering surface keeps
   * its default internal-border treatment).
   */
  stroke: string | null;
}

/** Inputs to `cellTreatment` per row. */
export interface CellTreatmentInput {
  /** Active highlight mode driven by the shared legend. */
  mode: HighlightMode;
  /** Selected party id (only consulted in `party_won` mode). */
  selected_party_id: string | null;
  /** Stepped margin filter (only consulted in `party_won` mode). */
  min_margin: MinMargin;
  /** The cell's winner party id (canonical `parties.IN.<SLUG>`). */
  winner_party_id: string | null;
  /** The cell's signed margin of victory. */
  margin_pct: number | null;
  /** The winner-party hex resolved via the 3-tier party palette. */
  winner_party_hex: string;
  /** Resolved `--party-neutral` token value for the recede fill. */
  neutral_hex: string;
}

/**
 * Compute the fill / opacity / stroke triple for one cell, given the
 * shared highlight state + the cell's own data. Pure: both StateAcMap
 * and TileCartogram call this per row so the visual contract is
 * identical across both surfaces.
 *
 * Cases:
 *  - mode === "margin"            => winner colour @ marginOpacity, no stroke.
 *  - mode === "party_won" + match => winner colour @ 1.0, no stroke.
 *  - mode === "party_won" + miss  => neutral_hex @ RECEDE_OPACITY + neutral_hex stroke.
 *
 * A match in party_won mode is: `selected_party_id != null
 *   && winner_party_id === selected_party_id
 *   && |margin_pct| >= min_margin`.
 */
export function cellTreatment(input: CellTreatmentInput): CellTreatment {
  const {
    mode,
    selected_party_id,
    min_margin,
    winner_party_id,
    margin_pct,
    winner_party_hex,
    neutral_hex,
  } = input;

  if (mode === "margin") {
    return {
      fill: winner_party_hex,
      opacity: marginOpacity(margin_pct),
      stroke: null,
    };
  }

  // mode === "party_won"
  const margin_abs = Math.abs(margin_pct ?? 0);
  const matches =
    selected_party_id != null &&
    winner_party_id != null &&
    winner_party_id === selected_party_id &&
    margin_abs >= min_margin;

  if (matches) {
    return {
      fill: winner_party_hex,
      opacity: 1,
      stroke: null,
    };
  }

  return {
    fill: neutral_hex,
    opacity: RECEDE_OPACITY,
    stroke: neutral_hex,
  };
}

/**
 * Read the live `--party-neutral` token from the running theme. Used
 * by callers that have a DOM handle; tests (node-env) skip this and
 * pass `NEUTRAL_HEX_FALLBACK` explicitly into `cellTreatment`.
 */
export function readNeutralHex(el: Element | null): string {
  if (
    typeof getComputedStyle === "undefined" ||
    el == null
  ) {
    return NEUTRAL_HEX_FALLBACK;
  }
  try {
    const v = getComputedStyle(el).getPropertyValue("--party-neutral").trim();
    return v || NEUTRAL_HEX_FALLBACK;
  } catch {
    return NEUTRAL_HEX_FALLBACK;
  }
}

// --- Legend reducer ----------------------------------------------------
// Encodes the user-facing transitions the MapHighlightLegend supports
// as pure functions so vitest can cover every branch without a DOM.
// The Svelte component just forwards events to these reducers and
// re-emits the new state via `on_change`.

export type LegendAction =
  | { kind: "set_mode"; next: HighlightMode }
  | { kind: "tap_party"; party_id: string }
  | { kind: "set_min_margin"; next: MinMargin };

export interface LegendAdvanceOpts {
  /** When set, a "set_mode" -> "party_won" transition without a
   *  pre-selected party auto-picks this first party. Lets the citizen
   *  see the recede effect immediately instead of an all-neutral map. */
  first_party_id?: string | null;
}

/**
 * Reducer for the shared legend. Pure: no I/O, no Svelte runes.
 *
 * Transitions:
 *  - set_mode("party_won")  : if no party selected and `first_party_id`
 *                              is supplied, auto-pick it (so the recede
 *                              effect is visible on flip). Otherwise
 *                              leave selected_party_id alone.
 *  - set_mode("margin")     : preserve selected_party_id (round-trip
 *                              friendly - re-flipping to party_won keeps
 *                              the previous selection).
 *  - tap_party(p)           : if currently selected, clear + revert to
 *                              margin mode. Else select p + force mode
 *                              to "party_won".
 *  - set_min_margin(n)      : just set; only meaningful in party_won
 *                              mode but the slider is hidden in margin
 *                              mode (legend concern, not reducer).
 */
export function advanceLegendState(
  state: HighlightState,
  action: LegendAction,
  opts: LegendAdvanceOpts = {},
): HighlightState {
  switch (action.kind) {
    case "set_mode": {
      if (action.next === state.mode) return state;
      if (action.next === "party_won" && state.selected_party_id == null) {
        return {
          mode: "party_won",
          selected_party_id: opts.first_party_id ?? null,
          min_margin: state.min_margin,
        };
      }
      return {
        mode: action.next,
        selected_party_id: state.selected_party_id,
        min_margin: state.min_margin,
      };
    }
    case "tap_party": {
      if (state.selected_party_id === action.party_id) {
        return {
          mode: "margin",
          selected_party_id: null,
          min_margin: state.min_margin,
        };
      }
      return {
        mode: "party_won",
        selected_party_id: action.party_id,
        min_margin: state.min_margin,
      };
    }
    case "set_min_margin": {
      if (action.next === state.min_margin) return state;
      return {
        mode: state.mode,
        selected_party_id: state.selected_party_id,
        min_margin: action.next,
      };
    }
  }
}
