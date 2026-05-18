// Citizen view-model loader for the IndiaMap leading-party choropleth
// (PR-G / Phase 1.3c).
//
// One bulk SQL fans the four party-* indicators across every (state, default
// event) pair on the home-page map. Replaces ~36 per-state fetchResultSummary
// HTTP requests with one DuckDB-WASM JOIN.
//
// Output is keyed by state_code and carries party_totals sorted by
// seats_won desc (with votes as tiebreak) so consumers can read top-N
// directly without re-sorting. Tooltip code reads top 3; map fills read
// top 1.
//
// Missing state in input map → not queried. Empty result for a queried
// state → that state absent from per_state (not an error — same shape as
// fetchResultSummary 404-tolerance on the old path). Any thrown error in
// the bulk query → failed arm.

import { describeFailure, type LoaderResult } from "../loader-result";
import { query, registerTable } from "../duckdb";
import type { PartyTotals } from "../data";

export interface IndiaLeadingPartiesEntry {
  event_id: string;
  party_totals: PartyTotals[];
}

export interface IndiaLeadingPartiesViewModel {
  per_state: Record<string, IndiaLeadingPartiesEntry>;
}

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

interface PartyRow {
  state_code: string;
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

const num = (v: unknown): number => (v == null ? 0 : Number(v));

async function runQueries(
  state_event_map: Record<string, string>,
): Promise<PartyRow[]> {
  await Promise.all([
    registerTable("elections.observations"),
    registerTable("elections.dim_parties"),
  ]);

  // (state, event) pairs → an OR-list of LIKE prefixes. Each prefix is
  // narrow (IN-<state>-<event>-PARTY-) so the planner can skip irrelevant
  // row groups efficiently.
  const clauses: string[] = [];
  for (const [state_code, event_id] of Object.entries(state_event_map)) {
    const prefix = sqlString(`IN-${state_code}-${event_id}-PARTY-`);
    clauses.push(`o.entity_id LIKE ${prefix} || '%'`);
  }
  if (clauses.length === 0) return [];

  const sql = `
    SELECT
      regexp_extract(o.entity_id, 'IN-([SU][0-9]+)-', 1)          AS state_code,
      o.period_label                                              AS period_label,
      regexp_extract(o.entity_id, '-PARTY-(.+)$', 1)              AS short_name_key,
      dp.short_name                                               AS short_name,
      dp.full_name                                                AS full_name,
      dp.eci_code                                                 AS eci_code,
      MAX(CASE WHEN o.indicator_id = 'party-contested-acs'  THEN o.value_numeric END) AS seats_contested,
      MAX(CASE WHEN o.indicator_id = 'party-seats-won'      THEN o.value_numeric END) AS seats_won,
      MAX(CASE WHEN o.indicator_id = 'party-votes-polled'   THEN o.value_numeric END) AS votes,
      MAX(CASE WHEN o.indicator_id = 'party-vote-share-pct' THEN o.value_numeric END) AS vote_share_pct
    FROM observations o
    LEFT JOIN dim_parties dp
      ON dp.short_name = regexp_extract(o.entity_id, '-PARTY-(.+)$', 1)
    WHERE (${clauses.join(" OR ")})
      AND o.indicator_id IN (
        'party-contested-acs',
        'party-seats-won',
        'party-votes-polled',
        'party-vote-share-pct'
      )
    GROUP BY 1, 2, 3, 4, 5, 6
  `;
  return query<PartyRow>(sql);
}

function assembleResult(rows: PartyRow[]): IndiaLeadingPartiesViewModel {
  const grouped = new Map<string, PartyRow[]>();
  for (const r of rows) {
    const arr = grouped.get(r.state_code) ?? [];
    arr.push(r);
    grouped.set(r.state_code, arr);
  }

  const per_state: Record<string, IndiaLeadingPartiesEntry> = {};
  for (const [state_code, arr] of grouped) {
    const totals: PartyTotals[] = arr.map((r) => ({
      party_eci_code: r.eci_code ?? null,
      party_short: r.short_name ?? r.short_name_key,
      party_full: r.full_name ?? null,
      seats_contested:
        r.seats_contested == null ? null : Number(r.seats_contested),
      seats_won: num(r.seats_won),
      votes: num(r.votes),
      vote_share_pct: num(r.vote_share_pct),
    }));
    totals.sort((a, b) => b.seats_won - a.seats_won || b.votes - a.votes);
    per_state[state_code] = {
      event_id: arr[0].period_label,
      party_totals: totals,
    };
  }

  return { per_state };
}

export async function loadIndiaLeadingParties(
  state_event_map: Record<string, string>,
): Promise<LoaderResult<IndiaLeadingPartiesViewModel>> {
  try {
    const rows = await runQueries(state_event_map);
    return { status: "ok", data: assembleResult(rows) };
  } catch (err) {
    return {
      status: "failed",
      reason: describeFailure(err),
      retry: () => loadIndiaLeadingParties(state_event_map),
    };
  }
}
