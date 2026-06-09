# Counting method: Top-2 Runoff (alliance pool)

**Last Updated**: 2026-06-09

The Election Studio's Top-2 Runoff alliance room applies the France
presidential model with ALLIANCE DISCIPLINE: eliminated votes pool to
the surviving candidate in the same alliance. Together with the
proportional-transfer variant, the two views BRACKET the real round-2
outcome between zero coordination and total coordination.

## How the simulator computes it

Per constituency:

1. Sort non-NOTA candidates by first-preference votes descending. The
   top 2 survive to round 2.
2. For each eliminated candidate:
   a. Look up the candidate's alliance in
      `datasets/data/entities/party_alliances.csv`.
   b. If one of the top 2 shares that alliance: route 100% of the
      eliminated candidate's votes to that survivor.
   c. If BOTH top 2 share the alliance (rare; happens within a single
      bloc): split proportionally to their first-round shares.
   d. If NEITHER top 2 shares the alliance (or the eliminated
      candidate has no alliance row): fall back to the proportional
      rule between s1 and s2.
3. The winner is whichever survivor has the higher post-transfer
   total.

NOTA is excluded throughout.

## The fascinating limit

This rule assumes **100% alliance discipline**. In reality alliance
discipline ranges from ~60% to ~95%. The 100% assumption is the UPPER
BOUND of how different the runoff outcome would look from FPTP given
real alliance coordination.

When you see a seat flip from FPTP under this rule, the FPTP plurality
is below 50% AND the eliminated bloc is large enough AND the bloc has
alliance affiliation that points toward the runner-up rather than the
leader. All three conditions must hold; the flip is structurally
informative.

## What this simulator cannot tell you

- **Real coordination breakdowns.** Even tight alliances see some
  voters defect; the LDF and DMK alliances typically hold 85-95%,
  not 100%.
- **Conditional alliance discipline.** Some alliance voters discipline
  is conditional on their candidate's elimination position; LDF
  voters whose candidate finishes a strong 3rd may transfer
  reliably, while those whose candidate finishes a distant 6th may
  not. The simulator treats all eliminated alliance voters
  identically.

## Why alliance data is per-election, not per-party

See [Ranked-choice (alliance-transfer)](ranked-choice-alliance.md)
for the rationale. The same `(party_id, period_label)` keying applies
here.

When the CSV has no rows for the active event, this rule degrades
transparently to Top-2 Runoff (proportional).

## Further reading

- [Counting methods: derivability](derivability.md) - the
  Medium-Validity tier.
- See also the [proportional-transfer variant](trs-round-2.md).
- [India-specific caveats](india-caveats.md) - alliance arithmetic
  + the caste-bloc caveat.
