# Counting methods: overview

**Last Updated**: 2026-06-09

There is no neutral counting rule. Every method makes a trade-off
between proportionality, geographic representation, simplicity, and
resistance to strategic voting. This page shows the trade-offs side by
side so you can choose which lens to apply to the data on the per-method
pages.

The Election Studio currently ships twelve counting methods, grouped by
how much they can tell you from the data India publishes.

## What this hub lets you do

- Pick the right method for the question you want to ask (the practical
  trade-off table below).
- Understand the mechanical differences between methods at a glance
  (the distinctions matrix).
- Read the theoretical constraints that no counting rule can escape
  (Arrow, Gibbard-Satterthwaite, Condorcet paradox).
- Choose the validity tier that matches your tolerance for explicit
  assumptions (see [Derivability](derivability.md)).

## Key mechanical distinctions

| Property | FPTP | IRV (proportional transfer) | Condorcet | PR (D'Hondt / Sainte-Lague / Hamilton) | STV |
| --- | --- | --- | --- | --- | --- |
| Ballot type | Single mark | Ranked | Ranked | Single mark (party) | Ranked |
| Per-constituency winner | Yes | Yes | Yes | No (state pool) | Yes (multi-seat) |
| Vote-to-seat proportionality | Low | Low to medium | Low to medium | High | High |
| Strategic-voting incentive | High (tactical) | Lower (rank honestly) | Lower (rank honestly) | Medium (large-party bonus) | Lowest |
| Mechanical complexity | Lowest | Medium (per-round elimination) | High (pairwise matrix) | Medium (divisor or quota) | High (quotas + transfers) |
| Counts NOTA as a vote | Yes (in denominator) | Yes (excluded from transfers) | Excluded | Excluded | Excluded |
| Reveals coalition mechanics | No | Some (transfer flows) | No | Yes (small-party survival) | Yes (preference flows) |

## Key theoretical constraints

Every counting rule operates inside three mathematical bounds.

**Arrow's Impossibility Theorem (1951).** No ranked-ballot voting rule
can satisfy all of: unanimity, independence-of-irrelevant-alternatives,
non-dictatorship, and transitivity simultaneously. Every rule trades
off at least one. Kenneth Arrow won the Nobel for this in 1972; the
implication is that "the fairest counting rule" is a category error -
fairness is a vector of trade-offs.

**Gibbard-Satterthwaite Theorem (1973).** Any voting rule with at
least three options is either dictatorial, restricted to two outcomes,
or vulnerable to strategic voting. Citizens will sometimes vote for
their second-best choice if that maximises their preferred outcome -
under EVERY rule. The simulator's "voters cast the same ballots as
under FPTP" assumption is the practical workaround for this.

**Condorcet Paradox.** Three or more voters with ranked preferences
can produce a cycle where A beats B in pairwise comparison, B beats C,
and C beats A. No "majority winner" exists. The Condorcet proxy room
in the Election Studio cannot exhibit this paradox under its data
substitution (vote counts are a total order; cycles only emerge from
real ranked ballots).

## Practical selection trade-offs

| Your priority | Preferred system |
| --- | --- |
| Simplest ballot + administration | FPTP |
| Majority legitimacy in each seat | TRS Round 2 or IRV |
| Vote-to-seat proportionality | MMP, D'Hondt, Sainte-Lague, or Hamilton |
| Resistance to strategic voting | Condorcet methods (Schulze, Ranked Pairs) |
| Expressive ballot (preference detail) | STAR voting, Score voting |
| Multi-seat constituencies + local link | STV or Open-List PR |
| Coalition-mechanic transparency | TRS Round 2 (alliance) or IRV (alliance-transfer) |

## How to read the validity tiers

The Election Studio splits its methods into two tiers (see the picker):

- **Fully workable today.** The method is a mechanical re-arrangement
  of the data India publishes (FPTP votes per AC). No assumption
  beyond "the ballots stay as cast" is required. Examples: FPTP,
  Sainte-Lague PR, D'Hondt PR, Hamilton PR, MMP, Approval.
- **Experimental.** The method requires data India does not collect
  (ranked ballots, alliance-transfer preferences, pairwise rankings).
  The simulator holds an explicit assumption constant so the rule can
  operate; the assumption is named on the picker card and detailed on
  the per-method page.

The split is structural, not aesthetic. Hiding the tier would obscure
the citizen's right to know which views are mechanical and which rest
on an assumption.

## Further reading

- [Counting methods: derivability](derivability.md) - the data tier
  each method requires + India-specific caveats.
- [India-specific caveats](india-caveats.md) - six structural
  features (caste arithmetic, NOTA, independents, electorate variance,
  multi-cornered contests, booth capture) that affect interpretation.
- Lijphart, A. (1999), *Patterns of Democracy*. Yale University Press.
- Tideman, N. (2006), *Collective Decisions and Voting*. Ashgate.
- NCRWC Report (2002), Chapter 4: Electoral Reforms.
