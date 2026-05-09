// Reactive party-color store backed by localStorage.
//
// Two-layer model: default canonical palette (parties.default.ts) overlaid by
// user overrides persisted in localStorage under the key below. Reads merge
// the layers; writes touch only the override layer so resetting a party is a
// matter of removing its override.
//
// Svelte 5 rune-based: file is .svelte.ts so $state/$derived/$effect work at
// module scope. Components import `colors` and read `colors.for(code)`.

import { defaultColorFor, type PartyColor } from "./parties.default";

const STORAGE_KEY = "yen-gov:party-colors";

function loadOverrides(): Record<string, PartyColor> {
  if (typeof localStorage === "undefined") return {};
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") return parsed as Record<string, PartyColor>;
  } catch {
    // Corrupt entry — drop it rather than crash. Settings page will rewrite on next save.
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
  /** Resolve the effective color for a party (override → default → fallback). */
  for(eci_code: string | null | undefined, short_name?: string): PartyColor {
    if (eci_code && overrides[eci_code]) return overrides[eci_code];
    if (short_name && overrides[short_name]) return overrides[short_name];
    return defaultColorFor(eci_code, short_name);
  },

  /** Convenience: just the fill hex. */
  fill(eci_code: string | null | undefined, short_name?: string): string {
    return this.for(eci_code, short_name).fill;
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
