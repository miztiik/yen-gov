// Loader for the 2014 LS PC affidavit-enriched winner row.
//
// Reads the 4 new affidavit columns added by Row B of
// TODO/20260614-three-ephemeral-ingests-plan.md
//   - criminal_cases_declared
//   - total_assets_inr
//   - total_liabilities_inr
//   - declared_election_expense_inr
//
// from `datasets/elections/parliament/election=2014/candidacies.csv`,
// joined with the existing biographic columns (sex / age / education /
// profession). One row per (state_slug, eci_no) PC for the winner
// only (`result='won'`). The function intentionally returns nullables
// for every field — callers (the MP-panel mount in Constituency.svelte)
// render the panel ONLY when at least one numeric affidavit field is
// non-null, per the parent plan's "no panel when no data" rule.
//
// Loader-self-containment per user-memory PR #1027: this loader does
// its own DuckDB-WASM read and does not take resolver callbacks; the
// only test injection point is the `__resetForTests` cache reset.

import { query, registerCsvFile } from "../duckdb";
import { DATA_BASE } from "../paths";
import { csvColumnsClause } from "../canonical/csv-columns";

const CSV_PATH = "datasets/elections/parliament/election=2014/candidacies.csv";

export interface PcAffidavit2014 {
  /** "won" winner row identity. */
  readonly state_slug: string;
  readonly eci_no: number;
  readonly candidate_name: string | null;
  readonly party_id: string | null;
  readonly party_short_raw: string | null;
  /** Biographic columns already on candidacies.csv pre-Row B. */
  readonly sex: string | null;
  readonly age: number | null;
  readonly education: string | null;
  readonly profession: string | null;
  /** The four affidavit columns Row B added. */
  readonly criminal_cases_declared: number | null;
  readonly total_assets_inr: number | null;
  readonly total_liabilities_inr: number | null;
  readonly declared_election_expense_inr: number | null;
}

interface RawRow {
  state: string | null;
  constituency_no: number | bigint | null;
  candidate_name: string | null;
  party_id: string | null;
  party_short_raw: string | null;
  sex: string | null;
  age: number | bigint | null;
  education: string | null;
  profession: string | null;
  criminal_cases_declared: number | bigint | null;
  total_assets_inr: number | bigint | null;
  total_liabilities_inr: number | bigint | null;
  declared_election_expense_inr: number | bigint | null;
}

const CACHE = new Map<string, Promise<PcAffidavit2014 | null>>();

function cacheKey(state_slug: string, eci_no: number): string {
  return `${state_slug}::${eci_no}`;
}

/** Coerce a DuckDB-WASM-side numeric (number | bigint | null) to a
 *  plain JS number-or-null. Mirrors the project-wide `numOrNull`
 *  pattern (see view-models/election-results.ts). Returns null on
 *  publisher-blank cells; rejects NaN. */
function numOrNull(v: number | bigint | null): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === "bigint") return Number(v);
  return Number.isFinite(v) ? v : null;
}

/** Load the 2014 PC winner's affidavit row for (state_slug, eci_no).
 *  Returns null when no winner row matches OR every affidavit field
 *  is blank. Cached per (state, eci_no). */
export async function loadPcAffidavit2014(
  state_slug: string,
  eci_no: number,
): Promise<PcAffidavit2014 | null> {
  const k = cacheKey(state_slug, eci_no);
  const cached = CACHE.get(k);
  if (cached) return cached;
  const p = loadUncached(state_slug, eci_no);
  CACHE.set(k, p);
  p.catch(() => CACHE.delete(k));
  return p;
}

async function loadUncached(
  state_slug: string,
  eci_no: number,
): Promise<PcAffidavit2014 | null> {
  const url = `${DATA_BASE}/${CSV_PATH.replace(/^datasets\//, "")}`;
  const [clause] = await Promise.all([
    csvColumnsClause(CSV_PATH),
    registerCsvFile(url),
  ]);
  const sql = `
    SELECT
      state,
      constituency_no,
      candidate_name,
      party_id,
      party_short_raw,
      sex,
      age,
      education,
      profession,
      criminal_cases_declared,
      total_assets_inr,
      total_liabilities_inr,
      declared_election_expense_inr
    FROM read_csv('${url}', ${clause})
    WHERE state = '${state_slug.replace(/'/g, "''")}'
      AND constituency_no = ${eci_no}
      AND result = 'won'
    LIMIT 1
  `;
  const rows = await query<RawRow>(sql);
  if (rows.length === 0) return null;
  const r = rows[0];
  const out: PcAffidavit2014 = {
    state_slug,
    eci_no,
    candidate_name: r.candidate_name,
    party_id: r.party_id,
    party_short_raw: r.party_short_raw,
    sex: r.sex,
    age: numOrNull(r.age),
    education: r.education,
    profession: r.profession,
    criminal_cases_declared: numOrNull(r.criminal_cases_declared),
    total_assets_inr: numOrNull(r.total_assets_inr),
    total_liabilities_inr: numOrNull(r.total_liabilities_inr),
    declared_election_expense_inr: numOrNull(r.declared_election_expense_inr),
  };
  // The panel is only useful when at least one affidavit field is
  // populated; return null so the caller can skip mounting the panel
  // and avoid an "About this MP" header with no rows.
  if (
    out.criminal_cases_declared === null &&
    out.total_assets_inr === null &&
    out.total_liabilities_inr === null &&
    out.declared_election_expense_inr === null
  ) {
    return null;
  }
  return out;
}

/** Test-only: reset the module-level cache so each test starts fresh.
 *  NOT for production use. */
export function __resetForTests(): void {
  CACHE.clear();
}
