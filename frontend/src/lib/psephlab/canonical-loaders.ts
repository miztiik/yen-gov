// Canonical-store loader for the Psephlab what-if simulator (F1.3a CSV cutover).
//
// Reads the per-(state, year) long-format CSV layout via DuckDB-WASM
// (see lib/duckdb.ts + lib/canonical/election-csv-paths.ts) and returns
// the SAME `Tallies` shape that Compare.svelte + Psephlab.svelte already
// consume. Drop-in replacement for the previous parquet-backed loader
// that JOINed `elections_candidacies.parquet` + `dim_persons.parquet` +
// `dim_acs.parquet` + `dim_parties.parquet` + `election_results.parquet`.
//
// What is JOINed:
//   datasets/elections/assembly/state=*/election=*/candidacies.csv (per-candidacy)
//   datasets/elections/assembly/state=*/election=*/summary.csv     (per-AC)
//   datasets/data/entities/electoral.csv                           (AC entity_id + eci_no + name)
//   elections.dim_parties  (CSV via registerCsvAsTable; X1a reader flip)
//
// Critical per-row contract (F1 sub-plan section 22.4 #4): every
// `read_csv(...)` carries an explicit `columns={...}` map derived from
// `datasets/data/_schema/columns.json` via `csvColumnsClause`. No
// hand-typed column lists.
//
// Known regressions vs the pre-F1.3a parquet world (documented for X1a):
// - NOTA votes: candidacies.csv FILTERS NOTA at the writer
//   (assembly_results._build_candidacy_rows). The legacy SQL synthesised
//   NOTA rows from the `ac-nota-votes` indicator on election_results.
//   F1.3a synthesises a NOTA bucket from
//   ``MAX(0, summary.votes_polled - SUM(candidacy votes))`` per AC —
//   exact when votes_polled is real-published and lossy-zero when not.
//   The Psephlab counting rule already treats NOTA as a ballot option,
//   not a candidate, so a slightly-imprecise NOTA tally is acceptable
//   for what-if simulations; X1a restores precision via a candidacies
//   schema extension.

import { query, registerCsvAsTable, registerCsvFile } from "../duckdb";
import { DATA_BASE } from "../paths";
import { csvColumnsClause } from "../canonical/csv-columns";
import {
  assemblyCandidaciesPath,
  assemblySummaryPath,
  electoralEntitiesPath,
} from "../canonical/election-csv-paths";
import { electionStatePartition } from "../election-partitions";
import type { AcTally, CandidateTally, Tallies } from "./types";

// ---------- Cache: identical-shape mirror of the legacy loader ------------

const cache = new Map<string, Promise<Tallies>>();

function key(event: string, state: string): string {
  return `${event}/${state}`;
}

// ---------- Row shapes returned by the JOINs ------------------------------

interface ConstituencyRow {
  ac_eci_no: number;
  name: string;
  votes_polled: number | null;
}

interface CandidateRow {
  ac_eci_no: number;
  rank: number | null;
  name: string;
  party_eci_code: string | null;
  party_short: string | null;
  votes: number | null;
  is_nota: number;
  party_id: string | null;
  brand_colour_hex: string | null;
  brand_colour_confidence: "high" | "medium" | "low" | null;
}

// ---------- SQL composition -----------------------------------------------

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

// DuckDB-WASM returns BIGINT as BigInt and DOUBLE as number. Vote counts
// in candidacies.csv are integer (BIGINT per columns.json); shares are
// DOUBLE. `Number(x ?? 0)` flattens both safely.
const num = (v: unknown): number => (v == null ? 0 : Number(v));

function buildConstituencySql(
  sumUrl: string,
  sumClause: string,
  electoralUrl: string,
  electoralClause: string,
  stateLiteral: string,
): string {
  // One row per AC. votes_polled doubles as the electorate proxy (same
  // contract as the legacy loader; turnout-uplift mutations get a real
  // electors column in X1a).
  return `
    SELECT
      e.eci_no                              AS ac_eci_no,
      e.name                                AS name,
      CAST(s.votes_polled AS BIGINT)        AS votes_polled
    FROM read_csv('${sumUrl}', ${sumClause}) s
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = s.entity_id
     AND e.entity_kind = 'ac'
    WHERE e.state = ${stateLiteral}
    ORDER BY e.eci_no
  `;
}

