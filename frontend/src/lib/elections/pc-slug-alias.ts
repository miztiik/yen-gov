// PC name-slug alias table (Row 5b of TODO/20260616-map-geometry-rip-and-palette-plan.md).
//
// After the Row 3 map-geometry rip every Lok Sabha event joins against the
// ONE national 2024 PC geometry. LS 2009-2019 events join by name-slug
// (`<state_ut_code>_<slugify(pc_name)>`) against the geometry's
// `pc_slug_uid`. ~96% match exactly; the residual misses are seats the
// 2024 geometry kept under their OLD English name while canonical
// electoral.csv carries the newer official name (the 2014 Karnataka city
// renamings) or a spelling variant.
//
// This table maps the canonical (electoral.csv) name-slug uid to the
// geometry's name-slug uid for those SAFE, same-seat cases ONLY. It does
// NOT contain genuine-change seats (Assam 2023 re-delimitation:
// Mangaldoi/Kaziranga/Sonitpur/Autonomous-District; J&K 2022:
// Anantnag→Anantnag-Rajouri) — those have a DIFFERENT polygon shape, so
// painting an old result on the new polygon would be a wrong-seat colour
// (Hans doctrine). They correctly stay grey (safe-by-construction).
//
// Each entry is a documented 1:1 continuity:
//   - Karnataka (S10): the Karnataka Official Languages (Amendment) Act
//     2014 renamings — Bangalore→Bengaluru, Bellary→Ballari,
//     Belgaum→Belagavi, Gulbarga→Kalaburagi, Mysore→Mysuru,
//     Shimoga→Shivamogga, Tumkur→Tumakuru, Bijapur→Vijayapura — same PC
//     polygon, official city rename. Plus the Udupi-Chikmagalur spelling.
//   - Jharkhand (S27): Palamau↔Palamu spelling.
//   - Telangana (S29): Mahabubnagar↔Mahbubnagar spelling (the distinct
//     Mahabubabad seat is NOT aliased).
//   - UTs: Andaman & Nicobar Islands↔Andaman-Nicobar (suffix);
//     Dadar↔Dadra (DNH spelling, same PC); Puducherry↔Pondicherry
//     (2006 official rename).
//
// Coverage receipt (measured 2026-06-16, frontend slugify rule): without
// this table 522/544 = 96.0% of delim=2008 PC name-slugs bind; with it
// 539/544 = 99.1% bind. The remaining 5 are the genuine-change tail above.
//
// Keyed + valued as full `<state_ut_code>_<name-slug>` uids so the lookup
// is a single O(1) map hit and the state prefix prevents cross-state
// shadowing. Applying it to a numeric 2024 uid (`S07_5`) is a no-op (no
// numeric key is present), so the call site can apply it unconditionally.

export const PC_SLUG_UID_ALIASES: Readonly<Record<string, string>> = Object.freeze({
  // Karnataka — 2014 official city renamings (same PC polygon).
  "S10_bengaluru-central": "S10_bangalore-central",
  "S10_bengaluru-north": "S10_bangalore-north",
  "S10_bengaluru-rural": "S10_bangalore-rural",
  "S10_bengaluru-south": "S10_bangalore-south",
  "S10_ballari": "S10_bellary",
  "S10_belagavi": "S10_belgaum",
  "S10_kalaburagi": "S10_gulbarga",
  "S10_mysuru": "S10_mysore",
  "S10_shivamogga": "S10_shimoga",
  "S10_tumakuru": "S10_tumkur",
  "S10_vijayapura": "S10_bijapur",
  "S10_udupi-chikkamagaluru": "S10_udupi-chikmagalur",
  // Jharkhand / Telangana — spelling variants (same PC).
  "S27_palamau": "S27_palamu",
  "S29_mahabubnagar": "S29_mahbubnagar",
  // UTs — suffix / spelling / official rename (same PC).
  "U01_andaman-nicobar-islands": "U01_andaman-nicobar",
  "U03_dadar-nagar-haveli": "U03_dadra-nagar-haveli",
  "U07_puducherry": "U07_pondicherry",
});

/**
 * Resolve a PC name-slug uid to its 2024-geometry equivalent via the
 * safe-alias table. Returns the input unchanged when no alias applies
 * (the common case, including every numeric 2024 uid). Pure.
 */
export function aliasPcSlugUid(uid: string): string {
  return PC_SLUG_UID_ALIASES[uid] ?? uid;
}
