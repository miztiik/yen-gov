// Per-state sql.js Database loader with caching.
//
// Why sql.js (not @sqlite.org/sqlite-wasm): documented in
// docs/architecture/frontend/data-loading.md > "/explore page uses sql.js".
// In short — 200 KB smaller wasm, no worker plumbing, our DBs are <200 KB
// and queries return in sub-millisecond on the main thread.
//
// Caching strategy: one Database per (event, state). Once loaded we keep it
// in memory because Svelte routes re-mount on navigation; without a cache
// every state hop would re-fetch and re-init. The map is unbounded but
// realistic ceilings (4 states × 1 event ≈ 1 MB) are fine.

import initSqlJs, { type Database } from "sql.js";
import wasmUrl from "sql.js/dist/sql-wasm.wasm?url";
import { DATA_BASE } from "./paths";

let sqlInit: ReturnType<typeof initSqlJs> | null = null;
const dbs = new Map<string, Promise<Database>>();

function key(event: string, state: string): string {
  return `${event}/${state}`;
}

/** Resolves to a Database for the given (event, state). Cached after first load. */
export function getDb(event: string, state: string): Promise<Database> {
  const k = key(event, state);
  const cached = dbs.get(k);
  if (cached) return cached;
  if (!sqlInit) sqlInit = initSqlJs({ locateFile: () => wasmUrl });
  const p = (async () => {
    const SQL = await sqlInit!;
    const res = await fetch(`${DATA_BASE}/elections/${event}/${state}/results.sqlite`);
    if (!res.ok) throw new Error(`fetch results.sqlite for ${state}: ${res.status}`);
    const buf = new Uint8Array(await res.arrayBuffer());
    return new SQL.Database(buf);
  })();
  dbs.set(k, p);
  // If the load fails, don't poison the cache — let the next attempt retry.
  p.catch(() => dbs.delete(k));
  return p;
}
