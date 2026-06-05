// DuckDB-WASM lazy init + query helper.
//
// Per canonical-store.md §15: the reader fetches long-format CSV files
// via HTTP Range and queries them through DuckDB-WASM `read_csv(columns=...)`
// (MIGRATING from Hive-partitioned Parquet per the platform-reset plan
// chunks F1 / X1a). We init lazily (first use) and cache the connection;
// the WASM bundle is ~10 MB so we never pay for it on routes that don't
// need it.
//
// Phase 0.8 scope: this module exposes the init seam + a thin query API.
// A real round-trip read test that exercises WASM + Web Workers belongs
// in Playwright (Phase 1, when the first canonical-backed citizen route
// lands). Unit tests in vitest can't run the WASM realistically — vitest
// is jsdom + Node, no real Web Worker shim. Treat this file as the
// integration seam, not the unit-test target.

import * as duckdb from "@duckdb/duckdb-wasm";

let connectionPromise: Promise<duckdb.AsyncDuckDBConnection> | null = null;

export async function getConnection(): Promise<duckdb.AsyncDuckDBConnection> {
  if (connectionPromise) return connectionPromise;
  connectionPromise = init();
  return connectionPromise;
}

async function init(): Promise<duckdb.AsyncDuckDBConnection> {
  const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
  const workerUrl = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker!}");`], { type: "text/javascript" }),
  );
  const worker = new Worker(workerUrl);
  const logger = new duckdb.ConsoleLogger();
  const db = new duckdb.AsyncDuckDB(logger, worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  URL.revokeObjectURL(workerUrl);
  return db.connect();
}

// Run a SELECT against a long-format CSV file (URL relative to the Pages
// origin). Caller supplies the SQL with the CSV path templated in via
// read_csv(<path>, columns={...}) per the typed-read boundary contract
// (parent plan section 21.5; CLAUDE.md Holy Law #3). Returns plain rows
// for the view-model layer to map.
export async function queryCsv<T = Record<string, unknown>>(
  sql: string,
): Promise<T[]> {
  const con = await getConnection();
  const result = await con.query(sql);
  return result.toArray().map((r) => r.toJSON() as T);
}

/**
 * Deprecated: use `queryCsv`.
 *
 * Kept as a re-export so any in-flight branch still importing the old
 * name compiles. The body is identical: DuckDB-WASM `con.query(sql)` is
 * format-agnostic, so renaming is naming-only. Removed by chunk X1a
 * (the atomic reader flip) once all callers move to `queryCsv`.
 */
export const queryParquet = queryCsv;

// For tests + teardown only. Production never closes.
export async function _resetForTests(): Promise<void> {
  if (!connectionPromise) return;
  try {
    const con = await connectionPromise;
    await con.close();
  } catch {
    // ignore; we're tearing down
  }
  connectionPromise = null;
}
