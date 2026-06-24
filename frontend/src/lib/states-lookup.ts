// Pure lookup helpers for the states-store. Extracted from
// `states.svelte.ts` in Wave-F F2 so the lookup logic is vitest-pinnable
// without standing up a Svelte-5 runes test environment. The store
// (`states.svelte.ts`) is a thin reactive wrapper around `entries` that
// delegates the actual `(code, slug) <-> StateEntry` resolution to the
// pure functions in this module.
//
// Doctrine anchor: the `legacy_id` fallback below is the F2 fix
// citizens see on the Party page. The strongholds mart still ships
// `state="delhi"` for U05 NCT of Delhi (LGD slug != canonical display
// slug); without this fallback `codeFromSlug("delhi")` returned null
// and AAP State-Assembly stronghold rows rendered as plain text. With
// it, the round-trip resolves to the canonical entity (`U05`) and the
// link builder emits `/nct-of-delhi/elections/...`. Only 3 entities
// carry `legacy_id` today (U05 Delhi = "Delhi", S10 Karnataka =
// "Mysore", S22 Tamil Nadu = "Madras"); only Delhi's legacy_id matches
// an active LGD slug, so the practical coverage is Delhi-only. JK-UT
// + A&N Islands have the same shape of bug but no legacy_id row;
// fixing those needs an upstream mart-side state-slug remap and is
// out of scope for Wave-F.

import type { StateEntry } from "./data";
import { slugify } from "./slug";

/**
 * Reverse lookup: slug -> ECI code. Returns null when not found.
 *
 * Lookup precedence (3-step chain):
 *   1) Direct `eci_code` match (case-insensitive). Preserves URL
 *      shapes like `/S22/...` that pre-date the slug rollout.
 *   2) `slugify(entry.name)` match. The canonical citizen path.
 *   3) `slugify(entry.legacy_id)` match. Backwards-compat for the LGD
 *      strongholds-mart shape (`state="delhi"` for U05).
 */
export function resolveCodeFromSlug(
  entries: readonly StateEntry[],
  slug: string | null | undefined,
): string | null {
  if (!slug) return null;
  const lc = slug.toLowerCase();
  const direct = entries.find(s => s.eci_code.toLowerCase() === lc);
  if (direct) return direct.eci_code;
  const byName = entries.find(s => slugify(s.name) === lc);
  if (byName) return byName.eci_code;
  const byLegacy = entries.find(
    s => s.legacy_id !== undefined && slugify(s.legacy_id) === lc,
  );
  return byLegacy?.eci_code ?? null;
}

/**
 * Slug for an ECI code OR an existing slug; falls back to the
 * lower-cased input. When the input is an arbitrary slug
 * (mart-emitted LGD slug, URL-derived string), we round-trip through
 * `resolveCodeFromSlug` so call sites get back the canonical display-
 * name slug (`"nct-of-delhi"`) instead of the lowercase fallback
 * (`"delhi"`) - the latter is a broken URL token in Grammar A.
 */
export function resolveSlugFromCode(
  entries: readonly StateEntry[],
  code: string | null | undefined,
): string {
  if (!code) return "";
  const hit = entries.find(s => s.eci_code === code);
  if (hit) return slugify(hit.name);
  const round = resolveCodeFromSlug(entries, code);
  if (round) {
    const canonical = entries.find(s => s.eci_code === round);
    if (canonical) return slugify(canonical.name);
  }
  return code.toLowerCase();
}

/**
 * Bare 2-letter ISO 3166-2 subdivision code for an ECI state code
 * (e.g. "S22" -> "TN", "S13" -> "MH"), derived by stripping the "IN-"
 * prefix from the entry's `iso_3166_2` ("IN-TN" -> "TN"). Returns null
 * when the code is unknown, the store has not loaded yet, or the entry
 * carries no ISO code.
 *
 * Powers the in-hex state label on multi-state tile cartograms (the
 * national PC atlas) - the US-style 2-letter tilegram convention. Pure
 * so it is vitest-pinnable without the Svelte-5 runes store; the
 * reactive wrapper (`states.code2`) just feeds it the loaded entries.
 */
export function resolveTwoLetterCode(
  entries: readonly StateEntry[],
  code: string | null | undefined,
): string | null {
  if (!code) return null;
  const iso = entries.find(s => s.eci_code === code)?.iso_3166_2;
  if (!iso) return null;
  const m = /^IN-([A-Z]{2,3})$/.exec(iso);
  return m ? m[1] : null;
}
