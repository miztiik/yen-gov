// Typed-read column-map helper for the CSV reader seam (F1.3a).
//
// Per CLAUDE.md Holy Law #3 ("contracts before logic") + parent plan
// section 22.4 contract invariant #4: every `read_csv(...)` call in the
// frontend MUST pass an explicit `columns={col1: 'TYPE', ...}` map. We
// NEVER `read_csv_auto`. The shape of every CSV file_class lives ONCE
// at `datasets/data/_schema/columns.json` (the D-DOC0 column contract);
// this module fetches that file at runtime and turns it into the DuckDB
// SQL fragment view-models can splice into their queries.
//
// Architectural notes:
//   - Async + single-flight: columns.json is small (a few KB); fetched
//     once per browser session and cached as a Promise so concurrent
//     callers share the same in-flight fetch.
//   - No hand-typed column lists: any caller that hand-rolls a map is
//     a Definition-of-Done violation per the F1 sub-plan invariants.
//   - Path served by Vite middleware `serveDatasets()` (see
//     `frontend/vite.config.ts`) at `/data/_schema/columns.json`. In
//     production the GitHub Pages workflow copies the same file into
//     `_site/data/_schema/columns.json` (see CLAUDE.md section 4
//     "frontend MUST NOT commit data files").
//
// Glob handling: file_class keys in columns.json may carry `=*` segments
// (e.g. `datasets/elections/assembly/state=*/election=*/candidacies.csv`).
// `fileClassForCsvPath(path)` collapses a concrete on-disk path back to
// its file_class glob so view-models can call `csvColumnsClause(path)`
// without knowing the schema-of-schemas glob shape.

import { DATA_BASE } from "../paths";

// -----------------------------------------------------------------------------
// columns.json shape (mirrors `datasets/data/_schema/columns.schema.json`)
// -----------------------------------------------------------------------------

/** Allowed dtypes in columns.json. Mirrors the columns.schema.json enum. */
export type CsvColumnDtype =
  | "string"
  | "integer"
  | "number"
  | "boolean"
  | "date"
  | "datetime";

export interface CsvColumnSpec {
  name: string;
  dtype: CsvColumnDtype;
  nullable: boolean;
  pk?: boolean;
  fk?: string;
  enum?: readonly string[];
  derived?: boolean;
}

export interface CsvFileClassSpec {
  notes?: string;
  columns: readonly CsvColumnSpec[];
}

export interface CsvColumnsContract {
  $schema: string;
  $schema_version: string;
  file_classes: Record<string, CsvFileClassSpec>;
}

// -----------------------------------------------------------------------------
// Fetch + cache
// -----------------------------------------------------------------------------

// `DATA_BASE` is `${BASE_URL}data` (e.g. `/data` in dev, `/yen-gov/data` on
// Pages) and the Vite middleware in `frontend/vite.config.ts:serveDatasets`
// maps `/data/*` -> `<repoRoot>/datasets/*`. The CSV column contract lives
// at `<repoRoot>/datasets/data/_schema/columns.json` so the URL has the
// awkward but correct double-`data` segment: the first `data` is the URL
// mount, the second is the `datasets/data/` subdir within the served tree.
const COLUMNS_URL = `${DATA_BASE}/data/_schema/columns.json`;

let contractPromise: Promise<CsvColumnsContract> | null = null;

/** Public for tests + advanced callers. View-models normally use
 *  `csvColumnsClause(...)` which goes through this internally. */
export async function loadCsvColumnsContract(): Promise<CsvColumnsContract> {
  if (contractPromise) return contractPromise;
  contractPromise = (async () => {
    const res = await fetch(COLUMNS_URL);
    if (!res.ok) {
      throw new Error(
        `csv-columns: fetch failed: ${res.status} ${res.statusText} (${COLUMNS_URL})`,
      );
    }
    const body = (await res.json()) as CsvColumnsContract;
    if (typeof body !== "object" || body === null || !body.file_classes) {
      throw new Error(
        `csv-columns: malformed columns.json (missing file_classes)`,
      );
    }
    return body;
  })();
  contractPromise.catch(() => {
    contractPromise = null;
  });
  return contractPromise;
}

// -----------------------------------------------------------------------------
// CSV-path -> file_class resolution
// -----------------------------------------------------------------------------

/**
 * Map a concrete CSV path under `datasets/...` back to its file_class
 * glob in columns.json. `state=tamil-nadu` -> `state=*`, `election=2021`
 * -> `election=*`, leaving the rest untouched. Pure; no I/O.
 *
 * Example:
 *   datasets/elections/assembly/state=tamil-nadu/election=2021/candidacies.csv
 *     -> datasets/elections/assembly/state=*\/election=*\/candidacies.csv
 *
 * Filename-glob handling: the partition-collapse output remains the
 * primary file_class shape. When a file class is keyed by a bare
 * filename wildcard (e.g. `datasets/data/datapoints/geo/*.csv`,
 * `datasets/data/datapoints/electoral/*.csv` - the per-indicator
 * canonical CSV file classes), the partition-collapsed form does NOT
 * match. The lookup callers (`csvColumnsClause`, `csvColumnsSpec`) walk
 * a `[exact, filename-glob]` sequence via `candidateFileClassKeys` so
 * the schema-of-schemas keeps a single glob entry per file class
 * without minting a new entry per concrete file.
 */
