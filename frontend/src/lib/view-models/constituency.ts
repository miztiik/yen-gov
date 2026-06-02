// Citizen view-model loader for the Constituency route (PR-E / Phase 1.3a).
//
// Reads the canonical Parquet store via DuckDB-WASM (see lib/duckdb.ts) and
// reconstructs the legacy `ConstituencyResult` shape so Constituency.svelte
// can render unchanged. Replaces `fetchConstituencyResult` from lib/data.ts —
// the per-shard JSON contract is retired by the canonical pivot (ADR-0030).
//
// What is JOINed:
//   elections.dim_acs           — AC identity + display name
//   elections.elections_candidacies — per-contest candidacy rows (PK = entity_id)
//   elections.dim_persons       — person identity + biographic fields
//   elections.dim_parties       — party labels (short / full / eci_code)
//   elections.election_results  — numeric facts (votes, share, AC totals)
//   taxonomy.sources            — provenance URLs (citation-ledger v2.0)
//
// LoaderResult arms:
//   ok       — JOIN produced 1+ candidate rows; full ConstituencyResult built.
//   partial  — candidacies has zero rows for (state, eci_no, event) — the
//              ECI did not publish a result (countermanded / postponed AC).
//              Returns a skeleton result + reason="not_published" so the
//              existing amber pane copy still renders.
//   failed   — DuckDB-WASM / fetch / SQL error; `describeFailure` maps to
//              citizen-readable copy + a retry callable.

import {
  describeFailure,
  type LoaderResult,
} from "../loader-result";
import { query, registerSlice, registerTable } from "../duckdb";
import { electionStatePartition } from "../election-partitions";
import type {
  CandidateResult,
  ConstituencyResult,
  SourceRef,
} from "../data";

