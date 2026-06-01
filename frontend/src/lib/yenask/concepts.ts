// Hand-authored concept → query-template registry.
//
// Each entry maps a `ConceptId` (the closed enum in
// `contracts/insight-intent.ts`) to:
//   - the required filter fields the compiler will demand
//   - a SQL builder that returns the main query
//   - an AnswerViewHints object describing the rendered table
//
// Per plan-doc §17 D-04: this file is HAND-AUTHORED and bounded. Adding a
// new concept is an explicit, reviewable PR change here + an enum addition
// in `contracts/insight-intent.ts`. No automation, no LLM-generated SQL.
//
// All four PR-1 concepts read from `election_results` (the fact table)
// at compile/execute time. The catalogue is the WRITE-time discipline
// (D-04); reading the fact table at compile time IS the entire point of
// YENASK.

import type { InsightIntent } from "./contracts/insight-intent";
import type { ConceptId } from "./contracts/insight-intent";
import type { AnswerViewHints, DuckDBPlan, ColumnFormat } from "./types";
import { ECI_TO_LGD_SLUG } from "../maplibre/sources";

// Reverse lookup: state_partition_id (LGD slug, e.g. "tamil-nadu") -> ECI st_code
// (e.g. "S22"). Used by every concept that builds entity_id prefixes like
// "IN-S22-AC-...". The InsightIntent CDM emits LGD slugs since the M3 rename;
// the canonical entity_id grammar still uses ECI codes, so concepts.ts is the
// translation seam.
const SLUG_TO_ECI: Readonly<Record<string, string>> = Object.fromEntries(
  Object.entries(ECI_TO_LGD_SLUG).map(([code, slug]) => [slug, code]),
);

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

// ---------- Concept handlers ----------------------------------------------

interface ConceptHandler {
  readonly required_filters: readonly (keyof InsightIntent["filters"])[];
  readonly default_limit: number;
  build(intent: InsightIntent): DuckDBPlan;
}

