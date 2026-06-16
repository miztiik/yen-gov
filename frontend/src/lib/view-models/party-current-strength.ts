// PR-7 of TODO/20260614-party-page-reimagination-plan.md.
//
// `loadPartyCurrentStrength(party_id)` builds the "Where this party
// sits today" strip view-model from `datasets/data/marts/party_pages/
// history.csv` (the same per-(party, body, period_label, state) mart
// that `loadPartyDetail` reads). The strip answers the citizen
// question "how big is this party right now?" with three lines:
//
//   Parliament (Jun 2024): 211 of 543 seats - 36.5% vote share.
//   State Assemblies (latest cycles in 31 of 31 states): 1,776 of 4,035 seats.
//   Last contested: West Bengal State Assembly, May 2026.
//
// Each line is conditional - parties with no Parliament history skip
// line 1; parties with no state assembly history skip line 2. Line 3
// renders whenever at least one of the other two is present.
//
// Sentinel parties (NOTA, UNK) return `null` from this loader - the
// caller suppresses the entire strip for them; the aggregate is
// structurally meaningless. Independent (IND) returns honest
// aggregates per Max M2 (the contracts subsume independents as a
// single row in the canonical store; the strip surfaces the row's
// numbers without scope-narrowing).

import { csvColumnsClause } from "../canonical/csv-columns";
import { query, registerCsvFile } from "../duckdb";
import { DATA_BASE } from "../paths";

/** Party-page mart paths (repo-relative for columns.json lookup +
 *  runtime URL for DuckDB-WASM HTTP reads). Mirrors the constants
 *  in `party-detail.ts` because both view-models read the same mart;
 *  duplicating the literals avoids a cross-import that would make
 *  `party-detail.ts` test setup harder to mock. */
const PARTY_HISTORY_REL = "datasets/data/marts/party_pages/history.csv";
const PARTY_HISTORY_URL = `${DATA_BASE}/data/marts/party_pages/history.csv`;

/** Parliament total seats - constant per the Constitution of India
 *  (Article 81; 543 elected + 2 nominated, citizen-facing denominator
 *  is 543). Hardcoded here because the canonical store does not yet
 *  carry a per-chamber-size lookup for Parliament; M5 of the plan-doc
 *  flags this as fine for v1 (the value is a constitutional invariant,
 *  not a publisher-vintaged datum). */
const LS_TOTAL_SEATS = 543;

/** Month-name lookup so a sort key can put `LsGenJun2024` after
 *  `LsGenMay2024` chronologically (alphabetical sort would yield
 *  Jun < May, which is wrong). Mirrors the same lookup in
 *  `party-detail.ts` for the same reason. */
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

const MONTH_NAMES = [
  "",
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
];

/** Latest Parliament general-election the party contested. Null when no LS history. */
export interface ParliamentLatest {
  /** Polling year (e.g. 2024). */
  year: number;
  /** Canonical event id derived from the period_label
   *  (e.g. `LsGenJun2024` -> `general-2024`). The slug shape mirrors
   *  the `/t/elections/<event_id>` topic URL grammar locked at
   *  [docs/architecture/frontend/url-grammar.md]. */
  event_id: string;
  /** Citizen-facing month label (e.g. `"Jun 2024"`). */
  month_label: string;
  /** Number of seats this party won across all states. */
  seats_won: number;
  /** Total LS chamber size (constitutional invariant: 543). */
  seats_total: number;
  /** Vote-share percentage (0..100) derived as
   *  SUM(party_votes) * 100 / SUM(total_votes) across all states;
   *  null when the mart did not carry party_votes/total_votes for
   *  this cycle (defensive; today's mart always carries both). */
  vote_share_pct: number | null;
  /** Optional ordinal label ("the largest party", "second largest",
   *  ...). v1 ships `null` - the derivation requires a cycle-wide
   *  all-parties JOIN that we defer to a follow-on PR. */
  rank_label: string | null;
}

/** Aggregated across the LATEST state Assembly cycle in each state
 *  with coverage. Null when this party has no assembly history. */
