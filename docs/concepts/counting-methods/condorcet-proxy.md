# Counting method: Condorcet proxy (pairwise from vote counts)

**Last Updated**: 2026-06-09

The Election Studio's Condorcet proxy room is an HONESTY MARKER. It
produces the same result as First-Past-The-Post - by construction,
because the substitution we make (vote counts for ranked preferences)
collapses the Condorcet method into a per-AC plurality count.

## Why the result equals FPTP

Real Condorcet voting asks every voter to rank every candidate.
"Candidate A is the Condorcet winner" means A beats every other
candidate in pairwise majority comparison. In a 3-way race with
ranked ballots, Condorcet can produce a winner DIFFERENT from the
FPTP winner if voters' second preferences disagree with their first.

India does not collect ranked ballots. The simulator PROXIES the
pairwise comparison by saying "A beats B in this AC if A has more
first-preference votes than B." Under this substitution, the
"beats" relation is the standard total order by vote count - which
means the Condorcet winner per AC is ALWAYS the candidate with the
highest vote count, which is exactly the FPTP winner.

Algorithmically, this rule delegates to FPTP.

## Why we still ship this room

The citizen has the right to ask "what would Condorcet voting
produce?" The honest answer from the data India collects is: exactly
what FPTP did, because the proxy CANNOT see preference reversals.

Hiding the question would imply Condorcet is unanswerable when in
fact the answer is precisely calibrated: "the proxy gives you the
same answer FPTP gives you, and that equivalence IS the finding."
The structural insight - that ranked ballots are a different DATA
PRODUCT, not just a different counting rule - is the lesson the room
teaches.

## What we cannot see

Real Condorcet voting reveals two structural objects the proxy
cannot:

**Cycles (Condorcet paradox).** Three or more voters with ranked
preferences can produce a cycle: A beats B, B beats C, C beats A.
No "majority winner" exists. The proxy under vote-count substitution
cannot produce a cycle - the rank-by-votes relation is transitive
by construction. Real Indian three-way races likely contain cycles
in real ranked preferences; the proxy is silent on them.

**Preference reversals.** A 30/40/30 three-way FPTP split says
candidate B wins by 10 points. Real ranked ballots could reveal that
A's voters prefer C to B and C's voters prefer A to B - making C
the Condorcet winner despite finishing third in FPTP. The proxy
gives this away by construction (the rank by votes is a total order,
so the FPTP winner IS the Condorcet winner under the proxy).

## What would lift this to Fully Workable

Pairwise preference data at AC grain. Either ranked ballots (most
straightforward) or specifically-targeted exit polls asking "do you
prefer A over B?" for every (A, B) pair in every AC. The exit-poll
cost is prohibitive (10 candidates per AC means 45 pair questions per
voter); ranked ballots produce the same matrix at the cost of one
extra rank-write per voter.

## Countries that use Condorcet methods

Rare in legislative elections. The Schulze method (a Condorcet variant
with cycle resolution) is used in some open-source-foundation board
elections (Debian, Wikimedia) and a few municipal pilot programmes.
Almost never used at national scale because of ballot complexity and
the cycle-resolution problem.

## Further reading

- [Counting methods: overview](overview.md) - the Condorcet paradox
  in the theoretical-constraints section.
- [Counting methods: derivability](derivability.md) - the
  Medium-Validity tier and the data-dependency that would lift this
  rule.
- Tideman, N. (2006), *Collective Decisions and Voting*. Chapter on
  Condorcet methods and cycle resolution.
