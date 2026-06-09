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
  label: "Approval (single mark)",
  short_label: "Approval (single mark)",
  headline: "What approval reveals when ballots stay single-mark.",
  validity: "fully_workable",
  requires_banner: true,
  caveat:
    "Approval voting asks each voter to mark every candidate they find " +
    "acceptable. India's EVMs record one button press, so for this view we " +
    "treat each cast vote as a single approval. The result is " +
    "mathematically identical to First-Past-The-Post by construction, and " +
    "that mirroring IS the finding: under the data India collects, Approval " +
    "and FPTP cannot diverge. To see Approval diverge, India would need an " +
    "approval ballot. This is the cleanest example in the whole Election " +
    "Studio of WHY ballot design matters - every other room shows a rule " +
    "applied to data; this room shows the rule that DATA itself is.",
  assumptions: [
    "Holds constant: each voter approves exactly one candidate (the one they voted for).",
    "Holds constant: no approval ballot data exists in India - a meaningful approval simulation would require a different ballot.",
    "Reveals: the structural choice that ballot design makes BEFORE counting begins.",
  ],

  apply(tallies: Tallies): SeatAllocation {
    // Approval-as-cast == FPTP. Delegate to keep one source of truth for
    // the NOTA-fallback + tie-breaking + assertSeatTallyInvariant logic.
    return fptp.apply(tallies);
  },
};
