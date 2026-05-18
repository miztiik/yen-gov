// Citizen view-model loader for the Constituency route (PR-E / Phase 1.3a).
//
// Reads the canonical Parquet store via DuckDB-WASM (see lib/duckdb.ts) and
// reconstructs the legacy `ConstituencyResult` shape so Constituency.svelte
// can render unchanged. Replaces `fetchConstituencyResult` from lib/data.ts —
// the per-shard JSON contract is retired by the canonical pivot (ADR-0030).
//
// What is JOINed:
//   elections.dim_acs        — AC identity + display name
//   elections.dim_candidates — per-contest candidate rows (PK = entity_id)
//   elections.dim_parties    — party labels (short / full / eci_code)
//   elections.observations   — numeric facts (votes, share, AC totals)
//   taxonomy.sources         — provenance URLs + first_fetched_at
//
// LoaderResult arms:
//   ok       — JOIN produced 1+ candidate rows; full ConstituencyResult built.
//   partial  — dim_candidates has zero rows for (state, eci_no, event) — the
//              ECI did not publish a result (countermanded / postponed AC).
//              Returns a skeleton result + reason="not_published" so the
//              existing amber pane copy still renders.
//   failed   — DuckDB-WASM / fetch / SQL error; `describeFailure` maps to
//              citizen-readable copy + a retry callable.

import {
  describeFailure,
  type LoaderResult,
} from "../loader-result";
import { query, registerTable } from "../duckdb";
import type {
  CandidateResult,
  ConstituencyResult,
  SourceRef,
} from "../data";

// Top-N cutoff matches the legacy per-AC contract (datasets/_old). The
// frontend already truncates display via this number; the canonical store
// does NOT materialise an "others" bucket because it's a UX concern, not a
// fact (see docs/architecture/data/elections-indicators.md §"What is NOT
// materialised"). For Phase 1.3a we surface every candidate the dim table
// holds and set cutoff to the row count, so Constituency.svelte's `Top {N}
// candidates` heading stays truthful.
function buildOthersBucket(
  candidates: CandidateResult[],
  cutoff: number,
): ConstituencyResult["others"] {
  const tail = candidates.slice(cutoff);
  if (tail.length === 0) return null;
  return {
    candidate_count: tail.length,
    votes: tail.reduce((s, c) => s + c.votes, 0),
    vote_share_pct: +tail.reduce((s, c) => s + c.vote_share_pct, 0).toFixed(2),
  };
}

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

interface CandidateRow {
  candidate_id: string;
  ac_id: string;
  constituency_name: string | null;
  candidate_name: string | null;
  rank: number;
  party_id: string;
  party_short: string | null;
  party_full: string | null;
  party_eci_code: string | null;
  votes: number | null;
  vote_share_pct: number | null;
}

interface AcScopeRow {
  indicator_id: string;
  value_numeric: number | null;
  value_text: string | null;
}

interface SourceJoinRow {
  url: string | null;
  first_fetched_at: string | null;
}

// Numeric coercion: DuckDB-WASM returns BIGINT as BigInt and DOUBLE as
// number. Candidate vote counts are stored as DOUBLE in observations.parquet
// (see canonical-store.md §11.1 — value_numeric is DOUBLE), so we just need
// `Number(x ?? 0)` to flatten. Kept in one helper so a future BIGINT switch
// in the schema doesn't scatter coercions across the loader.
const num = (v: unknown): number => (v == null ? 0 : Number(v));

