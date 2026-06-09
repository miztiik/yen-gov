# Counting method: Proportional (D'Hondt, state pool)

**Last Updated**: 2026-06-09

The Election Studio's D'Hondt room re-allocates the SAME ballots cast
under FPTP using the D'Hondt divisor method, state-wide. The
mechanical shape is identical to Sainte-Lague; only the divisor
sequence differs.

## How the simulator computes it

State-wide totals: sum every party's votes across every constituency
in the state (NOTA is excluded from the divisor).

D'Hondt divisors: **1, 2, 3, 4, 5, ...** (compared to Sainte-Lague's
1, 3, 5, 7, ...).

Iterative seat allocation:

1. Number of seats to allocate = number of constituencies in the
   state.
2. For each round, for each party: `quotient = party.votes /
   next_divisor(party)` where `next_divisor = seats_awarded_so_far + 1`.
3. The party with the highest quotient wins one seat. Ties are broken
   by party_short ASC for determinism.
4. Increment that party's seat count. Repeat until all seats are
   allocated.

The per-constituency view (`by_ac`) is intentionally empty - PR does
not bind to per-constituency outcomes.

## Why the result differs from Sainte-Lague

Sainte-Lague divisors (1, 3, 5, ...) grow faster than D'Hondt
divisors (1, 2, 3, ...). The faster growth in Sainte-Lague means a
party that has already won a seat has its quotient cut MORE under
Sainte-Lague than D'Hondt - so the next seat goes to a smaller party
more often.

In effect: D'Hondt gives larger parties more seats; Sainte-Lague is
more friendly to small parties. The Election Studio shows both so the
citizen can SEE that "proportional representation" is not one rule but
a family with internal trade-offs.

## What this simulator cannot tell you

- **Voter strategy.** Real voters strategise to the system. The
  simulator holds ballots constant - a load-bearing assumption.
- **District magnitude.** Many real PR systems allocate seats from
  multi-member districts, not state-wide. The state-pool variant
  maximises proportionality but loses geographic specificity.

## Countries that use D'Hondt PR

Belgium, the Netherlands, Spain, Israel, Argentina, Brazil, Portugal,
Finland, and many other proportional democracies. D'Hondt is the most
widely-used divisor method in the world.

## Further reading

- [Counting methods: overview](overview.md) - mechanical-distinctions
  table comparing D'Hondt with Sainte-Lague and Hamilton.
- [Counting methods: derivability](derivability.md) - the
  Fully-Workable tier.
- Pukelsheim, F. (2014), *Proportional Representation: Apportionment
  Methods and Their Applications*. Springer.
