// Compiler: InsightIntent + SemanticCatalogue -> DuckDBPlan.
//
// Per plan-doc §17 D-05 the compiler is pure with respect to DuckDB
// state - it does NOT import from `../duckdb`. It produces a
// `DuckDBPlan` value the executor consumes.
//
// F1.3b: `compileIntent` is now async because per-concept builders need
// to await `csvColumnsClause(path)` to embed the typed `columns={...}`
// fragment into the `read_csv(<url>, columns={...})` SQL. The fetched
// `datasets/data/_schema/columns.json` is cached per session by
// `lib/canonical/csv-columns.ts`, so the second call is a Map lookup.
// Vitest tests this module without booting WASM by mocking
// `csvColumnsClause` so the runtime fetch never happens.
//
// The compiler enforces THREE invariants:
//   1. The intent's `concept_id` is in the closed enum (already enforced
//      by Zod at the boundary).
//   2. The intent's `filters` resolve against the catalogue (e.g.
//      `state_partition_id` must exist in `catalogue.states`).
//   3. The plan ALWAYS includes a provenance JOIN (Holy Law #9). The
//      executor handles the source-miss case by synthesising a
//      "source unattested" row + flipping `provenance_status` (D-06).

import type { InsightIntent } from "./contracts/insight-intent";
import type { DuckDBPlan, SemanticCatalogue } from "./types";
import { CONCEPT_REGISTRY } from "./concepts";

/**
 * Async: compile an InsightIntent into a DuckDBPlan against the given
 * catalogue. Throws when the intent references catalogue values that
 * don't exist (e.g. an unknown state_partition_id).
 *
 * Throwing is the safe behaviour: the caller (UI) renders the error in
 * the citizen-visible failure surface rather than silently mis-answering.
 */
export async function compileIntent(
  intent: InsightIntent,
  catalogue: SemanticCatalogue,
): Promise<DuckDBPlan> {
  validateAgainstCatalogue(intent, catalogue);
  const handler = CONCEPT_REGISTRY[intent.concept_id];
  // Zod ensures concept_id is enum-bounded, so handler MUST exist; this
  // check defends against a registry/enum drift.
  if (!handler) {
    throw new Error(
      `compile: no handler registered for concept_id "${intent.concept_id}"`,
    );
  }
  return handler.build(intent);
}

function validateAgainstCatalogue(
  intent: InsightIntent,
  catalogue: SemanticCatalogue,
): void {
  const f = intent.filters;
  if (f.state_partition_id != null) {
    const known = catalogue.states.some(
      s => s.partition_id === f.state_partition_id,
    );
    if (!known) {
      throw new Error(
        `compile: filters.state_partition_id "${f.state_partition_id}" not in catalogue`,
      );
    }
  }
  if (f.period_label != null) {
    const known = catalogue.election_periods.some(
      p => p.period_label === f.period_label,
    );
    if (!known) {
      throw new Error(
        `compile: filters.period_label "${f.period_label}" not in catalogue`,
      );
    }
  }
  if (f.party_short_code != null) {
    const known = catalogue.parties.some(
      p => p.short_code === f.party_short_code,
    );
    if (!known) {
      throw new Error(
        `compile: filters.party_short_code "${f.party_short_code}" not in catalogue`,
      );
    }
  }
}