export interface StateAssembliesLatest {
  /** Sum of seats this party won across all state-latest cycles. */
  seats_won: number;
  /** Sum of chamber sizes for those states (= sum of all parties'
   *  seats won, since first-past-the-post fills every chamber seat). */
  seats_total: number;
  /** Number of states contributing to the aggregate (states where
   *  this party has at least one row in the latest cycle, contested
   *  or won). */
  state_count: number;
  /** Single most recent state event the party contested, formatted
   *  for the "Last contested" one-liner
   *  (e.g. `"West Bengal State Assembly, May 2026"`). */
  latest_event_label: string;
  /** Chronological sort key of the latest event (e.g. `"2026-05"`).
   *  Exposed so the caller can compare against `parliament_latest`
   *  for the cross-body "Last contested" line. */
  latest_event_sort_key: string;
}

/** Top-level view-model for the Current Strength strip. */
export interface PartyCurrentStrength {
  parliament_latest: ParliamentLatest | null;
  state_assemblies_latest: StateAssembliesLatest | null;
  /** Citizen-facing "Last contested" one-liner. Picks whichever of
   *  `parliament_latest` or `state_assemblies_latest.latest_event_label`
   *  is chronologically most recent. Null only when both are null. */
  last_contested_label: string | null;
}

/** Total LS chamber size - exported for vitest. */
export const PARLIAMENT_TOTAL_SEATS = LS_TOTAL_SEATS;

/** Raw shape of one row from the parliament-latest SQL query. */
interface RawParliamentRow {
  period_label: string | null;
  year: number | bigint | null;
  party_seats: number | bigint | null;
  party_votes: number | bigint | null;
  total_votes: number | bigint | null;
}

