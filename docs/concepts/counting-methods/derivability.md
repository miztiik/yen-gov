# Counting methods: derivability from FPTP data

**Last Updated**: 2026-06-09

India's EVMs record one button press per voter. From that single
data structure - the per-AC vote count by candidate - some counting
methods can be computed mechanically and others require an explicit
assumption. This page names which is which.

## What "derivable from FPTP" means

A counting method is **derivable from FPTP data** if every input the
algorithm consumes is present in the per-AC vote table the Election
Commission publishes. The output is then a mechanical re-arrangement,
not a prediction.

A method is **partially derivable** if it requires either (a) a
synthesised input the simulator must hand-author (the alliance map),
or (b) an assumption about voter behaviour the data cannot test (the
uniform transfer rule under IRV).

## Fully Workable (High Validity)

These six methods rearrange FPTP data without any new assumption about
voter preferences. The output is exact under "votes stay as cast".

| Method | How we compute it | India-specific note |
| --- | --- | --- |
| First-Past-The-Post | Per-AC plurality. Winner = candidate with most votes. | This IS the data; no derivation. |
| Proportional (Sainte-Lague) | State-wide party vote totals; iterative divisor allocation with divisors 1, 3, 5, ... | Small-party friendly; mirrors NZ MMP list tier. |
| Proportional (D'Hondt) | Same shape, divisors 1, 2, 3, ... | Larger-party bonus; used in Belgium, Spain, Israel. |
| Largest Remainder (Hamilton) | Hare quota; integer-share first, remainders settle the rest. | Susceptible to Alabama paradox (academic; rare in practice). |
| Mixed-Member Proportional (MMP) | Keep every FPTP constituency winner; add ~30% list-tier seats by state-wide vote share via Sainte-Lague. | Chamber grows past constituency count via overhang. |
| Approval (single mark) | Identical to FPTP by construction. India's EVMs record one button press per voter. | The honest "no useful difference" answer. |

## Workable With Explicit Assumptions (Medium Validity)

These six methods require data India does not collect (ranked ballots,
alliance preferences, pairwise rankings). The simulator holds an
explicit assumption constant so the rule can operate. The assumption
is named inline on the picker card and detailed on the per-method
page.

| Method | Holds constant | Validity grade |
| --- | --- | --- |
| Ranked-choice (proportional transfer) | Voter second preferences mirror current AC vote shares at each elimination round. | Medium - the "uniform transfer" rule is the gentlest defensible substitution. |
| Ranked-choice (alliance-transfer) | Eliminated votes route 100% to the surviving candidate in the same alliance (NDA -> NDA survivor; INDIA -> INDIA). | Medium - perfect coordination is an UPPER BOUND, not a prediction. |
| Top-2 Runoff (proportional) | Eliminated votes split between the top 2 in proportion to their first-round shares. | Medium - "politically agnostic" voters are an idealisation. |
| Top-2 Runoff (alliance) | Eliminated votes route to the surviving alliance partner (100% discipline). | Medium - paired with the proportional variant, the two BRACKET the real result. |
| Borda Count | Ranks fixed to FPTP vote order within each AC; one rank-position unit per AC regardless of electorate size. | Medium - AC-equal-weighting biases the result toward parties with many small-AC candidates. |
| Condorcet proxy | Pairwise wins inferred from first-preference vote order; the rank-by-votes total order makes the Condorcet winner identical to the FPTP winner by construction. | Medium - the proxy cannot exhibit cycles; real Condorcet on ranked ballots could. |

## Why we still ship the Medium-Validity views

Each Medium-Validity method has a documented "fascinating limit"
section in its per-method page that names the load-bearing assumption,
explains why it is the cleanest defensible substitution, and points to
what real ranked-ballot data would let us see beyond.

These views are pedagogical, not predictive. Read flips from the FPTP
baseline as a LOWER BOUND on how different India would look under real
ranked-choice ballots, alliance discipline, or pairwise voting.

## What would lift a method from Medium to Fully Workable

Each Medium-Validity method has a specific data dependency it would
need to graduate:

- **Ranked-choice (both variants).** Ranked ballots (rank every
  candidate, not single mark).
- **Top-2 Runoff (both variants).** Either a real second round of
  voting (France's presidential model) or exit-poll data with the
  question "if your candidate is eliminated, who is your second
  preference?" at AC grain.
- **Borda Count.** Ranked ballots. The current proxy uses FPTP rank
  as a substitute, which works algorithmically but loses the
  preference-reversal signal.
- **Condorcet proxy.** Pairwise preference data ("do you prefer A
  over B?" for every (A, B) pair). Only ranked ballots can produce
  this at scale; exit polls cannot afford the question count.

## Further reading

- [Counting methods: overview](overview.md) - the validity-tier
  framing and the three theoretical constraints (Arrow,
  Gibbard-Satterthwaite, Condorcet paradox).
- [India-specific caveats](india-caveats.md) - the six structural
  features that affect interpretation of every method.
- Per-method pages for the algorithmic detail + the "fascinating
  limit" section.
