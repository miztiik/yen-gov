// applicableMutationsFor - pure filter for the Psephlab "+ Add what-if"
// menu. Per Fowler verdict (2026-06-09 debate): the mutation declares
// which counting rules it is meaningful under, NOT the rule declaring
// which mutations it accepts (Open/Closed - adding a new rule needs zero
// edits to mutation files).
//
// Already-encoded scenarios with a mutation outside the active rule's
// allowed set are NOT silently dropped - the host UI renders them
// struck-through with explanatory micro-copy, per Fowler's "share-URL
// contract" defence. This helper only filters the NEW-mutation picker.

import { MUTATIONS } from "./mutations";
import type { MutationConfig, MutationPlugin } from "./types";

/** Mutations applicable when the citizen is exploring under `rule_id`.
 *  A mutation with no `allowed_rules` is treated as rule-agnostic and
 *  always included. Pure - safe to call on every render. */
export function applicableMutationsFor(
  rule_id: string,
): ReadonlyArray<MutationPlugin> {
  return MUTATIONS.filter(
    (m) => !m.allowed_rules || m.allowed_rules.includes(rule_id),
  );
}

/** True when the configured mutation is INERT under the active rule
 *  (would have zero visible effect on the seat tally). Used by the
 *  mutation panel to render strikethrough + a one-liner explanation
 *  instead of dropping the row from a shared scenario. */
export function isMutationInertUnder(
  mutation_id: string,
  rule_id: string,
): boolean {
  const m = MUTATIONS.find((x) => x.id === mutation_id);
  if (!m) return false;
  if (!m.allowed_rules) return false;
  return !m.allowed_rules.includes(rule_id);
}

/** Citizen-readable one-liner explaining WHY a mutation is inert under
 *  the active rule. Returns null when the mutation IS applicable.
 *  Used as the strikethrough tooltip + micro-copy on the mutation row. */
export function inertReasonFor(
  mutation: MutationConfig,
  rule_id: string,
): string | null {
  if (!isMutationInertUnder(mutation.id, rule_id)) return null;
  // The two known inert cases today: perAcSwing + thresholdDrop under
  // proportional. The copy explains the why ("PR aggregates state-wide")
  // so the citizen can fix it (switch rule OR remove the row).
  if (rule_id === "proportional") {
    if (mutation.id === "perAcSwing") {
      return "Per-AC vote swings do not change state-wide totals; under Proportional this has no visible effect. Switch to First-past-the-post / Ranked / Approval, or remove this row.";
    }
    if (mutation.id === "thresholdDrop") {
      return "Per-AC threshold drops do not change state-wide totals; under Proportional this has no visible effect. Switch to First-past-the-post / Ranked / Approval, or remove this row.";
    }
  }
  // Generic fallback for any future mutation/rule pairing that adds
  // an allow-list constraint without bespoke copy here.
  return `This what-if does not apply under the active counting rule. Switch the rule, or remove this row.`;
}
