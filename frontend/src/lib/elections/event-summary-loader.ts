// Event-summary loader: the single read seam for the per-event aggregate
// mart shipped by PR-E2 of TODO/20260615-elections-redesign-plan.md.
//
// File class: `datasets/data/marts/elections/event_summary.csv` (12 cols,
// composite PK `(event_id, state_code)`; see PR-E1 schema for the full
// shape). Citizen routes mounted in PR-E4:
//
//   /t/elections             -> GeneralElections.svelte; filter scope='national'
//   /t/elections/assemblies  -> AssemblyElections.svelte; filter scope='state'
//
// Both routes read this loader once on mount via the
// `loadEventSummary()` singleton-promise cache; the page-level view-
// models (general-elections-model + assembly-elections-model) project
// the raw rows into citizen-render shapes.
//
// Reader contract follows the project's typed-read seam doctrine
// (CLAUDE.md Holy Law #3): `registerCsvFile` -> `read_csv(...,
// columns=...)`. The columns map flows from columns.json via
// `csvColumnsClause`, so any schema change in PR-E1 propagates without
// touching the reader.

import { csvColumnsClause } from "../canonical/csv-columns";
import { query, registerCsvFile } from "../duckdb";
import { DATA_BASE } from "../paths";

/** File-class glob and URL for the event_summary mart. */
export const EVENT_SUMMARY_REL =
  "datasets/data/marts/elections/event_summary.csv";
export const EVENT_SUMMARY_URL =
  `${DATA_BASE}/data/marts/elections/event_summary.csv`;

/** Closed scope vocabulary mirrors the PR-E1 columns.json enum. */
export type EventSummaryScope = "national" | "state";

/** Closed event-kind vocabulary mirrors the PR-E1 columns.json enum. */
export type EventSummaryKind =
  | "parliament"
  | "assembly"
  | "assembly_bye"
  | "general_bye"
  | "by_election";

/** One row of the event_summary mart. Field types track DuckDB-WASM
 *  coercion of the file-class columns (string/integer/number/etc.). */
export interface EventSummaryRow {
  event_id: string;
  /** NULL for scope='national' rows (one row per event_id collapsing
   *  all PCs); set for scope='state' rows (one row per Assembly +
   *  state). DuckDB-WASM surfaces SQL NULL as JS `null`. */
  state_code: string | null;
  scope: EventSummaryScope;
  kind: EventSummaryKind;
  /** ISO date string (YYYY-MM-DD), the catalogue's polled_on. */
  polled_on: string;
  /** Canonical `parties.IN.<X>` party_id of the seat leader. NULL when
   *  the writer could not attribute a leader (zero-seat event, etc.). */
  leading_party_id: string | null;
  seats_won: number;
  seats_contested: number;
  /** Event-scope turnout (SUM(votes_polled) / SUM(electors) * 100).
   *  NULL when the upstream summary.csv rows lack electors/votes. */
  turnout_pct: number | null;
  runner_up_party_id: string | null;
  runner_up_seats: number | null;
  source_id: string;
}

/** DuckDB-WASM row shape (BIGINT -> bigint, DOUBLE -> number, NULL -> null). */
interface RawRow {
  event_id: string;
  state_code: string | null;
  scope: string;
  kind: string;
  polled_on: string;
  leading_party_id: string | null;
  seats_won: number | bigint | null;
  seats_contested: number | bigint | null;
  turnout_pct: number | null;
  runner_up_party_id: string | null;
  runner_up_seats: number | bigint | null;
  source_id: string;
}

// Singleton promise cache: one fetch + parse per page session. Both
// page routes (General + Assembly) trigger `loadEventSummary()` on
// mount; the second + later callers share the same in-flight promise.
let summaryPromise: Promise<EventSummaryRow[]> | null = null;

/** Reset the cache; for tests and HMR. Production never calls this. */
export function _resetEventSummaryCacheForTests(): void {
  summaryPromise = null;
}

/** Fetch + parse the event_summary mart (once per session, cached). */
export async function loadEventSummary(): Promise<EventSummaryRow[]> {
  if (summaryPromise) return summaryPromise;
  summaryPromise = (async () => {
    await registerCsvFile(EVENT_SUMMARY_URL);
    const columnsClause = await csvColumnsClause(EVENT_SUMMARY_REL);
    const sql = `SELECT
        event_id,
        state_code,
        scope,
        kind,
        polled_on,
        leading_party_id,
        CAST(seats_won AS BIGINT) AS seats_won,
        CAST(seats_contested AS BIGINT) AS seats_contested,
        turnout_pct,
        runner_up_party_id,
        CAST(runner_up_seats AS BIGINT) AS runner_up_seats,
        source_id
      FROM read_csv('${EVENT_SUMMARY_URL}', ${columnsClause}, header=true)`;
    const raw = await query<RawRow>(sql);
    return raw.map(_normaliseRow);
  })();
  summaryPromise.catch(() => {
    // Surface the failure to callers, but reset the cache so the next
    // attempt re-fetches instead of always rejecting.
    summaryPromise = null;
  });
  return summaryPromise;
}

function _normaliseRow(raw: RawRow): EventSummaryRow {
  return {
    event_id: raw.event_id,
    state_code: raw.state_code,
    scope: raw.scope as EventSummaryScope,
    kind: raw.kind as EventSummaryKind,
    polled_on: raw.polled_on,
    leading_party_id: raw.leading_party_id,
    seats_won: _intOrZero(raw.seats_won),
    seats_contested: _intOrZero(raw.seats_contested),
    turnout_pct: raw.turnout_pct,
    runner_up_party_id: raw.runner_up_party_id,
    runner_up_seats: _intOrNull(raw.runner_up_seats),
    source_id: raw.source_id,
  };
}

function _intOrZero(value: number | bigint | null): number {
  if (value == null) return 0;
  if (typeof value === "bigint") return Number(value);
  return Number.isFinite(value) ? Math.trunc(value) : 0;
}

function _intOrNull(value: number | bigint | null): number | null {
  if (value == null) return null;
  if (typeof value === "bigint") return Number(value);
  return Number.isFinite(value) ? Math.trunc(value) : null;
}
