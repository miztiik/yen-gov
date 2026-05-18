// Citizen view-model loader for the Settings page colour palette
// (PR-G / Phase 1.3c).
//
// Today's Settings page fetches parties.json across 5 hardcoded states. The
// new loader reads the canonical dim_parties table AND unions in the
// distinct short_name_key from observations for any party not in the dim
// (NOTA, IND, CPIM today). Net coverage is a strict superset of the legacy
// 5-state union — every party that has ever scored a party-totals row in
// the canonical store appears in the palette.

import { describeFailure, type LoaderResult } from "../loader-result";
import { query, registerTable } from "../duckdb";

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
  await Promise.all([
    registerTable("elections.observations"),
    registerTable("elections.dim_parties"),
  ]);

  const dim = await query<DimRow>(`
    SELECT eci_code, short_name, full_name, recognition
    FROM dim_parties
    WHERE short_name IS NOT NULL
  `);

  // Parties present in observations but absent from dim_parties.
  const fallback = await query<FallbackRow>(`
    SELECT DISTINCT regexp_extract(entity_id, '-PARTY-(.+)$', 1) AS short_name_key
    FROM observations
    WHERE entity_id LIKE 'IN-%-PARTY-%'
      AND regexp_extract(entity_id, '-PARTY-(.+)$', 1) NOT IN (
        SELECT short_name FROM dim_parties WHERE short_name IS NOT NULL
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
