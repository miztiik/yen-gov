// Pure helpers for IndiaPcMapD3.svelte + StatePcMapD3.svelte (PR rows
// A + B; restoration of the PC choropleth deferred in PR #954).
//
// Both PC choropleth components share the same per-PC paint pipeline:
//   winners[] -> {unique_id -> {fill, opacity}} via `cellTreatment` plus
//   an optional `fillsOverride` / `opacitiesOverride` precedence path.
//
// Extracted here so vitest can exercise the join + paint logic against
// fixture rows without mounting the Svelte component (repo vitest
// doctrine: node-env, no jsdom canvas, no @testing-library/svelte
// mounts; mirrors the pattern in `state-ac-map-helpers.ts`).

import {
  cellTreatment,
  type HighlightMode,
  type MinMargin,
} from "./map-highlight-utils";

/** Minimal winner row consumed by the per-PC paint pipeline. The full
 *  PcWinnerRow shape exposed by IndiaPcMapD3.svelte / StatePcMapD3.svelte
 *  carries additional tooltip-only fields (winner_candidate_name,
 *  symbol_asset_path, ...) that this helper does NOT touch. */
export interface PcCellRow {
  unique_id: string;
  party_id: string;
  margin_pct: number;
  /** Winner-party brand hex resolved via the 3-tier palette by the
   *  Svelte component. */
  winner_party_hex: string;
}

/** Build the canonical PC join key ("S07_8") from a winner row's
 *  `(state_code, eci_no)` pair. Verbatim shape of the topojson's
 *  `unique_id` property. */
export function pcUniqueId(state_code: string, eci_no: number): string {
  return `${state_code}_${eci_no}`;
}

/** Per-PC paint inputs feeding the cellTreatment fork. Bundles the row
 *  facts (party_id, margin, winner hex) with the shared legend axis
 *  (mode, selected party, min margin) and the live `--party-neutral`
 *  token value. */
export interface PcCellInput {
  party_id: string;
  margin_pct: number;
  winner_party_hex: string;
  neutral_hex: string;
  mode: HighlightMode;
  selected_party_id: string | null;
  min_margin: MinMargin;
}

/** One fully-resolved per-PC paint triple (fill + opacity). Strokes
 *  are uniform on the PC choropleth (hairline slate-400) so the
 *  triple does not carry a stroke - the Svelte component renders the
 *  hairline inline. */
export interface PcCellPaint {
  fill: string;
  opacity: number;
}

/**
 * Resolve the per-PC fill colour. `override` (the parent's
 * `fillsOverride[unique_id]`) wins outright when set, so the
 * party-filter rail (Row F) can recede muted-party cells without
 * touching the row data. Otherwise the cellTreatment fork picks
 * winner hex (margin mode + party_won match) or the neutral hex
 * (party_won miss).
 */
