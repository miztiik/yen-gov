// Approval voting simulator: cast = approval.
//
// Per parent plan section 25.6b-seam + override sub-plan
// `TODO/20260608-e6-user-override-and-pl2-pl3-execution-subplan.md`.
//
// Indian EVMs do not record approval ballots. This simulator treats each
// cast vote as approving exactly ONE candidate - which is MATHEMATICALLY
// IDENTICAL to First-Past-The-Post. The result is the SAME as the
// official FPTP count. The simulator exists to give the citizen an
// honest answer to "what would approval voting produce?": "Nothing
// different, because there is no separate approval data from which to
// model multi-candidate approval ballots."
//
// This is a HONESTY MARKER, not a fabrication. Showing the FPTP-equivalent
// result preserves the citizen's right to ask the question and demonstrates
// transparently that the data does not support a meaningful approval-vote
// counterfactual.

import type { CountingRule, SeatAllocation, Tallies } from "../types";
import { fptp } from "./fptp";

export const approval: CountingRule = {
  id: "approval",
  label: "Approval (cast = approval)",
  requires_banner: true,
  caveat:
    "Indian EVMs do not record approval ballots. This simulator treats " +
    "each cast vote as approving exactly ONE candidate - which is " +
    "MATHEMATICALLY IDENTICAL to First-Past-The-Post. The result is the " +
    "SAME as the official FPTP count. Showing this preserves the " +
    "citizen's right to ask 'what would approval voting produce?' The " +
    "honest answer from FPTP-only data is: nothing different. A " +
    "meaningful approval simulation requires ballot-level approval data " +
    "India does not collect.",
  assumptions: [
    "Each voter approves exactly one candidate (the one they voted for).",
    "There is no approval ballot data in India; this simulator cannot model 'voters might approve multiple candidates' without fabricating their preferences.",
    "The result is mathematically equivalent to FPTP by construction; this rule exists to give the citizen an honest 'no useful difference' answer rather than hide the question.",
  ],

  apply(tallies: Tallies): SeatAllocation {
    // Approval-as-cast == FPTP. Delegate to keep one source of truth for
    // the NOTA-fallback + tie-breaking + assertSeatTallyInvariant logic.
    return fptp.apply(tallies);
  },
};
