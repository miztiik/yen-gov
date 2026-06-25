// election-tile-layout view-model (UK-style elections plan, PR-B2).
//
// Grain-agnostic join between a persisted tile-cartogram layout
// (`datasets/grapher/election_tile_layouts.json`) and a winners array
// (`AcWinner[]` today, `PcWinner[]` later). The join key is the canonical
// `unit_id` carried on every layout tile, so the same code path serves AC
// (state assembly) and PC (Parliament) cartograms.
//
// This module owns the party-colour + margin->opacity semantics (mirrors
// StateAcMap.svelte) so neither caller nor the presentational
// `<TileCartogram>` component duplicates them.
//
// PR-SYM-6f7: one-identity migration. Colour resolution now flows through
// the canonical 3-tier `getPartyColor` / `resolvePartyPalette` resolver
// (anchor -> brand -> algorithmic). Callers SHOULD pass `party_id` on each
// `TileWinnerInput`; rows without one derive a stable
// `parties.IN.<UPPER(short)>` so the resolver still degrades to
// anchor / algorithmic tiers without losing identity stability. Mirrors
// the IndiaMap (PR #587) + ElectionMap (PR #589) precedent.

import { DATA_BASE } from "../paths";
import {
  getPartyColor,
  resolvePartyPalette,
  type PartyRowForResolver,
} from "../colors/resolver";
import { renderTooltipCard } from "../boundaries/tooltip-card";

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
  /** PR-SYM-6f7: canonical `parties.IN.<SLUG>`. When absent, the resolver
   *  receives a derived `parties.IN.<UPPER(party_short)>` fallback so the
   *  anchor / algorithmic tiers stay identity-stable. */
  party_id?: string | null;
  /** PR-SYM-6f7: brand_colour mirror from dim_parties v1.1. Honoured by
   *  the resolver's `brand` tier when confidence is high/medium. */
  brand_colour_hex?: string | null;
  brand_colour_confidence?: "high" | "medium" | "low" | null;
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
  /**
   * E4 (parent plan section 25.5): the winner's canonical
   * `parties.IN.<SLUG>` id, threaded so the presentational
   * `<TileCartogram>` can apply the shared `cellTreatment` per tile
   * when the highlight mode is `"party_won"`. Null on pending tiles
   * (no winner). Optional so older fixtures / call-sites that have not
   * been re-built compile and just lose the recede effect; the existing
   * `fill` / `opacity` keep them rendering identically to v3.
   */
  winner_party_id?: string | null;
  /**
   * E4 (parent plan section 25.5): the winner's signed margin of
   * victory in pp, threaded so `<TileCartogram>` can run the stepped
   * `min_margin` filter without re-joining the upstream winners. Null
   * on pending tiles. Optional for the same back-compat reason as
   * `winner_party_id`.
   */
  margin_pct?: number | null;
  /**
   * Optional 2-letter label drawn centred inside the hex (US-style
   * tilegram convention - cf. state postal codes on a hex map). Stamped
   * by `withStateCodes` ONLY for multi-state cartograms (the national PC
   * atlas), where it reads `MH` / `TN` / `UP` so the citizen finds a
   * state without hovering. Left null on single-state cartograms (every
   * tile would carry the same code = noise) and on any caller that does
   * not run `withStateCodes`, so the presentational `<TileCartogram>`
   * renders label-free exactly as before. Purely presentational.
   */
  code?: string | null;
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
  opts: {
    selected_unit_id?: string | null;
    /** Resolve a tile's ECI state code (e.g. "S13") to its display name
     *  (e.g. "Tamil Nadu") for the card's parent-state line (R-A row 1).
     *  Injected by the caller (which holds the reactive states store) so
     *  buildTileRows stays pure / node-testable. Absent -> no parent line. */
    stateNameForCode?: (code: string) => string | null;
  } = {},
): TileRow[] {
  const byUnit = new Map<string, TileWinnerInput>();
  for (const w of winners) byUnit.set(w.unit_id, w);

  // PR-SYM-6f7: batch-resolve a palette across every distinct winning
  // party via the canonical resolver. `partyIdFor` derives a stable
  // `parties.IN.<SLUG>` when the winner row hasn't been widened with
  // `party_id` yet (PcWinner / synthetic dev fixtures); the resolver
  // still picks anchor / algorithmic colours off that key.
  const partyIdFor = (w: TileWinnerInput): string => {
    if (w.party_id) return w.party_id;
    const slug = (w.party_short ?? "UNK").trim().toUpperCase();
    return `parties.IN.${slug}`;
  };
  const rowFor = (
    pid: string,
    w: TileWinnerInput,
  ): PartyRowForResolver | null => {
    if (w.brand_colour_hex == null) return null;
    return {
      party_id: pid,
      eci_code: w.party_key,
      brand_colour: {
        hex: w.brand_colour_hex,
        confidence: w.brand_colour_confidence ?? "medium",
      },
    };
  };
  const ids: string[] = [];
  const rowMap = new Map<string, PartyRowForResolver | null>();
  const pidByUnit = new Map<string, string>();
  for (const w of winners) {
    const pid = partyIdFor(w);
    pidByUnit.set(w.unit_id, pid);
    if (!rowMap.has(pid)) {
      ids.push(pid);
      rowMap.set(pid, rowFor(pid, w));
    }
  }
  const palette = resolvePartyPalette(ids, rowMap);

  const selected = opts.selected_unit_id ?? null;

  return tiles.map((t) => {
    // Parent-state line for the card (R-A row 1). Resolved from the tile's
    // ECI state code via the caller-injected resolver so this fn stays pure;
    // absent resolver -> null -> blank parent line (back-compat).
    const stateCode = stateCodeFromUnitId(t.unit_id);
    const parentLabel =
      opts.stateNameForCode && stateCode ? opts.stateNameForCode(stateCode) : null;
    const w = byUnit.get(t.unit_id);
    if (!w) {
      return {
        unit_id: t.unit_id,
        q: t.q,
        r: t.r,
        label: t.label,
        fill: NEUTRAL_FILL,
        opacity: NEUTRAL_OPACITY,
        tooltip_html: renderTooltipCard({
          title: t.label,
          grain: t.layout_kind === "pc" ? "PC" : "AC",
          parentLabel,
          partyShort: "",
          pending: true,
        }),
        selected: t.unit_id === selected,
        pending: true,
        winner_party_id: null,
        margin_pct: null,
      };
    }
    const pid = pidByUnit.get(t.unit_id) ?? partyIdFor(w);
    const fill =
      palette.get(pid)?.hex ?? getPartyColor(pid, rowMap.get(pid) ?? null).hex;
    return {
      unit_id: t.unit_id,
      q: t.q,
      r: t.r,
      label: t.label,
      fill,
      opacity: marginToOpacity(w.margin_pct),
      tooltip_html: renderTooltipCard({
        title: t.label,
        grain: t.layout_kind === "pc" ? "PC" : "AC",
        parentLabel,
        partyShort: w.party_short,
        partyColorHex: fill,
        marginPct: w.margin_pct,
      }),
      selected: t.unit_id === selected,
      pending: false,
      winner_party_id: pid,
      margin_pct: w.margin_pct,
    };
  });
}

