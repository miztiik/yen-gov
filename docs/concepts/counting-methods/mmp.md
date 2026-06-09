# Counting method: Mixed-Member Proportional (MMP)

**Last Updated**: 2026-06-09

The Election Studio's MMP room is the most politically interesting PR
variant for an Indian audience. It PRESERVES every constituency winner
the citizen voted for and ADDS a state-wide list tier that compensates
parties under-represented in the FPTP outcome.

## How the simulator computes it

1. Run FPTP across the state. Each AC elects its plurality winner.
2. List-tier target = floor(constituency_count * 0.3). For a TN
   234-AC Assembly that is 70 list seats; for a 543-seat Lok Sabha
   that would be 162 list seats.
3. Ideal chamber size = constituency_count + list_target.
4. Compute the IDEAL proportional allocation across the ideal chamber
   size using Sainte-Lague divisors on state-wide party vote totals
   (NOTA excluded).
5. For each party: list_seats = max(0, ideal_seats - fptp_seats).
   Parties already over-represented by FPTP keep their constituency
   winners as OVERHANG (no list-tier compensation needed; they are
   already at or above their proportional share).
6. Final chamber size = constituency_count + sum(list_seats). The
   chamber GROWS to absorb the list tier; it does not shrink the
   constituency tier.

The per-constituency view (`by_ac`) carries the FPTP winners exactly.

## Why the chamber grows past the nominal list target

The list_seats formula is **max(0, ideal - fptp)**, not (ideal - fptp).
Negative values would mean "FPTP gave this party MORE seats than
proportional says they deserve" - and the response is NOT to take
seats away (every FPTP winner keeps their seat) but to give the other
parties more list-tier seats to bring proportionality up to fairness.
This is the OVERHANG mechanism.

Germany calls the extra seats "leveling seats" (Ausgleichsmandate); New
Zealand calls them "overhang seats". Either way, the chamber size is
not fixed - it grows with the imbalance.

## Why this is the most workable PR variant for India

- Every citizen's local MLA stays the same. The local representative
  link is preserved.
- The list-tier rescues the proportionality FPTP eats. Small parties
  excluded by FPTP geography pick up seats.
- The chamber size adjustment is a feature, not a bug. Citizens see
  EXACTLY how much the constituency tier is over-rewarding the
  dominant party (the overhang).
- Both Germany and New Zealand run elections this way at federal
  scale. India would join an established tradition rather than
  invent a new one.

## What this simulator cannot tell you

- **Two-vote ballot dynamics.** Real MMP gives each voter TWO votes
  (one for the constituency, one for the party list). Voters in
  Germany routinely SPLIT their two votes - voting for the local
  CDU candidate but the SPD list, for example. The simulator uses
  the same vote for both tiers; real two-vote MMP would produce a
  different distribution.
- **Threshold effects.** Most MMP systems impose a 5% national
  threshold below which a party gets zero list seats (preventing
  Knesset-style fragmentation). The simulator does NOT model a
  threshold; small parties at 2-3% state-wide can pick up one or
  two list seats.
- **List-tier composition.** Real MMP requires parties to publish
  ordered candidate lists before the election. The simulator
  attributes list seats to parties without naming the candidates.

## Countries that use MMP

Germany (Bundestag since 1949), New Zealand (since 1996, replaced
FPTP after a 1993 referendum), Scotland (Holyrood since 1999), Wales
(Senedd since 1999), Mexico (Chamber of Deputies), Bolivia, Lesotho.

## Further reading

- [Counting methods: overview](overview.md) - where MMP sits in the
  practical-priority trade-off table.
- [Counting methods: derivability](derivability.md) - the
  Fully-Workable tier.
- New Zealand Electoral Commission, *MMP Voting System*.
- Vowles, J. (2014), *A New Post-MMP Politics?*.