// Phase 1.6 added `ac-candidates-total` + `ac-others-{votes,pct}` to the
// canonical observations so the view-model can reconstruct the real `others`
// bucket (count = total - kept) and expose the full field size on
// `candidates_total`. `top_n_cutoff` reflects the number of rows actually
// kept in elections_candidacies.
function buildOthersBucket(
  candidates: CandidateResult[],
  totalContested: number,
  othersVotes: number | undefined,
  othersPct: number | undefined,
): ConstituencyResult["others"] {
  const tail = totalContested - candidates.length;
  if (tail <= 0) return null;
  return {
    candidate_count: tail,
    votes: othersVotes ?? 0,
    vote_share_pct: +(othersPct ?? 0).toFixed(2),
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
  // PR-SYM-6b mirror columns from dim_parties (v1.1). Nullable in Parquet
  // -> nullable here. Resolver consumes brand_colour_hex + _confidence; UI
  // chips can render election_symbol_asset_path when present.
  brand_colour_hex: string | null;
  brand_colour_confidence: string | null;
  // v1.2 biographic columns (PR-S.2 / canonical pivot 1.8f). Nullable in
  // Parquet -> nullable here. Populated only for events where an ECI
  // Statistical Report adapter has run (currently TN AcGenApr2021).
  sex: string | null;
  age: number | null;
  education: string | null;
  profession: string | null;
  constituency_type: string | null;
  party_type: string | null;
}

interface AcScopeRow {
  indicator_id: string;
  value_numeric: number | null;
  value_text: string | null;
}

interface SourceJoinRow {
  url_main: string | null;
}

// Numeric coercion: DuckDB-WASM returns BIGINT as BigInt and DOUBLE as
// number. Candidate vote counts are stored as DOUBLE in election_results.parquet
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
    registerSlice("elections.election_results", { state: electionStatePartition(state_code) }),
    registerTable("elections.elections_candidacies"),
    registerTable("elections.dim_persons"),
    registerTable("elections.dim_acs"),
    registerTable("elections.dim_parties"),
    registerTable("taxonomy.sources"),
  ]);

  const evt = sqlString(event);
  const sc = sqlString(state_code);

  // Candidate JOIN: rank-ordered rows ready to fold into CandidateResult[].
  const candidateSql = `
    SELECT
      ec.candidacy_key  AS candidate_id,
      ec.ac_id          AS ac_id,
      da.name           AS constituency_name,
      p.display_name    AS candidate_name,
      ec.rank           AS rank,
      ec.party_id       AS party_id,
      CASE
        WHEN ec.party_id = 'parties.IN.UNK'
          THEN COALESCE(ec.party_short_raw, dp.short_name, 'UNK')
        ELSE dp.short_name
      END               AS party_short,
      dp.full_name      AS party_full,
      dp.eci_code       AS party_eci_code,
      -- PR-SYM-6b2: dim_parties.parquet rewritten to schema v1.1; project
      -- the real brand columns now. NULLs flow through when a row has no
      -- editorial brand colour (most parties) and the resolver falls
      -- through anchor -> algorithmic-fallback gracefully.
      dp.brand_colour_hex        AS brand_colour_hex,
      dp.brand_colour_confidence AS brand_colour_confidence,
      obs_v.value_numeric AS votes,
      obs_s.value_numeric AS vote_share_pct,
      p.sex             AS sex,
      p.age             AS age,
      p.education       AS education,
      p.profession      AS profession,
      ec.constituency_type AS constituency_type,
      ec.party_type     AS party_type
    FROM elections_candidacies ec
    JOIN dim_persons p ON p.person_id = ec.person_id
    JOIN dim_acs da ON da.ac_id = ec.ac_id
    LEFT JOIN dim_parties dp ON dp.party_id = ec.party_id
    LEFT JOIN election_results obs_v
      ON obs_v.entity_id = ec.candidacy_key
     AND obs_v.indicator_id = 'candidate-votes-polled'
     AND obs_v.period_label = ec.election_id
    LEFT JOIN election_results obs_s
      ON obs_s.entity_id = ec.candidacy_key
     AND obs_s.indicator_id = 'candidate-vote-share-pct'
     AND obs_s.period_label = ec.election_id
    WHERE da.state_code = ${sc}
      AND da.eci_no = ${eci_no}
      AND ec.election_id = ${evt}
    ORDER BY ec.rank
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
    FROM election_results
    WHERE entity_id = ${ac}
      AND period_label = ${evt}
      AND indicator_id LIKE 'ac-%'
  `);

  // Provenance: DISTINCT citations across every row that contributed to
  // this contest (AC-scope + candidate-scope). taxonomy.sources is the
  // canonical sources table under v2.0 (ADR-0032) — keyed on the citation
  // triple (producer, title, vintage). We project (url_main) and map it
  // into the legacy SourceRef shape the SourceList renderer already
  // understands; ``fetched_at`` is left empty because fetch telemetry is
  // operator state, not provenance, under the citation-ledger contract.
  const candidateIds = candidates
    .map((c) => sqlString(c.candidate_id))
    .join(", ");
  const sources = await query<SourceJoinRow>(`
    SELECT DISTINCT s.url_main
    FROM election_results o
    JOIN sources s ON s.source_id = o.source_id
    WHERE o.period_label = ${evt}
      AND (
        o.entity_id = ${ac}
        OR o.entity_id IN (${candidateIds})
      )
      AND s.url_main IS NOT NULL
      AND s.url_main <> ''
    ORDER BY s.url_main
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

  const candidates: CandidateResult[] = rows.candidates.map((r) => {
    // Bio columns: collapse to a single nullable object so the renderer
    // can guard with `{#if c.bio}` instead of probing six fields. `null`
    // when every bio column is NULL (the common case until a Statistical
    // Report adapter populates them); object when at least one is set.
    const hasBio =
      r.sex !== null || r.age !== null || r.education !== null ||
      r.profession !== null || r.constituency_type !== null ||
      r.party_type !== null;
    return {
      rank: Number(r.rank),
      name: r.candidate_name ?? "",
      party_id: r.party_id,
      party_eci_code: r.party_eci_code ?? null,
      party_short: r.party_short ?? r.party_id,
      votes: num(r.votes),
      vote_share_pct: num(r.vote_share_pct),
      is_winner: r.candidate_id === winnerCandidateId,
      brand_colour_hex: r.brand_colour_hex ?? null,
      brand_colour_confidence:
        r.brand_colour_confidence === "high" ||
        r.brand_colour_confidence === "medium" ||
        r.brand_colour_confidence === "low"
          ? r.brand_colour_confidence
          : null,
      bio: hasBio
        ? {
            sex: r.sex,
            age: r.age === null ? null : Number(r.age),
            education: r.education,
            profession: r.profession,
            constituency_type: r.constituency_type,
            party_type: r.party_type,
          }
        : null,
    };
  });

  const top_n_cutoff = candidates.length;
  const totalContested =
    acNum("ac-candidates-total") ?? candidates.length;
  const others = buildOthersBucket(
    candidates,
    totalContested,
    acNum("ac-others-votes"),
    acNum("ac-others-pct"),
  );

  const sources: SourceRef[] = rows.sources
    .filter((s) => !!s.url_main)
    .map((s) => ({
      url: s.url_main ?? "",
      // Citation ledger (v2.0) does not carry fetch telemetry —
      // ``fetched_at`` is intentionally empty; SourceList degrades to a
      // URL-only chip rather than misrepresenting an operator timestamp
      // as provenance. See ADR-0032.
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
    candidates_total: totalContested,
    winner: {
      name: winnerRow?.candidate_name ?? "",
      party_eci_code: winnerRow?.party_eci_code ?? null,
      party_short: winnerRow?.party_short ?? winnerRow?.party_id ?? "",
      votes: num(winnerRow?.votes),
      margin_votes: acNum("ac-margin-votes") ?? 0,
      margin_pct: acNum("ac-margin-pct") ?? 0,
      party_id: winnerRow?.party_id ?? null,
      brand_colour_hex: winnerRow?.brand_colour_hex ?? null,
      brand_colour_confidence:
        winnerRow?.brand_colour_confidence === "high" ||
        winnerRow?.brand_colour_confidence === "medium" ||
        winnerRow?.brand_colour_confidence === "low"
          ? winnerRow.brand_colour_confidence
          : null,
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
