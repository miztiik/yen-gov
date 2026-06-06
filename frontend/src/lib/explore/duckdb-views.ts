// Per-(event, state) DuckDB views for the Data Explorer (F1.3b CSV cutover).
//
// Phase 1.6b: Explore.svelte moves off the legacy parquet store onto the
// canonical long-format CSV store, like every other citizen route. The
// documented preset SQL keeps working with minimal syntactic change.
// Citizens who hand-edit a preset still see the same column names the
// footer doc advertises (`parties`, `constituencies`, `candidates`,
// `party_totals`).
//
// Views are scoped to one (event, state) at a time; the page rebuilds them
// whenever the state slug changes. Registration of the underlying CSV
// files + Parquet `dim_parties` is idempotent (handled by
// `registerCsvFile` / `registerTable`), so the per-state cost is just
// the view DDL itself.
//
// Source tables (one of three):
//   - parties:        elections.dim_parties (CSV via registerCsvAsTable; X1a reader flip)
//   - constituencies: datasets/elections/assembly/state=*/election=*/summary.csv
//                     JOIN datasets/data/entities/electoral.csv (CSV)
//   - candidates:     datasets/elections/assembly/state=*/election=*/candidacies.csv
//                     JOIN electoral.csv + dim_parties (CSV)
//                     NOTA rows already live INLINE in candidacies.csv
//                     (writer at backend/yen_gov/canonical/reingest/
//                     assembly_results.py does NOT filter NOTA per the
//                     ADR-0023 canonical-event-row contract).
//   - party_totals:   per-party aggregation from candidacies.csv (one
//                     row per party in the state for the event).
//
// Critical per-row contract (F1 sub-plan section 22.4 #4): every
// `read_csv(...)` carries an explicit `columns={...}` map derived from
// `datasets/data/_schema/columns.json` via `csvColumnsClause`. No
// hand-typed column lists.
//
// Known regressions vs the pre-F1.3b parquet world (documented for X1a):
//   - `candidates.party_short_raw` lived on
//     `elections_candidacies.party_short_raw` (the upstream-verbatim ECI
//     short for sentinel-keyed rows). candidacies.csv does NOT carry
//     this column today; the COALESCE falls through to
//     `dim_parties.short_name` + then to the post-`parties.IN.`
//     substring of `party_id`. Citizen-visible behaviour is identical
//     for the 80.7% of rows resolved at the writer (F1.3a); the
//     long-tail UNK rows that previously rendered the raw upstream
//     short now render the canonical-id substring (`UNK`). Restoring
//     the raw short is an X1a or candidacies-schema-extension task.

import {
  getConnection,
  registerCsvAsTable,
  registerCsvFile,
} from "../duckdb";
import { DATA_BASE } from "../paths";
import { csvColumnsClause } from "../canonical/csv-columns";
import {
  assemblyCandidaciesPath,
  assemblySummaryPath,
  electoralEntitiesPath,
} from "../canonical/election-csv-paths";
import { electionStatePartition } from "../election-partitions";

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

/**
 * Register canonical sources (CSV files + dim_parties Parquet) and
 * create per-(event, state) convenience views. Safe to call repeatedly;
 * views use CREATE OR REPLACE.
 */