export function pcFillForRow(
  input: PcCellInput,
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
 * Resolve the per-PC opacity. `override` (from `opacitiesOverride[
 * unique_id]`) wins when set. Otherwise the cellTreatment fork's base
 * opacity (margin ramp or party_won 0-or-1 step) carries.
 *
 * The PC choropleth does NOT carry a `highlight_eci_no` focus-dim
 * surface (only the per-AC drill-down has one); the StateAcMapD3
 * shape is intentionally NOT replicated here.
 */
export function pcOpacityForRow(
  input: PcCellInput,
  override: number | undefined,
): number {
  if (override != null) return override;
  return cellTreatment({
    mode: input.mode,
    selected_party_id: input.selected_party_id,
    min_margin: input.min_margin,
    winner_party_id: input.party_id,
    margin_pct: input.margin_pct,
    winner_party_hex: input.winner_party_hex,
    neutral_hex: input.neutral_hex,
  }).opacity;
}

/**
 * Batch helper: build the unique_id -> {fill, opacity} map driven by
 * each row's `(party_id, margin_pct, winner_party_hex)`.
 *
 * @param rows           Per-PC winner rows already palette-resolved.
 * @param shared         Shared E4 axis + neutral token.
 * @param fillsOverride  Per-uid fill override (party-filter rail).
 * @param opacitiesOverride Per-uid opacity override (party-filter rail).
 */
export function buildPcCellPaint(
  rows: readonly PcCellRow[],
  shared: {
    mode: HighlightMode;
    selected_party_id: string | null;
    min_margin: MinMargin;
    neutral_hex: string;
  },
  fillsOverride?: Record<string, string>,
  opacitiesOverride?: Record<string, number>,
): Map<string, PcCellPaint> {
  const out = new Map<string, PcCellPaint>();
  for (const r of rows) {
    const input: PcCellInput = {
      party_id: r.party_id,
      margin_pct: r.margin_pct,
      winner_party_hex: r.winner_party_hex,
      neutral_hex: shared.neutral_hex,
      mode: shared.mode,
      selected_party_id: shared.selected_party_id,
      min_margin: shared.min_margin,
    };
    out.set(r.unique_id, {
      fill: pcFillForRow(input, fillsOverride?.[r.unique_id]),
      opacity: pcOpacityForRow(input, opacitiesOverride?.[r.unique_id]),
    });
  }
  return out;
}

/** Pre-shaped reverse lookup: PartyBar's `hidden_parties` Set keys are
 *  `party_eci_code ?? party_short` but the map cells are keyed by
 *  `winner_party_id` (canonical `parties.IN.<SLUG>`). This bridge
 *  builds the `{partybar_key -> party_id}` map once per page so the
 *  route can compute `fillsOverride` / `opacitiesOverride` from the
 *  hidden set without re-walking the winners array per render. */
export interface PartyKeyToPidInput {
  party_eci_code: string | null;
  party_short: string | null;
  party_id: string;
}
export function buildPartyKeyToPid(
  winners: readonly PartyKeyToPidInput[],
): Map<string, string> {
  const out = new Map<string, string>();
  for (const w of winners) {
    const key = w.party_eci_code ?? w.party_short ?? "UNK";
    if (out.has(key)) continue;
    out.set(key, w.party_id);
  }
  return out;
}

/** Convert PartyBar's `hidden_parties` set into a canonical party_id
 *  Set. Caller uses the result to short-circuit per-row overrides
 *  (`if hidden_pids.has(winner_party_id) -> recede`). */
export function hiddenPidSet(
  hidden_party_keys: ReadonlySet<string>,
  key_to_pid: ReadonlyMap<string, string>,
): Set<string> {
  const out = new Set<string>();
  for (const k of hidden_party_keys) {
    const pid = key_to_pid.get(k);
    if (pid) out.add(pid);
  }
  return out;
}

/**
 * Map a national Parliament event slug to the PC-boundary delimitation
 * year that drives the Constituencies + Equal-seats choropleth arms:
 *   - LS 2024 and later  -> 2024 delim (numeric `<state>_<eci_no>` join).
 *   - LS 2009 / 2014 / 2019 -> 2008 delim (`<state>_<pc_name_slug>` join;
 *     canonical electoral.csv carries unreliable eci_no for delim=2008).
 *   - Pre-2009 LS events (1962 ... 2004), and any non-`general-YYYY`
 *     slug, -> null: yen-gov has no PC-level boundary layer for those
 *     delimitations, so a PC choropleth would draw an all-grey map keyed
 *     to boundaries that did not exist then.
 *
 * Returning null is the single source of truth for "this event has no
 * PC-level map arm"; the route gates the Constituencies + Equal-seats
 * toggles on `pcDelimYearForLsEvent(event) != null`.
 */
export function pcDelimYearForLsEvent(
  event_id: string | null | undefined,
): number | null {
  if (!event_id) return null;
  const m = /^general-(\d{4})$/.exec(event_id);
  if (!m) return null;
  const year = parseInt(m[1], 10);
  if (year >= 2024) return 2024;
  if (year >= 2009) return 2008;
  return null;
}
