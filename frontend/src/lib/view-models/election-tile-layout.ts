// election-tile-layout view-model (UK-style elections plan, PR-B2).
//
// Grain-agnostic join between a persisted tile-cartogram layout
// (`datasets/grapher/election_tile_layouts.json`) and a winners array
// (`AcWinner[]` today, `PcWinner[]` later). The join key is the canonical
// `unit_id` carried on every layout tile, so the same code path serves AC
// (state assembly) and PC (Lok Sabha) cartograms.
//
// This module owns the party-colour + margin->opacity semantics (mirrors
// StateAcMap.svelte) so neither caller nor the presentational
// `<TileCartogram>` component duplicates them. Colour resolution reads the
// shared `colors` store, so calling `buildTileRows` inside a Svelte
// `$derived` stays reactive to palette overrides.

import { DATA_BASE } from "../paths";
import { colors } from "../colors/store.svelte";

export interface TileLayoutRow {
  layout_kind: "ac" | "pc";
  scope: string;
  delim_year: number;
  unit_id: string;
  eci_no: number;
  q: number;
  r: number;
  label: string;
  source_id: string;
  derivation_method: string;
}

export interface ElectionTileLayoutDoc {
  $schema: string;
  $schema_version: string;
  tiles: TileLayoutRow[];
}

/** One covered (layout_kind, scope, delim_year) entry from the tiny scopes
 *  manifest. Lets the UI gate the equal-seats toggle without fetching the
 *  large layout document. */
export interface TileScopeRow {
  layout_kind: "ac" | "pc";
  scope: string;
  delim_year: number;
  tile_count: number;
}

export interface ElectionTileScopesDoc {
  $schema: string;
  $schema_version: string;
  scopes: TileScopeRow[];
}

/** A winner to paint onto a tile. Callers map their grain-specific winner
 *  (AcWinner / PcWinner) onto this shape, keyed by the canonical `unit_id`. */
export interface TileWinnerInput {
  unit_id: string;
  /** Stable party key for the colour resolver (eci code preferred). */
  party_key: string | null;
  /** Citizen-readable party short name (fallback colour key + tooltip). */
  party_short: string;
  /** Margin of victory as a percentage; null = unknown. */
  margin_pct: number | null;
}

/** A fully-resolved tile ready for the presentational `<TileCartogram>`. */
export interface TileRow {
  unit_id: string;
  q: number;
  r: number;
  label: string;
  fill: string;
  opacity: number;
  tooltip_html: string;
  selected: boolean;
  /** True when no winner joined this tile (e.g. results pending / unopposed). */
  pending: boolean;
}

const NEUTRAL_FILL = "#e2e8f0"; // slate-200 — "results pending" / no winner.
const NEUTRAL_OPACITY = 0.45;

let _cache: Promise<ElectionTileLayoutDoc> | null = null;

/** Fetch the persisted tile-cartogram layout document. Cached per page. */
export function fetchElectionTileLayouts(): Promise<ElectionTileLayoutDoc> {
  if (_cache) return _cache;
  _cache = (async () => {
    const res = await fetch(`${DATA_BASE}/grapher/election_tile_layouts.json`);
    if (!res.ok) {
      throw new Error(
        `fetch /grapher/election_tile_layouts.json failed: ${res.status} ${res.statusText}`,
      );
    }
    return (await res.json()) as ElectionTileLayoutDoc;
  })();
  return _cache;
}

let _scopesCache: Promise<ElectionTileScopesDoc> | null = null;

/** Fetch the tiny covered-scopes manifest. Cached per page. Used to decide
 *  whether to offer the equal-seats toggle for a given scope. */
export function fetchElectionTileScopes(): Promise<ElectionTileScopesDoc> {
  if (_scopesCache) return _scopesCache;
  _scopesCache = (async () => {
    const res = await fetch(`${DATA_BASE}/grapher/election_tile_scopes.json`);
    if (!res.ok) {
      throw new Error(
        `fetch /grapher/election_tile_scopes.json failed: ${res.status} ${res.statusText}`,
      );
    }
    return (await res.json()) as ElectionTileScopesDoc;
  })();
  return _scopesCache;
}