export async function buildExploreViews(
  event: string,
  state_code: string,
): Promise<void> {
  const candPath = assemblyCandidaciesPath(state_code, event);
  const sumPath = assemblySummaryPath(state_code, event);
  const electoralPath = electoralEntitiesPath();
  const candUrl = `${DATA_BASE}/${candPath.replace(/^datasets\//, "")}`;
  const sumUrl = `${DATA_BASE}/${sumPath.replace(/^datasets\//, "")}`;
  const electoralUrl = `${DATA_BASE}/${electoralPath.replace(/^datasets\//, "")}`;

  // Typed-read clauses + registrations in parallel. dim_parties flipped
  // to CSV via registerCsvAsTable in X1a (parties.csv); the seam projects
  // the legacy parquet column shape (eci_code, short_name, full_name,
  // recognition) so the `parties` view below is unchanged. ZERO
  // registrations of election_results / dim_acs / dim_persons /
  // elections_candidacies - the per-(state, year) CSV files cover
  // every observation Explore presets reach for.
  const [candClause, sumClause, electoralClause] = await Promise.all([
    csvColumnsClause(candPath),
    csvColumnsClause(sumPath),
    csvColumnsClause(electoralPath),
    registerCsvFile(candUrl),
    registerCsvFile(sumUrl),
    registerCsvFile(electoralUrl),
    registerCsvAsTable("elections.dim_parties"),
  ]);

  const slug = electionStatePartition(state_code);
  const stateLit = sqlString(slug);
  const conn = await getConnection();

  // parties: global dim, exposed verbatim - handy for "what's the full
  // name of this party_short?" probes regardless of state.
  await conn.query(`
    CREATE OR REPLACE VIEW parties AS
    SELECT party_id, eci_code, short_name, full_name, recognition
    FROM dim_parties
  `);

  // constituencies: one row per AC in this state, totals + name from
  // summary.csv + electoral.csv. Same column shape as the legacy
  // parquet view (ac_eci_no / name / votes_polled / total_electors /
  // turnout_pct) so documented presets keep working.
  //
  // votes_polled is required-non-null on summary.csv; electors +
  // turnout_pct are required-non-null too per the columns.json
  // contract for the assembly summary file_class.
  await conn.query(`
    CREATE OR REPLACE VIEW constituencies AS
    SELECT
      e.eci_no                        AS ac_eci_no,
      e.name                          AS name,
      CAST(s.votes_polled AS BIGINT)  AS votes_polled,
      CAST(s.electors     AS BIGINT)  AS total_electors,
      s.turnout_pct                   AS turnout_pct
    FROM read_csv('${sumUrl}', ${sumClause}) s
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = s.entity_id
     AND e.entity_kind = 'ac'
    WHERE e.state = ${stateLit}
    ORDER BY e.eci_no
  `);

  // candidates: per-candidacy rows for this (event, state) including
  // NOTA (which lives INLINE in candidacies.csv with
  // candidate_name='NOTA' and party_id=NULL). is_winner / is_nota stay
  // as INTEGER 0/1 to preserve legacy preset SQL like
  // `WHERE is_nota = 1` and `WHERE is_winner = 1`.
  //
  // party_short fallback chain mirrors psephlab/canonical-loaders.ts
  // (F1.3a): prefer dim_parties.short_name, fall back to substring of
  // canonical party_id (after the `parties.IN.` prefix), fall back to
  // the empty string -> 'IND' / 'NOTA' in renderer code.
  await conn.query(`
    CREATE OR REPLACE VIEW candidates AS
    SELECT
      e.eci_no                                       AS ac_eci_no,
      ec.position                                    AS rank,
      ec.candidate_name                              AS name,
      dp.eci_code                                    AS party_eci_code,
      CASE
        WHEN UPPER(ec.candidate_name) = 'NOTA' THEN 'NOTA'
        ELSE COALESCE(
          dp.short_name,
          CASE WHEN ec.party_id LIKE 'parties.IN.%'
               THEN substring(ec.party_id, length('parties.IN.') + 1)
               ELSE ec.party_id END,
          ''
        )
      END                                            AS party_short,
      CAST(ec.votes AS BIGINT)                       AS votes,
      ec.vote_share_pct                              AS vote_share_pct,
      CASE WHEN ec.position = 1 AND UPPER(ec.candidate_name) <> 'NOTA' THEN 1 ELSE 0 END AS is_winner,
      CASE WHEN UPPER(ec.candidate_name) = 'NOTA' THEN 1 ELSE 0 END AS is_nota
    FROM read_csv('${candUrl}', ${candClause}) ec
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = ec.entity_id
     AND e.entity_kind = 'ac'
    LEFT JOIN dim_parties dp ON dp.party_id = ec.party_id
    WHERE e.state = ${stateLit}
    ORDER BY e.eci_no, ec.position
  `);

  // party_totals: per-party aggregation across this (event, state).
  // Computed from candidacies.csv:
  //   - seats_won   = COUNT(DISTINCT entity_id WHERE position = 1
  //                                          AND candidate_name <> 'NOTA')
  //   - votes       = SUM(votes)
  //   - vote_share_pct = SUM(votes) / state-total-votes * 100
  // Mirrors the canonical-store party-totals indicator the legacy
  // parquet view pivoted out of `election_results`.
  await conn.query(`
    CREATE OR REPLACE VIEW party_totals AS
    WITH state_total AS (
      SELECT SUM(votes) AS total
      FROM read_csv('${candUrl}', ${candClause}) ec
      JOIN read_csv('${electoralUrl}', ${electoralClause}) e
        ON e.entity_id = ec.entity_id
       AND e.entity_kind = 'ac'
      WHERE e.state = ${stateLit}
    )
    SELECT
      CASE
        WHEN UPPER(ec.candidate_name) = 'NOTA' THEN 'NOTA'
        ELSE COALESCE(
          dp.short_name,
          CASE WHEN ec.party_id LIKE 'parties.IN.%'
               THEN substring(ec.party_id, length('parties.IN.') + 1)
               ELSE ec.party_id END,
          'IND'
        )
      END                                                       AS party_short,
      CAST(SUM(CASE WHEN ec.position = 1 AND UPPER(ec.candidate_name) <> 'NOTA' THEN 1 ELSE 0 END) AS INTEGER) AS seats_won,
      CAST(SUM(ec.votes) AS BIGINT)                             AS votes,
      ROUND(SUM(ec.votes) * 100.0 / NULLIF(MAX(st.total), 0), 2) AS vote_share_pct
    FROM read_csv('${candUrl}', ${candClause}) ec
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = ec.entity_id
     AND e.entity_kind = 'ac'
    LEFT JOIN dim_parties dp ON dp.party_id = ec.party_id
    CROSS JOIN state_total st
    WHERE e.state = ${stateLit}
    GROUP BY 1
    ORDER BY seats_won DESC, votes DESC
  `);
}
