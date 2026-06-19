// Hand-authored concept -> query-template registry (F1.3b CSV cutover).
//
// Each entry maps a `ConceptId` (the closed enum in
// `contracts/insight-intent.ts`) to:
//   - the required filter fields the compiler will demand
//   - an ASYNC SQL builder that returns the main + provenance query
//   - an AnswerViewHints object describing the rendered table
//
// Per plan-doc §17 D-04: this file is HAND-AUTHORED and bounded. Adding
// a new concept is an explicit, reviewable PR change here + an enum
// addition in `contracts/insight-intent.ts`. No automation, no
// LLM-generated SQL.
//
// F1.3b: the 4 templates now read the per-(state, year) long-format
// CSV files via DuckDB-WASM `read_csv(<url>, columns={...})` instead of
// the legacy `election_results` / `dim_acs` / `elections_candidacies` /
// `dim_persons` Parquet pivot. `dim_parties` + `taxonomy.sources` stay
// on Parquet until X1a (the atomic reader flip).
//
// Critical per-row contract (F1 sub-plan section 22.4 #4): every
// `read_csv(...)` call carries an explicit `columns={...}` map derived
// from `datasets/data/_schema/columns.json` via `csvColumnsClause`. No
// hand-typed column lists. `build(...)` is ASYNC to await the
// columns-map fetch (cached per session by `lib/canonical/csv-columns.ts`).
//
// What the 4 concepts read after F1.3b:
//   - party_totals:        candidacies.csv + electoral.csv + dim_parties (PQ)
//   - closest_contests:    summary.csv + electoral.csv
//   - constituency_result: candidacies.csv + electoral.csv + dim_parties (PQ)
//   - turnout_extremes:    summary.csv + electoral.csv
// Every provenance SQL JOINs the relevant CSV `source_id` column ->
// taxonomy.sources (PQ).

import type { InsightIntent } from "./contracts/insight-intent";
import type { ConceptId } from "./contracts/insight-intent";
import type {
  AnswerViewHints,
  DuckDBPlan,
  ColumnFormat,
} from "./types";
import { DATA_BASE } from "../paths";
import { csvColumnsClause } from "../canonical/csv-columns";
import {
  assemblyCandidaciesPath,
  assemblySummaryPath,
  electoralEntitiesPath,
  eventYear,
} from "../canonical/election-csv-paths";
import { withElectionReadOpts } from "../canonical/election-read-opts";

// ---------- SQL helpers ----------------------------------------------------

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

interface ResolvedFilters {
  state_partition_id: string;
  period_label: string;
  ac_no?: number;
  party_short_code?: string;
  limit: number;
}

/**
 * Per-call CSV path bundle. Computed once per build, then spliced into
 * the main + provenance SQL strings. Carries the registration URLs the
 * executor will pass to `registerCsvFile`.
 */
interface CsvBundle {
  candPath: string;
  sumPath: string;
  electoralPath: string;
  candUrl: string;
  sumUrl: string;
  electoralUrl: string;
  candClause: string;
  sumClause: string;
  electoralClause: string;
}

async function buildCsvBundle(
  state_partition_id: string,
  period_label: string,
): Promise<CsvBundle> {
  // The InsightIntent CDM emits LGD slugs as state_partition_id. The
  // per-(state, year) path helpers take the ECI state code in their
  // public signature; pass the slug directly because
  // `electionStatePartition(slug)` falls through to `slug.toLowerCase()`
  // when the slug is already in LGD form (the slug IS the partition).
  const candPath = assemblyCandidaciesPath(
    state_partition_id,
    period_label,
  );
  const sumPath = assemblySummaryPath(state_partition_id, period_label);
  const electoralPath = electoralEntitiesPath();
  const candUrl = `${DATA_BASE}/${candPath.replace(/^datasets\//, "")}`;
  const sumUrl = `${DATA_BASE}/${sumPath.replace(/^datasets\//, "")}`;
  const electoralUrl = `${DATA_BASE}/${electoralPath.replace(/^datasets\//, "")}`;
  const [candClause, sumClause, electoralClause] = await Promise.all([
    csvColumnsClause(candPath),
    csvColumnsClause(sumPath),
    csvColumnsClause(electoralPath),
  ]).then(([candCols, sumCols, electoralCols]) => [
    withElectionReadOpts(candCols),
    withElectionReadOpts(sumCols),
    withElectionReadOpts(electoralCols),
  ]);
  return {
    candPath,
    sumPath,
    electoralPath,
    candUrl,
    sumUrl,
    electoralUrl,
    candClause,
    sumClause,
    electoralClause,
  };
}

