// Shared electoral primitives. Single source of truth so Donut, Bar,
// ParliamentArc, MarginHistogram, Psephlab and any future chart agree on
// what "majority" means.
//
// First-past-the-post convention: the majority threshold is *strictly more
// than half* the seats. For an even-sized house (e.g. TN 234) that means
// 118, not 117 — `Math.ceil(N/2)` would be wrong because 234/2 = 117 is
// only "half", not "more than half". `Math.floor(N/2) + 1` is correct for
// both even and odd N (Lok Sabha 543 → 272; TN 234 → 118).
//
// Keeping this trivially small + dependency-free so it can be unit-tested
// or imported from any layer without cycles.

export function majorityFor(total_seats: number): number {
  if (!Number.isFinite(total_seats) || total_seats <= 0) return 0;
  return Math.floor(total_seats / 2) + 1;
}

/**
 * Did a party with `seats` win an outright majority of `total_seats`?
 * Convenience over `seats >= majorityFor(total_seats)` so callers don't
 * accidentally re-derive the threshold (and forget the off-by-one).
 */
export function hasMajority(seats: number, total_seats: number): boolean {
  return seats >= majorityFor(total_seats);
}
