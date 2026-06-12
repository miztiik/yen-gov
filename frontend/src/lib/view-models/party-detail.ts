// PR-4 of TODO/20260612-party-rendering-and-party-pages-plan.md.
//
// `loadPartyDetail(party_id)` assembles the per-party detail page
// view-model (header + KPI strip + LS/VS history + strongholds +
// metadata) by reading the canonical per-state election-results
// long-format CSVs at `datasets/data/datapoints/electoral/*.csv` plus
// the parties.csv metadata via the PR-1 `loadPartyMeta` accessor.
//
// Data shape (csv-column-contract §3.3 + columns.json "datasets/data/
// datapoints/electoral/*.csv"):
//   - entity_id pattern for party-aggregate rows:
//       `IN-<state>-<event>-PARTY-<short>`  (short = party_id tail)
//     e.g. `IN-S22-AcGenApr2021-PARTY-DMK` for the DMK row scoped to
//     Tamil Nadu's 2021 AE.
//   - per-cycle party indicators (one row per indicator per event):
//       `party-seats-won` (numeric)
//       `party-vote-share-pct` (numeric)
//       `party-contested-acs` (numeric)
//   - per-constituency winner rows:
//       `ac-winner-party-id` (value_text carries `parties.IN.<X>`)
//       `pc-winner-party-id` (same)
//   - period_label encodes the body:
//       `AcGen<Mon><Year>` / `AcBye<Mon><Year>` -> Vidhan Sabha (assembly)
//       `LsGen<Mon><Year>` / `LsBye<Mon><Year>` -> Lok Sabha (parliament)
//
// Multi-file glob: the loader registers EVERY per-state file as a single
// DuckDB view via the glob `<base>/data/datapoints/electoral/*.csv`. Cold
// load fetches all 36 files once via DuckDB-WASM's HTTP-Range reader; the
// underlying typed `read_csv(<glob>, columns={...})` reads them
// row-shape-identical (the columns.json file_class spec is glob-keyed).
//
// The loader returns `null` when `loadPartyMeta(party_id)` misses (the
// party_id is absent from parties.csv) so the page surface can render
// the "Party not found" empty state instead of crashing.

import { query, registerCsvFile } from "../duckdb";
import { csvColumnsClause } from "../canonical/csv-columns";
import { DATA_BASE } from "../paths";
import { loadPartyMeta, type PartyMeta } from "./parties";

/** Repo-relative path the columns.json contract looks up. We pass the
 *  glob form directly because `candidateFileClassKeys` short-circuits
 *  to the input string when it already matches the `<dir>/*<ext>`
 *  filename-glob shape. */
const ELECTORAL_GLOB_REL =
  "datasets/data/datapoints/electoral/*.csv";

/** Runtime URL glob; DuckDB-WASM's `read_csv` expands the `*.csv`
 *  pattern against the registered file cache. */
const ELECTORAL_GLOB_URL = `${DATA_BASE}/data/datapoints/electoral/*.csv`;

/** Canonical electoral.csv path (constituency-entity names + eci_no). */
const ELECTORAL_ENTITIES_REL = "datasets/data/entities/electoral.csv";
const ELECTORAL_ENTITIES_URL = `${DATA_BASE}/data/entities/electoral.csv`;

/** Static list of 36 state slugs whose `<slug>_election_results.csv`
 *  files comprise the long-format electoral corpus. Used to register
 *  each file individually with DuckDB-WASM's HTTP-Range cache before
 *  the glob `read_csv` fans them in. The list is hand-maintained:
 *  every state present in `datasets/data/datapoints/electoral/`
 *  appears here exactly once. New states added to the corpus need a
 *  one-line append here. */
const STATE_SLUGS: readonly string[] = [
  "andaman-and-nicobar",
  "andhra-pradesh",
  "arunachal-pradesh",
  "assam",
  "bihar",
  "chandigarh",
  "chhattisgarh",
  "dadra-and-nagar-haveli-and-daman-and-diu",
  "delhi",
  "goa",
  "gujarat",
  "haryana",
  "himachal-pradesh",
  "jammu-and-kashmir",
  "jharkhand",
  "karnataka",
  "kerala",
  "ladakh",
  "lakshadweep",
  "madhya-pradesh",
  "maharashtra",
  "manipur",
  "meghalaya",
  "mizoram",
  "nagaland",
  "odisha",
  "puducherry",
  "punjab",
  "rajasthan",
  "sikkim",
  "tamil-nadu",
  "telangana",
  "tripura",
  "uttar-pradesh",
  "uttarakhand",
  "west-bengal",
];

