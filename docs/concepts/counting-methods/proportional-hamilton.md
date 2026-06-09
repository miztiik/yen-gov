# Counting method: Largest Remainder PR (Hamilton)

**Last Updated**: 2026-06-09

The Election Studio's Hamilton room re-allocates the SAME ballots
cast under FPTP using the Hare-quota Largest-Remainder method. It is
the arithmetically simplest PR rule: each party's exact seat share is
the integer part of (vote-share x total-seats), and remaining seats
go to whoever has the largest fractional remainder.

## How the simulator computes it

1. Number of seats to allocate = number of constituencies in the
   state.
2. Hare quota = total non-NOTA votes / total seats.
3. For each party: exact share = party.votes / quota. Integer share =
   floor(exact share). Award those integer seats.
4. Sum the integer shares; the difference vs total seats is the
   number of remainder seats.
5. Sort parties by fractional remainder descending. Award one
   remainder seat per party in that order. Ties are broken by total
   votes descending, then by party_short ASC for determinism.

The per-constituency view (`by_ac`) is intentionally empty.

## What Hamilton reveals that D'Hondt and Sainte-Lague do not

The remainder step is where Hamilton differs from the divisor
methods. A small party with a 0.51 fractional remainder can take a
half-seat off a larger party that has a 0.49 remainder on its 5th or
6th seat. This produces the "small-party rescue" effect more strongly
than D'Hondt and slightly more than Sainte-Lague.

The arithmetic is also more transparent to a citizen: "5% of votes
gets you 5% of seats, plus a maybe-seat for the fractional remainder"
is easier to explain than "your votes are divided by 1, then 3, then
5, ...". When teaching PR to a non-technical audience, Hamilton is
often the starting point.

## The fascinating limit: Alabama paradox

Hamilton has one famous mathematical pathology. Increasing the total
number of seats can DECREASE a party's allocation. This is the
**Alabama paradox**, named after the 1880 US apportionment where
Alabama would have got 8 seats with a 299-seat House but only 7 with
a 300-seat House.

The paradox is rare in practice (it requires specific vote-share
combinations) but it is mathematically real. D'Hondt and Sainte-Lague
both AVOID the paradox by construction; that mathematical guarantee is
why they replaced Hamilton in most modern PR systems. The Election
Studio ships Hamilton not as a recommendation but as a clean reference
point for the trade-off.

## What this simulator cannot tell you

- **Voter strategy.** As with every PR variant, the simulator holds
  ballots constant.
- **District magnitude.** The state-pool variant maximises
  proportionality but loses geographic specificity.

## Countries that use Largest Remainder

Russia (Duma list tier), several Latin American countries (Costa
Rica, Honduras), Hong Kong, Tunisia. Less common in mature
democracies because of the Alabama paradox.

## Further reading

- [Counting methods: overview](overview.md) - mechanical-distinctions
  table comparing Hamilton with D'Hondt and Sainte-Lague.
- Balinski, M. & Young, H. P. (1982), *Fair Representation: Meeting
  the Ideal of One Man, One Vote*. The canonical text on
  apportionment paradoxes.