// ---------- Concept handlers ----------------------------------------------

interface ConceptHandler {
  readonly required_filters: readonly (keyof InsightIntent["filters"])[];
  readonly default_limit: number;
  build(intent: InsightIntent): Promise<DuckDBPlan>;
}

const PARTY_TOTALS: ConceptHandler = {
  required_filters: ["state_partition_id", "period_label"],
  default_limit: 10,
  async build(intent) {
    const f = requireFilters(intent, PARTY_TOTALS, 10);
    // Touch eventYear so a malformed period_label fails loud here, not
    // inside the embedded read_csv path; the value itself is implicit
    // in the assemblyCandidaciesPath builder.
    eventYear(f.period_label);
    const bundle = await buildCsvBundle(
      f.state_partition_id,
      f.period_label,
    );
    const stateLit = sqlString(f.state_partition_id);

    // Per-party aggregation from candidacies.csv: SUM(votes) per
    // party_short, COUNT(distinct ac where position=1) per party_short,
    // vote-share % via cross-join to the state-total votes.
    //
    // party_short fallback chain mirrors psephlab/canonical-loaders.ts
    // (F1.3a): prefer dim_parties.short_name, fall back to substring
    // of canonical party_id (after the `parties.IN.` prefix), fall
    // back to 'IND'. NOTA collapses to its own party_short bucket.
    const mainSql = `
      WITH state_total AS (
        SELECT SUM(ec.votes) AS total
        FROM read_csv('${bundle.candUrl}', ${bundle.candClause}) ec
        JOIN read_csv('${bundle.electoralUrl}', ${bundle.electoralClause}) e
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
        END                                                                                                  AS party_short,
        CAST(SUM(CASE WHEN ec.position = 1 AND UPPER(ec.candidate_name) <> 'NOTA' THEN 1 ELSE 0 END) AS INTEGER) AS seats_won,
        CAST(SUM(ec.votes) AS BIGINT)                                                                         AS votes,
        ROUND(SUM(ec.votes) * 100.0 / NULLIF(MAX(st.total), 0), 2)                                            AS vote_share_pct
      FROM read_csv('${bundle.candUrl}', ${bundle.candClause}) ec
      JOIN read_csv('${bundle.electoralUrl}', ${bundle.electoralClause}) e
        ON e.entity_id = ec.entity_id
       AND e.entity_kind = 'ac'
      LEFT JOIN dim_parties dp ON dp.party_id = ec.party_id
      CROSS JOIN state_total st
      WHERE e.state = ${stateLit}
      GROUP BY 1
      HAVING seats_won IS NOT NULL
      ORDER BY seats_won DESC NULLS LAST, votes DESC NULLS LAST
      LIMIT ${f.limit}
    `;
    const provenanceSql = `
      SELECT DISTINCT
        s.source_id, s.producer, s.title, s.vintage, s.license,
        s.confidence_tier, s.is_issuing_authority, s.verification_method,
        s.url_main, s.citation_full, s.notes
      FROM read_csv('${bundle.candUrl}', ${bundle.candClause}) ec
      JOIN read_csv('${bundle.electoralUrl}', ${bundle.electoralClause}) e
        ON e.entity_id = ec.entity_id
       AND e.entity_kind = 'ac'
      JOIN sources s ON s.source_id = ec.source_id
      WHERE e.state = ${stateLit}
      ORDER BY s.source_id
    `;
    const hints: AnswerViewHints = {
      question: intent.question,
      column_order: ["party_short", "seats_won", "votes", "vote_share_pct"],
      column_labels: {
        party_short: "Party",
        seats_won: "Seats won",
        votes: "Votes",
        vote_share_pct: "Vote share",
      },
      column_formats: {
        party_short: "text" as ColumnFormat,
        seats_won: "integer" as ColumnFormat,
        votes: "thousands" as ColumnFormat,
        vote_share_pct: "percentage" as ColumnFormat,
      },
    };
    return {
      concept_id: intent.concept_id,
      slice_registrations: [],
      table_registrations: [
        { table_id: "elections.dim_parties", view_name: "dim_parties" },
        { table_id: "taxonomy.sources", view_name: "sources" },
      ],
      csv_registrations: [
        { url: bundle.candUrl },
        { url: bundle.electoralUrl },
      ],
      main_sql: mainSql.trim(),
      provenance_sql: provenanceSql.trim(),
      view_hints: hints,
    };
  },
};

