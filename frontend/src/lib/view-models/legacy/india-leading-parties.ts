// LEGACY (kept under view-models/legacy/ in PR-W5a, 2026-06-10).
//
// Kept here, not deleted, because IndiaMap.svelte is its sole live
// consumer AND the W2b generic `loadElectionResults({event, state?, eci_no?})`
// does NOT yet support the `Record<state, event>` multi-event scope this
// loader takes (one event per state on the home-page map, where the
// default event varies by state). Folding in is a future PR that either
// (a) adds a fourth scope shape `{events_by_state}` to the generic loader
// or (b) leaves this as a separate concern. See [frontend/src/AGENTS.md]
// section "View-model collapse" + the PR-W5a row in
// TODO/20260609-election-experience-overhaul-plan.md.
//
// ----- Original module header (kept verbatim) -----
//
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

import { describeFailure, type LoaderResult } from "../../loader-result";
import { query, registerCsvAsTable, registerCsvFile } from "../../duckdb";
import {
  ELECTION_RESULTS_COLUMNS_CLAUSE,
  electionResultsCsvUrl,
  electionResultsStateSlug,
} from "../../canonical/election-results-csv";
import {
  resolveEventIdentity,
  type ElectionEventsCatalogue,
} from "../../election-events";
import type { PartyTotals } from "../../data";

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
  // PR-SYM-6f3: project dim_parties.party_id + brand_colour_* through to
  // PartyTotals so IndiaMap.svelte can call getPartyColor(party_id, row)
  // off the existing dim_parties LEFT JOIN.
  party_id: string | null;
  brand_colour_hex: string | null;
  brand_colour_confidence: string | null;
  seats_contested: number | null;
  seats_won: number | null;
  votes: number | null;
  vote_share_pct: number | null;
}

const num = (v: unknown): number => (v == null ? 0 : Number(v));

async function runQueries(
  state_event_map: Record<string, string>,
  catalogue: ElectionEventsCatalogue | null,
): Promise<{ rows: PartyRow[]; displayByState: Record<string, string> }> {
  // X1a-fu2-D (2026-06-07): the elections.election_results parquet was
  // retired; one CSV per state now lives under
  // data/datapoints/electoral/. Build one UNION ALL branch per queried
  // (state, event) pair and JOIN dim_parties once at the outer SELECT.
  const entries = Object.entries(state_event_map);
  if (entries.length === 0) return { rows: [], displayByState: {} };

  // Register every per-state CSV the bulk query reads, plus dim_parties.
  const urls = entries.map(([state_code]) =>
    electionResultsCsvUrl(electionResultsStateSlug(state_code)),
  );
  await Promise.all([
    ...urls.map((u) => registerCsvFile(u)),
    registerCsvAsTable("elections.dim_parties"),
  ]);

  // Bridge the citizen event slug to the on-disk identity (W2a doctrine +
  // canonical/election-results-csv preamble): the canonical store filed
  // these rows under the ECI cohort token (period_label `AcGenNov2024`,
  // entity_id `IN-<state>-AcGenNov2024-PARTY-*`), NOT the citizen slug
  // `assembly-2024` that defaultEventForState returns. resolveEventIdentity
  // turns each token into the full on-disk period_label set (filtered with
  // IN, so it is phase-proof: matches today's cohort data via the alias and
  // a future slug re-key via the slug) plus the citizen slug for display.
  // catalogue == null (unit tests) resolves each token to itself.
  const displayByState: Record<string, string> = {};
  const branches = entries.map(([state_code, event_token]) => {
    const identity = resolveEventIdentity(catalogue, state_code, event_token);
    displayByState[state_code] = identity.event_id;
    const slug = electionResultsStateSlug(state_code);
    const csvLit = sqlString(electionResultsCsvUrl(slug));
    const stateLit = sqlString(state_code);
    const statePrefix = sqlString(`IN-${state_code}-`);
    const periodList = identity.period_labels.map(sqlString).join(", ");
    return `
      SELECT
        ${stateLit}    AS state_code,
        period_label   AS period_label,
        entity_id      AS entity_id,
        indicator_id   AS indicator_id,
        value_numeric  AS value_numeric
      FROM read_csv(${csvLit}, ${ELECTION_RESULTS_COLUMNS_CLAUSE}, header=true, auto_detect=false)
      WHERE entity_id LIKE ${statePrefix} || '%-PARTY-%'
        AND period_label IN (${periodList})
        AND indicator_id IN (
          'party-contested-acs',
          'party-seats-won',
          'party-votes-polled',
          'party-vote-share-pct'
        )
    `;
  });

  const sql = `
    WITH per_state AS (
      ${branches.join(" UNION ALL ")}
    )
    SELECT
      ps.state_code                                              AS state_code,
      ps.period_label                                            AS period_label,
      regexp_extract(ps.entity_id, '-PARTY-(.+)$', 1)            AS short_name_key,
      dp.short_name                                              AS short_name,
      dp.full_name                                               AS full_name,
      dp.eci_code                                                AS eci_code,
      dp.party_id                                                AS party_id,
      dp.brand_colour_hex                                        AS brand_colour_hex,
      dp.brand_colour_confidence                                 AS brand_colour_confidence,
      MAX(CASE WHEN ps.indicator_id = 'party-contested-acs'  THEN ps.value_numeric END) AS seats_contested,
      MAX(CASE WHEN ps.indicator_id = 'party-seats-won'      THEN ps.value_numeric END) AS seats_won,
      MAX(CASE WHEN ps.indicator_id = 'party-votes-polled'   THEN ps.value_numeric END) AS votes,
      MAX(CASE WHEN ps.indicator_id = 'party-vote-share-pct' THEN ps.value_numeric END) AS vote_share_pct
    FROM per_state ps
    LEFT JOIN dim_parties dp
      ON dp.short_name = regexp_extract(ps.entity_id, '-PARTY-(.+)$', 1)
    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
  `;
  const rows = await query<PartyRow>(sql);
  return { rows, displayByState };
}

