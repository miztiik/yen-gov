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
  // The provenance query is typed as RawSourceRow because X1a's
  // CSV-as-table view projects 4 columns as NULL (license /
  // confidence_tier / is_issuing_authority / verification_method per
  // O3 5-field source.csv shape); coerceSourceRow fills sentinels at
  // the boundary so the downstream Zod schema accepts the row.
  const [mainRows, sourceRows] = await Promise.all([
    query<Record<string, unknown>>(plan.main_sql),
    query<RawSourceRow>(plan.provenance_sql),
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

/**
 * The raw shape the X1a `registerCsvAsTable("taxonomy.sources")` seam
 * actually returns. The 5-field `data/entities/source.csv` (per parent
 * plan section 20.3 / O3 doctrine) only carries `{source_id, owner,
 * title, vintage, url}`; the projected view aliases `owner -> producer`
 * and `url -> url_main` and surfaces the 4 retired fields as `NULL`
 * (license / confidence_tier / is_issuing_authority /
 * verification_method) plus 2 more nullable VARCHARs (citation_full /
 * notes). This widening type acknowledges that runtime reality without
 * pretending the TS contract has been retro-fitted onto every adapter.
 *
 * Holy Law #9 is preserved: every row STILL carries a source_id FK and
 * still surfaces producer/title/vintage. The dropped fields are
 * citizen-readable provenance richness, not the citation identity
 * itself (citation identity = `(producer, title, vintage)` per
 * docs/concepts/data-provenance.md).
 */
interface RawSourceRow {
  readonly source_id: string;
  readonly producer: string;
  readonly title: string;
  readonly vintage: string;
  readonly license: SourceV2Row["license"] | null;
  readonly confidence_tier: SourceV2Row["confidence_tier"] | null;
  readonly is_issuing_authority: boolean | null;
  readonly verification_method: SourceV2Row["verification_method"] | null;
  readonly url_main: string | null;
  readonly citation_full: string | null;
  readonly notes: string | null;
}

function coerceSourceRow(row: SourceV2Row | RawSourceRow): SourceRow {
  // X1a sentinel coercion (YA cutover 2026-06-06): the 5-field
  // source.csv shape (O3 doctrine binding) drops 4 of the 6 enum/bool
  // fields the Zod `SourceRowSchema` requires non-null. Fill the
  // safest enum variant at the boundary so the downstream Zod parse
  // accepts the row.
  //
  // Sentinel choices:
  //   - license -> "unknown-public" (the explicit "we know it's a
  //     public source but cannot pin a licence" variant; OWID-grade
  //     honesty preferred over a falsely-confident default).
  //   - confidence_tier -> "bronze" (lowest tier; signals "no
  //     confidence claim attached to this row").
  //   - is_issuing_authority -> false (we did not verify the producer
  //     is the official issuing authority; default conservative).
  //   - verification_method -> "editorial" (we did not record how the
  //     row was verified; "editorial" is the catch-all for
  //     unattested-method rows per source-list-v2/types.ts).
  //
  // These match the values `synthesiseUnattestedSource()` in types.ts
  // already uses for the empty-provenance synthesised row, so the
  // citizen-visible rendering of an X1a-NULL source and a fully-
  // synthesised unattested source are similar (and both clearly
  // distinguishable from a gold-tier official-issuing-authority row).
  return {
    source_id: row.source_id,
    producer: row.producer,
    title: row.title,
    vintage: row.vintage,
    license: row.license ?? "unknown-public",
    confidence_tier: row.confidence_tier ?? "bronze",
    is_issuing_authority: row.is_issuing_authority ?? false,
    verification_method: row.verification_method ?? "editorial",
    url_main: row.url_main,
    citation_full: row.citation_full,
    notes: row.notes,
  };
}