const CLOSEST_CONTESTS: ConceptHandler = {
  required_filters: ["state_partition_id", "period_label"],
  default_limit: 10,
  async build(intent) {
    const f = requireFilters(intent, CLOSEST_CONTESTS, 10);
    eventYear(f.period_label);
    const bundle = await buildCsvBundle(
      f.state_partition_id,
      f.period_label,
    );
    const stateLit = sqlString(f.state_partition_id);

    // Per-AC margin (winner share - runner-up share, expressed as %
    // points). summary.csv carries `margin_pct` published per-AC; no
    // candidate-level computation needed. Filter out NULLs to keep
    // the ORDER BY meaningful.
    const mainSql = `
      SELECT
        e.eci_no                        AS ac_no,
        e.name                          AS ac_name,
        s.margin_pct                    AS margin_pp,
        CAST(s.votes_polled AS BIGINT)  AS votes_polled
      FROM read_csv('${bundle.sumUrl}', ${bundle.sumClause}) s
      JOIN read_csv('${bundle.electoralUrl}', ${bundle.electoralClause}) e
        ON e.entity_id = s.entity_id
       AND e.entity_kind = 'ac'
      WHERE e.state = ${stateLit}
        AND s.margin_pct IS NOT NULL
      ORDER BY s.margin_pct ASC
      LIMIT ${f.limit}
    `;
    const provenanceSql = `
      SELECT DISTINCT
        s2.source_id, s2.producer, s2.title, s2.vintage, s2.license,
        s2.confidence_tier, s2.is_issuing_authority, s2.verification_method,
        s2.url_main, s2.citation_full, s2.notes
      FROM read_csv('${bundle.sumUrl}', ${bundle.sumClause}) s
      JOIN read_csv('${bundle.electoralUrl}', ${bundle.electoralClause}) e
        ON e.entity_id = s.entity_id
       AND e.entity_kind = 'ac'
      JOIN sources s2 ON s2.source_id = s.source_id
      WHERE e.state = ${stateLit}
      ORDER BY s2.source_id
    `;
    const hints: AnswerViewHints = {
      question: intent.question,
      column_order: ["ac_no", "ac_name", "margin_pp", "votes_polled"],
      column_labels: {
        ac_no: "AC #",
        ac_name: "Constituency",
        margin_pp: "Margin (pp)",
        votes_polled: "Votes polled",
      },
      column_formats: {
        ac_no: "integer" as ColumnFormat,
        ac_name: "text" as ColumnFormat,
        margin_pp: "percentage" as ColumnFormat,
        votes_polled: "thousands" as ColumnFormat,
      },
    };
    return {
      concept_id: intent.concept_id,
      slice_registrations: [],
      table_registrations: [
        { table_id: "taxonomy.sources", view_name: "sources" },
      ],
      csv_registrations: [
        { url: bundle.sumUrl },
        { url: bundle.electoralUrl },
      ],
      main_sql: mainSql.trim(),
      provenance_sql: provenanceSql.trim(),
      view_hints: hints,
    };
  },
};

