// DuckDB-WASM singleton loader for the canonical Parquet store.
//
// Phase 0.8 deliverable per TODO/20260517-canonical-long-format-pivot.md §6.
// Wires @duckdb/duckdb-wasm into an ISOLATED module — citizen routes do NOT
// import this yet (Phase 1.3 swaps loaders behind the view-model contract,
// D19). This module owns three things and only three things:
//
//   1. Lazy DuckDB-WASM boot (singleton; one Connection per browser tab).
//   2. Manifest fetch + table -> URL resolution (D21).
//   3. A thin typed query helper that returns plain JS objects.
//
// SQL composition, view-model shaping, and caveats/break joins live in the
// view-model loader (Phase 1.3). Keep this module the seam, not the policy.
//
// Why a singleton: each DuckDB-WASM init pulls a ~5 MB wasm + spins a worker.
// Multiple inits would race on file registration and waste memory. Per-tab
// singleton matches our SPA model (one navigation tree, one DB).

import * as duckdb from "@duckdb/duckdb-wasm";
import duckdbMvpWasm from "@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url";
import duckdbEhWasm from "@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url";
import mvpWorker from "@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url";
import ehWorker from "@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url";

import { acceptedSchemaVersions } from "./canonical/schema-compatibility";
import { DATA_BASE } from "./paths";

// -----------------------------------------------------------------------------
// Manifest contract (D21)
// -----------------------------------------------------------------------------

export interface ManifestFile {
  path: string;
  size_bytes: number;
  row_count: number;
  partition_values?: Record<string, string>;
}

export interface ManifestTable {
  table_id: string;
  family: string;
  table_name?: string;
  kind?: "observations" | "dim" | "taxonomy" | "other";
  format: "parquet";
  schema_version: string;
  partition_columns: string[];
  files: ManifestFile[];
  row_count_total: number;
}

export interface Manifest {
  $schema: string;
  $schema_version: string;
  manifest_version: string;
  generated_at: string;
  tables: ManifestTable[];
}

const MANIFEST_URL = `${DATA_BASE}/manifest.json`;

let manifestPromise: Promise<Manifest> | null = null;

const ROW_SCHEMA_BY_TABLE_ID: Readonly<Record<string, string>> = Object.freeze({
  "elections.dim_acs": "dim-acs.schema.json",
  "elections.dim_parties": "dim-parties.schema.json",
  "elections.dim_party_alliances": "dim-party-alliances.schema.json",
  "elections.dim_persons": "dim-persons.schema.json",
  "elections.elections_candidacies": "elections-candidacies.schema.json",
  "taxonomy.entities": "entity.schema.json",
  "taxonomy.indicators": "indicator-catalogue.schema.json",
  "taxonomy.methodology_breaks": "methodology-break.schema.json",
  "taxonomy.persons": "persons.schema.json",
  "taxonomy.sources": "source.schema.json",
});

function assertSupportedSchemaVersion(schemaFile: string, version: string, subject: string): void {
  const acceptedVersions = acceptedSchemaVersions(schemaFile);
  if (acceptedVersions.includes(version)) return;

  const rendered = acceptedVersions.length > 0 ? acceptedVersions.join(", ") : "none";
  throw new Error(
    `schema_version_unsupported: ${subject} schema_version ${version} ` +
      `not in reader's supported set for ${schemaFile}: ${rendered}`,
  );
}

function assertSupportedManifestVersion(manifest: Manifest): void {
  if (typeof manifest.$schema_version !== "string") {
    throw new Error("manifest: missing $schema_version");
  }
  assertSupportedSchemaVersion("manifest.schema.json", manifest.$schema_version, "manifest");
}

export function rowSchemaFileForTable(table: ManifestTable): string {
  if (table.kind === "observations") return "observation.schema.json";
  const schemaFile = ROW_SCHEMA_BY_TABLE_ID[table.table_id];
  if (schemaFile) return schemaFile;

  throw new Error(
    `manifest: no row schema mapping for ${table.table_id}; ` +
      "add manifest row_schema_id or an explicit runtime mapping",
  );
}

function assertSupportedTableVersion(table: ManifestTable): void {
  const schemaFile = rowSchemaFileForTable(table);
  assertSupportedSchemaVersion(schemaFile, table.schema_version, `table '${table.table_id}'`);
}

