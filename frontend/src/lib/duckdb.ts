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
import { csvColumnsClause } from "./canonical/csv-columns";
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
  // Post-B3 (2026-06-06): the parquet table_ids below are retired in X1b (#814)
  // (production manifest no longer carries them). Entries kept as inert
  // mock-fixture compatibility shims: the schema files were deleted in B3
  // but vitest mock manifests still spell these table_ids. The map only
  // fires when the manifest actually carries the table_id, so live readers
  // never hit these mappings post-X1b.
  //
  // X1a-fu2-A (2026-06-07): `"taxonomy.entities"` dropped because zero
  // live readers reference it - loadStates flipped to
  // `datasets/data/entities/geo.csv` via `registerCsvFile` +
  // `read_csv(columns=...)`; loadDistricts + loadAllDistrictEntities
  // flipped to `datasets/taxonomy/entities.json` (the hand-authored SoT)
  // for the legacy_id + IN-<eci>-D<lgd> shape preservation.
  "elections.dim_acs": "dim-acs.schema.json",
  "elections.dim_parties": "dim-parties.schema.json",
  "elections.dim_pcs": "dim-pcs.schema.json",
  "elections.dim_party_alliances": "dim-party-alliances.schema.json",
  "elections.dim_persons": "dim-persons.schema.json",
  "elections.elections_candidacies": "elections-candidacies.schema.json",
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

/**
 * Eagerly start the DuckDB-WASM boot (bundle download + worker spawn +
 * instantiate) without waiting for it. Idempotent. Safe to call multiple
 * times - the first call seeds the singleton promise, every subsequent
 * call resolves to the same in-flight handle.
 *
 * Use from route entrypoints that WILL need DuckDB (Home, Topic, state
 * pages) so the ~1-2s cold-boot pays in parallel with topic-catalogue
 * fetch + Svelte hydration, NOT serially after the first
 * `registerCsvAsTable(...)` waits for it.
 *
 * Returns void by design: callers must NOT await this. Use `getConnection`
 * or the high-level `registerTable` / `registerCsvAsTable` helpers when
 * you actually need to query.
 */
