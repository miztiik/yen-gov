// Citizen view-model loader for the ElectionSeatsTrend chart (PR-G / Phase 1.3c).
//
// Fans the four party-* indicators across every event the caller asks for
// (typically the full per-state catalogue) and returns one PartyTotals[] per
// event_id. The wrapper component reshapes the result into ResultSummaryDoc[]
// for the existing electionsToStackedTrend adapter — the adapter stays pure
// and untouched.
//
// What is JOINed:
//   elections.election_results  — numeric facts (party-* indicators only)
//   elections.dim_parties   — party labels (short_name, eci_code)
//   taxonomy.sources        — provenance for the union across events
//
// LoaderResult arms mirror PR-F:
//   ok       — at least one event yielded party rows.
//   partial  — caller passed zero events (state has no partywise cohort).
//   failed   — DuckDB-WASM / fetch / SQL error.

import { describeFailure, type LoaderResult } from "../loader-result";
import { query, registerTable } from "../duckdb";
import type { PartyTotals, SourceRef } from "../data";

export interface ElectionSeatsTrendEvent {
  event_id: string;
  party_totals: PartyTotals[];
  total_seats: number;
}

export interface ElectionSeatsTrendViewModel {
  state: string;
  events: ElectionSeatsTrendEvent[];
  sources: SourceRef[];
}

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

interface PartyRow {
  period_label: string;
  short_name_key: string;
  short_name: string | null;
  full_name: string | null;
  eci_code: string | null;
  seats_contested: number | null;
  seats_won: number | null;
  votes: number | null;
  vote_share_pct: number | null;
}

interface SourceJoinRow {
  url_main: string | null;
}

const num = (v: unknown): number => (v == null ? 0 : Number(v));

async function runQueries(
  state_code: string,
  event_ids: string[],
): Promise<{ parties: PartyRow[]; sources: SourceJoinRow[] }> {
  await Promise.all([
    registerTable("elections.election_results"),
    registerTable("elections.dim_parties"),
    registerTable("taxonomy.sources"),
  ]);

  const partyPrefix = sqlString(`IN-${state_code}-`);
  const eventList = event_ids.map(sqlString).join(", ");

  const partySql = `
    SELECT
      o.period_label                                              AS period_label,
      regexp_extract(o.entity_id, '-PARTY-(.+)$', 1)              AS short_name_key,
      dp.short_name                                               AS short_name,
      dp.full_name                                                AS full_name,
      dp.eci_code                                                 AS eci_code,
      MAX(CASE WHEN o.indicator_id = 'party-contested-acs'  THEN o.value_numeric END) AS seats_contested,
      MAX(CASE WHEN o.indicator_id = 'party-seats-won'      THEN o.value_numeric END) AS seats_won,
      MAX(CASE WHEN o.indicator_id = 'party-votes-polled'   THEN o.value_numeric END) AS votes,
      MAX(CASE WHEN o.indicator_id = 'party-vote-share-pct' THEN o.value_numeric END) AS vote_share_pct
    FROM election_results o
    LEFT JOIN dim_parties dp
      ON dp.short_name = regexp_extract(o.entity_id, '-PARTY-(.+)$', 1)
    WHERE o.entity_id LIKE ${partyPrefix} || '%-PARTY-%'
      AND o.period_label IN (${eventList})
      AND o.indicator_id IN (
        'party-contested-acs',
        'party-seats-won',
        'party-votes-polled',
        'party-vote-share-pct'
      )
    GROUP BY 1, 2, 3, 4, 5
  `;
  const parties = await query<PartyRow>(partySql);

  const sources = await query<SourceJoinRow>(`
    SELECT DISTINCT s.url_main
    FROM election_results o
    JOIN sources s ON s.source_id = o.source_id
    WHERE o.period_label IN (${eventList})
      AND o.entity_id LIKE ${partyPrefix} || '%'
      AND s.url_main IS NOT NULL
      AND s.url_main <> ''
    ORDER BY s.url_main
  `);

  return { parties, sources };
}

function assembleResult(
  state_code: string,
  rows: { parties: PartyRow[]; sources: SourceJoinRow[] },
): ElectionSeatsTrendViewModel {
  // Group rows by period_label.
  const byEvent = new Map<string, PartyRow[]>();
  for (const r of rows.parties) {
    const arr = byEvent.get(r.period_label) ?? [];
    arr.push(r);
    byEvent.set(r.period_label, arr);
  }

  const events: ElectionSeatsTrendEvent[] = [];
  for (const [event_id, arr] of byEvent) {
    const party_totals: PartyTotals[] = arr.map((r) => ({
      party_eci_code: r.eci_code ?? null,
      party_short: r.short_name ?? r.short_name_key,
      party_full: r.full_name ?? null,
      seats_contested:
        r.seats_contested == null ? null : Number(r.seats_contested),
      seats_won: num(r.seats_won),
      votes: num(r.votes),
      vote_share_pct: num(r.vote_share_pct),
    }));
    const total_seats = party_totals.reduce((s, p) => s + p.seats_won, 0);
    events.push({ event_id, party_totals, total_seats });
  }

  const sources: SourceRef[] = rows.sources
    .filter((s) => !!s.url_main)
    .map((s) => ({
      url: s.url_main ?? "",
      // Citation ledger (v2.0) does not carry fetch telemetry —
      // ``fetched_at`` is intentionally empty. See ADR-0032.
      fetched_at: "",
    }));

  return { state: state_code, events, sources };
}

function notPublishedSkeleton(state_code: string): ElectionSeatsTrendViewModel {
  return { state: state_code, events: [], sources: [] };
}

export async function loadElectionSeatsTrend(
  state_code: string,
  event_ids: string[],
): Promise<LoaderResult<ElectionSeatsTrendViewModel>> {
  if (event_ids.length === 0) {
    return {
      status: "partial",
      data: notPublishedSkeleton(state_code),
      reason: "not_published",
    };
  }
  try {
    const rows = await runQueries(state_code, event_ids);
    if (rows.parties.length === 0) {
      return {
        status: "partial",
        data: notPublishedSkeleton(state_code),
        reason: "not_published",
      };
    }
    return { status: "ok", data: assembleResult(state_code, rows) };
  } catch (err) {
    return {
      status: "failed",
      reason: describeFailure(err),
      retry: () => loadElectionSeatsTrend(state_code, event_ids),
    };
  }
}