const PARTY_TOTALS: ConceptHandler = {
  required_filters: ["state_partition_id", "period_label"],
  default_limit: 10,
  build(intent) {
    const f = requireFilters(intent, PARTY_TOTALS, 10);
    const evt = sqlString(f.period_label);
    const stateUpper = SLUG_TO_ECI[f.state_partition_id] ?? f.state_partition_id.toUpperCase();
    const partyPrefix = sqlString(`IN-${stateUpper}-${f.period_label}-PARTY-`);
    const mainSql = `
      SELECT
        regexp_extract(o.entity_id, '-PARTY-(.+)$', 1)                                       AS party_short,
        CAST(MAX(CASE WHEN o.indicator_id = 'party-seats-won'      THEN o.value_numeric END) AS INTEGER) AS seats_won,
        CAST(MAX(CASE WHEN o.indicator_id = 'party-votes-polled'   THEN o.value_numeric END) AS BIGINT)  AS votes,
             MAX(CASE WHEN o.indicator_id = 'party-vote-share-pct' THEN o.value_numeric END)             AS vote_share_pct
      FROM election_results o
      WHERE o.entity_id LIKE ${partyPrefix} || '%'
        AND o.period_label = ${evt}
        AND o.indicator_id IN ('party-seats-won', 'party-votes-polled', 'party-vote-share-pct')
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
      FROM election_results o
      JOIN sources s ON s.source_id = o.source_id
      WHERE o.entity_id LIKE ${partyPrefix} || '%'
        AND o.period_label = ${evt}
        AND o.indicator_id IN ('party-seats-won', 'party-votes-polled', 'party-vote-share-pct')
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
      slice_registrations: [
        { table_id: "elections.election_results", partition_filter: { state: f.state_partition_id }, view_name: "election_results" },
      ],
      table_registrations: [
        { table_id: "taxonomy.sources", view_name: "sources" },
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
  build(intent) {
    const f = requireFilters(intent, CLOSEST_CONTESTS, 10);
    const evt = sqlString(f.period_label);
    const stateUpper = SLUG_TO_ECI[f.state_partition_id] ?? f.state_partition_id.toUpperCase();
    const acPrefix = sqlString(`IN-${stateUpper}-`);

    // Per-AC winner vs runner-up vote-share gap. Reads ac-margin-pp
    // directly when published; otherwise computes from
    // candidate-vote-share-pct rank 1 vs rank 2 via candidacies.
    // For PR-1 we lean on `ac-margin-pp` when present (canonical
    // indicator emitted by the elections fold). Falls back to NULL
    // when missing — the row simply ranks lower.
    const mainSql = `
      SELECT
        da.eci_no       AS ac_no,
        da.name         AS ac_name,
        MAX(CASE WHEN o.indicator_id = 'ac-margin-pp' THEN o.value_numeric END) AS margin_pp,
        CAST(MAX(CASE WHEN o.indicator_id = 'ac-votes-polled' THEN o.value_numeric END) AS BIGINT) AS votes_polled
      FROM dim_acs da
      JOIN election_results o
        ON o.entity_id = da.ac_id
       AND o.period_label = ${evt}
       AND o.indicator_id IN ('ac-margin-pp', 'ac-votes-polled')
      WHERE da.state_code = ${sqlString(stateUpper)}
        AND da.ac_id LIKE ${acPrefix} || '%'
      GROUP BY da.eci_no, da.name
      HAVING margin_pp IS NOT NULL
      ORDER BY margin_pp ASC
      LIMIT ${f.limit}
    `;
    const provenanceSql = `
      SELECT DISTINCT
        s.source_id, s.producer, s.title, s.vintage, s.license,
        s.confidence_tier, s.is_issuing_authority, s.verification_method,
        s.url_main, s.citation_full, s.notes
      FROM dim_acs da
      JOIN election_results o
        ON o.entity_id = da.ac_id
       AND o.period_label = ${evt}
       AND o.indicator_id = 'ac-margin-pp'
      JOIN sources s ON s.source_id = o.source_id
      WHERE da.state_code = ${sqlString(stateUpper)}
      ORDER BY s.source_id
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
      slice_registrations: [
        { table_id: "elections.election_results", partition_filter: { state: f.state_partition_id }, view_name: "election_results" },
      ],
      table_registrations: [
        { table_id: "elections.dim_acs", view_name: "dim_acs" },
        { table_id: "taxonomy.sources", view_name: "sources" },
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
  build(intent) {
    const f = requireFilters(intent, CONSTITUENCY_RESULT, 7);
    if (f.ac_no == null) {
      throw new Error(
        "compile: constituency_result requires filters.ac_no",
      );
    }
    const evt = sqlString(f.period_label);
    const stateUpper = SLUG_TO_ECI[f.state_partition_id] ?? f.state_partition_id.toUpperCase();

    // Top-5 candidates by vote share for the named AC + NOTA row.
    // Mirrors the explore/duckdb-views.ts candidate pattern.
    const mainSql = `
      WITH cand_obs AS (
        SELECT
          o.entity_id AS candidate_id,
          MAX(CASE WHEN o.indicator_id = 'candidate-votes-polled'   THEN o.value_numeric END) AS votes,
          MAX(CASE WHEN o.indicator_id = 'candidate-vote-share-pct' THEN o.value_numeric END) AS vote_share_pct
        FROM election_results o
        WHERE o.period_label = ${evt}
          AND o.indicator_id IN ('candidate-votes-polled', 'candidate-vote-share-pct')
        GROUP BY o.entity_id
      )
      SELECT
        ec.rank                                                              AS rank,
        p.display_name                                                       AS candidate_name,
        CASE
          WHEN ec.party_id = 'parties.IN.UNK'
            THEN COALESCE(ec.party_short_raw, dp.short_name, 'UNK')
          ELSE dp.short_name
        END                                                                  AS party_short,
        CAST(co.votes AS BIGINT)                                             AS votes,
        co.vote_share_pct                                                    AS vote_share_pct
      FROM elections_candidacies ec
      JOIN dim_persons p ON p.person_id = ec.person_id
      JOIN dim_acs da    ON da.ac_id = ec.ac_id
      LEFT JOIN dim_parties dp ON dp.party_id = ec.party_id
      LEFT JOIN cand_obs co    ON co.candidate_id = ec.candidacy_key
      WHERE ec.election_id = ${evt}
        AND da.state_code = ${sqlString(stateUpper)}
        AND da.eci_no = ${f.ac_no}
      ORDER BY co.vote_share_pct DESC NULLS LAST
      LIMIT ${f.limit}
    `;
    const provenanceSql = `
      SELECT DISTINCT
        s.source_id, s.producer, s.title, s.vintage, s.license,
        s.confidence_tier, s.is_issuing_authority, s.verification_method,
        s.url_main, s.citation_full, s.notes
      FROM elections_candidacies ec
      JOIN dim_acs da ON da.ac_id = ec.ac_id
      JOIN election_results o
        ON o.entity_id = ec.candidacy_key
       AND o.period_label = ${evt}
       AND o.indicator_id IN ('candidate-votes-polled', 'candidate-vote-share-pct')
      JOIN sources s ON s.source_id = o.source_id
      WHERE da.state_code = ${sqlString(stateUpper)}
        AND da.eci_no = ${f.ac_no}
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
      slice_registrations: [
        { table_id: "elections.election_results", partition_filter: { state: f.state_partition_id }, view_name: "election_results" },
      ],
      table_registrations: [
        { table_id: "elections.dim_acs", view_name: "dim_acs" },
        { table_id: "elections.dim_parties", view_name: "dim_parties" },
        { table_id: "elections.dim_persons", view_name: "dim_persons" },
        { table_id: "elections.elections_candidacies", view_name: "elections_candidacies" },
        { table_id: "taxonomy.sources", view_name: "sources" },
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
  build(intent) {
    const f = requireFilters(intent, TURNOUT_EXTREMES, 10);
    const evt = sqlString(f.period_label);
    const stateUpper = SLUG_TO_ECI[f.state_partition_id] ?? f.state_partition_id.toUpperCase();

    // Per-AC turnout — one row per AC; the result table interleaves the
    // top-N (highest) and bottom-N (lowest) into a single ordered table
    // for the renderer. `band` distinguishes them.
    const mainSql = `
      WITH ranked AS (
        SELECT
          da.eci_no AS ac_no,
          da.name   AS ac_name,
          MAX(CASE WHEN o.indicator_id = 'ac-turnout-pct' THEN o.value_numeric END) AS turnout_pct
        FROM dim_acs da
        JOIN election_results o
          ON o.entity_id = da.ac_id
         AND o.period_label = ${evt}
         AND o.indicator_id = 'ac-turnout-pct'
        WHERE da.state_code = ${sqlString(stateUpper)}
        GROUP BY da.eci_no, da.name
        HAVING turnout_pct IS NOT NULL
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
        s.source_id, s.producer, s.title, s.vintage, s.license,
        s.confidence_tier, s.is_issuing_authority, s.verification_method,
        s.url_main, s.citation_full, s.notes
      FROM dim_acs da
      JOIN election_results o
        ON o.entity_id = da.ac_id
       AND o.period_label = ${evt}
       AND o.indicator_id = 'ac-turnout-pct'
      JOIN sources s ON s.source_id = o.source_id
      WHERE da.state_code = ${sqlString(stateUpper)}
      ORDER BY s.source_id
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
      slice_registrations: [
        { table_id: "elections.election_results", partition_filter: { state: f.state_partition_id }, view_name: "election_results" },
      ],
      table_registrations: [
        { table_id: "elections.dim_acs", view_name: "dim_acs" },
        { table_id: "taxonomy.sources", view_name: "sources" },
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
