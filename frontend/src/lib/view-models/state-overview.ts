// Citizen view-model loader for the StateOverview route (PR-F / Phase 1.3b).
//
// Reads the canonical Parquet store via DuckDB-WASM (see lib/duckdb.ts) and
// assembles a state-hub view-model — party totals + state totals + sources —
// to replace the per-shard `result.summary.json` projection for the
// StateOverview surface. PR-G (Phase 1.3c) also routes Party.svelte's
// summary side here, plus migrated ElectionSeatsTrend, IndiaMap, and
// Settings onto their own dedicated view-model loaders; `fetchResultSummary`
// is now deleted. `fetchParties` survives for Party.svelte's
// recognition/alliance metadata until PR-H extends dim_parties.
//
// What is JOINed:
//   elections.observations  — numeric facts (party-* + state-* indicators)
//   elections.dim_parties   — party labels (short_name, full_name, eci_code)
//   taxonomy.sources        — provenance URLs + first_fetched_at
//
// Party JOIN key: entity_id is `IN-<state>-<event>-PARTY-<short_name>`, so
// `regexp_extract(entity_id, '-PARTY-(.+)$', 1) = dim_parties.short_name`.
// LEFT JOIN so parties without a dim row still render with their extracted
// short_name (a recognised gap in the current dim_parties seed).
//
// LoaderResult arms (mirror PR-E / constituency.ts):
//   ok       — JOIN produced 1+ party rows; full StateOverviewViewModel.
//   partial  — zero party rows for (state, event) — the cohort is not yet
//              ingested into the canonical store. Returns a skeleton +
//              reason="not_published" so the route can render an empty-state.
//   failed   — DuckDB-WASM / fetch / SQL error; `describeFailure` maps to
//              citizen-readable copy + a retry callable.

import {
  describeFailure,
  type LoaderResult,
} from "../loader-result";
import { query, registerTable } from "../duckdb";
import type { PartyTotals, SourceRef } from "../data";

// View-model shape. Distinct from the legacy `ResultSummary` (which other
// routes still consume): no per-AC `winners` map (StateAcMap and the margin
// histogram still pull that from results.sqlite via getDb), and `body` is
// elided — StateOverview never reads it. `party_totals` reuses the legacy
// `PartyTotals` shape so PartyBar / SeatDonut / the party directory render
// with zero prop changes.
export interface StateOverviewViewModel {
  election: string;
  state: string;
  total_seats: number;
  totals: {
    electors?: number;
    votes_polled?: number;
    turnout_pct?: number;
  } | null;
  party_totals: PartyTotals[];
  sources: SourceRef[];
}

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

interface PartyRow {
  short_name_key: string;
  short_name: string | null;
  full_name: string | null;
  eci_code: string | null;
  seats_contested: number | null;
  seats_won: number | null;
  votes: number | null;
  vote_share_pct: number | null;
}

interface StateScopeRow {
  indicator_id: string;
  value_numeric: number | null;
}

interface SourceJoinRow {
  url: string | null;
  first_fetched_at: string | null;
}

const num = (v: unknown): number => (v == null ? 0 : Number(v));
const numOrUndef = (v: unknown): number | undefined =>
  v == null ? undefined : Number(v);

