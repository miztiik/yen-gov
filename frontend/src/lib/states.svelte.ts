// State name resolver: ECI state code (e.g. "S22") → display name
// (e.g. "Tamil Nadu"). Loads `datasets/reference/in/states.json` once at
// module init; until the fetch resolves, lookups return the code itself
// (graceful degradation — the UI never shows blank).
//
// Generality: nothing here is TN- or May-2026-specific. Any state code
// listed in states.json (whole 36-state set when bootstrapped) resolves
// transparently. Keeping the resolver in one module means future panels
// (admin, Compare's election picker, etc.) stay consistent.

import { fetchStates, type StateEntry } from "./data";

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
  /** All known states (reactive; empty until loaded). */
  get all(): readonly StateEntry[] {
    return entries;
  },
  get isLoaded(): boolean {
    return loaded;
  },
};
