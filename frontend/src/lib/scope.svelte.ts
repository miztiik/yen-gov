// Scope store: the (country, state) tuple the user is currently looking
// at. Country is fixed (India) for v1. State is derived from the URL path
// so the picker stays in sync with deep links.
//
// Election was removed from scope on 2026-05-11 per ADR-0023: there is no
// global "current election" in India (states poll on different cycles), so
// per-state event resolution lives in lib/election-events.ts instead.

import { route } from "./router.svelte";
import { states } from "./states.svelte";

// Hard-coded for v1 — the Country dropdown is intentionally a single
// option (India). When yen-gov goes multi-country, this becomes a list
// loaded from datasets/reference/.
export const COUNTRIES = [{ code: "IN", name: "India" }] as const;

/** Reactive scope. Country is fixed; state is derived from the URL. */
export const scope = {
  get country(): string {
    return COUNTRIES[0].code;
  },
  /**
   * ECI state code from the URL, or null on country-level routes.
   *
   * URL shapes (history routing, slug-based):
   *   /s/<state-slug>, /s/<state-slug>/..., /lab/<state-slug>/...,
   *   /compare/<state-slug>/...
   *
   * The slug captured here is resolved to the ECI code via `states`. While
   * the states reference is loading, the resolver returns null — callers
   * already handle that case (the picker just shows "All India").
   */
  get state(): string | null {
    const m = /^\/(?:s|lab|compare)\/([^/]+)/.exec(route.path);
    if (!m) return null;
    return states.codeFromSlug(m[1]);
  },
};
