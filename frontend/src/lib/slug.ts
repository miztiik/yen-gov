// Generic slug helpers for human-readable URLs.
//
// The site historically used opaque ECI codes in URLs (e.g. /s/S22). Slugs
// give us URLs like /s/tamil-nadu/ac/167-mylapore that read naturally and
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
// AC slugs prefix the ECI eci_no so the URL stays parseable without a
// reference-data lookup: `167-mylapore` → eci_no=167. The name half is
// purely cosmetic (and collision-tolerant — two ACs in the same state
// can share a name and still resolve via the numeric prefix).
//
// Party slugs are derived from the short_name field. Two parties in the
// same state can in principle share a short_name; when that happens the
// caller falls back to the ECI party code as a disambiguator (handled in
// the consuming page, not here — the slug itself stays simple).

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

/** Build a party slug from its short_name (or ECI code as a last resort). */
export function partySlug(short_name: string, eci_code?: string | null): string {
  const s = slugify(short_name);
  return s || (eci_code ? slugify(eci_code) : "party");
}