export function loadManifest(): Promise<Manifest> {
  if (manifestPromise) return manifestPromise;
  manifestPromise = (async () => {
    const res = await fetch(MANIFEST_URL);
    if (!res.ok) {
      throw new Error(`manifest fetch failed: ${res.status} ${res.statusText}`);
    }
    const manifest = (await res.json()) as Manifest;
    assertSupportedManifestVersion(manifest);
    return manifest;
  })();
  manifestPromise.catch(() => {
    manifestPromise = null;
  });
  return manifestPromise;
}

export function tableFromManifest(m: Manifest, table_id: string): ManifestTable {
  const t = m.tables.find(x => x.table_id === table_id);
  if (!t) throw new Error(`manifest: table_id not found: ${table_id}`);
  assertSupportedTableVersion(t);
  return t;
}

export function fileUrls(table: ManifestTable): string[] {
  return fileUrlsForFiles(table.files);
}

function fileUrlsForFiles(files: readonly ManifestFile[]): string[] {
  return files.map(f => `${DATA_BASE}/${f.path}`);
}

export type PartitionFilter = Record<string, string>;

export function filesForSlice(
  table: ManifestTable,
  partitionFilter: PartitionFilter,
  opts: { allowFullTableFallback?: boolean } = {},
): ManifestFile[] {
  const entries = Object.entries(partitionFilter);
  if (entries.length === 0) {
    throw new Error(`manifest: slice filter for ${table.table_id} is empty`);
  }

  if (table.partition_columns.length === 0) {
    if (opts.allowFullTableFallback) return table.files;
    throw new Error(
      `manifest: table ${table.table_id} is unpartitioned; use registerTable ` +
        `or pass allowFullTableFallback`,
    );
  }

  const partitionColumns = new Set(table.partition_columns);
  for (const [key] of entries) {
    if (!partitionColumns.has(key)) {
      const known = table.partition_columns.length > 0
        ? table.partition_columns.join(", ")
        : "none";
      throw new Error(
        `manifest: unknown partition key "${key}" for ${table.table_id}; ` +
          `partition_columns: ${known}`,
      );
    }
  }

  const files = table.files.filter(file =>
    entries.every(([key, value]) => file.partition_values?.[key] === value),
  );
  if (files.length === 0) {
    const rendered = entries.map(([key, value]) => `${key}=${value}`).join(", ");
    throw new Error(`manifest: no files match ${table.table_id} partition ${rendered}`);
  }
  return files;
}

/**
 * Default DuckDB view name for a manifest table when the caller does not
 * pass an explicit `viewName`. Prefers the manifest's `table_name` field
 * (added in manifest.schema.json v1.1 per THE PLAN row 1.8a-bis); falls
 * back to the last dotted segment of `table_id` for back-compat with
 * older manifests that pre-date the field.
 *
 * Pure helper — exported so contract tests can assert the defaulting rule
 * without booting DuckDB-WASM in vitest (Phase 0.11 Playwright owns the
 * real round-trip).
 */
export function defaultViewName(table: ManifestTable, table_id: string): string {
  return table.table_name ?? table_id.split(".").pop()!;
}

// -----------------------------------------------------------------------------
// DuckDB-WASM singleton
// -----------------------------------------------------------------------------

let dbPromise: Promise<duckdb.AsyncDuckDB> | null = null;
let connPromise: Promise<duckdb.AsyncDuckDBConnection> | null = null;
const registeredViews = new Map<string, string>();

// One-shot warning latch for deprecated legacy paths. Surfaces in the
// browser console the first time the loader sees a URL pointing at a
// retired Parquet file (e.g. `elections/observations.parquet`, renamed
// to `elections/election_results.parquet` in PR-O.1). PR-O.2-minimal
// adds the surface; PR-O.3 deletes the legacy path entirely. Citizens
// never see this; it exists to give downstream tooling / archived
// embeds a single noisy hint instead of a silent 404 cascade.
const LEGACY_PARQUET_PATTERNS: ReadonlyArray<{ marker: string; successor: string }> = [
  {
    marker: "elections/observations.parquet",
    successor: "elections/election_results.parquet",
  },
];
const warnedLegacyMarkers = new Set<string>();

function warnIfLegacyPath(url: string): void {
  for (const { marker, successor } of LEGACY_PARQUET_PATTERNS) {
    if (!url.includes(marker) || warnedLegacyMarkers.has(marker)) continue;
    warnedLegacyMarkers.add(marker);
    // eslint-disable-next-line no-console
    console.warn(
      `[yen-gov] manifest resolved a deprecated path "${marker}". ` +
        `Update consumers to "${successor}" — see datasets/CHANGELOG.md.`,
    );
  }
}

