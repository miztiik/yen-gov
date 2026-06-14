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
import { partyIdToSlug } from "../slug";

/** Repo-relative path used by `csvColumnsClause` to look up the typed
 *  column spec from datasets/data/_schema/columns.json. */
const PARTIES_CSV_REL = "datasets/data/entities/parties.csv";

/** Runtime URL the browser fetches via DuckDB-WASM HTTP-Range reads. */
const PARTIES_CSV_URL = `${DATA_BASE}/data/entities/parties.csv`;

/** PR-11 (TODO/20260613-party-deferred-followups-plan.md section 13):
 *  parties_leadership.csv is the term-shape party-leadership register
 *  shipped by PR-7+PR-9 (Wikidata SPARQL snapshot). The tooltip + the
 *  per-party header read the CURRENT row per party (valid_to empty);
 *  historic rows stay in the corpus for time-travel analysis but are
 *  not surfaced today. */
const LEADERSHIP_CSV_REL = "datasets/data/entities/parties_leadership.csv";
const LEADERSHIP_CSV_URL = `${DATA_BASE}/data/entities/parties_leadership.csv`;

/** Citizen-renderable shape for one party's current leader, projected
 *  from the term-shape parties_leadership.csv row whose `valid_to` is
 *  empty (= currently serving per the writer contract). */
export interface PartyLeader {
  /** Human-readable name as the publisher cites them, e.g.
   *  "Mallikarjun Kharge". */
  name: string;
  /** Free-text role label per the parties_leadership.csv contract
   *  (e.g. "President", "General Secretary", "National Convenor").
   *  Wikidata position labels are open-ended so the column carries
   *  no enum closure. */
  role: string;
  /** Wikidata Q-id when the publisher carries one (e.g. "Q6744197").
   *  Null when the row was hand-curated without a Wikidata entry. */
  person_wikidata_qid: string | null;
  /** Term start in raw `YYYY-MM-DD` shape per the CSV. Citizen-facing
   *  surfaces format this via `formatLeaderSince`; the raw string
   *  stays on the type so consumers can render their own format
   *  (Path-B decision per PR-11 brief: "since" date is per-leader
   *  data the citizen cares about; no synthetic "as of <vintage>"
   *  framing is plumbed). */
  since: string;
}

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
  /** PR-6: Citizen-readable alternate party names from
   *  `parties.csv::aliases` (pipe-delimited list exploded at the loader
   *  boundary). Empty array when upstream blank. The per-party page
   *  About card renders these as a comma-joined inline string when
   *  non-empty; the tooltip does NOT render aliases (Jony A2 - tooltip
   *  body is intentionally short). */
  aliases: string[];
  /** PR-6: Opaque `parties.IN.<X>` ids for predecessor parties from
   *  `parties.csv::predecessor_party_ids` (pipe-delimited list).
   *  Empty array when upstream blank. The per-party page About card
   *  renders these as a comma-joined list of links via `link.party()`
   *  (which returns null for UNK, in which case the consumer renders
   *  plain text). */
  predecessor_party_ids: string[];
  /** PR-6: Opaque `parties.IN.<X>` ids for successor parties from
   *  `parties.csv::successor_party_ids` (pipe-delimited list).
   *  Empty array when upstream blank. Same rendering rule as
   *  `predecessor_party_ids`. */
  successor_party_ids: string[];
  /** True for the 3 sentinel rows (`parties.IN.UNK`, `parties.IN.IND`,
   *  `parties.IN.NOTA`). The tooltip uses this to suppress the wiki
   *  link + founded line for sentinels even when DuckDB returns a
   *  truthy-looking founded_year for NOTA (2013 was the PUCL v Union
   *  of India ruling, not a party founding). */
  is_sentinel: boolean;
  /** PR-11: current party leader (the parties_leadership.csv row with
   *  empty `valid_to`) when one exists, else null. Null is the common
   *  case today - the first Wikidata SPARQL snapshot bound only ~9 of
   *  75 known party Q-ids (most Indian-party leadership graph is
   *  genuinely sparse on Wikidata). Set by `loadPartyMeta`; the bulk
   *  `loadAllPartiesMeta` Map carries `null` as a placeholder so the
   *  /parties index page does not pay the leader-load cost. */
  leader: PartyLeader | null;
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
  // PR-6: 3 new pipe-delimited list columns plumbed through the
  // PartyMeta typed projection. Declared optional so the existing
  // fixture rows in parties.test.ts that omit them stay valid; the
  // splitPipe(undefined) projection collapses missing values to [].
  aliases?: string | null;
  predecessor_party_ids?: string | null;
  successor_party_ids?: string | null;
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
 *  without going through DuckDB. The `leader` field is a placeholder
 *  here (`null`); `loadPartyMeta` merges in the resolved leader via
 *  a parallel `loadCurrentLeaders` fetch. */
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
    aliases: splitPipe(row.aliases),
    predecessor_party_ids: splitPipe(row.predecessor_party_ids),
    successor_party_ids: splitPipe(row.successor_party_ids),
    is_sentinel: row.is_sentinel === true,
    leader: null,
  };
}

