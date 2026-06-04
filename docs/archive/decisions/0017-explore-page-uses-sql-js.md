# ADR-0017: /explore page uses sql.js (not @sqlite.org/sqlite-wasm)

**Last Updated**: 2026-05-19
**Status**: superseded (by [ADR-0030 — canonical store on DuckDB-WASM + Parquet](0030-canonical-store-duckdb-wasm.md), 2026-05-19)

> **Superseded 2026-05-19 (PR-R.3, TODO row `1.8e`).** The `/explore` page migrated off sql.js + per-state `results.sqlite` shards onto DuckDB-WASM + the canonical Parquet store in PR-L (Phase 1.6b). The `sql.js` and `@types/sql.js` packages were removed from `frontend/package.json` in PR-R.3 (Phase 1.8e) alongside the deletion of `frontend/src/lib/sql.ts`, `frontend/src/lib/psephlab/actuals.ts`, `backend/yen_gov/emit/sqlite.py`, and the 41 `datasets/elections/<event>/<state>/results.sqlite` files. See [data-loading.md](../frontend/data-loading.md) (\"What this removes from the bundle\") and the deletion manifest row 1.8e in [canonical-pivot-deletion-manifest.md](../canonical-pivot-deletion-manifest.md). The body below is preserved as the audit trail for the original 2026-05-09 decision.

## Context

Phase 9 introduces an `/explore` page where the user can run ad-hoc SQL against the per-state SQLite database emitted in Phase 5 (ADR-0014). The per-state file is small (~150 KB for TN, similar for KL), read-only, and already shipped with the static bundle.

Two browser SQLite implementations are mature enough to depend on:

| | `sql.js` | `@sqlite.org/sqlite-wasm` |
|--|--|--|
| Source | Emscripten port of SQLite, community-maintained | Official SQLite project |
| Bundle (gzip) | ~370 KB | ~570 KB (+ a worker file) |
| API | Synchronous, single-threaded | Async, worker-only by default (OPFS support) |
| Persistence | None (in-memory) — caller passes `Uint8Array` | OPFS / IndexedDB / in-memory |
| Init | One `initSqlJs()` call | Worker plumbing + promiser |

Our requirements:

- Open a `~150 KB` `.sqlite` file fetched from `/data/elections/.../results.sqlite`.
- Run user-typed SELECTs against it.
- Render rows as a table.
- No need to write back, no need to persist across sessions, no need for OPFS, no need for multi-tab coordination.

## Decision

Use **`sql.js`**. The whole `/explore` page becomes:

1. `fetch()` the `.sqlite` bytes, hand them to `new SQL.Database(uint8)`.
2. Call `db.exec(sql)` on each user submission, render the result.

We do **not** introduce a Web Worker for query execution. SQLite's in-memory engine on a 150 KB DB returns sub-millisecond on every query we can imagine for this dataset. If a future schema (a country-level rollup file, or a per-PC index) crosses the threshold where main-thread SELECTs become noticeable, we can revisit — at that point a worker is a `new Worker(url)` away, with the existing API surface largely intact.

## Consequences

**Good**

- ~200 KB smaller initial payload than the official wasm. The /explore page is opt-in (only loaded when the user navigates there) so we lazy-import it inside the route component, keeping the rest of the bundle untouched.
- Zero worker plumbing. The page is ~80 lines of Svelte.
- API has been stable since 2018; well-trodden examples and Stack Overflow answers.

**Bad**

- Lower-level than the official binding. We hand-roll table rendering of `db.exec()` row arrays.
- No OPFS — every visit re-fetches the file. Cached by HTTP at 304, so the cost is one HEAD round-trip after the first load. Acceptable.

## Alternatives considered

- **`@sqlite.org/sqlite-wasm`** — the official package. Rejected for the bundle-size and worker-plumbing reasons above. Strongly preferred when (a) the database is large enough that main-thread queries block the UI, or (b) write-back/OPFS persistence is needed. Neither applies.
- **DuckDB-Wasm** — overkill for 150 KB and adds analytic-DB semantics we don't need. Bundle ~2 MB.
- **Re-emit the DB as JSON** and skip SQL entirely. Rejected: it duplicates the work of ADR-0014 and removes the user-facing affordance the /explore page exists to provide.
