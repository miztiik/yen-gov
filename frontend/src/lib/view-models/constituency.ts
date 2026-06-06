// Citizen view-model loader for the Constituency route (F1.3a CSV cutover).
//
// Reads the per-(state, year) long-format CSV layout via DuckDB-WASM
// (see lib/duckdb.ts + lib/canonical/election-csv-paths.ts) and
// reconstructs the legacy `ConstituencyResult` shape so
// Constituency.svelte renders unchanged. Replaces the previous
// `elections_candidacies.parquet` + `dim_persons.parquet` +
// `dim_acs.parquet` + `election_results.parquet` JOIN per the F1.3
// sub-plan ("drop the dim_persons join; project ec.sex, ec.age,
// ec.education, ec.profession, ec.candidate_name").
//
// What is JOINed:
//   datasets/elections/assembly/state=*/election=*/candidacies.csv (per-candidacy row)
//   datasets/elections/assembly/state=*/election=*/summary.csv     (per-AC row)
//   datasets/data/entities/electoral.csv                           (AC name + eci_no lookup)
//   elections.dim_parties  (PARQUET; X1a flips this away later)
//   taxonomy.sources       (PARQUET; X1a flips this away later)
//
// Critical per-row contract (F1 sub-plan section 22.4 #4): every
// `read_csv(...)` carries an explicit `columns={...}` map derived from
// `datasets/data/_schema/columns.json` via `csvColumnsClause`. No
// hand-typed column lists.
//
// LoaderResult arms:
//   ok       — candidacies has 1+ rows for (state, eci_no, year);
//              full ConstituencyResult built.
//   partial  — zero candidacies for (state, eci_no, year). Returns a
//              skeleton + reason="not_published".
//   failed   — DuckDB-WASM / fetch / SQL error; `describeFailure` maps
//              to citizen-readable copy + retry callable.

import {
  describeFailure,
  type LoaderResult,
} from "../loader-result";
import { query, registerCsvFile, registerTable } from "../duckdb";
import { electionStatePartition } from "../election-partitions";
import { DATA_BASE } from "../paths";
import { csvColumnsClause } from "../canonical/csv-columns";
import {
  assemblyCandidaciesPath,
  assemblySummaryPath,
  electoralEntitiesPath,
} from "../canonical/election-csv-paths";
import type {
  CandidateResult,
  ConstituencyResult,
  SourceRef,
} from "../data";

// Default top-N kept candidates per AC. Mirrors the implicit fold the
// previous `elections_candidacies.parquet` writer applied. Keeping it
// as a module-local constant rather than a config knob preserves the
// previous UI behaviour for citizens; the candidacies.csv source
// carries ALL candidates so a future renderer change can lift the cap
// without re-emitting data.
const TOP_N_CANDIDATES = 7;

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

interface CandidateRow {
  candidate_name: string | null;
  party_id_raw: string | null;
  votes: number | null;
  vote_share_pct: number | null;
  position: number | null;
  result: string | null;
  sex: string | null;
  age: number | null;
  education: string | null;
  profession: string | null;
  candidate_type: string | null;
  source_id: string | null;
  ac_id: string;
  constituency_name: string | null;
  dp_short_name: string | null;
  party_full: string | null;
  party_eci_code: string | null;
  brand_colour_hex: string | null;
  brand_colour_confidence: string | null;
  election_symbol_asset_path: string | null;
}

interface SummaryRow {
  electors: number | null;
  votes_polled: number | null;
  turnout_pct: number | null;
  winner_candidate: string | null;
  winner_party_id: string | null;
  winner_votes: number | null;
  margin_votes: number | null;
  margin_pct: number | null;
  source_id: string | null;
}

interface SourceJoinRow {
  url_main: string | null;
}

// Numeric coercion: DuckDB-WASM returns BIGINT as BigInt and DOUBLE as
// number. Per columns.json: `votes`/`age`/`electors`/`votes_polled`/
// `winner_votes`/`margin_votes` are integer (BIGINT); the rest are
// number (DOUBLE). `Number(x ?? 0)` flattens both safely.
const num = (v: unknown): number => (v == null ? 0 : Number(v));