const CONSTITUENCY_RESULT: ConceptHandler = {
  required_filters: ["state_partition_id", "period_label", "ac_no"],
  default_limit: 7,
  async build(intent) {
    const f = requireFilters(intent, CONSTITUENCY_RESULT, 7);
    if (f.ac_no == null) {
      throw new Error(
        "compile: constituency_result requires filters.ac_no",
      );
    }
    eventYear(f.period_label);
    const bundle = await buildCsvBundle(
      f.state_partition_id,
      f.period_label,
    );
    const stateLit = sqlString(f.state_partition_id);

    // Top-N contestants by vote share for the named AC. NOTA filtered
    // out to match the legacy elections_candidacies parquet contract
    // (which did not carry NOTA rows); explore/duckdb-views surfaces
    // NOTA inline because that is the legacy preset contract for the
    // Explore page, but the yenask constituency_result template stays
    // contestants-only.
    //
    // party_short fallback chain mirrors PARTY_TOTALS.
    const mainSql = `
      SELECT
        ec.position                                                          AS rank,
        ec.candidate_name                                                    AS candidate_name,
        COALESCE(
          dp.short_name,
          CASE WHEN ec.party_id LIKE 'parties.IN.%'
               THEN substring(ec.party_id, length('parties.IN.') + 1)
               ELSE ec.party_id END,
          'IND'
        )                                                                    AS party_short,
        CAST(ec.votes AS BIGINT)                                             AS votes,
        ec.vote_share_pct                                                    AS vote_share_pct
      FROM read_csv('${bundle.candUrl}', ${bundle.candClause}) ec
      JOIN read_csv('${bundle.electoralUrl}', ${bundle.electoralClause}) e
        ON e.entity_id = ec.entity_id
       AND e.entity_kind = 'ac'
      LEFT JOIN dim_parties dp ON dp.party_id = ec.party_id
      WHERE e.state = ${stateLit}
        AND e.eci_no = ${f.ac_no}
        AND UPPER(ec.candidate_name) <> 'NOTA'
      ORDER BY ec.vote_share_pct DESC NULLS LAST
      LIMIT ${f.limit}
    `;
    const provenanceSql = `
      SELECT DISTINCT
        s.source_id, s.producer, s.title, s.vintage, s.license,
        s.confidence_tier, s.is_issuing_authority, s.verification_method,
        s.url_main, s.citation_full, s.notes
      FROM read_csv('${bundle.candUrl}', ${bundle.candClause}) ec
      JOIN read_csv('${bundle.electoralUrl}', ${bundle.electoralClause}) e
        ON e.entity_id = ec.entity_id
       AND e.entity_kind = 'ac'
      JOIN sources s ON s.source_id = ec.source_id
      WHERE e.state = ${stateLit}
        AND e.eci_no = ${f.ac_no}
      ORDER BY s.source_id
    `;
    const hints: AnswerViewHints = {
      question: intent.question,
      column_order: ["rank", "candidate_name", "party_short", "votes", "vote_share_pct"],
      column_labels: {
        rank: "Rank",
        candidate_name: "Candidate",
        party_short: "Party",
        votes: "Votes",
        vote_share_pct: "Vote share",
      },
      column_formats: {
        rank: "integer" as ColumnFormat,
        candidate_name: "text" as ColumnFormat,
        party_short: "text" as ColumnFormat,
        votes: "thousands" as ColumnFormat,
        vote_share_pct: "percentage" as ColumnFormat,
      },
    };
    return {
      concept_id: intent.concept_id,
      slice_registrations: [],
      table_registrations: [
        { table_id: "elections.dim_parties", view_name: "dim_parties" },
        { table_id: "taxonomy.sources", view_name: "sources" },
      ],
      csv_registrations: [
        { url: bundle.candUrl },
        { url: bundle.electoralUrl },
      ],
      main_sql: mainSql.trim(),
      provenance_sql: provenanceSql.trim(),
      view_hints: hints,
    };
  },
};

