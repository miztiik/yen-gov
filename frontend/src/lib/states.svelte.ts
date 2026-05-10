// State name resolver: ECI state code (e.g. "S22") ↔ display name
// (e.g. "Tamil Nadu") ↔ slug (e.g. "tamil-nadu"). Loads
// `datasets/reference/in/states.json` once at module init; until the fetch
// resolves, lookups return the input itself (graceful degradation — the UI
// never shows blank).
//
// Slugs are derived deterministically from `name` via lib/slug.ts. We do
// not cache them in `states.json` — the slug *is* the public URL identity
// of a state, so deriving it from `name` keeps the source of truth in one
// place and avoids slug/name drift across data and UI.

import { fetchStates, type StateEntry } from "./data";
import { slugify } from "./slug";

let entries = $state<StateEntry[]>([]);
let loaded = $state(false);

void fetchStates()
  .then(c => {
    entries = c.states;
    loaded = true;
  })
  .catch(() => {
    // States reference is optional; lookups fall back to the code.
    loaded = true;
  });

export const states = {
  /** Display name for a state code, or the code itself if not yet loaded. */
  name(code: string | null | undefined): string {
    if (!code) return "";
    const hit = entries.find(s => s.eci_code === code);
    return hit?.name ?? code;
  },
  /** Slug for a state code (derived from `name`); falls back to lower-case code. */
  slug(code: string | null | undefined): string {
    if (!code) return "";
    const hit = entries.find(s => s.eci_code === code);
    return hit ? slugify(hit.name) : code.toLowerCase();
  },
  /**
   * Reverse lookup: slug → ECI code. Returns null when not found OR not
   * yet loaded — callers must distinguish the two via `isLoaded`.
   *
   * Backwards compatibility: if the input matches a known eci_code
   * (case-insensitive, e.g. `S22` or `s22`), it's returned as-is. This
   * means old URL shapes keep resolving while the slug shape rolls out.
   */
  codeFromSlug(slug: string | null | undefined): string | null {
    if (!slug) return null;
    const lc = slug.toLowerCase();
    const direct = entries.find(s => s.eci_code.toLowerCase() === lc);
    if (direct) return direct.eci_code;
    const byName = entries.find(s => slugify(s.name) === lc);
    return byName?.eci_code ?? null;
  },
  /** All known states (reactive; empty until loaded). */
  get all(): readonly StateEntry[] {
    return entries;
  },
  get isLoaded(): boolean {
    return loaded;
  },
};
