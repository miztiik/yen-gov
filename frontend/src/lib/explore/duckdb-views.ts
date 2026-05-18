// Per-(event, state) DuckDB views for the Data Explorer.
//
// Phase 1.6b: Explore.svelte moves off `getDb` / `results.sqlite` onto the
// canonical Parquet store, like every other citizen route. The old SQLite
// schema (`parties`, `constituencies`, `candidates`, `party_totals`) is
// reconstructed as DuckDB-WASM views so the documented preset SQL keeps
// working with minimal syntactic change. Citizens who hand-edit a preset
// still see the same column names the footer doc advertises.
//
// Views are scoped to one (event, state) at a time; the page rebuilds them
// whenever the state slug changes. Registration of the underlying canonical
// tables is idempotent (handled by `registerTable`), so the per-state cost
// is just the view DDL itself.
//
// NOTA handling: the canonical store keeps NOTA at AC scope only
// (`ac-nota-votes`, `ac-nota-pct`) — there is no per-candidate NOTA row in
// `dim_candidates`. The `candidates` view synthesises one NOTA row per AC
// from those AC-scope observations so legacy presets (`WHERE is_nota = 1`)
// continue to work.

import { getConnection, registerTable } from "../duckdb";

const REQUIRED_TABLES = [
  "elections.election_results",
  "elections.dim_acs",
  "elections.dim_candidates",
  "elections.dim_parties",
] as const;

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

/**
 * Register canonical tables and create per-(event, state) convenience views.
 * Safe to call repeatedly; views use CREATE OR REPLACE.
 */
export async function buildExploreViews(
  event: string,
  state_code: string,
): Promise<void> {
  await Promise.all(REQUIRED_TABLES.map((t) => registerTable(t)));
  const conn = await getConnection();
  const evt = sqlString(event);
  const sc = sqlString(state_code);

  // parties: global dim, exposed verbatim — handy for "what's the full name
  // of this party_short?" probes regardless of state.
  await conn.query(`
    CREATE OR REPLACE VIEW parties AS
    SELECT party_id, eci_code, short_name, full_name, recognition
    FROM dim_parties
  `);

  // constituencies: one row per AC in this state, with AC-scope totals
  // pivoted out of the fact-table rows.
  await conn.query(`
    CREATE OR REPLACE VIEW constituencies AS
    SELECT
      da.eci_no AS ac_eci_no,
      da.name   AS name,
      CAST(MAX(CASE WHEN o.indicator_id = 'ac-votes-polled'   THEN o.value_numeric END) AS BIGINT)  AS votes_polled,
      CAST(MAX(CASE WHEN o.indicator_id = 'ac-total-electors' THEN o.value_numeric END) AS BIGINT)  AS total_electors,
           MAX(CASE WHEN o.indicator_id = 'ac-turnout-pct'    THEN o.value_numeric END)             AS turnout_pct
    FROM dim_acs da
    LEFT JOIN election_results o
      ON o.entity_id = da.ac_id
     AND o.period_label = ${evt}
    WHERE da.state_code = ${sc}
    GROUP BY da.eci_no, da.name
  `);

  // candidates: per-candidate rows for this (event, state), UNION ALL with
  // synthetic NOTA rows (one per AC with a non-null ac-nota-votes value).
  // is_winner / is_nota stay as INTEGER 0/1 to preserve legacy preset SQL.
  await conn.query(`
    CREATE OR REPLACE VIEW candidates AS
    WITH cand_obs AS (
      SELECT
        o.entity_id AS candidate_id,
        MAX(CASE WHEN o.indicator_id = 'candidate-votes-polled'   THEN o.value_numeric END) AS votes,
        MAX(CASE WHEN o.indicator_id = 'candidate-vote-share-pct' THEN o.value_numeric END) AS vote_share_pct
      FROM election_results o
      WHERE o.period_label = ${evt}
        AND o.indicator_id IN ('candidate-votes-polled', 'candidate-vote-share-pct')
      GROUP BY o.entity_id
    ),
    ac_winner AS (
      SELECT entity_id AS ac_id, value_text AS winner_candidate_id
      FROM election_results
      WHERE indicator_id = 'ac-winner-candidate-id'
        AND period_label = ${evt}
    )
    SELECT
      da.eci_no                                       AS ac_eci_no,
      dc.rank                                         AS rank,
      dc.name                                         AS name,
      dp.eci_code                                     AS party_eci_code,
      dp.short_name                                   AS party_short,
      CAST(co.votes AS BIGINT)                        AS votes,
      co.vote_share_pct                               AS vote_share_pct,
      CASE WHEN aw.winner_candidate_id = dc.candidate_id THEN 1 ELSE 0 END AS is_winner,
      0                                               AS is_nota
    FROM dim_candidates dc
    JOIN dim_acs da       ON da.ac_id = dc.ac_id
    LEFT JOIN dim_parties dp ON dp.party_id = dc.party_id
    LEFT JOIN cand_obs co   ON co.candidate_id = dc.candidate_id
    LEFT JOIN ac_winner aw  ON aw.ac_id = dc.ac_id
    WHERE dc.period_label = ${evt}
      AND da.state_code   = ${sc}

    UNION ALL

    SELECT
      da.eci_no                                                                              AS ac_eci_no,
      NULL::INTEGER                                                                          AS rank,
      'NOTA'                                                                                 AS name,
      NULL::VARCHAR                                                                          AS party_eci_code,
      'NOTA'                                                                                 AS party_short,
      CAST(MAX(CASE WHEN o.indicator_id = 'ac-nota-votes' THEN o.value_numeric END) AS BIGINT) AS votes,
           MAX(CASE WHEN o.indicator_id = 'ac-nota-pct'   THEN o.value_numeric END)            AS vote_share_pct,
      0                                                                                      AS is_winner,
      1                                                                                      AS is_nota
    FROM dim_acs da
    JOIN election_results o
      ON o.entity_id = da.ac_id
     AND o.period_label = ${evt}
    WHERE da.state_code = ${sc}
      AND o.indicator_id IN ('ac-nota-votes', 'ac-nota-pct')
    GROUP BY da.eci_no
    HAVING MAX(CASE WHEN o.indicator_id = 'ac-nota-votes' THEN o.value_numeric END) IS NOT NULL
  `);

  // party_totals: from materialised party-* indicators, keyed to this
  // (event, state). Entity pattern: IN-<state>-<event>-PARTY-<short_name>.
  const partyPrefix = sqlString(`IN-${state_code}-${event}-PARTY-`);
  await conn.query(`
    CREATE OR REPLACE VIEW party_totals AS
    SELECT
      regexp_extract(o.entity_id, '-PARTY-(.+)$', 1)                                                      AS party_short,
      CAST(MAX(CASE WHEN o.indicator_id = 'party-seats-won'    THEN o.value_numeric END) AS INTEGER)       AS seats_won,
      CAST(MAX(CASE WHEN o.indicator_id = 'party-votes-polled' THEN o.value_numeric END) AS BIGINT)        AS votes,
           MAX(CASE WHEN o.indicator_id = 'party-vote-share-pct' THEN o.value_numeric END)                 AS vote_share_pct
    FROM election_results o
    WHERE o.entity_id LIKE ${partyPrefix} || '%'
      AND o.period_label = ${evt}
      AND o.indicator_id IN ('party-seats-won', 'party-votes-polled', 'party-vote-share-pct')
    GROUP BY 1
  `);
}