async function runQueries(
  event: string,
  state_code: string,
  eci_no: number,
): Promise<{
  candidates: CandidateRow[];
  acScope: AcScopeRow[];
  sources: SourceJoinRow[];
}> {
  // Register every Parquet view we need (idempotent per session).
  await Promise.all([
    registerTable("elections.observations"),
    registerTable("elections.dim_candidates"),
    registerTable("elections.dim_acs"),
    registerTable("elections.dim_parties"),
    registerTable("taxonomy.sources"),
  ]);

  const evt = sqlString(event);
  const sc = sqlString(state_code);

  // Candidate JOIN: rank-ordered rows ready to fold into CandidateResult[].
  const candidateSql = `
    SELECT
      dc.candidate_id   AS candidate_id,
      dc.ac_id          AS ac_id,
      da.name           AS constituency_name,
      dc.name           AS candidate_name,
      dc.rank           AS rank,
      dc.party_id       AS party_id,
      dp.short_name     AS party_short,
      dp.full_name      AS party_full,
      dp.eci_code       AS party_eci_code,
      obs_v.value_numeric AS votes,
      obs_s.value_numeric AS vote_share_pct
    FROM dim_candidates dc
    JOIN dim_acs da ON da.ac_id = dc.ac_id
    LEFT JOIN dim_parties dp ON dp.party_id = dc.party_id
    LEFT JOIN observations obs_v
      ON obs_v.entity_id = dc.candidate_id
     AND obs_v.indicator_id = 'candidate-votes-polled'
     AND obs_v.period_label = dc.period_label
    LEFT JOIN observations obs_s
      ON obs_s.entity_id = dc.candidate_id
     AND obs_s.indicator_id = 'candidate-vote-share-pct'
     AND obs_s.period_label = dc.period_label
    WHERE da.state_code = ${sc}
      AND da.eci_no = ${eci_no}
      AND dc.period_label = ${evt}
    ORDER BY dc.rank
  `;
  const candidates = await query<CandidateRow>(candidateSql);

  if (candidates.length === 0) {
    return { candidates, acScope: [], sources: [] };
  }

  const ac_id = candidates[0].ac_id;
  const ac = sqlString(ac_id);

  // AC-scope facts: turnout, totals, NOTA, winner refs, margin.
  const acScope = await query<AcScopeRow>(`
    SELECT indicator_id, value_numeric, value_text
    FROM observations
    WHERE entity_id = ${ac}
      AND period_label = ${evt}
      AND indicator_id LIKE 'ac-%'
  `);

  // Provenance: DISTINCT URLs across every row that contributed to this
  // contest (AC-scope + candidate-scope). taxonomy.sources is the canonical
  // sources table; we project (url, first_fetched_at) into the legacy
  // SourceRef shape the SourceList renderer already understands.
  const candidateIds = candidates
    .map((c) => sqlString(c.candidate_id))
    .join(", ");
  const sources = await query<SourceJoinRow>(`
    SELECT DISTINCT s.url, s.first_fetched_at
    FROM observations o
    JOIN sources s ON s.source_id = o.source_id
    WHERE o.period_label = ${evt}
      AND (
        o.entity_id = ${ac}
        OR o.entity_id IN (${candidateIds})
      )
      AND s.url <> ''
    ORDER BY s.first_fetched_at
  `);

  return { candidates, acScope, sources };
}

function assembleResult(
  event: string,
  state_code: string,
  eci_no: number,
  rows: {
    candidates: CandidateRow[];
    acScope: AcScopeRow[];
    sources: SourceJoinRow[];
  },
): ConstituencyResult {
  const acMap = new Map<string, AcScopeRow>();
  for (const r of rows.acScope) acMap.set(r.indicator_id, r);
  const acNum = (id: string): number | undefined => {
    const r = acMap.get(id);
    return r?.value_numeric == null ? undefined : Number(r.value_numeric);
  };
  const acText = (id: string): string | null =>
    acMap.get(id)?.value_text ?? null;

  const winnerCandidateId = acText("ac-winner-candidate-id");
  const winnerRow =
    rows.candidates.find((c) => c.candidate_id === winnerCandidateId) ??
    rows.candidates[0];

  const candidates: CandidateResult[] = rows.candidates.map((r) => ({
    rank: Number(r.rank),
    name: r.candidate_name ?? "",
    party_eci_code: r.party_eci_code ?? null,
    party_short: r.party_short ?? r.party_id,
    votes: num(r.votes),
    vote_share_pct: num(r.vote_share_pct),
    is_winner: r.candidate_id === winnerCandidateId,
  }));

  const top_n_cutoff = candidates.length;
  const others = buildOthersBucket(candidates, top_n_cutoff);

  const sources: SourceRef[] = rows.sources
    .filter((s) => !!s.url)
    .map((s) => ({
      url: s.url ?? "",
      fetched_at: s.first_fetched_at ?? "",
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
      electors: acNum("ac-total-electors"),
      votes_polled: acNum("ac-votes-polled") ?? 0,
      turnout_pct: acNum("ac-turnout-pct"),
    },
    candidates,
    nota: {
      votes: acNum("ac-nota-votes") ?? 0,
      vote_share_pct: acNum("ac-nota-pct") ?? 0,
    },
    others,
    top_n_cutoff,
    winner: {
      name: winnerRow?.candidate_name ?? "",
      party_eci_code: winnerRow?.party_eci_code ?? null,
      party_short: winnerRow?.party_short ?? winnerRow?.party_id ?? "",
      votes: num(winnerRow?.votes),
      margin_votes: acNum("ac-margin-votes") ?? 0,
      margin_pct: acNum("ac-margin-pct") ?? 0,
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
