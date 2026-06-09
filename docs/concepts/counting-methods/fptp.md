# Counting method: First-Past-The-Post (FPTP)

**Last Updated**: 2026-06-09

First-Past-The-Post is the counting rule India uses for every Lok Sabha
seat and every Vidhan Sabha seat. The candidate with the most votes in a
constituency wins that seat; the party with the most seats forms the
government. This is the OFFICIAL rule. The Election Studio uses it as
the baseline against which every other method is compared.

## How it works

Per constituency (AC or PC):

1. Sum every candidate's votes.
2. The candidate with the highest count wins.
3. Ties are broken by candidate-name ASC for determinism (in practice
   the Election Commission settles ties by lot; that is not modelled).

Per state / national tally:

1. Count the wins per party across all constituencies.
2. The party with the majority (or the largest plurality + a coalition)
   forms the government.

## What this rule guarantees

- A single winner per constituency.
- A clear ballot: voters pick exactly one candidate.
- Geographic representation: every elected MLA / MP represents a defined
  place.

## What this rule does NOT guarantee

- Seat shares matching vote shares - a party with 40% of votes can win
  60% of seats. The Election Studio's Gallagher index measures this gap
  in the OFFICIAL result, regardless of which method is on screen.
- Survival of the median voter - a party can win on the back of a
  divided opposition.

## Why this is the official method

The Indian Constitution does not name a counting method; the
Representation of the People Act, 1951, ss. 53-65A, encodes FPTP.
Changing the rule would require an Act of Parliament. The Election
Studio does NOT advocate any change - the alternate-method rooms are
exploratory, not prescriptive.

## Further reading

- Election Commission of India, *Manual on Electoral Rolls*.
- Representation of the People Act, 1951.
- NCRWC Report (2002), Chapter 4: Electoral Reforms.
