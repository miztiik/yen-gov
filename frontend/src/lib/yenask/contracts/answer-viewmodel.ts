// AnswerViewModel Zod contract (v0).
//
// This is the ONLY shape the renderer is allowed to display. See plan-doc
// §17 D-06: `source_strip` is REQUIRED non-empty and `provenance_status`
// is a REQUIRED enum, enforced at Zod parse time. Holy Law #9 (provenance
// is data, not commentary) is bound here at the type level so a regression
// can't smuggle a sourceless answer past the gate.

import { z } from "zod";

/**
 * One publisher pill in the citizen-visible source strip. Mirrors
 * `PublisherPill` in `frontend/src/lib/sources/types.ts` exactly.
 * Duplicated as a Zod schema here so the lab can validate executor
 * output without depending on runtime type assertions.
 *
 * Hard rule: when this schema and `PublisherPill` drift, the canonical
 * type wins. A vitest case asserts shape equivalence.
 */
export const SourceRowSchema = z
  .object({
    label: z.string().min(1),
    vintage_summary: z.string(),
    url: z.string().url().nullable(),
    count: z.number().int().positive(),
  })
  .strict();
export type SourceRow = z.infer<typeof SourceRowSchema>;

/**
 * A single cell value. DuckDB-WASM returns numbers, strings, booleans, or
 * nulls for the column types YENASK exposes (no Date / no BLOB / no Arrow
 * Vector pass-through). Anything outside this set is a compiler bug and
 * MUST fail the parse.
 */
export const CellValueSchema = z.union([
  z.string(),
  z.number(),
  z.boolean(),
  z.null(),
]);
export type CellValue = z.infer<typeof CellValueSchema>;

/**
 * One row of the answer table. Keys are column ids from the plan's
 * `view_hints.column_order`.
 */
export const AnswerRowSchema = z.record(z.string(), CellValueSchema);
export type AnswerRow = z.infer<typeof AnswerRowSchema>;

/**
 * The renderer-bound view of the compiled answer. Every field is required
 * EXCEPT `notes` (free-text caveats from the compiler — e.g. "field-size
 * collapse to top-5 + others applied").
 */
export const AnswerViewModelSchema = z
  .object({
    /** Citizen question echoed back. Sourced from the intent. */
    question: z.string().min(1),
    /** Computed answer rows. Empty array is allowed (e.g. no matches). */
    rows: z.array(AnswerRowSchema),
    /** Display-order column ids. MUST be non-empty. */
    column_order: z.array(z.string()).min(1),
    /** Map column id -> citizen-readable label. */
    column_labels: z.record(z.string(), z.string()),
    /** Map column id -> display format. See ColumnFormat in types.ts. */
    column_formats: z.record(
      z.string(),
      z.enum(["integer", "percentage", "thousands", "text"]),
    ),
    /**
     * Provenance strip. **REQUIRED non-empty** per D-06.
     *
     * If the underlying provenance JOIN returned zero rows, the compiler
     * MUST synthesise a single "source unattested" placeholder row (see
     * `synthesiseUnattestedPill()` in `../types.ts`) AND set
     * `provenance_status: "missing"`. The renderer then surfaces a visible
     * "source unattested — do not cite" notice.
     *
     * An EMPTY array fails the Zod parse — caught before reaching the UI.
     */
    source_strip: z.array(SourceRowSchema).min(1),
    /**
     * Whether the provenance JOIN succeeded with at least one real source.
     * REQUIRED enum so the renderer can branch on the value without
     * inferring intent from row counts.
     */
    provenance_status: z.enum(["joined", "missing"]),
    /**
     * Computation transparency. Filled by the compiler; rendered in the
     * collapsed "How was this computed?" disclosure.
     */
    computation: z
      .object({
        concept_id: z.string().min(1),
        slice_registrations: z.array(
          z.object({
            table_id: z.string(),
            partition_filter: z.record(z.string(), z.string()),
          }),
        ),
        main_sql: z.string().min(1),
        provenance_sql: z.string().min(1),
      })
      .strict(),
    /** Optional caveats text. */
    notes: z.string().optional(),
  })
  .strict();

export type AnswerViewModel = z.infer<typeof AnswerViewModelSchema>;

/**
 * Parses an AnswerViewModel, throwing on failure. The executor calls this
 * before handing the view-model to the renderer.
 */
export function parseAnswerViewModel(input: unknown): AnswerViewModel {
  return AnswerViewModelSchema.parse(input);
}

/**
 * Non-throwing variant.
 */
export function safeParseAnswerViewModel(
  input: unknown,
): z.ZodSafeParseResult<AnswerViewModel> {
  return AnswerViewModelSchema.safeParse(input);
}
