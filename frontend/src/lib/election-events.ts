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

// PR-W2a (2026-06-10): the kind enum is extended with `general_bye` +
// `assembly_bye` per the PR-0 bye-slug doctrine locked in
// docs/architecture/frontend/url-grammar.md. `by_election` is the legacy
// catch-all retained for backwards-compatibility with any catalogue rows
// not yet reclassified into the more specific assembly_bye / general_bye
// kinds. EventKind is a string union, not an exhaustive switch target;
// adding variants does not break the few `kind === "..."` equality
// checks in routes (StateElection / StateTopic / Compare).
export type EventKind =
  | "assembly"
  | "parliament"
  | "general_bye"
  | "assembly_bye"
  | "by_election";
export type DataStatus = "complete" | "partial" | "pending_upstream";

export interface ElectionEventRow {
  event_id: string;
  /**
   * Strangler-fig for one release cycle (PR-W2a, 2026-06-10): prior
   * cohort-form event_ids (e.g. `LsGenJun2024`, `AcGenMay2026`) that ALSO
   * resolve to this row. Covers (a) old bookmarks, (b) the on-disk
   * period_label values in datasets/data/datapoints/electoral/*.csv which
   * are still in cohort form (the backend's parse_period_label contract
   * makes them invariant). See backend/tests/test_election_event_alias_resolution.py
   * for the alias-index oracle. After W3+ surfaces flip to the renamed
   * slug this becomes a curiosity; deletion is a Phase 5+ concern.
   */
  event_id_aliases?: string[];
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
 * The default event for a state is the most-recent **assembly** election.
 * Returns null when the state has no entries — the caller renders the
 * "no election data" UI rather than a 404.
 *
 * Why assembly-only: every consumer of this helper (StateOverview,
 * StateTopic, Party, Explore, Constituency) is an assembly-house view —
 * AC map, house composition, seats-by-party, per-constituency drill-in.
 * PR #525 added the `LsGenJun2024` parliament event to every state's
 * catalogue. For any state whose last assembly election predates June 2024
 * (e.g. Karnataka AcGenMay2023), a naive most-recent-by-polled_on default
 * now resolves to the Parliament event, whose `IN-<state>-LsGenJun2024-PARTY-*`
 * rows the assembly query does not match — so the page falls into the
 * "not yet in the canonical store" arm and the donut / seats-by-party /
 * seat-composition sections vanish. Filtering to `kind === "assembly"`
 * keeps the state hub on its assembly axis; the picker (listEventsForState)
 * still lists the LS event so a citizen can select it explicitly.
 *
 * Fallback: if a state somehow has no assembly event at all, fall back to
 * the most-recent event of any kind so we never 404 a state that only has
 * non-assembly data ingested.
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
  const mostRecent = (candidates: ElectionEventRow[]): ElectionEventRow | null =>
    candidates.length === 0
      ? null
      : candidates.reduce((latest, r) => (r.polled_on > latest.polled_on ? r : latest));
  // Assembly-house views default to the latest assembly election; fall back
  // to the latest event of any kind only when no assembly event exists.
  return mostRecent(rows.filter((r) => r.kind === "assembly")) ?? mostRecent(rows);
}

/**
 * All known events for a state, sorted most-recent-first by `polled_on`.
 *
 * The on-disk catalogue is hand-authored and is not guaranteed to be
 * pre-sorted (in practice the AE-panel backfills landed S15 / S23 etc.
 * oldest-first). Sorting here gives every consumer a stable order: the
 * StateOverview picker leads with the most-recent event; downstream
 * adapters (ElectionSeatsTrend, etc.) re-sort by their own axis.
 *
 * Optional `kind` arg filters to a single event class (assembly /
 * parliament / by_election). Per Fowler verdict (2026-06-09 debate):
 * the Compare 'elec' mode uses this to constrain the cross-event
 * picker to the same kind as the origin event - if the user started
 * in an assembly election (kind === 'assembly') the dropdown lists
 * only assembly events; if they started in a parliament election
 * (kind === 'parliament') only LS events show. Cross-kind compare is
 * impossible by construction.
 */
export function listEventsForState(
  catalogue: ElectionEventsCatalogue | null,
  stateCode: string | null,
  kind?: EventKind,
): ElectionEventRow[] {
  if (!catalogue || !stateCode) return [];
  const rows = catalogue.states[stateCode];
  if (!rows) return [];
  // Copy before sort - never mutate the cached catalogue.
  const sorted = [...rows].sort((a, b) => b.polled_on.localeCompare(a.polled_on));
  return kind ? sorted.filter((r) => r.kind === kind) : sorted;
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

/**
 * True when the catalogue declares this event has no on-disk per-event
 * files yet (because the upstream publisher has not released results, or
 * the ingest has not landed). Citizen surfaces should render a calm
 * "Pending" affordance rather than fire a fetch and render an amber
 * "error" badge when the inevitable 404 comes back.
 *
 * The honesty tool `tools.election_events_honesty` is the single writer
 * that flips `data_status` between `complete` and `pending_upstream`
 * based on on-disk truth; see backend/tests/test_election_events_honesty.py
 * for the contract gate that keeps the catalogue honest.
 *
 * Returns false for rows without an explicit `data_status` field so old
 * cached catalogues continue to render as before until the next deploy.
 */
export function isPendingUpstream(row: ElectionEventRow): boolean {
  return row.data_status === "pending_upstream";
}