/** One contested election cycle for a party in one body. */
export interface PartyHistoryPoint {
  /** 4-digit polling year. */
  year: number;
  /** Canonical event id (e.g. `AcGenApr2021`, `LsGenMay2024`). */
  period_label: string;
  /** Number of seats won; 0 when the party contested but won none. */
  seats: number;
  /** Vote-share percentage (0..100); null when the cycle has no
   *  `party-vote-share-pct` row (rare; defensive). */
  vote_share_pct: number | null;
  /** Number of constituencies the party fielded a candidate in;
   *  null when the cycle has no `party-contested-acs` row. */
  contested: number | null;
}

/** One stronghold constituency for a party, scoped to one body. */
export interface PartyStronghold {
  /** Constituency entity_id (e.g. `IN-AC-2008-S22-167`). */
  entity_id: string;
  /** Citizen-readable constituency name from electoral.csv. Empty
   *  string when the JOIN misses (defensive). */
  constituency_name: string;
  /** LGD state slug derived from the entity_id; used for the linkout
   *  in future PRs. v1 ships text-only per the brief. */
  state: string;
  /** Total wins by this party in this constituency (across all
   *  events covered by the canonical store). */
  wins: number;
  /** Total elections held in this constituency (i.e. cycles where
   *  ANY winner_party_id row exists for this entity_id), regardless
   *  of whether this party contested. */
  contested: number;
  /** Per-event outcome chronologically (oldest first). `"W"` when
   *  this party won that event, `"L"` otherwise (loss OR no-contest). */
  results: ("W" | "L")[];
}

/** Aggregate KPI totals for the header strip. */
export interface PartyTotals {
  /** Sum of party-seats-won across every Lok Sabha cycle. */
  ls_seats: number;
  /** Sum of party-seats-won across every Vidhan Sabha cycle. */
  vs_seats: number;
  /** Number of cycles (LS + VS) where this party contested >0 or
   *  won >0. */
  elections_contested: number;
  /** Earliest polling year on file across ALL contested cycles
   *  (LS + VS). 0 when no cycles. */
  first_year: number;
  /** Latest polling year on file. 0 when no cycles. */
  last_year: number;
  /** Peak Lok Sabha seats won in any single cycle. 0 when no LS. */
  peak_ls_seats: number;
  /** Year of the peak LS cycle. 0 when no LS. */
  peak_ls_year: number;
  /** Peak Vidhan Sabha seats won in any single cycle. 0 when no VS. */
  peak_vs_seats: number;
  /** Year of the peak VS cycle. 0 when no VS. */
  peak_vs_year: number;
}

/** Per-party detail page view-model. */
export interface PartyDetailViewModel {
  metadata: PartyMeta;
  /** Lok Sabha history (chronological ascending). Empty for parties
   *  with no parliamentary contests. */
  ls_history: PartyHistoryPoint[];
  /** Vidhan Sabha history (chronological ascending). Empty for
   *  parties that only contest parliament (rare). */
  vs_history: PartyHistoryPoint[];
  /** Top-10 LS strongholds by wins descending. Empty when no LS
   *  presence. */
  ls_strongholds: PartyStronghold[];
  /** Top-10 VS strongholds by wins descending. Empty when no VS
   *  presence. */
  vs_strongholds: PartyStronghold[];
  /** Aggregate KPI totals. */
  totals: PartyTotals;
}

/** Raw history-row shape from DuckDB. */
interface RawHistoryRow {
  year: number | bigint | null;
  period_label: string | null;
  indicator_id: string | null;
  value_numeric: number | null;
}

/** Raw stronghold-row shape from DuckDB. */
interface RawStrongholdRow {
  entity_id: string | null;
  period_label: string | null;
  winner_party_id: string | null;
}

/** Raw electoral-entity row (for constituency display names). */
interface RawElectoralRow {
  entity_id: string | null;
  name: string | null;
  state: string | null;
}

