// Per-state election event inventory loader.
//
// This is the citizen-facing view of "which elections does each state
// have data for?" — see ADR-0023 and docs/concepts/government-vs-election.md.
// The frontend NEVER picks a global "current election"; instead, every
// state-scoped route resolves the default event from this catalogue.
//
// The schema is hand-authored at datasets/taxonomy/election_events.json
// and held in lockstep with backend/yen_gov/sources/eci/events.py by
// backend/tests/test_datasets_integrity.py::test_election_events_catalogue_matches_backend_registry.
//
// Path moved from `datasets/reference/in/election-events.json` in T.0b
// (TODO/20260517-canonical-long-format-pivot.md §0e Phase 0 closeout). Shape
// unchanged; the reference/in/ original is deleted in T.0c.
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
  _cache = fetch(`${DATA_BASE}/taxonomy/election_events.json`).then(async res => {
    if (!res.ok) {
      throw new Error(
        `fetch /taxonomy/election_events.json failed: ${res.status} ${res.statusText}`,
      );
    }
    return (await res.json()) as ElectionEventsCatalogue;
  });
  return _cache;
}

/**
 * The default event for a state is the one with the most recent `polled_on`
 * date. Returns null when the state has no entries — the caller renders the
 * "no election data" UI rather than a 404.
 *
 * Previously this read a hand-authored `default: true` flag with a `rows[0]`
 * fallback. That fallback returned the OLDEST event whenever a backfill
 * forgot to set the flag (Meghalaya showed 1978-02-25 instead of 2023-02-27,
 * Tripura 1977-12-31 instead of 2023-02-16, plus 5 other states off by 5
 * years each). `polled_on` is the canonical fact — using it directly
 * auto-corrects on every new ingest. PR #191 made polled_on canonical in
 * this helper; the follow-up Q1+PR-2 PR (2026-05-24) removed the now-dead
 * `default` field from the schema, the row type, the 23 on-disk entries,
 * the Pydantic seed, and the at-most-one-default invariant Tier-A test.
 */
export function defaultEventForState(
  catalogue: ElectionEventsCatalogue | null,
  stateCode: string | null,
): ElectionEventRow | null {
  if (!catalogue || !stateCode) return null;
  const rows = catalogue.states[stateCode];
  if (!rows || rows.length === 0) return null;
  // polled_on is ISO YYYY-MM-DD so lexicographic max == chronological max.
  return rows.reduce((latest, r) =>
    r.polled_on > latest.polled_on ? r : latest,
  );
}

/**
 * All known events for a state, sorted most-recent-first by `polled_on`.
 *
 * The on-disk catalogue is hand-authored and is not guaranteed to be
 * pre-sorted (in practice the AE-panel backfills landed S15 / S23 etc.
 * oldest-first). Sorting here gives every consumer a stable order: the
 * StateOverview picker leads with the most-recent event; downstream
 * adapters (ElectionSeatsTrend, etc.) re-sort by their own axis.
 */
export function listEventsForState(
  catalogue: ElectionEventsCatalogue | null,
  stateCode: string | null,
): ElectionEventRow[] {
  if (!catalogue || !stateCode) return [];
  const rows = catalogue.states[stateCode];
  if (!rows) return [];
  // Copy before sort — never mutate the cached catalogue.
  return [...rows].sort((a, b) => b.polled_on.localeCompare(a.polled_on));
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