// Bio object: collapse to a single nullable object so the renderer
// guards with `{#if c.bio}` instead of probing six fields. Returns
// `null` when every bio column is NULL.
function bioFromRow(r: CandidateRow): CandidateResult["bio"] {
  const hasBio =
    r.sex !== null || r.age !== null || r.education !== null ||
    r.profession !== null || r.candidate_type !== null;
  if (!hasBio) return null;
  return {
    sex: r.sex,
    age: r.age === null ? null : Number(r.age),
    education: r.education,
    profession: r.profession,
    // candidacies.csv carries no per-candidacy `constituency_type`; the
    // old elections_candidacies.parquet duplicated electoral.csv's
    // `reservation` (AC scope). F1.3a drops the duplicate; the
    // renderer can read reservation from the AC entity if needed.
    constituency_type: null,
    // `party_type` on the old parquet was an ad-hoc enum
    // (NEW/RECONTEST/...); the new CSV ladder calls this
    // `candidate_type` (incumbent/challenger/crossover per
    // columns.json). Map through with the same nullable contract.
    party_type: r.candidate_type,
  };
}

function buildOthersBucket(
  candidates: CandidateResult[],
  totalContested: number,
  othersVotes: number,
  othersPct: number,
): ConstituencyResult["others"] {
  const tail = totalContested - candidates.length;
  if (tail <= 0) return null;
  return {
    candidate_count: tail,
    votes: othersVotes,
    vote_share_pct: +othersPct.toFixed(2),
  };
}

async function runQueries(
  event: string,
  state_code: string,
  eci_no: number,
): Promise<{
  candidates: CandidateRow[];
  summary: SummaryRow | null;
  sources: SourceJoinRow[];
}> {
  const slug = electionStatePartition(state_code);

  const candPath = assemblyCandidaciesPath(state_code, event);
  const sumPath = assemblySummaryPath(state_code, event);
  const electoralPath = electoralEntitiesPath();

  const candUrl = `${DATA_BASE}/${candPath.replace(/^datasets\//, "")}`;
  const sumUrl = `${DATA_BASE}/${sumPath.replace(/^datasets\//, "")}`;
  const electoralUrl = `${DATA_BASE}/${electoralPath.replace(/^datasets\//, "")}`;

  // Typed-read clauses + view registrations in parallel. Per F1
  // sub-plan section 22.4 #4: read_csv MUST carry `columns={...}`
  // derived from columns.json (never `read_csv_auto`). dim_parties +
  // taxonomy.sources stay on Parquet; X1a flips them when the
  // Hive-partitioned per-(state,year) Parquet datasets retire.
  const [candClause, sumClause, electoralClause] = await Promise.all([
    csvColumnsClause(candPath),
    csvColumnsClause(sumPath),
    csvColumnsClause(electoralPath),
    registerCsvFile(candUrl),
    registerCsvFile(sumUrl),
    registerCsvFile(electoralUrl),
    registerTable("elections.dim_parties"),
    registerTable("taxonomy.sources"),
  ]);

  const slugLit = sqlString(slug);

  // Query 1: per-candidacy rows for this AC. JOIN electoral.csv for
  // the AC `entity_id` <-> ECI `eci_no` mapping (citizens always
  // navigate by eci_no in the URL); LEFT JOIN dim_parties (Parquet)
  // for the brand identity columns the candidate row carries
  // downstream.
  const candidatesSql = `
    SELECT
      ec.candidate_name             AS candidate_name,
      ec.party_id                   AS party_id_raw,
      ec.votes                      AS votes,
      ec.vote_share_pct             AS vote_share_pct,
      ec.position                   AS position,
      ec.result                     AS result,
      ec.sex                        AS sex,
      ec.age                        AS age,
      ec.education                  AS education,
      ec.profession                 AS profession,
      ec.candidate_type             AS candidate_type,
      ec.source_id                  AS source_id,
      e.entity_id                   AS ac_id,
      e.name                        AS constituency_name,
      dp.short_name                 AS dp_short_name,
      dp.full_name                  AS party_full,
      dp.eci_code                   AS party_eci_code,
      dp.brand_colour_hex           AS brand_colour_hex,
      dp.brand_colour_confidence    AS brand_colour_confidence,
      dp.election_symbol_asset_path AS election_symbol_asset_path
    FROM read_csv('${candUrl}', ${candClause}) ec
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = ec.entity_id
     AND e.entity_kind = 'ac'
    LEFT JOIN dim_parties dp ON dp.party_id = ec.party_id
    WHERE e.state = ${slugLit}
      AND e.eci_no = ${eci_no}
    ORDER BY ec.position
  `;
  const candidates = await query<CandidateRow>(candidatesSql);

  if (candidates.length === 0) {
    return { candidates, summary: null, sources: [] };
  }

  // Query 2: AC summary (electors / turnout / margin / winner). One
  // row per (state, eci_no) in summary.csv. The view-model reads
  // winner party_id + margin from here so the WinnerInfo block does
  // not need a second pass over the candidacy rows.
  const summarySql = `
    SELECT
      s.electors                    AS electors,
      s.votes_polled                AS votes_polled,
      s.turnout_pct                 AS turnout_pct,
      s.winner_candidate            AS winner_candidate,
      s.winner_party_id             AS winner_party_id,
      s.winner_votes                AS winner_votes,
      s.margin_votes                AS margin_votes,
      s.margin_pct                  AS margin_pct,
      s.source_id                   AS source_id
    FROM read_csv('${sumUrl}', ${sumClause}) s
    JOIN read_csv('${electoralUrl}', ${electoralClause}) e
      ON e.entity_id = s.entity_id
     AND e.entity_kind = 'ac'
    WHERE e.state = ${slugLit}
      AND e.eci_no = ${eci_no}
    LIMIT 1
  `;
  const summaryRows = await query<SummaryRow>(summarySql);
  const summary = summaryRows[0] ?? null;

  // Query 3: rich v2.0 citation rows for every source_id this contest
  // touched (candidacies + summary). taxonomy.sources stays on
  // Parquet until X1a; the `url_main` column is the only field the
  // legacy v1 SourceList renders, so we keep the existing url-only
  // projection for back-compat. The full v2 ledger picker lives on
  // state-overview for now.
  const sourceIds = new Set<string>();
  for (const r of candidates) {
    if (r.source_id) sourceIds.add(r.source_id);
  }
  if (summary?.source_id) sourceIds.add(summary.source_id);

  let sources: SourceJoinRow[] = [];
  if (sourceIds.size > 0) {
    const idList = [...sourceIds].map(sqlString).join(", ");
    sources = await query<SourceJoinRow>(`
      SELECT DISTINCT s.url_main
      FROM sources s
      WHERE s.source_id IN (${idList})
        AND s.url_main IS NOT NULL
        AND s.url_main <> ''
      ORDER BY s.url_main
    `);
  }

  return { candidates, summary, sources };
}

