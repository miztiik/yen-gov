// Canonical-store loader for the Psephlab what-if simulator.
//
// PR-R.1 (1.8e MIGRATE not retire). Tidy-first refactor: NEW module,
// side-by-side with the legacy `actuals.ts` sql.js loader. Returns the
// SAME `Tallies` shape so PR-R.2 can switch Psephlab.svelte + Compare.svelte
// at the call site with zero downstream change. PR-R.3 then deletes the
// legacy loader + `lib/sql.ts` + `backend/yen_gov/emit/sqlite.py` + the
// 41 `results.sqlite` files.
//
// Why a new file instead of edit-in-place: the legacy `actuals.ts` is a
// pure sql.js consumer (`db.exec()` + positional row arrays). The canonical
// path is DuckDB-WASM (`query<T>(sql)` returning JS objects). The two are
// different enough that a fork-then-delete arc is cleaner than an
// in-place rewrite, and it lets reviewers diff R.1 (purely additive)
// against R.2 (purely behavioural switch) against R.3 (purely subtractive).
//
// What is JOINed:
//   elections.dim_acs           — AC identity + display name
//   elections.dim_candidates    — per-contest candidate rows
//   elections.dim_parties       — party_eci_code + party_short
//   elections.election_results  — votes_polled (AC scope), candidate votes,
//                                 NOTA votes (synthesised as candidate rows
//                                 to match the legacy contract).
//
// SQL pattern mirrors `frontend/src/lib/explore/duckdb-views.ts`
// (the proven Explore-route migration, PR-L) and
// `frontend/src/lib/view-models/constituency.ts` (PR-E). Both surface
// `ac-votes-polled`, `ac-nota-votes`, `candidate-votes-polled` from the
// `election_results` long-format fact table.
//
// Test seam: the loader closes over `query` + `registerTable` from
// `../duckdb`. Tests `vi.mock("../duckdb", ...)` per the
// `view-models/constituency.test.ts` precedent — that IS the IO boundary
// per CLAUDE.md §15 carve-out (vitest cannot boot DuckDB-WASM; the real
// round-trip is asserted by Playwright in PR-R.2 against a real Parquet
// shard).

import { query, registerTable } from "../duckdb";
import type { AcTally, CandidateTally, Tallies } from "./types";

// ---------- Cache: identical-shape mirror of legacy actuals.ts ------------

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
  is_nota: number; // 0 or 1, matching legacy SQLite shape
}

// ---------- SQL composition -----------------------------------------------

function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

// DuckDB-WASM returns BIGINT as BigInt. Candidate vote counts in
// election_results.parquet are stored as DOUBLE (see canonical-store.md
// §11.1 — value_numeric is DOUBLE), and we CAST scope totals to BIGINT in
// the SQL itself. `Number(x ?? 0)` flattens both safely. Kept in one helper
// so a future BIGINT switch in the schema doesn't scatter coercions.
const num = (v: unknown): number => (v == null ? 0 : Number(v));

function buildConstituencySql(event: string, state_code: string): string {
  const evt = sqlString(event);
  const sc = sqlString(state_code);
  return `
    SELECT
      da.eci_no AS ac_eci_no,
      da.name   AS name,
      CAST(MAX(CASE WHEN o.indicator_id = 'ac-votes-polled' THEN o.value_numeric END) AS BIGINT) AS votes_polled
    FROM dim_acs da
    LEFT JOIN election_results o
      ON o.entity_id = da.ac_id
     AND o.period_label = ${evt}
    WHERE da.state_code = ${sc}
    GROUP BY da.eci_no, da.name
    ORDER BY da.eci_no
  `;
}

