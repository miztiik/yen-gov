# Counting method: Ranked-choice (alliance-transfer)

**Last Updated**: 2026-06-09

The Election Studio's Ranked-choice alliance-transfer room is the
politically grounded version of IRV for India. Where the proportional
variant treats every voter's second preference as agnostic, this
variant assumes ALLIANCE DISCIPLINE: eliminated votes route to the
surviving candidate in the same alliance.

## How the simulator computes it

Per constituency:

1. Start with each candidate's first-preference vote count = their
   actual FPTP votes.
2. If any non-NOTA candidate has more than 50% of remaining non-NOTA
   votes, they win. Stop.
3. Otherwise, eliminate the candidate with the FEWEST votes among the
   non-NOTA candidates (ties broken by candidate name ASC).
4. Look up the eliminated candidate's alliance in
   `datasets/data/entities/party_alliances.csv` (keyed by
   `(party_id, period_label)`).
5. Find surviving non-NOTA candidates in the same alliance. If any
   exist: distribute the eliminated votes 100% among them, split
   proportionally to those allies' CURRENT vote shares.
6. If no survivor shares the alliance (or the eliminated candidate
   has no alliance row): fall back to the proportional transfer rule
   across ALL surviving non-NOTA candidates.
7. Repeat from step 2 until a winner emerges.

NOTA is never eliminated and never receives transfers.

## The fascinating limit

This rule assumes **100% alliance discipline** at every transfer
round. In reality alliance discipline ranges from ~60% (loose
post-poll arrangements) to ~95% (long-standing tight alliances like
the LDF or the Janata Parivar pre-1989). The 100% assumption is the
UPPER BOUND of how different IRV would look from FPTP given real
alliance arithmetic.

The proportional-transfer variant of IRV is the LOWER bound (zero
alliance discipline, just per-AC vote-share-based distribution). The
two views together BRACKET what real ranked-choice ballots would
produce in India. The divergence between them locates the seats where
alliance discipline matters most to the final result.

## What this simulator cannot tell you

- **Real second preferences.** India does not collect ranked
  ballots. The alliance-discipline assumption is structural; even
  the most coordinated alliance has individual voters who defect.
- **Non-aligned third-party transfers.** When the eliminated
  candidate has no alliance row (typically Independents or
  small regional parties), the rule falls back to proportional
  transfer. The fallback is honest but it loses the alliance signal
  for those specific votes.

## Why alliance data is per-election, not per-party

Alliances change every election cycle in India. The DMK + INC + CPI
+ CPI(M) + MDMK + VCK + ... combination that contests as the SPA
in Tamil Nadu AcGenMay2026 is different from the 2019 Lok Sabha
INDIA bloc and different again from the UPA combinations of 2009 and
2014.

The simulator keys alliance lookup on `(party_id, period_label)` so
the alliance map travels with the election event. When the CSV has
no rows for the active event, the rule falls back to the
proportional-transfer variant transparently.

## Further reading

- [Counting methods: derivability](derivability.md) - the
  Medium-Validity tier and the data-dependency that would lift this
  rule.
- [India-specific caveats](india-caveats.md) - the
  caste-arithmetic and independent-candidate caveats relevant here.
- See also the [proportional-transfer variant](ranked-choice.md).