const TURNOUT_EXTREMES: ConceptHandler = {
  required_filters: ["state_partition_id", "period_label"],
  default_limit: 10,
  async build(intent) {
    const f = requireFilters(intent, TURNOUT_EXTREMES, 10);
    eventYear(f.period_label);
    const bundle = await buildCsvBundle(
      f.state_partition_id,
      f.period_label,
    );
    const stateLit = sqlString(f.state_partition_id);

    // Per-AC turnout from summary.csv; interleave top-N + bottom-N
    // into a single ordered table the renderer renders as two bands.
    const mainSql = `
      WITH ranked AS (
        SELECT
          e.eci_no       AS ac_no,
          e.name         AS ac_name,
          s.turnout_pct  AS turnout_pct
        FROM read_csv('${bundle.sumUrl}', ${bundle.sumClause}) s
        JOIN read_csv('${bundle.electoralUrl}', ${bundle.electoralClause}) e
          ON e.entity_id = s.entity_id
         AND e.entity_kind = 'ac'
        WHERE e.state = ${stateLit}
          AND s.turnout_pct IS NOT NULL
      ),
      highest AS (SELECT 'highest' AS band, ac_no, ac_name, turnout_pct FROM ranked ORDER BY turnout_pct DESC LIMIT ${f.limit}),
      lowest  AS (SELECT 'lowest'  AS band, ac_no, ac_name, turnout_pct FROM ranked ORDER BY turnout_pct ASC  LIMIT ${f.limit})
      SELECT band, ac_no, ac_name, turnout_pct FROM highest
      UNION ALL
      SELECT band, ac_no, ac_name, turnout_pct FROM lowest
      ORDER BY band DESC, turnout_pct DESC
    `;
    const provenanceSql = `
      SELECT DISTINCT
        s2.source_id, s2.producer, s2.title, s2.vintage, s2.license,
        s2.confidence_tier, s2.is_issuing_authority, s2.verification_method,
        s2.url_main, s2.citation_full, s2.notes
      FROM read_csv('${bundle.sumUrl}', ${bundle.sumClause}) s
      JOIN read_csv('${bundle.electoralUrl}', ${bundle.electoralClause}) e
        ON e.entity_id = s.entity_id
       AND e.entity_kind = 'ac'
      JOIN sources s2 ON s2.source_id = s.source_id
      WHERE e.state = ${stateLit}
      ORDER BY s2.source_id
    `;
    const hints: AnswerViewHints = {
      question: intent.question,
      column_order: ["band", "ac_no", "ac_name", "turnout_pct"],
      column_labels: {
        band: "Band",
        ac_no: "AC #",
        ac_name: "Constituency",
        turnout_pct: "Turnout",
      },
      column_formats: {
        band: "text" as ColumnFormat,
        ac_no: "integer" as ColumnFormat,
        ac_name: "text" as ColumnFormat,
        turnout_pct: "percentage" as ColumnFormat,
      },
    };
    return {
      concept_id: intent.concept_id,
      slice_registrations: [],
      table_registrations: [
        { table_id: "taxonomy.sources", view_name: "sources" },
      ],
      csv_registrations: [
        { url: bundle.sumUrl },
        { url: bundle.electoralUrl },
      ],
      main_sql: mainSql.trim(),
      provenance_sql: provenanceSql.trim(),
      view_hints: hints,
    };
  },
};

// ---------- Public registry ----------------------------------------------

export const CONCEPT_REGISTRY: Readonly<Record<ConceptId, ConceptHandler>> = Object.freeze({
  party_totals: PARTY_TOTALS,
  closest_contests: CLOSEST_CONTESTS,
  constituency_result: CONSTITUENCY_RESULT,
  turnout_extremes: TURNOUT_EXTREMES,
});

function requireFilters(
  intent: InsightIntent,
  handler: ConceptHandler,
  default_limit: number,
): ResolvedFilters {
  const f = intent.filters;
  for (const key of handler.required_filters) {
    if (f[key] == null) {
      throw new Error(
        `compile: concept_id "${intent.concept_id}" requires filters.${key}`,
      );
    }
  }
  // Narrowed copy; required fields are now non-null per the loop above.
  return {
    state_partition_id: f.state_partition_id as string,
    period_label: f.period_label as string,
    ac_no: f.ac_no,
    party_short_code: f.party_short_code,
    limit: f.limit ?? default_limit,
  };
}
