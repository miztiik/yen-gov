# Counting method: Approval (single mark)

**Last Updated**: 2026-06-09

The Election Studio's Approval room is an HONESTY MARKER. It produces
the same result as First-Past-The-Post - by construction, because
India's EVMs do not collect approval ballots and the simulator cannot
fabricate them.

## Why the result equals FPTP

Approval voting lets a voter mark MULTIPLE candidates as "acceptable";
the candidate with the most marks wins. To compute approval results
honestly we would need ballot-level data showing which candidates each
voter approved. India does not collect that data.

The simulator treats each cast vote as approving exactly ONE candidate
- the one the voter actually voted for. That is mathematically
equivalent to First-Past-The-Post counting. The result is the official
FPTP tally back to you.

## Why we still ship this room

The citizen has the right to ask "what would approval voting produce
in this election?" The honest answer from the data India collects is:
no useful difference. Showing that answer transparently is the
encouragement. Hiding the question - by removing the Approval room
from the Election Studio - would imply the question is unanswerable
when in fact the answer is small.

A meaningful approval simulation requires either:

- **Pre-election approval surveys.** A survey instrument that asks
  voters which subset of candidates they approve of. India does not
  conduct such surveys at constituency grain.
- **A different ballot.** Approval voting requires an APPROVAL
  ballot - a check-all-that-apply form. India's EVMs record exactly
  ONE button press per voter.

Until one of those exists, the Approval room is honest about its
limits.

## What this rule guarantees in theory

If India did collect approval data, approval voting would:

- Reward consensus candidates - the candidate approved by the broadest
  coalition wins, not necessarily the one with the most first-place
  picks.
- Reduce the spoiler effect - a popular third-party candidate cannot
  cost the most-broadly-acceptable candidate the seat.
- Simplify the ballot - no ranking, just a yes/no per candidate.

Approval voting is used in Latvia (multi-member districts), some US
society and association elections, and several mathematical-association
internal elections.

## Further reading

- Brams, S. J. & Fishburn, P. C. (1983), *Approval Voting*.
- The Center for Election Science (electionscience.org) publishes
  approval-voting research and US adoption case studies.
- NCRWC Report (2002) does NOT consider approval voting; the Indian
  electoral-reform debate has focused on PR, IRV, and constituency
  redistricting.
