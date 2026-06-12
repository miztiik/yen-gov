// Generic slug helpers for human-readable URLs.
//
// The site historically used opaque ECI codes in URLs (e.g. /s/S22). Slugs
// give us URLs like /tamil-nadu/mylapore that read naturally and
// survive copy-paste into chat / email without losing context.
//
// Slug rules:
//   * Lowercase ASCII a-z, 0-9, dashes only.
//   * NFKD normalisation strips diacritics so non-ASCII names (e.g.
//     "Mylāpore" → "mylapore") collapse to the same slug as their plain
//     romanised forms.
//   * Multiple separators collapse to a single dash; leading/trailing
//     dashes stripped.
//
// AC slug helpers:
//   * `acSlug(eci_no, name)` composes `<eci_no>-<name>` (e.g.
//     `167-mylapore`) for the LEGACY nested route shape
//     `/<state>/elections/<event>/ac/<n-slug>`. The current bare AC
//     URL is just the name (per ADR-0037 §AC-slug).
//   * `parseAcSlug(slug)` extracts the eci_no prefix, returns null when
//     no leading integer is present.
//
// Party slug helpers (PR-0 of TODO/20260612-party-rendering-and-party-pages-plan.md):
//   * `partyIdToSlug(party_id)` derives the canonical URL slug for a
//     parties.csv `party_id` (`parties.IN.<TOKEN>`). Lowercased tail
//     with `_` -> `-`. Unique by construction (party_id is the PK).
//     Sentinel exceptions: IND -> "independent" (spelled-out citizen
//     framing per Hans verdict); NOTA -> "nota" (bare-tail default);
//     UNK -> NULL (no citizen page; resolver fallback, not an entity).
//   * `partyIdFromSlug(slug)` is the round-trip inverse — used by
//     `Party.svelte` to recover the party_id from the route param.
//   * The legacy `partySlug(short, eci_code)` helper was deleted in
//     PR-0 alongside the legacy state-scoped `/:state/party/<slug>`
//     route grammar.

export function slugify(s: string): string {
  return s
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "") // strip combining marks
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Build an AC slug like `167-mylapore`. */
export function acSlug(eci_no: number, name: string): string {
  const tail = slugify(name);
  return tail ? `${eci_no}-${tail}` : String(eci_no);
}

/**
 * Extract the eci_no prefix from an AC slug. Accepts both `167` and
 * `167-mylapore` shapes; returns null when no leading integer is present
 * so callers can route to the not-found page rather than fetch garbage.
 */
export function parseAcSlug(slug: string): number | null {
  const m = /^(\d+)(?:-|$)/.exec(slug);
  if (!m) return null;
  const n = parseInt(m[1], 10);
  return Number.isFinite(n) ? n : null;
}

// =============================================================
// Party slug — PR-0 of the party-rendering plan (rip-and-replace)
// =============================================================

/**
 * Sentinel slug overrides. Three sentinel rows exist in parties.csv
 * with `is_sentinel = true`:
 *   - `parties.IN.IND` (Independent)   -> spelled-out per Hans verdict
 *     (citizen framing: "IND" is publisher shorthand; "independent" is
 *     the noun the citizen reads).
 *   - `parties.IN.NOTA` (None of the Above) -> bare-tail "nota" suffices
 *     (citizen recognition is on the acronym).
 *   - `parties.IN.UNK` (Unresolved Party) -> NO PAGE; the resolver
 *     fallback shows `party_short_raw` as plain text per the
 *     no-silent-demotion rule (CLAUDE.md §10).
 *
 * Plus three non-sentinel disambiguators caught by the Tier-A
 * disjointness contract (`frontend/src/contracts/url-namespace-disjointness.test.ts`):
 *   - `parties.IN.AC` (Arunachal Congress) -> bare tail `ac` collides
 *     with the RESERVED `ac` chrome token (bare-AC sub-namespace
 *     marker). Spelled-out to `arunachal-congress`.
 *   - `parties.IN.GOA` (Goemcarancho Otrec Astro, Goa) -> bare tail
 *     `goa` collides with the state slug `goa`. Spelled-out to
 *     `goemcarancho-otrec-astro` (the party's full name slugified).
 *   - `parties.IN.MAHAD` (Mahakranti Dal, UP) -> bare tail `mahad`
 *     collides with the AC slug `mahad` (Maharashtra constituency
 *     no. 194). Spelled-out to `mahakranti-dal` (the party's full
 *     name slugified).
 *
 * Same citizen-framing doctrine in every case: when the bare tail
 * collides with an existing reserved token / state slug / AC slug,
 * spell out the full party name. The disjointness test pins this
 * invariant so new collisions surface at PR-time, not citizen-time.
 */
