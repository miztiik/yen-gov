// The engine. Pure synchronous function:
//
//     run(actuals, scenario) -> RunResult
//
// Composes mutations in order, runs the chosen counting rule on the
// resulting Tallies, and also computes the unmutated baseline so the UI
// can render deltas without re-counting.

import { mutationById } from "./mutations";
import { ruleById } from "./rules";
import type { RunResult, Scenario, Tallies } from "./types";

export function run(actuals: Tallies, scenario: Scenario): RunResult {
  let mutated: Tallies = actuals;
  for (const cfg of scenario.mutations) {
    const m = mutationById(cfg.id);
    if (!m) continue;
    mutated = m.apply(mutated, cfg as never);
  }
  const rule = ruleById(scenario.rule);
  const allocation = rule.apply(mutated);
  // Always compute baseline against the *same* rule so a rule swap (when
  // we ship more rules) doesn't accidentally compare apples to oranges.
  const actuals_allocation = rule.apply(actuals);
  return { mutated, allocation, actuals_allocation };
}