export function prewarmDB(): void {
  if (!dbPromise) dbPromise = bootDB();
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
// CSV file URL registration (F1.3a typed-read seam)
// -----------------------------------------------------------------------------

const registeredCsvUrls = new Set<string>();

// In-flight CSV registrations keyed by URL. `registerCsvFile` is called
// concurrently for the SAME files by independent loaders (e.g. the AC
// district enrichment map and the AC-entity name index both register
// electoral.csv / membership.csv / geo.csv at once). The plain
// `has() ... await ... add()` shape is a check-then-act race: two
// concurrent callers both see `has(url) === false` and BOTH call
// `db.registerFileURL(url, ...)`, and DuckDB-WASM throws on the second
// registration of an already-registered name - rejecting one loader. The
// completed `registeredCsvUrls` set is the fast path; this map collapses
// the racing window so the underlying `registerFileURL` runs exactly once
// per URL and every concurrent caller awaits the same promise.
const inflightCsvRegistrations = new Map<string, Promise<void>>();

/**
 * Register a CSV file URL with DuckDB-WASM so subsequent `read_csv(<url>,
 * columns={...})` SQL can fetch it via HTTP. Idempotent per session.
 *
 * Unlike `registerTable` / `registerSlice` (which wrap a Parquet view
 * named via the manifest contract), this helper does not create a named
 * SQL view. View-models splice the URL directly into their `read_csv(...)`
 * call so they can pair it with a typed `columns={...}` clause built from
 * `frontend/src/lib/canonical/csv-columns.ts:csvColumnsClause`.
 *
 * Manifest contract is unchanged: the F1 cutover keeps the Parquet
 * manifest in place (the manifest only describes the Parquet store).
 * Long-format CSV files are addressed by deterministic per-(state, year)
 * paths derived from `canonical/election-csv-paths.ts`, NOT by manifest
 * lookup. X1a (the atomic reader flip) is when the manifest goes away
 * entirely and the typed-read seam becomes the only path.
 */
export async function registerCsvFile(url: string): Promise<void> {
  if (registeredCsvUrls.has(url)) return;
  let registration = inflightCsvRegistrations.get(url);
  if (!registration) {
    registration = (async () => {
      const db = await (dbPromise ?? (dbPromise = bootDB()));
      await db.registerFileURL(url, url, duckdb.DuckDBDataProtocol.HTTP, false);
      registeredCsvUrls.add(url);
    })();
    inflightCsvRegistrations.set(url, registration);
    // On failure, drop the in-flight entry so a later attempt re-registers
    // instead of permanently awaiting a rejected promise.
    registration.catch(() => inflightCsvRegistrations.delete(url));
  }
  return registration;
}

// -----------------------------------------------------------------------------
// CSV-as-table seam (X1a reader flip)
// -----------------------------------------------------------------------------
//
// X1a flips the two legacy taxonomy parquets F1.3a/b explicitly DEFERRED
// to this chunk (`elections.dim_parties` + `taxonomy.sources`) onto the
// canonical CSV store under `datasets/data/entities/`. The signature mirrors
// `registerTable` (idempotent per session, returns the DuckDB view name)
// so view-models swap `registerTable("elections.dim_parties")` ->
// `registerCsvAsTable("elections.dim_parties")` one-line; the JOIN syntax
// in the surrounding SQL is unchanged.
//
// Why a SELECT-aliased view rather than letting view-models call
// `read_csv` inline (the F1.3a pattern for candidacies + summary):
//   - 13 call sites JOIN `dim_parties dp ON dp.party_id = ...` /
//     `JOIN sources s` and reference legacy column names
//     (`dp.short_name`, `dp.brand_colour_hex`, `s.producer`,
//     `s.url`). Renaming each SQL string is a much bigger blast
//     radius than keeping the legacy column names visible at the JOIN
//     surface; the view is the rename point.
//
// Retired-by-rip columns (per parent plan section 20.3 / O3 — parties.csv
// is exactly `{party_id, short, full, eci_codes, brand_colour,
// symbol_asset, wikipedia}`; source.csv is exactly `{source_id, producer,
// title, vintage, url}` post sources-simplification PR-1 2026-06-11)
// project as `NULL::<dtype>` for the parties side so view-models with
// the existing nullable fallback chains (e.g. `r.brand_colour_confidence
// === "high" || ... || null`) degrade gracefully. The 3 retired party
// columns surface NULL everywhere on the parties side; the sources side
// is now natively 5-col (`source_id, producer, title, vintage, url`)
// with NO NULL projections - the v2 6-col extension (`license`,
// `confidence_tier`, `is_issuing_authority`, `verification_method`,
// `citation_full`, `notes`) is retired per ADR-NNNN
// `citation-ledger-5col` (data-provenance.md, 2026-06-11) + the
// PR-1 frontend rewrite in this same PR.
//
// Lifecycle: B3 (the parquet-writer + reader cleanup) eventually deletes
// `registerTable` / `registerSlice` whole. At that point this seam is
// the only path. The legacy table_id strings (`"elections.dim_parties"`,
// `"taxonomy.sources"`) survive as a stable contract for the dispatch
// keys; B3 can rename them then if the citizen-trust grammar wants the
// `elections.` / `taxonomy.` namespace gone.

export type CsvAsTableId = "elections.dim_parties" | "taxonomy.sources";

interface CsvAsTableSpec {
  /** DuckDB view name the view-model SQL JOINs against. */
  readonly viewName: string;
  /** Repo-relative CSV path (sliced into the URL via DATA_BASE). */
  readonly csvRel: string;
  /**
   * Build the `SELECT ... FROM read_csv(<url>, <columnsClause>)` body
   * that becomes the view definition. Returns SQL fragment WITHOUT the
   * `CREATE OR REPLACE VIEW ... AS` prefix (the caller adds that).
   *
   * `columnsClause` is the resolved `columns={...}` fragment derived
   * from `datasets/data/_schema/columns.json` via `csvColumnsClause`.
   * Passed in (rather than hardcoded inline) so a new column landing on
   * parties.csv / source.csv (e.g. G1 2026-06-08 added `aliases`)
   * flows through automatically - schema-as-single-source-of-truth per
   * CLAUDE.md Holy Law #6 + plan section 22.4 contract invariant #4.
   * The SELECT projection still hand-aliases only the columns the
   * legacy parquet view exposed; any new CSV column is read by the
   * underlying read_csv but simply ignored by the SELECT until a
   * consumer wants it.
   */
  selectSql(url: string, columnsClause: string): string;
}

const CSV_AS_TABLE_SPECS: Readonly<Record<CsvAsTableId, CsvAsTableSpec>> = Object.freeze({
  "elections.dim_parties": {
    viewName: "dim_parties",
    csvRel: "data/entities/parties.csv",
    // `full` and `short` are DuckDB reserved words (`full` for FULL OUTER
    // JOIN; `short` overlaps the SHORTINT type ID). The X1a flip
    // (PR #809) authored these columns unquoted and DuckDB-WASM rejected
    // the view with `Parser Error: syntax error at or near "AS"`, which
    // broke every dim_parties consumer (StateOverview, Psephlab, Compare,
    // Constituency). Fixed in E5 (PR for plan section 25.6a) by quoting
    // both identifiers. The seats-invariant gate (plan section 22.6)
    // would otherwise be trivially false because the view returns zero
    // rows -> sum(seats_won)=0 != total_seats=234.
    selectSql: (url: string, columnsClause: string): string => `
      SELECT
        party_id                     AS party_id,
        eci_codes                    AS eci_code,
        "short"                      AS short_name,
        "full"                       AS full_name,
        NULL::VARCHAR                AS recognition,
        NULL::VARCHAR                AS source_id,
        brand_colour                 AS brand_colour_hex,
        NULL::VARCHAR                AS brand_colour_confidence,
        wikipedia                    AS wikipedia_url,
        symbol_asset                 AS election_symbol_asset_path,
        NULL::VARCHAR                AS election_symbol_render_mode
      FROM read_csv('${url}', ${columnsClause}, header=true, auto_detect=false)
    `,
  },
  "taxonomy.sources": {
    viewName: "sources",
    csvRel: "data/entities/source.csv",
    selectSql: (url: string, columnsClause: string): string => `
      SELECT
        source_id                    AS source_id,
        producer                     AS producer,
        title                        AS title,
        vintage                      AS vintage,
        url                          AS url
      FROM read_csv('${url}', ${columnsClause}, header=true, auto_detect=false)
    `,
  },
});

/**
 * X1a CSV-as-table seam. Registers `data/entities/parties.csv` or
 * `data/entities/source.csv` and creates a DuckDB view named `dim_parties`
 * / `sources` with the legacy parquet column shape so view-model SQL
 * keeps JOINing against the same column names without any string rewrite.
 *
 * Idempotent per session via the shared `registeredViews` map (same as
 * `registerTable` / `registerSlice`). Returns the view name the caller
 * would have gotten from `registerTable`.
 */
export async function registerCsvAsTable(table_id: CsvAsTableId): Promise<string> {
  const spec = CSV_AS_TABLE_SPECS[table_id];
  const url = `${DATA_BASE}/${spec.csvRel}`;
  const key = `csv-as-table::${table_id}::${url}`;
  if (registeredViews.get(spec.viewName) === key) return spec.viewName;

  const [db, conn] = await Promise.all([
    dbPromise ?? (dbPromise = bootDB()),
    getConnection(),
  ]);

  // Register the CSV URL with DuckDB so the embedded `read_csv(<url>, ...)`
  // call inside the view body reaches it via HTTP-Range. Mirrors
  // `registerCsvFile` (same cache set + protocol) so a later
  // `registerCsvFile(<same url>)` call is a no-op.
  if (!registeredCsvUrls.has(url)) {
    await db.registerFileURL(url, url, duckdb.DuckDBDataProtocol.HTTP, false);
    registeredCsvUrls.add(url);
  }

  // Resolve the columns={...} clause from the canonical schema BEFORE
  // building the view body. The schema is the single source of truth
  // (CLAUDE.md Holy Law #6); a new column landing on parties.csv /
  // source.csv flows in automatically with no edit to this module. The
  // earlier hand-typed dict drifted on G1 (2026-06-08 - parties.csv
  // gained `aliases`) and silently broke every dim_parties consumer
  // (StateOverview, Psephlab, Compare, Constituency) with the DuckDB
  // sniffer error "7 columns in dict but 8 in file".
  const columnsClause = await csvColumnsClause(`datasets/${spec.csvRel}`);

  await conn.query(
    `CREATE OR REPLACE VIEW "${spec.viewName}" AS ${spec.selectSql(url, columnsClause)}`,
  );
  registeredViews.set(spec.viewName, key);
  return spec.viewName;
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
  registeredCsvUrls.clear();
  inflightCsvRegistrations.clear();
  warnedLegacyMarkers.clear();
}
