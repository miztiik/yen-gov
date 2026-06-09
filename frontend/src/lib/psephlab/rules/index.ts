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
import { instantRunoff } from "./instantRunoff";
import { approval } from "./approval";

// Round-2 (2026-06-09) expansion: 4 -> 6 rules. D'Hondt + Hamilton are
// PR divisor variants (alongside Sainte-Lague) per Hans + Fowler
// convergence verdict. Order in the array determines picker-card order
// in the new MethodPicker drawer; FPTP first as the official baseline.
export const RULES: CountingRule[] = [
  fptp,
  sainteLague,
  dhondt,
  hamilton,
  instantRunoff,
  approval,
];

export function ruleById(id: string): CountingRule {
  const r = RULES.find(x => x.id === id);
  // Unknown rule -> fall back to FPTP rather than throw. Scenarios saved
  // under a future rule name should still render *something* when loaded
  // by an older bundle, with the loader reporting the downgrade.
  return r ?? fptp;
}