async function bootDB(): Promise<duckdb.AsyncDuckDB> {
  const bundle = await duckdb.selectBundle({
    mvp: { mainModule: duckdbMvpWasm, mainWorker: mvpWorker },
    eh: { mainModule: duckdbEhWasm, mainWorker: ehWorker },
  });
  if (!bundle.mainWorker) {
    throw new Error("duckdb-wasm: no worker URL resolved from bundle");
  }
  const worker = new Worker(bundle.mainWorker);
  const logger = new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING);
  const db = new duckdb.AsyncDuckDB(logger, worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  return db;
}

export function getConnection(): Promise<duckdb.AsyncDuckDBConnection> {
  if (connPromise) return connPromise;
  if (!dbPromise) dbPromise = bootDB();
  connPromise = dbPromise.then(db => db.connect());
  connPromise.catch(() => {
    connPromise = null;
    dbPromise = null;
  });
  return connPromise;
}

// -----------------------------------------------------------------------------
// Table registration — make a manifest table queryable as a DuckDB view.
// -----------------------------------------------------------------------------

/**
 * Register a manifest table as a DuckDB view backed by HTTP-Range reads of
 * the manifest's Parquet files. Idempotent per table_id within this session.
 *
 * After this call, `SELECT * FROM <view_name>` queries the canonical store.
 * View name defaults to the last segment of table_id (e.g. "elections.election_results"
 * -> "election_results"); pass a custom name when two tables would collide.
 */
export async function registerTable(
  table_id: string,
  opts: { viewName?: string } = {},
): Promise<string> {
  const manifest = await loadManifest();
  const table = tableFromManifest(manifest, table_id);
  const viewName = opts.viewName ?? defaultViewName(table, table_id);
  const [db, conn] = await Promise.all([
    dbPromise ?? (dbPromise = bootDB()),
    getConnection(),
  ]);
  await registerFilesAsView(db, conn, viewName, table_id, fileUrls(table));
  return viewName;
}

export async function registerSlice(
  table_id: string,
  partitionFilter: PartitionFilter,
  opts: { viewName?: string; allowFullTableFallback?: boolean } = {},
): Promise<string> {
  const manifest = await loadManifest();
  const table = tableFromManifest(manifest, table_id);
  const viewName = opts.viewName ?? defaultViewName(table, table_id);
  const files = filesForSlice(table, partitionFilter, opts);
  const [db, conn] = await Promise.all([
    dbPromise ?? (dbPromise = bootDB()),
    getConnection(),
  ]);
  await registerFilesAsView(db, conn, viewName, table_id, fileUrlsForFiles(files));
  return viewName;
}

async function registerFilesAsView(
  db: duckdb.AsyncDuckDB,
  conn: duckdb.AsyncDuckDBConnection,
  viewName: string,
  table_id: string,
  urls: string[],
): Promise<void> {
  const key = `${table_id}::${urls.join("|")}`;
  if (registeredViews.get(viewName) === key) return;

  // Register each Parquet file by its URL so DuckDB-WASM can issue HTTP Range
  // reads. We DON'T pre-buffer the bytes — partitioned tables can be large
  // and DuckDB-WASM's read_parquet over HTTP is exactly the right path.
  for (const url of urls) {
    warnIfLegacyPath(url);
    await db.registerFileURL(url, url, duckdb.DuckDBDataProtocol.HTTP, false);
  }

  const urlList = urls
    .map(u => `'${u.replace(/'/g, "''")}'`)
    .join(", ");
  await conn.query(
    `CREATE OR REPLACE VIEW "${viewName}" AS SELECT * FROM read_parquet([${urlList}])`,
  );
  registeredViews.set(viewName, key);
}

// -----------------------------------------------------------------------------
// Thin query helper
// -----------------------------------------------------------------------------

/**
 * Run a SQL query and return rows as plain JS objects.
 *
 * Apache Arrow Table -> array of records. Use this for small result sets
 * (chart-sized — <50k rows). For large scans, work with the Arrow Table
 * directly via `(await getConnection()).query(sql)`.
 */
export async function query<T = Record<string, unknown>>(sql: string): Promise<T[]> {
  const conn = await getConnection();
  const result = await conn.query(sql);
  return result.toArray().map(row => row.toJSON() as T);
}

/**
 * Test-only reset hook. NOT for production use.
 */
export function __resetForTests(): void {
  manifestPromise = null;
  dbPromise = null;
  connPromise = null;
  registeredViews.clear();
  warnedLegacyMarkers.clear();
}