function assembleResult(
  event: string,
  state_code: string,
  eci_no: number,
  rows: {
    candidates: CandidateRow[];
    summary: SummaryRow | null;
    sources: SourceJoinRow[];
  },
): ConstituencyResult {
  // Split NOTA out of the candidate list per the existing UI contract
  // (NOTA appears in its own `nota` bucket, not in the candidate
  // table).
  const realCandidates = rows.candidates.filter(
    (c) => (c.candidate_name ?? "").toUpperCase() !== "NOTA",
  );
  const notaRow = rows.candidates.find(
    (c) => (c.candidate_name ?? "").toUpperCase() === "NOTA",
  ) ?? null;

  // Top-N cut: preserve the pre-CSV fold UI (kept rows + "others"
  // bucket for tail). candidacies.csv carries ALL candidates so the
  // fold happens here, not at write time.
  const totalContested = realCandidates.length;
  const keptRows = realCandidates.slice(0, TOP_N_CANDIDATES);
  const tailRows = realCandidates.slice(TOP_N_CANDIDATES);
  const othersVotes = tailRows.reduce((sum, r) => sum + num(r.votes), 0);
  const totalRealVotes = realCandidates.reduce(
    (sum, r) => sum + num(r.votes),
    0,
  );
  const othersPct =
    totalRealVotes > 0 ? (othersVotes / totalRealVotes) * 100 : 0;

  const winnerRow =
    keptRows.find((c) => Number(c.position) === 1) ?? keptRows[0];

  const candidates: CandidateResult[] = keptRows.map((r) => ({
    rank: Number(r.position ?? 0),
    name: r.candidate_name ?? "",
    party_id: r.party_id_raw ?? "parties.IN.UNK",
    party_eci_code: r.party_eci_code ?? null,
    party_short: r.dp_short_name ?? r.party_id_raw ?? "IND",
    votes: num(r.votes),
    vote_share_pct: num(r.vote_share_pct),
    is_winner: Number(r.position ?? 0) === 1,
    brand_colour_hex: r.brand_colour_hex ?? null,
    brand_colour_confidence:
      r.brand_colour_confidence === "high" ||
      r.brand_colour_confidence === "medium" ||
      r.brand_colour_confidence === "low"
        ? r.brand_colour_confidence
        : null,
    election_symbol_asset_path: r.election_symbol_asset_path ?? null,
    bio: bioFromRow(r),
  }));

  const top_n_cutoff = candidates.length;
  const others = buildOthersBucket(
    candidates,
    totalContested,
    othersVotes,
    othersPct,
  );

  // NOTA bucket from the dedicated NOTA candidate row.
  // vote_share_pct is published per-AC by the writer so we lift it
  // through; no derivation here.
  const nota = notaRow
    ? {
        votes: num(notaRow.votes),
        vote_share_pct: num(notaRow.vote_share_pct),
      }
    : { votes: 0, vote_share_pct: 0 };

  const sources: SourceRef[] = rows.sources
    .filter((s) => !!s.url_main)
    .map((s) => ({
      url: s.url_main ?? "",
      // Citation ledger (v2.0) does not carry fetch telemetry —
      // `fetched_at` is intentionally empty. See ADR-0032.
      fetched_at: "",
    }));

  return {
    $schema: "./schemas/constituency.schema.json",
    $schema_version: "1.1",
    sources,
    election: event,
    state: state_code,
    body: "AC",
    eci_no,
    constituency_name: rows.candidates[0]?.constituency_name ?? undefined,
    totals: {
      electors:
        rows.summary?.electors == null
          ? undefined
          : Number(rows.summary.electors),
      votes_polled:
        rows.summary?.votes_polled == null
          ? 0
          : Number(rows.summary.votes_polled),
      turnout_pct:
        rows.summary?.turnout_pct == null
          ? undefined
          : Number(rows.summary.turnout_pct),
    },
    candidates,
    nota,
    others,
    top_n_cutoff,
    candidates_total: totalContested,
    winner: {
      name: winnerRow?.candidate_name ?? "",
      party_eci_code: winnerRow?.party_eci_code ?? null,
      party_short:
        winnerRow?.dp_short_name ?? winnerRow?.party_id_raw ?? "IND",
      votes: num(winnerRow?.votes),
      margin_votes:
        rows.summary?.margin_votes == null
          ? 0
          : Number(rows.summary.margin_votes),
      margin_pct:
        rows.summary?.margin_pct == null
          ? 0
          : Number(rows.summary.margin_pct),
      party_id: winnerRow?.party_id_raw ?? null,
      brand_colour_hex: winnerRow?.brand_colour_hex ?? null,
      brand_colour_confidence:
        winnerRow?.brand_colour_confidence === "high" ||
        winnerRow?.brand_colour_confidence === "medium" ||
        winnerRow?.brand_colour_confidence === "low"
          ? winnerRow.brand_colour_confidence
          : null,
      election_symbol_asset_path:
        winnerRow?.election_symbol_asset_path ?? null,
    },
  };
}

