// Reactive party-colour store backed by localStorage.
//
// Three-layer model: user override (localStorage) -> anchor (curated iconic
// colour) -> algorithmic OkLCh swatch with in-use de-duplication. The pure
// resolution function lives in `party-colour.ts`; this file owns reactivity
// and the override layer.
//
// Svelte 5 rune-based: file is .svelte.ts so $state works at module scope.
// Components import `colors` and read either:
//
//   - colors.for(code, short_name?)      -- single look-up (backward compat).
//                                          Falls back to algorithmic with the
//                                          code itself as the only "in-use"
//                                          peer, so single look-ups never
//                                          collide with themselves.
//   - colors.forSet(codes)               -- recommended: pass every party the
//                                          chart is about to render. Returns
//                                          a Map<code, PartyColor> in one pass
//                                          so no two visible non-anchor
//                                          parties share a swatch.

import { partyColour } from "./party-colour";
import type { PartyColor } from "./anchors";

const STORAGE_KEY = "yen-gov:party-colors";

function loadOverrides(): Record<string, PartyColor> {
  if (typeof localStorage === "undefined") return {};
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") return parsed as Record<string, PartyColor>;
  } catch {
    // Corrupt entry -- drop it rather than crash. Settings page will rewrite on next save.
  }
  return {};
}

function persistOverrides(overrides: Record<string, PartyColor>): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides));
}

// Module-scoped rune state. Components reading `colors.overrides` get
// reactivity for free; writes through the methods below trigger re-render.
let overrides = $state<Record<string, PartyColor>>(loadOverrides());

export const colors = {
  /**
   * Resolve the effective colour for a party (override -> anchor -> algorithm).
   *
   * Backward-compatible signature. Internally treats `code` as its own in-use
   * list, so single look-ups are deterministic and never internally collide.
   * For multi-party charts prefer `colors.forSet(codes)`.
   */
  for(eci_code: string | null | undefined, short_name?: string): PartyColor {
    const key = (eci_code ?? short_name ?? "IND");
    return partyColour(key, [key], overrides);
  },

  /** Convenience: just the fill hex. */
  fill(eci_code: string | null | undefined, short_name?: string): string {
    return this.for(eci_code, short_name).fill;
  },

  /**
   * Resolve colours for a SET of parties in one pass. Use this in any chart
   * or map layer that renders multiple parties simultaneously: the returned
   * Map is built with in-use de-duplication so no two visible non-anchor
   * parties share a swatch. Lookup order is deterministic (codes are sorted
   * internally) so independent renders agree.
   */
  forSet(codes: readonly (string | null | undefined)[]): Map<string, PartyColor> {
    const out = new Map<string, PartyColor>();
    const filtered: string[] = [];
    const seen = new Set<string>();
    for (const c of codes) {
      const k = c ?? "IND";
      if (!seen.has(k)) {
        seen.add(k);
        filtered.push(k);
      }
    }
    for (const code of filtered) {
      out.set(code, partyColour(code, filtered, overrides));
    }
    return out;
  },

  /** Set or update an override; persists immediately. */
  set(eci_code: string, color: PartyColor): void {
    overrides[eci_code] = color;
    persistOverrides(overrides);
  },

  /** Remove an override (revert to default). */
  reset(eci_code: string): void {
    delete overrides[eci_code];
    persistOverrides(overrides);
  },

  /** Drop all overrides. Settings page exposes this behind a confirm. */
  resetAll(): void {
    overrides = {};
    persistOverrides(overrides);
  },

  /** Read-only view of current overrides; reactive. */
  get overrides(): Record<string, PartyColor> {
    return overrides;
  },
};

export type { PartyColor } from "./anchors";
