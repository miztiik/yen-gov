// Executor: DuckDBPlan -> AnswerViewModel.
//
// Impure: this is the seam where the lab touches `lib/duckdb.ts`. Per
// plan-doc §17 D-05 the executor stays thin — it registers the slice +
// table views the plan demands, runs the two SQL strings, and assembles
// the AnswerViewModel.
//
// Provenance discipline (§17 D-06): if the provenance JOIN returns zero
// rows, the executor SYNTHESISES a single "source unattested" placeholder
// row AND flips `provenance_status` to "missing". The renderer surfaces
// the visible notice. The empty-array case is unreachable in normal
// operation; it indicates a data-corruption regression and the citizen
// needs to know.

import {
  query,
  registerCsvAsTable,
  registerCsvFile,
  registerSlice,
  registerTable,
  type CsvAsTableId,
} from "../duckdb";
import { parseAnswerViewModel } from "./contracts/answer-viewmodel";
import type {
  AnswerRow,
  AnswerViewModel,
  SourceRow,
} from "./contracts/answer-viewmodel";
import type { DuckDBPlan } from "./types";
import { synthesiseUnattestedSource } from "./types";
import type { SourceV2Row } from "../source-list-v2";

/** X1a CSV-as-table dispatch set. The two table_ids the F1.3b yenask
 *  concept templates already advertise on their `table_registrations`
 *  are flipped to the CSV-backed view; everything else (e.g. dim_acs)
 *  stays on the parquet path until B3 retires `registerTable` entirely. */
const CSV_AS_TABLE_IDS: ReadonlySet<CsvAsTableId> = new Set([
  "elections.dim_parties",
  "taxonomy.sources",
]);

function isCsvAsTableId(table_id: string): table_id is CsvAsTableId {
  return (CSV_AS_TABLE_IDS as ReadonlySet<string>).has(table_id);
}

/**
 * Execute a DuckDBPlan and return a citizen-renderable AnswerViewModel.
 *
 * The final Zod parse via `parseAnswerViewModel` is the boundary check:
 * any compiler bug that produces a malformed view-model (wrong shape,
 * empty source_strip, etc.) fails here rather than rendering a half-baked
 * UI.
 */
export async function executePlan(plan: DuckDBPlan): Promise<AnswerViewModel> {
  // Register all views the plan needs. Idempotent in `lib/duckdb.ts`.
  // F1.3b: csv_registrations register URLs with DuckDB-WASM so the
  // `read_csv('<url>', columns={...})` calls embedded in the SQL
  // strings can HTTP-Range fetch them; no view name is created (the
  // URL itself is the SQL handle).
  //
  // X1a: route `elections.dim_parties` + `taxonomy.sources` table_ids
  // to `registerCsvAsTable` (which projects the legacy parquet column
  // shape from parties.csv + source.csv); other table_ids stay on
  // parquet via `registerTable` until B3 deletes the parquet path
  // entirely. The 4 concept SQL strings in `concepts.ts` are
  // UNCHANGED \u2014 they JOIN `dim_parties` / `sources` by view name and
  // the seam ensures the view name resolves to the CSV-backed body.
  await Promise.all([
    ...plan.csv_registrations.map(r => registerCsvFile(r.url)),
    ...plan.slice_registrations.map(s =>
      registerSlice(s.table_id, s.partition_filter, { viewName: s.view_name }),
    ),
    ...plan.table_registrations.map(t =>
      isCsvAsTableId(t.table_id)
        ? registerCsvAsTable(t.table_id)
        : registerTable(t.table_id, { viewName: t.view_name }),
    ),
  ]);

  // Two queries in parallel — they share the same registered views.
  const [mainRows, sourceRows] = await Promise.all([
    query<Record<string, unknown>>(plan.main_sql),
    query<SourceV2Row>(plan.provenance_sql),
  ]);

  const rows: AnswerRow[] = mainRows.map(coerceAnswerRow);

  // Per D-06: empty source_strip is forbidden. Synthesise the
  // "unattested" placeholder and flip the status so the renderer can
  // surface a visible notice. The `as SourceRow` coercion is safe — the
  // synthesised row is built to match the schema verbatim.
  const provenance_status: "joined" | "missing" =
    sourceRows.length > 0 ? "joined" : "missing";
  const source_strip: SourceRow[] =
    sourceRows.length > 0
      ? sourceRows.map(coerceSourceRow)
      : [coerceSourceRow(synthesiseUnattestedSource())];

  const candidate: AnswerViewModel = {
    question: plan.view_hints.question,
    rows,
    column_order: [...plan.view_hints.column_order],
    column_labels: { ...plan.view_hints.column_labels },
    column_formats: { ...plan.view_hints.column_formats },
    source_strip,
    provenance_status,
    computation: {
      concept_id: plan.concept_id,
      slice_registrations: plan.slice_registrations.map(s => ({
        table_id: s.table_id,
        partition_filter: { ...s.partition_filter },
      })),
      main_sql: plan.main_sql,
      provenance_sql: plan.provenance_sql,
    },
  };

  return parseAnswerViewModel(candidate);
}

function coerceAnswerRow(row: Record<string, unknown>): AnswerRow {
  const out: AnswerRow = {};
  for (const [k, v] of Object.entries(row)) {
    if (v == null) {
      out[k] = null;
    } else if (typeof v === "bigint") {
      out[k] = Number(v);
    } else if (typeof v === "number" || typeof v === "string" || typeof v === "boolean") {
      out[k] = v;
    } else {
      // Fallback: stringify exotic types (Arrow Decimal, Date, etc.) so
      // the renderer always has something it can show. Mirrors the
      // existing `num` / `String(x ?? "")` shape from psephlab loaders.
      out[k] = String(v);
    }
  }
  return out;
}

function coerceSourceRow(row: SourceV2Row): SourceRow {
  // SourceV2Row and SourceRow are structurally identical; this is a
  // typed re-export. Any drift fails the Zod parse downstream.
  return {
    source_id: row.source_id,
    producer: row.producer,
    title: row.title,
    vintage: row.vintage,
    license: row.license,
    confidence_tier: row.confidence_tier,
    is_issuing_authority: row.is_issuing_authority,
    verification_method: row.verification_method,
    url_main: row.url_main,
    citation_full: row.citation_full,
    notes: row.notes,
  };
}
