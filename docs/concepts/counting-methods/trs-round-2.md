# Counting method: Top-2 Runoff (proportional transfer)

**Last Updated**: 2026-06-09

The Election Studio's Top-2 Runoff room runs France's presidential
model per constituency. Only the top 2 first-preference candidates
survive to the runoff; the eliminated candidates' votes redistribute
to the survivors in proportion to those two's first-round shares.

## How the simulator computes it

Per constituency:

1. Sort non-NOTA candidates by first-preference votes descending.
2. The top 2 candidates survive to round 2. Every other non-NOTA
   candidate is eliminated.
3. Sum the eliminated candidates' votes.
4. Survivor 1 share = s1.votes / (s1.votes + s2.votes).
5. Distribute the eliminated total to s1 and s2 proportionally to
   their first-round shares.
6. The winner is whichever survivor has the higher post-transfer
   total (ties by candidate name ASC).

NOTA is excluded from the top-2 selection and from redistribution
(NOTA votes are "exhausted" in round 2).

## Why this variant is the LOWER bound on the real outcome

The proportional-transfer rule treats eliminated voters as
politically agnostic between the two survivors. In Indian practice,
alliance affiliation strongly predicts second-round preference. The
proportional rule under-rewards alliance coordination; the alliance
variant of this rule (Top-2 Runoff alliance) over-rewards it.

Together, the two views BRACKET the real round-2 outcome between
zero coordination (proportional) and total coordination (alliance).

## The fascinating limit

Under proportional transfer, the winner of round 2 is ALWAYS the
candidate with more first-round votes - the larger top-2 share in
round 1 means a larger share of the redistributed votes too. So this
rule never flips a seat from the FPTP winner. Its informational value
is therefore in the MARGIN, not the winner: it shows how much the
eliminated bloc would have to vote ASYMMETRICALLY (against
proportionality) to flip the seat.

The alliance-variant rule flips seats; this one quantifies how much
flipping is structurally possible.

## What this simulator cannot tell you

- **Asymmetric voter preferences.** In real round-2 elections,
  eliminated voters often have ideological or caste-based reasons to
  break asymmetrically toward one survivor. The simulator's
  proportional rule is the conservative null hypothesis - "no
  systematic preference" - against which the alliance variant is the
  alternative.
- **Strategic ballot-spoiling in round 1.** Real two-round systems
  see voters strategically wasting their first-round vote on a
  hopeless candidate to "send a message". The simulator holds the
  first-round ballot constant.

## Countries that use Two-Round Runoff

France (presidential elections since 1965, legislative elections),
Brazil (presidential), Argentina (presidential, modified), most
Francophone African countries, Iran (some elections). The
two-round variant is the most common runoff system worldwide.

## Further reading

- [Counting methods: derivability](derivability.md) - the
  Medium-Validity tier.
- See also the [alliance-variant of this rule](trs-round-2-alliance.md).
- [India-specific caveats](india-caveats.md) - the
  caste-arithmetic caveat is particularly relevant.
