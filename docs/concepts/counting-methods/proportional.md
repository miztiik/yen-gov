# Counting method: Proportional (Sainte-Lague, state-wide)

**Last Updated**: 2026-06-09

The Election Studio's Proportional room re-allocates the SAME ballots
that were cast under FPTP using the Sainte-Lague divisor method,
state-wide. This is a mechanical illustration of the difference between
FPTP and Proportional Representation - NOT a prediction of how voters
would behave under PR.

## How the simulator computes it

State-wide totals: sum every party's votes across every constituency in
the state (NOTA is excluded from the divisor).

Sainte-Lague divisors: 1, 3, 5, 7, 9, ...

Iterative seat allocation:

1. Number of seats to allocate = number of constituencies in the state.
2. For each round, for each party: quotient = `party.votes /
   next_divisor(party)`.
3. The party with the highest quotient wins one seat. Ties are broken
   by party_short ASC for determinism.
4. Increment that party's divisor index. Repeat until all seats are
   allocated.

The per-constituency view (`by_ac`) is intentionally empty - PR does
not bind to per-constituency outcomes; it distributes seats from the
state-wide pool. The Election Studio renders this by hiding the per-AC
margin board when the active rule is Proportional.

## Why the result looks the way it does under PR

- Smaller parties pick up seats they did not win under FPTP. A party
  with 5% of state-wide votes wins roughly 5% of state-wide seats.
- The largest single party often loses its absolute majority, requiring
  coalitions to govern.
- The Sainte-Lague divisor (1, 3, 5, ...) is more favourable to small
  parties than the alternative d'Hondt divisor (1, 2, 3, ...). NZ MMP
  and Norway use Sainte-Lague.

## What this simulator cannot tell you

- **Voter strategy.** Real voters strategise to the system. Indian
  voters under FPTP often vote for the second-best party that has a
  chance of winning rather than the party they prefer most. Under PR
  many of those voters would vote for their first preference. This
  simulator assumes ballots are unchanged - a load-bearing assumption.
- **District magnitude.** Many PR systems (Ireland STV, NZ MMP)
  allocate seats from multi-member districts, not state-wide. The
  Sainte-Lague-state-wide variant maximises proportionality but loses
  geographic specificity.

## How it compares to FPTP

The Gallagher index (Least-Squares Index) measures the gap between
vote shares and seat shares. Indian FPTP elections typically score
8 to 15 (moderately disproportional). Under perfect Sainte-Lague PR
the Gallagher index drops below 5.

## Countries that use Sainte-Lague PR

New Zealand (MMP, since 1996), Norway, Sweden, Germany (partially).
The state-wide variant is closer to the NZ list-tier than to Ireland's
STV (which is also proportional but uses ranked ballots).

## Further reading

- Gallagher, M. (1991), *Proportionality, Disproportionality and
  Electoral Systems*, Electoral Studies 10(1).
- New Zealand Electoral Commission, *MMP Voting System*.
- NCRWC Report (2002), Chapter 4 on Indian electoral reform proposals.
