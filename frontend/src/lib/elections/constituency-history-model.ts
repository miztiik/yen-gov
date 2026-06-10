// Pure derivation for ConstituencyHistoryBar.svelte (PR-W4a, 2026-06-10).
//
// Election experience overhaul plan: the constituency drill page mounts
// a row-per-event history bar so the citizen sees the seat's full
// electoral lineage at a glance. Width = winner vote-share %, right-side
// party-pill + margin %.
//
// Extracted from the Svelte component for the project's standard reason:
// vitest is node-env / no @testing-library/svelte. The pure model is the
// behavioural contract; the template just echoes its rows.
//
// Data flow (in Constituency.svelte):
//   1. Resolve current entity_id from the slug lookup.
//   2. Resolve the body (PC vs AC) from the event-slug prefix.
//   3. Filter `listEventsForState` to events of that body.
//   4. For each event, call `loadElectionResults({ event, [state] })`
//      and find the row whose `entity_id` matches.
//   5. Pass the resulting EventResultEntry[] to `buildHistoryRows`.
//
// The model never owns I/O - it composes the per-event loader output
// into the row shape the template renders.

import type { ElectionEventRow } from "../election-events";
import type { ElectionResultRow } from "../view-models/election-results";

/** One row of the history bar. The Svelte template reads every field
 *  verbatim; nothing is computed at render time. */
export interface HistoryRow {
  event_id: string;
  /** ISO YYYY-MM-DD polled_on date - lets the template format the
   *  pill year + ISO label in one place. */
  polled_on: string;
  year: number;
  /** Canonical party id from `dim_parties` (e.g. `parties.IN.BJP`).
   *  Falls back to a synthesised UNK id when the loader returned null
   *  so `getPartyColor()` always has a stable key. */
  winner_party_id: string;
  /** Display label - the upstream `party_short_raw` is preferred so
   *  fringe parties not yet in `parties.json` do not show the literal
   *  UNK sentinel (yen-gov-architecture.md "v1.1 party_short_raw"). */
  winner_party_short: string;
  /** Winner's share of the votes_polled denominator, percent. Drives the
   *  bar width. */
  winner_vote_share_pct: number;
  margin_pct: number;
}

/** Per-event loader output, paired with the catalogue row so the model
 *  has every fact it needs without re-walking the catalogue. */
export interface EventResultEntry {
  event: ElectionEventRow;
  /** Full result-row set for the event (national-PC scope) or for the
   *  event x state (STATE-AC scope). The model filters to this
   *  entity_id internally. Empty array = event has no data on disk
   *  yet; the row is skipped. */
  rows: readonly ElectionResultRow[];
}

/** The winner row for a given entity_id in a loader response. Returns
 *  null when no row exists (entity not contested in this event, or the
 *  partition is not yet on disk). */
export function winnerForEntity(
  rows: readonly ElectionResultRow[],
  entity_id: string,
): ElectionResultRow | null {
  // Winner-only scopes (NATIONAL-PC / STATE-AC) emit a single row per
  // entity with `is_winner === true` and `position === 1`. We accept
  // the first row that matches the entity_id and is the winner;
  // ignoring drill-down-scope rows that the caller would never pass.
  for (const r of rows) {
    if (r.entity_id !== entity_id) continue;
    if (!r.is_winner) continue;
    return r;
  }
  return null;
}

/** Build the history rows for a given entity. Sorted oldest-first
 *  (left-to-right reads as time-moving-forward, matching `YearPillStrip`
 *  + the indiavotes.com convention the plan-doc cites). Pure - safe to
 *  re-run on every loader resolve. */
export function buildHistoryRows(
  entries: readonly EventResultEntry[],
  entity_id: string,
): HistoryRow[] {
  const out: HistoryRow[] = [];
  for (const entry of entries) {
    const winner = winnerForEntity(entry.rows, entity_id);
    if (!winner) continue;
    // Skip events where the loader returned a winner but key
    // chart-driving fields are null (e.g. summary CSV present but
    // turnout / margin not parsed for that year). Surfacing a
    // zero-width bar would mislead more than omitting the row.
    if (
      winner.vote_share_pct == null ||
      winner.margin_pct == null
    )
      continue;
    out.push({
      event_id: entry.event.event_id,
      polled_on: entry.event.polled_on,
      year: yearOfPolledOn(entry.event.polled_on),
      winner_party_id: winner.party_id ?? "parties.IN.UNK",
      winner_party_short:
        winner.party_short_raw ?? winner.party_short ?? "—",
      winner_vote_share_pct: winner.vote_share_pct,
      margin_pct: winner.margin_pct,
    });
  }
  out.sort((a, b) => a.polled_on.localeCompare(b.polled_on));
  return out;
}

function yearOfPolledOn(polled_on: string): number {
  const yr = Number(polled_on.slice(0, 4));
  return Number.isFinite(yr) ? yr : 0;
}