function notPublishedSkeleton(
  event: string,
  state_code: string,
  eci_no: number,
): ConstituencyResult {
  return {
    $schema: "./schemas/constituency.schema.json",
    $schema_version: "1.1",
    sources: [],
    election: event,
    state: state_code,
    body: "AC",
    eci_no,
    totals: { votes_polled: 0 },
    candidates: [],
    nota: { votes: 0, vote_share_pct: 0 },
    others: null,
    top_n_cutoff: 0,
    winner: {
      name: "",
      party_eci_code: null,
      party_short: "",
      votes: 0,
      margin_votes: 0,
      margin_pct: 0,
    },
  };
}

export async function loadConstituencyResult(
  event: string,
  state_code: string,
  eci_no: number,
): Promise<LoaderResult<ConstituencyResult>> {
  try {
    const rows = await runQueries(event, state_code, eci_no);
    if (rows.candidates.length === 0) {
      return {
        status: "partial",
        data: notPublishedSkeleton(event, state_code, eci_no),
        reason: "not_published",
      };
    }
    return {
      status: "ok",
      data: assembleResult(event, state_code, eci_no, rows),
    };
  } catch (err) {
    return {
      status: "failed",
      reason: describeFailure(err),
      retry: () => loadConstituencyResult(event, state_code, eci_no),
    };
  }
}
