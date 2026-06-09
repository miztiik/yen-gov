# Counting method: Borda Count (rank-based scoring)

**Last Updated**: 2026-06-09

The Election Studio's Borda Count room is a positional rank-based
system. Each voter ranks every candidate; the candidate at position i
in a voter's ballot earns (N - i) points where N is the candidate
count.

India does not collect ranked ballots, so the simulator PROXIES each
voter's ranking with the FPTP rank order within their constituency.
Every voter is assumed to share the AC-level FPTP rank order as their
preference order.

## How the simulator computes it

State-wide allocation:

1. Per constituency: sort non-NOTA candidates by first-preference
   votes descending. The candidate at position i (0-indexed) earns
   `(n - i)` points where n is the non-NOTA candidate count in that
   AC.
2. Each rank position contributes ONE UNIT to the party's state-wide
   Borda total - independent of how many voters that AC contains.
3. Allocate `total_seats` (= constituency count) proportionally to
   party Borda totals using Sainte-Lague divisors.

The per-constituency view (`by_ac`) is intentionally empty - Borda
under our proxy is a state-wide PR-shaped rule.

## The fascinating limit

Two assumptions deserve attention.

**First, the rank-from-FPTP proxy.** A voter's FPTP rank order is
not their genuine preference order. A DMK voter whose third-ranked
candidate is BJP and second-ranked is AIADMK may not actually prefer
AIADMK over BJP - the FPTP rank reflects their VOTE, not their full
preference order. The simulator's Borda result is therefore the Borda
result that WOULD obtain if voters' ranked preferences happened to
match the per-AC FPTP vote order. Read it as a lower bound on how
different Borda would look from FPTP with real ranked ballots.

**Second, the equal-AC weighting.** One rank-position unit per AC,
regardless of how many voters that AC contains. A 50,000-voter AC and
a 3,000,000-voter AC contribute the same Borda mass per candidate
position. This isn't a flaw to apologise for - it's the structural
cost Borda PAYS for rewarding broad acceptability over plurality
strength. A vote-weighted Borda would collapse to a vote-share
average; the rank-position version is what makes Borda Borda.

## Why we still ship the Borda view

The Borda rule rewards candidates who finish 2nd or 3rd everywhere
over candidates who finish 1st somewhere and last elsewhere. In
multi-party Indian races this surfaces "consensus" parties that have
broad acceptability without plurality wins.

The cleanest example: in a 6-AC fixture where party A wins every AC
(FPTP A=6, others=0) but party C is consistently 2nd, Borda gives A=3,
C=2, B=1 instead of FPTP's lopsided A=6. The 2nd-place mass earns
seats it could never earn under plurality counting.

## Countries that use Borda Count

Slovenia (national minority MPs), Nauru (modified). Rare at national
scale because of strategic-voting vulnerability (push a disliked
candidate to the bottom and your preferred candidate's relative
position rises mechanically).

## Further reading

- [Counting methods: overview](overview.md) - the Gibbard-Satterthwaite
  theorem and Borda's strategic-voting vulnerability.
- [Counting methods: derivability](derivability.md) - the
  Medium-Validity tier and the data-dependency that would lift this
  rule.
- [India-specific caveats](india-caveats.md) - the
  electorate-variance caveat is particularly relevant.
- Saari, D. (2001), *Decisions and Elections: Explaining the
  Unexpected*. Cambridge University Press.