/** Raw shape of one row from the state-assemblies SQL query. */
interface RawStateAssemblyRow {
  state: string | null;
  period_label: string | null;
  year: number | bigint | null;
  party_seats: number | bigint | null;
  chamber_seats: number | bigint | null;
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

/** Pure: derive a chronological sort key from a period_label
 *  (e.g. `LsGenJun2024` -> `2024-06`). Falls back to a deterministic
 *  large key when no `<Mon><Year>` suffix matches so the sort stays
 *  total. Exported for vitest. */
export function chronologicalSortKey(period_label: string): string {
  const m = period_label.match(/([A-Z][a-z]{2})(\d{4})$/);
  if (!m) return `9999-99-${period_label}`;
  const month = MONTH_INDEX[m[1]!] ?? 99;
  return `${m[2]}-${String(month).padStart(2, "0")}`;
}

/** Pure: extract the citizen-facing `"Mon YYYY"` month label from a
 *  period_label (e.g. `LsGenJun2024` -> `"Jun 2024"`). Returns null
 *  when no `<Mon><Year>` suffix matches. Exported for vitest. */
export function parseMonthFromPeriodLabel(
  period_label: string,
): string | null {
  const m = period_label.match(/([A-Z][a-z]{2})(\d{4})$/);
  if (!m) return null;
  return `${m[1]} ${m[2]}`;
}

/** Pure: derive the event_id slug from a Parliament period_label
 *  (e.g. `LsGenJun2024` -> `"general-2024"`). The slug mirrors the
 *  `/t/elections/<event_id>` topic URL grammar so the caller can
 *  cheaply link back. Returns null for non-LS or malformed labels.
 *  Exported for vitest. */
export function lsEventIdFromPeriodLabel(
  period_label: string,
): string | null {
  if (!period_label.startsWith("LsGen")) return null;
  const m = period_label.match(/(\d{4})$/);
  if (!m) return null;
  return `general-${m[1]}`;
}

/** Pure: convert a state slug (e.g. `"tamil-nadu"`,
 *  `"jammu-and-kashmir"`) to a Title Case display name
 *  (`"Tamil Nadu"`, `"Jammu And Kashmir"`). v1 simplification:
 *  word-by-word capitalisation. The lossy `"And"` (vs `"and"`)
 *  is acceptable for the brief "Last contested" line because:
 *    1. The full citizen-facing display name lives in
 *       `datasets/data/entities/electoral.csv` and is reachable
 *       via `states.codeFromSlug(slug)` + `states.name(code)` in
 *       the Svelte component layer - this helper is the test-friendly
 *       fallback used only when the runtime state-catalogue lookup
 *       returns null.
 *    2. The brief Max M2c example "Maharashtra State Assembly, Nov
 *       2024" uses single-word state names where the lossy
 *       capitalisation is a no-op.
 *  Exported for vitest. */
export function titleCaseStateSlug(slug: string): string {
  if (!slug) return "";
  return slug
    .split("-")
    .map((part) => (part.length === 0 ? part : part[0]!.toUpperCase() + part.slice(1)))
    .join(" ");
}

/** Pure: build the parliament-latest SQL. Returns one row per
 *  `(period_label)` for the focal party, with seats and vote
 *  inputs summed across all states. The caller picks the
 *  chronologically max row in JS via `chronologicalSortKey`.
 *
 *  CAST(SUM(...) AS BIGINT) per the chronic DuckDB-WASM HUGEINT
 *  trap documented in user-memory lessons-2026-06-12: SUM(BIGINT)
 *  promotes to HUGEINT which duckdb-wasm serializes as a string
 *  that JS `Number.isFinite(...)` rejects, so the `intOrNull`
 *  helper would surface `null`-then-zero on the citizen UI.
 *
 *  Exported for vitest. */
export function buildParliamentLatestSql(
  safePartyId: string,
  historyClause: string,
  partyHistoryUrl: string,
): string {
  return `
    SELECT
      period_label,
      MAX(year) AS year,
      CAST(SUM(seats) AS BIGINT) AS party_seats,
      CAST(SUM(party_votes) AS BIGINT) AS party_votes,
      CAST(SUM(total_votes) AS BIGINT) AS total_votes
    FROM read_csv('${partyHistoryUrl}', ${historyClause}, header=true)
    WHERE party_id = '${safePartyId}' AND body = 'parliament'
    GROUP BY period_label
    ORDER BY year DESC, period_label DESC
  `;
}

/** Pure: build the state-assemblies-latest SQL. Returns one row per
 *  `(state, period_label)` where:
 *    - `state` + `period_label` is the LATEST assembly cycle for that
 *      state (computed from the full all-parties view, NOT just rows
 *      belonging to the focal party).
 *    - `party_seats` is the focal party's seats won in that cycle.
 *    - `chamber_seats` is the sum across ALL parties (= chamber size
 *      under first-past-the-post).
 *  States where the focal party has NO row in the latest cycle are
 *  excluded (the inner JOIN restricts the row set). The caller
 *  aggregates the resulting rows in JS to surface seats_won,
 *  seats_total, state_count, and the latest_event_label.
 *
 *  ROW_NUMBER() OVER (PARTITION BY state ORDER BY year DESC) picks
 *  the per-state latest. QUALIFY is NOT used because earlier DuckDB-
 *  WASM bundles in this project's history have not supported it
 *  reliably; the outer subquery pattern is portable.
 *
 *  Exported for vitest. */
export function buildStateAssembliesLatestSql(
  safePartyId: string,
  historyClause: string,
  partyHistoryUrl: string,
): string {
  return `
    WITH all_assembly AS (
      SELECT state, period_label, year, party_id, seats
      FROM read_csv('${partyHistoryUrl}', ${historyClause}, header=true)
      WHERE body = 'assembly'
    ),
    state_cycles AS (
      SELECT DISTINCT state, period_label, year FROM all_assembly
    ),
    ranked AS (
      SELECT state, period_label, year,
        ROW_NUMBER() OVER (PARTITION BY state ORDER BY year DESC, period_label DESC) AS rn
      FROM state_cycles
    ),
    latest_per_state AS (
      SELECT state, period_label, year FROM ranked WHERE rn = 1
    ),
    party_latest AS (
      SELECT a.state, a.period_label, a.year,
        CAST(SUM(a.seats) AS BIGINT) AS party_seats
      FROM all_assembly a
      JOIN latest_per_state l
        ON a.state = l.state AND a.period_label = l.period_label
      WHERE a.party_id = '${safePartyId}'
      GROUP BY a.state, a.period_label, a.year
    ),
    chamber_latest AS (
      SELECT a.state, a.period_label,
        CAST(SUM(a.seats) AS BIGINT) AS chamber_seats
      FROM all_assembly a
      JOIN latest_per_state l
        ON a.state = l.state AND a.period_label = l.period_label
      GROUP BY a.state, a.period_label
    )
    SELECT
      p.state,
      p.period_label,
      p.year,
      p.party_seats,
      c.chamber_seats
    FROM party_latest p
    JOIN chamber_latest c
      ON p.state = c.state AND p.period_label = c.period_label
    ORDER BY p.year DESC, p.period_label DESC, p.state
  `;
}

/** Pure: project the parliament-latest SQL rows into the view-model
 *  shape. Picks the chronologically most-recent row via
 *  `chronologicalSortKey`. Returns null when the row set is empty
 *  (party has no LS history). Exported for vitest. */
export function projectParliamentLatest(
  rows: RawParliamentRow[],
): ParliamentLatest | null {
  if (rows.length === 0) return null;
  let best: RawParliamentRow | null = null;
  let bestKey = "";
  for (const r of rows) {
    if (!r.period_label) continue;
    const key = chronologicalSortKey(r.period_label);
    if (best === null || key > bestKey) {
      best = r;
      bestKey = key;
    }
  }
  if (!best || !best.period_label) return null;
  const year = intOrNull(best.year);
  if (year === null) return null;
  const month_label = parseMonthFromPeriodLabel(best.period_label);
  if (!month_label) return null;
  const event_id = lsEventIdFromPeriodLabel(best.period_label) ?? "";
  const seats_won = intOrNull(best.party_seats) ?? 0;
  const party_votes = intOrNull(best.party_votes);
  const total_votes = intOrNull(best.total_votes);
  let vote_share_pct: number | null = null;
  if (party_votes !== null && total_votes !== null && total_votes > 0) {
    vote_share_pct = (party_votes * 100) / total_votes;
  }
  return {
    year,
    event_id,
    month_label,
    seats_won,
    seats_total: LS_TOTAL_SEATS,
    vote_share_pct,
    rank_label: null,
  };
}

/** Pure: project the state-assemblies SQL rows into the view-model
 *  shape. Returns null when the row set is empty (party has no
 *  state-assembly history).
 *
 *  The `latest_event_label` is built by picking the chronologically
 *  most-recent row (state + period_label) and formatting it as
 *  `"<State> State Assembly, <Mon> <YYYY>"`. The state-name resolver
 *  is injected so production callers can plumb the canonical states
 *  catalogue lookup (`states.name(states.codeFromSlug(slug))`) while
 *  tests can use a synthetic Map. When the resolver returns null,
 *  the helper falls back to the slug Title Cased via
 *  `titleCaseStateSlug` so the line never shows an empty placeholder.
 *
 *  Exported for vitest. */
export function projectStateAssembliesLatest(
  rows: RawStateAssemblyRow[],
  stateNameFromSlug: (slug: string) => string | null,
): StateAssembliesLatest | null {
  if (rows.length === 0) return null;
  let seats_won = 0;
  let seats_total = 0;
  const states = new Set<string>();
  let latest: RawStateAssemblyRow | null = null;
  let latestKey = "";
  for (const r of rows) {
    if (!r.state || !r.period_label) continue;
    states.add(r.state);
    seats_won += intOrNull(r.party_seats) ?? 0;
    seats_total += intOrNull(r.chamber_seats) ?? 0;
    const key = chronologicalSortKey(r.period_label);
    if (latest === null || key > latestKey || (key === latestKey && r.state < (latest.state ?? ""))) {
      latest = r;
      latestKey = key;
    }
  }
  if (states.size === 0 || latest === null || !latest.state || !latest.period_label) {
    return null;
  }
  const month_label = parseMonthFromPeriodLabel(latest.period_label);
  if (!month_label) return null;
  const resolved = stateNameFromSlug(latest.state);
  const state_name =
    resolved && resolved.trim().length > 0
      ? resolved
      : titleCaseStateSlug(latest.state);
  return {
    seats_won,
    seats_total,
    state_count: states.size,
    latest_event_label: `${state_name} State Assembly, ${month_label}`,
    latest_event_sort_key: latestKey,
  };
}

/** Pure: pick the citizen-facing "Last contested" one-liner. Compares
 *  parliament_latest vs state_assemblies_latest by chronological sort
 *  key; whichever is more recent wins. Ties (same year + month for an
 *  LS general AND an AC general) break in favour of the state assembly
 *  because they are state-grain (more locally specific) - the citizen
 *  reads it as the more concrete event. Returns null when both are
 *  null. Exported for vitest. */
export function pickLastContestedLabel(
  parliament: ParliamentLatest | null,
  assemblies: StateAssembliesLatest | null,
): string | null {
  const parliamentKey =
    parliament === null
      ? null
      : `${parliament.year.toString().padStart(4, "0")}-${String(MONTH_INDEX[parliament.month_label.slice(0, 3)] ?? 99).padStart(2, "0")}`;
  const assemblyKey = assemblies?.latest_event_sort_key ?? null;
  if (parliamentKey === null && assemblyKey === null) return null;
  if (assemblyKey !== null && (parliamentKey === null || assemblyKey >= parliamentKey)) {
    return assemblies!.latest_event_label;
  }
  return `Parliament General Election, ${parliament!.month_label}`;
}

/** Module-level Promise cache, keyed by party_id. Mirrors the
 *  `detailCache` pattern from `party-detail.ts`: repeated calls
 *  for the same party return the SAME Promise so the browser pays
 *  the corpus-fetch + DuckDB query exactly once per tab. */
const strengthCache = new Map<
  string,
  Promise<PartyCurrentStrength | null>
>();

/**
 * Load the per-party Current Strength view-model. Returns `null` for
 * sentinel parties (caller should also short-circuit at the meta
 * level - this is a defensive second line) or for parties with no
 * Parliament AND no state assembly history at all.
 *
 * The state-name resolver is injected (callers from Svelte plumb
 * the `states` reactive store; tests pass a synthetic resolver).
 * When undefined, the helper falls back to `titleCaseStateSlug`
 * so vitest stays free of the `states.svelte.ts` runtime.
 *
 * Per the canonical-store loader pattern: the cache survives the
 * lifetime of the browser tab; only `__resetForTests` clears it.
 * A fetch failure clears that party's cache entry so a retry
 * re-issues the underlying queries.
 */
export function loadPartyCurrentStrength(
  party_id: string | null | undefined,
  opts: {
    is_sentinel?: boolean;
    stateNameFromSlug?: (slug: string) => string | null;
  } = {},
): Promise<PartyCurrentStrength | null> {
  if (!party_id) return Promise.resolve(null);
  if (opts.is_sentinel) return Promise.resolve(null);
  const cached = strengthCache.get(party_id);
  if (cached) return cached;
  const promise = fetchPartyCurrentStrength(
    party_id,
    opts.stateNameFromSlug ?? (() => null),
  ).catch((err) => {
    strengthCache.delete(party_id);
    throw err;
  });
  strengthCache.set(party_id, promise);
  return promise;
}

async function fetchPartyCurrentStrength(
  party_id: string,
  stateNameFromSlug: (slug: string) => string | null,
): Promise<PartyCurrentStrength | null> {
  await registerCsvFile(PARTY_HISTORY_URL);
  const historyClause = await csvColumnsClause(PARTY_HISTORY_REL);
  const safePartyId = party_id.replace(/'/g, "''");

  const parliamentSql = buildParliamentLatestSql(
    safePartyId,
    historyClause,
    PARTY_HISTORY_URL,
  );
  const stateAssembliesSql = buildStateAssembliesLatestSql(
    safePartyId,
    historyClause,
    PARTY_HISTORY_URL,
  );
  const [parliamentRows, stateAssemblyRows] = await Promise.all([
    query<RawParliamentRow>(parliamentSql),
    query<RawStateAssemblyRow>(stateAssembliesSql),
  ]);

  const parliament_latest = projectParliamentLatest(parliamentRows);
  const state_assemblies_latest = projectStateAssembliesLatest(
    stateAssemblyRows,
    stateNameFromSlug,
  );
  if (parliament_latest === null && state_assemblies_latest === null) {
    return null;
  }
  const last_contested_label = pickLastContestedLabel(
    parliament_latest,
    state_assemblies_latest,
  );
  return {
    parliament_latest,
    state_assemblies_latest,
    last_contested_label,
  };
}

/** Test-only cache reset. NOT exported from index.ts. */
export function __resetForTests(): void {
  strengthCache.clear();
}