const SENTINEL_SLUG_OVERRIDES = new Map<string, string>([
  ["parties.IN.IND", "independent"],
  ["parties.IN.AC", "arunachal-congress"],
  ["parties.IN.GOA", "goemcarancho-otrec-astro"],
  ["parties.IN.MAHAD", "mahakranti-dal"],
]);

/** party_ids that have NO citizen-facing /parties/<slug> page. */
const NO_PARTY_PAGE = new Set<string>(["parties.IN.UNK"]);

/**
 * Derive the citizen-facing `/parties/<slug>` segment from a canonical
 * `party_id`. Returns null when the party_id is a no-page sentinel
 * (UNK) — callers MUST fall back to plain text rendering of
 * `party_short_raw` for that case.
 *
 * Slug shape: lowercased tail after the last `.`, with `_` -> `-`.
 * Examples:
 *   `parties.IN.INC`     -> `inc`
 *   `parties.IN.BJP`     -> `bjp`
 *   `parties.IN.JDU`     -> `jdu`            (parties.csv uses JDU not JD_U)
 *   `parties.IN.CPIM`    -> `cpim`           (parties.csv uses CPIM not CPI_M)
 *   `parties.IN.BSP_A`   -> `bsp-a`
 *   `parties.IN.CPI_ML_L` -> `cpi-ml-l`
 *   `parties.IN.IND`     -> `independent`    (sentinel override)
 *   `parties.IN.NOTA`    -> `nota`
 *   `parties.IN.UNK`     -> null             (no page)
 *
 * Unique by construction (verified 2026-06-12: 2259/2259 unique tails
 * across parties.csv). The disjointness contract test asserts this
 * invariant against the on-disk corpus.
 */
export function partyIdToSlug(party_id: string): string | null {
  if (NO_PARTY_PAGE.has(party_id)) return null;
  const override = SENTINEL_SLUG_OVERRIDES.get(party_id);
  if (override !== undefined) return override;
  const tail = party_id.includes(".")
    ? party_id.slice(party_id.lastIndexOf(".") + 1)
    : party_id;
  return tail.toLowerCase().replace(/_/g, "-");
}

/**
 * Inverse of `partyIdToSlug`. Resolves a URL slug back to its canonical
 * `party_id`. Used by `Party.svelte` to look up the parties.csv row.
 *
 * The inverse is deterministic for every slug that ROUND-TRIPS through
 * `partyIdToSlug` — namely every non-UNK row in parties.csv. The unit
 * test in `slug.test.ts` exercises the round-trip across every row.
 *
 * For an unknown slug (typo or sentinel-shape that doesn't exist) the
 * function still returns a well-formed `parties.IN.<TOKEN>` string;
 * the caller's parties.csv lookup is what fails (returns null) and the
 * route renders NotFound.
 */
export function partyIdFromSlug(slug: string): string {
  // Reverse the sentinel overrides first so `/parties/independent`
  // resolves to `parties.IN.IND` (not `parties.IN.INDEPENDENT`).
  for (const [pid, s] of SENTINEL_SLUG_OVERRIDES) {
    if (s === slug) return pid;
  }
  return `parties.IN.${slug.toUpperCase().replace(/-/g, "_")}`;
}
