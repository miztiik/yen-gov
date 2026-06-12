// PR-1 of TODO/20260612-party-rendering-and-party-pages-plan.md.
//
// `parties.csv` reader for the PartyPill tooltip + future per-party detail
// page (PR-4) + future parties index (PR-3). One module-level Promise
// caches the full parties.csv as a Map<party_id, PartyMeta>; `loadPartyMeta`
// is a thin per-key accessor on top.
//
// Why a direct `read_csv` instead of the existing `dim_parties` view
// (registered by `registerCsvAsTable("elections.dim_parties")` in
// frontend/src/lib/duckdb.ts): the view exposes only a subset of
// columns (party_id / short_name / full_name / brand_colour_hex /
// wikipedia_url / election_symbol_asset_path) for compatibility with
// pre-X1a parquet consumers; the tooltip needs the 10 identity-metadata
// columns added in `parties.csv` v1.1 (founded_year, dissolved_year,
// recognition_scope, home_state_codes, name_native_script, is_sentinel,
// ...). Reading the CSV directly via `registerCsvFile` + the typed
// `read_csv(<url>, columns={...})` boundary follows the parties-palette.ts
// precedent for direct CSV reads and avoids touching duckdb.ts (which is
// a high-collision file). The two paths use the same DuckDB CSV cache,
// so registering parties.csv twice (once for dim_parties, once for our
// query) is a no-op on the second call.

import { query, registerCsvFile } from "../duckdb";
import { csvColumnsClause } from "../canonical/csv-columns";
import { DATA_BASE } from "../paths";

/** Repo-relative path used by `csvColumnsClause` to look up the typed
 *  column spec from datasets/data/_schema/columns.json. */
const PARTIES_CSV_REL = "datasets/data/entities/parties.csv";

/** Runtime URL the browser fetches via DuckDB-WASM HTTP-Range reads. */
const PARTIES_CSV_URL = `${DATA_BASE}/data/entities/parties.csv`;

/**
 * Citizen-readable identity metadata for one party row in
 * `datasets/data/entities/parties.csv`. Shape locked to the v1.1
 * column set (PR-0 of TODO/20260610-electoral-data-quality-and-party-catalogue-plan.md).
 *
 * Pipe-delimited list columns (`home_state_codes`) are exploded into
 * arrays at the loader boundary so consumers do not re-do the split.
 * Empty strings on optional string columns are normalised to `null`.
 */
export interface PartyMeta {
  /** Opaque slug `parties.IN.<UPPER_TOKEN>`; sole PK. */
  party_id: string;
  /** Display label (e.g. "BJP"). Falls back to `party_id` when the
   *  upstream `short` column is empty - parties.csv v1.1 marks short
   *  NOT NULL but a defensive fallback keeps the tooltip readable
   *  under a future schema bump. */
  short: string;
  /** Long name as commonly cited. Null when upstream blank. */
  full: string | null;
  /** Year the party was founded (integer). Null when not known. */
  founded_year: number | null;
  /** Year the party formally dissolved. Null when still active. */
  dissolved_year: number | null;
  /** ECI recognition class. Enum: `national`, `state`,
   *  `unrecognised_registered`, `defunct`, `sentinel`. Null when
   *  upstream blank. */
  recognition_scope: string | null;
  /** ISO 3166-2 codes for state-recognised parties (e.g. `["IN-TN"]`).
   *  Empty array when upstream blank. */
  home_state_codes: string[];
  /** Repo-relative path under `frontend/public/` to the party's
   *  election-symbol SVG/PNG. Null when no symbol is on file - the
   *  Jony A3 missing-symbol rule says the renderer MUST NOT show a
   *  placeholder. */
  symbol_asset: string | null;
  /** OkLCh hex hint (e.g. "#ea580c"). Null when blank. The 3-tier
   *  party-colour resolver consumes this; the tooltip itself does
   *  NOT paint with this colour. */
  brand_colour: string | null;
  /** Canonical Wikipedia URL. Null when blank - sentinels (IND/NOTA/UNK)
   *  have no wiki entry. */
  wikipedia: string | null;
  /** Non-Latin name where the publisher emits one. Null when blank.
   *  Citizen-surface filtering on the elections route is the consumer's
   *  call (No-Hindi policy lives in url-grammar.md). */
  name_native_script: string | null;
  /** True for the 3 sentinel rows (`parties.IN.UNK`, `parties.IN.IND`,
   *  `parties.IN.NOTA`). The tooltip uses this to suppress the wiki
   *  link + founded line for sentinels even when DuckDB returns a
   *  truthy-looking founded_year for NOTA (2013 was the PUCL v Union
   *  of India ruling, not a party founding). */
  is_sentinel: boolean;
}

/** Raw DuckDB row shape - mirrors parties.csv columns.json typed
 *  projection. All optional CSV columns surface as `string | null`
 *  before normalisation; `BIGINT` columns surface as `number | bigint
 *  | null` (DuckDB-WASM returns a `bigint` for BIGINT columns); the
 *  one boolean column surfaces as `boolean | null`. */
