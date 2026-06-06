// Citizen view-model loader for the Settings page colour palette
// (PR-G / Phase 1.3c).
//
// Today's Settings page derives the citizen colour palette from every
// party in the canonical `dim_parties` view + any extras the historical
// election candidacies reveal. The X1a-followup flip swapped the
// candidacies source from `elections.election_results` (parquet) to the
// per-(state, year) `candidacies.csv` long-format store; in practice
// every party_id that appears in candidacies.csv ALSO exists in
// parties.csv (verified via repo audit 2026-06-06 against all 257
// candidacies files across 620 parties.csv rows -> ZERO orphans), so
// the fallback path now defensively guards against new gaps but
// returns no rows on today's data.

import { describeFailure, type LoaderResult } from "../loader-result";
import { query, registerCsvAsTable, registerCsvFile } from "../duckdb";
import { csvColumnsClause } from "../canonical/csv-columns";
import { DATA_BASE } from "../paths";
import {
  ASSEMBLY_CANDIDACIES_GLOB,
  PARLIAMENT_CANDIDACIES_GLOB,
} from "../canonical/election-csv-paths";

export interface PartiesPaletteEntry {
  /** The canonical eci_code if dim_parties has one; otherwise the
   *  short_name (Settings already tolerates fake codes for overrides). */
  eci_code: string;
  short_name: string;
  full_name: string | null;
  recognition?: string;
}

export interface PartiesPaletteViewModel {
  parties: PartiesPaletteEntry[];
}

interface DimRow {
  eci_code: string | null;
  short_name: string;
  full_name: string | null;
  recognition: string | null;
}

interface FallbackRow {
  short_name_key: string;
}

async function runQueries(): Promise<{
  dim: DimRow[];
  fallback: FallbackRow[];
}> {
  // Glob CSV reads to scan every per-(state, year) candidacies file in
  // one go. DuckDB's read_csv accepts a glob and unions across files
  // transparently.
  const assemblyGlobPath = ASSEMBLY_CANDIDACIES_GLOB;
  const parliamentGlobPath = PARLIAMENT_CANDIDACIES_GLOB;
  const assemblyGlobUrl = `${DATA_BASE}/${assemblyGlobPath.replace(/^datasets\//, "")}`;
  const parliamentGlobUrl = `${DATA_BASE}/${parliamentGlobPath.replace(/^datasets\//, "")}`;

  const [assemblyClause, parliamentClause] = await Promise.all([
    csvColumnsClause(assemblyGlobPath),
    csvColumnsClause(parliamentGlobPath),
    registerCsvAsTable("elections.dim_parties"),
  ]);

  const dim = await query<DimRow>(`
    SELECT eci_code, short_name, full_name, recognition
    FROM dim_parties
    WHERE short_name IS NOT NULL
  `);

  // Parties present in candidacies but absent from dim_parties. In
  // practice empty on today's data (parties.csv covers every
  // candidacies.csv party_id per repo audit 2026-06-06), but the
  // defensive guard surfaces any future drift as a fallback chip
  // rather than silently dropping the party.
  //
  // The candidacies row carries `party_id` (e.g. parties.IN.NOTA); the
  // legacy parquet pre-aggregated synthetic `IN-<state>-<event>-PARTY-<short>`
  // entity_ids and the fallback extracted the suffix. With the CSV path
  // we use the canonical `party_id` as the bare label when no
  // dim_parties row resolves; the in-practice empty result keeps the
  // visible delta from the legacy "CPIM/IND/NOTA" fallback list at
  // zero today.
  const fallback = await query<FallbackRow>(`
    SELECT DISTINCT c.party_id AS short_name_key
    FROM (
      SELECT party_id FROM read_csv('${assemblyGlobUrl}', ${assemblyClause}) WHERE party_id IS NOT NULL
      UNION ALL
      SELECT party_id FROM read_csv('${parliamentGlobUrl}', ${parliamentClause}) WHERE party_id IS NOT NULL
    ) c
    WHERE c.party_id NOT IN (
      SELECT party_id FROM dim_parties WHERE party_id IS NOT NULL
    )
  `);

  return { dim, fallback };
}

function assembleResult(rows: {
  dim: DimRow[];
  fallback: FallbackRow[];
}): PartiesPaletteViewModel {
  const seen = new Set<string>();
  const parties: PartiesPaletteEntry[] = [];

  for (const r of rows.dim) {
    if (seen.has(r.short_name)) continue;
    seen.add(r.short_name);
    parties.push({
      eci_code: r.eci_code ?? r.short_name,
      short_name: r.short_name,
      full_name: r.full_name,
      recognition: r.recognition ?? undefined,
    });
  }

  for (const r of rows.fallback) {
    if (!r.short_name_key || seen.has(r.short_name_key)) continue;
    seen.add(r.short_name_key);
    parties.push({
      eci_code: r.short_name_key,
      short_name: r.short_name_key,
      full_name: null,
    });
  }

  parties.sort((a, b) => a.short_name.localeCompare(b.short_name));
  return { parties };
}

export async function loadPartiesPalette(): Promise<
  LoaderResult<PartiesPaletteViewModel>
> {
  try {
    const rows = await runQueries();
    return { status: "ok", data: assembleResult(rows) };
  } catch (err) {
    return {
      status: "failed",
      reason: describeFailure(err),
      retry: () => loadPartiesPalette(),
    };
  }
}
