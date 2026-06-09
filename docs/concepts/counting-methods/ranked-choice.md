# Counting method: Ranked-choice (proportional transfer)

**Last Updated**: 2026-06-09

The Election Studio's Ranked-choice room runs Instant Runoff Voting
(IRV) per constituency. India does not collect ranked ballots, so the
simulator's transfer rule is an explicit, defensible-but-untestable
assumption.

## How the simulator computes it

Per constituency (AC or PC):

1. Start with each candidate's first-preference vote count = their
   actual FPTP votes.
2. If any candidate has more than 50% of the remaining non-NOTA votes,
   they win. Stop.
3. Otherwise, eliminate the candidate with the FEWEST votes among the
   non-NOTA candidates (ties broken by candidate-name ASC).
4. Redistribute the eliminated candidate's votes to the surviving
   non-NOTA candidates in PROPORTION to those survivors' current vote
   shares (the "uniform transfer" rule).
5. Repeat from step 2 until a winner emerges or only one non-NOTA
   candidate remains.

NOTA is never eliminated and never receives transfers (it represents
abstention rather than a ranked preference).

## What this simulator cannot tell you

- **Real voter preferences.** Indian EVMs record exactly ONE vote per
  ballot. The simulator has no data on which candidate a voter would
  rank second. The uniform-transfer rule assumes second preferences
  are distributed in the same proportion as first preferences within
  the AC - defensible but un-testable.
- **Compulsory ranking.** Real IRV systems (Australia House of
  Representatives) often require voters to rank EVERY candidate. The
  simulator implicitly treats every voter's ballot as ranking only
  their first preference, with everything below distributed by the
  uniform rule.
- **Strategic voting under IRV.** IRV changes incentives. A voter
  whose first preference is a minor party may be more willing to
  express that preference if they know their second preference still
  counts. This simulator does NOT model that shift.

## Why uniform transfer rather than alternatives

Other defensible transfer rules exist:
- *Random-with-replacement* - sample the eliminated voter's likely
  second preference from a distribution.
- *Survey-informed* - use exit-poll data to estimate transfer rates.
- *Bloc transfer* - send 100% of the eliminated party's votes to
  whichever surviving party has the closest ideology.

Uniform transfer is the simplest defensible rule given the data India
publishes: it requires only the per-AC vote distribution, makes no
ideological assumption, and produces deterministic results. It is also
the rule most likely to AGREE with FPTP - in close races the FPTP
runner-up rarely overtakes the leader under uniform transfer, which
makes the simulator's output a CONSERVATIVE estimate of how different
IRV would look from the official result.

## How it compares to FPTP

In most Indian races where the leader has >40% of first preferences,
IRV produces the same winner as FPTP. The difference shows up in close
three-way races where the leader is below 40% - there the cumulative
transfer can flip the winner.

## Countries that use IRV

Australia (House of Representatives, since 1918), Ireland (President),
the United Kingdom (some local elections), most US municipal elections
that have adopted "ranked-choice voting" since 2008.

## Further reading

- Australian Electoral Commission, *Preferential voting in House of
  Representatives*.
- Reilly, B. (2001), *Democracy in Divided Societies: Electoral
  Engineering for Conflict Management*.
- FairVote.org publishes US RCV election data and methodology.