/**
 * Parse the ECI state code (`S##` / `U##`) embedded in a tile `unit_id`.
 *
 * Robust across both layout grains because each `unit_id` carries exactly
 * one state segment:
 *   - AC: `IN-S13-AC-2008-1`  -> `S13`
 *   - PC: `IN-PC-2008-S13-1`  -> `S13`
 *
 * Returns null when no state segment is present (e.g. synthetic dev
 * fixtures). Pure - does not depend on the row's `scope`, which is the
 * per-state code on disk but `"national"` in some test fixtures.
 */
export function stateCodeFromUnitId(unit_id: string): string | null {
  for (const seg of unit_id.split("-")) {
    if (/^[SU]\d{1,2}$/.test(seg)) return seg;
  }
  return null;
}

/**
 * Stamp a 2-letter state code (`MH`, `TN`, `UP`...) onto each tile for the
 * in-hex label, US-style tilegram convention.
 *
 * The codes are applied ONLY when the tile set spans more than one state
 * (the national PC atlas). On a single-state cartogram every hex would
 * carry the same code - pure noise - so the codes are omitted and the
 * board renders label-free. This keeps the rule in the data, not in any
 * one mount: a renderer shows codes iff the rows carry them.
 *
 * `isoForEci` resolves an ECI state code (`"S13"`) to its ISO 3166-2
 * subdivision code (`"IN-MH"`); the `IN-` prefix is stripped to the bare
 * 2-letter code. Backed by the canonical states store (`states.code2`),
 * so no state list is hardcoded here. Codes that fail to resolve (store
 * not yet loaded, unknown code) leave that tile label-free.
 *
 * Returns a new array; input rows are not mutated.
 */
export function withStateCodes(
  rows: readonly TileRow[],
  isoForEci: (eciCode: string) => string | null | undefined,
): TileRow[] {
  const distinct = new Set<string>();
  for (const r of rows) {
    const sc = stateCodeFromUnitId(r.unit_id);
    if (sc) distinct.add(sc);
  }
  if (distinct.size <= 1) {
    return rows.map((r) => ({ ...r, code: null }));
  }
  return rows.map((r) => {
    const sc = stateCodeFromUnitId(r.unit_id);
    const iso = sc ? isoForEci(sc) : null;
    const code = iso ? iso.replace(/^IN-/, "") : null;
    return { ...r, code };
  });
}
