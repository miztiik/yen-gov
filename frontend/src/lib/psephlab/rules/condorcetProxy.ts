// Condorcet proxy simulator.
//
// Per Hans + Fowler round-2 verdict (2026-06-09). Real Condorcet voting
// asks each voter to rank every candidate, then runs all-pairs majority
// contests. The Condorcet winner is the candidate that beats every
// other in pairwise majority comparison.
//
// India does not collect ranked ballots. Our PROXY substitutes vote
// counts for preference orderings: "A beats B in this AC if A has more
// first-preference votes than B." Under this proxy, the rank-by-votes
// relation is a TOTAL ORDER (transitive), so the Condorcet winner per
// AC is always the candidate with the highest votes - which is exactly
// the FPTP winner.
//
// This makes Condorcet proxy ALGORITHMICALLY IDENTICAL to FPTP per-AC.
// The honesty marker is that the equivalence is BY CONSTRUCTION of the
// proxy: real Condorcet on ranked ballots WOULD diverge from FPTP in
// 3-way races, but the proxy can't capture that. The interesting object
// is the per-AC pairwise-cycle counter (cycles can exist when votes
// tie; otherwise the proxy is always cycle-free), reported as a stub
// for now via the documentation footnote.
//
// Like Approval, this is an honest equivalence-disclosure rule: the
// citizen asks "what would Condorcet do?" and the answer from
// FPTP-only data is "exactly what FPTP did - here is why."

import type { CountingRule, SeatAllocation, Tallies } from "../types";
import { fptp } from "./fptp";

export const condorcetProxy: CountingRule = {
  id: "condorcet-proxy",
  label: "Condorcet proxy (pairwise from vote counts)",
  short_label: "Condorcet proxy",
  headline: "Pairwise contests inferred from vote counts.",
  validity: "medium_validity",
  requires_banner: true,
  caveat:
    "Real Condorcet voting would ask 'do voters of C prefer A or B?' " +
    "India's EVMs don't record that, so we proxy: A beats B in this AC " +
    "if A has more first-preference votes than B. Under this proxy, " +
    "the rank-by-votes relation is transitive, so the Condorcet winner " +
    "per AC equals the FPTP winner BY CONSTRUCTION. This makes the " +
    "method ALGORITHMICALLY IDENTICAL to FPTP under our data. The " +
    "fascinating thing is what we CANNOT see: real Condorcet on ranked " +
    "ballots would diverge from FPTP in 3-way races where voters' " +
    "second preferences matter. Look for the cycles, not the winner.",
  assumptions: [
    "Holds constant: pairwise wins inferred from first-preference vote order in each AC.",
    "Holds constant: the rank-by-votes total order makes the Condorcet winner identical to the FPTP winner BY CONSTRUCTION.",
    "Holds constant: cycles (A>B>C>A) cannot occur under a total order; real Condorcet ranked-ballot cycles are not modeled.",
    "Reveals: that the FPTP winner is ALSO the Condorcet winner under any vote-count-based proxy; the divergence lives in the data we don't collect.",
  ],

  apply(tallies: Tallies): SeatAllocation {
    // Condorcet proxy under vote-count substitution == FPTP per-AC.
    // Delegate to fptp to keep one source of truth for the NOTA
    // fallback + tie-breaking + assertSeatTallyInvariant logic.
    return fptp.apply(tallies);
  },
};
