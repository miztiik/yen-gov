// YENASK lab — shared TS types not covered by Zod.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// for the design-decision log (entries D-01..D-11).
//
// Zod-typed contracts live next door under `./contracts/`. This file holds
// derived types and lab-internal structures that the compiler / executor /
// renderer pass between each other but that never come from a model and
// never get persisted to disk.

import type { PublisherPill } from "../sources";
import type { Manifest } from "../duckdb";

// -----------------------------------------------------------------------------
// Semantic catalogue (per D-04).
// -----------------------------------------------------------------------------
//
// Derived at startup from datasets/manifest.json + the taxonomy parquets.
// MUST NOT be sourced from any fact table. The `no-fact-scan` vitest spies
// on every SQL string and asserts allowlist conformance.

export interface CatalogueState {
  /** Internal canonical id (e.g. "tamil-nadu"). Used as Hive partition value. */
  readonly partition_id: string;
  /** ECI state code (e.g. "S22"). */
  readonly eci_code: string;
  /** Citizen-readable display name (e.g. "Tamil Nadu"). */
  readonly display_name: string;
}

export interface CatalogueElectionPeriod {
  /** Period label as it appears in canonical Parquet (e.g. "AcGenMay2026"). */
  readonly period_label: string;
  /** Human-readable label (e.g. "Tamil Nadu AC General — May 2026"). */
  readonly display_name: string;
  /** State partition the period belongs to (e.g. "tamil-nadu"). */
  readonly state_partition_id: string;
}

export interface CatalogueParty {
  /** ECI short code (e.g. "DMK"). */
  readonly short_code: string;
  /** Citizen-readable display name (e.g. "Dravida Munnetra Kazhagam"). */
  readonly display_name: string;
}

export interface CatalogueSource {
  readonly source_id: string;
  readonly producer: string;
  readonly title: string;
  readonly vintage: string;
}

export interface CatalogueTable {
  /** Manifest table_id (e.g. "elections.election_results"). */
  readonly table_id: string;
  readonly family: string;
  readonly kind: string;
  readonly partition_columns: readonly string[];
}

/**
 * The full lab-internal semantic catalogue. Built once per page load by
 * `loadSemanticCatalogue()` in `./semantic-catalogue.ts`.
 */
export interface SemanticCatalogue {
  readonly tables: readonly CatalogueTable[];
  readonly states: readonly CatalogueState[];
  readonly election_periods: readonly CatalogueElectionPeriod[];
  readonly parties: readonly CatalogueParty[];
  readonly sources: readonly CatalogueSource[];
  /** Reference to the underlying manifest so compiler can do its own lookups. */
  readonly manifest: Manifest;
}

// -----------------------------------------------------------------------------
// DuckDB plan (per D-05).
// -----------------------------------------------------------------------------
//
// `compileIntent(intent, catalogue) -> DuckDBPlan` is PURE. The plan is the
// instruction set the executor runs against `lib/duckdb.ts`. Encoded this
// way so the compiler can be unit-tested without booting WASM.

export interface DuckDBSliceRegistration {
  readonly table_id: string;
  readonly partition_filter: Readonly<Record<string, string>>;
  readonly view_name: string;
}

export interface DuckDBTableRegistration {
  readonly table_id: string;
  readonly view_name: string;
}

/**
 * F1.3b: a long-format CSV URL the executor must register with
 * DuckDB-WASM (via `registerCsvFile`) before running the SQL strings.
 * The URL is spliced INLINE into the `main_sql` / `provenance_sql`
 * `read_csv('<url>', columns={...})` calls by the compiler; the
 * executor only registers the URL so DuckDB-WASM streams it over HTTP
 * Range when the query runs. No SQL view name is created (the URL
 * itself is the view).
 */
export interface DuckDBCsvRegistration {
  readonly url: string;
}

export interface DuckDBPlan {
  /**
   * The originating intent's concept_id. Carried on the plan so the
   * executor can write it into the AnswerViewModel.computation block
   * without re-deriving it from SQL string shape.
   */
  readonly concept_id: string;
  /** Partition-scoped views to register before the main query. */
  readonly slice_registrations: readonly DuckDBSliceRegistration[];
  /** Full-table views to register (e.g. taxonomy.sources). */
  readonly table_registrations: readonly DuckDBTableRegistration[];
  /**
   * F1.3b CSV URLs to register with DuckDB-WASM before the SQL runs.
   * Empty array when the concept reads only Parquet (legacy plans pre-
   * F1.3b, and any future plan that touches only dim_* parquets).
   */
  readonly csv_registrations: readonly DuckDBCsvRegistration[];
  /** Main SELECT — must reference the views registered above. */
  readonly main_sql: string;
  /**
   * Provenance SELECT - joined separately so the source_strip is built
   * deterministically even when the main SQL aggregates. The result MUST
   * be a list of 5-col `SourceRow`-shaped rows from `taxonomy.sources`
   * (the executor casts them to that shape after running the query, then
   * dedupes to publisher pills via `dedupeToPills` at the boundary).
   *
   * Per D-06: when the provenance SELECT returns zero rows, the executor
   * synthesises a single placeholder pill labelled "Source unattested"
   * AND sets `provenance_status: "missing"` on the AnswerViewModel.
   */
  readonly provenance_sql: string;
  /**
   * View-model assembly hints. The renderer uses these to decide column
   * order, formatting, and headline-question text.
   */
  readonly view_hints: AnswerViewHints;
}

export interface AnswerViewHints {
  /** Citizen-facing question that the plan claims to answer. */
  readonly question: string;
  /** Ordered list of column ids that should appear in the rendered table. */
  readonly column_order: readonly string[];
  /** Human-readable column labels keyed by column id. */
  readonly column_labels: Readonly<Record<string, string>>;
  /** Per-column display format ("integer" | "percentage" | "thousands" | "text"). */
  readonly column_formats: Readonly<Record<string, ColumnFormat>>;
}

export type ColumnFormat = "integer" | "percentage" | "thousands" | "text";

// -----------------------------------------------------------------------------
// Provenance helpers (per D-06).
// -----------------------------------------------------------------------------

/**
 * Synthesises a placeholder publisher pill when the provenance JOIN
 * returns zero rows. Citizen sees a visible "source unattested" notice
 * via the renderer (which checks `provenance_status: "missing"` and
 * surfaces a banner separately).
 *
 * Mirrors the canonical PublisherPill shape (lib/sources/types.ts) so
 * the new SourceList component can render it without special-casing.
 */
export function synthesiseUnattestedPill(): PublisherPill {
  return {
    label: "Source unattested",
    vintage_summary: "",
    url: null,
    count: 1,
  };
}