async function runQueries(
  event: string,
  state_code: string,
): Promise<{
  parties: PartyRow[];
  stateScope: StateScopeRow[];
  sources: SourceJoinRow[];
}> {
  await Promise.all([
    registerTable("elections.observations"),
    registerTable("elections.dim_parties"),
    registerTable("taxonomy.sources"),
  ]);

  const evt = sqlString(event);
  const sc = sqlString(state_code);
  const partyPrefix = sqlString(`IN-${state_code}-${event}-PARTY-`);
  const statePrefix = sqlString(`IN-${state_code}-`);
  const stateEntity = sqlString(`IN-${state_code}-${event}`);

  // Pivot the four party-* indicators with MAX(CASE WHEN ...). LEFT JOIN to
  // dim_parties on the extracted short_name so unmatched parties still
  // render (e.g. dim_parties currently has no row for CPIM).
  const partySql = `
    SELECT
      regexp_extract(o.entity_id, '-PARTY-(.+)$', 1) AS short_name_key,
      dp.short_name     AS short_name,
      dp.full_name      AS full_name,
      dp.eci_code       AS eci_code,
      MAX(CASE WHEN o.indicator_id = 'party-contested-acs'  THEN o.value_numeric END) AS seats_contested,
      MAX(CASE WHEN o.indicator_id = 'party-seats-won'      THEN o.value_numeric END) AS seats_won,
      MAX(CASE WHEN o.indicator_id = 'party-votes-polled'   THEN o.value_numeric END) AS votes,
      MAX(CASE WHEN o.indicator_id = 'party-vote-share-pct' THEN o.value_numeric END) AS vote_share_pct
    FROM observations o
    LEFT JOIN dim_parties dp
      ON dp.short_name = regexp_extract(o.entity_id, '-PARTY-(.+)$', 1)
    WHERE o.entity_id LIKE ${partyPrefix} || '%'
      AND o.period_label = ${evt}
      AND o.indicator_id IN (
        'party-contested-acs',
        'party-seats-won',
        'party-votes-polled',
        'party-vote-share-pct'
      )
    GROUP BY 1, 2, 3, 4
  `;
  const parties = await query<PartyRow>(partySql);

  if (parties.length === 0) {
    return { parties, stateScope: [], sources: [] };
  }

  const stateScope = await query<StateScopeRow>(`
    SELECT indicator_id, value_numeric
    FROM observations
    WHERE entity_id = ${stateEntity}
      AND period_label = ${evt}
      AND indicator_id IN (
        'state-electors-total',
        'state-votes-polled',
        'state-turnout-pct'
      )
  `);

  const sources = await query<SourceJoinRow>(`
    SELECT DISTINCT s.url, s.first_fetched_at
    FROM observations o
    JOIN sources s ON s.source_id = o.source_id
    WHERE o.period_label = ${evt}
      AND o.entity_id LIKE ${statePrefix} || '%'
      AND s.url <> ''
    ORDER BY s.first_fetched_at
  `);

  // State variable referenced by the loader caller; suppress unused warning
  // when sc is not referenced after string composition.
  void sc;

  return { parties, stateScope, sources };
}

function assembleResult(
  event: string,
  state_code: string,
  rows: {
    parties: PartyRow[];
    stateScope: StateScopeRow[];
    sources: SourceJoinRow[];
  },
): StateOverviewViewModel {
  const scopeMap = new Map<string, StateScopeRow>();
  for (const r of rows.stateScope) scopeMap.set(r.indicator_id, r);
  const scopeNum = (id: string): number | undefined =>
    numOrUndef(scopeMap.get(id)?.value_numeric);

  // PartyTotals carries `party_eci_code: string | null` — dim_parties.eci_code
  // is currently null for every row in the canonical seed (a known gap), so
  // most parties surface with null here. PartyBar handles null gracefully.
  const party_totals: PartyTotals[] = rows.parties.map((r) => ({
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

  const sources: SourceRef[] = rows.sources
    .filter((s) => !!s.url)
    .map((s) => ({
      url: s.url ?? "",
      fetched_at: s.first_fetched_at ?? "",
    }));

  return {
    election: event,
    state: state_code,
    total_seats,
    totals: {
      electors: scopeNum("state-electors-total"),
      votes_polled: scopeNum("state-votes-polled"),
      turnout_pct: scopeNum("state-turnout-pct"),
    },
    party_totals,
    sources,
  };
}

function notPublishedSkeleton(
  event: string,
  state_code: string,
): StateOverviewViewModel {
  return {
    election: event,
    state: state_code,
    total_seats: 0,
    totals: null,
    party_totals: [],
    sources: [],
  };
}

export async function loadStateOverview(
  event: string,
  state_code: string,
): Promise<LoaderResult<StateOverviewViewModel>> {
  try {
    const rows = await runQueries(event, state_code);
    if (rows.parties.length === 0) {
      return {
        status: "partial",
        data: notPublishedSkeleton(event, state_code),
        reason: "not_published",
      };
    }
    return { status: "ok", data: assembleResult(event, state_code, rows) };
  } catch (err) {
    return {
      status: "failed",
      reason: describeFailure(err),
      retry: () => loadStateOverview(event, state_code),
    };
  }
}
