// Pure ordering for the ParliamentArc hemicycle (extracted so it can be
// unit-tested without rendering the component).
//
// Without an alliance resolver the seat-bearing parties are ordered by
// seats descending (chamber-left tradition: the largest party fills from
// the left). With `alliance_of` the parties are grouped into alliance
// blocs - blocs ordered by total seats descending, parties within a bloc
// by seats descending, unaligned parties trailing last - so allied parties
// sit together and a bloc crossing the majority midline reads at a glance.

/** Minimal shape the ordering needs; `PartyResult` satisfies it. */
export interface ArcOrderable {
  seats_won: number;
  party_short: string;
}

const UNALIGNED = "\u0000__unaligned__";

/** Order seat-bearing parties left -> right for the hemicycle. Pure. */
export function orderArcParties<T extends ArcOrderable>(
  parties: readonly T[],
  alliance_of?: (party: T) => string | null,
): T[] {
  const active = parties.filter((p) => p.seats_won > 0);
  const bySeats = (a: T, b: T): number =>
    b.seats_won - a.seats_won || a.party_short.localeCompare(b.party_short);

  if (!alliance_of) return active.slice().sort(bySeats);

  const groups = new Map<string, { seats: number; parties: T[] }>();
  for (const p of active) {
    const key = alliance_of(p) ?? UNALIGNED;
    let g = groups.get(key);
    if (!g) {
      g = { seats: 0, parties: [] };
      groups.set(key, g);
    }
    g.seats += p.seats_won;
    g.parties.push(p);
  }

  const orderedGroups = [...groups.entries()].sort(([ka, ga], [kb, gb]) => {
    if (ka === UNALIGNED) return 1;
    if (kb === UNALIGNED) return -1;
    return gb.seats - ga.seats || ka.localeCompare(kb);
  });

  const out: T[] = [];
  for (const [, g] of orderedGroups) out.push(...g.parties.slice().sort(bySeats));
  return out;
}