function buildCandidateSql(
  candUrl: string,
  candClause: string,
  sumUrl: string,
  sumClause: string,
  electoralUrl: string,
  electoralClause: string,
  stateLiteral: string,
): string {
  // UNION ALL of:
  //   (a) real candidacy rows from candidacies.csv joined to electoral.csv
  //       (for eci_no) and dim_parties (for brand identity).
  //   (b) synthesised NOTA rows: one per AC where
  //       `votes_polled - SUM(real votes) > 0`. NOTA rank is NULL so it
  //       sorts after real candidates per ASC NULLS LAST default.
  // The party_short fallback chain mirrors the legacy loader: prefer
  // dim_parties.short_name, fall back to the substring-extracted
  // short_name_key when the LEFT JOIN misses (long-tail parties), fall
  // back to the empty string when both are null (the consumer maps
  // empty -> "IND").
  return `
    SELECT
      e.eci_no                                              AS ac_eci_no,
      ec.position                                           AS rank,
      ec.candidate_name                                     AS name,
      dp.eci_code                                           AS party_eci_code,
      COALESCE(
        dp.short_name,
        CASE WHEN ec.party_id LIKE 'parties.IN.%'
             THEN substring(ec.party_id, length('parties.IN.') + 1)
             ELSE ec.party_id END,
        ''
      )                                                     AS party_short,
      ec.party_id                                           AS party_id,
      dp.brand_colour_hex                                   AS brand_colour_hex,
      dp.brand_colour_confidence                            AS brand_colour_confidence,
      CAST(ec.votes AS BIGINT)                              AS votes,
      0                                                     AS is_nota
    FROM read_csv('${candUrl}', ${candClause}) ec
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = ec.entity_id
     AND e.entity_kind = 'ac'
    LEFT JOIN dim_parties dp ON dp.party_id = ec.party_id
    WHERE e.state = ${stateLiteral}

    UNION ALL

    SELECT
      e.eci_no                                              AS ac_eci_no,
      NULL::INTEGER                                         AS rank,
      'NOTA'                                                AS name,
      NULL::VARCHAR                                         AS party_eci_code,
      'NOTA'                                                AS party_short,
      'parties.IN.NOTA'                                     AS party_id,
      NULL::VARCHAR                                         AS brand_colour_hex,
      NULL::VARCHAR                                         AS brand_colour_confidence,
      CAST(GREATEST(
        COALESCE(s.votes_polled, 0) - COALESCE(real.real_votes, 0),
        0
      ) AS BIGINT)                                          AS votes,
      1                                                     AS is_nota
    FROM read_csv('${sumUrl}', ${sumClause}) s
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = s.entity_id
     AND e.entity_kind = 'ac'
    LEFT JOIN (
      SELECT entity_id, SUM(votes) AS real_votes
      FROM read_csv('${candUrl}', ${candClause})
      GROUP BY entity_id
    ) real ON real.entity_id = s.entity_id
    WHERE e.state = ${stateLiteral}
      AND COALESCE(s.votes_polled, 0) > COALESCE(real.real_votes, 0)

    ORDER BY ac_eci_no, rank
  `;
}

// ---------- Public API: SAME signature + return shape as legacy ----------

/**
 * Load a `Tallies` snapshot for one (event, state) via the canonical CSV
 * store. Same signature + return shape + caching + Object.freeze semantics
 * as the legacy parquet loader. Consumers (Compare.svelte +
 * Psephlab.svelte) need no change.
 */
