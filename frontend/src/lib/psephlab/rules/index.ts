// Counting-rule registry. New rules register here; the UI reads `RULES` to
// populate the dropdown. Three alternate methods landed under the E6
// user-override sprint per TODO/20260608-e6-user-override-and-pl2-pl3-execution-subplan.md:
// Proportional (Sainte-Lague, state-wide), Ranked-choice (IRV with
// uniform transfer), and Approval (cast = approval). Each carries a
// `requires_banner: true` flag + a Hans-grade caveat that
// ImaginingCard (the encouraging-tone successor to the retired
// HypotheticalRecountBanner, 2026-06-09 redesign) surfaces above the
// seat panel; FPTP remains the only rule that DOES NOT mount the card.

import type { CountingRule } from "../types";
import { fptp } from "./fptp";
import { sainteLague } from "./sainteLague";
import { dhondt } from "./dhondt";
import { hamilton } from "./hamilton";
import { mmp } from "./mmp";
import { instantRunoff } from "./instantRunoff";
import { trsRound2 } from "./trsRound2";
import { borda } from "./borda";
import { condorcetProxy } from "./condorcetProxy";
import { approval } from "./approval";

// Round-2 (2026-06-09) expansion: 4 -> 10 rules. New methods grouped by
// Hans's validity tier: fully_workable (mechanical re-arrangement of
// FPTP data) versus medium_validity (requires an explicit assumption
// India doesn't publish data for). Order in the array determines
// picker-card order in the MethodPicker drawer; FPTP first as the
// official baseline.
export const RULES: CountingRule[] = [
  fptp,
  sainteLague,
  dhondt,
  hamilton,
  mmp,
  instantRunoff,
  trsRound2,
  borda,
  condorcetProxy,
  approval,
];

export function ruleById(id: string): CountingRule {
  const r = RULES.find(x => x.id === id);
  // Unknown rule -> fall back to FPTP rather than throw. Scenarios saved
  // under a future rule name should still render *something* when loaded
  // by an older bundle, with the loader reporting the downgrade.
  return r ?? fptp;
}