/** True when the manifest lists a layout for (layout_kind, scope, delim_year). */
export function hasLayoutForScope(
  doc: ElectionTileScopesDoc,
  sel: { layout_kind: "ac" | "pc"; scope: string; delim_year: number },
): boolean {
  return doc.scopes.some(
    (s) =>
      s.layout_kind === sel.layout_kind &&
      s.scope === sel.scope &&
      s.delim_year === sel.delim_year &&
      s.tile_count > 0,
  );
}

/** Select the tiles for one (layout_kind, scope, delim_year) layout. */
export function selectLayout(
  doc: ElectionTileLayoutDoc,
  sel: { layout_kind: "ac" | "pc"; scope: string; delim_year: number },
): TileLayoutRow[] {
  return doc.tiles.filter(
    (t) =>
      t.layout_kind === sel.layout_kind &&
      t.scope === sel.scope &&
      t.delim_year === sel.delim_year,
  );
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : c === '"' ? "&quot;" : "&#39;",
  );
}

// Map margin% -> opacity in [0.35, 0.95]; >=30% saturates. Mirrors
// StateAcMap.svelte so the tile cartogram and the geographic map agree.
function marginToOpacity(margin_pct: number | null): number {
  const m = Math.max(0, Math.min(30, margin_pct ?? 0));
  return 0.35 + (m / 30) * 0.6;
}

/**
 * Join layout tiles to winners by `unit_id` and resolve fill/opacity/tooltip.
 *
 * - Every tile produces exactly one `TileRow` (one tile = one unit).
 * - Tiles with no matching winner render in the neutral "pending" style so a
 *   dark-launched cartogram (e.g. national PC before results) still shows the
 *   full seat geography.
 * - `selected_unit_id` marks exactly that tile `selected`.
 */
export function buildTileRows(
  tiles: readonly TileLayoutRow[],
  winners: readonly TileWinnerInput[],
  opts: { selected_unit_id?: string | null } = {},
): TileRow[] {
  void colors.overrides; // reactive dependency when called inside $derived
  const byUnit = new Map<string, TileWinnerInput>();
  for (const w of winners) byUnit.set(w.unit_id, w);

  const palette = colors.forSet(
    winners.map((w) => w.party_key ?? w.party_short),
  );

  const selected = opts.selected_unit_id ?? null;

  return tiles.map((t) => {
    const w = byUnit.get(t.unit_id);
    if (!w) {
      return {
        unit_id: t.unit_id,
        q: t.q,
        r: t.r,
        label: t.label,
        fill: NEUTRAL_FILL,
        opacity: NEUTRAL_OPACITY,
        tooltip_html:
          `<div class="font-semibold">${t.eci_no}. ${escapeHtml(t.label)}</div>` +
          `<div class="text-slate-500">Results pending</div>`,
        selected: t.unit_id === selected,
        pending: true,
      };
    }
    const key = w.party_key ?? w.party_short;
    const fill = palette.get(key)?.fill ?? colors.fill(w.party_key, w.party_short);
    const marginLabel = w.margin_pct == null ? "—" : `${w.margin_pct.toFixed(1)}%`;
    return {
      unit_id: t.unit_id,
      q: t.q,
      r: t.r,
      label: t.label,
      fill,
      opacity: marginToOpacity(w.margin_pct),
      tooltip_html:
        `<div class="font-semibold">${t.eci_no}. ${escapeHtml(t.label)}</div>` +
        `<div class="text-slate-600">Winner: ${escapeHtml(w.party_short)}</div>` +
        `<div class="text-slate-500">Margin: ${marginLabel}</div>`,
      selected: t.unit_id === selected,
      pending: false,
    };
  });
}
