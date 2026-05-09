// Scope store: the (country, state, election) tuple the user is currently
// looking at. Derives state code from the URL path so the picker stays in
// sync with deep links, and persists the last-picked election in
// localStorage so a return visit lands the user back where they were.
//
// Country and election are single-value today (India / AcGenMay2026); the
// rune-based store still surfaces them so Phase 1e's picker UI is uniform
// and so adding a second event later is one diff, not a refactor.

import { route } from "./router.svelte";

const ELECTION_KEY = "yen-gov:scope:election";

// Hard-coded for v1 — the Country dropdown is intentionally a single
// option (India). When yen-gov goes multi-country, this becomes a list
// loaded from datasets/reference/.
export const COUNTRIES = [{ code: "IN", name: "India" }] as const;

// Same for elections: only AcGenMay2026 is published today. The dropdown
// shows it as the single option; future events extend this array.
export const ELECTIONS = [
  { code: "AcGenMay2026", name: "Assembly · May 2026" },
] as const;

function loadElection(): string {
  if (typeof localStorage === "undefined") return ELECTIONS[0].code;
  const stored = localStorage.getItem(ELECTION_KEY);
  if (stored && ELECTIONS.some(e => e.code === stored)) return stored;
  return ELECTIONS[0].code;
}

let chosen_election = $state<string>(loadElection());

/** Reactive scope. Country/election are tracked here; state is derived from URL. */
export const scope = {
  get country(): string {
    return COUNTRIES[0].code;
  },
  /** ECI state code from the URL, or null on country-level routes. */
  get state(): string | null {
    // URL shapes: /s/:state, /s/:state/..., /lab/:state/...
    const m = /^\/(?:s|lab)\/([A-Z0-9]+)/.exec(route.path);
    return m ? m[1] : null;
  },
  get election(): string {
    return chosen_election;
  },
  setElection(code: string): void {
    if (!ELECTIONS.some(e => e.code === code)) return;
    chosen_election = code;
    if (typeof localStorage !== "undefined") localStorage.setItem(ELECTION_KEY, code);
  },
};