function buildCandidateSql(event: string, state_code: string): string {
  const evt = sqlString(event);
  const sc = sqlString(state_code);
  // The candidate SELECT is a UNION ALL of:
  //   (a) real candidates from dim_candidates × dim_parties × election_results
  //   (b) synthesised NOTA rows from ac-nota-votes (one per AC, when present)
  // Ordering ensures the legacy ORDER BY (ac_eci_no, rank) holds: NOTA rows
  // have rank NULL which sorts LAST per DuckDB ASC NULLS LAST default. The
  // legacy SQLite loader put NOTA at the end of each AC's candidate list,
  // so this preserves the contract.
  return `
    WITH cand_votes AS (
      SELECT
        o.entity_id AS candidate_id,
        MAX(CASE WHEN o.indicator_id = 'candidate-votes-polled' THEN o.value_numeric END) AS votes
      FROM election_results o
      WHERE o.period_label = ${evt}
        AND o.indicator_id = 'candidate-votes-polled'
      GROUP BY o.entity_id
    )
    SELECT
      da.eci_no                                       AS ac_eci_no,
      dc.rank                                         AS rank,
      dc.name                                         AS name,
      dp.eci_code                                     AS party_eci_code,
      -- party_short fallback chain (no-UNK-regression, PR-R.2):
      --   1. dim_parties.short_name when party_id is resolved to a real party
      --   2. dim_candidates.party_short_raw — verbatim ECI short — when
      --      party_id is the sentinel parties.IN.UNK (long-tail party not yet
      --      in canonical taxonomy). Citizens see "JNSRJP" not "UNK".
      --   3. literal 'UNK' as a last resort (should be unreachable —
      --      every UNK row is built with party_short_raw populated by the
      --      adapter at v1.1; this branch defends against pre-v1.1 rows
      --      that might survive a partial-corpus backfill).
      CASE
        WHEN dc.party_id = 'parties.IN.UNK'
          THEN COALESCE(dc.party_short_raw, dp.short_name, 'UNK')
        ELSE dp.short_name
      END                                             AS party_short,
      CAST(cv.votes AS BIGINT)                        AS votes,
      0                                               AS is_nota
    FROM dim_candidates dc
    JOIN dim_acs da          ON da.ac_id = dc.ac_id
    LEFT JOIN dim_parties dp ON dp.party_id = dc.party_id
    LEFT JOIN cand_votes cv  ON cv.candidate_id = dc.candidate_id
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
      1                                                                                      AS is_nota
    FROM dim_acs da
    JOIN election_results o
      ON o.entity_id = da.ac_id
     AND o.period_label = ${evt}
    WHERE da.state_code = ${sc}
      AND o.indicator_id = 'ac-nota-votes'
    GROUP BY da.eci_no
    HAVING MAX(CASE WHEN o.indicator_id = 'ac-nota-votes' THEN o.value_numeric END) IS NOT NULL

    ORDER BY ac_eci_no, rank
  `;
}

// ---------- Public API: SAME signature + return shape as legacy ----------

/**
 * Load a `Tallies` snapshot for one (event, state) via the canonical Parquet
 * store. Drop-in replacement for `psephlab/actuals.ts:loadActuals` — same
 * signature, same return shape, same per-(event, state) caching and
 * Object.freeze semantics. Switching the call site is a one-line import
 * change (PR-R.2).
 */
export function loadActuals(event: string, state: string): Promise<Tallies> {
  const k = key(event, state);
  const hit = cache.get(k);
  if (hit) return hit;

  const p = (async (): Promise<Tallies> => {
    // Register every Parquet view we need (idempotent per session).
    await Promise.all([
      registerTable("elections.election_results"),
      registerTable("elections.dim_acs"),
      registerTable("elections.dim_candidates"),
      registerTable("elections.dim_parties"),
    ]);

    const [constituencies, candidates] = await Promise.all([
      query<ConstituencyRow>(buildConstituencySql(event, state)),
      query<CandidateRow>(buildCandidateSql(event, state)),
    ]);

    const acs: AcTally[] = [];
    const ac_index = new Map<number, AcTally>();
    for (const row of constituencies) {
      const eci_no = Number(row.ac_eci_no);
      const ac: AcTally = {
        eci_no,
        name: String(row.name ?? ""),
        // votes_polled doubles as our electorate proxy until we ship a
        // separate electors column. Turnout-uplift mutations (deferred to
        // v2 per psephlab.md) will need a real value here. Same contract
        // as legacy actuals.ts.
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
      const c: CandidateTally = {
        party_eci_code: is_nota ? "NOTA" : (party_code ?? "IND"),
        party_short: party_short || (is_nota ? "NOTA" : "IND"),
        name,
        votes: num(row.votes),
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
 * Reset the per-module Tallies cache. NOT for production use — tests
 * call this between cases so cached promises from one case don't bleed
 * into the next.
 */
export function __resetForTests(): void {
  cache.clear();
}
