// Per-state election event inventory loader.
//
// This is the citizen-facing view of "which elections does each state
// have data for?" — see ADR-0023 and docs/concepts/government-vs-election.md.
// The frontend NEVER picks a global "current election"; instead, every
// state-scoped route resolves the default event from this catalogue.
//
// The schema is hand-authored at datasets/reference/in/election-events.json
// and held in lockstep with backend/yen_gov/sources/eci/events.py by
// backend/tests/test_datasets_integrity.py::test_election_events_catalogue_matches_backend_registry.
//
// This file is the only place in the frontend that knows the catalogue's
// shape; routes ask `defaultEventForState(state)` and `listEventsForState(state)`.

import { DATA_BASE } from "./paths";

export type EventKind = "assembly" | "lok_sabha" | "by_election";
export type DataStatus = "complete" | "partial" | "pending_upstream";

export interface ElectionEventRow {
  event_id: string;
  kind: EventKind;
  display: string;
  polled_on: string;        // ISO date (YYYY-MM-DD)
  term_end_estimated?: string | null;
  default?: boolean;
  data_status?: DataStatus;
  notes?: string;
}

export interface ElectionEventsCatalogue {
  $schema: string;
  $schema_version: string;
  sources: { url: string; fetched_at: string; name?: string; authority?: string }[];
  states: Record<string, ElectionEventRow[]>;
}

let _cache: Promise<ElectionEventsCatalogue> | null = null;

/**
 * Fetch (and cache) the catalogue. The catalogue is small (~3 KB gzipped
 * for ~15 states) and is loaded lazily on first call. All callers share a
 * single Promise — there is no need for an in-memory store rune.
 */
export function fetchElectionEvents(): Promise<ElectionEventsCatalogue> {
  if (_cache !== null) return _cache;
  _cache = fetch(`${DATA_BASE}/reference/in/election-events.json`).then(async res => {
    if (!res.ok) {
      throw new Error(
        `fetch /reference/in/election-events.json failed: ${res.status} ${res.statusText}`,
      );
    }
    return (await res.json()) as ElectionEventsCatalogue;
  });
  return _cache;
}

/**
 * The default event for a state is the row marked `default: true`. If no
 * row is so marked, falls back to the first row (catalogue convention is
 * most-recent-first). Returns null when the state has no entries — the
 * caller renders the "no election data" UI rather than a 404.
 */
export function defaultEventForState(
  catalogue: ElectionEventsCatalogue | null,
  stateCode: string | null,
): ElectionEventRow | null {
  if (!catalogue || !stateCode) return null;
  const rows = catalogue.states[stateCode];
  if (!rows || rows.length === 0) return null;
  return rows.find(r => r.default === true) ?? rows[0];
}

/** All known events for a state (most recent first per catalogue order). */
export function listEventsForState(
  catalogue: ElectionEventsCatalogue | null,
  stateCode: string | null,
): ElectionEventRow[] {
  if (!catalogue || !stateCode) return [];
  return catalogue.states[stateCode] ?? [];
}

/** Lookup a specific event in a state — used by routes that take an event_id segment. */
export function findEvent(
  catalogue: ElectionEventsCatalogue | null,
  stateCode: string | null,
  eventId: string,
): ElectionEventRow | null {
  return listEventsForState(catalogue, stateCode).find(r => r.event_id === eventId) ?? null;
}

/**
 * Days since this event's polling date (negative if polling is in the future).
 * Used by StateOverview's recency rule: <90 days → election leads above the
 * government card; otherwise government card leads.
 */
export function daysSincePolled(row: ElectionEventRow, now: Date = new Date()): number {
  const polled = new Date(row.polled_on + "T00:00:00Z").getTime();
  return Math.floor((now.getTime() - polled) / (1000 * 60 * 60 * 24));
}