export function fileClassForCsvPath(csvPath: string): string {
  return csvPath.replace(/=[^/]+/g, "=*");
}

/** Ordered file_class lookup-key candidates for a concrete CSV path.
 *  Tried in order: (1) the partition-collapsed path as-is (exact +
 *  partition-wildcard file classes), (2) `<dirname>/*<ext>` (filename-
 *  wildcard file classes like `datasets/data/datapoints/geo/*.csv`).
 *  Duplicates suppressed when collapse #1 and #2 yield the same key. */
export function candidateFileClassKeys(csvPath: string): readonly string[] {
  const partitionCollapsed = fileClassForCsvPath(csvPath);
  const lastSlash = partitionCollapsed.lastIndexOf("/");
  if (lastSlash < 0) return [partitionCollapsed];
  const filename = partitionCollapsed.slice(lastSlash + 1);
  const lastDot = filename.lastIndexOf(".");
  if (lastDot <= 0) return [partitionCollapsed];
  const ext = filename.slice(lastDot);
  const dirname = partitionCollapsed.slice(0, lastSlash);
  const filenameGlob = `${dirname}/*${ext}`;
  if (filenameGlob === partitionCollapsed) return [partitionCollapsed];
  return [partitionCollapsed, filenameGlob];
}

// -----------------------------------------------------------------------------
// DuckDB columns={...} fragment builder
// -----------------------------------------------------------------------------

/** Map a columns.json dtype to the DuckDB type literal used inside
 *  `read_csv(<path>, columns={col: 'TYPE'})`. `boolean` lifts to
 *  `BOOLEAN`; `date` and `datetime` lift to `DATE` / `TIMESTAMP`. */
function duckdbType(dtype: CsvColumnDtype): string {
  switch (dtype) {
    case "string":
      return "VARCHAR";
    case "integer":
      return "BIGINT";
    case "number":
      return "DOUBLE";
    case "boolean":
      return "BOOLEAN";
    case "date":
      return "DATE";
    case "datetime":
      return "TIMESTAMP";
  }
}

function escapeSqlIdent(name: string): string {
  // Column names in DuckDB `columns={...}` map keys are SQL string
  // literals. Escape any embedded single-quote. Our columns are all
  // ASCII identifiers so this is defensive only.
  return name.replace(/'/g, "''");
}

/** Build the `columns={'col1': 'TYPE', ...}` SQL fragment for one
 *  file_class. Pure; consumed by callers after the contract is loaded. */
export function buildColumnsClause(spec: CsvFileClassSpec): string {
  const entries = spec.columns
    .map((c) => `'${escapeSqlIdent(c.name)}': '${duckdbType(c.dtype)}'`)
    .join(", ");
  return `columns={${entries}}`;
}

/**
 * Fetch the contract (once) and return the `columns={...}` SQL fragment
 * for the file_class matching `csvPath`. Throws if the file_class is
 * absent from columns.json - that is a schema-contract gap, not a
 * runtime miss, and should fail loud at the boundary.
 *
 * This is the single function view-models call. Example:
 *
 *   const path = `datasets/elections/assembly/state=${slug}/election=${yr}/candidacies.csv`;
 *   const clause = await csvColumnsClause(path);
 *   const sql = `SELECT * FROM read_csv('${path}', ${clause})`;
 */
export async function csvColumnsClause(csvPath: string): Promise<string> {
  const contract = await loadCsvColumnsContract();
  const candidates = candidateFileClassKeys(csvPath);
  for (const key of candidates) {
    const spec = contract.file_classes[key];
    if (spec) return buildColumnsClause(spec);
  }
  throw new Error(
    `csv-columns: no file_class match for ${csvPath} (looked up ${candidates.join(", ")})`,
  );
}

/** Convenience: return the typed column list for a file_class without
 *  building the SQL fragment. View-models that need to type their row
 *  shapes can use this for IDE/type cross-checks. */
export async function csvColumnsSpec(
  csvPath: string,
): Promise<readonly CsvColumnSpec[]> {
  const contract = await loadCsvColumnsContract();
  const candidates = candidateFileClassKeys(csvPath);
  for (const key of candidates) {
    const spec = contract.file_classes[key];
    if (spec) return spec.columns;
  }
  throw new Error(
    `csv-columns: no file_class match for ${csvPath} (looked up ${candidates.join(", ")})`,
  );
}

// -----------------------------------------------------------------------------
// Test-only reset
// -----------------------------------------------------------------------------

/** Reset the singleton cache. NOT for production use. */
export function __resetForTests(): void {
  contractPromise = null;
}