function intOrNull(value: number | bigint | null | undefined): number | null {
  if (value == null) return null;
  if (typeof value === "bigint") return Number(value);
  return Number.isFinite(value) ? Math.trunc(value) : null;
}

function numOrNull(value: number | null | undefined): number | null {
  if (value == null) return null;
  return Number.isFinite(value) ? Number(value) : null;
}

/** Pure: classify a period_label into the body it belongs to. */
export function bodyForPeriodLabel(
  period_label: string,
): "ls" | "vs" | null {
  if (period_label.startsWith("Ls")) return "ls";
  if (period_label.startsWith("Ac")) return "vs";
  return null;
}

/** Pure: extract the SHORT (party_id tail) from a `parties.IN.<X>` id.
 *  The on-disk `entity_id` pattern uses the SHORT verbatim
 *  (e.g. `IN-S22-AcGenApr2021-PARTY-DMK` for `parties.IN.DMK`). */
export function partyIdTail(party_id: string): string {
  const dot = party_id.lastIndexOf(".");
  return dot >= 0 ? party_id.slice(dot + 1) : party_id;
}

/** Recognised history indicator ids; rows carrying anything else
 *  are silently ignored at the fold boundary. */
const HISTORY_INDICATORS = new Set<string>([
  "party-seats-won",
  "party-vote-share-pct",
  "party-contested-acs",
]);

/** Pure: split a flat list of history rows into one
 *  `PartyHistoryPoint` per `period_label`. Rows arrive 3-per-cycle
 *  (one for seats, one for vote share, one for contested); we fold
 *  by period_label. Output is sorted chronologically by year then
 *  period_label as a tie-breaker (multiple bye-elections in one
 *  year keep a deterministic order). Rows with no period_label,
 *  no year, or an unrecognised indicator_id are silently dropped
 *  before they can introduce a phantom event into the fold. */
export function foldHistoryRows(
  rows: RawHistoryRow[],
): PartyHistoryPoint[] {
  const byEvent = new Map<string, PartyHistoryPoint>();
  for (const r of rows) {
    if (!r.period_label || !r.indicator_id) continue;
    if (!HISTORY_INDICATORS.has(r.indicator_id)) continue;
    const year = intOrNull(r.year);
    if (year == null) continue;
    const value = numOrNull(r.value_numeric);
    const existing = byEvent.get(r.period_label) ?? {
      year,
      period_label: r.period_label,
      seats: 0,
      vote_share_pct: null,
      contested: null,
    };
    switch (r.indicator_id) {
      case "party-seats-won":
        existing.seats = value ?? 0;
        break;
      case "party-vote-share-pct":
        existing.vote_share_pct = value;
        break;
      case "party-contested-acs":
        existing.contested = value == null ? null : Math.trunc(value);
        break;
    }
    byEvent.set(r.period_label, existing);
  }
  const out = [...byEvent.values()];
  out.sort((a, b) => {
    if (a.year !== b.year) return a.year - b.year;
    return a.period_label.localeCompare(b.period_label);
  });
  return out;
}

/** Month-name lookup so a sort key can put `AcGenApr2021` after
 *  `AcGenJan1989` chronologically (alphabetical sort would yield
 *  Apr < Feb < Jan, which is wrong). */
const MONTH_INDEX: Record<string, number> = {
  Jan: 1,
  Feb: 2,
  Mar: 3,
  Apr: 4,
  May: 5,
  Jun: 6,
  Jul: 7,
  Aug: 8,
  Sep: 9,
  Oct: 10,
  Nov: 11,
  Dec: 12,
};

/** Pure: derive a chronological sort key from an ECI event id
 *  (e.g. `AcGenApr2021` -> `2021-04`). Falls back to the raw label
 *  when no `<Mon><Year>` suffix matches so the sort stays
 *  deterministic. Exported for test coverage. */
export function chronologicalSortKey(period_label: string): string {
  const m = period_label.match(/([A-Z][a-z]{2})(\d{4})$/);
  if (!m) return `9999-99-${period_label}`;
  const month = MONTH_INDEX[m[1]!] ?? 99;
  return `${m[2]}-${String(month).padStart(2, "0")}`;
}

