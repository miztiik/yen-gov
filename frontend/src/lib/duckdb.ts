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

import { DATA_BASE } from "./paths";

// -----------------------------------------------------------------------------
// Manifest contract (D21)
// -----------------------------------------------------------------------------

export interface ManifestFile {
  path: string;
  size_bytes: number;
  row_count: number;
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
  manifest_version: string;
  generated_at: string;
  tables: ManifestTable[];
}

const MANIFEST_URL = `${DATA_BASE}/manifest.json`;

let manifestPromise: Promise<Manifest> | null = null;

export function loadManifest(): Promise<Manifest> {
  if (manifestPromise) return manifestPromise;
  manifestPromise = (async () => {
    const res = await fetch(MANIFEST_URL);
    if (!res.ok) {
      throw new Error(`manifest fetch failed: ${res.status} ${res.statusText}`);
    }
    return (await res.json()) as Manifest;
  })();
  manifestPromise.catch(() => {
    manifestPromise = null;
  });
  return manifestPromise;
}

export function tableFromManifest(m: Manifest, table_id: string): ManifestTable {
  const t = m.tables.find(x => x.table_id === table_id);
  if (!t) throw new Error(`manifest: table_id not found: ${table_id}`);
  return t;
}

export function fileUrls(table: ManifestTable): string[] {
  return table.files.map(f => `${DATA_BASE}/${f.path}`);
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
const registeredTables = new Set<string>();

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
  const [db, conn, manifest] = await Promise.all([
    dbPromise ?? (dbPromise = bootDB()),
    getConnection(),
    loadManifest(),
  ]);
  const table = tableFromManifest(manifest, table_id);
  const viewName = opts.viewName ?? defaultViewName(table, table_id);
  const key = `${table_id}::${viewName}`;
  if (registeredTables.has(key)) return viewName;

  // Register each Parquet file by its URL so DuckDB-WASM can issue HTTP Range
  // reads. We DON'T pre-buffer the bytes — partitioned tables can be large
  // and DuckDB-WASM's read_parquet over HTTP is exactly the right path.
  for (const url of fileUrls(table)) {
    await db.registerFileURL(url, url, duckdb.DuckDBDataProtocol.HTTP, false);
  }

  const urlList = fileUrls(table)
    .map(u => `'${u.replace(/'/g, "''")}'`)
    .join(", ");
  await conn.query(
    `CREATE OR REPLACE VIEW "${viewName}" AS SELECT * FROM read_parquet([${urlList}])`,
  );
  registeredTables.add(key);
  return viewName;
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
  registeredTables.clear();
}
