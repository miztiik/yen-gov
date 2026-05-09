// Counting-rule registry. New rules register here; the UI reads `RULES` to
// populate the dropdown. Defer-list (IRV, STV, D'Hondt, Sainte-Laguë) lives
// in psephlab.md, not here — adding any of them is one entry plus a sibling
// file under this directory.

import type { CountingRule } from "../types";
import { fptp } from "./fptp";

export const RULES: CountingRule[] = [fptp];

export function ruleById(id: string): CountingRule {
  const r = RULES.find(x => x.id === id);
  // Unknown rule → fall back to FPTP rather than throw. Scenarios saved
  // under a future rule name should still render *something* when loaded
  // by an older bundle, with the loader reporting the downgrade.
  return r ?? fptp;
}
