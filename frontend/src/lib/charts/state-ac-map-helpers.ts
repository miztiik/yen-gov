// Pure helpers for StateAcMapD3.svelte (PR-5 of TODO/20260611-elections-off-
// maplibre-and-map-ux-plan.md), the d3-geo replacement for the legacy
// `lib/maplibre/StateAcMap.svelte`.
//
// Extracted so vitest can exercise the per-AC fill / opacity / stroke
// pipeline against fixture rows without mounting the Svelte component
// (repo vitest doctrine: node-env, no jsdom canvas, no @testing-library
// /svelte mounts).
//
// The sub-threshold marker pipeline (path bbox -> projected centroid
// -> overlay descriptor) is owned by `./india-party-map-helpers.ts` and
// reused as-is here - PR-5 imports `SUB_THRESHOLD_PX` +
// `computeSubThresholdMarkers` directly. This module covers ONLY the
// per-row paint formula that's specific to the per-state AC choropleth
// (winner-party fill, margin-ramp opacity, highlight-mode focus dim,
// override precedence). The cellTreatment fork between margin /
// party_won mode lives in `./map-highlight-utils.ts` and is shared
// with TileCartogram; PR-5's helper layer wraps it + adds the per-AC
// `highlight_eci_no` focus-dim that the legacy StateAcMap implemented
// inline.

import {
  cellTreatment,
  type HighlightMode,
  type MinMargin,
} from "./map-highlight-utils";

/**
 * The non-mode-bearing focus-dim multiplier applied to every AC whose
 * eci_no does NOT match the highlighted one. The matched AC is forced
 * to full opacity (1.0) so the per-AC drill-down's mini-map reads as a
 * "this is the seat you are on" highlight regardless of underlying
 * margin or party_won-mode opacity.
 *
 * Locked at 0.18 to match the legacy StateAcMap formula verbatim (the
 * value that paired with the margin-ramp's 0.35..0.95 band has been
 * tuned over multiple plan-doc rounds; do not retune without a
 * matching plan-doc row + design review). NB: `RECEDE_OPACITY` in
 * `map-highlight-utils.ts` is also 0.18 but is a SEPARATE constant
 * for the party_won-mode recede; the values happening to coincide is
 * not a contract.
 */
export const FOCUS_DIM_MULTIPLIER = 0.18;

/**
 * Slate-900 stroke that paints around the focused AC in highlight
 * mode. 2.5 px width sits visibly above the 0.5 px hairline internal
 * border without dominating the surrounding cell colour. Hairline
 * stroke for unfocused cells is the slate-400 the legacy MapChoropleth
 * uses for AC internal borders.
 */
export const HIGHLIGHT_STROKE_HEX = "#0f172a"; // slate-900
export const HIGHLIGHT_STROKE_WIDTH_PX = 2.5;
export const HAIRLINE_STROKE_HEX = "#94a3b8"; // slate-400
export const HAIRLINE_STROKE_WIDTH_PX = 0.5;

/**
 * Per-AC inputs that feed the cellTreatment fork. Bundles the row
 * facts (party_id, margin, winner hex) with the shared legend axis
 * (mode, selected party, min margin) and the live `--party-neutral`
 * token value read from `:root` (or `NEUTRAL_HEX_FALLBACK` in SSR).
 *
 * Pure: every field is a primitive or a hex string; no DOM, no
 * promises, no Svelte runes.
 */
export interface AcCellInput {
  /** Canonical winner party id (e.g. "parties.IN.DMK"). */
  party_id: string;
  /** Signed margin of victory in percentage points. */
  margin_pct: number;
  /** Winner party's brand/anchor hex resolved via the 3-tier palette. */
  winner_party_hex: string;
  /** The current `--party-neutral` token value (recede fill in party_won mode). */
  neutral_hex: string;
  /** Active highlight mode driven by `MapHighlightLegend`. */
  mode: HighlightMode;
  /** Selected party id (only consulted in `party_won` mode). */
  selected_party_id: string | null;
  /** Stepped margin filter (only consulted in `party_won` mode). */
  min_margin: MinMargin;
}

/**
 * Resolve the per-AC fill colour. `override` (the parent's
 * `fillsOverride[eci_no]`) wins outright when set, so the
 * PR-B8 filter-rail path keeps its bespoke recolour. Otherwise the
 * cellTreatment fork picks winner hex (margin mode + party_won match)
 * or the neutral hex (party_won miss).
 */
export function acFillForRow(
  input: AcCellInput,
  override?: string,
): string {
  if (override != null) return override;
  return cellTreatment({
    mode: input.mode,
    selected_party_id: input.selected_party_id,
    min_margin: input.min_margin,
    winner_party_id: input.party_id,
    margin_pct: input.margin_pct,
    winner_party_hex: input.winner_party_hex,
    neutral_hex: input.neutral_hex,
  }).fill;
}

/**
 * Resolve the per-AC opacity, including the `highlight_eci_no` focus
 * dim that the constituency drill-down's mini-map relies on.
 *
 * Precedence (matches the legacy StateAcMap formula verbatim):
 *
 *   1. `override` (from `opacitiesOverride[eci_no]`) ONLY when the
 *      caller is NOT focusing a single AC. The PR-B8 filter-rail
 *      passes overrides AND no `highlight_eci_no`; the per-AC
 *      drill-down passes `highlight_eci_no` AND no overrides.
 *   2. `cellTreatment` base opacity (margin ramp in margin mode;
 *      0/1 step in party_won mode).
 *   3. If `highlight_eci_no` is set:
 *        a. The matched AC gets 1.0 (forced full opacity so a
 *           razor-thin win still reads at the focus).
 *        b. Every OTHER AC gets `base * FOCUS_DIM_MULTIPLIER` (0.18)
 *           so the unfocused field recedes uniformly.
 */
export function acOpacityForRow(
  input: AcCellInput,
  eci_no: number,
  override: number | undefined,
  highlight_eci_no: number | undefined,
): number {
  if (override != null && highlight_eci_no === undefined) return override;

  const base = cellTreatment({
    mode: input.mode,
    selected_party_id: input.selected_party_id,
    min_margin: input.min_margin,
    winner_party_id: input.party_id,
    margin_pct: input.margin_pct,
    winner_party_hex: input.winner_party_hex,
    neutral_hex: input.neutral_hex,
  }).opacity;

  if (highlight_eci_no === undefined) return base;
  if (eci_no === highlight_eci_no) return 1;
  return base * FOCUS_DIM_MULTIPLIER;
}

/** Per-AC stroke for the focus highlight; hairline border otherwise. */
export interface AcStrokeStyle {
  stroke: string;
  strokeWidth: number;
}
export function acStrokeForHighlight(
  eci_no: number,
  highlight_eci_no: number | undefined,
): AcStrokeStyle {
  if (highlight_eci_no != null && eci_no === highlight_eci_no) {
    return {
      stroke: HIGHLIGHT_STROKE_HEX,
      strokeWidth: HIGHLIGHT_STROKE_WIDTH_PX,
    };
  }
  return {
    stroke: HAIRLINE_STROKE_HEX,
    strokeWidth: HAIRLINE_STROKE_WIDTH_PX,
  };
}