/** Pure: fold stronghold rows into per-constituency aggregates.
 *  `target_party_id` is the party we're scoring against. For each
 *  (entity_id), count `wins` (rows where this party is the winner) +
 *  `contested` (total events with ANY winner). The `results[]`
 *  sparkline is per-event chronologically; per-event we emit "W"
 *  if this party won OR "L" otherwise. */
export function foldStrongholdRows(
  rows: RawStrongholdRow[],
  target_party_id: string,
  entity_name_lookup: Map<string, string>,
  entity_state_lookup: Map<string, string>,
): PartyStronghold[] {
  // First pass: group all rows by entity_id, sort by chronological
  // (year, month) so the sparkline reads chronologically.
  const byEntity = new Map<
    string,
    { period_label: string; winner_party_id: string }[]
  >();
  for (const r of rows) {
    if (!r.entity_id || !r.period_label) continue;
    const winner = (r.winner_party_id ?? "").trim();
    const list = byEntity.get(r.entity_id) ?? [];
    list.push({ period_label: r.period_label, winner_party_id: winner });
    byEntity.set(r.entity_id, list);
  }
  const out: PartyStronghold[] = [];
  for (const [entity_id, events] of byEntity) {
    events.sort((a, b) =>
      chronologicalSortKey(a.period_label).localeCompare(
        chronologicalSortKey(b.period_label),
      ),
    );
    let wins = 0;
    const results: ("W" | "L")[] = [];
    for (const e of events) {
      const isWin = e.winner_party_id === target_party_id;
      if (isWin) wins += 1;
      results.push(isWin ? "W" : "L");
    }
    // Only surface strongholds where the party has at least one win;
    // a 0-win row is not a stronghold and would noise the top-10.
    if (wins === 0) continue;
    out.push({
      entity_id,
      constituency_name: entity_name_lookup.get(entity_id) ?? "",
      state: entity_state_lookup.get(entity_id) ?? "",
      wins,
      contested: events.length,
      results,
    });
  }
  // Top-10 by wins desc, then by win-rate desc (so a 5-of-5 sweeper
  // outranks a 5-of-10 streaky party), then by entity_id for
  // determinism.
  out.sort((a, b) => {
    if (a.wins !== b.wins) return b.wins - a.wins;
    const winRateDiff = b.wins / b.contested - a.wins / a.contested;
    if (Math.abs(winRateDiff) > 1e-9) return winRateDiff;
    return a.entity_id.localeCompare(b.entity_id);
  });
  return out.slice(0, 10);
}

/** Pure: compute the aggregate KPI totals from the LS + VS history. */
export function computeTotals(
  ls_history: PartyHistoryPoint[],
  vs_history: PartyHistoryPoint[],
): PartyTotals {
  let ls_seats = 0;
  let peak_ls_seats = 0;
  let peak_ls_year = 0;
  for (const p of ls_history) {
    ls_seats += p.seats;
    if (p.seats > peak_ls_seats) {
      peak_ls_seats = p.seats;
      peak_ls_year = p.year;
    }
  }
  let vs_seats = 0;
  let peak_vs_seats = 0;
  let peak_vs_year = 0;
  for (const p of vs_history) {
    vs_seats += p.seats;
    if (p.seats > peak_vs_seats) {
      peak_vs_seats = p.seats;
      peak_vs_year = p.year;
    }
  }
  const all = [...ls_history, ...vs_history];
  const contested_cycles = all.filter(
    (p) => p.seats > 0 || (p.contested ?? 0) > 0,
  );
  const elections_contested = contested_cycles.length;
  let first_year = 0;
  let last_year = 0;
  if (contested_cycles.length > 0) {
    first_year = contested_cycles.reduce(
      (acc, p) => Math.min(acc, p.year),
      contested_cycles[0]!.year,
    );
    last_year = contested_cycles.reduce(
      (acc, p) => Math.max(acc, p.year),
      contested_cycles[0]!.year,
    );
  }
  return {
    ls_seats,
    vs_seats,
    elections_contested,
    first_year,
    last_year,
    peak_ls_seats,
    peak_ls_year,
    peak_vs_seats,
    peak_vs_year,
  };
}