function assembleResult(
  rows: PartyRow[],
  displayByState: Record<string, string>,
): IndiaLeadingPartiesViewModel {
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
      // PR-SYM-6f3: additive brand-identity fields from dim_parties. Null
      // when the LEFT JOIN missed (party not yet in canonical seed) so
      // IndiaMap's getPartyColor call falls through to the algorithmic tier.
      party_id: r.party_id ?? null,
      brand_colour_hex: r.brand_colour_hex ?? null,
      brand_colour_confidence:
        r.brand_colour_confidence === "high" ||
        r.brand_colour_confidence === "medium" ||
        r.brand_colour_confidence === "low"
          ? r.brand_colour_confidence
          : null,
      seats_contested:
        r.seats_contested == null ? null : Number(r.seats_contested),
      seats_won: num(r.seats_won),
      votes: num(r.votes),
      vote_share_pct: num(r.vote_share_pct),
    }));
    totals.sort((a, b) => b.seats_won - a.seats_won || b.votes - a.votes);
    per_state[state_code] = {
      // Citizen slug (assembly-2024) resolved from the catalogue, NOT the
      // on-disk cohort token (AcGenNov2024) the row's period_label carries -
      // cohort codes must never reach citizen display (schema display rule).
      event_id: displayByState[state_code] ?? arr[0].period_label,
      party_totals: totals,
    };
  }

  return { per_state };
}

/**
 * Load each state's leading parties for the home-page choropleth.
 *
 * `state_event_map` is keyed by ECI state code; the value is the citizen
 * event token (the slug `assembly-2024` from `defaultEventForState`, or an
 * explicit cohort token from a cohort-scoped consumer). `catalogue` is the
 * SSOT used to resolve that token to the on-disk `period_label` set the
 * canonical store actually filed the rows under (see runQueries). Passing
 * `null` (the default, used by unit tests) resolves each token to itself -
 * an exact-match pass-through.
 */
export async function loadIndiaLeadingParties(
  state_event_map: Record<string, string>,
  catalogue: ElectionEventsCatalogue | null = null,
): Promise<LoaderResult<IndiaLeadingPartiesViewModel>> {
  try {
    const { rows, displayByState } = await runQueries(state_event_map, catalogue);
    return { status: "ok", data: assembleResult(rows, displayByState) };
  } catch (err) {
    return {
      status: "failed",
      reason: describeFailure(err),
      retry: () => loadIndiaLeadingParties(state_event_map, catalogue),
    };
  }
}