export function loadActuals(event: string, state: string): Promise<Tallies> {
  const k = key(event, state);
  const hit = cache.get(k);
  if (hit) return hit;

  const p = (async (): Promise<Tallies> => {
    const candPath = assemblyCandidaciesPath(state, event);
    const sumPath = assemblySummaryPath(state, event);
    const electoralPath = electoralEntitiesPath();
    const candUrl = `${DATA_BASE}/${candPath.replace(/^datasets\//, "")}`;
    const sumUrl = `${DATA_BASE}/${sumPath.replace(/^datasets\//, "")}`;
    const electoralUrl = `${DATA_BASE}/${electoralPath.replace(/^datasets\//, "")}`;

    const [candClause, sumClause, electoralClause] = await Promise.all([
      csvColumnsClause(candPath),
      csvColumnsClause(sumPath),
      csvColumnsClause(electoralPath),
      registerCsvFile(candUrl),
      registerCsvFile(sumUrl),
      registerCsvFile(electoralUrl),
      registerCsvAsTable("elections.dim_parties"),
    ]);

    // candidacies + summary carry the LGD state slug as their `state`
    // column; electoral.csv carries it too. The defensive WHERE filter
    // mirrors the constituency.ts pattern (electoral.csv contains every
    // state's ACs and we want only this state's).
    const slug = electionStatePartition(state);
    const stateLit = sqlString(slug);

    const [constituencies, candidates] = await Promise.all([
      query<ConstituencyRow>(
        buildConstituencySql(sumUrl, sumClause, electoralUrl, electoralClause, stateLit),
      ),
      query<CandidateRow>(
        buildCandidateSql(
          candUrl,
          candClause,
          sumUrl,
          sumClause,
          electoralUrl,
          electoralClause,
          stateLit,
        ),
      ),
    ]);

    const acs: AcTally[] = [];
    const ac_index = new Map<number, AcTally>();
    for (const row of constituencies) {
      const eci_no = Number(row.ac_eci_no);
      const ac: AcTally = {
        eci_no,
        name: String(row.name ?? ""),
        electorate: num(row.votes_polled),
        candidates: [],
      };
      acs.push(ac);
      ac_index.set(eci_no, ac);
    }

    for (const row of candidates) {
      const eci_no = Number(row.ac_eci_no);
      const ac = ac_index.get(eci_no);
      if (!ac) continue;
      const is_nota = Number(row.is_nota ?? 0) === 1;
      const name = String(row.name ?? "");
      const party_code = row.party_eci_code == null ? null : String(row.party_eci_code);
      const party_short = String(row.party_short ?? "");
      const resolved_eci = is_nota ? "NOTA" : (party_code ?? "IND");
      const resolved_short = party_short || (is_nota ? "NOTA" : "IND");
      // party_id resolution: prefer the dim_parties.party_id from the JOIN
      // (carried via ec.party_id which already maps to the canonical id);
      // for NOTA the SQL hardcodes parties.IN.NOTA; for IND fallback rows
      // (party_id NULL in candidacies.csv) synthesise the canonical sentinel.
      const party_id =
        row.party_id != null && row.party_id !== ""
          ? String(row.party_id)
          : is_nota
            ? "parties.IN.NOTA"
            : "parties.IN.IND";
      const c: CandidateTally = {
        party_eci_code: resolved_eci,
        party_short: resolved_short,
        name,
        votes: num(row.votes),
        party_id,
        brand_colour_hex: row.brand_colour_hex ?? null,
        brand_colour_confidence: row.brand_colour_confidence ?? null,
      };
      ac.candidates.push(c);
    }

    const tallies: Tallies = {
      scope: { country: "IN", state, election: event },
      acs,
    };
    Object.freeze(tallies);
    Object.freeze(tallies.acs);
    return tallies;
  })();

  cache.set(k, p);
  p.catch(() => cache.delete(k));
  return p;
}

// ---------- Test-only hook ------------------------------------------------

/**
 * Reset the per-module Tallies cache. NOT for production use - tests
 * call this between cases so cached promises from one case don't bleed
 * into the next.
 */
export function __resetForTests(): void {
  cache.clear();
}