async function fetchPartyDetail(
  party_id: string,
  metadata: PartyMeta,
): Promise<PartyDetailViewModel> {
  // Register every per-state file so the DuckDB-WASM cache resolves
  // them BEFORE the glob `read_csv` runs (the glob expansion looks
  // up registered URLs; un-registered files 404). The shared HTTP
  // cache makes repeat calls cheap. Electoral entities CSV is
  // registered alongside for the constituency-name JOIN.
  await Promise.all([
    ...STATE_SLUGS.map((slug) =>
      registerCsvFile(
        `${DATA_BASE}/data/datapoints/electoral/${slug}_election_results.csv`,
      ),
    ),
    registerCsvFile(ELECTORAL_ENTITIES_URL),
  ]);

  const [electoralClause, electoralEntitiesClause] = await Promise.all([
    csvColumnsClause(ELECTORAL_GLOB_REL),
    csvColumnsClause(ELECTORAL_ENTITIES_REL),
  ]);

  const short = partyIdTail(party_id);
  // Escape the party_id tail for SQL string interpolation; entity_id
  // pattern uses `-PARTY-<short>` as the suffix.
  const safeShort = short.replace(/'/g, "''");
  const safePartyId = party_id.replace(/'/g, "''");

  // VS history query: pull the 3 per-cycle indicators for the party-
  // aggregate entity_id pattern (one row per party per AC event). Note
  // ONLY Vidhan Sabha events emit party-aggregate rows in the canonical
  // store today; the LS branch is synthesised below from per-PC winner
  // rows because the upstream ingest does not yet ship LS party-aggregate.
  const vsHistorySql = `
    SELECT
      year,
      period_label,
      indicator_id,
      value_numeric
    FROM read_csv('${ELECTORAL_GLOB_URL}', ${electoralClause})
    WHERE entity_id LIKE 'IN-%-PARTY-${safeShort}'
      AND indicator_id IN (
        'party-seats-won',
        'party-vote-share-pct',
        'party-contested-acs'
      )
      AND (period_label LIKE 'Ac%')
  `;
  const vsHistoryRows = await query<RawHistoryRow>(vsHistorySql);

  // LS history synthesis: count pc-winner-party-id rows per LS event
  // where value_text matches this party_id. The per-state CSVs only
  // carry LS data as per-PC winner rows (no party-aggregate row); we
  // group + count here to derive seats_won. Vote share + contested
  // remain null at v1 because they would require per-candidacy
  // aggregation - documented as a follow-up backfill in the page's
  // coverage caption.
  const lsHistorySql = `
    SELECT
      MIN(year)             AS year,
      period_label          AS period_label,
      COUNT(*)              AS seats_count
    FROM read_csv('${ELECTORAL_GLOB_URL}', ${electoralClause})
    WHERE indicator_id = 'pc-winner-party-id'
      AND value_text = '${safePartyId}'
      AND period_label LIKE 'Ls%'
    GROUP BY period_label
  `;
  const lsCountRows = await query<{
    year: number | bigint | null;
    period_label: string | null;
    seats_count: number | bigint | null;
  }>(lsHistorySql);

  // Stronghold query: pull every ac/pc winner_party_id row that
  // matches the target party_id. We need the FULL winner history
  // per entity_id (not just THIS party's wins) so the `contested`
  // denominator is accurate; the SQL pulls all winners and the
  // pure folder filters per-party.
  const strongholdSql = `
    SELECT
      entity_id,
      period_label,
      value_text AS winner_party_id
    FROM read_csv('${ELECTORAL_GLOB_URL}', ${electoralClause})
    WHERE indicator_id IN ('ac-winner-party-id', 'pc-winner-party-id')
      AND entity_id IN (
        SELECT DISTINCT entity_id
        FROM read_csv('${ELECTORAL_GLOB_URL}', ${electoralClause})
        WHERE indicator_id IN ('ac-winner-party-id', 'pc-winner-party-id')
          AND value_text = '${safePartyId}'
      )
  `;
  const strongholdRows = await query<RawStrongholdRow>(strongholdSql);

  // Electoral-entity JOIN for display names. Pull only the entity_ids
  // that appear in the stronghold rows to keep the round-trip small.
  const entityIds = new Set<string>();
  for (const r of strongholdRows) {
    if (r.entity_id) entityIds.add(r.entity_id);
  }
  let electoralRows: RawElectoralRow[] = [];
  if (entityIds.size > 0) {
    const idList = [...entityIds]
      .map((id) => `'${id.replace(/'/g, "''")}'`)
      .join(", ");
    const entitySql = `
      SELECT
        entity_id,
        name,
        state
      FROM read_csv('${ELECTORAL_ENTITIES_URL}', ${electoralEntitiesClause})
      WHERE entity_id IN (${idList})
    `;
    electoralRows = await query<RawElectoralRow>(entitySql);
  }
  const nameLookup = new Map<string, string>();
  const stateLookup = new Map<string, string>();
  for (const r of electoralRows) {
    if (r.entity_id) {
      nameLookup.set(r.entity_id, r.name ?? "");
      stateLookup.set(r.entity_id, r.state ?? "");
    }
  }

  // Split VS history rows from the party-aggregate query (already
  // filtered to Ac% in SQL). LS history is the per-event count from
  // the synthesised query.
  const vs_history = foldHistoryRows(vsHistoryRows);
  const ls_history: PartyHistoryPoint[] = lsCountRows
    .filter((r) => r.period_label != null)
    .map((r) => ({
      year: intOrNull(r.year) ?? 0,
      period_label: r.period_label!,
      seats: intOrNull(r.seats_count) ?? 0,
      vote_share_pct: null,
      contested: null,
    }))
    .sort((a, b) => {
      if (a.year !== b.year) return a.year - b.year;
      return a.period_label.localeCompare(b.period_label);
    });

  // Split stronghold rows into LS + VS via period_label prefix
  // (the ac vs pc indicator already disambiguates body, but the
  // period_label is what makes the sparkline chronological within
  // a body).
  const lsStrongRaw: RawStrongholdRow[] = [];
  const vsStrongRaw: RawStrongholdRow[] = [];
  for (const r of strongholdRows) {
    if (!r.period_label) continue;
    const body = bodyForPeriodLabel(r.period_label);
    if (body === "ls") lsStrongRaw.push(r);
    else if (body === "vs") vsStrongRaw.push(r);
  }
  const ls_strongholds = foldStrongholdRows(
    lsStrongRaw,
    party_id,
    nameLookup,
    stateLookup,
  );
  const vs_strongholds = foldStrongholdRows(
    vsStrongRaw,
    party_id,
    nameLookup,
    stateLookup,
  );

  const totals = computeTotals(ls_history, vs_history);

  return {
    metadata,
    ls_history,
    vs_history,
    ls_strongholds,
    vs_strongholds,
    totals,
  };
}

/** Module-level Promise cache, keyed by party_id. Repeated calls
 *  for the same party return the SAME Promise so the browser pays
 *  the corpus-fetch + DuckDB query exactly once per tab. */
const detailCache = new Map<string, Promise<PartyDetailViewModel | null>>();

/**
 * Load the per-party detail view-model. Returns `null` when the
 * party_id is absent from parties.csv (the page renders the
 * "Party not found" empty state on null). Returns a fully-populated
 * view-model (with possibly-empty arrays for parties with no data
 * in one body) otherwise.
 *
 * Per the canonical-store loader pattern: the cache survives the
 * lifetime of the browser tab; only `__resetForTests` clears it.
 * A fetch failure clears that party's cache entry so a retry
 * re-issues the underlying queries.
 */
export function loadPartyDetail(
  party_id: string | null | undefined,
): Promise<PartyDetailViewModel | null> {
  if (!party_id) return Promise.resolve(null);
  const cached = detailCache.get(party_id);
  if (cached) return cached;
  const promise = (async (): Promise<PartyDetailViewModel | null> => {
    const metadata = await loadPartyMeta(party_id);
    if (!metadata) return null;
    return fetchPartyDetail(party_id, metadata);
  })().catch((err) => {
    detailCache.delete(party_id);
    throw err;
  });
  detailCache.set(party_id, promise);
  return promise;
}

/** Test-only cache reset. NOT exported from index.ts. */
export function __resetForTests(): void {
  detailCache.clear();
}
