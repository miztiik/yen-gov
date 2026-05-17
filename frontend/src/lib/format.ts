// Citizen-readable population formatter for the unmapped-region chip
// (frontend/src/lib/UnmappedRegionChips.svelte). The chip shows a small
// population anchor next to each UT's value so the citizen can read the
// indicator's per-capita weight against an absolute size — Hans's
// governance ground truth: tiny denominators flip per-capita rankings,
// the citizen needs to see why.
//
// Output convention matches the prevailing publisher shorthand the
// median Indian citizen already reads on news graphics:
//
//   < 1_000      → exact integer            ("640")
//   < 1_000_000  → "Nk" rounded to nearest k ("64k", "274k", "381k")
//   ≥ 1_000_000  → "N.NM" one decimal       ("1.2M")
//
// The chip component appends " people" — the noun lives in the call site
// because some contexts (tooltips, accessibility-adjacent strings) want
// the bare number.

export function formatPopulationShort(people: number | null | undefined): string {
  if (people == null || !Number.isFinite(people) || people < 0) return "—";
  if (people < 1_000) return String(Math.round(people));
  if (people < 1_000_000) return `${Math.round(people / 1_000)}k`;
  const m = people / 1_000_000;
  // One decimal, no trailing ".0" — `1_000_000 → "1M"`, `1_240_000 → "1.2M"`.
  const oneDp = Math.round(m * 10) / 10;
  return Number.isInteger(oneDp) ? `${oneDp}M` : `${oneDp.toFixed(1)}M`;
}