// --- PR-11: parties_leadership.csv loader --------------------------------

/** Raw DuckDB row shape mirroring parties_leadership.csv columns.json
 *  typed projection. Every column is `string | null` because the CSV
 *  carries 7 string columns and DuckDB-WASM round-trips them as such. */
interface RawLeadershipRow {
  party_id: string | null;
  role: string | null;
  person_name: string | null;
  person_wikidata_qid: string | null;
  valid_from: string | null;
  valid_to: string | null;
  source_id: string | null;
}

/** Project a raw leadership row into a `PartyLeader` IFF the row is
 *  CURRENT (`valid_to` empty / null per writer contract). Historic
 *  rows return null; rows missing required fields (name / role /
 *  valid_from) return null defensively. Pure; exported for vitest. */
export function toCurrentLeader(row: RawLeadershipRow): PartyLeader | null {
  // Historic rows (valid_to populated) MUST NOT surface as current.
  if (trimmedOrNull(row.valid_to) !== null) return null;
  const name = trimmedOrNull(row.person_name);
  const role = trimmedOrNull(row.role);
  const since = trimmedOrNull(row.valid_from);
  if (!name || !role || !since) return null;
  return {
    name,
    role,
    person_wikidata_qid: trimmedOrNull(row.person_wikidata_qid),
    since,
  };
}

/** Module-level promise cache for the current-leaders Map; parallel
 *  to `allPartiesPromise`. Reset by `__resetForTests`. */
let currentLeadersPromise: Promise<Map<string, PartyLeader>> | null = null;

async function fetchCurrentLeaders(): Promise<Map<string, PartyLeader>> {
  await registerCsvFile(LEADERSHIP_CSV_URL);
  const columnsClause = await csvColumnsClause(LEADERSHIP_CSV_REL);
  // SQL-level current-row filter so the JS path only sees rows the
  // projection is happy to keep. DuckDB-WASM treats empty CSV cells
  // as NULL with the typed columns= projection; the `OR = ''` clause
  // is belt-and-braces in case a future writer emits literal empty.
  const rows = await query<RawLeadershipRow>(`
    SELECT
      party_id,
      role,
      person_name,
      person_wikidata_qid,
      valid_from,
      valid_to,
      source_id
    FROM read_csv('${LEADERSHIP_CSV_URL}', ${columnsClause}, header=true)
    WHERE valid_to IS NULL OR valid_to = ''
  `);
  const map = new Map<string, PartyLeader>();
  for (const raw of rows) {
    const party_id = trimmedOrNull(raw.party_id);
    const leader = toCurrentLeader(raw);
    if (party_id && leader) {
      // PK on the CSV writer is `(party_id, valid_from)` so two
      // current-rows for one party_id are impossible by contract.
      // Defensive first-write-wins keeps the loader pure.
      if (!map.has(party_id)) map.set(party_id, leader);
    }
  }
  return map;
}

/** Bulk fetch the current-leader row per party from
 *  parties_leadership.csv. Cached for the lifetime of the browser
 *  tab; returns the SAME Promise on every call. */
export function loadCurrentLeaders(): Promise<Map<string, PartyLeader>> {
  if (!currentLeadersPromise) {
    currentLeadersPromise = fetchCurrentLeaders().catch((err) => {
      currentLeadersPromise = null;
      throw err;
    });
  }
  return currentLeadersPromise;
}