interface RawPartiesRow {
  party_id: string | null;
  short: string | null;
  full: string | null;
  founded_year: number | bigint | null;
  dissolved_year: number | bigint | null;
  recognition_scope: string | null;
  home_state_codes: string | null;
  symbol_asset: string | null;
  brand_colour: string | null;
  wikipedia: string | null;
  name_native_script: string | null;
  is_sentinel: boolean | null;
}

function trimmedOrNull(value: string | null | undefined): string | null {
  if (value == null) return null;
  const trimmed = value.trim();
  return trimmed.length === 0 ? null : trimmed;
}

function intOrNull(value: number | bigint | null | undefined): number | null {
  if (value == null) return null;
  if (typeof value === "bigint") return Number(value);
  return Number.isFinite(value) ? Math.trunc(value) : null;
}

function splitPipe(value: string | null | undefined): string[] {
  if (value == null) return [];
  const trimmed = value.trim();
  if (trimmed.length === 0) return [];
  return trimmed
    .split("|")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

/** Project a raw DuckDB row into the typed `PartyMeta` shape. Pure;
 *  exported so the loader test can drive it against synthetic rows
 *  without going through DuckDB. */
export function toPartyMeta(row: RawPartiesRow): PartyMeta | null {
  const party_id = trimmedOrNull(row.party_id);
  if (!party_id) return null;
  return {
    party_id,
    short: trimmedOrNull(row.short) ?? party_id,
    full: trimmedOrNull(row.full),
    founded_year: intOrNull(row.founded_year),
    dissolved_year: intOrNull(row.dissolved_year),
    recognition_scope: trimmedOrNull(row.recognition_scope),
    home_state_codes: splitPipe(row.home_state_codes),
    symbol_asset: trimmedOrNull(row.symbol_asset),
    brand_colour: trimmedOrNull(row.brand_colour),
    wikipedia: trimmedOrNull(row.wikipedia),
    name_native_script: trimmedOrNull(row.name_native_script),
    is_sentinel: row.is_sentinel === true,
  };
}

/** Module-level promise cache. One `loadAllPartiesMeta()` invocation
 *  fetches parties.csv once per browser tab; every subsequent call -
 *  including every `loadPartyMeta(<pid>)` - resolves to the same Map.
 *  Reset only via `__resetForTests`. */
let allPartiesPromise: Promise<Map<string, PartyMeta>> | null = null;

async function fetchAllPartiesMeta(): Promise<Map<string, PartyMeta>> {
  await registerCsvFile(PARTIES_CSV_URL);
  const columnsClause = await csvColumnsClause(PARTIES_CSV_REL);
  // `short` and `full` are DuckDB reserved words (`short` shadows
  // SHORTINT; `full` shadows FULL OUTER JOIN). Quote them in the
  // projection - same precedent as the dim_parties view in
  // frontend/src/lib/duckdb.ts.
  const rows = await query<RawPartiesRow>(`
    SELECT
      party_id,
      "short"            AS "short",
      "full"             AS "full",
      founded_year,
      dissolved_year,
      recognition_scope,
      home_state_codes,
      symbol_asset,
      brand_colour,
      wikipedia,
      name_native_script,
      is_sentinel
    FROM read_csv('${PARTIES_CSV_URL}', ${columnsClause}, header=true)
  `);
  const map = new Map<string, PartyMeta>();
  for (const raw of rows) {
    const meta = toPartyMeta(raw);
    if (meta) map.set(meta.party_id, meta);
  }
  return map;
}

/** Bulk fetch every party row from parties.csv. Cached for the lifetime
 *  of the browser tab; consumed by the PR-3 parties index + the loader's
 *  own per-key accessor. Returns the SAME Promise on every call (per
 *  the user-memory canonical-store loader pattern); callers MAY await
 *  it concurrently without triggering multiple network fetches. */
export function loadAllPartiesMeta(): Promise<Map<string, PartyMeta>> {
  if (!allPartiesPromise) {
    allPartiesPromise = fetchAllPartiesMeta().catch((err) => {
      // Reset the cache on failure so a retry re-issues the fetch.
      allPartiesPromise = null;
      throw err;
    });
  }
  return allPartiesPromise;
}

/** Resolve one party's identity metadata. Returns `null` for any
 *  party_id absent from parties.csv (including malformed input) -
 *  callers branch on truthiness. Cache-hits share the bulk Map; cold
 *  calls trigger the bulk fetch once. */
export async function loadPartyMeta(
  party_id: string | null | undefined,
): Promise<PartyMeta | null> {
  if (!party_id) return null;
  const map = await loadAllPartiesMeta();
  return map.get(party_id) ?? null;
}

/** Test-only cache reset. NOT exported from index.ts; consumed by the
 *  loader's own vitest only. */
export function __resetForTests(): void {
  allPartiesPromise = null;
}
