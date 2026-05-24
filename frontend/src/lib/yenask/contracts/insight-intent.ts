// InsightIntent Zod contract (v0).
//
// This is the ONLY thing the model is allowed to output. The compiler
// rejects anything else via Zod parse at the boundary. See plan-doc §17
// D-03 for the design decision (TS-Zod only; no JSON Schema mirror under
// datasets/schemas/).
//
// Discriminator: every intent carries `version: "insight.intent.v0"`.
// A v1 would be a NEW file (`insight-intent-v1.ts`) — never a silent bump.
//
// The four PR-1 concept ids ("party_totals" | "closest_contests" |
// "constituency_result" | "turnout_extremes") are an enum so the compiler
// can dispatch on a closed set. PR-2+ adds new ids; each new id needs both
// a Zod entry here AND a handler in compile-intent.ts.

import { z } from "zod";

/**
 * The closed set of concepts the compiler can answer in PR-1.
 *
 * Every entry MUST have a matching handler in `compile-intent.ts` and a
 * matching template in `concepts.ts`. Adding a new concept = three edits.
 */
export const ConceptIdEnum = z.enum([
  "party_totals",
  "closest_contests",
  "constituency_result",
  "turnout_extremes",
]);
export type ConceptId = z.infer<typeof ConceptIdEnum>;

/**
 * Filter parameters the model can pass to a concept. Field set is
 * INTENTIONALLY narrow in v0 — every additional field is a new way for
 * the model to invent values. The compiler still re-validates each field
 * against the semantic catalogue (e.g. `state_partition_id` must exist in
 * `catalogue.states`).
 */
export const IntentFiltersSchema = z
  .object({
    /** Hive partition id for the state (e.g. "in_s22"). */
    state_partition_id: z.string().regex(/^in_[a-z][a-z0-9_]+$/).optional(),
    /** Period label as it appears in canonical Parquet (e.g. "AcGenMay2026"). */
    period_label: z.string().min(3).max(64).optional(),
    /** ECI AC number (positive integer, no leading zeros). */
    ac_no: z.number().int().positive().max(9999).optional(),
    /** Party short code (e.g. "DMK"). */
    party_short_code: z.string().min(1).max(16).optional(),
    /** Limit on result rows the model may request. Hard-capped at 100. */
    limit: z.number().int().positive().max(100).optional(),
  })
  .strict();

export type IntentFilters = z.infer<typeof IntentFiltersSchema>;

/**
 * The InsightIntent itself. `version` is the discriminator; treating it
 * as a `z.literal` means future v1 work is type-distinguishable without
 * runtime tag-checking.
 */
export const InsightIntentSchema = z
  .object({
    version: z.literal("insight.intent.v0"),
    /** Citizen question, verbatim from the input. Used to caption the answer. */
    question: z.string().min(3).max(400),
    /** The compiler dispatch key. Closed enum. */
    concept_id: ConceptIdEnum,
    /** Narrow optional filter bag. See IntentFiltersSchema. */
    filters: IntentFiltersSchema.default({}),
    /**
     * Reason the model believes this intent answers the question.
     * Echoed back to the citizen in the disclosure panel for trust.
     * Limited to keep the panel compact and to discourage waffle.
     */
    reasoning: z.string().min(0).max(600).default(""),
  })
  .strict();

export type InsightIntent = z.infer<typeof InsightIntentSchema>;

/**
 * Parses raw text or a JS value into an InsightIntent, throwing a
 * Zod-typed error on failure. The model adapter (PR-2) calls this against
 * the model's raw text; PR-1 calls it against the canned-intent fixtures
 * to prove the round-trip.
 */
export function parseInsightIntent(input: unknown): InsightIntent {
  return InsightIntentSchema.parse(input);
}

/**
 * Non-throwing variant. Useful in UI code that wants to render the Zod
 * error inline instead of bubbling.
 */
export function safeParseInsightIntent(
  input: unknown,
): z.ZodSafeParseResult<InsightIntent> {
  return InsightIntentSchema.safeParse(input);
}