/** Per-key accessor for the current leader of one party. Returns
 *  `null` when no current row exists (the common case today - most
 *  parties have no Wikidata leadership binding). */
export async function loadPartyLeader(
  party_id: string | null | undefined,
): Promise<PartyLeader | null> {
  if (!party_id) return null;
  const map = await loadCurrentLeaders();
  return map.get(party_id) ?? null;
}

/** Citizen-friendly format for a `YYYY-MM-DD` term-start string from
 *  the leadership CSV. Pure; exported so the tooltip + per-party
 *  header + the vitest pin all agree on the rendered form. Falls
 *  back to the raw input string when the shape is malformed (no
 *  fabrication, no exception). */
const MONTH_ABBR = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;
export function formatLeaderSince(yyyymmdd: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(yyyymmdd);
  if (!m) return yyyymmdd;
  const year = m[1]!;
  const month = parseInt(m[2]!, 10);
  const day = parseInt(m[3]!, 10);
  if (month < 1 || month > 12 || day < 1 || day > 31) return yyyymmdd;
  return `${day} ${MONTH_ABBR[month - 1]} ${year}`;
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
      aliases,
      predecessor_party_ids,
      successor_party_ids,
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
 *  calls trigger the bulk fetch once.
 *
 *  PR-11: also merges in the current leader row (from
 *  parties_leadership.csv) on the returned object via a parallel
 *  `loadCurrentLeaders` fetch. The bulk-Map values keep
 *  `leader: null` so /parties index consumers do not pay the
 *  leader-load cost; only per-key callers (PartyTooltip,
 *  party-detail) trigger the second fetch. */
export async function loadPartyMeta(
  party_id: string | null | undefined,
): Promise<PartyMeta | null> {
  if (!party_id) return null;
  const [partiesMap, leadersMap] = await Promise.all([
    loadAllPartiesMeta(),
    loadCurrentLeaders(),
  ]);
  const meta = partiesMap.get(party_id);
  if (!meta) return null;
  return { ...meta, leader: leadersMap.get(party_id) ?? null };
}

/** Test-only cache reset. NOT exported from index.ts; consumed by the
 *  loader's own vitest only. */
export function __resetForTests(): void {
  allPartiesPromise = null;
  allPartySummariesPromise = null;
  currentLeadersPromise = null;
}

// --- PR-3: parties index summary ------------------------------------------

/**
 * Citizen-facing summary row for ONE party as consumed by the `/parties`
 * index page (PR-3 of TODO/20260612-party-rendering-and-party-pages-plan.md).
 *
 * Shape differs from `PartyMeta` in three ways:
 *   1. `slug` carries the URL slug derived via `partyIdToSlug` (the
 *      `null`-slug UNK row is filtered out upstream so this is always
 *      non-null on consumers; the type is `string` rather than
 *      `string | null`).
 *   2. `home_state_codes` + `aliases` stay as the RAW pipe-delimited
 *      strings the CSV ships - the index page filters substring-style
 *      across them (the loader does not pre-explode because the chip
 *      filter is a string contains-check, not a set membership check).
 *   3. `recognition_scope` collapses null to `""` so the chip filter
 *      can default-include defunct + sentinel rows under "All" without
 *      a null-guard branch.
 *
 * `full` collapses null to the empty string for the same reason -
 * the index page renders it inline next to the pill and a null check
 * everywhere would noise up the template.
 */
export interface PartySummary {
  /** Opaque `parties.IN.<X>` taxonomy id. */
  party_id: string;
  /** URL slug per `partyIdToSlug` - never null on a consumed row
   *  (UNK is filtered out at the loader boundary). */
  slug: string;
  /** Display short (e.g. "BJP"). Falls back to `party_id` when
   *  upstream blank. */
  short: string;
  /** Long name as commonly cited. Empty string when upstream blank. */
  full: string;
  /** ECI recognition class. Enum: `national`, `state`,
   *  `unrecognised_registered`, `defunct`, `sentinel`. Empty string
   *  when upstream blank. */
  recognition_scope: string;
  /** Raw pipe-delimited home-state-codes string (e.g. `"IN-BR|IN-HR"`).
   *  Empty string when upstream blank. Index page filters substring-
   *  style; per-chip search does NOT need the array form. */
  home_state_codes: string;
  /** Year the party was founded. Null when not known. */
  founded_year: number | null;
  /** Repo-relative symbol asset path. Null when no symbol on file. */
  symbol_asset: string | null;
  /** OkLCh hex hint. Null when blank. */
  brand_colour: string | null;
  /** Raw pipe-delimited aliases string (e.g. `"AAAAP|AAAP"`). Empty
   *  string when upstream blank. Index search box does substring
   *  match on the raw string (so a query of `"AAAA"` matches `AAAAP`). */
  aliases: string;
  /** True for the 3 sentinel rows (IND / NOTA; UNK is filtered out). */
  is_sentinel: boolean;
}

/** Raw DuckDB row for the summary projection - same `read_csv` as the
 *  PartyMeta path, plus the `aliases` column. */
interface RawPartiesSummaryRow {
  party_id: string | null;
  short: string | null;
  full: string | null;
  recognition_scope: string | null;
  home_state_codes: string | null;
  founded_year: number | bigint | null;
  symbol_asset: string | null;
  brand_colour: string | null;
  aliases: string | null;
  is_sentinel: boolean | null;
}

/** Project a raw row into the typed `PartySummary` shape. Returns null
 *  when the row has no party_id OR when its `partyIdToSlug` is null
 *  (UNK is the only row in parties.csv that hits the latter at v1.1).
 *  Pure; exported for test coverage against synthetic rows. */
export function toPartySummary(
  row: RawPartiesSummaryRow,
): PartySummary | null {
  const party_id = trimmedOrNull(row.party_id);
  if (!party_id) return null;
  const slug = partyIdToSlug(party_id);
  if (slug === null) return null;
  return {
    party_id,
    slug,
    short: trimmedOrNull(row.short) ?? party_id,
    full: trimmedOrNull(row.full) ?? "",
    recognition_scope: trimmedOrNull(row.recognition_scope) ?? "",
    home_state_codes: trimmedOrNull(row.home_state_codes) ?? "",
    founded_year: intOrNull(row.founded_year),
    symbol_asset: trimmedOrNull(row.symbol_asset),
    brand_colour: trimmedOrNull(row.brand_colour),
    aliases: trimmedOrNull(row.aliases) ?? "",
    is_sentinel: row.is_sentinel === true,
  };
}

/** Module-level promise cache for the summary projection - parallel
 *  to `allPartiesPromise` so the tooltip path + the index path keep
 *  their own typed caches. Both share the underlying parties.csv byte
 *  cache via `registerCsvFile` (the second call is a no-op). */
let allPartySummariesPromise: Promise<PartySummary[]> | null = null;

async function fetchAllPartySummaries(): Promise<PartySummary[]> {
  await registerCsvFile(PARTIES_CSV_URL);
  const columnsClause = await csvColumnsClause(PARTIES_CSV_REL);
  // `short` / `full` are DuckDB reserved words; quote per the PartyMeta
  // precedent. Sort by lower(short) in SQL so the consumer doesn't
  // pay a JS sort on 2300+ rows.
  const rows = await query<RawPartiesSummaryRow>(`
    SELECT
      party_id,
      "short"            AS "short",
      "full"             AS "full",
      recognition_scope,
      home_state_codes,
      founded_year,
      symbol_asset,
      brand_colour,
      aliases,
      is_sentinel
    FROM read_csv('${PARTIES_CSV_URL}', ${columnsClause}, header=true)
    ORDER BY lower("short")
  `);
  const out: PartySummary[] = [];
  for (const raw of rows) {
    const s = toPartySummary(raw);
    if (s) out.push(s);
  }
  return out;
}

/**
 * Bulk fetch every consumable party row for the `/parties` index page.
 * Rows are sorted by `short` (case-insensitive) at the SQL boundary;
 * rows with no URL slug (currently only `parties.IN.UNK`) are filtered
 * out at the projection.
 *
 * Cached for the lifetime of the browser tab. Returns the SAME Promise
 * on every call (per the canonical-store loader pattern); callers MAY
 * await it concurrently without triggering multiple network fetches.
 */
export function loadAllParties(): Promise<PartySummary[]> {
  if (!allPartySummariesPromise) {
    allPartySummariesPromise = fetchAllPartySummaries().catch((err) => {
      allPartySummariesPromise = null;
      throw err;
    });
  }
  return allPartySummariesPromise;
}
