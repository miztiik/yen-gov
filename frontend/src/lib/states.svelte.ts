// State name resolver: ECI state code (e.g. "S22") <-> display name
// (e.g. "Tamil Nadu") <-> slug (e.g. "tamil-nadu"). Loads the current
// state+UT projection of `datasets/taxonomy/entities.json` once at module
// init (via `fetchStates()` in lib/data.ts, which now reads the canonical
// entity catalogue rather than the retired `reference/in/states.json`
// shim - see Phase C closeout in TODO/20260521-states-json-port-blocker-
// entities-ut-gap.md). Until the fetch resolves, lookups return the input
// itself (graceful degradation - the UI never shows blank).
//
// Slugs are derived deterministically from `display_name` via lib/slug.ts.
// We do not cache them in the entity row - the slug *is* the public URL
// identity of a state, so deriving it from `name` keeps the source of
// truth in one place and avoids slug/name drift across data and UI.
//
// Wave-F F2 (2026-06-15): the slug + codeFromSlug resolution logic was
// extracted to `./states-lookup.ts` so the legacy_id round-trip can be
// vitest-pinned without standing up a Svelte 5 runes test environment.
// The store below is a thin reactive wrapper - the actual lookup
// algorithm lives in the pure helpers.

import { fetchStates, type StateEntry } from "./data";
import {
  resolveCodeFromSlug,
  resolveSlugFromCode,
  resolveTwoLetterCode,
} from "./states-lookup";

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
  /**
   * Slug for a state code OR an existing slug; falls back to lower-case
   * input. Delegates to `resolveSlugFromCode` (pure helper) so the
   * legacy_id round-trip is vitest-pinned - see Wave-F F2 docstring on
   * `./states-lookup.ts`.
   */
  slug(code: string | null | undefined): string {
    return resolveSlugFromCode(entries, code);
  },
  /**
   * Reverse lookup: slug -> ECI code. Returns null when not found OR not
   * yet loaded - callers must distinguish the two via `isLoaded`.
   * Delegates to `resolveCodeFromSlug` (pure helper); see Wave-F F2
   * docstring on `./states-lookup.ts` for the 3-step lookup precedence.
   */
  codeFromSlug(slug: string | null | undefined): string | null {
    return resolveCodeFromSlug(entries, slug);
  },
  /**
   * Bare 2-letter ISO 3166-2 code for a state code (e.g. "S22" -> "TN"),
   * or null when unknown / not yet loaded. Reactive (reads the loaded
   * `entries`). Powers the in-hex label on multi-state tile cartograms
   * via `withStateCodes` - the US-style 2-letter tilegram convention.
   */
  code2(code: string | null | undefined): string | null {
    return resolveTwoLetterCode(entries, code);
  },
  /** All known states (reactive; empty until loaded). */
  get all(): readonly StateEntry[] {
    return entries;
  },
  get isLoaded(): boolean {
    return loaded;
  },
};

